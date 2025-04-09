# -*- coding: utf-8 -*-
"""
MySQL数据库操作日志审计系统配置文件
"""

# 数据库连接配置
DB_CONFIG = {
    'host': '192.168.10.129',  # 修改为本地数据库
    'port': 3310,          # 修改为标准MySQL端口
    'user': 'root',
    'password': '123456',
    'database': 'mysql_log'
}

# 应用配置（作为默认值和参考）
APP_CONFIG = {
    'default_days': 3,  # 默认显示最近3天的数据
    
    # 默认风险操作定义
    'RISK_OPERATIONS': {
        'High': [
            {'type': 'DDL'},
            {'type': 'DCL'},
            {'type': 'DELETE'}
        ],
        'Medium': [
            {'type': 'UPDATE'}
        ],
        'Low': [
            {'type': 'SELECT'},
            {'type': 'INSERT'},
            {'type': 'SHOW'}
        ]
    },
    
    # 默认写入风险级别
    'WRITE_RISK_LEVELS': ['High', 'Medium']
}
