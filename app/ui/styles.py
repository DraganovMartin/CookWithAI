"""Small CSS layer on top of .streamlit/config.toml for Material-style surfaces."""

import streamlit as st

# Containers created with key="card-..." get the class "st-key-card-..." from Streamlit.
# Don't write anything tag-like in here, even in a CSS comment: st.html's sanitizer drops the
# whole style block if it finds one.
_CSS = """
<style>
[class*="st-key-card-"] {
    background: #FFFFFF;
    border-radius: 16px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, .3), 0 1px 3px 1px rgba(0, 0, 0, .15);
    transition: box-shadow .2s ease;
}
[class*="st-key-card-"]:hover {
    box-shadow: 0 1px 2px rgba(0, 0, 0, .3), 0 2px 6px 2px rgba(0, 0, 0, .15);
}
[class*="st-key-step-"] {
    background: #FFFFFF;
    border-radius: 12px;
}
h1, h2, h3 { letter-spacing: 0; font-weight: 500 !important; }
/* Login comes first in the DOM (Enter submits it) but is shown to the right of Register. */
.st-key-auth-buttons { flex-direction: row-reverse; }
/* A tertiary button styled as a link, so opening the page keeps the Streamlit session. */
.st-key-forgot-link button, .st-key-forgot-link button p {
    color: #6750A4;
    text-decoration: underline;
}
</style>
"""


def inject_styles() -> None:
    st.html(_CSS)
