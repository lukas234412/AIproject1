import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        c.post("/register", data={"login": "jan", "password": "tajnehaslo1"})
        yield c


def login(client, login="jan", password="tajnehaslo1"):
    return client.post(
        "/login", data={"login": login, "password": password}, follow_redirects=False
    )


def test_login_form_renders(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert 'action="/login"' in response.text


def test_login_with_correct_password(client):
    response = login(client)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    page = client.get("/")
    assert page.status_code == 200
    assert "jan" in page.text
    assert client.get("/api/items").status_code == 200


def test_login_is_case_insensitive_and_trimmed(client):
    assert login(client, login="  JAN ").status_code == 303
    assert client.get("/api/items").status_code == 200


def test_wrong_password_is_rejected(client):
    response = login(client, password="zlehaslo123")
    assert response.status_code == 401
    assert "Nieprawidłowy login lub hasło" in response.text
    assert 'value="jan"' in response.text
    assert client.get("/api/items").status_code == 401


def test_unknown_login_gives_same_error(client):
    response = login(client, login="nieistnieje")
    assert response.status_code == 401
    assert "Nieprawidłowy login lub hasło" in response.text


@pytest.mark.parametrize("data", [{}, {"login": "jan"}, {"password": "tajnehaslo1"}])
def test_missing_fields_are_rejected(client, data):
    response = client.post("/login", data=data, follow_redirects=False)
    assert response.status_code == 401
    assert client.get("/api/items").status_code == 401


def test_logged_in_user_on_login_page_is_redirected(client):
    login(client)
    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_logout_ends_session(client):
    login(client)
    response = client.post("/logout", follow_redirects=False)
    assert response.headers["location"] == "/login"
    assert client.get("/api/items").status_code == 401
    assert client.get("/", follow_redirects=False).status_code == 303


def test_session_cookie_is_httponly_and_has_no_password(client):
    response = login(client)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "tajnehaslo1" not in cookie


def test_tampered_session_cookie_is_ignored(client):
    login(client)
    client.cookies.set("session", "sfalszowane.ciasteczko")
    assert client.get("/api/items").status_code == 401
