"""Email + password accounts and the 2-hour login session."""

import hashlib
import hmac
import re
import secrets
import sqlite3
import uuid
from dataclasses import dataclass

from app.db import repository
from app.db.database import connect

SESSION_SECONDS = 2 * 60 * 60
MIN_PASSWORD_LENGTH = 8

_EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")

# OWASP's recommended scrypt settings for 32 MiB of memory.
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 3
_SALT_BYTES = 16
_HASH_BYTES = 32


class AuthError(Exception):
    """A registration problem whose message is safe to show to the user."""


@dataclass(frozen=True)
class User:
    """The signed-in user as the UI sees it; deliberately has no password hash."""

    id: int
    email: str
    display_name: str


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        maxmem=256 * n * r,  # OpenSSL's 32 MiB default is too low for these settings
        dklen=_HASH_BYTES,
    )


def hash_password(password: str) -> str:
    """Hash a password with a fresh random salt.

    Args:
        password: The plain-text password.

    Returns:
        A string holding the scrypt parameters, salt and hash, ready to store.
    """
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = _scrypt(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a password against a value produced by `hash_password`.

    Args:
        password: The plain-text password to check.
        stored_hash: The stored hash string.

    Returns:
        True if the password matches.
    """
    _, n, r, p, salt, digest = stored_hash.split("$")
    candidate = _scrypt(password, bytes.fromhex(salt), int(n), int(r), int(p))
    return hmac.compare_digest(candidate, bytes.fromhex(digest))


# Checked for unknown emails, so they take as long to reject as a wrong password.
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def _to_user(record: repository.UserRecord) -> User:
    return User(id=record.id, email=record.email, display_name=record.display_name)


class AuthService:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    def register(self, email: str, password: str) -> User:
        """Create an account.

        Args:
            email: The email to use as the username.
            password: The plain-text password; only its hash is stored.

        Returns:
            The new user.

        Raises:
            AuthError: If the email is invalid or taken, or the password is too short.
        """
        email = normalize_email(email)
        if not _EMAIL_PATTERN.fullmatch(email):
            raise AuthError("Enter a valid email address.")
        if len(password) < MIN_PASSWORD_LENGTH:
            raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")

        password_hash = hash_password(password)
        try:
            with connect(self._db_path) as conn:
                record = repository.create_user(conn, email, email.split("@")[0], password_hash)
        except sqlite3.IntegrityError as exc:
            raise AuthError("An account with that email already exists.") from exc
        return _to_user(record)

    def login(self, email: str, password: str) -> User | None:
        """Check credentials.

        Args:
            email: The email entered as the username.
            password: The plain-text password.

        Returns:
            The user, or None if the email or password is wrong.
        """
        with connect(self._db_path) as conn:
            record = repository.get_user_by_email(conn, normalize_email(email))
        if record is None:
            verify_password(password, _DUMMY_HASH)
            return None
        return _to_user(record) if verify_password(password, record.password_hash) else None

    def start_session(self, user_id: int) -> str:
        """Start a session for a user, ending any session they already had.

        Args:
            user_id: The user who just logged in.

        Returns:
            The new session ID, a random UUID.
        """
        session_id = str(uuid.uuid4())
        with connect(self._db_path) as conn:
            repository.start_session(conn, user_id, session_id, SESSION_SECONDS)
        return session_id

    def user_from_session(self, session_id: str) -> User | None:
        """Look up the user of an active session.

        Args:
            session_id: The session ID from the browser.

        Returns:
            The user, or None if the session is unknown, ended or expired.
        """
        with connect(self._db_path) as conn:
            record = repository.get_user_by_session(conn, session_id)
        return _to_user(record) if record else None

    def end_session(self, session_id: str) -> None:
        with connect(self._db_path) as conn:
            repository.end_session(conn, session_id)
