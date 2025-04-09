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

# 应用配置
APP_CONFIG = {
    'default_days': 3,  # 默认显示最近3天的数据

    # !! 修改为结构化的风险操作定义 (RISK_OPERATIONS) !!
    # log_parser.py 中的 determine_risk_level 函数将使用这个结构
    # 规则按 High -> Medium -> Low 的顺序匹配，第一个匹配到的生效
    'RISK_OPERATIONS': {
        # 高危操作定义: 匹配类型或关键字
        'High': [
            {'type': 'DDL'},      # 所有 DDL (CREATE, ALTER, DROP, TRUNCATE)
            {'type': 'DCL'},      # 所有 DCL (GRANT, REVOKE)
            # 根据您之前的配置添加 DELETE, DROP, TRUNCATE (作为类型或关键字)
            {'type': 'DELETE'},    # 将 DELETE 操作类型直接定义为高危
            # {'keyword': 'delete from '}, # 或者更具体地匹配关键字
            {'keyword': 'drop table'},
            {'keyword': 'drop database'},
            {'keyword': 'truncate table'},
            {'keyword': 'set password'}, # 设置密码也视为高危
        ],
        # 中危操作定义: 匹配类型或关键字
        'Medium': [
            {'type': 'UPDATE'},    # 将 UPDATE 操作类型定义为中危
            # 根据您之前的配置添加 ALTER (DDL 已在高危中，但可以更具体)
            # {'keyword': 'alter table'}, # 如果只想让 alter table 是中危
            {'keyword': 'alter user'},
            {'keyword': 'drop user'},
        ],
        # 低危操作定义: (通常用于覆盖默认行为，或明确指定)
        'Low': [
            {'type': 'SELECT'},
            {'type': 'INSERT'},
            {'type': 'SHOW'},
            {'type': 'CONNECT'},
            {'type': 'QUIT'},
            {'type': 'USE_DB'},
            {'type': 'TCL'},      # 事务控制通常视为低风险
            # ... 其他可以明确标为低风险的操作 ...
        ]
        # 未明确匹配到 High/Medium/Low 规则的操作，将默认为 Low
    },

    # !! 保留：指定要写入数据库的风险等级 !!
    # 您可以修改这个列表来控制写入哪些等级的数据
    'WRITE_RISK_LEVELS': ['High', 'Medium'] # 当前配置为写入所有等级
    # 例如，只写入高危和中危:
    # 'WRITE_RISK_LEVELS': ['High', 'Medium'],
}
