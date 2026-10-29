"""Reusable Streamlit building blocks."""

import streamlit as st

from app.llm.schemas import RecipeDetails, RecipeSuggestion

_DIFFICULTY_ICON = {
    "easy": ":material/sentiment_satisfied:",
    "medium": ":material/local_fire_department:",
    "hard": ":material/whatshot:",
}


def availability_badge(suggestion: RecipeSuggestion) -> None:
    # Badges truncate in narrow columns, so keep them short and list the items separately.
    if suggestion.uses_only_available:
        st.badge("You have everything", icon=":material/check_circle:", color="green")
    else:
        count = len(suggestion.missing_ingredients)
        st.badge(f"Need {count} more", icon=":material/shopping_cart:", color="orange")
        st.caption(f"Missing: {', '.join(suggestion.missing_ingredients)}")


def suggestion_card(suggestion: RecipeSuggestion, index: int) -> bool:
    """Render one suggestion; returns True when its "Cook this" button was clicked."""
    with st.container(border=True, key=f"card-{index}", height="stretch"):
        st.subheader(suggestion.title, anchor=False)
        availability_badge(suggestion)
        st.write(suggestion.short_description)
        st.caption(
            f":material/schedule: {suggestion.estimated_time_minutes} min"
            f" &nbsp;·&nbsp; {_DIFFICULTY_ICON[suggestion.difficulty]} {suggestion.difficulty.title()}"
        )
        return st.button(
            "Cook this",
            key=f"cook-{index}",
            type="primary",
            icon=":material/restaurant:",
            width="stretch",
        )


def recipe_detail_view(details: RecipeDetails, key_prefix: str) -> None:
    st.title(details.title, anchor=False)

    total_minutes = sum(s.duration_minutes or 0 for s in details.steps)
    missing = [i for i in details.ingredients if i.is_missing]
    with st.container(horizontal=True):
        st.badge(f"{details.servings} servings", icon=":material/group:", color="violet")
        if total_minutes:
            st.badge(f"~{total_minutes} min", icon=":material/timer:", color="blue")
        if missing:
            st.badge(f"{len(missing)} to buy", icon=":material/shopping_cart:", color="orange")
        else:
            st.badge("Nothing to buy", icon=":material/check_circle:", color="green")

    left, right = st.columns([1, 2], gap="large")
    with left:
        st.subheader(":material/grocery: Ingredients", anchor=False)
        for i, ingredient in enumerate(details.ingredients):
            label = f"**{ingredient.quantity}** {ingredient.name}"
            if ingredient.is_missing:
                label += " :orange-badge[missing]"
            st.checkbox(label, key=f"{key_prefix}-ing-{i}")

    with right:
        st.subheader(":material/format_list_numbered: Steps", anchor=False)
        for step in details.steps:
            with st.container(border=True, key=f"step-{key_prefix}-{step.number}"):
                header = f"**Step {step.number}**"
                if step.duration_minutes:
                    header += f" &nbsp;·&nbsp; :material/timer: {step.duration_minutes} min"
                st.markdown(header)
                st.write(step.instruction)

        if details.tips:
            st.subheader(":material/lightbulb: Tips", anchor=False)
            for tip in details.tips:
                st.info(tip, icon=":material/tips_and_updates:")
