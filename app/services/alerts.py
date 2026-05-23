from __future__ import annotations

from app.models import StatsSnapshot


def evaluate_quota_alerts(snapshot: StatsSnapshot, quotas: dict[str, int]) -> list[dict]:
    alerts = []

    for user, traffic in snapshot.users.items():
        quota_gb = quotas.get(user)
        if not quota_gb:
            continue

        quota_bytes = quota_gb * 1024 * 1024 * 1024
        percent = traffic.total / quota_bytes * 100

        for threshold in (80, 90, 100):
            if percent >= threshold:
                alerts.append(
                    {
                        "user": user,
                        "threshold": threshold,
                        "usage_percent": round(percent, 2),
                    }
                )

    return alerts

