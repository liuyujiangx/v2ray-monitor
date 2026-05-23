from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.message import EmailMessage

from app.config import AppConfig, EmailAlertsConfig

logger = logging.getLogger(__name__)


def notify_new_alert(config: AppConfig, alert: dict, created_at: datetime) -> None:
    alerts = config.alerts
    if not alerts.enabled:
        return

    provider = alerts.provider.strip().lower()
    if provider == "none":
        return
    if provider == "email":
        try:
            send_email_alert(alerts.email, alert, created_at)
        except Exception:
            logger.exception("Failed to send email alert for %s", alert.get("alert_key"))
        return
    if provider in {"bark", "telegram"}:
        logger.warning(
            "Alert provider %r is not implemented yet; alert stored only in database",
            provider,
        )
        return

    logger.warning("Unknown alert provider %r; skipping external notification", provider)


def send_email_alert(
    email_cfg: EmailAlertsConfig,
    alert: dict,
    created_at: datetime,
) -> None:
    if not _email_config_ready(email_cfg):
        logger.warning(
            "Email alerts enabled but SMTP is incomplete "
            "(need smtp_host, from_addr, and at least one to_addrs); skipping send"
        )
        return

    message = _build_email_message(email_cfg, alert, created_at)
    _deliver_smtp(email_cfg, message)


def _email_config_ready(email_cfg: EmailAlertsConfig) -> bool:
    return bool(
        email_cfg.smtp_host.strip()
        and email_cfg.from_addr.strip()
        and any(addr.strip() for addr in email_cfg.to_addrs)
    )


def _build_email_message(
    email_cfg: EmailAlertsConfig,
    alert: dict,
    created_at: datetime,
) -> EmailMessage:
    scope = alert["scope"]
    name = alert["name"]
    threshold = alert["threshold"]
    usage_percent = alert["usage_percent"]
    used_gb = alert["used_bytes"] / (1024**3)
    quota_gb = alert["quota_bytes"] / (1024**3)
    time_text = created_at.isoformat(timespec="seconds")

    scope_label = "总量" if scope == "total" else f"用户 ({scope})"
    subject = f"[V2Ray Monitor] 流量告警 {name} ≥ {threshold}%"
    body = (
        f"V2Ray Monitor 流量告警\n\n"
        f"范围: {scope_label}\n"
        f"名称: {name}\n"
        f"阈值: {threshold}%\n"
        f"当前使用率: {usage_percent}%\n"
        f"本月已用: {used_gb:.2f} GB / {quota_gb:.2f} GB\n"
        f"时间: {time_text}\n\n"
        f"---\n"
        f"Scope: {scope}\n"
        f"Name: {name}\n"
        f"Threshold: {threshold}%\n"
        f"Usage: {usage_percent}% ({used_gb:.2f} GB of {quota_gb:.2f} GB)\n"
        f"Time: {time_text}\n"
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = email_cfg.from_addr
    message["To"] = ", ".join(addr.strip() for addr in email_cfg.to_addrs if addr.strip())
    message.set_content(body)
    return message


def _deliver_smtp(email_cfg: EmailAlertsConfig, message: EmailMessage) -> None:
    recipients = [addr.strip() for addr in email_cfg.to_addrs if addr.strip()]
    if email_cfg.use_ssl:
        with smtplib.SMTP_SSL(email_cfg.smtp_host, email_cfg.smtp_port) as smtp:
            _login_if_needed(smtp, email_cfg)
            smtp.send_message(message, to_addrs=recipients)
        return

    with smtplib.SMTP(email_cfg.smtp_host, email_cfg.smtp_port) as smtp:
        if email_cfg.use_tls:
            smtp.starttls()
        _login_if_needed(smtp, email_cfg)
        smtp.send_message(message, to_addrs=recipients)


def _login_if_needed(smtp: smtplib.SMTP, email_cfg: EmailAlertsConfig) -> None:
    if email_cfg.username and email_cfg.password:
        smtp.login(email_cfg.username, email_cfg.password)
