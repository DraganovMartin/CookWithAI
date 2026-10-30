"""CookWithAI Streamlit entry point: run with `streamlit run src/cookwithai/main.py`."""

import logging

import streamlit as st

from cookwithai.config import get_settings
from cookwithai.db.database import init_db
from cookwithai.llm.base import LLMClient, LLMError
from cookwithai.llm.factory import get_llm_client
from cookwithai.llm.schemas import RecipeDetails
from cookwithai.services.auth_service import SESSION_SECONDS, AuthService, User
from cookwithai.services.recipe_service import RecipeService, RecipeSession
from cookwithai.ui.auth import render_auth_page
from cookwithai.ui.components import recipe_detail_view, suggestion_card
from cookwithai.ui.styles import inject_styles

logging.basicConfig(level=logging.INFO)

SESSION_COOKIE = "cookwithai_session"
SESSION_CHECK_INTERVAL = "60s"

COMMON_INGREDIENTS = [
    "beans",
    "bell pepper",
    "butter",
    "carrots",
    "cheese",
    "chicken breast",
    "eggs",
    "garlic",
    "ground beef",
    "lemon",
    "milk",
    "mushrooms",
    "onion",
    "pasta",
    "potatoes",
    "rice",
    "spinach",
    "tofu",
    "tomato",
    "zucchini",
]


@st.cache_resource
def get_llm() -> LLMClient:
    return get_llm_client(get_settings())


@st.cache_resource
def get_auth_service() -> AuthService:
    settings = get_settings()
    init_db(settings.database_path)
    return AuthService(settings.database_path)


# --- state helpers (used as on_click callbacks, so they run before the next render) ---


def _init_state() -> None:
    st.session_state.setdefault("session", None)
    st.session_state.setdefault("show_details", False)
    st.session_state.setdefault("ingredients", [])
    st.session_state.setdefault("login_session_id", None)
    st.session_state.setdefault("cookie_read", False)
    st.session_state.setdefault("pending_cookie", None)
    st.session_state.setdefault("session_expired", False)
    st.session_state.setdefault("show_auth", False)
    st.session_state.setdefault("show_forgot_password", False)
    st.session_state.setdefault("login_failed", False)


def _show_auth() -> None:
    st.session_state.show_auth = True
    st.session_state.show_forgot_password = False
    st.session_state.login_failed = False


def _new_search() -> None:
    st.session_state.session = None
    st.session_state.show_details = False
    st.session_state.ingredients = []


def _load_session(service: RecipeService, recipe_id: int) -> None:
    session = service.load(recipe_id)
    if session is None:
        st.toast("That recipe could not be found.", icon=":material/error:")
        return
    st.session_state.session = session
    st.session_state.ingredients = session.available_ingredients
    st.session_state.show_details = session.details is not None


def _back_to_suggestions() -> None:
    st.session_state.show_details = False


# --- login session ---


def _clear_login() -> None:
    """Forget the login in this browser, along with anything the user had on screen."""
    st.session_state.login_session_id = None
    st.session_state.pending_cookie = ""
    _new_search()


def _logout(auth: AuthService) -> None:
    auth.end_session(st.session_state.login_session_id)
    _clear_login()


def _start_login(auth: AuthService, user: User) -> None:
    session_id = auth.start_session(user.id)
    st.session_state.login_session_id = session_id
    st.session_state.pending_cookie = session_id
    st.session_state.show_auth = False
    st.session_state.session = None
    st.session_state.show_details = False


def current_user(auth: AuthService) -> User | None:
    """Return the logged-in user, or None for a guest.

    The session ID comes from the browser cookie once per connection, because
    `st.context.cookies` never changes after the page loads and would still show a cookie that
    has since been replaced or cleared. Every run then re-checks the session in the database.

    Args:
        auth: The service that looks sessions up.

    Returns:
        The user of the active session, if there is one.
    """
    if not st.session_state.cookie_read:
        st.session_state.cookie_read = True
        st.session_state.login_session_id = st.context.cookies.get(SESSION_COOKIE)

    session_id = st.session_state.login_session_id
    if session_id is None:
        return None
    user = auth.user_from_session(session_id)
    if user is None:
        _clear_login()
        st.session_state.session_expired = True
    return user


def write_pending_cookie() -> None:
    """Set or clear the session cookie. Streamlit can only do this from the browser."""
    value = st.session_state.pending_cookie
    if value is None:
        return
    st.session_state.pending_cookie = None
    max_age = SESSION_SECONDS if value else 0
    # `value` is a UUID we generated or an empty string, so it's safe to put in the script.
    st.html(
        f"""<script>
        document.cookie = "{SESSION_COOKIE}={value}; Path=/; SameSite=Lax; Max-Age={max_age}"
            + (location.protocol === "https:" ? "; Secure" : "");
        </script>""",
        unsafe_allow_javascript=True,
    )


@st.fragment(run_every=SESSION_CHECK_INTERVAL)
def watch_session(auth: AuthService, session_id: str) -> None:
    """Log an idle tab out when its session ends, without waiting for a click."""
    if auth.user_from_session(session_id) is None:
        st.rerun(scope="app")


# --- sections ---


def render_sidebar(service: RecipeService, auth: AuthService, user: User | None) -> None:
    with st.sidebar:
        st.button(
            "New search",
            icon=":material/add:",
            type="primary",
            width="stretch",
            on_click=_new_search,
        )
        if user is None:
            st.caption("Guest searches aren't saved.")
            st.button(
                "Log in or register",
                icon=":material/login:",
                width="stretch",
                on_click=_show_auth,
            )
            return

        st.subheader(":material/history: Recent", anchor=False)
        history = service.history()
        if not history:
            st.caption("Your searches will show up here.")
        for past in history:
            if past.details:
                label, icon = past.details.title, ":material/restaurant_menu:"
            else:
                label, icon = (
                    f"Ideas for {', '.join(past.available_ingredients)}",
                    ":material/lightbulb:",
                )
            st.button(
                label,
                key=f"history-{past.recipe_id}",
                icon=icon,
                type="tertiary",
                help=past.created_at,
                on_click=_load_session,
                args=(service, past.recipe_id),
            )

        st.divider()
        st.caption(user.email)
        st.button(
            "Log out",
            icon=":material/logout:",
            width="stretch",
            on_click=_logout,
            args=(auth,),
        )


def render_search(service: RecipeService) -> None:
    current = st.session_state.ingredients
    with st.form("search", border=False):
        st.multiselect(
            "What's in your pantry?",
            options=sorted(set(COMMON_INGREDIENTS) | set(current)),
            key="ingredients",
            accept_new_options=True,
            placeholder="Pick or type ingredients, then press Enter…",
        )
        submitted = st.form_submit_button("Find recipes", icon=":material/search:", type="primary")

    if submitted:
        try:
            with st.spinner("Asking the chef for ideas…"):
                st.session_state.session = service.suggest(st.session_state.ingredients)
        except ValueError as exc:
            st.warning(str(exc), icon=":material/info:")
        except LLMError as exc:
            st.error(f"Couldn't get suggestions: {exc}", icon=":material/error:")
        else:
            st.session_state.show_details = False
            st.rerun()  # so the sidebar history picks up the new search


def render_suggestions(service: RecipeService, session: RecipeSession) -> None:
    st.subheader(":material/auto_awesome: Pick a recipe", anchor=False)
    columns = st.columns(len(session.suggestions), gap="medium")
    for index, (column, suggestion) in enumerate(zip(columns, session.suggestions, strict=True)):
        with column:
            if suggestion_card(suggestion, index):
                try:
                    with st.spinner(f"Writing up {suggestion.title}…"):
                        service.choose(session, suggestion)
                except LLMError as exc:
                    st.error(f"Couldn't load the recipe: {exc}", icon=":material/error:")
                    return
                st.session_state.show_details = True
                st.rerun()


def render_details(session: RecipeSession, details: RecipeDetails) -> None:
    st.button(
        "Back to suggestions",
        icon=":material/arrow_back:",
        type="tertiary",
        on_click=_back_to_suggestions,
    )
    # Guests have no recipe id; id(session) keeps checkbox state separate between their recipes.
    recipe_detail_view(details, key_prefix=str(session.recipe_id or id(session)))


def main() -> None:
    st.set_page_config(page_title="CookWithAI", page_icon=":material/skillet:", layout="wide")
    inject_styles()
    _init_state()

    auth = get_auth_service()
    user = current_user(auth)
    write_pending_cookie()

    if user is None and st.session_state.show_auth:
        signed_in = render_auth_page(auth)
        if signed_in:
            _start_login(auth, signed_in)
            st.rerun()
        return

    try:
        service = RecipeService(get_llm(), get_settings().database_path, user.id if user else None)
    except ValueError as exc:
        st.error(str(exc), icon=":material/error:")
        st.stop()

    render_sidebar(service, auth, user)
    if user:
        watch_session(auth, st.session_state.login_session_id)

    if st.session_state.session_expired:
        st.session_state.session_expired = False
        st.warning("Your session has expired.", icon=":material/schedule:")

    session: RecipeSession | None = st.session_state.session
    if session and session.details and st.session_state.show_details:
        render_details(session, session.details)
        return

    st.title(":material/skillet: CookWithAI", anchor=False)
    st.caption("Tell me what you have, and I'll suggest what to cook.")
    if get_settings().llm_provider == "mock":
        st.badge("Mock AI responses", icon=":material/science:", color="gray")

    render_search(service)
    session = st.session_state.session
    if session:
        render_suggestions(service, session)


main()
