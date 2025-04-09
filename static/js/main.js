// 使用 $(document).ready 确保 DOM 加载完毕后再执行脚本
$(document).ready(function() {
    // --- 全局变量 ---
    let currentPage = 1;
    const limit = 50;
    let currentStatsData = null;
    let currentRiskRules = null;
    let currentWriteRiskLevels = null;
    let currentServerToDelete = null;

    // --- 中文映射 ---
    const riskLevelMap = { 'Low': '低危', 'Medium': '中危', 'High': '高危' };

    // --- 初始化日期范围选择器 ---
    // (保持不变)
    const defaultStartDate = moment().subtract(6, 'days'); const defaultEndDate = moment(); try { $('#daterange').daterangepicker({ startDate: defaultStartDate, endDate: defaultEndDate, locale: { format: 'YYYY-MM-DD', applyLabel: '确定', cancelLabel: '取消', fromLabel: '从', toLabel: '到', customRangeLabel: '自定义范围', daysOfWeek: ['日', '一', '二', '三', '四', '五', '六'], monthNames: ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'], firstDay: 1 }, ranges: { '今天': [moment(), moment()], '昨天': [moment().subtract(1, 'days'), moment().subtract(1, 'days')], '最近 7 天': [moment().subtract(6, 'days'), moment()], '最近 30 天': [moment().subtract(29, 'days'), moment()], '本月': [moment().startOf('month'), moment().endOf('month')], '上个月': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')] } }, function(start, end, label) { /* console.log("...") */ fetchData(); }); $('#daterange').val(defaultStartDate.format('YYYY-MM-DD') + ' - ' + defaultEndDate.format('YYYY-MM-DD')); /* console.log(...) */ } catch (e) { console.error("初始化日期范围选择器失败:", e); $('#daterange').val('日期组件加载失败'); }

    // --- 数据获取函数 ---
    // (getFilters, fetchActivities, fetchStats 保持不变)
    function getFilters() { const serverId = $('#server-select').val(); const operationType = $('#operation-type-select').val(); const riskLevel = $('#risk-level-select').val(); const usernameValue = $('#username-input').val(); const userName = (typeof usernameValue === 'string') ? usernameValue.trim() : ''; let startDate = ''; let endDate = ''; try { const picker = $('#daterange').data('daterangepicker'); if (picker && picker.startDate && picker.startDate.isValid()) { startDate = picker.startDate.format('YYYY-MM-DD'); } else { /* console.warn(...) */ } if (picker && picker.endDate && picker.endDate.isValid()) { endDate = picker.endDate.format('YYYY-MM-DD'); } else { /* console.warn(...) */ } } catch (e) { console.error("从日期选择器获取日期时出错:", e); } /* console.log(...) */ return { serverId, startDate, endDate, operationType, riskLevel, userName }; }
    function fetchActivities(page = 1) { const filters = getFilters(); currentPage = page; const params = new URLSearchParams({ server_id: filters.serverId || '', start_date: filters.startDate || '', end_date: filters.endDate || '', operation_type: filters.operationType || '', risk_level: filters.riskLevel || '', user_name: filters.userName || '', page: currentPage, limit: limit }); /* console.log(...) */ showLoadingIndicator('activities-table-body'); fetch(`/api/activities?${params.toString()}`).then(response => { if (!response.ok) { return response.json().then(err => { throw new Error(err.error || `HTTP error ${response.status}`) }); } return response.json(); }).then(data => { /* console.log(...) */ renderActivitiesTable(data.activities || []); renderPagination(data.total || 0); hideLoadingIndicator('activities-table-body'); }).catch(error => { console.error('加载活动记录失败:', error); /* showErrorAlert(...) */ renderActivitiesTable([]); renderPagination(0); hideLoadingIndicator('activities-table-body'); }); }
    function fetchStats() { const filters = getFilters(); const params = new URLSearchParams({ server_id: filters.serverId || '', start_date: filters.startDate || '', end_date: filters.endDate || '' }); /* console.log(...) */ showLoadingIndicator('stats-container'); fetch(`/api/stats?${params.toString()}`).then(response => { if (!response.ok) { return response.json().then(err => { throw new Error(err.error || `HTTP error ${response.status}`) }); } return response.json(); }).then(data => { /* console.log(...) */ currentStatsData = data; renderDashboardCharts(); hideLoadingIndicator('stats-container'); }).catch(error => { console.error('加载统计数据失败:', error); /* showErrorAlert(...) */ currentStatsData = null; clearDashboardCharts(); hideLoadingIndicator('stats-container'); }); }

    // --- 渲染函数 ---

    // !! 修正 renderActivitiesTable 函数，初始化 badgeClass !!
    function renderActivitiesTable(activities) {
        const tableBody = $('#activities-table-body');
        tableBody.empty();

        if (!activities || activities.length === 0) {
            tableBody.append('<tr><td colspan="8" class="text-center text-gray-500 py-10">没有找到符合条件的记录</td></tr>');
            return;
        }

        activities.forEach(act => {
            const riskLevel = act.risk_level || 'Unknown';
            const riskLevelChinese = riskLevelMap[riskLevel] || riskLevel;
            // !! 在 switch 前初始化 badgeClass 为默认值 !!
            let badgeClass = 'risk-badge-unknown'; // 默认/未知风险的样式
            // let rowClass = ''; // 行背景色可以省略

            // 根据风险等级设置特定的徽章样式类
            switch (riskLevel) {
                case 'High':
                    badgeClass = 'risk-badge-high';
                    break;
                case 'Medium':
                    badgeClass = 'risk-badge-medium';
                    break;
                case 'Low':
                    badgeClass = 'risk-badge-low';
                    break;
                // default: // 因为已初始化，default 不是必需的了
                //     badgeClass = 'risk-badge-unknown';
            }

            // 构建表格行 HTML
            const row = `
                <tr>
                    <td class="px-4 py-2 border-b border-gray-200 text-gray-700">${act.id || 'N/A'}</td>
                    <td class="px-4 py-2 border-b border-gray-200 text-gray-700">${act.activity_time || 'N/A'}</td>
                    <td class="px-4 py-2 border-b border-gray-200 text-gray-700">${escapeHtml(act.user_name || 'N/A')}</td>
                    <td class="px-4 py-2 border-b border-gray-200 text-gray-700">${escapeHtml(act.client_host || 'N/A')}</td>
                    <td class="px-4 py-2 border-b border-gray-200 text-gray-700">${escapeHtml(act.db_name || 'N/A')}</td>
                    <td class="px-4 py-2 border-b border-gray-200 text-gray-700">${escapeHtml(act.operation_type || act.command_type || 'N/A')}</td>
                    <td class="px-4 py-2 border-b border-gray-200 text-xs text-gray-600 break-all">
                        <span title="${escapeHtml(act.argument || '')}">${escapeHtml(truncateString(act.argument || '', 100))}</span>
                        ${(act.argument || '').length > 100 ? '<button class="text-indigo-600 hover:text-indigo-800 text-xs ml-1 underline show-details-btn" data-details="' + escapeHtml(act.argument || '') + '">[详情]</button>' : ''}
                    </td>
                    <td class="px-4 py-2 border-b border-gray-200">
                        <span class="risk-badge ${badgeClass}">${escapeHtml(riskLevelChinese)}</span>
                    </td>
                </tr>
            `;
            tableBody.append(row);
        });
    }

    // (renderPagination, renderDashboardCharts, renderSingleChartSet, clearDashboardCharts 保持不变)
    function renderPagination(totalItems) { const totalPages = Math.ceil(totalItems / limit); const paginationContainer = $('#pagination'); paginationContainer.empty(); if (totalPages <= 1) return; let paginationHtml = '<div class="flex justify-center items-center space-x-2 mt-4">'; paginationHtml += `<button class="px-3 py-1 border rounded text-sm ${currentPage === 1 ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-white text-gray-700 hover:bg-gray-50'}" data-page="${currentPage - 1}" ${currentPage === 1 ? 'disabled' : ''}>上一页</button>`; paginationHtml += `<span class="text-sm text-gray-700">第 ${currentPage} / ${totalPages} 页</span>`; paginationHtml += `<button class="px-3 py-1 border rounded text-sm ${currentPage === totalPages ? 'bg-gray-100 text-gray-400 cursor-not-allowed' : 'bg-white text-gray-700 hover:bg-gray-50'}" data-page="${currentPage + 1}" ${currentPage === totalPages ? 'disabled' : ''}>下一页</button>`; paginationHtml += '</div>'; paginationContainer.html(paginationHtml); }
    function renderDashboardCharts() { if (!currentStatsData) { /* console.warn(...) */ clearDashboardCharts(); return; } renderSingleChartSet(currentStatsData); }
    function renderSingleChartSet(stats) { const riskChartId = `risk-levels-chart`; const opChartId = `op-types-chart`; const hourlyChartId = `hourly-chart`; const topUsersListId = `top-users-list`; const plotlyConfig = { responsive: true, displayModeBar: false }; try { const opTypesDataRaw = stats.operation_types || []; const opTypesLabels = opTypesDataRaw.map(item => item.operation_type || 'UNKNOWN'); const opTypesValues = opTypesDataRaw.map(item => item.count || 0); if (opTypesLabels.length > 0) { Plotly.newPlot(opChartId, [{labels: opTypesLabels, values: opTypesValues, type: 'pie', hole: .4, textinfo: 'percent', hoverinfo: 'label+value'}], {title: null, showlegend: true, legend: { x: 1, y: 0.5 }, margin: { l: 20, r: 20, t: 20, b: 20 }}, plotlyConfig); } else { $(`#${opChartId}`).html('<p class="text-center text-gray-500 py-4">无操作类型数据</p>'); } const riskLevelsData = stats.risk_levels || []; const riskLevelsLabels = riskLevelsData.map(item => riskLevelMap[item.risk_level] || item.risk_level || '未知'); const riskLevelsValues = riskLevelsData.map(item => item.count); if (riskLevelsLabels.length > 0) { Plotly.newPlot(riskChartId, [{ x: riskLevelsLabels, y: riskLevelsValues, type: 'bar', marker: { color: riskLevelsData.map(item => { if (item.risk_level === 'High') return '#ef4444'; if (item.risk_level === 'Medium') return '#f59e0b'; return '#10b981'; }) } }], {title: null, xaxis: { title: null }, yaxis: { title: '次数' }, margin: { l: 40, r: 20, t: 20, b: 30 } }, plotlyConfig); } else { $(`#${riskChartId}`).html('<p class="text-center text-gray-500 py-4">无风险等级数据</p>'); } const hourlyData = stats.hourly_distribution || {}; const hours = Object.keys(hourlyData).map(h => parseInt(h)).sort((a, b) => a - b); const hourlyCounts = hours.map(h => hourlyData[h]); if (hours.length > 0 && hourlyCounts.some(c => c > 0)) { Plotly.newPlot(hourlyChartId, [{x: hours.map(h => `${h}:00`), y: hourlyCounts, type: 'scatter', mode: 'lines+markers', line: {color: '#4f46e5'} }], {title: null, xaxis: { title: '时间 (小时)' }, yaxis: { title: '次数' }, margin: { l: 40, r: 20, t: 20, b: 30 }}, plotlyConfig); } else { $(`#${hourlyChartId}`).html('<p class="text-center text-gray-500 py-4">无小时分布数据</p>'); } const topUsersData = stats.top_users || []; const topUsersContainer = $(`#${topUsersListId}`); topUsersContainer.empty(); if (topUsersData.length > 0) { topUsersData.forEach((user, index) => { topUsersContainer.append(`<li class="py-1 flex justify-between"><span>${index + 1}. ${escapeHtml(user.user_name)}</span> <span class="font-medium">${user.count} 次</span></li>`); }); } else { topUsersContainer.html('<li class="text-center text-gray-500 py-4">无活跃用户数据</li>'); } } catch(e) { console.error(`渲染图表时出错:`, e); /* showErrorAlert(...) */ } }
    function clearDashboardCharts() { $('#op-types-chart').empty().html('<p class="text-center text-gray-500 py-4">等待加载数据...</p>'); $('#risk-levels-chart').empty().html('<p class="text-center text-gray-500 py-4">等待加载数据...</p>'); $('#hourly-chart').empty().html('<p class="text-center text-gray-500 py-4">等待加载数据...</p>'); $('#top-users-list').empty().html('<li class="text-center text-gray-500 py-4">等待加载数据...</li>'); }

    // --- 工具函数 ---
    // (保持不变)
    function showLoadingIndicator(elementId) { $(`#${elementId}`).css('opacity', 0.5); }
    function hideLoadingIndicator(elementId) { $(`#${elementId}`).css('opacity', 1); }
    function showErrorAlert(message) { console.error("Alert:", message); }
    function escapeHtml(unsafe) { if (!unsafe) return ''; return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;"); }
    function truncateString(str, num) { if (!str) return ''; if (str.length <= num) return str; return str.slice(0, num) + '...'; }

    // --- 事件绑定 ---
    // (保持不变)
    $('nav a[data-tab]').on('click', function(e) { e.preventDefault(); const tabId = $(this).data('tab'); const targetContentId = `#${tabId}-content`; const pageTitle = $(this).text(); /* console.log(...) */ $('nav a[data-tab]').removeClass('bg-gray-700 text-white').addClass('text-gray-300 hover:bg-gray-700 hover:text-white').attr('data-active', 'false'); $(this).removeClass('text-gray-300 hover:bg-gray-700 hover:text-white').addClass('bg-gray-700 text-white').attr('data-active', 'true'); $('.tab-content').addClass('hidden'); $(targetContentId).removeClass('hidden'); $('#main-content-title').text(pageTitle); if (currentStatsData && tabId === 'dashboard') { renderDashboardCharts(); } lucide.createIcons(); });
    $('#filter-btn').on('click', function() { fetchData(1); });
    $('#pagination').on('click', 'button', function() { const page = $(this).data('page'); if (page && page !== currentPage) { fetchActivities(page); } });
    $('#activities-table-body').on('click', '.show-details-btn', function() { const details = $(this).data('details'); $('#details-modal-content').text(details || '无详情'); $('#details-modal').removeClass('hidden'); lucide.createIcons(); });
    $('#details-modal-close, #details-modal-close-icon').on('click', function() { $('#details-modal').addClass('hidden'); });
    $('#details-modal').on('click', function(event) { if (event.target === this) { $(this).addClass('hidden'); } });
    $('#scan-logs-btn').on('click', function() { const scanButton = $(this); const statusDiv = $('#scan-status'); const indicatorDiv = $('#scan-indicator'); const serverId = $('#server-select').val(); const url = '/api/scan'; const payload = {}; let confirmMessage = '确定要扫描所有服务器的日志吗？'; if (serverId) { payload.server_id = parseInt(serverId); const serverName = $('#server-select option:selected').text(); confirmMessage = `确定要扫描服务器 "${serverName}" 的日志吗？`; } if (confirm(confirmMessage)) { scanButton.prop('disabled', true).text('扫描中...'); statusDiv.text(''); indicatorDiv.removeClass('hidden'); fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', }, body: JSON.stringify(payload), }).then(response => response.json().then(data => ({ status: response.status, body: data }))).then(({ status, body }) => { if (status >= 200 && status < 300 && body.status === 'success') { console.log("扫描请求成功:", body.message); statusDiv.text(body.message.includes("开始扫描") ? "扫描任务已提交" : "扫描完成").removeClass('text-red-500 text-gray-400').addClass('text-green-500'); fetchData(1); } else { throw new Error(body.error || body.message || `请求失败，状态码: ${status}`); } }).catch(error => { console.error('扫描日志请求失败:', error); statusDiv.text(`扫描失败: ${error.message}`).removeClass('text-green-500 text-gray-400').addClass('text-red-500'); }).finally(() => { scanButton.prop('disabled', false).text('扫描日志'); indicatorDiv.addClass('hidden'); setTimeout(() => { statusDiv.text('').removeClass('text-green-500 text-red-500'); }, 8000); }); } else { statusDiv.text(''); } });

    // --- 服务器配置相关函数 ---
    function fetchServers() {
        showLoadingIndicator('servers-table-body');
        fetch('/api/servers')
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || `HTTP error ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                renderServersTable(data.servers || []);
                hideLoadingIndicator('servers-table-body');
            })
            .catch(error => {
                console.error('加载服务器配置失败:', error);
                showErrorAlert(error.message || '加载服务器配置失败，请刷新页面重试。');
                renderServersTable([]);
                hideLoadingIndicator('servers-table-body');
            });
    }

    function renderServersTable(servers) {
        const tableBody = $('#servers-table-body');
        tableBody.empty();

        if (!servers || servers.length === 0) {
            tableBody.append('<tr><td colspan="8" class="text-center text-gray-500 py-10">暂无服务器配置，请点击 "添加服务器" 按钮添加</td></tr>');
            return;
        }

        servers.forEach(server => {
            // 构建认证方式显示
            let authDisplay;
            if (server.has_password) {
                authDisplay = '<span class="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs">密码</span>';
            } else if (server.has_ssh_key) {
                authDisplay = '<span class="bg-green-100 text-green-800 px-2 py-1 rounded text-xs">SSH密钥</span>';
            } else {
                authDisplay = '<span class="bg-gray-100 text-gray-600 px-2 py-1 rounded text-xs">未配置</span>';
            }

            // 构建日志扫描配置显示
            let logScanDisplay = [];
            if (server.enable_general_log) {
                logScanDisplay.push('<span class="bg-indigo-100 text-indigo-800 px-2 py-1 rounded text-xs mr-1">General</span>');
            }
            if (server.enable_binlog) {
                logScanDisplay.push('<span class="bg-purple-100 text-purple-800 px-2 py-1 rounded text-xs">Binlog</span>');
            }
            if (logScanDisplay.length === 0) {
                logScanDisplay.push('<span class="bg-gray-100 text-gray-600 px-2 py-1 rounded text-xs">未启用</span>');
            }

            const row = `
                <tr>
                    <td class="px-4 py-2 border-b border-gray-200 text-gray-700">${server.server_id || 'N/A'}</td>
                    <td class="px-4 py-2 border-b border-gray-200 text-gray-700">${escapeHtml(server.name || 'N/A')}</td>
                    <td class="px-4 py-2 border-b border-gray-200 text-gray-700">${escapeHtml(server.host || 'N/A')}</td>
                    <td class="px-4 py-2 border-b border-gray-200 text-gray-700">${server.port || 'N/A'}</td>
                    <td class="px-4 py-2 border-b border-gray-200 text-gray-700">${escapeHtml(server.user || 'N/A')}</td>
                    <td class="px-4 py-2 border-b border-gray-200">${authDisplay}</td>
                    <td class="px-4 py-2 border-b border-gray-200">${logScanDisplay.join('')}</td>
                    <td class="px-4 py-2 border-b border-gray-200">
                        <div class="flex space-x-2">
                            <button class="edit-server-btn text-blue-600 hover:text-blue-800" data-server-id="${server.server_id}">
                                <i data-lucide="edit" class="h-4 w-4"></i>
                            </button>
                            <button class="delete-server-btn text-red-600 hover:text-red-800" data-server-id="${server.server_id}">
                                <i data-lucide="trash-2" class="h-4 w-4"></i>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
            tableBody.append(row);
        });
        
        // 重新初始化Lucide图标
        lucide.createIcons();
    }

    function fetchServerDetails(serverId) {
        return fetch(`/api/server/${serverId}`)
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || `HTTP error ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                return data.server;
            });
    }

    function saveServer(formData, isNew) {
        const url = isNew ? '/api/server' : `/api/server/${formData.server_id}`;
        const method = isNew ? 'POST' : 'PUT';

        return fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData),
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || `HTTP error ${response.status}`);
                    });
                }
                return response.json();
            });
    }

    function deleteServer(serverId) {
        return fetch(`/api/server/${serverId}`, {
            method: 'DELETE',
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || `HTTP error ${response.status}`);
                    });
                }
                return response.json();
            });
    }

    function openServerModal(serverId = null) {
        // 重置表单
        $('#server-form')[0].reset();
        $('#server-id').val('');
        
        // 默认显示密码输入框
        $('#password-auth-container').show();
        $('#ssh-key-auth-container').hide();
        
        if (serverId) {
            // 编辑模式
            $('#server-modal-title').text('编辑服务器');
            
            // 获取服务器详情
            fetchServerDetails(serverId)
                .then(server => {
                    $('#server-id').val(server.server_id);
                    $('#server-name').val(server.name);
                    $('#server-host').val(server.host);
                    $('#server-port').val(server.port);
                    $('#server-user').val(server.user);
                    
                    // 设置认证方式
                    if (server.has_ssh_key) {
                        $('#server-auth-type').val('ssh_key');
                        $('#password-auth-container').hide();
                        $('#ssh-key-auth-container').show();
                    } else {
                        $('#server-auth-type').val('password');
                        $('#password-auth-container').show();
                        $('#ssh-key-auth-container').hide();
                    }
                    
                    $('#server-general-log').val(server.general_log_path);
                    $('#server-binlog').val(server.binlog_path);
                    $('#server-enable-general').prop('checked', server.enable_general_log);
                    $('#server-enable-binlog').prop('checked', server.enable_binlog);
                    
                    // 显示模态框
                    $('#server-modal').removeClass('hidden');
                })
                .catch(error => {
                    console.error('获取服务器详情失败:', error);
                    showErrorAlert(error.message || '获取服务器详情失败，请重试。');
                });
        } else {
            // 添加模式
            $('#server-modal-title').text('添加服务器');
            $('#server-modal').removeClass('hidden');
        }
    }

    function closeServerModal() {
        $('#server-modal').addClass('hidden');
    }

    // --- 风险规则相关函数 ---
    function fetchRiskRules() {
        fetch('/api/risk_rules')
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || `HTTP error ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                currentRiskRules = data.risk_rules;
                renderRiskRules(data.risk_rules);
            })
            .catch(error => {
                console.error('加载风险规则失败:', error);
                showErrorAlert(error.message || '加载风险规则失败，请刷新页面重试。');
            });
    }

    function renderRiskRules(riskRules) {
        // 渲染高风险规则
        renderRiskRuleList('high-risk-rules', riskRules.High || []);
        
        // 渲染中风险规则
        renderRiskRuleList('medium-risk-rules', riskRules.Medium || []);
        
        // 渲染低风险规则
        renderRiskRuleList('low-risk-rules', riskRules.Low || []);
    }

    function renderRiskRuleList(containerId, rules) {
        const container = $(`#${containerId}`);
        container.empty();
        
        if (!rules || rules.length === 0) {
            container.html('<p class="text-gray-500">暂无规则配置</p>');
            return;
        }
        
        let html = '<ul class="list-disc pl-5 space-y-1">';
        rules.forEach(rule => {
            if (rule.type) {
                html += `<li><strong>类型：</strong>${escapeHtml(rule.type)}</li>`;
            } else if (rule.keyword) {
                html += `<li><strong>关键字：</strong>${escapeHtml(rule.keyword)}</li>`;
            }
        });
        html += '</ul>';
        
        container.html(html);
    }

    function openRiskRulesModal() {
        // 如果还没有加载风险规则，先加载
        if (!currentRiskRules) {
            fetchRiskRules();
            return;
        }
        
        // 清空编辑区域
        $('#high-risk-items, #medium-risk-items, #low-risk-items').empty();
        
        // 填充高风险规则
        fillRiskRuleItems('high-risk-items', currentRiskRules.High || []);
        
        // 填充中风险规则
        fillRiskRuleItems('medium-risk-items', currentRiskRules.Medium || []);
        
        // 填充低风险规则
        fillRiskRuleItems('low-risk-items', currentRiskRules.Low || []);
        
        // 显示模态框
        $('#risk-rules-modal').removeClass('hidden');
    }

    function fillRiskRuleItems(containerId, rules) {
        const container = $(`#${containerId}`);
        
        rules.forEach((rule, index) => {
            addRuleItem(container, rule, index);
        });
    }

    function addRuleItem(container, rule = null, index = null) {
        const itemId = index !== null ? index : Date.now();
        let ruleType = '';
        let ruleKeyword = '';
        
        if (rule) {
            ruleType = rule.type || '';
            ruleKeyword = rule.keyword || '';
        }
        
        const html = `
            <div class="rule-item flex items-center gap-2 mb-2 p-2 bg-white rounded border border-gray-200">
                <div class="flex-1">
                    <div class="mb-1">
                        <label class="inline-flex items-center">
                            <input type="radio" name="rule-type-${itemId}" class="rule-type-radio" value="type" ${ruleType ? 'checked' : ''}>
                            <span class="ml-1 text-sm">类型</span>
                        </label>
                        <input type="text" class="rule-type-input ml-2 px-2 py-1 border border-gray-300 rounded text-sm ${!ruleType ? 'hidden' : ''}" value="${escapeHtml(ruleType)}">
                    </div>
                    <div>
                        <label class="inline-flex items-center">
                            <input type="radio" name="rule-type-${itemId}" class="rule-type-radio" value="keyword" ${ruleKeyword ? 'checked' : ''}>
                            <span class="ml-1 text-sm">关键字</span>
                        </label>
                        <input type="text" class="rule-keyword-input ml-2 px-2 py-1 border border-gray-300 rounded text-sm ${!ruleKeyword ? 'hidden' : ''}" value="${escapeHtml(ruleKeyword)}">
                    </div>
                </div>
                <button type="button" class="delete-rule-btn text-red-600 hover:text-red-800">
                    <i data-lucide="trash-2" class="h-4 w-4"></i>
                </button>
            </div>
        `;
        
        container.append(html);
        lucide.createIcons();
    }

    function closeRiskRulesModal() {
        $('#risk-rules-modal').addClass('hidden');
    }

    function saveRiskRules() {
        // 收集高风险规则
        const highRiskRules = collectRulesFromContainer('high-risk-items');
        
        // 收集中风险规则
        const mediumRiskRules = collectRulesFromContainer('medium-risk-items');
        
        // 收集低风险规则
        const lowRiskRules = collectRulesFromContainer('low-risk-items');
        
        // 构建提交数据
        const riskRules = {
            High: highRiskRules,
            Medium: mediumRiskRules,
            Low: lowRiskRules
        };
        
        return fetch('/api/risk_rules', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ risk_rules: riskRules }),
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || `HTTP error ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                currentRiskRules = riskRules;
                renderRiskRules(riskRules);
                closeRiskRulesModal();
            });
    }

    function collectRulesFromContainer(containerId) {
        const rules = [];
        $(`#${containerId} .rule-item`).each(function() {
            const $item = $(this);
            const typeRadio = $item.find('.rule-type-radio:checked').val();
            
            if (typeRadio === 'type') {
                const type = $item.find('.rule-type-input').val().trim();
                if (type) {
                    rules.push({ type });
                }
            } else if (typeRadio === 'keyword') {
                const keyword = $item.find('.rule-keyword-input').val().trim();
                if (keyword) {
                    rules.push({ keyword });
                }
            }
        });
        
        return rules;
    }

    // --- 写入风险级别相关函数 ---
    function fetchWriteRiskLevels() {
        fetch('/api/write_risk_levels')
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || `HTTP error ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                currentWriteRiskLevels = data.write_risk_levels;
                renderWriteRiskLevels(data.write_risk_levels);
            })
            .catch(error => {
                console.error('加载写入风险级别失败:', error);
                showErrorAlert(error.message || '加载写入风险级别失败，请刷新页面重试。');
            });
    }

    function renderWriteRiskLevels(levels) {
        const container = $('#write-risk-levels');
        container.empty();
        
        if (!levels || levels.length === 0) {
            container.html('<span class="risk-badge risk-badge-unknown">未配置</span>');
            return;
        }
        
        levels.forEach(level => {
            let badgeClass = 'risk-badge-unknown';
            if (level === 'High') {
                badgeClass = 'risk-badge-high';
            } else if (level === 'Medium') {
                badgeClass = 'risk-badge-medium';
            } else if (level === 'Low') {
                badgeClass = 'risk-badge-low';
            }
            
            container.append(`<span class="risk-badge ${badgeClass}">${riskLevelMap[level] || level}</span>`);
        });
    }

    function openWriteLevelsModal() {
        // 如果还没有加载写入风险级别，先加载
        if (!currentWriteRiskLevels) {
            fetchWriteRiskLevels();
            return;
        }
        
        // 重置选中状态
        $('#write-high, #write-medium, #write-low').prop('checked', false);
        
        // 根据当前配置选中对应的复选框
        if (currentWriteRiskLevels.includes('High')) {
            $('#write-high').prop('checked', true);
        }
        if (currentWriteRiskLevels.includes('Medium')) {
            $('#write-medium').prop('checked', true);
        }
        if (currentWriteRiskLevels.includes('Low')) {
            $('#write-low').prop('checked', true);
        }
        
        // 显示模态框
        $('#write-levels-modal').removeClass('hidden');
    }

    function closeWriteLevelsModal() {
        $('#write-levels-modal').addClass('hidden');
    }

    function saveWriteRiskLevels() {
        // 收集选中的风险级别
        const levels = [];
        if ($('#write-high').prop('checked')) {
            levels.push('High');
        }
        if ($('#write-medium').prop('checked')) {
            levels.push('Medium');
        }
        if ($('#write-low').prop('checked')) {
            levels.push('Low');
        }
        
        return fetch('/api/write_risk_levels', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ write_risk_levels: levels }),
        })
            .then(response => {
                if (!response.ok) {
                    return response.json().then(err => {
                        throw new Error(err.error || `HTTP error ${response.status}`);
                    });
                }
                return response.json();
            })
            .then(data => {
                currentWriteRiskLevels = levels;
                renderWriteRiskLevels(levels);
                closeWriteLevelsModal();
            });
    }

    function openDeleteConfirmModal(serverId) {
        currentServerToDelete = serverId;
        $('#confirm-delete-modal').removeClass('hidden');
    }

    function closeDeleteConfirmModal() {
        currentServerToDelete = null;
        $('#confirm-delete-modal').addClass('hidden');
    }

    // --- 服务器配置相关事件绑定 ---
    // 添加服务器按钮
    $('#add-server-btn').on('click', function() {
        openServerModal();
    });
    
    // 服务器表单认证类型切换
    $('#server-auth-type').on('change', function() {
        const authType = $(this).val();
        if (authType === 'password') {
            $('#password-auth-container').show();
            $('#ssh-key-auth-container').hide();
        } else if (authType === 'ssh_key') {
            $('#password-auth-container').hide();
            $('#ssh-key-auth-container').show();
        }
    });
    
    // 服务器表单提交
    $('#server-form').on('submit', function(e) {
        e.preventDefault();
        
        // 收集表单数据
        const serverId = $('#server-id').val();
        const formData = {
            name: $('#server-name').val(),
            host: $('#server-host').val(),
            port: parseInt($('#server-port').val(), 10),
            user: $('#server-user').val(),
            auth_type: $('#server-auth-type').val(),
            general_log_path: $('#server-general-log').val(),
            binlog_path: $('#server-binlog').val(),
            enable_general_log: $('#server-enable-general').prop('checked'),
            enable_binlog: $('#server-enable-binlog').prop('checked')
        };
        
        // 添加认证信息
        if (formData.auth_type === 'password') {
            formData.password = $('#server-password').val();
        } else if (formData.auth_type === 'ssh_key') {
            formData.ssh_key_path = $('#server-ssh-key').val();
        }
        
        // 如果是编辑模式，添加ID
        if (serverId) {
            formData.server_id = parseInt(serverId, 10);
        }
        
        // 保存服务器配置
        saveServer(formData, !serverId)
            .then(data => {
                closeServerModal();
                fetchServers();
            })
            .catch(error => {
                console.error('保存服务器配置失败:', error);
                showErrorAlert(error.message || '保存服务器配置失败，请重试。');
            });
    });
    
    // 服务器模态框关闭按钮
    $('#server-modal-close-icon, #server-modal-cancel').on('click', function() {
        closeServerModal();
    });
    
    // 服务器模态框点击背景关闭
    $('#server-modal').on('click', function(event) {
        if (event.target === this) {
            closeServerModal();
        }
    });
    
    // 编辑服务器按钮
    $(document).on('click', '.edit-server-btn', function() {
        const serverId = $(this).data('server-id');
        openServerModal(serverId);
    });
    
    // 删除服务器按钮
    $(document).on('click', '.delete-server-btn', function() {
        const serverId = $(this).data('server-id');
        openDeleteConfirmModal(serverId);
    });
    
    // 确认删除按钮
    $('#confirm-delete-confirm').on('click', function() {
        if (currentServerToDelete) {
            deleteServer(currentServerToDelete)
                .then(data => {
                    closeDeleteConfirmModal();
                    fetchServers();
                })
                .catch(error => {
                    console.error('删除服务器配置失败:', error);
                    showErrorAlert(error.message || '删除服务器配置失败，请重试。');
                });
        }
    });
    
    // 取消删除按钮
    $('#confirm-delete-cancel').on('click', function() {
        closeDeleteConfirmModal();
    });
    
    // 确认删除模态框点击背景关闭
    $('#confirm-delete-modal').on('click', function(event) {
        if (event.target === this) {
            closeDeleteConfirmModal();
        }
    });
    
    // --- 风险规则相关事件绑定 ---
    // 编辑风险规则按钮
    $('#edit-risk-rules-btn').on('click', function() {
        openRiskRulesModal();
    });
    
    // 风险规则模态框关闭按钮
    $('#risk-rules-modal-close-icon, #risk-rules-modal-cancel').on('click', function() {
        closeRiskRulesModal();
    });
    
    // 风险规则模态框点击背景关闭
    $('#risk-rules-modal').on('click', function(event) {
        if (event.target === this) {
            closeRiskRulesModal();
        }
    });
    
    // 添加风险规则按钮
    $('.add-rule-btn').on('click', function() {
        const level = $(this).data('level');
        const container = $(`#${level.toLowerCase()}-risk-items`);
        addRuleItem(container);
    });
    
    // 规则类型单选按钮切换
    $(document).on('change', '.rule-type-radio', function() {
        const value = $(this).val();
        const $item = $(this).closest('.rule-item');
        
        if (value === 'type') {
            $item.find('.rule-type-input').removeClass('hidden');
            $item.find('.rule-keyword-input').addClass('hidden');
        } else if (value === 'keyword') {
            $item.find('.rule-type-input').addClass('hidden');
            $item.find('.rule-keyword-input').removeClass('hidden');
        }
    });
    
    // 删除规则按钮
    $(document).on('click', '.delete-rule-btn', function() {
        $(this).closest('.rule-item').remove();
    });
    
    // 风险规则表单提交
    $('#risk-rules-form').on('submit', function(e) {
        e.preventDefault();
        
        saveRiskRules()
            .catch(error => {
                console.error('保存风险规则失败:', error);
                showErrorAlert(error.message || '保存风险规则失败，请重试。');
            });
    });
    
    // --- 写入风险级别相关事件绑定 ---
    // 编辑写入级别按钮
    $('#edit-write-levels-btn').on('click', function() {
        openWriteLevelsModal();
    });
    
    // 写入级别模态框关闭按钮
    $('#write-levels-modal-close-icon, #write-levels-modal-cancel').on('click', function() {
        closeWriteLevelsModal();
    });
    
    // 写入级别模态框点击背景关闭
    $('#write-levels-modal').on('click', function(event) {
        if (event.target === this) {
            closeWriteLevelsModal();
        }
    });
    
    // 写入级别表单提交
    $('#write-levels-form').on('submit', function(e) {
        e.preventDefault();
        
        saveWriteRiskLevels()
            .catch(error => {
                console.error('保存写入风险级别失败:', error);
                showErrorAlert(error.message || '保存写入风险级别失败，请重试。');
            });
    });
    
    // 当切换到配置页面时加载配置数据
    $('nav a[data-tab="config"]').on('click', function() {
        fetchServers();
        fetchRiskRules();
        fetchWriteRiskLevels();
    });

    // --- 初始数据加载 ---
    function fetchData(page = 1) { 
        fetchActivities(page); 
        fetchStats(); 
    }
    setTimeout(fetchData, 150);
    lucide.createIcons();

}); // end of $(document).ready
