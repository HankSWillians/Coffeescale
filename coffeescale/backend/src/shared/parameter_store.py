"""AWS Parameter Store client with in-memory TTL cache.

Avoids a round-trip to SSM on every Lambda invocation while keeping
configuration fresh within the runtime lifecycle.  Default TTL = 60 s.
"""

import os
import time
from typing import Any

import boto3

_cache: dict[str, tuple[str, float]] = {}  # path -> (value, expires_at)
_client: Any = None
DEFAULT_TTL = int(os.environ.get("PARAM_CACHE_TTL_SECONDS", "60"))


def _get_client() -> Any:
    global _client  # noqa: PLW0603
    if _client is None:
        _client = boto3.client("ssm", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _client


def get_parameter(path: str, ttl: int = DEFAULT_TTL, decrypt: bool = True) -> str:
    """Fetch *path* from Parameter Store, returning the cached value if fresh.

    Args:
        path: Full SSM path, e.g. "/coffeescale/hmac/secret".
        ttl: Cache TTL in seconds.
        decrypt: Whether to decrypt SecureString parameters.

    Returns:
        The parameter value as a string.

    Raises:
        boto3 exceptions on SSM errors (caller decides how to handle).
    """
    now = time.monotonic()
    if path in _cache:
        value, expires_at = _cache[path]
        if now < expires_at:
            return value

    response = _get_client().get_parameter(Name=path, WithDecryption=decrypt)
    value = response["Parameter"]["Value"]
    _cache[path] = (value, now + ttl)
    return value


def invalidate(path: str) -> None:
    """Remove *path* from cache (useful in tests)."""
    _cache.pop(path, None)


def clear_cache() -> None:
    """Clear entire cache (useful in tests)."""
    _cache.clear()
