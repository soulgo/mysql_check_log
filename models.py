# -*- coding: utf-8 -*-
# 导入所需库
import pymysql
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from config import DB_CONFIG

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
    """初始化数据库，创建 user_activities 和 server_scan_status 表"""
    conn = get_db_connection()
    if not conn:
        logger.error("无法连接到数据库，初始化失败。")
        return False
    try:
        with conn.cursor() as cursor:
            # user_activities 表
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

            # server_scan_status 表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS `server_scan_status` (
              `server_id` int(11) NOT NULL COMMENT '关联到 config.py 中 LOG_CONFIG 的服务器 ID',
              `last_scan_time` datetime(6) NULL DEFAULT NULL COMMENT '此服务器上次成功扫描完成的时间 (UTC)',
              PRIMARY KEY (`server_id`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='记录服务器扫描状态';
            """)
            logger.info("server_scan_status 表检查/创建成功。")

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
            inserted_count = cursor.executemany(sql, data_to_insert)
        conn.commit()
        logger.info(f"成功批量插入 {inserted_count}/{len(data_to_insert)} 条活动记录。")
    except pymysql.MySQLError as e:
        logger.error(f"批量插入活动记录到数据库时出错: {e}")
        conn.rollback()
    except Exception as e:
        logger.error(f"批量插入活动到数据库时发生意外错误: {e} - 前几条数据: {activities[:2]}...")
        conn.rollback()
    finally:
        if conn:
            conn.close()

def get_last_scan_time(server_id: int) -> Optional[datetime]:
    """获取指定服务器的上次扫描时间 (UTC)"""
    if server_id is None:
        return None
    sql = "SELECT last_scan_time FROM server_scan_status WHERE server_id = %s"
    conn = get_db_connection()
    if not conn:
        return None
    last_time = None
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, (server_id,))
            result = cursor.fetchone()
            if result and result[0] is not None:
                # 确保返回的是带 UTC 时区的 datetime 对象
                last_time_naive = result[0]
                last_time = last_time_naive.replace(tzinfo=timezone.utc)
                logger.debug(f"获取到服务器 {server_id} 的上次扫描时间: {last_time}")
            else:
                logger.info(f"未找到服务器 {server_id} 的上次扫描时间记录，将进行全量扫描。")
    except pymysql.MySQLError as e:
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
    INSERT INTO server_scan_status (server_id, last_scan_time)
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
    except pymysql.MySQLError as e:
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

        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(count_sql, params)
            count_result = cursor.fetchone()
            if count_result:
                total = count_result.get('total', 0)
            if total > 0:
                cursor.execute(data_sql, data_params)
                results = cursor.fetchall()
                results = list(results) if results else []
        return results, total
    except pymysql.MySQLError as e:
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

        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # 1. 总操作数
            sql_total = f"SELECT COUNT(*) as total FROM user_activities WHERE {base_where_sql}"
            cursor.execute(sql_total, params)
            total_result = cursor.fetchone()
            stats['total_count'] = total_result.get('total', 0) if total_result else 0

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
    except pymysql.MySQLError as e:
        logger.error(f"获取操作统计信息时出错: {e}")
        return {}
    except Exception as e:
        logger.exception(f"获取操作统计信息时发生意外错误: {e}")
        return {}
    finally:
        if conn:
            conn.close()
