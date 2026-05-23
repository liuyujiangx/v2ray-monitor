from __future__ import annotations

import secrets
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import ROOT_DIR, load_config
from app.services.history import HistoryStore
from app.services.v2ray import read_stats


config = load_config()
app = FastAPI(title="V2Ray Monitor")
security = HTTPBasic(auto_error=False)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

history = HistoryStore(str(ROOT_DIR / config.database.path))


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
    history.record_snapshot(snapshot)
    return snapshot.to_dict(quotas=config.quota)


@app.get("/api/health", response_class=JSONResponse)
def api_health(_: None = Depends(require_auth)):
    snapshot = read_stats(config.v2ray)
    return {
        "ok": snapshot.ok,
        "error": snapshot.error,
        "updated_at": snapshot.updated_at.isoformat(),
    }
