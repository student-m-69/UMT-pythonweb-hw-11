# UMT-pythonweb-hw-08

REST API for storing and managing contacts, built with **FastAPI**, **SQLAlchemy**
and **PostgreSQL**, with request validation through **Pydantic** and interactive
Swagger documentation.

Homework 8, "FullStack Web Development on Python".

## Features

- Full CRUD for contacts
- Search by first name, last name or email through query parameters
- Contacts with a birthday in the next 7 days
- Swagger UI at `/docs` and ReDoc at `/redoc`
- Alembic migrations
- Pydantic validation of every field, including the birthday as a real date

## Contact fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `first_name` | string, 1–50 | yes | trimmed, must not be blank |
| `last_name` | string, 1–50 | yes | trimmed, must not be blank |
| `email` | email | yes | unique, validated by `EmailStr` |
| `phone` | string, ≤30 | yes | digits with `+`, spaces, dashes, parentheses |
| `birthday` | date | yes | must be a real date, in the past, after 1900 |
| `additional_data` | string, ≤500 | no | free-form notes |
| `id`, `created_at`, `updated_at` | — | — | set by the server |

## Getting started

### 1. Start PostgreSQL

```bash
docker compose up -d
```

or manually:

```bash
docker run --name hw08-postgres -p 5432:5432 \
  -e POSTGRES_PASSWORD=hw08secret -e POSTGRES_DB=contacts_app -d postgres:16
```

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # adjust DATABASE_URL if needed
```

### 3. Apply migrations

```bash
alembic upgrade head
```

### 4. Run the API

```bash
uvicorn main:app --reload
```

Open **http://localhost:8000/docs** for the Swagger UI.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/contacts` | Create a contact — `201`, or `409` if the email is taken |
| `GET` | `/api/contacts` | List contacts, with search and pagination |
| `GET` | `/api/contacts/{id}` | Get one contact — `404` if it does not exist |
| `PUT` | `/api/contacts/{id}` | Update a contact, partial payloads allowed |
| `DELETE` | `/api/contacts/{id}` | Delete a contact — `204` |
| `GET` | `/api/contacts/birthdays` | Contacts with a birthday in the next 7 days |
| `GET` | `/api/healthchecker` | Verify the database connection |

### Search

`GET /api/contacts` accepts these query parameters. All matching is partial and
case-insensitive; the named filters combine with AND.

| Parameter | Description |
|-----------|-------------|
| `first_name` | match part of the first name |
| `last_name` | match part of the last name |
| `email` | match part of the email |
| `search` | match any of the three fields above |
| `skip`, `limit` | pagination, default `0` and `100` |

```bash
curl 'http://localhost:8000/api/contacts?last_name=petr'
curl 'http://localhost:8000/api/contacts?search=example.com'
```

### Upcoming birthdays

```bash
curl 'http://localhost:8000/api/contacts/birthdays'
curl 'http://localhost:8000/api/contacts/birthdays?days=30'
```

Returns everyone whose birthday falls in the window starting today, sorted by
how soon it is. Matching uses the month and day rather than the stored year, so
a window running from late December into January works without a special case.
A 29 February birthday is shown on 28 February in non-leap years.

### Example

```bash
curl -X POST http://localhost:8000/api/contacts \
  -H 'Content-Type: application/json' \
  -d '{
        "first_name": "Ivan",
        "last_name": "Petrenko",
        "email": "ivan.petrenko@example.com",
        "phone": "+380441234567",
        "birthday": "1990-05-17",
        "additional_data": "Met at PyCon"
      }'
```

## Project layout

```
UMT-pythonweb-hw-08/
├── main.py                  # FastAPI application
├── src/
│   ├── database/
│   │   ├── db.py            # engine, session factory, request dependency
│   │   └── models.py        # SQLAlchemy Contact model
│   ├── repository/
│   │   └── contacts.py      # all database queries
│   ├── routes/
│   │   └── contacts.py      # HTTP layer
│   └── schemas.py           # Pydantic schemas
├── migrations/              # Alembic
├── alembic.ini
├── requirements.txt
├── docker-compose.yaml
└── .env.example
```

Routes stay thin: they translate HTTP into repository calls and turn missing
rows into `404`s, while every query and `commit` lives in the repository layer.
