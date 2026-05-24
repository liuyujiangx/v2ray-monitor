from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from app.models import StatsSnapshot, TrafficPair


SCHEMA = """
CREATE TABLE IF NOT EXISTS traffic_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    name TEXT NOT NULL,
    direction TEXT NOT NULL,
    value_bytes INTEGER NOT NULL,
    delta_bytes INTEGER NOT NULL,
    sampled_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_traffic_samples_lookup
ON traffic_samples (scope, name, direction, sampled_at);

CREATE TABLE IF NOT EXISTS alert_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_key TEXT NOT NULL UNIQUE,
    scope TEXT NOT NULL,
    name TEXT NOT NULL,
    threshold INTEGER NOT NULL,
    usage_percent REAL NOT NULL,
    used_bytes INTEGER NOT NULL,
    quota_bytes INTEGER NOT NULL,
    message TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_alert_events_created_at
ON alert_events (created_at);

CREATE TABLE IF NOT EXISTS notification_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_key TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_notification_events_created_at
ON notification_events (created_at);
"""


@dataclass
class SampleMetric:
    value_bytes: int
    delta_bytes: int
    seconds: float
    sampled_at: str = ""

    @property
    def bytes_per_second(self) -> float:
        if self.seconds <= 0:
            return 0
        return self.delta_bytes / self.seconds


@dataclass
class SnapshotRecord:
    speeds: dict[str, dict[str, TrafficPair]] = field(
        default_factory=lambda: {"user": {}, "inbound": {}, "outbound": {}}
    )
    deltas: dict[str, dict[str, TrafficPair]] = field(
        default_factory=lambda: {"user": {}, "inbound": {}, "outbound": {}}
    )


class HistoryStore:
    def __init__(self, database_path: str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def record_snapshot(self, snapshot: StatsSnapshot) -> SnapshotRecord:
        record = SnapshotRecord()
        if not snapshot.ok:
            return record

        sampled_at = snapshot.updated_at.isoformat()
        rows = []

        for scope, items in iter_snapshot(snapshot):
            for name, traffic in items.items():
                rows.append((scope, name, "uplink", traffic.uplink, sampled_at))
                rows.append((scope, name, "downlink", traffic.downlink, sampled_at))

        with sqlite3.connect(self.path) as conn:
            for scope, name, direction, value, sampled in rows:
                previous = self._latest_sample(conn, scope, name, direction)
                delta = max(value - previous.value_bytes, 0) if previous else 0
                seconds = seconds_between(previous.sampled_at, sampled) if previous else 0
                speed = delta / seconds if seconds > 0 else 0

                delta_pair = record.deltas[scope].setdefault(name, TrafficPair())
                speed_pair = record.speeds[scope].setdefault(name, TrafficPair())
                setattr(delta_pair, direction, delta)
                setattr(speed_pair, direction, int(speed))

                conn.execute(
                    """
                    INSERT INTO traffic_samples
                    (scope, name, direction, value_bytes, delta_bytes, sampled_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (scope, name, direction, value, delta, sampled),
                )

        return record

    def sum_delta(
        self,
        scope: str,
        since: datetime,
        until: datetime | None = None,
    ) -> dict[str, TrafficPair]:
        until = until or datetime.now(since.tzinfo)
        result: dict[str, TrafficPair] = {}

        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                """
                SELECT name, direction, SUM(delta_bytes)
                FROM traffic_samples
                WHERE scope = ?
                  AND sampled_at >= ?
                  AND sampled_at < ?
                GROUP BY name, direction
                """,
                (scope, since.isoformat(), until.isoformat()),
            ).fetchall()

        for name, direction, value in rows:
            traffic = result.setdefault(name, TrafficPair())
            setattr(traffic, direction, int(value or 0))

        return result

    def recent_points(
        self,
        scope: str,
        since: datetime,
        until: datetime | None = None,
    ) -> list[dict]:
        until = until or datetime.now(since.tzinfo)

        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                """
                SELECT sampled_at, SUM(delta_bytes)
                FROM traffic_samples
                WHERE scope = ?
                  AND sampled_at >= ?
                  AND sampled_at < ?
                GROUP BY sampled_at
                ORDER BY sampled_at ASC
                """,
                (scope, since.isoformat(), until.isoformat()),
            ).fetchall()

        return [
            {
                "sampled_at": sampled_at,
                "bytes": int(value or 0),
            }
            for sampled_at, value in rows
        ]

    def create_alert_event(
        self,
        alert_key: str,
        scope: str,
        name: str,
        threshold: int,
        usage_percent: float,
        used_bytes: int,
        quota_bytes: int,
        message: str,
        created_at: datetime,
    ) -> bool:
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    """
                    INSERT INTO alert_events
                    (alert_key, scope, name, threshold, usage_percent, used_bytes,
                     quota_bytes, message, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        alert_key,
                        scope,
                        name,
                        threshold,
                        usage_percent,
                        used_bytes,
                        quota_bytes,
                        message,
                        created_at.isoformat(),
                    ),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def list_alert_events(self, limit: int = 20) -> list[dict]:
        with sqlite3.connect(self.path) as conn:
            rows = conn.execute(
                """
                SELECT scope, name, threshold, usage_percent, used_bytes,
                       quota_bytes, message, created_at
                FROM alert_events
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            {
                "scope": scope,
                "name": name,
                "threshold": threshold,
                "usage_percent": usage_percent,
                "used_bytes": used_bytes,
                "quota_bytes": quota_bytes,
                "message": message,
                "created_at": created_at,
            }
            for (
                scope,
                name,
                threshold,
                usage_percent,
                used_bytes,
                quota_bytes,
                message,
                created_at,
            ) in rows
        ]

    def create_notification_event(
        self,
        event_key: str,
        kind: str,
        created_at: datetime,
    ) -> bool:
        try:
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    """
                    INSERT INTO notification_events (event_key, kind, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (event_key, kind, created_at.isoformat()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def notification_event_exists(self, event_key: str) -> bool:
        with sqlite3.connect(self.path) as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM notification_events
                WHERE event_key = ?
                LIMIT 1
                """,
                (event_key,),
            ).fetchone()
        return row is not None

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)

    @staticmethod
    def _latest_sample(
        conn: sqlite3.Connection,
        scope: str,
        name: str,
        direction: str,
    ) -> SampleMetric | None:
        row = conn.execute(
            """
            SELECT value_bytes, delta_bytes, sampled_at
            FROM traffic_samples
            WHERE scope = ? AND name = ? AND direction = ?
            ORDER BY sampled_at DESC, id DESC
            LIMIT 1
            """,
            (scope, name, direction),
        ).fetchone()
        if not row:
            return None

        return SampleMetric(
            value_bytes=int(row[0]),
            delta_bytes=int(row[1]),
            seconds=0,
            sampled_at=row[2],
        )


def iter_snapshot(snapshot: StatsSnapshot):
    yield "user", snapshot.users
    yield "inbound", snapshot.inbound
    yield "outbound", snapshot.outbound


def seconds_between(previous: str, current: str) -> float:
    previous_dt = datetime.fromisoformat(previous)
    current_dt = datetime.fromisoformat(current)
    return max((current_dt - previous_dt).total_seconds(), 0)
