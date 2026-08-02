"""REST API for storing and managing contacts.

    uvicorn main:app --reload

Swagger UI is served at /docs and ReDoc at /redoc.
"""

from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text

from src.database.db import DbSession
from src.routes import contacts

app = FastAPI(
    title="Contacts API",
    description="REST API for storing and managing contacts, built with "
    "FastAPI, SQLAlchemy and PostgreSQL.",
    version="1.0.0",
)

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
