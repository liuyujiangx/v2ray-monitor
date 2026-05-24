from __future__ import annotations

from datetime import datetime, time

from app.config import AppConfig
from app.models import TrafficPair, usage_percent
from app.services.access_log import read_access_log
from app.services.history import HistoryStore
from app.services.v2ray import read_stats


def build_daily_usage_report(
    config: AppConfig,
    history: HistoryStore,
    now: datetime,
) -> dict:
    snapshot = read_stats(config.v2ray)
    record = history.record_snapshot(snapshot)

    today_start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    month_start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)

    today_users = history.sum_delta("user", today_start, now)
    month_users = history.sum_delta("user", month_start, now)
    today_total = sum_pairs(today_users)
    month_total = sum_pairs(month_users)
    quota_gb = config.traffic.monthly_quota_gb
    quota_bytes = quota_gb * 1024 * 1024 * 1024

    logs = read_access_log(config.logs.access_path, config.daily_report.log_max_lines)
    log_summary = logs.get("summary", {})
    top_limit = max(config.daily_report.top_limit, 1)

    return {
        "ok": snapshot.ok,
        "error": snapshot.error,
        "created_at": now,
        "quota_gb": quota_gb,
        "quota_bytes": quota_bytes,
        "today_total": today_total,
        "month_total": month_total,
        "month_usage_percent": usage_percent(month_total.total, quota_gb),
        "month_remaining_bytes": max(quota_bytes - month_total.total, 0),
        "users_today": sorted_pairs(today_users, top_limit),
        "users_month": sorted_pairs(month_users, top_limit),
        "speeds": sum_scope(record.speeds.get("user", {})),
        "logs_ok": bool(logs.get("ok")),
        "logs_error": logs.get("error"),
        "log_total": log_summary.get("total", 0),
        "top_targets": log_summary.get("top_targets", [])[:top_limit],
        "top_source_ips": log_summary.get("top_source_ips", [])[:top_limit],
        "latest_access_at": log_summary.get("latest_at"),
    }


def format_daily_usage_report(report: dict) -> tuple[str, str]:
    created_at = report["created_at"]
    date_text = created_at.strftime("%Y-%m-%d")
    subject = f"[V2Ray Monitor] 每日用量日报 {date_text}"

    lines = [
        "V2Ray Monitor 每日用量日报",
        "",
        f"生成时间: {created_at.isoformat(timespec='seconds')}",
        "",
        "总额度",
        f"- 月度总额度: {report['quota_gb']} GB",
        f"- 本月已用: {format_bytes(report['month_total'].total)}",
        f"- 本月剩余: {format_bytes(report['month_remaining_bytes'])}",
        f"- 本月使用率: {format_percent(report['month_usage_percent'])}",
        f"- 今日已用: {format_bytes(report['today_total'].total)}",
        f"- 当前速度: 上行 {format_bytes(report['speeds'].uplink)}/s, 下行 {format_bytes(report['speeds'].downlink)}/s",
        "",
        "本月用户用量排行",
        *format_pair_ranking(report["users_month"]),
        "",
        "今日用户用量排行",
        *format_pair_ranking(report["users_today"]),
        "",
        "访问最多的 URL / 目标地址",
        *format_count_ranking(report["top_targets"]),
        "",
        "使用过流量的来源 IP",
        *format_count_ranking(report["top_source_ips"]),
        "",
        "说明: URL 和来源 IP 来自 V2Ray access log，当前日志格式不包含字节数，因此这里统计的是访问次数，不是按流量字节排序。",
    ]

    if not report["ok"]:
        lines.extend(["", f"V2Ray API 状态: 异常 - {report['error'] or 'unknown error'}"])
    if not report["logs_ok"]:
        lines.extend(["", f"Access log 状态: 异常 - {report['logs_error'] or 'unknown error'}"])
    else:
        lines.extend(["", f"Access log 采样行数: {report['log_total']}"])
        if report["latest_access_at"]:
            lines.append(f"最近访问时间: {report['latest_access_at']}")

    return subject, "\n".join(lines)


def sorted_pairs(items: dict[str, TrafficPair], limit: int) -> list[tuple[str, TrafficPair]]:
    return sorted(items.items(), key=lambda entry: entry[1].total, reverse=True)[:limit]


def sum_pairs(items: dict[str, TrafficPair]) -> TrafficPair:
    total = TrafficPair()
    for traffic in items.values():
        total.uplink += traffic.uplink
        total.downlink += traffic.downlink
    return total


def sum_scope(items: dict[str, TrafficPair]) -> TrafficPair:
    return sum_pairs(items)


def format_pair_ranking(items: list[tuple[str, TrafficPair]]) -> list[str]:
    if not items:
        return ["- 无数据"]
    return [
        f"- {name}: {format_bytes(traffic.total)} (上行 {format_bytes(traffic.uplink)}, 下行 {format_bytes(traffic.downlink)})"
        for name, traffic in items
    ]


def format_count_ranking(items: list[dict]) -> list[str]:
    if not items:
        return ["- 无数据"]
    return [f"- {item['name']}: {item['count']} 次" for item in items]


def format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value or 0)
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    decimals = 0 if size >= 10 or unit_index == 0 else 2
    return f"{size:.{decimals}f} {units[unit_index]}"


def format_percent(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}%"
