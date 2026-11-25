import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.accounts import hash_password, verify_password


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    from app.main import app

    with TestClient(app) as c:
        c.db_path = db_path
        yield c


def users(client):
    conn = sqlite3.connect(client.db_path)
    try:
        return conn.execute("SELECT login, password_hash FROM users ORDER BY id").fetchall()
    finally:
        conn.close()


def register(client, login="jan", password="tajnehaslo1"):
    return client.post("/register", data={"login": login, "password": password})


def test_register_form_renders(client):
    response = client.get("/register")
    assert response.status_code == 200
    assert 'name="login"' in response.text
    assert 'name="password"' in response.text


def test_login_page_links_to_register(client):
    assert 'href="/register"' in client.get("/login").text


def test_register_success_links_to_login(client):
    assert 'href="/login"' in register(client).text


def test_register_new_account(client):
    response = register(client)
    assert response.status_code == 201
    assert "zostało utworzone" in response.text
    assert [u[0] for u in users(client)] == ["jan"]


def test_duplicate_login_is_rejected(client):
    register(client, password="pierwszehaslo")
    response = register(client, password="innehaslo123")
    assert response.status_code == 409
    assert "już zajęty" in response.text
    rows = users(client)
    assert len(rows) == 1
    assert verify_password("pierwszehaslo", rows[0][1])


def test_duplicate_login_is_case_insensitive(client):
    register(client, login="Jan")
    response = register(client, login="jAN")
    assert response.status_code == 409
    assert len(users(client)) == 1


def test_login_is_trimmed_before_duplicate_check(client):
    register(client, login="jan")
    assert register(client, login="  jan  ").status_code == 409


def test_different_logins_create_separate_accounts(client):
    assert register(client, login="jan").status_code == 201
    assert register(client, login="anna").status_code == 201
    assert [u[0] for u in users(client)] == ["jan", "anna"]


@pytest.mark.parametrize("login", ["", "ab", "a" * 33, "jan kowalski", "jan<script>", "żółw"])
def test_invalid_login_is_rejected(client, login):
    response = register(client, login=login)
    assert response.status_code == 400
    assert users(client) == []


@pytest.mark.parametrize("password", ["", "krotkie", "x" * 129])
def test_invalid_password_is_rejected(client, password):
    response = register(client, password=password)
    assert response.status_code == 400
    assert users(client) == []


def test_login_is_kept_in_form_after_error(client):
    response = register(client, login="jan", password="123")
    assert 'value="jan"' in response.text


def test_password_is_not_stored_in_plain_text(client):
    register(client, password="tajnehaslo1")
    stored = users(client)[0][1]
    assert "tajnehaslo1" not in stored
    assert stored.startswith("scrypt$")


def test_hash_uses_random_salt():
    assert hash_password("takie-same") != hash_password("takie-same")


def test_verify_password():
    stored = hash_password("poprawne-haslo")
    assert verify_password("poprawne-haslo", stored)
    assert not verify_password("zle-haslo", stored)
    assert not verify_password("poprawne-haslo", "uszkodzony")
