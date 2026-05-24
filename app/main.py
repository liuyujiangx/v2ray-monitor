from __future__ import annotations

import asyncio
import logging
import secrets
from pathlib import Path
from typing import Optional
from datetime import datetime, time, timedelta

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import ROOT_DIR, load_config
from app.models import TrafficPair, usage_percent
from app.services.access_log import read_access_log
from app.services.alerts import evaluate_monthly_alerts
from app.services.history import HistoryStore
from app.services.notify import notify_new_alert, send_email_report
from app.services.reports import build_daily_usage_report, format_daily_usage_report
from app.services.v2ray import read_stats


config = load_config()
app = FastAPI(title="V2Ray Monitor")
security = HTTPBasic(auto_error=False)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

history = HistoryStore(str(ROOT_DIR / config.database.path))
daily_report_task: asyncio.Task | None = None


@app.on_event("startup")
async def start_daily_report_scheduler() -> None:
    global daily_report_task
    if not config.daily_report.enabled:
        return
    daily_report_task = asyncio.create_task(daily_report_loop())


@app.on_event("shutdown")
async def stop_daily_report_scheduler() -> None:
    if daily_report_task is None:
        return
    daily_report_task.cancel()
    try:
        await daily_report_task
    except asyncio.CancelledError:
        pass


async def daily_report_loop() -> None:
    while True:
        try:
            await maybe_send_daily_report()
        except Exception:
            logger.exception("Daily report scheduler failed")
        await asyncio.sleep(60)


async def maybe_send_daily_report() -> None:
    now = datetime.now().astimezone()
    send_time = parse_send_time(config.daily_report.send_time)
    if send_time is None:
        logger.warning(
            "Invalid daily_report.send_time %r; expected HH:MM",
            config.daily_report.send_time,
        )
        return
    if now.time() < send_time:
        return

    event_key = f"daily-report:{now:%Y-%m-%d}"
    if history.notification_event_exists(event_key):
        return

    sent = await asyncio.to_thread(send_daily_report, now)
    if sent:
        history.create_notification_event(event_key, "daily_report", now)


def send_daily_report(now: datetime) -> bool:
    report = build_daily_usage_report(config, history, now)
    subject, body = format_daily_usage_report(report)
    return send_email_report(config.alerts.email, subject, body)


def parse_send_time(value: str) -> time | None:
    try:
        hour_text, minute_text = value.strip().split(":", 1)
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return time(hour=hour, minute=minute)


def require_auth(credentials: Optional[HTTPBasicCredentials] = Depends(security)) -> None:
    if not config.auth.enabled:
        return

    if credentials is None:
        raise_unauthorized()

    username_ok = secrets.compare_digest(credentials.username, config.auth.username)
    password_ok = secrets.compare_digest(credentials.password, config.auth.password)

    if not (username_ok and password_ok):
        raise_unauthorized()


def raise_unauthorized() -> None:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Basic"},
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request, _: None = Depends(require_auth)):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "refresh_seconds": config.dashboard.refresh_seconds,
        },
    )


@app.get("/api/stats", response_class=JSONResponse)
def api_stats(_: None = Depends(require_auth)):
    snapshot = read_stats(config.v2ray)
    record = history.record_snapshot(snapshot)

    now = datetime.now().astimezone()
    today_start = datetime.combine(now.date(), time.min, tzinfo=now.tzinfo)
    month_start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
    recent_start = now - timedelta(hours=24)

    today_users = history.sum_delta("user", today_start, now)
    month_users = history.sum_delta("user", month_start, now)
    today_total = sum_pairs(today_users)
    month_total = sum_pairs(month_users)

    for alert in evaluate_monthly_alerts(
        total_bytes=month_total.total,
        total_quota_gb=config.traffic.monthly_quota_gb,
        thresholds=config.alerts.thresholds,
        now=now,
    ):
        if history.create_alert_event(
            alert_key=alert["alert_key"],
            scope=alert["scope"],
            name=alert["name"],
            threshold=alert["threshold"],
            usage_percent=alert["usage_percent"],
            used_bytes=alert["used_bytes"],
            quota_bytes=alert["quota_bytes"],
            message=alert["message"],
            created_at=now,
        ):
            notify_new_alert(config, alert, now)

    payload = snapshot.to_dict(quotas=config.quota)
    payload.update(
        {
            "speeds": serialize_scope(record.speeds),
            "today": {
                "total": today_total.to_dict(),
                "users": serialize_pairs(today_users),
            },
            "month": {
                "total": {
                    **month_total.to_dict(),
                    "quota_gb": config.traffic.monthly_quota_gb,
                    "usage_percent": usage_percent(
                        month_total.total,
                        config.traffic.monthly_quota_gb,
                    ),
                    "remaining": max(
                        config.traffic.monthly_quota_gb * 1024 * 1024 * 1024
                        - month_total.total,
                        0,
                    ),
                },
                "users": serialize_month_users(month_users, config.quota),
            },
            "history": {
                "recent": history.recent_points("user", recent_start, now),
            },
            "alerts": history.list_alert_events(limit=10),
        }
    )
    return payload


@app.get("/api/health", response_class=JSONResponse)
def api_health(_: None = Depends(require_auth)):
    snapshot = read_stats(config.v2ray)
    return {
        "ok": snapshot.ok,
        "error": snapshot.error,
        "updated_at": snapshot.updated_at.isoformat(),
        "database_path": str(history.path),
        "access_log_path": config.logs.access_path,
    }


@app.post("/api/reports/daily/send", response_class=JSONResponse)
async def api_send_daily_report(_: None = Depends(require_auth)):
    now = datetime.now().astimezone()
    try:
        sent = await asyncio.to_thread(send_daily_report, now)
    except Exception as exc:
        logger.exception("Manual daily report send failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送日报失败: {exc}",
        ) from exc

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邮件配置不完整，未发送日报",
        )

    return {
        "ok": True,
        "message": "日报邮件已发送",
        "sent_at": now.isoformat(),
    }


@app.get("/api/logs/recent", response_class=JSONResponse)
def api_recent_logs(_: None = Depends(require_auth)):
    return read_access_log(config.logs.access_path, config.logs.max_lines)


def sum_pairs(items: dict[str, TrafficPair]) -> TrafficPair:
    total = TrafficPair()
    for traffic in items.values():
        total.uplink += traffic.uplink
        total.downlink += traffic.downlink
    return total


def serialize_pairs(items: dict[str, TrafficPair]) -> dict[str, dict[str, int]]:
    return {
        name: traffic.to_dict()
        for name, traffic in sorted(
            items.items(),
            key=lambda entry: entry[1].total,
            reverse=True,
        )
    }


def serialize_scope(
    scopes: dict[str, dict[str, TrafficPair]]
) -> dict[str, dict[str, dict[str, int]]]:
    return {
        scope: serialize_pairs(items)
        for scope, items in scopes.items()
    }


def serialize_month_users(
    month_users: dict[str, TrafficPair],
    quotas: dict[str, int],
) -> dict[str, dict]:
    return {
        name: {
            **traffic.to_dict(),
            "quota_gb": quotas.get(name),
            "usage_percent": usage_percent(traffic.total, quotas.get(name)),
            "remaining": (
                max(quotas[name] * 1024 * 1024 * 1024 - traffic.total, 0)
                if name in quotas
                else None
            ),
        }
        for name, traffic in sorted(
            month_users.items(),
            key=lambda entry: entry[1].total,
            reverse=True,
        )
    }
