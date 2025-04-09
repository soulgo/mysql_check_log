# MySQL 数据库操作日志审计系统

## 1. 项目简介

本项目是一个基于 Flask Web 框架开发的 MySQL 数据库操作日志审计系统。旨在通过 SSH 连接到远程 MySQL 服务器，拉取并解析其 General Log，对 SQL 操作进行分类、风险评估，并将审计结果存入MySQL数据库，最终通过 Web 界面进行可视化展示、查询和统计分析。

**核心特性**:

* **数据库驱动配置**: 所有服务器配置均存储在MySQL数据库中，可通过Web界面动态管理，无需修改配置文件。
* **远程日志获取**: 使用 Paramiko 库通过 SSH 安全连接远程服务器。
* **智能日志查找**: 自动扫描指定日志目录 (`general_log_path`) 下最新的 `.log` 文件进行处理。
* **流式处理与性能优化**: 采用流式读取和解析大日志文件，结合数据库批量插入，有效处理大数据量并降低内存消耗。
* **详细操作分类**: 不仅识别 CRUD 操作，还能识别 DDL, DCL, TCL, 连接/断开等多种 MySQL 操作类型。
* **结构化风险评估**: 根据灵活配置的规则（可基于操作类型和 SQL 关键字）对操作进行高、中、低三级风险评估。
* **风险写入过滤**: 可配置只将指定风险等级（如高、中危）的日志写入数据库，以减轻数据库压力。
* **Web 可视化界面**:
    * 提供仪表盘，通过图表展示风险等级分布、操作类型分布、活跃用户排行、操作次数按小时分布等统计信息。
    * 提供操作记录查询页面，支持按服务器、日期范围、操作类型、风险等级、用户名进行筛选和分页查看。
    * 界面元素（如风险等级、操作类型筛选）提供中文支持。
    * 提供扫描状态的实时反馈（侧边栏指示器）和扫描完成后的自动数据刷新。
* **服务器配置管理**: 提供Web界面完整管理MySQL服务器配置的功能，包括添加、编辑和删除服务器。

## 2. 系统架构

系统主要由以下几个模块组成：

1.  **Web 后端 (Flask - `app.py`)**:
    * 处理 HTTP 请求，提供 Web 界面和 API 接口。
    * 负责调用日志解析和数据查询模块。
    * 提供服务器配置管理API。
2.  **配置文件 (`config.py`)**:
    * **`DB_CONFIG`**: MySQL数据库的连接信息，用于存储审计结果和系统配置。
    * **`APP_CONFIG`**: 应用相关配置，包括风险评估规则 (`RISK_OPERATIONS`) 和要写入数据库的风险等级 (`WRITE_RISK_LEVELS`)。
3.  **日志解析器 (`log_parser.py`)**:
    * 从数据库获取服务器配置，连接远程服务器。
    * 查找并流式读取 General Log 文件。
    * 逐行解析日志，提取时间、用户、IP、线程 ID、操作命令、SQL 语句等。
    * 调用辅助函数判断操作类型和风险等级。
    * 根据 `WRITE_RISK_LEVELS` 配置过滤记录。
    * 将符合条件的记录分批次传递给数据模型层进行存储。
4.  **数据模型 (`models.py`)**:
    * 负责与MySQL数据库交互，管理系统所有数据。
    * 管理数据库表结构（初始化、升级）。
    * 提供服务器配置管理功能（增删改查）。
    * 提供批量插入活动记录的功能。
    * 提供查询活动记录和统计信息的功能。
    * 提供系统设置的存取功能。
5.  **前端界面 (`templates/index.html`, `static/`)**:
    * 使用 HTML, CSS (Tailwind CSS) 和 JavaScript (jQuery, Moment.js, Daterangepicker, Plotly.js) 构建用户界面。
    * 通过 API 与后端交互获取数据并展示。
    * 实现筛选、分页、Tab 切换、扫描状态提示、数据自动刷新等交互功能。

**数据流**: `models.py` (Get Server Config) -> `log_parser.py` -> SSH -> Remote Log File -> `log_parser.py` (Parse & Filter) -> `models.py` (Batch Insert into `user_activities`) -> `app.py` (Query API) -> `main.js` (Fetch & Render) -> `index.html` (Display)

## 3. 数据库设计

系统使用MySQL数据库，包含以下主要数据表：

* **`server_configs`**（服务器配置表）:
    * `server_id` (INT, PK): 服务器ID，主键。
    * `name` (VARCHAR): 服务器名称。
    * `host` (VARCHAR): 服务器主机地址。
    * `port` (INT): SSH连接端口，默认22。
    * `user` (VARCHAR): SSH连接用户名。
    * `password` (VARCHAR): SSH连接密码。
    * `ssh_key_path` (VARCHAR): SSH密钥文件路径。
    * `general_log_path` (VARCHAR): MySQL通用日志目录路径。
    * `binlog_path` (VARCHAR): MySQL二进制日志路径。
    * `enable_general_log` (TINYINT): 是否启用通用日志扫描，1启用，0禁用。
    * `enable_binlog` (TINYINT): 是否启用二进制日志扫描，1启用，0禁用。
  
* **`user_activities`**（用户数据库操作记录表）:
    * `id` (BIGINT, PK): 记录ID，自增主键。
    * `server_id` (INT, FK): 服务器ID，关联到server_configs表。
    * `timestamp` (DATETIME(6)): 操作发生时间，精确到微秒。
    * `user_name` (VARCHAR): 数据库用户名。
    * `client_host` (VARCHAR): 客户端来源 IP 或主机名。
    * `db_name` (VARCHAR): 操作时所在的数据库名。
    * `thread_id` (INT): MySQL 服务器线程 ID。
    * `command_type` (VARCHAR): 从日志中解析出的原始命令类型 (如 Query, Connect)。
    * `operation_type` (VARCHAR): 进一步分类的操作类型 (如 SELECT, INSERT, DDL)。
    * `argument` (TEXT): SQL 语句或命令参数。
    * `risk_level` (ENUM('Low','Medium','High')): 风险等级。
    * `created_at` (TIMESTAMP): 记录插入时间。

* **`server_scan_records`**（服务器扫描记录表）:
    * `server_id` (INT, PK): 服务器ID，主键。
    * `last_scan_time` (DATETIME(6)): 最后一次成功扫描的时间。

* **`system_settings`**（系统设置表）:
    * `key` (VARCHAR, PK): 设置键名。
    * `value` (TEXT): 设置值。
    * `updated_at` (DATETIME): 最后更新时间。

## 4. 配置说明

系统配置分为两部分：

### 4.1 基础配置（`config.py`文件）

* **`DB_CONFIG`**: 配置MySQL数据库连接信息：
  ```python
  DB_CONFIG = {
      'host': '数据库服务器地址',
      'port': 3306,
      'user': '数据库用户名',
      'password': '数据库密码',
      'database': 'mysql_log'
  }
  ```

* **`APP_CONFIG`**: 应用默认配置：
  ```python
  APP_CONFIG = {
      'default_days': 3,  # 默认显示最近3天的数据
      
      # 风险操作定义
      'RISK_OPERATIONS': {
          'High': [ {'type': 'DDL'}, {'keyword': 'delete from'} ],
          'Medium': [ {'type': 'UPDATE'} ],
          'Low': [ {'type': 'SELECT'} ]
      },
      
      # 要写入数据库的风险等级
      'WRITE_RISK_LEVELS': ['High', 'Medium']
  }
  ```

### 4.2 系统配置（存储在数据库中）

* **服务器配置**: 存储在`server_configs`表中，可通过Web界面管理。
* **风险操作规则**: 存储在`system_settings`表中，键名为`RISK_OPERATIONS`。
* **写入风险级别**: 存储在`system_settings`表中，键名为`WRITE_RISK_LEVELS`。

系统首次启动时会使用`APP_CONFIG`中的默认值初始化数据库中的系统配置，之后会优先使用数据库中的配置。

## 5. 部署与运行

1.  **环境准备**:
    * Python 3.x
    * MySQL 数据库服务器
2.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```
    (请确保 `requirements.txt` 文件包含 `Flask`, `PyMySQL`, `paramiko`, `pytz`, `python-dateutil` 等必要库)。
3.  **配置 `config.py`**: 
    * 修改 `DB_CONFIG` 中的MySQL数据库连接信息。
    * 根据需要调整 `APP_CONFIG` 中的默认设置。
4.  **初始化数据库**:
    * 确保 `DB_CONFIG` 中指定的数据库已创建。
    * 运行 `python app.py` 启动应用，系统将自动创建所需的数据表。
5.  **运行应用**:
    ```bash
    python app.py
    ```
    应用将在 `http://0.0.0.0:5000` 启动。对于生产环境，请使用 Gunicorn 或 uWSGI 等 WSGI 服务器部署。

## 6. 使用说明

1.  **访问**: 在浏览器中打开 Flask 应用运行的地址。
2.  **服务器配置**:
    * 首次使用时，系统会创建一个默认的服务器配置。
    * 点击界面上的"管理服务器"按钮进入服务器配置管理页面。
    * 在此页面可以添加、编辑或删除服务器配置。
    * 必须正确配置服务器的连接信息和日志目录路径。
3.  **仪表盘**: 默认视图，展示风险分布、操作类型分布、小时分布、活跃用户等统计图表。
4.  **操作记录**: 显示详细的审计日志表格。
    * **筛选**: 使用顶部的筛选条件（服务器、时间范围、操作类型、风险等级、用户名）过滤记录。
    * **分页**: 使用表格下方的分页控件浏览记录。
    * **查看详情**: 点击 SQL 语句列末尾的 "[详情]" 按钮可查看完整的 SQL 语句。
5.  **扫描日志**: 点击左下角的"扫描日志"按钮。
    * 可以选择扫描"全部服务器"或选择特定服务器。
    * 确认后开始扫描，界面会显示扫描状态。
    * 扫描完成后，页面数据会自动刷新。
6.  **系统设置**: 可以通过系统设置页面修改风险评估规则和其他系统设置。

## 7. 注意事项

* **SSH 权限**: 配置的 SSH 用户必须拥有读取目标服务器上 MySQL general log 文件的权限。
* **日志文件路径**: 服务器配置中的 general_log_path 必须指定为日志文件所在的目录路径，系统会自动查找该目录下最新的 .log 文件。
* **MySQL 配置**: 确保目标 MySQL 服务器已开启 general log 功能 (`general_log = ON`)，并且日志输出到文件 (`log_output = FILE` 或 `FILE,TABLE`)。
* **数据安全**: 系统存储的服务器连接信息（包括密码）存储在数据库中，请确保数据库安全。
* **增量扫描**: 系统会记录每个服务器的最后扫描时间，后续扫描只处理新增的日志，提高效率。
* **错误处理**: 请关注控制台输出的日志信息，以便诊断扫描过程中可能出现的错误。

## 8. 技术参考

* **服务器配置字段说明**:
  * `server_id`: 服务器ID，必须唯一
  * `name`: 服务器名称，用于在界面中显示
  * `host`: 服务器主机地址，用于SSH连接
  * `port`: SSH连接端口，默认22
  * `user`: SSH连接用户名
  * `password`: SSH连接密码
  * `ssh_key_path`: SSH密钥文件路径（与密码二选一）
  * `general_log_path`: MySQL通用日志目录路径
  * `binlog_path`: MySQL二进制日志路径（当前未实现）
  * `enable_general_log`: 是否启用通用日志扫描
  * `enable_binlog`: 是否启用二进制日志扫描（当前未实现）

* **风险规则配置格式**:
  ```json
  {
    "High": [
      {"type": "DDL"},
      {"keyword": "drop table"}
    ],
    "Medium": [
      {"type": "UPDATE"}
    ],
    "Low": [
      {"type": "SELECT"}
    ]
  }
  ```

* **数据库字段中文注释**: 系统为所有数据库表和字段添加了详细的中文注释，便于理解和管理。

