import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import connect, init_db

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Todo list", lifespan=lifespan)


def fetch_items() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT id, text, done FROM items ORDER BY id").fetchall()
    return [{"id": r["id"], "text": r["text"], "done": bool(r["done"])} for r in rows]


@app.get("/", response_class=HTMLResponse)
def index(request: Request, error: str | None = None):
    return templates.TemplateResponse(
        request,
        "index.html",
        {"items": fetch_items(), "error": error},
    )


@app.post("/items")
def add_item(text: str = Form("")):
    text = text.strip()
    if not text:
        return RedirectResponse("/?error=Pusty+element+nie+może+być+dodany", status_code=303)
    try:
        with connect() as conn:
            conn.execute("INSERT INTO items (text) VALUES (?)", (text,))
    except sqlite3.IntegrityError:
        return RedirectResponse("/?error=Ten+element+już+istnieje", status_code=303)
    return RedirectResponse("/", status_code=303)


@app.post("/items/{item_id}/toggle")
def toggle_item(item_id: int):
    with connect() as conn:
        cur = conn.execute(
            "UPDATE items SET done = CASE WHEN done = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (item_id,),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Nie znaleziono elementu")
    return RedirectResponse("/", status_code=303)


@app.post("/items/{item_id}/delete")
def delete_item(item_id: int):
    with connect() as conn:
        cur = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Nie znaleziono elementu")
    return RedirectResponse("/", status_code=303)


@app.get("/api/items")
def api_items():
    return fetch_items()
