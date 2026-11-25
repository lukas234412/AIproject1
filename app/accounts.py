"""Konta użytkowników: rejestracja, logowanie i wylogowanie (login + hasło)."""

import hashlib
import hmac
import re
import secrets
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.db import connect

LOGIN_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128

# Parametry scrypt (ok. 16 MB pamięci na hash)
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
router = APIRouter()


class UserExists(Exception):
    """Konto o podanym loginie już istnieje."""


class LoginRequired(Exception):
    """Strona HTML wymaga zalogowanego użytkownika."""


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p)
    )
    return hmac.compare_digest(digest.hex(), digest_hex)


_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def validate(login: str, password: str) -> str | None:
    """Zwraca komunikat błędu albo None, gdy dane są poprawne."""
    if not LOGIN_RE.fullmatch(login):
        return "Login musi mieć 3–32 znaki: litery, cyfry, _ . -"
    if len(password) < MIN_PASSWORD_LEN:
        return f"Hasło musi mieć co najmniej {MIN_PASSWORD_LEN} znaków"
    if len(password) > MAX_PASSWORD_LEN:
        return f"Hasło może mieć najwyżej {MAX_PASSWORD_LEN} znaków"
    return None


def create_user(login: str, password: str) -> int:
    """Tworzy konto. Rzuca UserExists, gdy login jest zajęty (bez względu na wielkość liter)."""
    password_hash = hash_password(password)
    try:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (login, password_hash) VALUES (?, ?)",
                (login, password_hash),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError:
        raise UserExists(login) from None


def authenticate(login: str, password: str) -> dict | None:
    """Zwraca użytkownika przy poprawnym loginie i haśle, w przeciwnym razie None."""
    with connect() as conn:
        row = conn.execute(
            "SELECT id, login, password_hash FROM users WHERE login = ?", (login,)
        ).fetchone()
    if row is None:
        # Liczymy hash także dla nieistniejącego loginu, żeby czas odpowiedzi
        # nie zdradzał, które loginy są zarejestrowane.
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return {"id": row["id"], "login": row["login"]}


def current_user(request: Request) -> dict | None:
    return request.session.get("user")


def require_user_page(request: Request) -> dict:
    """Zależność dla stron HTML: przekierowuje na /login, gdy brak sesji."""
    user = current_user(request)
    if user is None:
        raise LoginRequired()
    return user


def require_user_api(request: Request) -> dict:
    """Zależność dla API: zwraca 401, gdy brak sesji."""
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Wymagane logowanie")
    return user


def render(request: Request, template: str = "register.html", status_code: int = 200, **context):
    return templates.TemplateResponse(
        request, template, {"error": None, "created": None, "login": "", **context},
        status_code=status_code,
    )


@router.get("/register")
def register_form(request: Request):
    return render(request)


@router.post("/register")
def register(request: Request, login: str = Form(""), password: str = Form("")):
    login = login.strip()
    error = validate(login, password)
    if error:
        return render(request, status_code=400, error=error, login=login)
    try:
        create_user(login, password)
    except UserExists:
        return render(
            request, status_code=409, error="Ten login jest już zajęty", login=login
        )
    return render(request, status_code=201, created=login)


@router.get("/login")
def login_form(request: Request):
    if current_user(request):
        return RedirectResponse("/", status_code=303)
    return render(request, "login.html")


@router.post("/login")
def login(request: Request, login: str = Form(""), password: str = Form("")):
    login = login.strip()
    user = authenticate(login, password) if login and password else None
    if user is None:
        return render(
            request, "login.html", status_code=401,
            error="Nieprawidłowy login lub hasło", login=login,
        )
    request.session.clear()  # nowa sesja po zalogowaniu (ochrona przed session fixation)
    request.session["user"] = user
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
