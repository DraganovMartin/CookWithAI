import re

from cookwithai.ui.styles import _CSS


def test_css_has_nothing_the_html_sanitizer_would_reject():
    # st.html silently drops the whole style block if its text contains anything tag-like.
    stylesheet = _CSS.replace("<style>", "").replace("</style>", "")
    assert not re.search(r"<[/\w!]", stylesheet)
