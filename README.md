# Napak Wheels V2

Flask-based car marketplace app using SQLAlchemy and SQL Server.

## Tech Stack

- Python 3.12
- Flask
- Flask-SQLAlchemy / SQLAlchemy
- Microsoft SQL Server (via `pyodbc`)

## Prerequisites

- Python installed
- SQL Server running (your `SQLEXPRESS` instance)
- ODBC Driver 17 for SQL Server installed on Windows

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create `.env` in project root (or copy from `.env.example`) and set values:

```env
SECRET_KEY=replace-with-a-strong-random-secret
DATABASE_URL=mssql+pyodbc://bahawal:786great@127.0.0.1,60849/NapakWheels?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes
LOG_LEVEL=INFO
```

Notes:
- `DATABASE_URL` is required.
- `LOG_LEVEL` can be `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.

## Run

```bash
python main.py
```

App starts on:
- `http://127.0.0.1:5000`

## Logging

Console logs include:
- app startup and DB initialization
- every request start/end with method, path, status code, and response time

Example log line:

```text
2026-04-14 20:10:00,000 | INFO | app | Request completed: GET / -> 200 (24.10 ms)
```

## Database Notes

- The app is configured for SQL Server via `DATABASE_URL`.
- SQLite fallback was removed from config.
- Tables are created automatically at startup with `db.create_all()`.

## Common Issues

- **Connection timeout / server not accessible**
  - Verify SQL Server service is running.
  - Verify port in `DATABASE_URL` matches SQL Express dynamic TCP port.
  - Verify credentials (`UID`/`PWD`) and database name.
- **ODBC driver error**
  - Install or repair **ODBC Driver 17 for SQL Server**.

## Security

- Do not commit `.env`.
- Rotate `SECRET_KEY` and DB password before production use.
- Consider using a dedicated SQL login with minimum required privileges.

