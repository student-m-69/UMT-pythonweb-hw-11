"""REST API for storing and managing contacts, with JWT authentication.

    uvicorn main:app --reload

Swagger UI is served at /docs and ReDoc at /redoc.
"""

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from src.conf.config import settings
from src.database.db import DbSession
from src.routes import auth, contacts, users
from src.services.limiter import limiter

app = FastAPI(
    title="Contacts API",
    description="REST API for storing and managing contacts, built with "
    "FastAPI, SQLAlchemy and PostgreSQL. All contact operations require "
    "a JWT obtained via /api/auth/login.",
    version="2.0.0",
)

# Rate limiting (slowapi): routes opt in with @limiter.limit(...).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(contacts.router, prefix="/api")


@app.get("/", tags=["utility"], summary="Service greeting")
def root():
    return {"message": "Contacts API. See /docs for the Swagger documentation."}


@app.get("/api/healthchecker", tags=["utility"], summary="Database connectivity check")
def healthchecker(db: DbSession):
    """Confirm the API can reach PostgreSQL."""
    try:
        result = db.execute(text("SELECT 1")).scalar()
    except Exception as error:  # pragma: no cover - depends on the environment
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error connecting to the database",
        ) from error

    if result != 1:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database is not configured correctly",
        )
    return {"message": "Database connection is healthy"}
