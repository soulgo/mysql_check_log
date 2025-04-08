// 使用 $(document).ready 确保 DOM 加载完毕后再执行脚本
$(document).ready(function() {
    // --- 全局变量 ---
    let currentPage = 1;
    const limit = 50;
    let currentStatsData = null;

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

    // --- 初始数据加载 ---
    function fetchData(page = 1) { fetchActivities(page); fetchStats(); }
    setTimeout(fetchData, 150);
    lucide.createIcons();

}); // end of $(document).ready
