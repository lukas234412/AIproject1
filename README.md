# AIproject1 — lista zadań (FastAPI)

Lekka aplikacja do zarządzania listą zadań. Stack: Python 3.13, FastAPI, Jinja2, SQLite (wbudowane w Pythona).

## Uruchomienie w WSL (Ubuntu)

```bash
git clone https://github.com/lukas234412/AIproject1.git
cd AIproject1

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Aplikacja będzie dostępna pod adresem http://127.0.0.1:8000 (w przeglądarce na Windows też).
Dane są zapisywane w pliku `data.db` w katalogu projektu. Można zmienić ścieżkę zmienną `DATABASE_PATH`.

Dokumentacja API (Swagger): http://127.0.0.1:8000/docs

## Testy

```bash
pytest
```

## Endpointy

| Metoda | Ścieżka                    | Opis                          |
|--------|----------------------------|-------------------------------|
| GET    | `/`                        | Strona z listą zadań          |
| POST   | `/items`                   | Dodaje zadanie (pole `text`)  |
| POST   | `/items/{id}/toggle`       | Przełącza status wykonania    |
| POST   | `/items/{id}/delete`       | Usuwa zadanie                 |
| GET    | `/api/items`               | Lista zadań w formacie JSON   |
