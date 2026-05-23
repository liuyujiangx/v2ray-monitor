from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class TrafficPair:
    uplink: int = 0
    downlink: int = 0

    @property
    def total(self) -> int:
        return self.uplink + self.downlink

    def to_dict(self) -> dict[str, int]:
        return {
            "uplink": self.uplink,
            "downlink": self.downlink,
            "total": self.total,
        }


@dataclass
class StatsSnapshot:
    ok: bool
    users: dict[str, TrafficPair] = field(default_factory=dict)
    inbound: dict[str, TrafficPair] = field(default_factory=dict)
    outbound: dict[str, TrafficPair] = field(default_factory=dict)
    error: str | None = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def total(self) -> TrafficPair:
        total = TrafficPair()
        for item in self.users.values():
            total.uplink += item.uplink
            total.downlink += item.downlink
        return total

    def to_dict(self, quotas: dict[str, int] | None = None) -> dict:
        quotas = quotas or {}

        return {
            "ok": self.ok,
            "error": self.error,
            "updated_at": self.updated_at.isoformat(),
            "total": self.total.to_dict(),
            "users": {
                name: {
                    **traffic.to_dict(),
                    "quota_gb": quotas.get(name),
                    "usage_percent": usage_percent(traffic.total, quotas.get(name)),
                }
                for name, traffic in sorted(
                    self.users.items(),
                    key=lambda entry: entry[1].total,
                    reverse=True,
                )
            },
            "inbound": serialize_sorted(self.inbound),
            "outbound": serialize_sorted(self.outbound),
        }


def serialize_sorted(items: dict[str, TrafficPair]) -> dict[str, dict[str, int]]:
    return {
        name: traffic.to_dict()
        for name, traffic in sorted(
            items.items(),
            key=lambda entry: entry[1].total,
            reverse=True,
        )
    }


def usage_percent(total_bytes: int, quota_gb: int | None) -> float | None:
    if not quota_gb:
        return None

    quota_bytes = quota_gb * 1024 * 1024 * 1024
    return round(total_bytes / quota_bytes * 100, 2)

