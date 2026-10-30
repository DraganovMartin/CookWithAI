"""Register / login page and the forgotten password page."""

import streamlit as st

from app.services.auth_service import AuthError, AuthService, User


def _leave_auth_page() -> None:
    st.session_state.show_auth = False


def _show_forgot_password(show: bool) -> None:
    st.session_state.show_forgot_password = show
    st.session_state.login_failed = False


def _render_forgot_password() -> None:
    st.subheader("Forgotten password", anchor=False)
    with st.form("forgot-password", border=False):
        st.text_input("Email", autocomplete="email")
        submitted = st.form_submit_button("Reset password", type="primary", width="stretch")
    if submitted:
        st.info(
            "Password reset emails aren't set up yet, so nothing was sent.",
            icon=":material/info:",
        )
    st.button(
        "Back to login",
        icon=":material/arrow_back:",
        type="tertiary",
        on_click=_show_forgot_password,
        args=(False,),
    )


def _render_login(auth: AuthService) -> User | None:
    message = st.empty()
    with st.form("auth", border=False):
        email = st.text_input("Email", autocomplete="email")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        # Enter clicks a form's first submit button. That has to be Login, so a mistyped email
        # can't create an account; the CSS for this key shows Register on the left.
        with st.container(horizontal=True, key="auth-buttons"):
            login = st.form_submit_button("Login", type="primary", width="stretch")
            register = st.form_submit_button("Register", width="stretch")

    user = None
    error = None
    if login:
        user = auth.login(email, password)
        if user is None:
            st.session_state.login_failed = True
            error = "Username or password are incorrect."
    elif register:
        try:
            user = auth.register(email, password)
        except AuthError as exc:
            error = str(exc)
    if error:
        message.error(error, icon=":material/error:")

    if st.session_state.login_failed:
        st.button(
            "Forgotten password?",
            key="forgot-link",
            type="tertiary",
            on_click=_show_forgot_password,
            args=(True,),
        )
    st.button(
        "Continue as guest",
        icon=":material/person:",
        type="tertiary",
        on_click=_leave_auth_page,
    )
    return user


def render_auth_page(auth: AuthService) -> User | None:
    """Render the login page, or the forgotten password page if it was opened.

    Args:
        auth: The service that checks credentials and creates accounts.

    Returns:
        The user who just logged in or registered, otherwise None.
    """
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.title(":material/skillet: CookWithAI", anchor=False)
        if st.session_state.show_forgot_password:
            _render_forgot_password()
            return None
        return _render_login(auth)
