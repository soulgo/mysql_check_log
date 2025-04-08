"""
MySQL数据库操作日志审计系统配置文件
"""

# 数据库连接配置
DB_CONFIG = {
    'host': '192.168.10.129',  # 修改为本地数据库
    'port': 3310,         # 修改为标准MySQL端口
    'user': 'root',
    'password': '123456',
    'database': 'mysql_log'
}

# 日志服务器配置
LOG_CONFIG = {
    'servers': [
        {
            'server_id': 1,
            'name': 'MySQL服务器1',
            'host': '192.168.10.129',  # 确保这是正确的服务器IP
            'port': 22,                # 确保这是正确的SSH端口
            'user': 'root',            # 确保这是有效的SSH用户名
            'password': '123456',      # 确保这是正确的SSH密码
            'general_log_path': '/data/general_log',  # 修改为更可能存在的路径
            'binlog_path': '/var/lib/mysql',       # 修改为更可能存在的路径
            'enable_general_log': True,  # 是否开启general_log解析
            'enable_binlog': False       # 是否开启binlog解析
        }
    ]
}

# 应用配置
APP_CONFIG = {
    'default_days': 3,  # 默认显示最近3天的数据
    'high_risk_operations': ['DELETE', 'DROP', 'TRUNCATE'],
    'warning_operations': ['UPDATE', 'ALTER'],
    'normal_operations': ['SELECT', 'INSERT', 'SHOW']
}
