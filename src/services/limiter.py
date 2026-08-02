"""Shared slowapi rate limiter, keyed by the client address.

Routes decorate themselves with ``@limiter.limit(...)``; main.py registers the
handler that turns an exceeded limit into a 429 response.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
