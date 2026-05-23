from __future__ import annotations

import sqlite3
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
"""


class HistoryStore:
    def __init__(self, database_path: str) -> None:
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def record_snapshot(self, snapshot: StatsSnapshot) -> None:
        if not snapshot.ok:
            return

        sampled_at = snapshot.updated_at.isoformat()
        rows = []

        for scope, items in iter_snapshot(snapshot):
            for name, traffic in items.items():
                rows.append((scope, name, "uplink", traffic.uplink, sampled_at))
                rows.append((scope, name, "downlink", traffic.downlink, sampled_at))

        with sqlite3.connect(self.path) as conn:
            for scope, name, direction, value, sampled in rows:
                previous = self._latest_value(conn, scope, name, direction)
                delta = max(value - previous, 0) if previous is not None else 0
                conn.execute(
                    """
                    INSERT INTO traffic_samples
                    (scope, name, direction, value_bytes, delta_bytes, sampled_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (scope, name, direction, value, delta, sampled),
                )

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

    def _init_db(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SCHEMA)

    @staticmethod
    def _latest_value(
        conn: sqlite3.Connection,
        scope: str,
        name: str,
        direction: str,
    ) -> int | None:
        row = conn.execute(
            """
            SELECT value_bytes
            FROM traffic_samples
            WHERE scope = ? AND name = ? AND direction = ?
            ORDER BY sampled_at DESC, id DESC
            LIMIT 1
            """,
            (scope, name, direction),
        ).fetchone()
        return int(row[0]) if row else None


def iter_snapshot(snapshot: StatsSnapshot):
    yield "user", snapshot.users
    yield "inbound", snapshot.inbound
    yield "outbound", snapshot.outbound

