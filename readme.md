以下是根据您的要求重新生成的技术文档，内容经过优化，结构清晰，涵盖完整的技术说明和实现细节。

---

# MySQL 5.7.36 数据库操作日志审计系统技术文档

## 项目概述

本系统通过SSH远程连接MySQL服务器，读取并分析`binlog`和`general_log`日志文件，实现对数据库操作的审计功能。系统基于Python Flask框架开发，提供直观的可视化界面，用于展示审计报告，包括用户活动时间线、操作分类统计和详细查询结果。系统旨在帮助数据库管理员和安全审计人员实时监控数据库操作，发现潜在安全风险并确保合规性。
页面默认显示前三天的数据，所以日志读取的时候也是前三天的数据。页面可以通过时间范围来筛选数据。通过读取配置文件来读取日志目录。

### 目标用户
- **数据库管理员**：负责数据库日常管理，需监控操作并优化性能。
- **安全审计人员**：关注数据库操作的安全性与合规性，识别异常行为。

### 使用场景
- **实时监控**：追踪用户对数据库的访问和修改行为。
- **安全审计**：分析操作记录，确保合规性并发现高危操作。
- **风险预警**：识别潜在威胁并及时告警。

---

## 功能特性

### 1. 日志采集
- **实现方式**：
  - 通过SSH远程连接MySQL服务器，读取`binlog`和`general_log`文件。
  - 支持实时日志解析和增量读取。
  - 采用分批处理机制，优化大规模日志解析性能。
- **支持的日志类型**：
  - `binlog`：支持`ROW`、`STATEMENT`和`MIXED`格式。
  - `general_log`：记录所有SQL查询和连接事件。

### 2. 安全分级
- **功能描述**：
  - **高危操作**：识别`DELETE`、`DROP`、`TRUNCATE`等操作，触发告警。
  - **警告操作**：记录`UPDATE`、`ALTER`等操作的详细信息。
  - **普通操作**：分类`SELECT`、`INSERT`等操作，便于审计。
- **优势**：
  - 操作风险分级，便于快速定位威胁。

### 3. 可视化审计报告
- **功能描述**：
  - **用户活动时间线**：按时间顺序展示用户操作。
  - **操作分类统计**：统计操作类型频率和分布。
  - **详细查询功能**：支持按用户、操作类型、时间范围等条件筛选。
- **界面特点**：
  - 基于Flask的Web界面，响应式设计，适配多种设备。

---

## 系统架构

### 技术选型
- **前端**：Flask + Jinja2模板，轻量且易于扩展。
- **后端**：Python 3.10，支持异步编程，提升性能。
- **核心依赖**：
  - `paramiko`：实现SSH远程连接。
  - `python-binlog`：解析MySQL `binlog`。
  - `pymysql`：连接MySQL数据库。
  - `pandas`：处理和分析日志数据。

### 架构流程
1. **日志采集**：通过SSH连接MySQL服务器，读取日志文件。
2. **数据解析**：解析日志内容，提取用户信息、操作类型、时间戳等。
3. **数据存储**：将解析结果存入MySQL数据库。
4. **数据展示**：通过Flask渲染可视化审计报告。

---

## 数据库设计

系统使用MySQL存储审计数据，表结构设计如下：

### 1. `mysql_servers`（服务器信息）
```sql
CREATE TABLE mysql_servers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  server_name VARCHAR(50) NOT NULL COMMENT '服务器名称',
  server_ip VARCHAR(15) NOT NULL COMMENT '服务器IP',
  last_scan_time DATETIME COMMENT '最后扫描时间',
  INDEX idx_server_ip (server_ip)
);
```

### 2. `user_activities`（用户活动）
```sql
CREATE TABLE user_activities (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_name VARCHAR(50) NOT NULL COMMENT '操作用户',
  operation_type VARCHAR(20) NOT NULL COMMENT '操作类型',
  timestamp DATETIME NOT NULL COMMENT '操作时间',
  client_ip VARCHAR(15) COMMENT '客户端IP',
  server_id INT,
  FOREIGN KEY (server_id) REFERENCES mysql_servers(id),
  INDEX idx_timestamp (timestamp)
);
```

---

## 部署指南

### 1. 环境准备
- 安装Python 3.10和pip。
- 安装依赖：
  ```bash
  pip install -r requirements.txt
  ```

### 2. 配置说明
- 编辑`config.py`，配置SSH和数据库连接：
  ```python
  DB_CONFIG = {
      'host': 'localhost',
      'port': 3306,
      'user': 'audit_user',
      'password': 'password',
      'database': 'mysql_log'
  }
  LOG_CONFIG = {
      'servers': [
          {
              'server_id': 1,
              'host': '127.0.0.1',
              'port': 22,
              'user': 'root',
              'password': 'xxxx',
              'general_log_path': '/data/general_log',
              'binlog_path': '/data/binlog'
          }
      ]
  }
  ```

### 3. 启动服务
- 运行应用：
  ```bash
  flask run --host=0.0.0.0 --port=5000
  ```
- 访问：`http://localhost:5000`。

---
页面显示如下：
![alt text](image.png)

---

## 安全审计功能

- **实时监控**：支持日志增量读取，实时更新审计报告。
- **高危操作告警**：通过配置规则，自动识别并标记高危操作。
- **数据过滤**：支持多条件查询，快速定位异常。

---
