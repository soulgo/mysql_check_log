# MySQL 数据库操作日志审计系统

## 1. 项目简介

本项目是一个基于 Flask Web 框架开发的 MySQL 数据库操作日志审计系统。旨在通过 SSH 连接到远程 MySQL 服务器，拉取并解析其 General Log，对 SQL 操作进行分类、风险评估，并将审计结果存入本地数据库，最终通过 Web 界面进行可视化展示、查询和统计分析。

**核心特性**:

* **配置驱动**: 完全通过 `config.py` 文件定义需要审计的 MySQL 服务器列表及其连接信息、日志路径等。
* **远程日志获取**: 使用 Paramiko 库通过 SSH 安全连接远程服务器。
* **智能日志查找**: 自动扫描指定日志目录 (`general_log_path`) 下最新的 `.log` 文件进行处理。
* **流式处理与性能优化**: 采用流式读取和解析大日志文件，结合数据库批量插入，有效处理大数据量并降低内存消耗。
* **详细操作分类**: 不仅识别 CRUD 操作，还能识别 DDL, DCL, TCL, 连接/断开等多种 MySQL 操作类型。
* **结构化风险评估**: 根据 `config.py` 中灵活配置的规则（可基于操作类型和 SQL 关键字）对操作进行高、中、低三级风险评估。
* **风险写入过滤**: 可在 `config.py` 中配置只将指定风险等级（如高、中危）的日志写入数据库，以减轻数据库压力。
* **Web 可视化界面**:
    * 提供仪表盘，通过图表展示风险等级分布、操作类型分布、活跃用户排行、操作次数按小时分布等统计信息。
    * 提供操作记录查询页面，支持按服务器、日期范围、操作类型、风险等级、用户名进行筛选和分页查看。
    * 界面元素（如风险等级、操作类型筛选）提供中文支持。
    * 提供扫描状态的实时反馈（侧边栏指示器）和扫描完成后的自动数据刷新。

## 2. 系统架构

系统主要由以下几个模块组成：

1.  **Web 后端 (Flask - `app.py`)**:
    * 处理 HTTP 请求，提供 Web 界面和 API 接口。
    * 负责调用日志解析和数据查询模块。
    * 从 `config.py` 读取服务器配置列表。
2.  **配置文件 (`config.py`)**:
    * **`DB_CONFIG`**: 本地审计数据库的连接信息。
    * **`LOG_CONFIG`**: **核心配置**，包含一个 `'servers'` 列表，列表中每个字典定义了一个需要审计的 MySQL 服务器的详细信息（`server_id`, `name`, `host`, `port`, `user`, `password`/`ssh_key_path`, `general_log_path` (目录), `enable_general_log` 等）。
    * **`APP_CONFIG`**: 应用相关配置，包括风险评估规则 (`RISK_OPERATIONS`) 和要写入数据库的风险等级 (`WRITE_RISK_LEVELS`)。
3.  **日志解析器 (`log_parser.py`)**:
    * 根据 `LOG_CONFIG` 连接远程服务器。
    * 查找并流式读取 General Log 文件。
    * 逐行解析日志，提取时间、用户、IP、线程 ID、操作命令、SQL 语句等。
    * 调用辅助函数判断操作类型和风险等级。
    * 根据 `WRITE_RISK_LEVELS` 配置过滤记录。
    * 将符合条件的记录分批次传递给数据模型层进行存储。
4.  **数据模型 (`models.py`)**:
    * 负责与本地审计数据库 (`mysql_log`) 交互。
    * 包含 `user_activities` 表的初始化 (`init_db`)。
    * 提供批量插入活动记录 (`add_user_activities_batch`) 的功能。
    * 提供查询活动记录 (`get_user_activities`) 和统计信息 (`get_operation_stats`) 的功能。
    * **注意**: 不再使用 `mysql_servers` 表。
5.  **前端界面 (`templates/index.html`, `static/`)**:
    * 使用 HTML, CSS (Tailwind CSS) 和 JavaScript (jQuery, Moment.js, Daterangepicker, Plotly.js) 构建用户界面。
    * 通过 API 与后端交互获取数据并展示。
    * 实现筛选、分页、Tab 切换、扫描状态提示、数据自动刷新等交互功能。

**数据流**: `config.py` -> `app.py` / `log_parser.py` -> SSH -> Remote Log File -> `log_parser.py` (Parse & Filter) -> `models.py` (Batch Insert into `user_activities`) -> `app.py` (Query API) -> `main.js` (Fetch & Render) -> `index.html` (Display)

## 3. 数据库设计

系统仅使用一个核心数据表 `user_activities` 来存储审计日志结果。

* **`user_activities`**:
    * `id` (BIGINT, PK): 自增主键。
    * `server_id` (INT, Not Null): **关联 `config.py` 中 `LOG_CONFIG['servers']` 列表内服务器字典的 `server_id`**。
    * `timestamp` (DATETIME(6), Not Null): 操作发生时间（精确到微秒，UTC 时区存储）。
    * `user_name` (VARCHAR): 数据库用户名。
    * `client_host` (VARCHAR): 客户端来源 IP 或主机名。
    * `db_name` (VARCHAR): 操作时所在的数据库名。
    * `thread_id` (INT): MySQL 服务器线程 ID。
    * `command_type` (VARCHAR): 从日志中解析出的原始命令类型 (如 Query, Connect)。
    * `operation_type` (VARCHAR): 进一步分类的操作类型 (如 SELECT, INSERT, DDL)。
    * `argument` (TEXT): SQL 语句或命令参数。
    * `risk_level` (ENUM('Low','Medium','High')): 风险等级。
    * `created_at` (TIMESTAMP): 记录插入时间。

**注意**: `mysql_servers` 表已不再使用。

## 4. 配置说明

所有配置均在 `config.py` 文件中完成。

* **`DB_CONFIG`**: 配置本地用于存储审计结果的 MySQL 数据库连接信息（host, port, user, password, database）。
* **`LOG_CONFIG`**: **核心配置**。
    * 必须是一个字典，包含一个键 `'servers'`。
    * `'servers'` 的值必须是一个**列表**。
    * 列表中的**每个元素**都是一个**字典**，代表一个要审计的 MySQL 服务器，**必须包含**以下键：
        * `'server_id'` (int): **必需**，为此服务器分配一个**唯一**的整数 ID。所有审计记录将使用此 ID 关联。
        * `'host'` (str): **必需**，远程 MySQL 服务器的 IP 地址或主机名，用于 SSH 连接。
        * `'user'` (str): **必需**，用于 SSH 连接的用户名（需要有读取目标日志文件的权限）。
        * `'general_log_path'` (str): **必需** (如果 `enable_general_log` 为 True)，MySQL general log 文件所在的**目录**路径（程序会自动查找该目录下最新的 `.log` 文件）。
        * `'enable_general_log'` (bool): **必需**，设为 `True` 以启用对此服务器 general log 的扫描。
    * **可选**的键：
        * `'name'` (str): 服务器的友好名称，用于在界面下拉列表中显示。如果省略，将使用 `'host'` 的值。
        * `'port'` (int): SSH 连接端口，默认为 22。
        * `'password'` (str): SSH 连接密码。**注意：密码和密钥至少提供一个。**
        * `'ssh_key_path'` (str): SSH 私钥文件的**绝对路径**。如果使用密钥认证，请提供此项。
        * `'binlog_path'` (str): Binlog 文件路径或目录（当前 Binlog 解析未实现）。
        * `'enable_binlog'` (bool): 是否启用 Binlog 解析（当前未实现），默认为 `False`。
* **`APP_CONFIG`**: 应用行为配置。
    * `'default_days'` (int): 页面加载时默认显示的日志天数。
    * **`'RISK_OPERATIONS'`** (dict): **必需**，用于定义风险等级规则。结构如下：
        ```python
        'RISK_OPERATIONS': {
            'High': [ {'type': 'DDL'}, {'keyword': 'delete from '} ],
            'Medium': [ {'type': 'UPDATE'} ],
            'Low': [ {'type': 'SELECT'} ]
        }
        ```
        * 包含 'High', 'Medium', 'Low' 三个键。
        * 每个键的值是一个**字典列表**。
        * 每个字典规则可以包含 `'type'` (匹配 `determine_operation_type` 返回的操作类型，大小写不敏感) 或 `'keyword'` (匹配 SQL 语句中的小写关键字) 或两者都有。
        * 匹配时按 High -> Medium -> Low 顺序检查，第一个完全匹配的规则生效。
        * 未匹配任何规则的操作默认为 Low。
    * **`'WRITE_RISK_LEVELS'`** (list): **必需**，一个包含字符串 'High', 'Medium', 'Low' 的列表，指定哪些风险等级的日志记录**需要被写入数据库**。例如 `['High', 'Medium']` 表示只写入高危和中危记录。如果想写入所有记录，使用 `['High', 'Medium', 'Low']`。

## 5. 部署与运行

1.  **环境准备**:
    * Python 3.x
    * MySQL 数据库 (用于存储审计结果)
2.  **安装依赖**:
    ```bash
    pip install -r requirements.txt
    ```
    (请确保 `requirements.txt` 文件包含 `Flask`, `PyMySQL`, `paramiko`, `pytz`, `python-dateutil` 等必要库)。
3.  **配置 `config.py`**: 根据实际情况修改 `DB_CONFIG`, `LOG_CONFIG`, `APP_CONFIG`。**务必为 `LOG_CONFIG['servers']` 中的每个服务器添加唯一的 `server_id` 并提供正确的连接信息和日志目录路径。**
4.  **初始化数据库**:
    * 确保 `DB_CONFIG` 配置正确，并且目标数据库已存在。
    * 可以运行 `python models.py` (如果 `models.py` 有 `if __name__ == '__main__': init_db()` 入口) 或通过其他方式执行 `models.init_db()` 函数来创建 `user_activities` 表。
    * 可以使用 `python reset_db.py` 脚本清空并重新初始化 `user_activities` 表（**注意：会删除现有数据！**）。
5.  **运行应用**:
    ```bash
    python app.py
    ```
    应用将在 `http://0.0.0.0:5000` (或您指定的地址和端口) 启动。对于生产环境，请使用 Gunicorn 或 uWSGI 等 WSGI 服务器部署。
6.  **首次扫描**: 应用启动后，数据库中没有数据。需要访问 Web 界面，点击“扫描日志”按钮来执行首次日志扫描和数据入库。

## 6. 使用说明

1.  **访问**: 在浏览器中打开 Flask 应用运行的地址。
2.  **仪表盘**: 默认视图，展示风险分布、操作类型分布、小时分布、活跃用户等统计图表。
3.  **操作记录**: 显示详细的审计日志表格。
    * **筛选**: 使用顶部的筛选条件（服务器、时间范围、操作类型、风险等级、用户名）过滤记录。点击“应用筛选”按钮生效。
    * **分页**: 使用表格下方的分页控件浏览记录。
    * **查看详情**: 点击 SQL 语句列末尾的 "[详情]" 按钮可查看完整的 SQL 语句。
4.  **扫描日志**: 点击左下角的“扫描日志”按钮。
    * 可以选择扫描“全部服务器”或在下拉列表中选择特定服务器。
    * 点击后会弹出确认框。
    * 确认后，按钮变为“扫描中...”，按钮上方会出现旋转动画提示。
    * 扫描结束后，动画消失，按钮恢复，按钮下方会短暂显示结果信息（如“扫描完成”或错误信息）。
    * **扫描成功后，页面上的数据会自动刷新**。

## 7. 注意事项

* **SSH 权限**: `config.py` 中配置的 SSH 用户必须拥有读取目标服务器上 MySQL general log 文件的权限。
* **日志文件路径**: 务必在 `config.py` 中为每个服务器配置正确的 general log **目录**路径 (`general_log_path`)。代码会自动查找该目录下最新的 `.log` 文件。
* **MySQL 配置**: 确保目标 MySQL 服务器已开启 general log 功能 (`general_log = ON`)，并且日志输出到文件 (`log_output = FILE` 或 `FILE,TABLE`)。
* **性能**: 扫描非常大的日志文件仍然可能需要较长时间，虽然已进行优化。增量扫描是未来的优化方向。
* **安全性**: `config.py` 中可能包含敏感信息（如密码），请妥善保管。考虑使用 SSH 密钥认证代替密码。
* **错误处理**: 请关注 Flask 应用的控制台输出或 `app.log` 文件，以便诊断扫描过程中可能出现的错误。

