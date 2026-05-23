const refreshSeconds = window.V2RAY_MONITOR?.refreshSeconds || 2;

const elements = {
    statusText: document.getElementById("status-text"),
    totalUplink: document.getElementById("total-uplink"),
    totalDownlink: document.getElementById("total-downlink"),
    totalTraffic: document.getElementById("total-traffic"),
    updatedAt: document.getElementById("updated-at"),
    usersBody: document.getElementById("users-body"),
    inboundBody: document.getElementById("inbound-body"),
    outboundBody: document.getElementById("outbound-body"),
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

function formatDate(value) {
    if (!value) {
        return "-";
    }

    return new Date(value).toLocaleString();
}

function quotaText(stat) {
    if (!stat.quota_gb) {
        return '<span class="muted">未设置</span>';
    }

    return `${stat.quota_gb} GB`;
}

function usageText(stat) {
    if (stat.usage_percent === null || stat.usage_percent === undefined) {
        return '<span class="muted">-</span>';
    }

    const cssClass = stat.usage_percent >= 100
        ? "danger"
        : stat.usage_percent >= 80
            ? "warning"
            : "";

    return `<span class="${cssClass}">${stat.usage_percent}%</span>`;
}

function renderRows(tbody, items, options = {}) {
    tbody.innerHTML = "";

    if (!items || Object.keys(items).length === 0) {
        const tr = document.createElement("tr");
        const colSpan = options.users ? 6 : 4;
        tr.innerHTML = `<td colspan="${colSpan}" class="muted">暂无数据</td>`;
        tbody.appendChild(tr);
        return;
    }

    for (const [name, stat] of Object.entries(items)) {
        const tr = document.createElement("tr");

        if (options.users) {
            tr.innerHTML = `
                <td>${name}</td>
                <td>${formatBytes(stat.uplink)}</td>
                <td>${formatBytes(stat.downlink)}</td>
                <td>${formatBytes(stat.total)}</td>
                <td>${quotaText(stat)}</td>
                <td>${usageText(stat)}</td>
            `;
        } else {
            tr.innerHTML = `
                <td>${name}</td>
                <td>${formatBytes(stat.uplink)}</td>
                <td>${formatBytes(stat.downlink)}</td>
                <td>${formatBytes(stat.total)}</td>
            `;
        }

        tbody.appendChild(tr);
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
        elements.totalUplink.textContent = formatBytes(data.total.uplink);
        elements.totalDownlink.textContent = formatBytes(data.total.downlink);
        elements.totalTraffic.textContent = formatBytes(data.total.total);
        elements.updatedAt.textContent = formatDate(data.updated_at);

        renderRows(elements.usersBody, data.users, { users: true });
        renderRows(elements.inboundBody, data.inbound);
        renderRows(elements.outboundBody, data.outbound);
    } catch (error) {
        elements.statusText.textContent = `请求失败：${error.message}`;
    }
}

elements.refreshButton.addEventListener("click", fetchStats);
setInterval(fetchStats, refreshSeconds * 1000);
fetchStats();

