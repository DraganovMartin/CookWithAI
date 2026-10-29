"""CookWithAI Streamlit entry point: run with `streamlit run app/main.py`."""

import logging

import streamlit as st

from app.config import get_settings
from app.db.database import init_db
from app.llm.base import LLMError
from app.llm.factory import get_llm_client
from app.services.recipe_service import RecipeService, RecipeSession
from app.ui.components import recipe_detail_view, suggestion_card
from app.ui.styles import inject_styles

logging.basicConfig(level=logging.INFO)

COMMON_INGREDIENTS = [
    "beans", "bell pepper", "butter", "carrots", "cheese", "chicken breast", "eggs",
    "garlic", "ground beef", "lemon", "milk", "mushrooms", "onion", "pasta", "potatoes",
    "rice", "spinach", "tofu", "tomato", "zucchini",
]


@st.cache_resource
def get_service() -> RecipeService:
    settings = get_settings()
    init_db(settings.database_path)
    return RecipeService(get_llm_client(settings), settings.database_path)


# --- state helpers (used as on_click callbacks, so they run before the next render) ---

def _init_state() -> None:
    st.session_state.setdefault("session", None)
    st.session_state.setdefault("show_details", False)
    st.session_state.setdefault("ingredients", [])


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


# --- sections ---

def render_sidebar(service: RecipeService) -> None:
    with st.sidebar:
        st.button(
            "New search", icon=":material/add:", type="primary", width="stretch",
            on_click=_new_search,
        )
        st.subheader(":material/history: Recent", anchor=False)
        history = service.history()
        if not history:
            st.caption("Your searches will show up here.")
        for past in history:
            if past.details:
                label, icon = past.details.title, ":material/restaurant_menu:"
            else:
                label, icon = f"Ideas for {', '.join(past.available_ingredients)}", ":material/lightbulb:"
            st.button(
                label, key=f"history-{past.recipe_id}", icon=icon, type="tertiary",
                help=past.created_at, on_click=_load_session, args=(service, past.recipe_id),
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
        submitted = st.form_submit_button(
            "Find recipes", icon=":material/search:", type="primary"
        )

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
    for index, (column, suggestion) in enumerate(zip(columns, session.suggestions)):
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


def render_details(session: RecipeSession) -> None:
    st.button(
        "Back to suggestions", icon=":material/arrow_back:", type="tertiary",
        on_click=_back_to_suggestions,
    )
    recipe_detail_view(session.details, key_prefix=str(session.recipe_id))


def main() -> None:
    st.set_page_config(page_title="CookWithAI", page_icon=":material/skillet:", layout="wide")
    inject_styles()
    _init_state()

    try:
        service = get_service()
    except ValueError as exc:
        st.error(str(exc), icon=":material/error:")
        st.stop()

    render_sidebar(service)

    session: RecipeSession | None = st.session_state.session
    if session and session.details and st.session_state.show_details:
        render_details(session)
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
