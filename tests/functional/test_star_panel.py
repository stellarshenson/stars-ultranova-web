"""
Functional: star selection, star panel, production queue edit.

Selects the player's owned star (GameState.selectStar - the canvas map
has no DOM per-star target), verifies the star panel shows population
and infrastructure, then adds a Factory to the production queue through
the Add dialog and sees it appear in the queue.
"""

from .helpers import create_game, select_owned_star


def test_star_panel_and_production_queue(page, server):
    create_game(page, server, seed=2222, players=2, size="small",
                name="Functional Star Panel")

    star_name = select_owned_star(page)
    panel = page.locator("#star-panel")
    assert panel.is_visible()

    text = panel.inner_text()
    low = text.lower()
    assert star_name in text
    assert "population" in low
    assert "colonists" in low
    assert "factories" in low
    assert "mines" in low

    # Add a Factory via the production Add dialog
    page.click("#btn-add-production")
    page.wait_for_selector("#select-dialog-value")
    page.select_option("#select-dialog-value", "0")  # Factory
    page.click("#btn-select-confirm")

    page.wait_for_selector("#prompt-dialog-value")
    page.fill("#prompt-dialog-value", "2")
    page.click("#btn-prompt-confirm")

    # The item lands in the rendered queue
    page.wait_for_selector("#star-panel .production-queue .queue-item")
    item = page.locator("#star-panel .production-queue .queue-item").first
    assert "Factory" in item.inner_text()
    assert "x2" in item.inner_text()

    # And in the server-refreshed state
    queue = page.evaluate(
        "() => GameState.stars.find(s => s.intel === 'owned')"
        ".production_queue")
    assert queue and queue[0]["quantity"] == 2
