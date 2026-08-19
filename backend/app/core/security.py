from __future__ import annotations

import hashlib
import secrets
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from threading import Lock

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

PASSWORD_MIN_LENGTH = 10
SESSION_COOKIE_NAME = "funding_session"
LOGIN_LIMIT = 5
LOGIN_WINDOW = timedelta(minutes=15)

password_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def hash_password(password: str) -> str:
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(f"A senha deve ter pelo menos {PASSWORD_MIN_LENGTH} caracteres.")
    return password_hasher.hash(password)


DUMMY_PASSWORD_HASH = password_hasher.hash(secrets.token_urlsafe(32))


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def new_session_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(48)
    return token, session_token_hash(token)


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class LoginRateLimiter:
    def __init__(self) -> None:
        self._attempts: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = Lock()

    @staticmethod
    def key(client_ip: str, email: str) -> str:
        safe_email = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
        return f"{client_ip}:{safe_email}"

    def retry_after(self, key: str, now: datetime | None = None) -> int:
        current = now or datetime.now(UTC)
        with self._lock:
            attempts = self._attempts[key]
            while attempts and current - attempts[0] >= LOGIN_WINDOW:
                attempts.popleft()
            if len(attempts) < LOGIN_LIMIT:
                return 0
            return max(1, int((LOGIN_WINDOW - (current - attempts[0])).total_seconds()))

    def record_failure(self, key: str, now: datetime | None = None) -> None:
        current = now or datetime.now(UTC)
        with self._lock:
            self._attempts[key].append(current)

    def clear(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

    def reset(self) -> None:
        with self._lock:
            self._attempts.clear()


login_rate_limiter = LoginRateLimiter()
