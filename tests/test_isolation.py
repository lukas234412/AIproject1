import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.accounts import hash_password
from app.db import init_db


@pytest.fixture
def app_and_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    from app.main import app

    return app, db_path


def logged_in(app, login, password="haslo12345"):
    c = TestClient(app)
    c.__enter__()
    c.post("/register", data={"login": login, "password": password})
    assert c.post("/login", data={"login": login, "password": password},
                  follow_redirects=False).status_code == 303
    return c


@pytest.fixture
def two_users(app_and_db):
    app, _ = app_and_db
    lukas, drugi = logged_in(app, "lukas"), logged_in(app, "drugi")
    yield lukas, drugi
    lukas.__exit__(None, None, None)
    drugi.__exit__(None, None, None)


def texts(client):
    return [i["text"] for i in client.get("/api/items").json()]


def test_users_see_only_their_own_items(two_users):
    lukas, drugi = two_users
    lukas.post("/items", data={"text": "Zadanie Lukasa"})
    drugi.post("/items", data={"text": "Zadanie drugiego"})

    assert texts(lukas) == ["Zadanie Lukasa"]
    assert texts(drugi) == ["Zadanie drugiego"]
    assert "Zadanie Lukasa" not in drugi.get("/").text


def test_new_user_starts_with_empty_list(two_users):
    lukas, drugi = two_users
    lukas.post("/items", data={"text": "Prywatne"})
    assert texts(drugi) == []
    assert "Brak zadań" in drugi.get("/").text


def test_same_text_allowed_for_different_users(two_users):
    lukas, drugi = two_users
    lukas.post("/items", data={"text": "Kupić mleko"})
    response = drugi.post("/items", data={"text": "Kupić mleko"}, follow_redirects=True)
    assert "już istnieje" not in response.text
    assert texts(drugi) == ["Kupić mleko"]


def test_duplicate_still_rejected_within_one_list(two_users):
    lukas, _ = two_users
    lukas.post("/items", data={"text": "Jajka"})
    response = lukas.post("/items", data={"text": "Jajka"}, follow_redirects=True)
    assert "już istnieje" in response.text
    assert texts(lukas) == ["Jajka"]


def test_cannot_toggle_or_delete_someone_elses_item(two_users):
    lukas, drugi = two_users
    lukas.post("/items", data={"text": "Nie ruszać"})
    item_id = lukas.get("/api/items").json()[0]["id"]

    assert drugi.post(f"/items/{item_id}/toggle").status_code == 404
    assert drugi.post(f"/items/{item_id}/delete").status_code == 404
    assert lukas.get("/api/items").json() == [{"id": item_id, "text": "Nie ruszać", "done": False}]


def test_migration_assigns_old_items_to_oldest_account(app_and_db):
    _, db_path = app_and_db
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            text TEXT NOT NULL UNIQUE, done INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT,
                            login TEXT NOT NULL UNIQUE COLLATE NOCASE,
                            password_hash TEXT NOT NULL,
                            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        INSERT INTO items (id, text, done) VALUES (3, 'stare', 1);
        """
    )
    conn.execute("INSERT INTO users (id, login, password_hash) VALUES (2, 'pierwszy', ?)",
                 (hash_password("x" * 8),))
    conn.execute("INSERT INTO users (id, login, password_hash) VALUES (4, 'drugi', ?)",
                 (hash_password("x" * 8),))
    conn.commit()
    conn.close()

    init_db()
    init_db()  # migracja jest idempotentna

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT id, user_id, text, done FROM items").fetchall() == [(3, 2, "stare", 1)]
    conn.close()


def test_migration_without_users_keeps_items_hidden(app_and_db):
    _, db_path = app_and_db
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                 " text TEXT NOT NULL UNIQUE, done INTEGER NOT NULL DEFAULT 0)")
    conn.execute("INSERT INTO items (text) VALUES ('sierota')")
    conn.commit()
    conn.close()

    init_db()

    conn = sqlite3.connect(db_path)
    assert conn.execute("SELECT user_id, text FROM items").fetchall() == [(None, "sierota")]
    conn.close()
