"""Leadbox — приём заявок с сайта: форма, API, админка, A/B-тест заголовка.

Запуск локально:  uvicorn app.main:app --reload
Переменные окружения: ADMIN_TOKEN (обязателен в проде), LEADBOX_DB, IP_SALT.
"""
import hashlib
import hmac
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import db
from .validators import validate_lead

ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "dev-token")
IP_SALT = os.environ.get("IP_SALT", "leadbox")
RATE_LIMIT_PER_HOUR = int(os.environ.get("RATE_LIMIT_PER_HOUR", "5"))
COOKIE = "lb_variant"
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Leadbox", version="1.0", lifespan=lifespan)


class LeadIn(BaseModel):
    name: str = ""
    contact: str = ""
    message: str = ""
    utm_source: str = ""
    utm_campaign: str = ""
    variant: str = "A"


def ip_hash(request: Request) -> str:
    raw = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "")
    return hashlib.sha256((IP_SALT + raw).encode()).hexdigest()[:32]


def require_admin(authorization: str | None) -> None:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Нужен токен: Authorization: Bearer <token>")
    token = authorization.split(" ", 1)[1].strip()
    if not hmac.compare_digest(token, ADMIN_TOKEN):
        raise HTTPException(status_code=403, detail="Токен не подходит")


@app.get("/api/health")
def health():
    return {"ok": True, "service": "leadbox"}


@app.get("/api/variant")
def variant(request: Request, response: Response):
    """Вариант заголовка для A/B: закрепляется кукой, чтобы не прыгал при перезагрузке."""
    current = request.cookies.get(COOKIE)
    if current in ("A", "B"):
        return {"variant": current, "fresh": False}
    chosen = "A" if secrets.randbelow(2) == 0 else "B"
    response.set_cookie(COOKIE, chosen, max_age=60 * 60 * 24 * 90, samesite="lax", httponly=False)
    db.add_view(chosen)
    return {"variant": chosen, "fresh": True}


@app.post("/api/leads", status_code=201)
def create_lead(payload: LeadIn, request: Request):
    clean, errors = validate_lead(payload.model_dump())
    if errors:
        return JSONResponse(status_code=422, content={"ok": False, "errors": errors})

    hashed = ip_hash(request)
    try:
        lead_id = db.create_lead(clean, hashed, RATE_LIMIT_PER_HOUR)
    except db.RateLimited:
        return JSONResponse(
            status_code=429,
            content={"ok": False, "errors": {"form": "Слишком много заявок с этого адреса. Попробуйте через час."}},
        )
    except db.DuplicateContact:
        return JSONResponse(
            status_code=409,
            content={"ok": False, "errors": {"contact": "Заявка с этим контактом уже есть за последние сутки."}},
        )
    return {"ok": True, "id": lead_id}


@app.get("/api/leads")
def leads(limit: int = 50, offset: int = 0, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    limit = max(1, min(limit, 200))
    return {"items": db.list_leads(limit, max(0, offset))}


@app.delete("/api/leads/{lead_id}", status_code=204)
def remove_lead(lead_id: int, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    if not db.delete_lead(lead_id):
        raise HTTPException(status_code=404, detail="Заявки с таким номером нет")
    return Response(status_code=204)


@app.get("/api/stats")
def get_stats(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    return db.stats()


@app.get("/api/public-stats")
def public_stats():
    """Агрегаты для витрины: без имён, контактов и ip. Персональные данные — только в админке."""
    data = db.stats()
    return {
        "views": sum(data["views"].values()),
        "leads": data["total_leads"],
        "best_conversion": max(data["conversion"].values()) if data["conversion"] else 0.0,
    }


@app.get("/api/config")
def public_config():
    """То, что можно отдавать фронтенду: лимит и подсказки, без служебных секретов."""
    return {"rate_limit_per_hour": RATE_LIMIT_PER_HOUR}


@app.get("/admin", include_in_schema=False)
def admin_page():
    """Админка по короткому адресу: /admin.html открывается и так, но ссылка должна быть опрятной."""
    return FileResponse(os.path.join(STATIC_DIR, "admin.html"))


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
