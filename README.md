# UMT-pythonweb-hw-11

REST API for storing and managing contacts, built with **FastAPI**, **SQLAlchemy**
and **PostgreSQL** — continued from hw-08 with **JWT authentication**, **email
verification**, **rate limiting**, **CORS** and **Cloudinary** avatar uploads.

Homework 11, "FullStack Web Development on Python".

## Features

- Registration and login with **JWT** access tokens
- Passwords stored only as **bcrypt** hashes
- **Email verification**: the signup email carries a confirmation link
  (without SMTP configured the link is written to the server log instead)
- Every contact belongs to its owner — users see **only their own contacts**
- Full CRUD for contacts, search, upcoming birthdays (from hw-08)
- `GET /api/users/me` is **rate limited** (10 requests/minute)
- **CORS** enabled, allowed origins configurable via `.env`
- Avatar upload to **Cloudinary** via `PATCH /api/users/avatar`
- All secrets live in `.env`; Docker Compose runs both the API and PostgreSQL

## Getting started

### Option A: everything in Docker

```bash
cp .env.example .env      # fill in SECRET_KEY at minimum
docker compose up --build
```

The API container applies migrations on start and serves at
**http://localhost:8000/docs**.

### Option B: PostgreSQL in Docker, API on the host

```bash
docker compose up -d postgres

uv venv .venv && source .venv/bin/activate   # or python -m venv .venv
pip install -r requirements.txt
cp .env.example .env                          # fill in SECRET_KEY

alembic upgrade head
uvicorn main:app --reload
```

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## Endpoints

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/signup` | Register — `201` with the user, `409` if the email is taken |
| `POST` | `/api/auth/login` | Form fields `username` (the email) + `password` — `200` with `access_token`, `401` on bad credentials or unconfirmed email |
| `GET` | `/api/auth/confirmed_email/{token}` | Landing for the link from the verification email |
| `POST` | `/api/auth/request_email` | Re-send the verification email |

### Users

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/users/me` | The authenticated user — limited to 10 requests/minute, `429` above that |
| `PATCH` | `/api/users/avatar` | Multipart upload; stores the image in Cloudinary and saves the URL |

### Contacts (JWT required, each user sees only their own)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/contacts` | Create a contact — `201`, or `409` if the email is already in this user's book |
| `GET` | `/api/contacts` | List contacts, with search and pagination |
| `GET` | `/api/contacts/{id}` | Get one contact — `404` if it does not exist or belongs to someone else |
| `PUT` | `/api/contacts/{id}` | Update a contact, partial payloads allowed |
| `DELETE` | `/api/contacts/{id}` | Delete a contact — `204` |
| `GET` | `/api/contacts/birthdays` | Contacts with a birthday in the next 7 days (`?days=` up to 365) |
| `GET` | `/api/healthchecker` | Verify the database connection |

Without a valid `Authorization: Bearer <token>` header every contacts route
answers `401`.

### Example session

```bash
# 1. Register
curl -X POST http://localhost:8000/api/auth/signup \
  -H 'Content-Type: application/json' \
  -d '{"username": "murad", "email": "murad@example.com", "password": "secret123"}'

# 2. Confirm the email: click the link from the inbox, or copy it from the
#    server log when SMTP is not configured.

# 3. Log in (form-encoded; `username` carries the email)
curl -X POST http://localhost:8000/api/auth/login \
  -d 'username=murad@example.com&password=secret123'

# 4. Use the token
TOKEN=eyJ...
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/contacts
```

## How the pieces work

**Authentication.** `POST /api/auth/signup` hashes the password with bcrypt and
stores the user; the response is `201` with the new user (never the password).
`POST /api/auth/login` verifies the hash and answers `401` for an unknown email
and a wrong password alike, so it does not leak which accounts exist.

**Authorization.** Login issues a JWT access token (`scope: access_token`,
lifetime from `ACCESS_TOKEN_EXPIRE_MINUTES`). The `get_current_user` dependency
decodes the Bearer token and loads the user; every contacts route depends on
it, and every repository query filters by `contact.user_id`, so one user can
never read or modify another user's contacts — a foreign contact id simply
looks like a `404`.

**Email verification.** The signup email contains a link with a second kind of
JWT (`scope: email_token`, valid 7 days). `GET /api/auth/confirmed_email/{token}`
marks the account confirmed; until then login answers `401 Email not confirmed`.
`POST /api/auth/request_email` re-sends the link. With `MAIL_SERVER` empty the
app logs the link instead of sending it, which keeps local testing easy.

**Rate limiting.** slowapi limits `GET /api/users/me` to 10 requests per minute
per client address; beyond that the server answers `429 Too Many Requests`.

**Avatars.** `PATCH /api/users/avatar` uploads the image to Cloudinary under a
per-user public id (so a new upload replaces the old one) and stores a 250×250
delivery URL on the user.

## Project layout

```
UMT-pythonweb-hw-11/
├── main.py                  # FastAPI application, CORS, rate-limit handler
├── src/
│   ├── conf/
│   │   └── config.py        # settings loaded from .env (pydantic-settings)
│   ├── database/
│   │   ├── db.py            # engine, session factory, request dependency
│   │   └── models.py        # User and Contact models
│   ├── repository/
│   │   ├── contacts.py      # contact queries, always filtered by owner
│   │   └── users.py         # user queries
│   ├── routes/
│   │   ├── auth.py          # signup, login, email verification
│   │   ├── contacts.py      # contact CRUD (JWT required)
│   │   └── users.py         # /me (rate limited), avatar upload
│   ├── services/
│   │   ├── auth.py          # bcrypt hashing, JWT issue/verify, CurrentUser
│   │   ├── email.py         # verification email (or logged link)
│   │   └── limiter.py       # shared slowapi limiter
│   └── schemas.py           # Pydantic schemas
├── migrations/              # Alembic (hw-08 schema + users/ownership)
├── Dockerfile               # runs migrations, then uvicorn
├── docker-compose.yaml      # api + postgres
├── requirements.txt
└── .env.example             # every configurable value, no secrets committed
```

Routes stay thin: they translate HTTP into repository calls, while every query
and `commit` lives in the repository layer and everything security-related
lives in `src/services/auth.py`.
