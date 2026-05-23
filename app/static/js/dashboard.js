const refreshSeconds = window.V2RAY_MONITOR?.refreshSeconds || 2;

let latestLogs = [];
let selectedLogUser = "";
let logSearch = "";

const elements = {
    statusText: document.getElementById("status-text"),
    monthUsed: document.getElementById("month-used"),
    monthRemaining: document.getElementById("month-remaining"),
    todayTraffic: document.getElementById("today-traffic"),
    monthUsage: document.getElementById("month-usage"),
    totalUplink: document.getElementById("total-uplink"),
    totalDownlink: document.getElementById("total-downlink"),
    totalTraffic: document.getElementById("total-traffic"),
    updatedAt: document.getElementById("updated-at"),
    usersBody: document.getElementById("users-body"),
    inboundBody: document.getElementById("inbound-body"),
    outboundBody: document.getElementById("outbound-body"),
    alertsList: document.getElementById("alerts-list"),
    logsBody: document.getElementById("logs-body"),
    logSearch: document.getElementById("log-search"),
    logUserFilter: document.getElementById("log-user-filter"),
    logTotal: document.getElementById("log-total"),
    logLatest: document.getElementById("log-latest"),
    logIpCount: document.getElementById("log-ip-count"),
    targetRank: document.getElementById("target-rank"),
    sourceRank: document.getElementById("source-rank"),
    refreshButton: document.getElementById("refresh-button"),
};

function formatBytes(bytes) {
    const units = ["B", "KB", "MB", "GB", "TB"];
    let value = Number(bytes || 0);
    let unitIndex = 0;

    while (value >= 1024 && unitIndex < units.length - 1) {
        value /= 1024;
        unitIndex += 1;
    }

    return `${value.toFixed(value >= 10 || unitIndex === 0 ? 0 : 2)} ${units[unitIndex]}`;
}

function formatSpeed(bytes) {
    return `${formatBytes(bytes)}/s`;
}

function formatDate(value) {
    if (!value) {
        return "-";
    }

    return new Date(value).toLocaleString();
}

function quotaText(stat) {
    if (!stat?.quota_gb) {
        return '<span class="muted">未设置</span>';
    }

    return `${stat.quota_gb} GB`;
}

function usageCell(stat) {
    if (stat?.usage_percent === null || stat?.usage_percent === undefined) {
        return '<span class="muted">-</span>';
    }

    const value = Math.min(Number(stat.usage_percent), 100);
    const cssClass = stat.usage_percent >= 100
        ? "danger"
        : stat.usage_percent >= 80
            ? "warning"
            : "good";

    return `
        <div class="usage">
            <span class="usage-track"><span class="${cssClass}" style="width: ${value}%"></span></span>
            <span>${stat.usage_percent}%</span>
        </div>
    `;
}

function renderUsers(data) {
    elements.usersBody.innerHTML = "";
    const users = data.users || {};
    const monthUsers = data.month?.users || {};
    const todayUsers = data.today?.users || {};
    const speeds = data.speeds?.user || {};

    if (Object.keys(users).length === 0) {
        elements.usersBody.innerHTML = '<tr><td colspan="8" class="muted">暂无数据</td></tr>';
        return;
    }

    for (const [name, stat] of Object.entries(users)) {
        const month = monthUsers[name] || {};
        const today = todayUsers[name] || {};
        const speed = speeds[name] || {};
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${escapeHtml(name)}</td>
            <td>${formatBytes(stat.uplink)}</td>
            <td>${formatBytes(stat.downlink)}</td>
            <td>${formatSpeed((speed.uplink || 0) + (speed.downlink || 0))}</td>
            <td>${formatBytes(today.total)}</td>
            <td>${formatBytes(month.total)}</td>
            <td>${quotaText(month)}</td>
            <td>${usageCell(month)}</td>
        `;
        elements.usersBody.appendChild(tr);
    }
}

function renderRows(tbody, items) {
    tbody.innerHTML = "";

    if (!items || Object.keys(items).length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="muted">暂无数据</td></tr>';
        return;
    }

    for (const [name, stat] of Object.entries(items)) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${escapeHtml(name)}</td>
            <td>${formatBytes(stat.uplink)}</td>
            <td>${formatBytes(stat.downlink)}</td>
            <td>${formatBytes(stat.total)}</td>
        `;
        tbody.appendChild(tr);
    }
}

function renderAlerts(alerts) {
    elements.alertsList.innerHTML = "";

    if (!alerts || alerts.length === 0) {
        elements.alertsList.innerHTML = '<div class="empty">暂无告警</div>';
        return;
    }

    for (const alert of alerts) {
        const item = document.createElement("div");
        item.className = "alert-item";
        item.innerHTML = `
            <div>
                <strong>${escapeHtml(alert.message)}</strong>
                <span>${formatDate(alert.created_at)} · 阈值 ${alert.threshold}%</span>
            </div>
            <b>${formatBytes(alert.used_bytes)}</b>
        `;
        elements.alertsList.appendChild(item);
    }
}

function renderLogSummary(data) {
    const summary = data.summary || {};
    elements.logTotal.textContent = summary.total ?? 0;
    elements.logLatest.textContent = formatDate(summary.latest_at);
    elements.logIpCount.textContent = summary.top_source_ips?.length ?? 0;
    renderRank(elements.targetRank, summary.top_targets || []);
    renderRank(elements.sourceRank, summary.top_source_ips || []);
}

function renderRank(target, items) {
    target.innerHTML = "";
    if (items.length === 0) {
        target.innerHTML = '<li class="muted">暂无数据</li>';
        return;
    }

    for (const item of items) {
        const li = document.createElement("li");
        li.innerHTML = `<span>${escapeHtml(item.name)}</span><b>${item.count}</b>`;
        target.appendChild(li);
    }
}

function renderLogFilters(entries) {
    const users = Array.from(new Set(entries.map((entry) => entry.email).filter(Boolean))).sort();
    const current = selectedLogUser;
    elements.logUserFilter.innerHTML = '<option value="">全部用户</option>';

    for (const user of users) {
        const option = document.createElement("option");
        option.value = user;
        option.textContent = user;
        option.selected = user === current;
        elements.logUserFilter.appendChild(option);
    }
}

function renderLogs() {
    elements.logsBody.innerHTML = "";
    const keyword = logSearch.trim().toLowerCase();

    const rows = latestLogs.filter((entry) => {
        if (selectedLogUser && entry.email !== selectedLogUser) {
            return false;
        }

        if (!keyword) {
            return true;
        }

        return [
            entry.email,
            entry.source_ip,
            entry.target,
            entry.outbound,
            entry.protocol,
        ].some((value) => String(value || "").toLowerCase().includes(keyword));
    }).slice(0, 100);

    if (rows.length === 0) {
        elements.logsBody.innerHTML = '<tr><td colspan="5" class="muted">暂无匹配日志</td></tr>';
        return;
    }

    for (const entry of rows) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${formatDate(entry.timestamp)}</td>
            <td>${escapeHtml(entry.email || "-")}</td>
            <td>${escapeHtml(entry.source_ip)}:${entry.source_port}</td>
            <td>${escapeHtml(entry.protocol)}:${escapeHtml(entry.target)}:${entry.target_port}</td>
            <td>${escapeHtml(entry.outbound)}</td>
        `;
        elements.logsBody.appendChild(tr);
    }
}

async function fetchStats() {
    try {
        const response = await fetch("/api/stats");
        const data = await response.json();

        if (!data.ok) {
            elements.statusText.textContent = data.error || "V2Ray API 异常";
            return;
        }

        elements.statusText.textContent = "V2Ray API 连接正常";
        elements.monthUsed.textContent = formatBytes(data.month?.total?.total);
        elements.monthRemaining.textContent = formatBytes(data.month?.total?.remaining);
        elements.todayTraffic.textContent = formatBytes(data.today?.total?.total);
        elements.monthUsage.innerHTML = usageCell(data.month?.total);
        elements.totalUplink.textContent = formatSpeed(data.speeds?.userTotal?.uplink || data.speeds?.user_total?.uplink || 0);
        elements.totalDownlink.textContent = formatSpeed(data.speeds?.userTotal?.downlink || data.speeds?.user_total?.downlink || 0);
        elements.totalTraffic.textContent = formatBytes(data.total.total);
        elements.updatedAt.textContent = formatDate(data.updated_at);

        const userSpeeds = Object.values(data.speeds?.user || {}).reduce(
            (total, item) => ({
                uplink: total.uplink + (item.uplink || 0),
                downlink: total.downlink + (item.downlink || 0),
            }),
            { uplink: 0, downlink: 0 }
        );
        elements.totalUplink.textContent = formatSpeed(userSpeeds.uplink);
        elements.totalDownlink.textContent = formatSpeed(userSpeeds.downlink);

        renderUsers(data);
        renderRows(elements.inboundBody, data.inbound);
        renderRows(elements.outboundBody, data.outbound);
        renderAlerts(data.alerts);
    } catch (error) {
        elements.statusText.textContent = `请求失败：${error.message}`;
    }
}

async function fetchLogs() {
    try {
        const response = await fetch("/api/logs/recent");
        const data = await response.json();

        if (!data.ok) {
            latestLogs = [];
            elements.logsBody.innerHTML = `<tr><td colspan="5" class="muted">${escapeHtml(data.error || "访问日志不可用")}</td></tr>`;
            renderLogSummary(data);
            return;
        }

        latestLogs = data.entries || [];
        renderLogSummary(data);
        renderLogFilters(latestLogs);
        renderLogs();
    } catch (error) {
        elements.logsBody.innerHTML = `<tr><td colspan="5" class="muted">日志请求失败：${escapeHtml(error.message)}</td></tr>`;
    }
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

elements.refreshButton.addEventListener("click", () => {
    fetchStats();
    fetchLogs();
});

elements.logSearch.addEventListener("input", (event) => {
    logSearch = event.target.value;
    renderLogs();
});

elements.logUserFilter.addEventListener("change", (event) => {
    selectedLogUser = event.target.value;
    renderLogs();
});

setInterval(fetchStats, refreshSeconds * 1000);
setInterval(fetchLogs, Math.max(refreshSeconds * 1000, 5000));
fetchStats();
fetchLogs();
