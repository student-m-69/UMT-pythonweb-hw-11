# UMT-pythonweb-hw-11

REST API for storing and managing contacts, built with **FastAPI**, **SQLAlchemy**,
**PostgreSQL** and **Redis**. Started as homework 8, extended with JWT
authentication in homework 11, and finished as the **final project (homework 13)**
with tests, Sphinx documentation, Redis caching, password reset and user roles —
all in this repository, one homework per pull request.

## Features

- Registration and login with a **JWT token pair** — short-lived `access_token`
  plus rotating `refresh_token`
- Passwords stored only as **bcrypt** hashes
- **Email verification**: the signup email carries a confirmation link
  (without SMTP configured the link is written to the server log instead)
- **Password reset** over email with a dedicated single-purpose token
- **Roles**: every account is a `user`; only **admins** may change their avatar
- **Redis caching** of the authenticated user — `get_current_user` serves most
  requests without touching PostgreSQL, and every account change evicts the entry
- Every contact belongs to its owner — users see **only their own contacts**
- Full CRUD for contacts, search, upcoming birthdays
- `GET /api/users/me` is **rate limited** (10 requests/minute)
- **CORS** enabled, allowed origins configurable via `.env`
- Avatar upload to **Cloudinary** via `PATCH /api/users/avatar` (admins only)
- **55 unit and integration tests, 94% coverage** (`pytest`, `pytest-cov`)
- **Sphinx documentation** generated from the docstrings
- All secrets live in `.env`; Docker Compose runs the API, PostgreSQL and Redis

## Getting started

### Option A: everything in Docker

```bash
cp .env.example .env      # fill in SECRET_KEY at minimum
docker compose up --build
```

The API container applies migrations on start and serves at
**http://localhost:8000/docs**.

### Option B: databases in Docker, API on the host

```bash
docker compose up -d postgres redis

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

## Tests and coverage

```bash
pip install -r requirements-dev.txt
pytest --cov=src --cov=main --cov-report=term-missing
```

The suite needs no running services: it uses an in-memory SQLite database and
`fakeredis`, and pins its own environment, so it passes with or without a local
`.env`. Current state: **55 passed, 94% total coverage** (the requirement is 75%).

Unit tests cover the repository layer (`tests/test_unit_repository_*.py`);
integration tests drive the HTTP routes through `TestClient`
(`tests/test_integration_*.py`), including the auth flows, contact ownership,
the rate limit, the Redis cache behaviour and the role checks.

## Documentation

```bash
pip install -r requirements-dev.txt
sphinx-build -b html docs docs/_build/html
```

Open `docs/_build/html/index.html`. Every public function and method carries a
Google-style docstring that Sphinx (autodoc + napoleon) renders.

## Endpoints

### Auth

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/auth/signup` | Register — `201` with the user, `409` if the email is taken |
| `POST` | `/api/auth/login` | Form fields `username` (the email) + `password` — `200` with the token pair, `401` on bad credentials or unconfirmed email |
| `POST` | `/api/auth/refresh_token` | `Authorization: Bearer <refresh_token>` — `200` with a new pair; the old refresh token stops working |
| `GET` | `/api/auth/confirmed_email/{token}` | Landing for the link from the verification email |
| `POST` | `/api/auth/request_email` | Re-send the verification email |
| `POST` | `/api/auth/forgot_password` | Email a password-reset link |
| `POST` | `/api/auth/reset_password/{token}` | Set the new password; signs every session out |

### Users

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/users/me` | The authenticated user — limited to 10 requests/minute, `429` above that |
| `PATCH` | `/api/users/avatar` | Multipart upload to Cloudinary — **admins only**, `403` for a regular user |

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

# 4. Use the access token
TOKEN=eyJ...
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/contacts

# 5. When it expires, trade the refresh token for a new pair
curl -X POST http://localhost:8000/api/auth/refresh_token \
  -H "Authorization: Bearer $REFRESH_TOKEN"
```

## How the pieces work

**Authentication.** `POST /api/auth/signup` hashes the password with bcrypt and
stores the user; the response is `201` with the new user (never the password).
`POST /api/auth/login` verifies the hash and answers `401` for an unknown email
and a wrong password alike, so it does not leak which accounts exist.

**Authorization.** Login issues an access/refresh JWT pair, told apart by the
`scope` claim. The `get_current_user` dependency decodes the Bearer token and
loads the user; every contacts route depends on it, and every repository query
filters by `contact.user_id`, so one user can never reach another user's
contacts. The refresh token is stored on the user row and **rotates**: each
refresh invalidates the previous token, and a mismatch revokes the session.

**Redis cache.** `get_current_user` checks Redis first and only falls back to
PostgreSQL on a miss, caching the result for `USER_CACHE_TTL_SECONDS`
(15 minutes by default). Only plain JSON with the profile fields is cached —
never the password hash or the refresh token — and every mutation of the
account (confirmation, avatar, password) evicts the entry, so the cache stays
both safe and current. If Redis is down the app just runs against the database.

**Email verification.** The signup email contains a link with an
`email_token`-scoped JWT (valid 7 days). `GET /api/auth/confirmed_email/{token}`
marks the account confirmed; until then login answers `401 Email not confirmed`.

**Password reset.** `POST /api/auth/forgot_password` emails a link with a
`password_reset`-scoped token — a verification token cannot reset a password
and vice versa. `POST /api/auth/reset_password/{token}` stores the new bcrypt
hash, evicts the cached user and revokes the refresh token, signing out every
existing session. The response never reveals whether an email is registered.

**Roles.** Accounts have a `role` — `user` by default, `admin` granted by hand
(e.g. `UPDATE users SET role = 'admin' WHERE email = ...`). The reusable
`RoleAccess` dependency guards admin-only routes; changing one's avatar is the
admin-only operation, a regular user gets `403`.

**Rate limiting.** slowapi limits `GET /api/users/me` to 10 requests per minute
per client address; beyond that the server answers `429 Too Many Requests`.

## Project layout

```
UMT-pythonweb-hw-11/
├── main.py                  # FastAPI application, CORS, rate-limit handler
├── src/
│   ├── conf/
│   │   └── config.py        # settings loaded from .env (pydantic-settings)
│   ├── database/
│   │   ├── db.py            # engine, session factory, request dependency
│   │   └── models.py        # User (with Role) and Contact models
│   ├── repository/
│   │   ├── contacts.py      # contact queries, always filtered by owner
│   │   └── users.py         # user queries, cache eviction on mutation
│   ├── routes/
│   │   ├── auth.py          # signup, login, refresh, verification, reset
│   │   ├── contacts.py      # contact CRUD (JWT required)
│   │   └── users.py         # /me (rate limited), avatar (admins only)
│   ├── services/
│   │   ├── auth.py          # bcrypt, JWT pairs, CurrentUser, RoleAccess
│   │   ├── cache.py         # the Redis user cache
│   │   ├── email.py         # verification + reset emails (or logged links)
│   │   └── limiter.py       # shared slowapi limiter
│   └── schemas.py           # Pydantic schemas
├── tests/                   # unit (repository) + integration (routes) suites
├── docs/                    # Sphinx configuration and index
├── migrations/              # Alembic (schema history since hw-08)
├── Dockerfile               # runs migrations, then uvicorn
├── docker-compose.yaml      # api + postgres + redis
├── requirements.txt         # runtime dependencies
├── requirements-dev.txt     # pytest, coverage, fakeredis, Sphinx
└── .env.example             # every configurable value, no secrets committed
```

Routes stay thin: they translate HTTP into repository calls, while every query
and `commit` lives in the repository layer and everything security-related
lives in `src/services/auth.py`.
