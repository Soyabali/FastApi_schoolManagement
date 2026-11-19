"""Password hashing, token helpers and time helpers."""

import hashlib
import secrets
from datetime import UTC, datetime

import bcrypt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        # The stored value is not a valid bcrypt hash (for example the sample rows).
        return False


def new_token() -> str:
    """A random, URL-safe token for sessions and password resets."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Reset tokens are stored hashed, so a database leak doesn't expose usable tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def utcnow() -> datetime:
    """Current time in UTC (time-zone aware), matching the timestamptz columns."""
    return datetime.now(UTC)
