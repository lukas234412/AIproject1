import logging
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.accounts import LoginRequired, require_user_api, require_user_page
from app.accounts import router as accounts_router
from app.db import connect, init_db

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def session_secret() -> str:
    secret = os.environ.get("SESSION_SECRET")
    if not secret:
        logger.warning("Brak SESSION_SECRET: sesje wygasną po restarcie serwera")
        secret = secrets.token_urlsafe(32)
    return secret


app = FastAPI(title="Todo list", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    same_site="lax",
    https_only=os.environ.get("SESSION_HTTPS_ONLY", "").lower() in ("1", "true"),
    max_age=7 * 24 * 3600,
)
app.include_router(accounts_router)


@app.exception_handler(LoginRequired)
def login_required_handler(request: Request, exc: LoginRequired):
    return RedirectResponse("/login", status_code=303)


def fetch_items(user_id: int) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, text, done FROM items WHERE user_id = ? ORDER BY id", (user_id,)
        ).fetchall()
    return [{"id": r["id"], "text": r["text"], "done": bool(r["done"])} for r in rows]


@app.get("/", response_class=HTMLResponse)
def index(request: Request, error: str | None = None, user: dict = Depends(require_user_page)):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"items": fetch_items(user["id"]), "error": error, "user": user},
    )


@app.post("/items")
def add_item(text: str = Form(""), user: dict = Depends(require_user_page)):
    text = text.strip()
    if not text:
        return RedirectResponse("/?error=Pusty+element+nie+może+być+dodany", status_code=303)
    try:
        with connect() as conn:
            conn.execute(
                "INSERT INTO items (user_id, text) VALUES (?, ?)", (user["id"], text)
            )
    except sqlite3.IntegrityError:
        return RedirectResponse("/?error=Ten+element+już+istnieje", status_code=303)
    return RedirectResponse("/", status_code=303)


@app.post("/items/{item_id}/toggle")
def toggle_item(item_id: int, user: dict = Depends(require_user_page)):
    with connect() as conn:
        cur = conn.execute(
            "UPDATE items SET done = CASE WHEN done = 1 THEN 0 ELSE 1 END"
            " WHERE id = ? AND user_id = ?",
            (item_id, user["id"]),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Nie znaleziono elementu")
    return RedirectResponse("/", status_code=303)


@app.post("/items/{item_id}/delete")
def delete_item(item_id: int, user: dict = Depends(require_user_page)):
    with connect() as conn:
        cur = conn.execute(
            "DELETE FROM items WHERE id = ? AND user_id = ?", (item_id, user["id"])
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Nie znaleziono elementu")
    return RedirectResponse("/", status_code=303)


@app.get("/api/items")
def api_items(user: dict = Depends(require_user_api)):
    return fetch_items(user["id"])
