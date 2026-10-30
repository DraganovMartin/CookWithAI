import uuid

import pytest

from cookwithai.db.database import connect
from cookwithai.services.auth_service import (
    SESSION_SECONDS,
    AuthError,
    hash_password,
    verify_password,
)

EMAIL = "cook@example.com"
PASSWORD = "correct horse"


def _backdate_login(db_path, user_id, seconds):
    with connect(db_path) as conn:
        conn.execute(
            "UPDATE users SET login_timestamp = datetime('now', ?) WHERE id = ?",
            (f"-{seconds} seconds", user_id),
        )


def test_hash_verifies_only_the_right_password():
    stored = hash_password(PASSWORD)
    assert PASSWORD not in stored
    assert verify_password(PASSWORD, stored)
    assert not verify_password("wrong password", stored)


def test_same_password_gets_a_different_salt():
    assert hash_password(PASSWORD) != hash_password(PASSWORD)


def test_register_stores_only_a_hash(auth, db_path):
    user = auth.register(EMAIL, PASSWORD)
    with connect(db_path) as conn:
        stored = conn.execute("SELECT * FROM users WHERE id = ?", (user.id,)).fetchone()
    assert stored["password_hash"].startswith("scrypt$")
    assert PASSWORD not in tuple(stored)
    assert user.display_name == "cook"


@pytest.mark.parametrize("email", ["", "no-at-sign", "two@@example.com", "a b@example.com", "a@b"])
def test_register_rejects_invalid_email(auth, email):
    with pytest.raises(AuthError, match="valid email"):
        auth.register(email, PASSWORD)


def test_register_rejects_short_password(auth):
    with pytest.raises(AuthError, match="at least 8"):
        auth.register(EMAIL, "short")


@pytest.mark.parametrize("duplicate", [EMAIL, "  COOK@Example.com "])
def test_register_rejects_existing_email(auth, duplicate):
    auth.register(EMAIL, PASSWORD)
    with pytest.raises(AuthError, match="already exists"):
        auth.register(duplicate, PASSWORD)


def test_login_ignores_email_case_and_spaces(auth):
    user = auth.register(EMAIL, PASSWORD)
    assert auth.login(" COOK@example.com ", PASSWORD) == user


@pytest.mark.parametrize(
    ("email", "password"),
    [(EMAIL, "wrong password"), ("nobody@example.com", PASSWORD), ("", "")],
)
def test_login_rejects_bad_credentials(auth, email, password):
    auth.register(EMAIL, PASSWORD)
    assert auth.login(email, password) is None


def test_session_id_is_a_random_uuid_lasting_two_hours(auth, db_path):
    user = auth.register(EMAIL, PASSWORD)
    session_id = auth.start_session(user.id)

    assert uuid.UUID(session_id).version == 4
    assert auth.user_from_session(session_id) == user
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user.id,)).fetchone()
    assert row["session_id"] == session_id
    assert row["session_time"] == 7200
    assert row["login_timestamp"] is not None


def test_session_is_active_until_two_hours_have_passed(auth, db_path):
    user = auth.register(EMAIL, PASSWORD)
    session_id = auth.start_session(user.id)

    _backdate_login(db_path, user.id, SESSION_SECONDS - 60)
    assert auth.user_from_session(session_id) == user

    _backdate_login(db_path, user.id, SESSION_SECONDS)
    assert auth.user_from_session(session_id) is None


def test_ended_session_is_inactive_but_keeps_the_login_time(auth, db_path):
    user = auth.register(EMAIL, PASSWORD)
    session_id = auth.start_session(user.id)

    auth.end_session(session_id)

    assert auth.user_from_session(session_id) is None
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user.id,)).fetchone()
    assert row["session_id"] is None
    assert row["login_timestamp"] is not None


def test_new_login_replaces_the_previous_session(auth):
    user = auth.register(EMAIL, PASSWORD)
    first = auth.start_session(user.id)
    second = auth.start_session(user.id)

    assert auth.user_from_session(first) is None
    assert auth.user_from_session(second) == user


def test_unknown_session(auth):
    assert auth.user_from_session(str(uuid.uuid4())) is None
