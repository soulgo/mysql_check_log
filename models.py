# -*- coding: utf-8 -*-
# 导入所需库
import pymysql # MySQL 数据库连接库
import logging # 日志库
from datetime import datetime # 导入 datetime 用于 add_user_activity 类型提示 (可选)
from config import DB_CONFIG # 从配置文件导入数据库连接信息

# 配置日志记录器
logger = logging.getLogger(__name__)

# --- 数据库连接 ---
def get_db_connection():
    """获取数据库连接"""
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG.get('port', 3306),
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset='utf8mb4'
        )
        logger.debug("数据库连接成功。")
        return conn
    except pymysql.MySQLError as e:
        logger.error(f"数据库连接失败: {e}")
        return None
    except KeyError as e:
        logger.error(f"数据库配置错误，缺少键: {e}")
        return None

# --- 数据库初始化 ---
def init_db():
    """初始化数据库，仅创建 user_activities 表"""
    conn = get_db_connection()
    if not conn:
        logger.error("无法连接到数据库，初始化失败。")
        return False
    try:
        with conn.cursor() as cursor:
            # !! 不再创建 mysql_servers 表 !!

            # user_activities 表 (使用代码逻辑期望的列名，包括 timestamp)
            # server_id 现在关联到 config.py 中 LOG_CONFIG 条目的 'id'
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS `user_activities` (
              `id` bigint(20) NOT NULL AUTO_INCREMENT COMMENT '活动ID',
              `server_id` int(11) NOT NULL COMMENT '关联到 config.py 中 LOG_CONFIG 的服务器 ID',
              `timestamp` datetime(6) NOT NULL COMMENT '活动发生时间(带微秒)',
              `user_name` varchar(100) DEFAULT NULL COMMENT '数据库用户名',
              `client_host` varchar(255) DEFAULT NULL COMMENT '客户端主机或IP',
              `db_name` varchar(100) DEFAULT NULL COMMENT '操作的数据库名',
              `thread_id` int(11) DEFAULT NULL COMMENT 'MySQL线程ID',
              `command_type` varchar(50) DEFAULT NULL COMMENT '原始命令类型(Connect, Query等)',
              `operation_type` varchar(50) DEFAULT NULL COMMENT '解析后的操作类型(SELECT, INSERT等)',
              `argument` text COMMENT '命令参数或SQL语句',
              `risk_level` enum('Low','Medium','High') DEFAULT 'Low' COMMENT '风险等级',
              `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
              PRIMARY KEY (`id`),
              KEY `idx_server_time` (`server_id`,`timestamp`),
              KEY `idx_user_time` (`user_name`,`timestamp`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户数据库活动记录';
            """)
            logger.info("user_activities 表检查/创建成功。")
        conn.commit()
        return True
    except pymysql.MySQLError as e:
        logger.error(f"数据库初始化时发生错误: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

# --- 数据操作函数 ---

# !! 移除 get_servers 和 get_server_by_id !!

# !! add_user_activity 保持不变 (它依赖传入的 server_id) !!
def add_user_activity(activity_data: dict): # 添加类型提示
    """将单条用户活动记录添加到数据库"""
    if not isinstance(activity_data, dict):
        logger.error(f"尝试添加无效的活动数据到数据库 (非字典): {activity_data}")
        return

    sql = """
    INSERT INTO user_activities
    (server_id, `timestamp`, user_name, client_host, db_name, thread_id, command_type, operation_type, argument, risk_level)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    conn = get_db_connection()
    if not conn:
        logger.error("添加用户活动失败：无法连接数据库。")
        return

    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, (
                activity_data.get('server_id'), # 这个 ID 来自 config.LOG_CONFIG
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
        conn.commit()
        logger.debug(f"成功添加活动记录: ServerID(Config)={activity_data.get('server_id')}, Thread={activity_data.get('thread_id')}")
    except pymysql.MySQLError as e:
        logger.error(f"向数据库插入活动记录时出错: {e} - 数据: {activity_data}")
        conn.rollback()
    except Exception as e:
        logger.error(f"添加活动到数据库时发生意外错误: {e} - 数据: {activity_data}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

# !! 移除 update_server_scan_time !!

# (get_user_activities, get_operation_stats 保持不变，它们基于 server_id 查询 user_activities)
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
            where_clauses.append("server_id = %s") # server_id 现在对应 config.py 中的 ID
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
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(count_sql, params)
            count_result = cursor.fetchone()
            if count_result: total = count_result.get('total', 0)
            if total > 0:
                cursor.execute(data_sql, data_params)
                results = cursor.fetchall()
                results = list(results) if results else []
        return results, total
    except pymysql.MySQLError as e:
        logger.error(f"获取用户活动记录时出错: {e}")
        return [], 0
    finally:
        if conn: conn.close()

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
            where_clauses.append("server_id = %s") # server_id 现在对应 config.py 中的 ID
            params.append(server_id)
        if start_date:
            where_clauses.append("`timestamp` >= %s")
            params.append(start_date)
        if end_date:
            where_clauses.append("`timestamp` <= %s")
            params.append(end_date)
        base_where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
        stats = {}
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            sql_total = f"SELECT COUNT(*) as total FROM user_activities WHERE {base_where_sql}"
            cursor.execute(sql_total, params)
            total_result = cursor.fetchone(); stats['total_count'] = total_result.get('total', 0) if total_result else 0
            sql_ops = f"SELECT operation_type, COUNT(*) as count FROM user_activities WHERE {base_where_sql} GROUP BY operation_type ORDER BY count DESC"
            cursor.execute(sql_ops, params); op_stats_raw = cursor.fetchall()
            stats['operation_types'] = [{'operation_type': row.get('operation_type', 'UNKNOWN') or 'UNKNOWN', 'count': row.get('count', 0)} for row in op_stats_raw]
            sql_risk = f"SELECT risk_level, COUNT(*) as count FROM user_activities WHERE {base_where_sql} GROUP BY risk_level ORDER BY FIELD(risk_level, 'High', 'Medium', 'Low')"
            cursor.execute(sql_risk, params); risk_stats_raw = cursor.fetchall()
            stats['risk_levels'] = [{'risk_level': row.get('risk_level', 'Low') or 'Low', 'count': row.get('count', 0)} for row in risk_stats_raw]
            sql_hourly = f"SELECT HOUR(`timestamp`) as hour, COUNT(*) as count FROM user_activities WHERE {base_where_sql} GROUP BY hour ORDER BY hour ASC"
            cursor.execute(sql_hourly, params); hourly_stats_raw = cursor.fetchall()
            hourly_stats = {hour: 0 for hour in range(24)}
            for row in hourly_stats_raw:
                hour = row.get('hour');
                if hour is not None: hourly_stats[hour] = row.get('count', 0)
            stats['hourly_distribution'] = hourly_stats
            sql_users = f"SELECT user_name, COUNT(*) as count FROM user_activities WHERE {base_where_sql} AND user_name IS NOT NULL AND user_name != '' GROUP BY user_name ORDER BY count DESC LIMIT 10"
            cursor.execute(sql_users, params); user_stats_raw = cursor.fetchall()
            stats['top_users'] = [{'user_name': row.get('user_name', 'UNKNOWN') or 'UNKNOWN', 'count': row.get('count', 0)} for row in user_stats_raw]
        return stats
    except pymysql.MySQLError as e:
        logger.error(f"获取操作统计信息时出错: {e}")
        return {}
    except Exception as e:
        logger.exception(f"获取操作统计信息时发生意外错误: {e}")
        return {}
    finally:
        if conn: conn.close()
