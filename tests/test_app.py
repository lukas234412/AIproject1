import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    from app.main import app

    with TestClient(app) as c:
        yield c


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
