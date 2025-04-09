# -*- coding: utf-8 -*-
# 导入所需库
import pymysql
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from config import DB_CONFIG
import json
import time
import copy
from config import APP_CONFIG

# 配置日志记录器
logger = logging.getLogger(__name__)

# --- 数据库连接 ---
def get_db_connection():
    """获取数据库连接"""
    try:
        # 使用pymysql连接MySQL数据库
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        logger.debug("数据库连接成功。")
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None

# --- 数据库初始化 ---
def init_db():
    """初始化数据库，创建 user_activities 和 server_scan_status 表"""
    logger.info("初始化数据库...")
    conn = get_db_connection()
    if not conn:
        logger.error("无法连接到数据库，初始化失败。")
        return False
    try:
        with conn.cursor() as cursor:
            # 创建用户活动表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_activities (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                server_id INT NOT NULL,
                `timestamp` DATETIME(6) NOT NULL,
                user_name VARCHAR(100),
                client_host VARCHAR(255),
                db_name VARCHAR(100),
                thread_id INT,
                command_type VARCHAR(50),
                operation_type VARCHAR(50),
                argument TEXT,
                risk_level ENUM('Low','Medium','High') DEFAULT 'Low',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_server_time(server_id, `timestamp`),
                INDEX idx_user_time(user_name, `timestamp`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
            ''')
            
            # 创建服务器扫描记录表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_scan_records (
                server_id INT PRIMARY KEY,
                last_scan_time DATETIME(6) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
            ''')
            
            # 创建服务器配置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_configs (
                server_id INT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                host VARCHAR(255) NOT NULL,
                port INT DEFAULT 22,
                user VARCHAR(100) NOT NULL,
                password VARCHAR(255),
                ssh_key_path VARCHAR(255),
                general_log_path VARCHAR(255),
                binlog_path VARCHAR(255),
                enable_general_log TINYINT(1) DEFAULT 1,
                enable_binlog TINYINT(1) DEFAULT 0
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
            ''')
            
            # 创建系统设置表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_settings (
                `key` VARCHAR(50) PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
            ''')
        
        conn.commit()
        
        # 初始化服务器配置（如果为空）
        init_server_configs()
        
        # 初始化系统设置（如果为空）
        init_system_settings()
        
        logger.info("数据库初始化完成")
        return True
    except Exception as e:
        logger.error(f"初始化数据库时出错: {e}")
        return False
    finally:
        if conn:
            conn.close()

def init_server_configs():
    """初始化服务器配置（仅当表为空时）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 检查是否已有配置
            cursor.execute('SELECT COUNT(*) as count FROM server_configs')
            result = cursor.fetchone()
            if result['count'] == 0:
                # 表为空，创建一个默认服务器配置
                server_id = 1
                cursor.execute('''
                INSERT INTO server_configs (
                    server_id, name, host, port, user, password, ssh_key_path,
                    general_log_path, binlog_path, enable_general_log, enable_binlog
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (
                    server_id,
                    'MySQL服务器1',
                    '127.0.0.1',
                    22,
                    'root',
                    '',
                    '',
                    '/var/log/mysql',
                    '',
                    1,
                    0
                ))
                conn.commit()
                logger.info("创建了默认服务器配置")
    except Exception as e:
        logger.error(f"初始化服务器配置时出错: {e}")
    finally:
        if conn:
            conn.close()

def init_system_settings():
    """初始化系统设置（如果表为空）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 检查是否已有设置
            cursor.execute('SELECT COUNT(*) as count FROM system_settings')
            result = cursor.fetchone()
            if result['count'] == 0:
                # 表为空，从 APP_CONFIG 导入设置
                now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
                
                # 导入风险操作规则
                risk_operations = APP_CONFIG.get('RISK_OPERATIONS', {})
                if risk_operations:
                    cursor.execute(
                        'INSERT INTO system_settings (`key`, value, updated_at) VALUES (%s, %s, %s)',
                        ('RISK_OPERATIONS', json.dumps(risk_operations), now)
                    )
                
                # 导入写入风险级别
                write_risk_levels = APP_CONFIG.get('WRITE_RISK_LEVELS', ['High', 'Medium'])
                if write_risk_levels:
                    cursor.execute(
                        'INSERT INTO system_settings (`key`, value, updated_at) VALUES (%s, %s, %s)',
                        ('WRITE_RISK_LEVELS', json.dumps(write_risk_levels), now)
                    )
                
                conn.commit()
                logger.info("从 APP_CONFIG 初始化了系统设置")
    except Exception as e:
        logger.error(f"初始化系统设置时出错: {e}")
    finally:
        if conn:
            conn.close()

# --- 数据操作函数 ---

def add_user_activity(activity_data: dict):
    """将单条用户活动记录添加到数据库 (调用批量版本)"""
    add_user_activities_batch([activity_data])

def add_user_activities_batch(activities: List[Dict[str, Any]]):
    """将一批用户活动记录批量添加到数据库"""
    if not activities:
        return

    sql = """
    INSERT INTO user_activities
    (server_id, `timestamp`, user_name, client_host, db_name, thread_id, command_type, operation_type, argument, risk_level)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    conn = get_db_connection()
    if not conn:
        logger.error("批量添加用户活动失败：无法连接数据库。")
        return

    data_to_insert = []
    for activity_data in activities:
        if isinstance(activity_data, dict):
            data_to_insert.append((
                activity_data.get('server_id'),
                activity_data.get('timestamp'),
                activity_data.get('user_name'),
                activity_data.get('client_host'),
                activity_data.get('db_name'),
                activity_data.get('thread_id'),
                activity_data.get('command_type'),
                activity_data.get('operation_type'),
                activity_data.get('argument'),
                activity_data.get('risk_level', 'Low')
            ))
        else:
            logger.warning(f"批量插入时发现无效的活动数据 (非字典): {activity_data}")

    if not data_to_insert:
        logger.warning("批量插入调用时没有有效的活动数据。")
        if conn: conn.close() # 关闭连接如果无数据插入
        return

    try:
        with conn.cursor() as cursor:
            cursor.executemany(sql, data_to_insert)
            conn.commit()
            logger.info(f"成功批量插入 {len(data_to_insert)} 条活动记录。")
    except Exception as e:
        logger.error(f"批量插入活动记录到数据库时出错: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

def get_last_scan_time(server_id: int) -> Optional[datetime]:
    """获取指定服务器的上次扫描时间 (UTC)"""
    if server_id is None:
        return None
    sql = "SELECT last_scan_time FROM server_scan_records WHERE server_id = %s"
    conn = get_db_connection()
    if not conn:
        return None
    last_time = None
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, (server_id,))
            result = cursor.fetchone()
            if result and result['last_scan_time'] is not None:
                # 确保返回的是带 UTC 时区的 datetime 对象
                last_time_naive = result['last_scan_time']
                last_time = last_time_naive.replace(tzinfo=timezone.utc)
                logger.debug(f"获取到服务器 {server_id} 的上次扫描时间: {last_time}")
            else:
                logger.info(f"未找到服务器 {server_id} 的上次扫描时间记录，将进行全量扫描。")
    except Exception as e:
        logger.error(f"获取服务器 {server_id} 上次扫描时间时出错: {e}")
    finally:
        if conn:
            conn.close()
    return last_time

def update_last_scan_time(server_id: int, scan_time: datetime):
    """更新或插入指定服务器的最后扫描时间 (确保传入 UTC 时间)"""
    if server_id is None or scan_time is None:
        return
    # 确保 scan_time 是 naive 或者已经是 UTC
    if scan_time.tzinfo is not None and scan_time.tzinfo != timezone.utc:
        scan_time = scan_time.astimezone(timezone.utc)
    # 存入数据库时通常不带时区信息 (或数据库自动处理)
    scan_time_naive = scan_time.replace(tzinfo=None)

    sql = """
    INSERT INTO server_scan_records (server_id, last_scan_time)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE last_scan_time = VALUES(last_scan_time)
    """
    conn = get_db_connection()
    if not conn:
        logger.error(f"更新服务器 {server_id} 扫描时间失败：无法连接数据库。")
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, (server_id, scan_time_naive))
        conn.commit()
        logger.info(f"服务器 {server_id} 的最后扫描时间已更新为 {scan_time} (UTC)。")
    except Exception as e:
        logger.error(f"更新服务器 {server_id} 扫描时间时出错: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

def get_user_activities(server_id=None, start_date=None, end_date=None, operation_type=None, risk_level=None, user_name=None, limit=1000, offset=0):
    """根据筛选条件获取用户活动记录列表"""
    conn = get_db_connection()
    if not conn:
        logger.error("获取用户活动失败：无法连接数据库。")
        return [], 0
    try:
        where_clauses = []
        params = []
        if server_id:
            where_clauses.append("server_id = %s")
            params.append(server_id)
        if start_date:
            where_clauses.append("`timestamp` >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("`timestamp` <= %s")
            params.append(end_date)
        if operation_type:
            where_clauses.append("operation_type = %s")
            params.append(operation_type)
        if risk_level:
            where_clauses.append("risk_level = %s")
            params.append(risk_level)
        if user_name:
            where_clauses.append("user_name LIKE %s")
            params.append(f"%{user_name}%")

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        count_sql = f"SELECT COUNT(*) as total FROM user_activities WHERE {where_sql}"
        data_sql = f"""
        SELECT id, server_id, `timestamp` as activity_time, user_name, client_host, db_name, thread_id, command_type, operation_type, argument, risk_level
        FROM user_activities WHERE {where_sql} ORDER BY `timestamp` DESC LIMIT %s OFFSET %s
        """
        data_params = params + [limit, offset]
        total = 0
        results = []

        with conn.cursor() as cursor:
            cursor.execute(count_sql, params)
            count_result = cursor.fetchone()
            if count_result:
                total = count_result['total']
            if total > 0:
                cursor.execute(data_sql, data_params)
                results = cursor.fetchall()
                results = list(results) if results else []
        return results, total
    except Exception as e:
        logger.error(f"获取用户活动记录时出错: {e}")
        return [], 0
    finally:
        if conn:
            conn.close()

def get_operation_stats(server_id=None, start_date=None, end_date=None):
    """获取操作统计信息"""
    conn = get_db_connection()
    if not conn:
        logger.error("获取统计信息失败：无法连接数据库。")
        return {}
    try:
        where_clauses = []
        params = []
        if server_id:
            where_clauses.append("server_id = %s")
            params.append(server_id)
        if start_date:
            where_clauses.append("`timestamp` >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("`timestamp` <= %s")
            params.append(end_date)
        base_where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        stats = {}

        with conn.cursor() as cursor:
            # 1. 总操作数
            sql_total = f"SELECT COUNT(*) as total FROM user_activities WHERE {base_where_sql}"
            cursor.execute(sql_total, params)
            total_result = cursor.fetchone()
            stats['total_count'] = total_result['total'] if total_result else 0

            # 2. 按操作类型统计
            sql_ops = f"SELECT operation_type, COUNT(*) as count FROM user_activities WHERE {base_where_sql} GROUP BY operation_type ORDER BY count DESC"
            cursor.execute(sql_ops, params)
            op_stats_raw = cursor.fetchall()
            stats['operation_types'] = [{'operation_type': row.get('operation_type', 'UNKNOWN') or 'UNKNOWN', 'count': row.get('count', 0)} for row in op_stats_raw]

            # 3. 按风险等级统计
            sql_risk = f"SELECT risk_level, COUNT(*) as count FROM user_activities WHERE {base_where_sql} GROUP BY risk_level ORDER BY FIELD(risk_level, 'High', 'Medium', 'Low')"
            cursor.execute(sql_risk, params)
            risk_stats_raw = cursor.fetchall()
            stats['risk_levels'] = [{'risk_level': row.get('risk_level', 'Low') or 'Low', 'count': row.get('count', 0)} for row in risk_stats_raw]

            # 4. 按小时分布统计 (保持修正后的格式)
            sql_hourly = f"SELECT HOUR(`timestamp`) as hour, COUNT(*) as count FROM user_activities WHERE {base_where_sql} GROUP BY hour ORDER BY hour ASC"
            cursor.execute(sql_hourly, params)
            hourly_stats_raw = cursor.fetchall()
            hourly_stats = {hour_key: 0 for hour_key in range(24)}
            for row in hourly_stats_raw:
                hour = row.get('hour')
                if hour is not None:
                    hourly_stats[hour] = row.get('count', 0)
            stats['hourly_distribution'] = hourly_stats # 赋值在循环外

            # 5. Top N 用户统计
            sql_users = f"SELECT user_name, COUNT(*) as count FROM user_activities WHERE {base_where_sql} AND user_name IS NOT NULL AND user_name != '' GROUP BY user_name ORDER BY count DESC LIMIT 10"
            cursor.execute(sql_users, params)
            user_stats_raw = cursor.fetchall()
            stats['top_users'] = [{'user_name': row.get('user_name', 'UNKNOWN') or 'UNKNOWN', 'count': row.get('count', 0)} for row in user_stats_raw]

        return stats
    except Exception as e:
        logger.error(f"获取操作统计信息时出错: {e}")
        return {}
    finally:
        if conn:
            conn.close()

# --- 服务器配置管理函数 ---
def get_all_servers():
    """获取所有服务器配置"""
    conn = get_db_connection()
    if not conn:
        logger.error("获取服务器配置失败：无法连接数据库。")
        return []
    
    try:
        servers = []
        with conn.cursor() as cursor:
            cursor.execute('''
            SELECT server_id, name, host, port, user, 
                   CASE WHEN password IS NOT NULL AND password != '' THEN 1 ELSE 0 END as has_password,
                   CASE WHEN ssh_key_path IS NOT NULL AND ssh_key_path != '' THEN 1 ELSE 0 END as has_ssh_key,
                   enable_general_log, enable_binlog
            FROM server_configs
            ORDER BY server_id
            ''')
            results = cursor.fetchall()
        
            for row in results:
                servers.append({
                    'server_id': row['server_id'],
                    'name': row['name'],
                    'host': row['host'],
                    'port': row['port'],
                    'user': row['user'],
                    'has_password': bool(row['has_password']),
                    'has_ssh_key': bool(row['has_ssh_key']),
                    'enable_general_log': bool(row['enable_general_log']),
                    'enable_binlog': bool(row['enable_binlog'])
                })
        
        return servers
    except Exception as e:
        logger.error(f"获取服务器配置列表时出错: {e}")
        return []
    finally:
        if conn:
            conn.close()

def get_server_by_id(server_id):
    """获取指定ID的服务器配置"""
    conn = get_db_connection()
    if not conn:
        logger.error(f"获取服务器配置失败：无法连接数据库。")
        return None
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('''
            SELECT server_id, name, host, port, user, 
                   CASE WHEN password IS NOT NULL AND password != '' THEN 1 ELSE 0 END as has_password,
                   CASE WHEN ssh_key_path IS NOT NULL AND ssh_key_path != '' THEN 1 ELSE 0 END as has_ssh_key,
                   general_log_path, binlog_path, enable_general_log, enable_binlog
            FROM server_configs WHERE server_id = %s
            ''', (server_id,))
            result = cursor.fetchone()
        
            if result:
                return {
                    'server_id': result['server_id'],
                    'name': result['name'],
                    'host': result['host'],
                    'port': result['port'],
                    'user': result['user'],
                    'has_password': bool(result['has_password']),
                    'has_ssh_key': bool(result['has_ssh_key']),
                    'general_log_path': result['general_log_path'],
                    'binlog_path': result['binlog_path'],
                    'enable_general_log': bool(result['enable_general_log']),
                    'enable_binlog': bool(result['enable_binlog'])
                }
            return None
    except Exception as e:
        logger.error(f"获取服务器配置失败: {e}")
        return None
    finally:
        if conn:
            conn.close()

def get_server_full_config(server_id):
    """获取服务器完整配置（包括密码/密钥）"""
    conn = get_db_connection()
    if not conn:
        logger.error(f"获取服务器配置失败：无法连接数据库。")
        return None
    
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT * FROM server_configs WHERE server_id = %s', (server_id,))
            result = cursor.fetchone()
        
            if result:
                return {
                    'server_id': result['server_id'],
                    'name': result['name'],
                    'host': result['host'],
                    'port': result['port'],
                    'user': result['user'],
                    'password': result['password'],
                    'ssh_key_path': result['ssh_key_path'],
                    'general_log_path': result['general_log_path'],
                    'binlog_path': result['binlog_path'],
                    'enable_general_log': bool(result['enable_general_log']),
                    'enable_binlog': bool(result['enable_binlog'])
                }
            return None
    except Exception as e:
        logger.error(f"获取服务器完整配置(ID:{server_id})时出错: {e}")
        return None
    finally:
        if conn:
            conn.close()

def add_server(server_data):
    """添加新服务器配置"""
    conn = get_db_connection()
    if not conn:
        logger.error("添加服务器配置失败：无法连接数据库。")
        return None
    
    try:
        # 检查需要的必要字段
        required_fields = ['name', 'host', 'user']
        for field in required_fields:
            if field not in server_data:
                logger.error(f"添加服务器配置失败: 缺少必要字段 '{field}'")
                return False
        
        # 获取当前最大server_id
        with conn.cursor() as cursor:
            cursor.execute('SELECT MAX(server_id) as max_id FROM server_configs')
            result = cursor.fetchone()
            max_id = result['max_id'] if result and result['max_id'] is not None else 0
            server_id = max_id + 1
        
            # 插入新配置
            cursor.execute('''
            INSERT INTO server_configs (
                server_id, name, host, port, user, password, ssh_key_path,
                general_log_path, binlog_path, enable_general_log, enable_binlog
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                server_id,
                server_data.get('name'),
                server_data.get('host'),
                server_data.get('port', 22),
                server_data.get('user'),
                server_data.get('password', ''),
                server_data.get('ssh_key_path', ''),
                server_data.get('general_log_path', ''),
                server_data.get('binlog_path', ''),
                1 if server_data.get('enable_general_log', True) else 0,
                1 if server_data.get('enable_binlog', False) else 0
            ))
        
        conn.commit()
        logger.info(f"已添加新的服务器配置 ID:{server_id}")
        return server_id
    except Exception as e:
        logger.error(f"添加服务器配置时出错: {e}")
        conn.rollback()
        return None
    finally:
        if conn:
            conn.close()

def update_server(server_id, server_data):
    """更新服务器配置"""
    conn = get_db_connection()
    if not conn:
        logger.error("更新服务器配置失败：无法连接数据库。")
        return False
    
    try:
        # 检查服务器是否存在
        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as count FROM server_configs WHERE server_id = %s', (server_id,))
            result = cursor.fetchone()
            if not result or result['count'] == 0:
                logger.error(f"更新服务器配置失败: ID:{server_id} 不存在")
                return False
            
            # 更新配置
            cursor.execute('''
            UPDATE server_configs SET
                name = %s,
                host = %s,
                port = %s,
                user = %s,
                password = CASE WHEN %s = '' THEN password ELSE %s END,
                ssh_key_path = CASE WHEN %s = '' THEN ssh_key_path ELSE %s END,
                general_log_path = %s,
                binlog_path = %s,
                enable_general_log = %s,
                enable_binlog = %s
            WHERE server_id = %s
            ''', (
                server_data.get('name'),
                server_data.get('host'),
                server_data.get('port', 22),
                server_data.get('user'),
                server_data.get('password', ''),
                server_data.get('password', ''),
                server_data.get('ssh_key_path', ''),
                server_data.get('ssh_key_path', ''),
                server_data.get('general_log_path', ''),
                server_data.get('binlog_path', ''),
                1 if server_data.get('enable_general_log', True) else 0,
                1 if server_data.get('enable_binlog', False) else 0,
                server_id
            ))
        
        conn.commit()
        logger.info(f"已更新服务器配置 ID:{server_id}")
        return True
    except Exception as e:
        logger.error(f"更新服务器配置时出错: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def delete_server(server_id):
    """删除服务器配置"""
    conn = get_db_connection()
    if not conn:
        logger.error("删除服务器配置失败：无法连接数据库。")
        return False
    
    try:
        # 检查服务器是否存在
        with conn.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) as count FROM server_configs WHERE server_id = %s', (server_id,))
            result = cursor.fetchone()
            if not result or result['count'] == 0:
                logger.error(f"删除服务器配置失败: ID:{server_id} 不存在")
                return False
            
            # 删除配置
            cursor.execute('DELETE FROM server_configs WHERE server_id = %s', (server_id,))
            
            # 同时删除相关的扫描记录
            cursor.execute('DELETE FROM server_scan_records WHERE server_id = %s', (server_id,))
        
        conn.commit()
        logger.info(f"已删除服务器配置 ID:{server_id}")
        return True
    except Exception as e:
        logger.error(f"删除服务器配置时出错: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# --- 系统设置管理函数 ---
def get_system_setting(key):
    """获取系统设置值"""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor() as cursor:
            cursor.execute('SELECT value FROM system_settings WHERE `key` = %s', (key,))
            result = cursor.fetchone()
            
            if result:
                # 尝试解析JSON
                try:
                    return json.loads(result['value'])
                except:
                    # 如果无法解析，直接返回原始值
                    return result['value']
        return None
    except Exception as e:
        logger.error(f"获取系统设置时出错: {key}, {e}")
        return None
    finally:
        if conn:
            conn.close()

def update_system_setting(key, value):
    """更新系统设置值"""
    conn = get_db_connection()
    if not conn:
        return False
    try:
        # 将对象/列表转换为JSON字符串
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)
        
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        
        with conn.cursor() as cursor:
            # 检查键是否存在
            cursor.execute('SELECT COUNT(*) as count FROM system_settings WHERE `key` = %s', (key,))
            result = cursor.fetchone()
            exists = result['count'] > 0 if result else False
            
            if exists:
                # 更新现有记录
                cursor.execute(
                    'UPDATE system_settings SET value = %s, updated_at = %s WHERE `key` = %s',
                    (value_str, now, key)
                )
            else:
                # 插入新记录
                cursor.execute(
                    'INSERT INTO system_settings (`key`, value, updated_at) VALUES (%s, %s, %s)',
                    (key, value_str, now)
                )
        
        conn.commit()
        logger.info(f"已更新系统设置: {key}")
        return True
    except Exception as e:
        logger.error(f"更新系统设置时出错: {key}, {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()
