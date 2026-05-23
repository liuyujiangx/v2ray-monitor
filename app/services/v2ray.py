from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from app.config import V2RayConfig
from app.models import StatsSnapshot, TrafficPair


def read_stats(config: V2RayConfig) -> StatsSnapshot:
    cmd = [
        config.command,
        "api",
        "stats",
        f"-server={config.api_address}",
        "-json",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            check=False,
            text=True,
            timeout=8,
        )
    except FileNotFoundError:
        return StatsSnapshot(
            ok=False,
            error=f"Command not found: {config.command}",
            updated_at=datetime.now(timezone.utc),
        )
    except subprocess.TimeoutExpired:
        return StatsSnapshot(
            ok=False,
            error="V2Ray API command timed out",
            updated_at=datetime.now(timezone.utc),
        )

    if result.returncode != 0:
        return StatsSnapshot(
            ok=False,
            error=result.stderr.strip() or "V2Ray API command failed",
            updated_at=datetime.now(timezone.utc),
        )

    try:
        raw = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return StatsSnapshot(
            ok=False,
            error="V2Ray API returned invalid JSON",
            updated_at=datetime.now(timezone.utc),
        )

    return parse_stats(raw)


def parse_stats(raw: dict) -> StatsSnapshot:
    snapshot = StatsSnapshot(ok=True, updated_at=datetime.now(timezone.utc))

    for item in raw.get("stat", []):
        name = item.get("name", "")
        value = int(item.get("value", 0))
        parts = name.split(">>>")

        if len(parts) < 4:
            continue

        scope, item_name, _, direction = parts[:4]
        if direction not in {"uplink", "downlink"}:
            continue

        bucket = {
            "user": snapshot.users,
            "inbound": snapshot.inbound,
            "outbound": snapshot.outbound,
        }.get(scope)

        if bucket is None:
            continue

        traffic = bucket.setdefault(item_name, TrafficPair())
        setattr(traffic, direction, value)

    return snapshot

