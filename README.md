# AIproject1 — lista zadań (FastAPI)

Lekka aplikacja do zarządzania listą zadań. Stack: Python 3.13, FastAPI, Jinja2, SQLite (wbudowane w Pythona).

## Uruchomienie w WSL (Ubuntu)

```bash
git clone https://github.com/lukas234412/AIproject1.git
cd AIproject1

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # wpisz losowy SESSION_SECRET (polecenie w pliku)
uvicorn app.main:app --reload --env-file .env
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
| GET    | `/register`                | Formularz rejestracji         |
| POST   | `/register`                | Zakłada konto (`login`, `password`) |
| GET    | `/login`                   | Formularz logowania           |
| POST   | `/login`                   | Logowanie (`login`, `password`) |
| POST   | `/logout`                  | Wylogowanie                   |

Każde konto ma własną, prywatną listę zadań (ten sam tekst zadania może istnieć na różnych kontach). Lista zadań i wszystkie operacje na niej wymagają zalogowania: strony HTML przekierowują na `/login`, a `/api/items` zwraca `401`.

## Rejestracja kont

- Login: 3–32 znaki (litery, cyfry, `_ . -`), unikalny bez względu na wielkość liter (`Jan` = `jan`).
- Hasło: 8–128 znaków, zapisywane jako hash scrypt z losową solą (nigdy jawnym tekstem).
- Odpowiedzi `POST /register`: `201` konto utworzone, `400` niepoprawne dane, `409` login zajęty.

## Logowanie i sesja

Po zalogowaniu sesja jest trzymana w podpisanym ciasteczku (`HttpOnly`, `SameSite=Lax`, ważne 7 dni).

| Zmienna              | Opis                                                                 |
|----------------------|----------------------------------------------------------------------|
| `SESSION_SECRET`     | Klucz podpisujący ciasteczko. Bez niego sesje wygasają po restarcie serwera. |
| `SESSION_HTTPS_ONLY` | `true` przy wdrożeniu za HTTPS                                       |

Wygenerowanie klucza: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
