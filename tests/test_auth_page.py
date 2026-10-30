"""Drives the real Streamlit script with AppTest."""

from pathlib import Path
from types import SimpleNamespace

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from app.db.database import connect

APP_PATH = Path(__file__).parents[1] / "app" / "main.py"
EMAIL = "cook@example.com"
PASSWORD = "correct horse"


@pytest.fixture
def browser_cookies(monkeypatch):
    """The cookies the browser sends; AppTest would otherwise hand the app a MagicMock."""
    cookies: dict[str, str] = {}
    client = SimpleNamespace(cookies=cookies)
    monkeypatch.setattr("streamlit.runtime.context._get_client_context", lambda: client)
    return cookies


@pytest.fixture
def app(db_path, monkeypatch, browser_cookies):
    monkeypatch.setenv("DATABASE_PATH", db_path)
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    st.cache_resource.clear()
    return AppTest.from_file(APP_PATH, default_timeout=15).run()


def _button(app, label):
    return next(b for b in app.button if b.label == label)


def _labels(app):
    return [b.label for b in app.button]


def _open_auth_page(app):
    _button(app, "Log in or register").click().run()


def _submit(app, label, email, password):
    app.text_input[0].set_value(email)
    app.text_input[1].set_value(password)
    _button(app, label).click().run()


def test_guest_lands_on_the_app_with_a_login_button(app):
    assert not app.exception
    assert "Log in or register" in _labels(app)
    assert "Log out" not in _labels(app)
    assert any("aren't saved" in c.value for c in app.sidebar.caption)


def test_auth_page_fields_and_buttons(app):
    _open_auth_page(app)

    assert [t.label for t in app.text_input] == ["Email", "Password"]
    labels = _labels(app)
    # Login is first in the DOM so Enter submits it; CSS shows Register on the left.
    assert labels.index("Login") < labels.index("Register")
    assert "Forgotten password?" not in labels
    assert not app.error


def test_failed_login_shows_error_and_forgotten_password_link(app):
    _open_auth_page(app)
    _submit(app, "Login", EMAIL, "wrong password")

    assert [e.value for e in app.error] == ["Username or password are incorrect."]
    labels = _labels(app)
    assert labels.index("Register") < labels.index("Forgotten password?")
    assert labels.index("Login") < labels.index("Forgotten password?")


def test_forgotten_password_page_has_an_email_field(app):
    _open_auth_page(app)
    _submit(app, "Login", EMAIL, "wrong password")
    _button(app, "Forgotten password?").click().run()

    assert [t.label for t in app.text_input] == ["Email"]

    app.text_input[0].set_value(EMAIL)
    _button(app, "Reset password").click().run()
    assert "nothing was sent" in app.info[0].value

    _button(app, "Back to login").click().run()
    assert [t.label for t in app.text_input] == ["Email", "Password"]
    assert "Forgotten password?" not in _labels(app)


def test_register_logs_in_and_stores_a_session(app, db_path):
    _open_auth_page(app)
    _submit(app, "Register", EMAIL, PASSWORD)

    assert not app.exception
    assert "Log out" in _labels(app)
    assert any(EMAIL in c.value for c in app.sidebar.caption)
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (EMAIL,)).fetchone()
    assert app.session_state.login_session_id == row["session_id"]
    assert row["session_time"] == 7200


def test_register_with_bad_input_shows_the_reason(app):
    _open_auth_page(app)
    _submit(app, "Register", EMAIL, "short")

    assert "at least 8" in app.error[0].value
    assert "Forgotten password?" not in _labels(app)


def test_logout_ends_the_session(app, db_path):
    _open_auth_page(app)
    _submit(app, "Register", EMAIL, PASSWORD)
    _button(app, "Log out").click().run()

    assert "Log in or register" in _labels(app)
    assert not app.warning
    with connect(db_path) as conn:
        assert (
            conn.execute("SELECT session_id FROM users WHERE email = ?", (EMAIL,)).fetchone()[0]
            is None
        )


def test_expired_session_logs_the_user_out(app, db_path):
    _open_auth_page(app)
    _submit(app, "Register", EMAIL, PASSWORD)
    with connect(db_path) as conn:
        conn.execute("UPDATE users SET login_timestamp = datetime('now', '-2 hours')")

    app.run()

    assert "Log in or register" in _labels(app)
    assert app.warning[0].value == "Your session has expired."


def test_reopening_with_an_active_session_logs_in_automatically(browser_cookies, app, auth):
    user = auth.register(EMAIL, PASSWORD)
    browser_cookies["cookwithai_session"] = auth.start_session(user.id)

    reopened = AppTest.from_file(APP_PATH, default_timeout=15).run()

    assert not reopened.exception
    assert "Log out" in _labels(reopened)


def test_reopening_with_an_expired_session_stays_logged_out(db_path, browser_cookies, app, auth):
    user = auth.register(EMAIL, PASSWORD)
    browser_cookies["cookwithai_session"] = auth.start_session(user.id)
    with connect(db_path) as conn:
        conn.execute("UPDATE users SET login_timestamp = datetime('now', '-2 hours')")

    reopened = AppTest.from_file(APP_PATH, default_timeout=15).run()

    assert "Log in or register" in _labels(reopened)
    assert reopened.warning[0].value == "Your session has expired."


def test_logout_stays_logged_out_though_the_page_still_sees_the_old_cookie(
    browser_cookies, app, auth
):
    user = auth.register(EMAIL, PASSWORD)
    browser_cookies["cookwithai_session"] = auth.start_session(user.id)
    reopened = AppTest.from_file(APP_PATH, default_timeout=15).run()

    _button(reopened, "Log out").click().run()
    reopened.run()

    assert "Log in or register" in _labels(reopened)
    assert not reopened.warning


def test_continue_as_guest_leaves_the_auth_page(app):
    _open_auth_page(app)
    _button(app, "Continue as guest").click().run()

    assert "Log in or register" in _labels(app)
    assert not app.text_input
