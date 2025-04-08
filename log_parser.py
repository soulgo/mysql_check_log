# -*- coding: utf-8 -*-
# 导入所需库
import re
import paramiko
import logging
from datetime import datetime, timezone
import pytz
import posixpath # 用于处理远程服务器路径 (通常是 POSIX 风格)
# !! 从 config 导入 LOG_CONFIG 和 APP_CONFIG !!
from config import LOG_CONFIG, APP_CONFIG
# !! 从 models 仅导入 add_user_activity !!
from models import add_user_activity

# 配置日志记录器
logger = logging.getLogger(__name__)

# --- 正则表达式模式 ---
# (保持不变)
pattern_new = re.compile(
    r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\t *'
    r'(\d+)\s+'
    r'(Query|Connect|Init DB|Quit|Prepare|Execute|Close stmt|Change user|Field List)\t'
    r'(.*)'
)
connect_pattern = re.compile(r'([^@]+)@([^ ]+)(?: on (\S*))?')

# --- 辅助函数 ---
# (determine_operation_type, determine_risk_level, create_activity_entry 保持不变)
def determine_operation_type(sql):
    sql_upper = sql.strip().upper();
    if sql_upper.startswith(('SELECT', 'SHOW', 'DESC', 'EXPLAIN')): return 'SELECT'
    if sql_upper.startswith(('INSERT', 'REPLACE')): return 'INSERT'
    if sql_upper.startswith('UPDATE'): return 'UPDATE'
    if sql_upper.startswith('DELETE'): return 'DELETE'
    if sql_upper.startswith(('CREATE', 'ALTER', 'DROP', 'TRUNCATE')): return 'DDL'
    if sql_upper.startswith(('GRANT', 'REVOKE', 'SET PASSWORD')): return 'DCL'
    if sql_upper.startswith(('COMMIT', 'ROLLBACK', 'START TRANSACTION', 'SAVEPOINT')): return 'TCL'
    if sql_upper.startswith('USE '): return 'USE_DB'
    return 'OTHER'

def determine_risk_level(operation_type, argument):
    op_type_upper = operation_type.upper()
    if op_type_upper in [op.upper() for op in APP_CONFIG.get('high_risk_operations', [])]: return 'High'
    if op_type_upper in [op.upper() for op in APP_CONFIG.get('warning_operations', [])]: return 'Medium'
    return 'Low'

def create_activity_entry(server_id, timestamp_str, user_name, client_host, db_name, thread_id, command, argument):
    try:
        timestamp_dt = datetime.strptime(timestamp_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
        operation_type = determine_operation_type(argument) if command == 'Query' else command.upper()
        risk_level = determine_risk_level(operation_type, argument)
        return {'server_id': server_id, 'timestamp': timestamp_dt, 'user_name': user_name, 'client_host': client_host, 'db_name': db_name, 'thread_id': thread_id, 'command_type': command, 'operation_type': operation_type, 'argument': argument, 'risk_level': risk_level }
    except ValueError as e: logger.error(f"解析时间戳错误 '{timestamp_str}': {e}"); return None
    except Exception as e: logger.error(f"为线程 {thread_id} 创建活动条目时出错: {e}"); return None

# --- 核心解析逻辑 ---
# (parse_general_log 保持不变)
def parse_general_log(content, server_id, thread_user_map):
    activities = []; lines = content.splitlines()
    for line in lines:
        line = line.strip();
        if not line: continue
        match = pattern_new.match(line)
        if not match: continue
        timestamp_str, thread_id_str, command, argument = match.groups()
        thread_id = int(thread_id_str); argument = argument.strip()
        if command == 'Connect':
            user = 'unknown'; host = 'unknown'; db_name = None
            connect_match = connect_pattern.match(argument)
            if connect_match: user = connect_match.group(1).strip(); host = connect_match.group(2).strip(); db_name = connect_match.group(3).strip() if connect_match.group(3) else None
            thread_user_map[thread_id] = {'user': user, 'host': host, 'db': db_name}; logger.info(f"连接事件: 线程 {thread_id} -> 用户={user}, 主机={host}, 数据库={db_name}")
        elif command == 'Quit':
            if thread_id in thread_user_map: logger.info(f"断开事件: 从映射表中移除线程 {thread_id} ({thread_user_map[thread_id].get('user','?')})。"); del thread_user_map[thread_id]
            else: logger.warning(f"断开事件: 线程 {thread_id} 在映射表中未找到。")
        elif command == 'Change user':
            user = 'unknown'; host = 'unknown'; db_name = None
            connect_match = connect_pattern.match(argument)
            if connect_match: user = connect_match.group(1).strip(); host = connect_match.group(2).strip(); db_name = connect_match.group(3).strip() if connect_match.group(3) else None
            else:
                 parts = argument.split(' as ');
                 if len(parts) > 0:
                     user_host_part = parts[0].strip(); fallback_match = connect_pattern.match(user_host_part)
                     if fallback_match: user = fallback_match.group(1).strip(); host = fallback_match.group(2).strip()
            if thread_id in thread_user_map: logger.info(f"切换用户事件: 更新线程 {thread_id} 从 {thread_user_map[thread_id]['user']}@{thread_user_map[thread_id]['host']} 到 {user}@{host}")
            else: logger.info(f"切换用户事件: 设置线程 {thread_id} 为 {user}@{host}")
            thread_user_map[thread_id] = {'user': user, 'host': host, 'db': db_name}
        elif command in ['Query', 'Init DB', 'Prepare', 'Execute', 'Close stmt', 'Field List']:
            user_info = thread_user_map.get(thread_id); user_name = 'unknown'; client_host = 'unknown'; db_name = None
            if user_info:
                user_name = user_info.get('user', 'unknown'); client_host = user_info.get('host', 'unknown'); db_name = user_info.get('db')
                if command == 'Init DB':
                     db_name = argument;
                     if isinstance(user_info, dict): user_info['db'] = db_name
            else:
                if command == 'Query': logger.warning(f"在映射表中未找到线程 {thread_id} 的用户信息。命令: {command}, 参数: {argument[:100]}...")
            activity = create_activity_entry(server_id, timestamp_str, user_name, client_host, db_name, thread_id, command, argument)
            if activity: activities.append(activity)
    return activities, thread_user_map

# --- SSH 和文件读取 ---
# (connect_ssh 保持不变)
def connect_ssh(hostname, port, username, password=None, pkey_path=None):
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        if pkey_path: pkey = paramiko.RSAKey.from_private_key_file(pkey_path); client.connect(hostname, port=port, username=username, pkey=pkey, timeout=10); logger.info(f"SSH 已使用私钥连接到 {username}@{hostname}:{port}。")
        elif password: client.connect(hostname, port=port, username=username, password=password, timeout=10); logger.info(f"SSH 已使用密码连接到 {username}@{hostname}:{port}。")
        else: logger.error("SSH 连接失败：未提供密码或私钥。"); return None
        return client
    except paramiko.AuthenticationException: logger.error(f"SSH 认证失败: {username}@{hostname}:{port}。"); return None
    except Exception as e: logger.error(f"SSH 连接到 {hostname}:{port} 失败: {e}"); return None

# !! 修改 read_log_file 以接受完整文件路径 !!
def read_log_file(sftp_client: paramiko.SFTPClient, full_log_path: str):
    """通过 SFTP 读取指定的日志文件内容"""
    try:
        logger.info(f"正在读取日志文件: {full_log_path}")
        # 直接使用传入的完整路径打开文件
        with sftp_client.open(full_log_path, 'r') as file:
            content = file.read().decode('utf-8', errors='ignore')
            logger.info(f"从 {full_log_path} 读取了 {len(content)} 字节。")
        return content
    except FileNotFoundError:
        logger.error(f"远程服务器上未找到日志文件: {full_log_path}")
        return None
    except IOError as e: # IOError 通常表示权限问题或尝试读取目录
         logger.error(f"通过 SFTP 读取日志文件 {full_log_path} 时发生 IO 错误 (可能是权限或路径问题): {e}")
         return None
    except Exception as e:
        logger.error(f"通过 SFTP 读取日志文件 {full_log_path} 时出错: {e}")
        return None

# !! 修改 parse_general_log_chunked 以接受完整文件路径 !!
# 注意：分块逻辑对于此实现可能不是最优，但我们保留结构
def parse_general_log_chunked(sftp_client: paramiko.SFTPClient, full_log_path: str, server_id: int):
    """读取并解析指定的日志文件，维护用户上下文"""
    # 读取整个文件内容
    content = read_log_file(sftp_client, full_log_path)
    if content is None:
        return [] # 读取失败则返回空

    all_activities = []; thread_user_map = {}
    logger.info(f"正在解析服务器 ID {server_id} 的内容 (来自 {full_log_path}, 大小: {len(content)})")
    activities, _ = parse_general_log(content, server_id, thread_user_map)
    all_activities.extend(activities)
    logger.info(f"从 {full_log_path} 解析了 {len(all_activities)} 个活动。")
    return all_activities

# --- 主要扫描函数 ---

# !! 修改 scan_logs_for_server 以查找目录中的日志文件 !!
def scan_logs_for_server(server_config: dict):
    """
    扫描单个服务器的日志目录，查找并处理最新的 .log 文件。
    期望 server_config 是来自 config.py 中 LOG_CONFIG['servers'] 列表的字典。
    """
    logger.debug(f"Entering scan_logs_for_server for server_config: {server_config}")
    logger.debug(f"Type of server_config: {type(server_config)}")

    if not isinstance(server_config, dict):
        logger.error(f"无效的服务器配置类型: {type(server_config)}。跳过。")
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
    # !! log_dir 是配置中的路径，现在代表目录 !!
    log_dir = server_config.get('general_log_path') if enable_general else None
    log_type = 'general' if enable_general else None

    # 检查关键信息
    if not server_id or not hostname or not username:
         logger.error(f"服务器配置信息不完整: ID={server_id}, Host={hostname}, User={username}。跳过。")
         return
    if enable_general and not log_dir:
         logger.error(f"服务器 {server_name} ({hostname}) 启用了 general_log 但缺少 general_log_path (目录) 配置。跳过。")
         return
    if not enable_general:
        logger.warning(f"服务器 {server_name} ({hostname}) 未启用 general_log 进行扫描。跳过。")
        return

    logger.info(f"开始扫描服务器日志目录: Name={server_name}, Host={hostname}, ID(Config)={server_id}, LogDir={log_dir}")

    ssh_client = connect_ssh(hostname, port, username, password, pkey_path)
    if not ssh_client:
        logger.error(f"连接服务器 {hostname} 失败。")
        return

    sftp = None # 初始化 SFTP 客户端变量
    try:
        sftp = ssh_client.open_sftp() # 打开 SFTP 连接
        logger.info(f"SFTP 连接已建立，准备列出目录: {log_dir}")

        target_log_file = None # 要扫描的目标日志文件名
        latest_mtime = 0       # 最新的修改时间戳

        try:
            # !! 列出指定目录下的文件属性 !!
            dir_entries = sftp.listdir_attr(log_dir)
            logger.debug(f"目录 {log_dir} 下找到 {len(dir_entries)} 个条目。")

            # !! 查找以 .log 结尾且修改时间最新的文件 !!
            log_files = []
            for entry in dir_entries:
                # 简单的检查，确保是文件而不是目录 (st_mode & 0o170000 == 0o100000)
                # 并且文件名以 .log 结尾
                is_file = (entry.st_mode & 0o170000) == 0o100000
                if is_file and entry.filename.lower().endswith('.log'):
                    log_files.append(entry)
                    logger.debug(f"找到 .log 文件: {entry.filename}, 修改时间: {datetime.fromtimestamp(entry.st_mtime)}")

            if not log_files:
                logger.error(f"在目录 {log_dir} 中未找到任何以 .log 结尾的文件。无法继续扫描。")
                return # 退出函数

            # 按修改时间降序排序
            log_files.sort(key=lambda x: x.st_mtime, reverse=True)
            # 选择最新的文件
            target_log_file_entry = log_files[0]
            target_log_filename = target_log_file_entry.filename
            # !! 使用 posixpath 拼接远程路径 !!
            full_log_path = posixpath.join(log_dir, target_log_filename)
            logger.info(f"在目录 {log_dir} 中选择最新的 .log 文件进行扫描: {full_log_path} (修改时间: {datetime.fromtimestamp(target_log_file_entry.st_mtime)})")

        except FileNotFoundError:
            logger.error(f"指定的日志目录 {log_dir} 在远程服务器上不存在。")
            return
        except IOError as e:
            logger.error(f"访问日志目录 {log_dir} 时发生 IO 错误 (可能是权限问题): {e}")
            return
        except Exception as e:
            logger.exception(f"在目录 {log_dir} 中查找日志文件时发生意外错误: {e}")
            return

        # --- 如果找到了目标文件，则继续处理 ---
        if full_log_path:
            # !! 调用 parse_general_log_chunked 处理找到的文件 !!
            # !! 传递 sftp 客户端和完整路径 !!
            activities = parse_general_log_chunked(sftp, full_log_path, server_id)

            logger.info(f"为服务器 {server_name} ({hostname}, ID: {server_id}) 找到了 {len(activities)} 个活动。")

            count = 0
            for activity in activities:
                if not isinstance(activity, dict): continue
                try:
                    activity['server_id'] = server_id
                    add_user_activity(activity)
                    count += 1
                except Exception as e:
                    logger.error(f"为服务器 {server_id} 添加活动到数据库时出错, 线程 {activity.get('thread_id')}: {e} - 活动: {activity}")
            logger.info(f"成功将 {count}/{len(activities)} 个活动添加到服务器 {server_name} ({hostname}) 的数据库。")
        else:
             # 这个分支理论上不会执行，因为前面已经 return 了
             logger.error(f"未能确定在目录 {log_dir} 中要扫描的具体日志文件。")


    except Exception as e:
        logger.exception(f"扫描服务器 {server_name} ({hostname}) 日志时发生错误: {e}")
    finally:
        # 确保 SFTP 和 SSH 连接都关闭
        if sftp:
            sftp.close()
            logger.info(f"SFTP 连接已关闭 ({hostname})。")
        if ssh_client:
            ssh_client.close()
            logger.info(f"SSH 连接已关闭 ({hostname})。")


# (scan_all_servers, parse_binlog, extract_user_from_query, __main__ 保持不变)
def scan_all_servers():
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
             logger.error(f"在 LOG_CONFIG['servers'] 中发现无效的配置项（非字典或缺少'server_id'）: {server_config}。已跳过。")
    logger.info(f"已完成对 {servers_processed}/{len(server_list)} 个服务器的日志扫描尝试。")

def parse_binlog(ssh_client, binlog_path, server_id, last_scan_time=None):
     logger.warning("Binlog 解析逻辑尚未实现。"); return []

def extract_user_from_query(query_text, thread_id, thread_user_map):
    user_info = thread_user_map.get(thread_id)
    if user_info: return user_info.get('user', 'unknown'), user_info.get('host', 'unknown')
    comment_pattern = re.compile(r'/\*\s*User:\s*(\S+),\s*Host:\s*(\S+)\s*\*/')
    match = comment_pattern.search(query_text)
    if match: return match.group(1), match.group(2)
    logger.debug(f"线程 {thread_id} 的备用用户提取失败。查询: {query_text[:100]}")
    return 'unknown', 'unknown'

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger.info("从 log_parser.py 手动启动扫描")
    scan_all_servers()
