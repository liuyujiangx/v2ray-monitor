from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT_DIR / "config.toml"


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass(frozen=True)
class V2RayConfig:
    api_address: str = "127.0.0.1:10085"
    command: str = "v2ray"


@dataclass(frozen=True)
class DashboardConfig:
    refresh_seconds: int = 2


@dataclass(frozen=True)
class AuthConfig:
    enabled: bool = False
    username: str = "admin"
    password: str = "change-me"


@dataclass(frozen=True)
class DatabaseConfig:
    path: str = "data/traffic.sqlite3"


@dataclass(frozen=True)
class TrafficConfig:
    monthly_quota_gb: int = 100


@dataclass(frozen=True)
class LogsConfig:
    access_path: str = "/var/log/v2ray/access.log"
    max_lines: int = 500


@dataclass(frozen=True)
class EmailAlertsConfig:
    smtp_host: str = ""
    smtp_port: int = 587
    use_tls: bool = True
    use_ssl: bool = False
    username: str = ""
    password: str = ""
    from_addr: str = ""
    to_addrs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AlertsConfig:
    enabled: bool = False
    provider: str = "none"
    thresholds: list[int] = field(default_factory=lambda: [80, 90, 100])
    email: EmailAlertsConfig = field(default_factory=EmailAlertsConfig)


@dataclass(frozen=True)
class DailyReportConfig:
    enabled: bool = False
    send_time: str = "09:00"
    top_limit: int = 10
    log_max_lines: int = 2000


@dataclass(frozen=True)
class AppConfig:
    server: ServerConfig = field(default_factory=ServerConfig)
    v2ray: V2RayConfig = field(default_factory=V2RayConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    traffic: TrafficConfig = field(default_factory=TrafficConfig)
    logs: LogsConfig = field(default_factory=LogsConfig)
    quota: dict[str, int] = field(default_factory=dict)
    alerts: AlertsConfig = field(default_factory=AlertsConfig)
    daily_report: DailyReportConfig = field(default_factory=DailyReportConfig)


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    if not path.exists():
        return AppConfig()

    try:
        import tomllib
    except ModuleNotFoundError:  # Python 3.10 and earlier
        import tomli as tomllib

    with path.open("rb") as fp:
        raw = tomllib.load(fp)

    return AppConfig(
        server=ServerConfig(**raw.get("server", {})),
        v2ray=V2RayConfig(**raw.get("v2ray", {})),
        dashboard=DashboardConfig(**raw.get("dashboard", {})),
        auth=AuthConfig(**raw.get("auth", {})),
        database=DatabaseConfig(**raw.get("database", {})),
        traffic=TrafficConfig(**raw.get("traffic", {})),
        logs=LogsConfig(**raw.get("logs", {})),
        quota=raw.get("quota", {}),
        alerts=_load_alerts_config(raw.get("alerts", {})),
        daily_report=DailyReportConfig(**raw.get("daily_report", {})),
    )


def _load_alerts_config(raw: dict) -> AlertsConfig:
    data = dict(raw)
    email_raw = data.pop("email", {})
    return AlertsConfig(
        email=EmailAlertsConfig(**email_raw),
        **data,
    )
