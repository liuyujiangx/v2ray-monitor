from __future__ import annotations

from datetime import datetime


def evaluate_monthly_alerts(
    total_bytes: int,
    total_quota_gb: int,
    user_totals: dict[str, int],
    user_quota_gb: dict[str, int],
    thresholds: list[int],
    now: datetime,
) -> list[dict]:
    alerts = []
    month_key = now.strftime("%Y-%m")
    total_quota_bytes = gb_to_bytes(total_quota_gb)

    alerts.extend(
        build_alerts(
            scope="total",
            name="AWS 免费额度",
            used_bytes=total_bytes,
            quota_bytes=total_quota_bytes,
            thresholds=thresholds,
            month_key=month_key,
        )
    )

    for user, used_bytes in user_totals.items():
        quota_gb = user_quota_gb.get(user)
        if quota_gb is None:
            continue

        alerts.extend(
            build_alerts(
                scope="user",
                name=user,
                used_bytes=used_bytes,
                quota_bytes=gb_to_bytes(quota_gb),
                thresholds=thresholds,
                month_key=month_key,
            )
        )

    return alerts


def build_alerts(
    scope: str,
    name: str,
    used_bytes: int,
    quota_bytes: int,
    thresholds: list[int],
    month_key: str,
) -> list[dict]:
    if quota_bytes <= 0:
        return []

    usage_percent = used_bytes / quota_bytes * 100
    alerts = []

    for threshold in thresholds:
        if usage_percent >= threshold:
            alerts.append(
                {
                    "alert_key": f"{month_key}:{scope}:{name}:{threshold}",
                    "scope": scope,
                    "name": name,
                    "threshold": threshold,
                    "usage_percent": round(usage_percent, 2),
                    "used_bytes": used_bytes,
                    "quota_bytes": quota_bytes,
                    "message": f"{name} 本月流量已达到 {round(usage_percent, 2)}%",
                }
            )

    return alerts


def gb_to_bytes(value: int) -> int:
    return value * 1024 * 1024 * 1024
