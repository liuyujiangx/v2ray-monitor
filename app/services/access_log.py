from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import re


LOG_PATTERN = re.compile(
    r"^(?P<time>\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) "
    r"(?P<source_ip>[^:\s]+):(?P<source_port>\d+) "
    r"(?P<status>\w+) "
    r"(?P<protocol>\w+):(?P<target>.+):(?P<target_port>\d+) "
    r"\[(?P<outbound>[^\]]+)\](?: email: (?P<email>.+))?$"
)


@dataclass(frozen=True)
class AccessLogEntry:
    timestamp: str
    source_ip: str
    source_port: int
    status: str
    protocol: str
    target: str
    target_port: int
    outbound: str
    email: str | None
    raw: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "source_ip": self.source_ip,
            "source_port": self.source_port,
            "status": self.status,
            "protocol": self.protocol,
            "target": self.target,
            "target_port": self.target_port,
            "outbound": self.outbound,
            "email": self.email,
            "raw": self.raw,
        }


def read_access_log(path: str, max_lines: int = 500) -> dict:
    log_path = Path(path)
    if not log_path.exists():
        return {
            "ok": False,
            "error": f"Access log not found: {path}",
            "entries": [],
            "summary": empty_summary(),
        }

    try:
        lines = tail_lines(log_path, max_lines)
    except OSError as exc:
        return {
            "ok": False,
            "error": str(exc),
            "entries": [],
            "summary": empty_summary(),
        }

    entries = [entry for line in lines if (entry := parse_line(line))]
    entries.reverse()

    return {
        "ok": True,
        "error": None,
        "entries": [entry.to_dict() for entry in entries[:max_lines]],
        "summary": summarize(entries),
    }


def tail_lines(path: Path, max_lines: int) -> list[str]:
    with path.open("r", encoding="utf-8", errors="replace") as fp:
        lines = fp.readlines()
    return [line.strip() for line in lines[-max_lines:] if line.strip()]


def parse_line(line: str) -> AccessLogEntry | None:
    match = LOG_PATTERN.match(line)
    if not match:
        return None

    data = match.groupdict()
    timestamp = datetime.strptime(data["time"], "%Y/%m/%d %H:%M:%S").isoformat()

    return AccessLogEntry(
        timestamp=timestamp,
        source_ip=data["source_ip"],
        source_port=int(data["source_port"]),
        status=data["status"],
        protocol=data["protocol"],
        target=data["target"],
        target_port=int(data["target_port"]),
        outbound=data["outbound"],
        email=data.get("email"),
        raw=line,
    )


def summarize(entries: list[AccessLogEntry]) -> dict:
    targets = Counter(entry.target for entry in entries)
    source_ips = Counter(entry.source_ip for entry in entries)
    users = Counter(entry.email or "unknown" for entry in entries)

    return {
        "total": len(entries),
        "top_targets": counter_items(targets),
        "top_source_ips": counter_items(source_ips),
        "users": counter_items(users),
        "latest_at": entries[0].timestamp if entries else None,
    }


def counter_items(counter: Counter, limit: int = 8) -> list[dict]:
    return [
        {"name": name, "count": count}
        for name, count in counter.most_common(limit)
    ]


def empty_summary() -> dict:
    return {
        "total": 0,
        "top_targets": [],
        "top_source_ips": [],
        "users": [],
        "latest_at": None,
    }
