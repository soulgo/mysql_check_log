# -*- coding: utf-8 -*-
# 导入所需库
import logging
import logging.handlers
import os
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta
# 从 models 导入需要的函数
from models import (
    init_db, add_user_activity, get_user_activities, get_operation_stats,
    get_all_servers, get_server_by_id, get_server_full_config, add_server, update_server, delete_server,
    get_system_setting, update_system_setting
)
# 从 log_parser 导入需要的函数
from log_parser import scan_logs_for_server, scan_all_servers
# 从 config 导入默认配置
from config import APP_CONFIG

# --- 日志配置 ---
# 移除文件日志配置
# 保留基础控制台日志配置
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Flask 应用初始化 ---
app = Flask(__name__)

# --- 初始配置缓存 ---
# 这两个缓存会在应用启动时和配置变更时更新
CACHED_RISK_OPERATIONS = None
CACHED_WRITE_RISK_LEVELS = None

# --- 数据库初始化 ---
try:
    if init_db():
        logger.info("数据库初始化成功或已存在。")
    else:
        logger.error("数据库初始化失败。请检查数据库连接和权限。")
except Exception as e:
    logger.exception(f"数据库初始化过程中发生意外错误: {e}")

# --- 初始加载配置 ---
def load_system_settings():
    """从数据库加载系统配置到内存缓存"""
    global CACHED_RISK_OPERATIONS, CACHED_WRITE_RISK_LEVELS
    
    # 加载风险操作规则
    risk_operations = get_system_setting('RISK_OPERATIONS')
    if risk_operations:
        CACHED_RISK_OPERATIONS = risk_operations
    else:
        # 如果数据库中没有，使用默认值
        CACHED_RISK_OPERATIONS = APP_CONFIG.get('RISK_OPERATIONS', {})
    
    # 加载写入风险级别
    write_risk_levels = get_system_setting('WRITE_RISK_LEVELS')
    if write_risk_levels:
        CACHED_WRITE_RISK_LEVELS = write_risk_levels
    else:
        # 如果数据库中没有，使用默认值
        CACHED_WRITE_RISK_LEVELS = APP_CONFIG.get('WRITE_RISK_LEVELS', ['High', 'Medium'])
    
    logger.info("系统配置已从数据库加载到内存缓存")

# 初始加载配置
load_system_settings()

# --- 路由定义 ---

@app.route('/')
def index():
    """渲染主页面，服务器列表来自数据库"""
    server_options = []
    try:
        # 从数据库获取服务器列表
        server_list = get_all_servers()
        if server_list and isinstance(server_list, list):
            server_options = [
                {'id': s.get('server_id'), 'name': s.get('name', s.get('host', f"ID: {s.get('server_id')}"))}
                for s in server_list if s.get('server_id') is not None
            ]
            server_options.sort(key=lambda x: x.get('id', 0))
            logger.info(f"从数据库加载的 server_options: {server_options}")
        else:
            logger.warning("数据库中未找到服务器配置。")
        # 渲染模板，传入服务器选项
        return render_template('index.html', servers=server_options)
    except Exception as e:
        logger.exception(f"渲染主页时出错: {e}")
        # 出错时也渲染页面，但下拉列表将为空
        return render_template('index.html', servers=[])

@app.route('/api/activities', methods=['GET'])
def get_activities():
    """获取用户活动记录 API"""
    try:
        # 获取请求参数
        server_id = request.args.get('server_id', type=int)
        start_date_str = request.args.get('start_date')
        end_date_str = request.args.get('end_date')
        operation_type = request.args.get('operation_type')
        risk_level = request.args.get('risk_level')
        user_name = request.args.get('user_name')
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 50, type=int)
        offset = (page - 1) * limit

        # 解析日期 (包含对 "Invalid date" 的处理)
        start_date = None
        end_date = None
        if start_date_str and start_date_str.lower() != 'invalid date':
            try: start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError: logger.warning(f"无效的 start_date 格式: {start_date_str}")
        if end_date_str and end_date_str.lower() != 'invalid date':
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                if end_date: end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            except ValueError: logger.warning(f"无效的 end_date 格式: {end_date_str}")

        # logger.info(f"接收到的活动请求参数: ...") # 日志可选

        # 调用 models 获取数据
        activities, total = get_user_activities(
            server_id=server_id if server_id else None, start_date=start_date, end_date=end_date,
            operation_type=operation_type if operation_type else None, risk_level=risk_level if risk_level else None,
            user_name=user_name if user_name else None, limit=limit, offset=offset
        )
        # logger.info(f"筛选后的活动数据条数: ...") # 日志可选

        # 格式化结果
        activities_list = []
        for act in activities:
             if isinstance(act, dict):
                 if isinstance(act.get('activity_time'), datetime):
                     act['activity_time'] = act['activity_time'].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                 activities_list.append(act)

        return jsonify({'activities': activities_list, 'total': total})

    except Exception as e:
        logger.exception(f"获取活动数据失败: {e}")
        return jsonify({'error': f'获取活动数据失败: 服务器内部错误'}), 500

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
            try: start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError: logger.warning(f"无效的 start_date 格式: {start_date_str}")
        if end_date_str and end_date_str.lower() != 'invalid date':
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                if end_date: end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            except ValueError: logger.warning(f"无效的 end_date 格式: {end_date_str}")

        # logger.info(f"接收到的统计请求参数: ...") # 日志可选

        # 调用 models 获取统计数据
        stats = get_operation_stats(
            server_id=server_id if server_id else None,
            start_date=start_date,
            end_date=end_date
        )
        return jsonify(stats)

    except Exception as e:
        logger.exception(f"获取统计数据失败: {e}")
        return jsonify({'error': f'获取统计数据失败: 服务器内部错误'}), 500

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """触发日志扫描 API"""
    scan_message = "扫描任务已提交" # 默认成功消息
    status_code = 200
    response_data = {}
    try:
        server_id_to_scan = request.json.get('server_id') if request.is_json else None
        logger.info(f"收到扫描请求: server_id_to_scan={server_id_to_scan}")
        
        # 从数据库获取服务器配置
        if server_id_to_scan is not None:
            # 扫描指定服务器
            server_config_to_scan = get_server_full_config(server_id_to_scan)
            if server_config_to_scan:
                display_name = server_config_to_scan.get('name', server_config_to_scan.get('host', server_id_to_scan))
                logger.info(f"开始扫描特定服务器 (来自数据库): Name={display_name}, ID={server_id_to_scan}")
                # 注意：这里的扫描是同步执行的，会阻塞请求直到完成
                scan_logs_for_server(server_config_to_scan)
                scan_message = f"服务器 {display_name} 扫描完成"
                response_data = {'status': 'success', 'message': scan_message} # 返回成功状态
            else:
                logger.error(f"扫描失败：在数据库中未找到 ID 为 {server_id_to_scan} 的服务器配置。")
                response_data = {'status': 'error', 'error': f'未在配置中找到ID为 {server_id_to_scan} 的服务器'}
                status_code = 404
        else:
            # 扫描所有服务器
            logger.info("开始扫描所有服务器 (来自数据库)...")
            # 注意：这里的扫描是同步执行的
            scan_all_servers()
            scan_message = "所有服务器扫描完成"
            response_data = {'status': 'success', 'message': scan_message} # 返回成功状态

        # 返回 JSON 响应和状态码
        return jsonify(response_data), status_code

    except Exception as e:
        # 捕获扫描过程中的任何未预料错误
        logger.exception(f"扫描日志 API 处理失败: {e}")
        # 返回统一的错误格式
        return jsonify({'status': 'error', 'error': f'扫描日志失败: 服务器内部错误'}), 500

# --- 服务器配置管理相关路由 ---
@app.route('/api/servers', methods=['GET'])
def get_servers():
    """获取所有服务器配置"""
    try:
        # 从数据库获取服务器配置
        servers = get_all_servers()
        return jsonify({'status': 'success', 'servers': servers})
    except Exception as e:
        logger.exception(f"获取服务器配置失败: {e}")
        return jsonify({'status': 'error', 'error': f'获取服务器配置失败: {str(e)}'}), 500

@app.route('/api/server/<int:server_id>', methods=['GET'])
def get_server(server_id):
    """获取特定服务器配置"""
    try:
        # 从数据库获取服务器配置
        server = get_server_by_id(server_id)
        if not server:
            return jsonify({'status': 'error', 'error': f'未找到ID为 {server_id} 的服务器配置'}), 404
            
        return jsonify({'status': 'success', 'server': server})
    except Exception as e:
        logger.exception(f"获取服务器配置失败: {e}")
        return jsonify({'status': 'error', 'error': f'获取服务器配置失败: {str(e)}'}), 500

@app.route('/api/server', methods=['POST'])
def api_add_server():
    """添加新服务器配置"""
    try:
        if not request.is_json:
            return jsonify({'status': 'error', 'error': '请求必须是JSON格式'}), 400
            
        server_data = request.json
        
        # 验证必要字段
        required_fields = ['name', 'host', 'port', 'user']
        missing_fields = [field for field in required_fields if field not in server_data]
        if missing_fields:
            return jsonify({'status': 'error', 'error': f'缺少必要字段: {", ".join(missing_fields)}'}), 400
            
        # 将服务器配置添加到数据库
        server_id = add_server(server_data)
        if server_id:
            return jsonify({
                'status': 'success', 
                'message': '服务器配置已添加', 
                'server_id': server_id
            })
        else:
            return jsonify({'status': 'error', 'error': '添加服务器配置失败'}), 500
    except Exception as e:
        logger.exception(f"添加服务器配置失败: {e}")
        return jsonify({'status': 'error', 'error': f'添加服务器配置失败: {str(e)}'}), 500

@app.route('/api/server/<int:server_id>', methods=['PUT'])
def api_update_server(server_id):
    """更新服务器配置"""
    try:
        if not request.is_json:
            return jsonify({'status': 'error', 'error': '请求必须是JSON格式'}), 400
            
        server_data = request.json
        
        # 验证必要字段
        required_fields = ['name', 'host', 'port', 'user']
        missing_fields = [field for field in required_fields if field not in server_data]
        if missing_fields:
            return jsonify({'status': 'error', 'error': f'缺少必要字段: {", ".join(missing_fields)}'}), 400
            
        # 更新数据库中的服务器配置
        success = update_server(server_id, server_data)
        if success:
            return jsonify({
                'status': 'success', 
                'message': '服务器配置已更新'
            })
        else:
            return jsonify({'status': 'error', 'error': f'未找到ID为 {server_id} 的服务器配置或更新失败'}), 404
    except Exception as e:
        logger.exception(f"更新服务器配置失败: {e}")
        return jsonify({'status': 'error', 'error': f'更新服务器配置失败: {str(e)}'}), 500

@app.route('/api/server/<int:server_id>', methods=['DELETE'])
def api_delete_server(server_id):
    """删除服务器配置"""
    try:
        # 从数据库删除服务器配置
        success = delete_server(server_id)
        if success:
            return jsonify({
                'status': 'success', 
                'message': '服务器配置已删除'
            })
        else:
            return jsonify({'status': 'error', 'error': f'未找到ID为 {server_id} 的服务器配置'}), 404
    except Exception as e:
        logger.exception(f"删除服务器配置失败: {e}")
        return jsonify({'status': 'error', 'error': f'删除服务器配置失败: {str(e)}'}), 500

@app.route('/api/risk_rules', methods=['GET'])
def get_risk_rules():
    """获取风险规则配置"""
    try:
        # 从内存缓存获取风险规则
        risk_rules = CACHED_RISK_OPERATIONS
        return jsonify({'status': 'success', 'risk_rules': risk_rules})
    except Exception as e:
        logger.exception(f"获取风险规则失败: {e}")
        return jsonify({'status': 'error', 'error': f'获取风险规则失败: {str(e)}'}), 500

@app.route('/api/risk_rules', methods=['PUT'])
def update_risk_rules():
    """更新风险规则配置"""
    try:
        if not request.is_json:
            return jsonify({'status': 'error', 'error': '请求必须是JSON格式'}), 400
            
        risk_rules = request.json.get('risk_rules')
        if not risk_rules or not isinstance(risk_rules, dict):
            return jsonify({'status': 'error', 'error': '风险规则格式无效'}), 400
            
        # 验证风险规则格式
        for level, rules in risk_rules.items():
            if level not in ['High', 'Medium', 'Low']:
                return jsonify({'status': 'error', 'error': f'无效的风险等级: {level}'}), 400
            if not isinstance(rules, list):
                return jsonify({'status': 'error', 'error': f'等级 {level} 的规则必须是列表'}), 400
            for rule in rules:
                if not isinstance(rule, dict):
                    return jsonify({'status': 'error', 'error': f'等级 {level} 的规则必须是字典'}), 400
                if 'type' not in rule and 'keyword' not in rule:
                    return jsonify({'status': 'error', 'error': f'规则必须包含 type 或 keyword 字段'}), 400
        
        # 更新数据库和内存缓存中的风险规则
        success = update_system_setting('RISK_OPERATIONS', risk_rules, '风险操作规则配置')
        if success:
            global CACHED_RISK_OPERATIONS
            CACHED_RISK_OPERATIONS = risk_rules
            return jsonify({
                'status': 'success', 
                'message': '风险规则已更新'
            })
        else:
            return jsonify({'status': 'error', 'error': '更新风险规则失败'}), 500
    except Exception as e:
        logger.exception(f"更新风险规则失败: {e}")
        return jsonify({'status': 'error', 'error': f'更新风险规则失败: {str(e)}'}), 500

@app.route('/api/write_risk_levels', methods=['GET'])
def get_write_risk_levels():
    """获取写入风险级别配置"""
    try:
        # 从内存缓存获取写入风险级别
        write_risk_levels = CACHED_WRITE_RISK_LEVELS
        return jsonify({'status': 'success', 'write_risk_levels': write_risk_levels})
    except Exception as e:
        logger.exception(f"获取写入风险级别失败: {e}")
        return jsonify({'status': 'error', 'error': f'获取写入风险级别失败: {str(e)}'}), 500

@app.route('/api/write_risk_levels', methods=['PUT'])
def update_write_risk_levels():
    """更新写入风险级别配置"""
    try:
        if not request.is_json:
            return jsonify({'status': 'error', 'error': '请求必须是JSON格式'}), 400
            
        write_risk_levels = request.json.get('write_risk_levels')
        if not write_risk_levels or not isinstance(write_risk_levels, list):
            return jsonify({'status': 'error', 'error': '写入风险级别格式无效'}), 400
            
        # 验证风险级别格式
        for level in write_risk_levels:
            if level not in ['High', 'Medium', 'Low']:
                return jsonify({'status': 'error', 'error': f'无效的风险等级: {level}'}), 400
                
        # 更新数据库和内存缓存中的写入风险级别
        success = update_system_setting('WRITE_RISK_LEVELS', write_risk_levels, '写入数据库的风险级别')
        if success:
            global CACHED_WRITE_RISK_LEVELS
            CACHED_WRITE_RISK_LEVELS = write_risk_levels
            return jsonify({
                'status': 'success', 
                'message': '写入风险级别已更新'
            })
        else:
            return jsonify({'status': 'error', 'error': '更新写入风险级别失败'}), 500
    except Exception as e:
        logger.exception(f"更新写入风险级别失败: {e}")
        return jsonify({'status': 'error', 'error': f'更新写入风险级别失败: {str(e)}'}), 500

# --- 应用运行 ---
if __name__ == '__main__':
    # 生产环境应设置 debug=False
    app.run(debug=True, host='0.0.0.0', port=5000)
