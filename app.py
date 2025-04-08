# -*- coding: utf-8 -*-
# 导入所需库
import logging
import logging.handlers
import os
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
# 从 models 导入需要的函数
from models import init_db, add_user_activity, get_user_activities, get_operation_stats
# 从 log_parser 导入需要的函数
from log_parser import scan_logs_for_server, scan_all_servers
# 从 config 导入 LOG_CONFIG
from config import LOG_CONFIG

# --- 日志配置 ---
log_dir = 'logs'
os.makedirs(log_dir, exist_ok=True) # 使用 exist_ok=True 避免目录已存在时报错
log_file = os.path.join(log_dir, 'app.log')
# 配置根 logger
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# 配置按天轮转的文件处理器
file_handler = logging.handlers.TimedRotatingFileHandler(
    log_file, when='midnight', interval=1, backupCount=7, encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logging.getLogger('').addHandler(file_handler) # 添加到根 logger
# 获取 Flask 应用本身的 logger
logger = logging.getLogger(__name__)

# --- Flask 应用初始化 ---
app = Flask(__name__)

# --- 数据库初始化 ---
try:
    if init_db():
        logger.info("数据库初始化成功或已存在。")
    else:
        logger.error("数据库初始化失败。请检查数据库连接和权限。")
except Exception as e:
    logger.exception(f"数据库初始化过程中发生意外错误: {e}")

# --- 路由定义 ---

@app.route('/')
def index():
    """渲染主页面，服务器列表来自 config.py"""
    server_options = []
    try:
        # 从 config.LOG_CONFIG['servers'] (列表) 构建服务器选项
        server_list = LOG_CONFIG.get('servers', [])
        if server_list and isinstance(server_list, list):
            server_options = [
                {'id': s.get('server_id'), 'name': s.get('name', s.get('host', f"ID: {s.get('server_id')}"))}
                for s in server_list if isinstance(s, dict) and s.get('server_id') is not None
            ]
            server_options.sort(key=lambda x: x.get('id', 0))
            logger.info(f"从 config.py 加载的 server_options: {server_options}")
        else:
            logger.warning("config.py 中的 LOG_CONFIG['servers'] 未定义、为空或不是列表。")
        # 渲染模板，传入服务器选项
        return render_template('index.html', servers=server_options)
    except Exception as e:
        logger.exception(f"渲染主页时出错: {e}")
        # 出错时也渲染页面，但下拉列表将为空
        return render_template('index.html', servers=[])

# !! 修正 get_activities 函数的格式 !!
@app.route('/api/activities', methods=['GET'])
def get_activities():
    """获取用户活动记录 API"""
    try:
        # 从请求参数中获取筛选条件
        server_id = request.args.get('server_id', type=int)
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        operation_type = request.args.get('operation_type')
        risk_level = request.args.get('risk_level')
        user_name = request.args.get('user_name')
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        offset = (page - 1) * limit

        # 解析日期
        start_date = None
        end_date = None
        if start_date_str and start_date_str.lower() != 'invalid date':
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                logger.warning(f"无效的 start_date 格式: {start_date_str}")
        if end_date_str and end_date_str.lower() != 'invalid date':
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                if end_date: # 确保 end_date 转换成功
                    # 包含当天结束时间
                    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            except ValueError:
                logger.warning(f"无效的 end_date 格式: {end_date_str}")

        logger.info(f"接收到的活动请求参数: server_id={server_id}, start_date={start_date_str}, end_date={end_date_str}, operation_type={operation_type}, risk_level={risk_level}, user_name={user_name}")

        # 调用 models 函数获取数据
        activities, total = get_user_activities(
            server_id=server_id if server_id else None,
            start_date=start_date,
            end_date=end_date,
            operation_type=operation_type if operation_type else None,
            risk_level=risk_level if risk_level else None,
            user_name=user_name if user_name else None,
            limit=limit,
            offset=offset
        )
        logger.info(f"筛选后的活动数据条数: {len(activities)} / 总数: {total}")

        # 格式化结果用于 JSON 响应
        activities_list = []
        for act in activities:
             if isinstance(act, dict):
                 # 格式化 datetime 对象为字符串
                 if isinstance(act.get('activity_time'), datetime):
                     act['activity_time'] = act['activity_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                 activities_list.append(act)

        return jsonify({'activities': activities_list, 'total': total})

    except Exception as e:
        # 记录异常并返回错误响应
        logger.exception(f"获取活动数据失败: {e}")
        return jsonify({'error': f'获取活动数据失败: {e}'}), 500

# !! 修正 get_stats 函数的格式 !!
@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息 API"""
    try:
        # 获取请求参数
        server_id = request.args.get('server_id', type=int)
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')

        # 解析日期
        start_date = None
        end_date = None
        if start_date_str and start_date_str.lower() != 'invalid date':
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                logger.warning(f"无效的 start_date 格式: {start_date_str}")
        if end_date_str and end_date_str.lower() != 'invalid date':
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                if end_date: # 确保 end_date 转换成功
                    end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            except ValueError:
                logger.warning(f"无效的 end_date 格式: {end_date_str}")

        logger.info(f"接收到的统计请求参数: server_id={server_id}, start_date={start_date_str}, end_date={end_date_str}")

        # 调用 models 函数获取统计数据
        stats = get_operation_stats(
            server_id=server_id if server_id else None,
            start_date=start_date,
            end_date=end_date
        )

        # 返回 JSON 结果
        return jsonify(stats)

    except Exception as e:
        # 记录异常并返回错误响应
        logger.exception(f"获取统计数据失败: {e}")
        return jsonify({'error': f'获取统计数据失败: {e}'}), 500

# !! /api/scan 路由保持正确格式 !!
@app.route('/api/scan', methods=['POST'])
def api_scan():
    """触发日志扫描 API"""
    scan_message = "扫描任务已提交" # 默认成功消息
    try:
        server_id_to_scan = request.json.get('server_id') if request.is_json else None
        logger.info(f"收到扫描请求: server_id_to_scan={server_id_to_scan}")
        server_list = LOG_CONFIG.get('servers', [])
        if not server_list or not isinstance(server_list, list):
             logger.error("config.py 中的 LOG_CONFIG['servers'] 未定义、为空或不是列表。")
             return jsonify({'status': 'error', 'error': '服务器配置错误'}), 500

        if server_id_to_scan is not None:
            # 扫描指定服务器
            server_config_to_scan = next((cfg for cfg in server_list if isinstance(cfg, dict) and cfg.get('server_id') == server_id_to_scan), None)
            if server_config_to_scan:
                display_name = server_config_to_scan.get('name', server_config_to_scan.get('host', server_id_to_scan))
                logger.info(f"开始扫描特定服务器 (来自 config.py): Name={display_name}, ID={server_id_to_scan}")
                scan_logs_for_server(server_config_to_scan) # 同步执行扫描
                scan_message = f"服务器 {display_name} 扫描完成"
                return jsonify({'status': 'success', 'message': scan_message})
            else:
                logger.error(f"扫描失败：在 config.py 中未找到 ID 为 {server_id_to_scan} 的服务器配置。")
                return jsonify({'status': 'error', 'error': f'未在配置中找到ID为 {server_id_to_scan} 的服务器'}), 404
        else:
            # 扫描所有服务器
            logger.info("开始扫描所有服务器 (来自 config.py)...")
            scan_all_servers() # 同步执行扫描
            scan_message = "所有服务器扫描完成"
            return jsonify({'status': 'success', 'message': scan_message})

    except Exception as e:
        logger.exception(f"扫描日志 API 处理失败: {e}")
        return jsonify({'status': 'error', 'error': f'扫描日志失败: {e}'}), 500

# --- 应用运行 ---
if __name__ == '__main__':
    # 启用调试模式，方便开发
    # 生产环境请务必设置为 debug=False 并使用 WSGI 服务器部署
    app.run(debug=True, host='0.0.0.0', port=5000)
