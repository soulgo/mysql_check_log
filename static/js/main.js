// 使用 $(document).ready 确保 DOM 加载完毕后再执行脚本
$(document).ready(function() {
    // --- 全局变量 ---
    let currentPage = 1;
    const limit = 50;
    let currentStatsData = null;

    // --- 中文映射 ---
    const riskLevelMap = { 'Low': '低危', 'Medium': '中危', 'High': '高危' };
    // 不再需要 crudTypes 变量
    // const crudTypes = ['SELECT', 'INSERT', 'UPDATE', 'DELETE'];

    // --- 初始化日期范围选择器 ---
    // (保持不变)
    const defaultStartDate = moment().subtract(6, 'days'); const defaultEndDate = moment(); try { $('#daterange').daterangepicker({ startDate: defaultStartDate, endDate: defaultEndDate, locale: { format: 'YYYY-MM-DD', applyLabel: '确定', cancelLabel: '取消', fromLabel: '从', toLabel: '到', customRangeLabel: '自定义范围', daysOfWeek: ['日', '一', '二', '三', '四', '五', '六'], monthNames: ['一月', '二月', '三月', '四月', '五月', '六月', '七月', '八月', '九月', '十月', '十一月', '十二月'], firstDay: 1 }, ranges: { '今天': [moment(), moment()], '昨天': [moment().subtract(1, 'days'), moment().subtract(1, 'days')], '最近 7 天': [moment().subtract(6, 'days'), moment()], '最近 30 天': [moment().subtract(29, 'days'), moment()], '本月': [moment().startOf('month'), moment().endOf('month')], '上个月': [moment().subtract(1, 'month').startOf('month'), moment().subtract(1, 'month').endOf('month')] } }, function(start, end, label) { console.log("选择了新的日期范围: " + start.format('YYYY-MM-DD') + ' 到 ' + end.format('YYYY-MM-DD')); fetchData(); }); $('#daterange').val(defaultStartDate.format('YYYY-MM-DD') + ' - ' + defaultEndDate.format('YYYY-MM-DD')); console.log("日期范围选择器初始化成功。"); } catch (e) { console.error("初始化日期范围选择器失败:", e); $('#daterange').val('日期组件加载失败'); }

    // --- 数据获取函数 ---
    // (getFilters, fetchActivities, fetchStats 保持不变)
    function getFilters() { const serverId = $('#server-select').val(); const operationType = $('#operation-type-select').val(); const riskLevel = $('#risk-level-select').val(); const usernameValue = $('#username-input').val(); const userName = (typeof usernameValue === 'string') ? usernameValue.trim() : ''; let startDate = ''; let endDate = ''; try { const picker = $('#daterange').data('daterangepicker'); if (picker && picker.startDate && picker.startDate.isValid()) { startDate = picker.startDate.format('YYYY-MM-DD'); } else { console.warn("无法获取有效的开始日期 (picker:", picker, ")，将使用空值。"); } if (picker && picker.endDate && picker.endDate.isValid()) { endDate = picker.endDate.format('YYYY-MM-DD'); } else { console.warn("无法获取有效的结束日期 (picker:", picker, ")，将使用空值。"); } } catch (e) { console.error("从日期选择器获取日期时出错:", e); } console.log("当前筛选条件:", { serverId, startDate, endDate, operationType, riskLevel, userName }); return { serverId, startDate, endDate, operationType, riskLevel, userName }; }
    function fetchActivities(page = 1) { const filters = getFilters(); currentPage = page; const params = new URLSearchParams({ server_id: filters.serverId || '', start_date: filters.startDate || '', end_date: filters.endDate || '', operation_type: filters.operationType || '', risk_level: filters.riskLevel || '', user_name: filters.userName || '', page: currentPage, limit: limit }); console.log("请求活动记录 API:", `/api/activities?${params.toString()}`); showLoadingIndicator('activities-table-body'); fetch(`/api/activities?${params.toString()}`).then(response => { if (!response.ok) { return response.json().then(err => { throw new Error(err.error || `HTTP error ${response.status}`) }); } return response.json(); }).then(data => { console.log("收到活动记录数据:", data); renderActivitiesTable(data.activities || []); renderPagination(data.total || 0); hideLoadingIndicator('activities-table-body'); }).catch(error => { console.error('加载活动记录失败:', error); showErrorAlert(`加载活动记录失败: ${error.message}`); renderActivitiesTable([]); renderPagination(0); hideLoadingIndicator('activities-table-body'); }); }
    function fetchStats() { const filters = getFilters(); const params = new URLSearchParams({ server_id: filters.serverId || '', start_date: filters.startDate || '', end_date: filters.endDate || '' }); console.log("请求统计数据 API:", `/api/stats?${params.toString()}`); showLoadingIndicator('stats-container'); fetch(`/api/stats?${params.toString()}`).then(response => { if (!response.ok) { return response.json().then(err => { throw new Error(err.error || `HTTP error ${response.status}`) }); } return response.json(); }).then(data => { console.log("收到统计数据:", data); currentStatsData = data; renderDashboardCharts(); hideLoadingIndicator('stats-container'); }).catch(error => { console.error('加载统计数据失败:', error); showErrorAlert(`加载统计数据失败: ${error.message}`); currentStatsData = null; clearDashboardCharts(); hideLoadingIndicator('stats-container'); }); }


    // --- 渲染函数 ---
    // (renderActivitiesTable, renderPagination 保持不变)
    function renderActivitiesTable(activities) { const tableBody = $('#activities-table-body'); tableBody.empty(); if (!activities || activities.length === 0) { tableBody.append('<tr><td colspan="8" class="text-center text-gray-500 py-4">没有找到符合条件的记录</td></tr>'); return; } activities.forEach(act => { let riskClass = ''; const riskLevelChinese = riskLevelMap[act.risk_level] || act.risk_level || '未知'; switch (act.risk_level) { case 'High': riskClass = 'bg-red-100 text-red-800'; break; case 'Medium': riskClass = 'bg-yellow-100 text-yellow-800'; break; case 'Low': riskClass = 'bg-green-100 text-green-800'; break; default: riskClass = 'bg-gray-100 text-gray-800'; } const row = `<tr class="${riskClass}"><td class="px-4 py-2 border">${act.id || 'N/A'}</td><td class="px-4 py-2 border">${act.activity_time || 'N/A'}</td><td class="px-4 py-2 border">${escapeHtml(act.user_name || 'N/A')}</td><td class="px-4 py-2 border">${escapeHtml(act.client_host || 'N/A')}</td><td class="px-4 py-2 border">${escapeHtml(act.db_name || 'N/A')}</td><td class="px-4 py-2 border">${escapeHtml(act.operation_type || act.command_type || 'N/A')}</td><td class="px-4 py-2 border text-xs break-all" title="${escapeHtml(act.argument || '')}">${escapeHtml(truncateString(act.argument || '', 100))}${(act.argument || '').length > 100 ? '<button class="text-blue-500 text-xs ml-1 show-details-btn" data-details="' + escapeHtml(act.argument || '') + '">[详情]</button>' : ''}</td><td class="px-4 py-2 border font-semibold">${escapeHtml(riskLevelChinese)}</td></tr>`; tableBody.append(row); }); }
    function renderPagination(totalItems) { const totalPages = Math.ceil(totalItems / limit); const paginationContainer = $('#pagination'); paginationContainer.empty(); if (totalPages <= 1) return; let paginationHtml = '<div class="flex justify-center items-center space-x-2 mt-4">'; paginationHtml += `<button class="px-3 py-1 border rounded ${currentPage === 1 ? 'bg-gray-200 text-gray-400 cursor-not-allowed' : 'bg-white text-blue-600 hover:bg-blue-50'}" data-page="${currentPage - 1}" ${currentPage === 1 ? 'disabled' : ''}>上一页</button>`; paginationHtml += `<span class="text-gray-700">第 ${currentPage} / ${totalPages} 页</span>`; paginationHtml += `<button class="px-3 py-1 border rounded ${currentPage === totalPages ? 'bg-gray-200 text-gray-400 cursor-not-allowed' : 'bg-white text-blue-600 hover:bg-blue-50'}" data-page="${currentPage + 1}" ${currentPage === totalPages ? 'disabled' : ''}>下一页</button>`; paginationHtml += '</div>'; paginationContainer.html(paginationHtml); }

    // (renderDashboardCharts 保持不变)
    function renderDashboardCharts() { if (!currentStatsData) { console.warn("没有可用的统计数据。"); clearDashboardCharts(); return; } renderSingleChartSet(currentStatsData); }

    // !! 修改 renderSingleChartSet 以显示详细的操作类型 !!
    function renderSingleChartSet(stats) {
        const riskChartId = `risk-levels-chart`;
        const opChartId = `op-types-chart`;
        const hourlyChartId = `hourly-chart`;
        const topUsersListId = `top-users-list`;
        const plotlyConfig = { responsive: true, displayModeBar: false }; // 隐藏模式栏

        try {
            // 1. 操作类型分布饼图 (显示详细类型，不再简化)
            const opTypesDataRaw = stats.operation_types || [];
            // !! 直接使用从 API 获取的原始数据 !!
            const opTypesLabels = opTypesDataRaw.map(item => item.operation_type || 'UNKNOWN');
            const opTypesValues = opTypesDataRaw.map(item => item.count || 0);

            if (opTypesLabels.length > 0) {
                Plotly.newPlot(opChartId, [{
                    labels: opTypesLabels, // 使用详细标签
                    values: opTypesValues, // 使用详细计数值
                    type: 'pie', hole: .4, textinfo: 'percent', hoverinfo: 'label+value'
                }], {title: '操作类型分布', showlegend: true, legend: { x: 1, y: 0.5 }}, plotlyConfig);
            } else { $(`#${opChartId}`).html('<p class="text-center text-gray-500 py-4">无操作类型数据</p>'); }

            // 2. 风险等级分布条形图 (保持不变，使用中文标签)
            const riskLevelsData = stats.risk_levels || []; const riskLevelsLabels = riskLevelsData.map(item => riskLevelMap[item.risk_level] || item.risk_level || '未知'); const riskLevelsValues = riskLevelsData.map(item => item.count); if (riskLevelsLabels.length > 0) { Plotly.newPlot(riskChartId, [{ x: riskLevelsLabels, y: riskLevelsValues, type: 'bar', marker: { color: riskLevelsData.map(item => { if (item.risk_level === 'High') return 'rgba(239, 68, 68, 0.7)'; if (item.risk_level === 'Medium') return 'rgba(245, 158, 11, 0.7)'; return 'rgba(16, 185, 129, 0.7)'; }) } }], {title: '风险等级分布', xaxis: { title: '风险等级' }, yaxis: { title: '次数' }}, plotlyConfig); } else { $(`#${riskChartId}`).html('<p class="text-center text-gray-500 py-4">无风险等级数据</p>'); }

            // 3. 小时分布折线图 (保持不变)
            const hourlyData = stats.hourly_distribution || {}; const hours = Object.keys(hourlyData).map(h => parseInt(h)).sort((a, b) => a - b); const hourlyCounts = hours.map(h => hourlyData[h]); if (hours.length > 0 && hourlyCounts.some(c => c > 0)) { Plotly.newPlot(hourlyChartId, [{x: hours.map(h => `${h}:00`), y: hourlyCounts, type: 'scatter', mode: 'lines+markers'}], {title: '操作次数按小时分布', xaxis: { title: '时间 (小时)' }, yaxis: { title: '次数' }}, plotlyConfig); } else { $(`#${hourlyChartId}`).html('<p class="text-center text-gray-500 py-4">无小时分布数据</p>'); }

            // 4. Top 用户排行 (保持不变)
            const topUsersData = stats.top_users || []; const topUsersContainer = $(`#${topUsersListId}`); topUsersContainer.empty(); if (topUsersData.length > 0) { topUsersData.forEach((user, index) => { topUsersContainer.append(`<li class="py-1">${index + 1}. ${escapeHtml(user.user_name)}: ${user.count} 次</li>`); }); } else { topUsersContainer.html('<li class="text-center text-gray-500 py-4">无活跃用户数据</li>'); }
        } catch(e) {
             console.error(`渲染图表时出错:`, e);
             showErrorAlert(`渲染统计图表时出错，请检查控制台。`);
        }
    }

    // (clearDashboardCharts 保持不变)
    function clearDashboardCharts() { $('#op-types-chart').empty().html('<p class="text-center text-gray-500 py-4">等待加载数据...</p>'); $('#risk-levels-chart').empty().html('<p class="text-center text-gray-500 py-4">等待加载数据...</p>'); $('#hourly-chart').empty().html('<p class="text-center text-gray-500 py-4">等待加载数据...</p>'); $('#top-users-list').empty().html('<li class="text-center text-gray-500 py-4">等待加载数据...</li>'); }

    // --- 工具函数 ---
    // (保持不变)
    function showLoadingIndicator(elementId) { $(`#${elementId}`).css('opacity', 0.5); }
    function hideLoadingIndicator(elementId) { $(`#${elementId}`).css('opacity', 1); }
    function showErrorAlert(message) { alert(message); }
    function escapeHtml(unsafe) { if (!unsafe) return ''; return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;"); }
    function truncateString(str, num) { if (!str) return ''; if (str.length <= num) return str; return str.slice(0, num) + '...'; }

    // --- 事件绑定 ---
    // (保持不变)
    $('nav a[data-tab]').on('click', function(e) { e.preventDefault(); const tabId = $(this).data('tab'); const targetContentId = `#${tabId}-content`; const pageTitle = $(this).text(); console.log(`切换到 Tab: ${tabId}`); $('nav a[data-tab]').removeClass('bg-gray-700'); $(this).addClass('bg-gray-700'); $('.tab-content').addClass('hidden'); $(targetContentId).removeClass('hidden'); $('#main-content-title').text(pageTitle); if (currentStatsData && tabId === 'dashboard') { renderDashboardCharts(); } });
    $('#filter-btn').on('click', function() { fetchData(1); });
    $('#pagination').on('click', 'button', function() { const page = $(this).data('page'); if (page && page !== currentPage) { fetchActivities(page); } });
    $('#activities-table-body').on('click', '.show-details-btn', function() { const details = $(this).data('details'); $('#details-modal-content').text(details || '无详情'); $('#details-modal').removeClass('hidden'); });
    $('#details-modal-close').on('click', function() { $('#details-modal').addClass('hidden'); });
    $('#details-modal').on('click', function(event) { if (event.target === this) { $(this).addClass('hidden'); } });
    $('#scan-logs-btn').on('click', function() { const serverId = $('#server-select').val(); const url = '/api/scan'; const payload = {}; let message = '确定要扫描所有服务器的日志吗？'; if (serverId) { payload.server_id = parseInt(serverId); const serverName = $('#server-select option:selected').text(); message = `确定要扫描服务器 "${serverName}" 的日志吗？`; } if (confirm(message)) { $(this).prop('disabled', true).text('扫描中...'); fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', }, body: JSON.stringify(payload), }).then(response => response.json().then(data => ({ status: response.status, body: data }))).then(({ status, body }) => { if (status >= 200 && status < 300) { console.log("扫描请求成功:", body.message); } else { throw new Error(body.error || `请求失败，状态码: ${status}`); } }).catch(error => { console.error('扫描日志请求失败:', error); }).finally(() => { $(this).prop('disabled', false).text('扫描日志'); }); } });

    // --- 初始数据加载 ---
    function fetchData(page = 1) { fetchActivities(page); fetchStats(); }
    setTimeout(fetchData, 100);

}); // end of $(document).ready
