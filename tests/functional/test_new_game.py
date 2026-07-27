"""
Functional: main menu -> New Game dialog -> Create Game.

Verifies the load-bearing new-game flow through the real UI: the map
canvas renders (non-blank pixels) and the empire summary bar shows the
starting empire.
"""

from .helpers import canvas_is_non_blank, create_game


def test_new_game_creates_playable_game(page, server):
    create_game(page, server, seed=1111, players=2, size="small",
                name="Functional New Game")

    # Main menu replaced by the game container
    assert page.locator("#menu-container").is_hidden()
    assert page.locator("#game-container").is_visible()

    # Galaxy map canvas renders actual content
    canvas = page.locator("#galaxy-map")
    assert canvas.is_visible()
    assert canvas_is_non_blank(page, "#galaxy-map"), \
        "galaxy map canvas is blank"

    # Empire summary bar shows the starting empire (1 planet, fleets)
    assert page.locator("#empire-summary").is_visible()
    assert page.locator("#summary-planets").inner_text() == "1"
    assert int(page.locator("#summary-fleets").inner_text()) >= 1

    # Footer year indicator shows the starting year
    year = page.evaluate("() => GameState.game.turn")
    assert f"Year {year}" in page.locator("#turn-indicator").inner_text()
