import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def anon_client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(anon_client):
    anon_client.post("/register", data={"login": "tester", "password": "haslo12345"})
    response = anon_client.post(
        "/login", data={"login": "tester", "password": "haslo12345"}, follow_redirects=False
    )
    assert response.status_code == 303
    return anon_client


def test_home_page_renders_empty_state(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Brak zadań" in response.text


def test_add_item_appears_in_list(client):
    response = client.post("/items", data={"text": "Kupić mleko"}, follow_redirects=True)
    assert response.status_code == 200
    assert "Kupić mleko" in response.text


def test_add_item_strips_whitespace(client):
    client.post("/items", data={"text": "   Zadanie   "})
    items = client.get("/api/items").json()
    assert [i["text"] for i in items] == ["Zadanie"]


def test_empty_item_is_rejected(client):
    response = client.post("/items", data={"text": "   "}, follow_redirects=True)
    assert "Pusty element" in response.text
    assert client.get("/api/items").json() == []


def test_duplicate_item_is_rejected(client):
    client.post("/items", data={"text": "Jajka"})
    response = client.post("/items", data={"text": "Jajka"}, follow_redirects=True)
    assert "już istnieje" in response.text
    assert len(client.get("/api/items").json()) == 1


def test_toggle_marks_item_done_and_back(client):
    client.post("/items", data={"text": "Sprzątanie"})
    item_id = client.get("/api/items").json()[0]["id"]

    client.post(f"/items/{item_id}/toggle")
    assert client.get("/api/items").json()[0]["done"] is True

    client.post(f"/items/{item_id}/toggle")
    assert client.get("/api/items").json()[0]["done"] is False


def test_delete_removes_item(client):
    client.post("/items", data={"text": "Do usunięcia"})
    item_id = client.get("/api/items").json()[0]["id"]

    client.post(f"/items/{item_id}/delete")
    assert client.get("/api/items").json() == []


def test_toggle_and_delete_unknown_item_return_404(client):
    assert client.post("/items/999/toggle").status_code == 404
    assert client.post("/items/999/delete").status_code == 404


# --- dostęp tylko po zalogowaniu ---


def test_anonymous_home_redirects_to_login(anon_client):
    response = anon_client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_anonymous_api_returns_401(anon_client):
    assert anon_client.get("/api/items").status_code == 401


@pytest.mark.parametrize("path", ["/items", "/items/1/toggle", "/items/1/delete"])
def test_anonymous_cannot_modify_items(anon_client, path):
    response = anon_client.post(path, data={"text": "Hack"}, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_logged_in_user_sees_name_and_logout(client):
    response = client.get("/")
    assert "tester" in response.text
    assert 'action="/logout"' in response.text
