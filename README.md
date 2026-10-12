# StockWiz Folio Management

A FastAPI-based folio management system with PostgreSQL, SQLAlchemy, Alembic migrations, and Celery background tasks.

## Tech Stack

- **Backend:** FastAPI, Python
- **Database:** PostgreSQL, SQLAlchemy
- **Migrations:** Alembic
- **Background Tasks:** Celery, Redis
- **Testing:** Pytest

## Setup

### 1. Create Virtual Environment

```bash
python -m venv env
```

Activate on Windows:

```powershell
env\Scripts\Activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file and configure:

```env
DATABASE_URL=postgresql+psycopg://postgres:root@localhost:5432/folio_db
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

Update database credentials as needed.

### 4. Run Database Migrations

```bash
alembic upgrade head
```

### 5. Start FastAPI

```bash
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Swagger Docs: http://127.0.0.1:8000/docs

### 6. Start Celery Worker

Ensure Redis is running, then open another terminal:

```bash
celery -A app.workers.celery_app:celery_app worker -Q rebalance --pool=solo --loglevel=info
```

### 7. Run Tests

```bash
pytest
```

## Project Structure

```text
app/
├── api/          # API endpoints
├── core/         # Configuration and utilities
├── db/           # Database and migrations
├── models/       # SQLAlchemy models
├── schemas/      # Request and response schemas
├── services/     # Business logic
├── workers/      # Celery background tasks
├── utils/        # Helper functions
└── main.py       # FastAPI entry point

tests/             # Automated tests
```
## Authentication

### Create the first admin

```bash
python -m app.scripts.create_admin \
    --email admin@stockwiz.local \
    --password 'ChangeMe_StrongPass123' \
    --full-name 'Platform Admin'
```

अगर user पहले से मौजूद है: `--promote` flag जोड़ें।

### Login flow

- `POST /api/auth/login` — email + password. On success, sets:
  - `folio_access_token` — HttpOnly cookie (JWT)
  - `folio_csrf_token` — readable cookie for CSRF double-submit
- `GET /api/auth/me` — returns current user (role included).
- `POST /api/auth/logout` — clears both cookies. Requires `X-CSRF-Token` header.

### Role-based redirect

Frontend reads `user.role` from `/api/auth/login` response (or `/me`), and:
- `ADMIN` → `/admin-dashboard.html`
- `USER` → `/user-dashboard.html`
- anything else → error message

### CSRF

Every `POST/PUT/DELETE/PATCH` must send:

```
X-CSRF-Token: <value of folio_csrf_token cookie>
```

`GET/HEAD/OPTIONS` are exempt.

### Environment

Add to `.env`:

```env
SECRET_KEY=<output of: python -c "import secrets; print(secrets.token_urlsafe(64))">
ACCESS_TOKEN_EXPIRE_MINUTES=480
COOKIE_SECURE=false      # true when serving over HTTPS
```

### Tests

```bash
pytest tests/test_auth.py -v
pytest -q                # full suite
```