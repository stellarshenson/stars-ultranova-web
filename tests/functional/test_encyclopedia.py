"""
Functional: encyclopedia entries render artwork and numbers.

Opens the encyclopedia from the Help menu and iterates ALL entries:
each must paint a non-blank artwork canvas (pixel data not uniform)
and state concrete numbers in its text.
"""

import re

from .helpers import canvas_is_non_blank, menu_action, open_app


def test_encyclopedia_entries_render(page, server):
    open_app(page, server)

    menu_action(page, "help", "encyclopedia")
    page.wait_for_selector("#encyclopedia-content")

    entries = page.locator(".encyclopedia-entry")
    ids = [entries.nth(i).get_attribute("data-entry")
           for i in range(entries.count())]
    assert len(ids) >= 3, f"suspiciously few encyclopedia entries: {ids}"

    for i, entry_id in enumerate(ids):
        entries.nth(i).click()
        page.wait_for_selector("#encyclopedia-art")
        page.wait_for_function(
            "id => {"
            "  const el = document.querySelector("
            "    '.encyclopedia-entry[data-entry=\"' + id + '\"]');"
            "  return el && el.classList.contains('active');"
            "}", arg=entry_id)

        assert canvas_is_non_blank(page, "#encyclopedia-art"), \
            f"entry '{entry_id}' artwork canvas is blank"

        content = page.locator("#encyclopedia-content").inner_text()
        assert re.search(r"\d", content), \
            f"entry '{entry_id}' states no numbers"
