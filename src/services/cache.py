"""Caching the authenticated user in Redis.

:func:`src.services.auth.get_current_user` runs on every protected request,
and without a cache each of those requests costs a database query. The user
is therefore kept in Redis for a short TTL and dropped from the cache
whenever anything about the account changes (avatar, confirmation, password,
role), so the cached copy can never outlive an update for long.

The cached value is plain JSON — only the fields the request pipeline needs,
never the password hash — so nothing executable is ever deserialised. When
Redis is unreachable every function degrades to a no-op and the app simply
falls back to PostgreSQL.
"""

import json
import logging

import redis

from src.conf.config import settings
from src.database.models import Role, User

logger = logging.getLogger("uvicorn.error")

_client: redis.Redis | None = None
_warned = False


def _get_client() -> redis.Redis:
    """Create the Redis client once and reuse it afterwards."""
    global _client
    if _client is None:
        _client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _client


def _key(email: str) -> str:
    return f"user:{email}"


def _warn_once(error: Exception) -> None:
    global _warned
    if not _warned:
        logger.warning("Redis unavailable, user cache disabled: %s", error)
        _warned = True


def get_cached_user(email: str) -> User | None:
    """Return the cached user for ``email``, or ``None`` on a miss.

    Args:
        email: The email claimed by the access token.

    Returns:
        A detached :class:`~src.database.models.User` rebuilt from the cached
        JSON, or ``None`` when the cache has no entry or Redis is down.
    """
    try:
        raw = _get_client().get(_key(email))
    except redis.RedisError as error:
        _warn_once(error)
        return None

    if raw is None:
        return None
    data = json.loads(raw)
    return User(
        id=data["id"],
        username=data["username"],
        email=data["email"],
        avatar=data["avatar"],
        confirmed=data["confirmed"],
        role=Role(data["role"]),
        created_at=data["created_at"],
    )


def cache_user(user: User) -> None:
    """Store ``user`` in Redis for ``USER_CACHE_TTL_SECONDS``.

    Only the fields needed to serve a request are stored; the password hash
    and the refresh token deliberately never reach the cache.

    Args:
        user: The freshly loaded user to cache.
    """
    data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "avatar": user.avatar,
        "confirmed": user.confirmed,
        "role": user.role.value,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
    try:
        _get_client().set(
            _key(user.email), json.dumps(data), ex=settings.user_cache_ttl_seconds
        )
    except redis.RedisError as error:
        _warn_once(error)


def invalidate_user(email: str) -> None:
    """Drop the cached entry after anything about the account changed.

    Args:
        email: The email of the account to evict.
    """
    try:
        _get_client().delete(_key(email))
    except redis.RedisError as error:
        _warn_once(error)
