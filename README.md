## Setup & Run

### 1. Install dependencies

Install the project dependencies in your virtual environment using the existing `requirements.txt`:

```powershell
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and update the PostgreSQL database credentials and Redis configuration.

```powershell
Copy-Item .env.example .env
```

Ensure PostgreSQL and Redis are running before starting the application.

### 3. Start the FastAPI application

Run the following command from the project root:

```powershell
uvicorn app.main:app --reload
```

Application URLs:

- Frontend: http://127.0.0.1:8000/
- Swagger API documentation: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

### 4. Start the Celery worker

Open a separate terminal in the project root and run:

```powershell
celery -A app.workers.celery_app:celery_app worker -Q rebalance --pool=solo --loglevel=info
```

The Celery worker processes asynchronous stock-rebalancing tasks from the `rebalance` queue. Keep the worker running while testing the rebalance workflow.

## Database Migrations

Apply the existing Alembic migrations:

```powershell
alembic upgrade head
```

Generate a migration after modifying database models:

```powershell
alembic revision --autogenerate -m "describe your schema change"
```

Review the generated migration before applying it.

## Running Tests

Run the complete test suite:

```powershell
pytest -q
```

Run an individual test module:

```powershell
pytest tests/test_subscriptions.py -v
```

The test suite covers broker receipts, subscription creation, order quantities, subscription exits, stock replacement, and asynchronous rebalance behavior.

## Async Rebalancing Requirements

- PostgreSQL must be available and correctly configured in `.env`.
- Redis must be running and accessible through the configured Celery broker URL.
- The FastAPI application and Celery worker must run in separate terminals.
- The worker must listen to the `rebalance` queue.
