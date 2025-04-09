#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 导入所需库
import re
import paramiko
import logging
from datetime import datetime, timezone, timedelta # 引入 timedelta
import pytz # 确保 pytz 用于时区处理
import posixpath # 用于处理远程路径
from typing import List, Dict, Any, Optional, Generator
# 从 config 导入APP_CONFIG
from config import APP_CONFIG
# 从 models 导入需要的函数
from models import add_user_activities_batch, get_last_scan_time, update_last_scan_time, get_all_servers, get_server_full_config, get_system_setting

# 配置日志记录器
logger = logging.getLogger(__name__)

# --- 常量 ---
BATCH_INSERT_SIZE = 500 # 定义批量插入的大小

# --- 正则表达式模式 ---
pattern_new = re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\t *(\d+)\s+(Query|Connect|Init DB|Quit|Prepare|Execute|Close stmt|Change user|Field List)\t(.*)')
connect_pattern = re.compile(r'([^@]+)@([^ ]+)(?: on (\S*))?')

# --- 辅助函数 ---
def determine_operation_type(sql):
    """根据 SQL 语句判断操作类型"""
    sql_upper = sql.strip().upper()
    if sql_upper.startswith(('SELECT', 'SHOW', 'DESC', 'EXPLAIN')): return 'SELECT'
    elif sql_upper.startswith(('INSERT', 'REPLACE')): return 'INSERT'
    elif sql_upper.startswith('UPDATE'): return 'UPDATE'
    elif sql_upper.startswith('DELETE'): return 'DELETE'
    elif sql_upper.startswith(('CREATE', 'ALTER', 'DROP', 'TRUNCATE')): return 'DDL'
    elif sql_upper.startswith(('GRANT', 'REVOKE', 'SET PASSWORD')): return 'DCL'
    elif sql_upper.startswith(('COMMIT', 'ROLLBACK', 'START TRANSACTION', 'SAVEPOINT')): return 'TCL'
    elif sql_upper.startswith('USE '): return 'USE_DB'
    return 'OTHER'

def determine_risk_level(operation_type, argument):
    """根据配置 (结构化 RISK_OPERATIONS) 判断操作的风险等级"""
    risk_definitions = APP_CONFIG.get('RISK_OPERATIONS', {})
    argument_lower = argument.lower()
    # 优先检查 High risk
    for rule in risk_definitions.get('High', []):
        rule_type = rule.get('type', '').upper()
        rule_keyword = rule.get('keyword', '').lower()
        type_match = (not rule_type or operation_type.upper() == rule_type)
        keyword_match = (not rule_keyword or rule_keyword in argument_lower)
        if type_match and keyword_match: return 'High'
    # 检查 Medium risk
    for rule in risk_definitions.get('Medium', []):
        rule_type = rule.get('type', '').upper()
        rule_keyword = rule.get('keyword', '').lower()
        type_match = (not rule_type or operation_type.upper() == rule_type)
        keyword_match = (not rule_keyword or rule_keyword in argument_lower)
        if type_match and keyword_match: return 'Medium'
    # 检查 Low risk
    for rule in risk_definitions.get('Low', []):
        rule_type = rule.get('type', '').upper()
        rule_keyword = rule.get('keyword', '').lower()
        type_match = (not rule_type or operation_type.upper() == rule_type)
        keyword_match = (not rule_keyword or rule_keyword in argument_lower)
        if type_match and keyword_match: return 'Low'
    # 默认 Low
    return 'Low'

def create_activity_entry(server_id, timestamp_str, user_name, client_host, db_name, thread_id, command, argument):
    """创建一个代表用户活动日志条目的字典"""
    try:
        timestamp_dt = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        operation_type = determine_operation_type(argument) if command == 'Query' else command.upper()
        risk_level = determine_risk_level(operation_type, argument)
        return {'server_id': server_id, 'timestamp': timestamp_dt, 'user_name': user_name, 'client_host': client_host, 'db_name': db_name, 'thread_id': thread_id, 'command_type': command, 'operation_type': operation_type, 'argument': argument, 'risk_level': risk_level }
    except ValueError as e: logger.error(f"解析时间戳错误 '{timestamp_str}': {e}"); return None
    except Exception as e: logger.error(f"为线程 {thread_id} 创建活动条目时出错: {e}"); return None

# --- 核心解析逻辑 ---
def parse_general_log_stream(sftp_file: paramiko.SFTPFile, server_id: int) -> Generator[Dict[str, Any], None, None]:
    """ 流式解析打开的 SFTP general log 文件。 """
    thread_user_map = {}
    line_count = 0
    parsed_count = 0
    try:
        for line_bytes in sftp_file:
            line_count += 1
            try: line = line_bytes.decode('utf-8', errors='ignore').strip()
            except UnicodeDecodeError: logger.warning(f"解码第 {line_count} 行时出错，已跳过。"); continue
            if not line: continue
            match = pattern_new.match(line)
            if not match: continue
            timestamp_str, thread_id_str, command, argument = match.groups()
            thread_id = int(thread_id_str); argument = argument.strip(); activity = None
            # --- 处理命令类型 ---
            if command == 'Connect':
                user = 'unknown'; host = 'unknown'; db_name = None
                connect_match = connect_pattern.match(argument)
                if connect_match: user = connect_match.group(1).strip(); host = connect_match.group(2).strip(); db_name = connect_match.group(3).strip() if connect_match.group(3) else None
                thread_user_map[thread_id] = {'user': user, 'host': host, 'db': db_name}; logger.info(f"L{line_count}: Connect: Thread {thread_id} -> User={user}, Host={host}")
            elif command == 'Quit':
                if thread_id in thread_user_map: logger.info(f"L{line_count}: Quit: Removing Thread {thread_id} ({thread_user_map[thread_id].get('user','?')})"); del thread_user_map[thread_id]
                else: logger.warning(f"L{line_count}: Quit: Thread {thread_id} not in map.")
            elif command == 'Change user':
                 user = 'unknown'; host = 'unknown'; db_name = None; connect_match = connect_pattern.match(argument);
                 if connect_match: user = connect_match.group(1).strip(); host = connect_match.group(2).strip(); db_name = connect_match.group(3).strip() if connect_match.group(3) else None
                 else: parts = argument.split(' as ');
                 if len(parts) > 0: user_host_part = parts[0].strip(); fallback_match = connect_pattern.match(user_host_part);
                 if fallback_match: user = fallback_match.group(1).strip(); host = fallback_match.group(2).strip()
                 if thread_id in thread_user_map: logger.info(f"L{line_count}: Change User: Update Thread {thread_id} to {user}@{host}")
                 else: logger.info(f"L{line_count}: Change User: Set Thread {thread_id} to {user}@{host}")
                 thread_user_map[thread_id] = {'user': user, 'host': host, 'db': db_name}
            elif command in ['Query', 'Init DB', 'Prepare', 'Execute', 'Close stmt', 'Field List']:
                user_info = thread_user_map.get(thread_id); user_name = 'unknown'; client_host = 'unknown'; db_name = None
                if user_info: user_name = user_info.get('user', 'unknown'); client_host = user_info.get('host', 'unknown'); db_name = user_info.get('db');
                if command == 'Init DB': db_name = argument;
                if isinstance(user_info, dict): user_info['db'] = db_name
                else:
                    if command == 'Query': logger.warning(f"L{line_count}: User info not found for Thread {thread_id}. Cmd: {command}, Arg: {argument[:100]}...")
                activity = create_activity_entry(server_id, timestamp_str, user_name, client_host, db_name, thread_id, command, argument)
            # --- 产出结果 ---
            if activity: parsed_count += 1; yield activity
            if line_count % 10000 == 0: logger.info(f"已处理 {line_count} 行日志...")
    except Exception as e: logger.exception(f"处理日志流时发生错误 (约在第 {line_count} 行): {e}")
    finally: logger.info(f"日志流处理完成，共处理 {line_count} 行，解析出 {parsed_count} 个潜在活动记录。")

# --- SSH 和文件读取 ---
def connect_ssh(hostname, port, username, password=None, pkey_path=None):
    """建立 SSH 连接"""
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if pkey_path: pkey = paramiko.RSAKey.from_private_key_file(pkey_path); client.connect(hostname, port=port, username=username, pkey=pkey, timeout=10); logger.info(f"SSH 已使用私钥连接到 {username}@{hostname}:{port}。")
        elif password: client.connect(hostname, port=port, username=username, password=password, timeout=10); logger.info(f"SSH 已使用密码连接到 {username}@{hostname}:{port}。")
        else: logger.error("SSH 连接失败：未提供密码或私钥。"); return None
        return client
    except paramiko.AuthenticationException: logger.error(f"SSH 认证失败: {username}@{hostname}:{port}。"); return None
    except Exception as e: logger.error(f"SSH 连接到 {hostname}:{port} 失败: {e}"); return None

# --- 主要扫描函数 ---

# !! 实现增量扫描逻辑 !!
def scan_logs_for_server(server_config: dict):
    """
    扫描单个服务器的日志目录，查找并处理自上次扫描以来修改过的 .log 文件，
    根据时间戳和风险等级过滤，并批量插入数据库。
    """
    logger.debug(f"Entering scan_logs_for_server for server_config: {server_config}")
    if not isinstance(server_config, dict): logger.error(f"无效配置类型: {type(server_config)}"); return

    server_id = server_config.get('server_id'); hostname = server_config.get('host'); server_name = server_config.get('name', hostname); port = server_config.get('port', 22); username = server_config.get('user'); password = server_config.get('password'); pkey_path = server_config.get('ssh_key_path'); enable_general = server_config.get('enable_general_log', False); log_dir = server_config.get('general_log_path') if enable_general else None; log_type = 'general' if enable_general else None
    allowed_risk_levels = APP_CONFIG.get('WRITE_RISK_LEVELS', ['High', 'Medium', 'Low']); allowed_risk_levels_set = {level.capitalize() for level in allowed_risk_levels}; logger.info(f"将只写入风险等级为 {allowed_risk_levels_set} 的记录。")

    if not server_id or not hostname or not username: logger.error(f"配置信息不完整: ID={server_id}, Host={hostname}, User={username}"); return
    if enable_general and not log_dir: logger.error(f"服务器 {server_name} ({hostname}) 缺少 general_log_path (目录) 配置"); return
    if not enable_general: logger.warning(f"服务器 {server_name} ({hostname}) 未启用 general_log 扫描"); return

    logger.info(f"开始增量扫描服务器日志目录: Name={server_name}, Host={hostname}, ID(Config)={server_id}, LogDir={log_dir}")

    # 获取上次扫描时间 (确保是 UTC)
    last_scan_time = get_last_scan_time(server_id)
    if last_scan_time is None:
        last_scan_time = datetime(1970, 1, 1, tzinfo=timezone.utc) # 默认从最早开始
        logger.info(f"未找到上次扫描时间，将处理所有时间戳晚于 {last_scan_time} 的记录。")
    elif last_scan_time.tzinfo is None: # 如果数据库存的是 naive 时间，假定它是 UTC
         last_scan_time = last_scan_time.replace(tzinfo=timezone.utc)
         logger.warning(f"从数据库获取的上次扫描时间无时区，已假定为 UTC: {last_scan_time}")
    else: # 确保是 UTC
         last_scan_time = last_scan_time.astimezone(timezone.utc)
         logger.info(f"上次扫描完成时间: {last_scan_time} (UTC). 将处理此时间之后修改的文件和记录。")

    ssh_client = connect_ssh(hostname, port, username, password, pkey_path)
    if not ssh_client: logger.error(f"连接服务器 {hostname} 失败"); return

    sftp = None; total_added_count = 0; scan_successful = True; current_scan_start_time = datetime.now(timezone.utc)
    try:
        sftp = ssh_client.open_sftp(); logger.info(f"SFTP 连接已建立，准备列出目录: {log_dir}")
        files_to_process = []

        # 查找修改过的 .log 文件
        try:
            dir_entries = sftp.listdir_attr(log_dir); logger.debug(f"目录 {log_dir} 下找到 {len(dir_entries)} 个条目。")
            for entry in dir_entries:
                is_file = (entry.st_mode & 0o170000) == 0o100000
                # 将 st_mtime (float, Unix timestamp) 转换为带 UTC 时区的 datetime 对象
                mtime_dt = datetime.fromtimestamp(entry.st_mtime, tz=timezone.utc)
                # 选择修改时间晚于上次扫描时间的文件
                if is_file and entry.filename.lower().endswith('.log') and mtime_dt > last_scan_time:
                    files_to_process.append({'name': entry.filename, 'mtime': mtime_dt})
                    logger.debug(f"找到待处理文件: {entry.filename}, 修改时间: {mtime_dt}")

            if not files_to_process:
                logger.info(f"目录 {log_dir} 中没有找到自 {last_scan_time} 以来修改过的 .log 文件。")
                update_last_scan_time(server_id, current_scan_start_time) # 仍然更新扫描时间
                return

            # 按修改时间排序，确保按顺序处理日志
            files_to_process.sort(key=lambda x: x['mtime'])
            logger.info(f"将按顺序处理 {len(files_to_process)} 个修改过的日志文件: {[f['name'] for f in files_to_process]}")

        except Exception as e:
            logger.exception(f"在目录 {log_dir} 中查找日志文件时发生错误: {e}")
            scan_successful = False
            return # 查找文件出错，直接退出

        # 遍历处理筛选出的文件
        for file_info in files_to_process:
            filename = file_info['name']
            full_log_path = posixpath.join(log_dir, filename)
            sftp_file = None
            try:
                logger.info(f"正在打开日志文件流: {full_log_path}")
                sftp_file = sftp.open(full_log_path, 'rb') # 以二进制模式打开

                activities_batch = []
                processed_count_in_file = 0
                added_count_in_file = 0

                # 流式解析
                for activity in parse_general_log_stream(sftp_file, server_id):
                    processed_count_in_file += 1
                    activity_time = activity.get('timestamp') # 已经是带时区的 datetime 对象

                    # 按时间戳过滤 (只处理比上次扫描时间新的记录)
                    if activity_time and activity_time > last_scan_time:
                        # 按风险等级过滤
                        risk_level = activity.get('risk_level', 'Low').capitalize()
                        if risk_level in allowed_risk_levels_set:
                            activities_batch.append(activity)
                            # 批量插入
                            if len(activities_batch) >= BATCH_INSERT_SIZE:
                                logger.info(f"文件 {filename}: 达到批次大小 {BATCH_INSERT_SIZE}，执行批量插入...")
                                add_user_activities_batch(activities_batch)
                                added_count_in_file += len(activities_batch)
                                activities_batch = [] # 清空批次
                        # else: logger.debug(f"过滤掉风险等级为 {risk_level} 的活动")
                    # else: logger.debug(f"过滤掉时间戳过旧的活动: {activity_time}")

                # 处理文件末尾的最后一批
                if activities_batch:
                    logger.info(f"文件 {filename}: 处理最后一批 {len(activities_batch)} 条记录...")
                    add_user_activities_batch(activities_batch)
                    added_count_in_file += len(activities_batch)

                total_added_count += added_count_in_file
                logger.info(f"文件 {filename} 处理完成: 处理 {processed_count_in_file} 条潜在活动, 添加 {added_count_in_file} 条新记录。")

            except Exception as e:
                logger.exception(f"处理文件 {full_log_path} 时发生错误: {e}")
                scan_successful = False # 标记扫描中遇到错误
                # 这里可以选择 continue 来尝试处理下一个文件，或者 break/return 中断本次扫描
                # break # 如果一个文件失败就中断整个服务器的扫描
            finally:
                if sftp_file:
                    sftp_file.close()
                    logger.info(f"SFTP 文件流已关闭 ({full_log_path})。")

        # --- 所有文件处理完毕 ---
        if scan_successful:
            logger.info(f"服务器 {server_name} ({hostname}) 所有修改过的日志文件处理完毕。总共添加 {total_added_count} 条新记录。")
            # 只有在所有文件都成功处理后才更新时间
            update_last_scan_time(server_id, current_scan_start_time)
        else:
            logger.error(f"服务器 {server_name} ({hostname}) 扫描过程中发生错误，未更新上次扫描时间。")

    except Exception as e:
        logger.exception(f"扫描服务器 {server_name} ({hostname}) 日志时发生错误: {e}")
    finally:
        # 清理资源
        if sftp: sftp.close(); logger.info(f"SFTP 连接已关闭 ({hostname})。")
        if ssh_client: ssh_client.close(); logger.info(f"SSH 连接已关闭 ({hostname})。")

# !! 保持 scan_all_servers 的正确格式 !!
def scan_all_servers():
    """扫描全部服务器日志"""
    try:
        # 从数据库获取所有服务器配置
        servers = get_all_servers()
        logger.info(f"从数据库获取到 {len(servers)} 个服务器配置")
        
        success_count = 0
        fail_count = 0
        
        for server in servers:
            server_id = server.get('server_id')
            # 获取完整配置（包含密码/密钥）
            full_config = get_server_full_config(server_id)
            if full_config:
                # 执行日志扫描
                result = scan_logs_for_server(full_config)
                if result:
                    success_count += 1
                else:
                    fail_count += 1
            else:
                logger.warning(f"未能获取服务器 ID {server_id} 的完整配置")
                fail_count += 1
        
        logger.info(f"扫描完成: {success_count} 个成功, {fail_count} 个失败")
        return success_count > 0  # 至少有一个成功就返回 True
    
    except Exception as e:
        logger.exception(f"扫描所有服务器日志时出错: {e}")
        return False

# !! 保持 parse_binlog 的正确格式 !!
def parse_binlog(ssh_client, binlog_path, server_id, last_scan_time=None):
     """Binlog 解析逻辑占位符"""
     logger.warning("Binlog 解析逻辑尚未实现。")
     return []

# !! 保持 extract_user_from_query 的正确格式 !!
def extract_user_from_query(query_text, thread_id, thread_user_map):
    """ Tries to extract user info (less reliable fallback method)."""
    user_info = thread_user_map.get(thread_id)
    if user_info:
        return user_info.get('user', 'unknown'), user_info.get('host', 'unknown')
    comment_pattern = re.compile(r'/\*\s*User:\s*(\S+),\s*Host:\s*(\S+)\s*\*/')
    match = comment_pattern.search(query_text)
    if match:
        return match.group(1), match.group(2)
    logger.debug(f"线程 {thread_id} 的备用用户提取失败。查询: {query_text[:100]}")
    return 'unknown', 'unknown'

# !! 保持主程序入口的正确格式 !!
if __name__ == '__main__':
    # 配置基本日志记录到控制台，级别设为 DEBUG 以查看详细信息
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("从 log_parser.py 手动启动扫描")
    # 调用扫描所有服务器的函数
    scan_all_servers()
