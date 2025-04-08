# -*- coding: utf-8 -*-
# 导入所需库
import re
import paramiko
import logging
from datetime import datetime, timezone
import pytz
import posixpath
from typing import List, Dict, Any, Optional, Generator
# 从 config 导入 LOG_CONFIG 和 APP_CONFIG
from config import LOG_CONFIG, APP_CONFIG
# 从 models 导入 add_user_activities_batch
from models import add_user_activities_batch

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
    if sql_upper.startswith(('SELECT', 'SHOW', 'DESC', 'EXPLAIN')):
        return 'SELECT'
    elif sql_upper.startswith(('INSERT', 'REPLACE')):
        return 'INSERT'
    elif sql_upper.startswith('UPDATE'):
        return 'UPDATE'
    elif sql_upper.startswith('DELETE'):
        return 'DELETE'
    elif sql_upper.startswith(('CREATE', 'ALTER', 'DROP', 'TRUNCATE')):
        return 'DDL'
    elif sql_upper.startswith(('GRANT', 'REVOKE', 'SET PASSWORD')):
        return 'DCL'
    elif sql_upper.startswith(('COMMIT', 'ROLLBACK', 'START TRANSACTION', 'SAVEPOINT')):
        return 'TCL'
    elif sql_upper.startswith('USE '):
        return 'USE_DB'
    return 'OTHER'

def determine_risk_level(operation_type, argument):
    """根据配置 (结构化 RISK_OPERATIONS) 判断操作的风险等级"""
    risk_definitions = APP_CONFIG.get('RISK_OPERATIONS', {})
    argument_lower = argument.lower()
    # 检查 High risk
    for rule in risk_definitions.get('High', []):
        rule_type = rule.get('type', '').upper()
        rule_keyword = rule.get('keyword', '').lower()
        type_match = (not rule_type or operation_type.upper() == rule_type)
        keyword_match = (not rule_keyword or rule_keyword in argument_lower)
        if type_match and keyword_match:
            return 'High'
    # 检查 Medium risk
    for rule in risk_definitions.get('Medium', []):
        rule_type = rule.get('type', '').upper()
        rule_keyword = rule.get('keyword', '').lower()
        type_match = (not rule_type or operation_type.upper() == rule_type)
        keyword_match = (not rule_keyword or rule_keyword in argument_lower)
        if type_match and keyword_match:
            return 'Medium'
    # 检查 Low risk
    for rule in risk_definitions.get('Low', []):
        rule_type = rule.get('type', '').upper()
        rule_keyword = rule.get('keyword', '').lower()
        type_match = (not rule_type or operation_type.upper() == rule_type)
        keyword_match = (not rule_keyword or rule_keyword in argument_lower)
        if type_match and keyword_match:
            return 'Low'
    # 默认 Low
    return 'Low'

def create_activity_entry(server_id, timestamp_str, user_name, client_host, db_name, thread_id, command, argument):
    """创建一个代表用户活动日志条目的字典"""
    try:
        timestamp_dt = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        operation_type = determine_operation_type(argument) if command == 'Query' else command.upper()
        risk_level = determine_risk_level(operation_type, argument)
        return {
            'server_id': server_id,
            'timestamp': timestamp_dt,
            'user_name': user_name,
            'client_host': client_host,
            'db_name': db_name,
            'thread_id': thread_id,
            'command_type': command,
            'operation_type': operation_type,
            'argument': argument,
            'risk_level': risk_level
        }
    except ValueError as e:
        logger.error(f"解析时间戳错误 '{timestamp_str}': {e}")
        return None
    except Exception as e:
        logger.error(f"为线程 {thread_id} 创建活动条目时出错: {e}")
        return None

# --- 核心解析逻辑 ---

def parse_general_log_stream(sftp_file: paramiko.SFTPFile, server_id: int) -> Generator[Dict[str, Any], None, None]:
    """ 流式解析打开的 SFTP general log 文件。 """
    thread_user_map = {}
    line_count = 0
    parsed_count = 0
    try:
        for line_bytes in sftp_file:
            line_count += 1
            try:
                line = line_bytes.decode('utf-8', errors='ignore').strip()
            except UnicodeDecodeError:
                logger.warning(f"解码第 {line_count} 行时出错，已跳过。")
                continue

            if not line: continue # 跳过空行

            match = pattern_new.match(line)
            if not match: continue # 跳过格式不符的行

            timestamp_str, thread_id_str, command, argument = match.groups()
            thread_id = int(thread_id_str)
            argument = argument.strip()
            activity = None

            # --- 处理命令类型 (保持正确格式) ---
            if command == 'Connect':
                user = 'unknown'; host = 'unknown'; db_name = None
                connect_match = connect_pattern.match(argument)
                if connect_match:
                    user = connect_match.group(1).strip()
                    host = connect_match.group(2).strip()
                    db_name = connect_match.group(3).strip() if connect_match.group(3) else None
                thread_user_map[thread_id] = {'user': user, 'host': host, 'db': db_name}
                logger.info(f"L{line_count}: Connect: Thread {thread_id} -> User={user}, Host={host}")
            elif command == 'Quit':
                if thread_id in thread_user_map:
                    logger.info(f"L{line_count}: Quit: Removing Thread {thread_id} ({thread_user_map[thread_id].get('user','?')})")
                    del thread_user_map[thread_id]
                else:
                    logger.warning(f"L{line_count}: Quit: Thread {thread_id} not in map.")
            elif command == 'Change user':
                 user = 'unknown'; host = 'unknown'; db_name = None
                 connect_match = connect_pattern.match(argument)
                 if connect_match:
                     user = connect_match.group(1).strip()
                     host = connect_match.group(2).strip()
                     db_name = connect_match.group(3).strip() if connect_match.group(3) else None
                 else:
                     parts = argument.split(' as ')
                     if len(parts) > 0:
                         user_host_part = parts[0].strip()
                         fallback_match = connect_pattern.match(user_host_part)
                         if fallback_match:
                             user = fallback_match.group(1).strip()
                             host = fallback_match.group(2).strip()
                 if thread_id in thread_user_map:
                     logger.info(f"L{line_count}: Change User: Update Thread {thread_id} to {user}@{host}")
                 else:
                     logger.info(f"L{line_count}: Change User: Set Thread {thread_id} to {user}@{host}")
                 thread_user_map[thread_id] = {'user': user, 'host': host, 'db': db_name}
            elif command in ['Query', 'Init DB', 'Prepare', 'Execute', 'Close stmt', 'Field List']:
                user_info = thread_user_map.get(thread_id)
                user_name = 'unknown'; client_host = 'unknown'; db_name = None
                if user_info:
                    user_name = user_info.get('user', 'unknown')
                    client_host = user_info.get('host', 'unknown')
                    db_name = user_info.get('db')
                    if command == 'Init DB':
                        db_name = argument
                        if isinstance(user_info, dict):
                            user_info['db'] = db_name
                else:
                    if command == 'Query':
                        logger.warning(f"L{line_count}: User info not found for Thread {thread_id}. Cmd: {command}, Arg: {argument[:100]}...")
                activity = create_activity_entry(server_id, timestamp_str, user_name, client_host, db_name, thread_id, command, argument)

            if activity:
                parsed_count += 1
                yield activity
            if line_count % 10000 == 0:
                logger.info(f"已处理 {line_count} 行日志...")
    except Exception as e:
        logger.exception(f"处理日志流时发生错误 (约在第 {line_count} 行): {e}")
    finally:
        logger.info(f"日志流处理完成，共处理 {line_count} 行，解析出 {parsed_count} 个潜在活动记录。")

# --- SSH 和文件读取 ---

# !! 保持 connect_ssh 的正确格式 !!
def connect_ssh(hostname, port, username, password=None, pkey_path=None):
    """建立 SSH 连接"""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if pkey_path:
            pkey = paramiko.RSAKey.from_private_key_file(pkey_path)
            client.connect(hostname, port=port, username=username, pkey=pkey, timeout=10)
            logger.info(f"SSH 已使用私钥连接到 {username}@{hostname}:{port}。")
        elif password:
            client.connect(hostname, port=port, username=username, password=password, timeout=10)
            logger.info(f"SSH 已使用密码连接到 {username}@{hostname}:{port}。")
        else:
            logger.error("SSH 连接失败：未提供密码或私钥。")
            return None
        return client
    except paramiko.AuthenticationException:
        logger.error(f"SSH 认证失败: {username}@{hostname}:{port}。")
        return None
    except Exception as e:
        logger.error(f"SSH 连接到 {hostname}:{port} 失败: {e}")
        return None

# --- 主要扫描函数 ---

# !! 修正 scan_logs_for_server 的格式 !!
def scan_logs_for_server(server_config: dict):
    """
    扫描单个服务器的日志目录，查找并流式处理最新的 .log 文件，
    根据风险等级过滤，并批量插入数据库。
    """
    logger.debug(f"Entering scan_logs_for_server for server_config: {server_config}")
    if not isinstance(server_config, dict):
        logger.error(f"无效配置类型: {type(server_config)}")
        return

    # 从配置字典中获取信息
    server_id = server_config.get('server_id')
    hostname = server_config.get('host')
    server_name = server_config.get('name', hostname)
    port = server_config.get('port', 22)
    username = server_config.get('user')
    password = server_config.get('password')
    pkey_path = server_config.get('ssh_key_path')
    enable_general = server_config.get('enable_general_log', False)
    log_dir = server_config.get('general_log_path') if enable_general else None
    log_type = 'general' if enable_general else None

    # 获取允许写入的风险等级
    allowed_risk_levels = APP_CONFIG.get('WRITE_RISK_LEVELS', ['High', 'Medium', 'Low'])
    allowed_risk_levels_set = {level.capitalize() for level in allowed_risk_levels}
    logger.info(f"将只写入风险等级为 {allowed_risk_levels_set} 的记录。")

    # 检查关键配置
    if not server_id or not hostname or not username:
        logger.error(f"配置信息不完整: ID={server_id}, Host={hostname}, User={username}")
        return
    if enable_general and not log_dir:
        logger.error(f"服务器 {server_name} ({hostname}) 缺少 general_log_path (目录) 配置")
        return
    if not enable_general:
        logger.warning(f"服务器 {server_name} ({hostname}) 未启用 general_log 扫描")
        return

    logger.info(f"开始扫描服务器日志目录: Name={server_name}, Host={hostname}, ID(Config)={server_id}, LogDir={log_dir}")

    # 建立 SSH 连接
    ssh_client = connect_ssh(hostname, port, username, password, pkey_path)
    if not ssh_client:
        logger.error(f"连接服务器 {hostname} 失败")
        return

    sftp = None
    sftp_file = None
    total_added_count = 0
    try:
        sftp = ssh_client.open_sftp()
        logger.info(f"SFTP 连接已建立，准备列出目录: {log_dir}")
        full_log_path = None

        # 查找最新的 .log 文件
        try:
            dir_entries = sftp.listdir_attr(log_dir)
            logger.debug(f"目录 {log_dir} 下找到 {len(dir_entries)} 个条目。")
            log_files = []
            for entry in dir_entries:
                is_file = (entry.st_mode & 0o170000) == 0o100000
                if is_file and entry.filename.lower().endswith('.log'):
                    log_files.append(entry)
                    logger.debug(f"找到 .log 文件: {entry.filename}, 修改时间: {datetime.fromtimestamp(entry.st_mtime)}")

            if not log_files:
                logger.error(f"在目录 {log_dir} 中未找到任何以 .log 结尾的文件。")
                return # 必须 return 退出

            log_files.sort(key=lambda x: x.st_mtime, reverse=True)
            target_log_file_entry = log_files[0]
            target_log_filename = target_log_file_entry.filename
            full_log_path = posixpath.join(log_dir, target_log_filename)
            logger.info(f"选择最新的 .log 文件进行扫描: {full_log_path} (修改时间: {datetime.fromtimestamp(target_log_file_entry.st_mtime)})")
        except Exception as e:
            logger.exception(f"在目录 {log_dir} 中查找日志文件时发生错误: {e}")
            return # 必须 return 退出

        # 处理找到的日志文件
        if full_log_path:
            logger.info(f"正在打开日志文件流: {full_log_path}")
            sftp_file = sftp.open(full_log_path, 'rb') # 以二进制模式打开

            activities_batch = []
            processed_count = 0
            # 遍历流式解析器
            for activity in parse_general_log_stream(sftp_file, server_id):
                processed_count += 1
                risk_level = activity.get('risk_level', 'Low').capitalize()
                # 过滤风险等级
                if risk_level in allowed_risk_levels_set:
                    activities_batch.append(activity)
                    # 批量插入
                    if len(activities_batch) >= BATCH_INSERT_SIZE:
                        logger.info(f"达到批次大小 {BATCH_INSERT_SIZE}，执行批量插入...")
                        add_user_activities_batch(activities_batch)
                        total_added_count += len(activities_batch)
                        activities_batch = [] # 清空批次

            # 处理最后一批
            if activities_batch:
                logger.info(f"处理最后一批 {len(activities_batch)} 条记录...")
                add_user_activities_batch(activities_batch)
                total_added_count += len(activities_batch)

            logger.info(f"扫描完成: 共处理 {processed_count} 条潜在活动, 成功添加 {total_added_count} 条记录到数据库。")
        else:
             logger.error(f"未能确定在目录 {log_dir} 中要扫描的具体日志文件。")

    except Exception as e:
        logger.exception(f"扫描服务器 {server_name} ({hostname}) 日志时发生错误: {e}")
    finally:
        # 清理资源
        if sftp_file:
            sftp_file.close()
            logger.info(f"SFTP 文件流已关闭 ({hostname})。")
        if sftp:
            sftp.close()
            logger.info(f"SFTP 连接已关闭 ({hostname})。")
        if ssh_client:
            ssh_client.close()
            logger.info(f"SSH 连接已关闭 ({hostname})。")

# !! 修正 scan_all_servers 的格式 !!
def scan_all_servers():
    """扫描 config.py 中 LOG_CONFIG['servers'] 定义的所有服务器的日志"""
    logger.info("开始扫描所有已配置的服务器 (来自 config.py)...")
    server_list = LOG_CONFIG.get('servers', [])
    if not server_list or not isinstance(server_list, list):
        logger.warning("config.py 中的 LOG_CONFIG['servers'] 未定义、为空或不是列表。无法扫描。")
        return

    logger.info(f"准备遍历 {len(server_list)} 个服务器配置...")
    servers_processed = 0
    for server_config in server_list:
        if isinstance(server_config, dict) and server_config.get('server_id') is not None:
             logger.debug(f"正在调用 scan_logs_for_server 处理服务器配置: server_id={server_config.get('server_id')}")
             scan_logs_for_server(server_config)
             servers_processed += 1
        else:
             logger.error(f"在 LOG_CONFIG['servers'] 中发现无效的配置项: {server_config}。已跳过。")
    logger.info(f"已完成对 {servers_processed}/{len(server_list)} 个服务器的日志扫描尝试。")

# !! 修正 parse_binlog 的格式 !!
def parse_binlog(ssh_client, binlog_path, server_id, last_scan_time=None):
     """Binlog 解析逻辑占位符"""
     logger.warning("Binlog 解析逻辑尚未实现。")
     return []

# (extract_user_from_query 保持不变)
def extract_user_from_query(query_text, thread_id, thread_user_map):
    user_info = thread_user_map.get(thread_id);
    if user_info: return user_info.get('user', 'unknown'), user_info.get('host', 'unknown')
    comment_pattern = re.compile(r'/\*\s*User:\s*(\S+),\s*Host:\s*(\S+)\s*\*/'); match = comment_pattern.search(query_text);
    if match: return match.group(1), match.group(2)
    logger.debug(f"线程 {thread_id} 的备用用户提取失败。查询: {query_text[:100]}"); return 'unknown', 'unknown'

# !! 修正主程序入口的格式 !!
if __name__ == '__main__':
    # 配置基本日志记录到控制台，级别设为 DEBUG 以查看详细信息
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("从 log_parser.py 手动启动扫描")
    # 调用扫描所有服务器的函数
    scan_all_servers()
