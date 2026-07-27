"""
Shared UI-driving helpers for the functional browser harness.

All helpers use real clicks on the served frontend; JS evaluation is
reserved for assertions and for object selection where the canvas map
offers no DOM target (GameState.selectStar / selectFleet).
"""


def open_app(page, base_url):
    """Load the app and wait for the main menu."""
    page.goto(base_url)
    page.wait_for_selector("#menu-new-game")


def open_new_game_dialog(page):
    page.click("#menu-new-game")
    page.wait_for_selector("#btn-create-game")


def create_game(page, base_url, seed, players=2, size="small",
                name="Functional Game"):
    """Create a game through the New Game dialog and wait for load."""
    open_app(page, base_url)
    open_new_game_dialog(page)
    page.fill("#game-name", name)
    page.select_option("#player-count", str(players))
    page.select_option("#universe-size", size)
    page.fill("#game-seed", str(seed))
    page.click("#btn-create-game")
    page.wait_for_selector("#game-container:not(.hidden)", timeout=60000)
    page.wait_for_function(
        "() => window.GameState && GameState.game "
        "&& GameState.stars && GameState.stars.length > 0")


def close_dialog_if_open(page, timeout=3000):
    """Dismiss the current modal dialog (e.g. the turn report)."""
    try:
        page.wait_for_selector("#dialog-overlay:not(.hidden)",
                               timeout=timeout)
    except Exception:
        return
    page.click("#dialog-overlay .dialog-footer .btn-primary")
    page.wait_for_selector("#dialog-overlay.hidden", state="attached",
                           timeout=5000)


def menu_action(page, menu, action):
    """Open a menu-bar dropdown and click one of its actions."""
    page.click(f".menu-item[data-menu='{menu}']")
    page.click(f".menu-action[data-action='{action}']")


def current_year(page):
    return page.evaluate("() => GameState.game ? GameState.game.turn : null")


def generate_turn(page):
    """Generate a turn via the Turn menu; returns the new year.

    Waits for the year to increment, then dismisses the turn report
    dialog the app opens after each generation.
    """
    year_before = current_year(page)
    menu_action(page, "turn", "generateTurn")
    page.wait_for_function(
        f"() => GameState.game && GameState.game.turn === {year_before + 1}",
        timeout=120000)
    close_dialog_if_open(page)
    return year_before + 1


def select_owned_star(page):
    """Select the player's (first) owned star; returns its name."""
    return page.evaluate(
        "() => {"
        "  const star = GameState.stars.find(s => s.intel === 'owned');"
        "  GameState.selectStar(star);"
        "  return star.name;"
        "}")


def select_own_fleet(page, index=0):
    """Select one of the player's fleets; returns its name."""
    return page.evaluate(
        f"() => {{"
        f"  const fleet = GameState.fleets[{index}];"
        f"  GameState.selectFleet(fleet);"
        f"  return fleet.name;"
        f"}}")


def add_factory_to_queue(page, quantity=1):
    """Add Factories to the selected star's queue via the Add dialog."""
    page.click("#btn-add-production")
    page.wait_for_selector("#select-dialog-value")
    page.select_option("#select-dialog-value", "0")  # Factory
    page.click("#btn-select-confirm")
    page.wait_for_selector("#prompt-dialog-value")
    page.fill("#prompt-dialog-value", str(quantity))
    page.click("#btn-prompt-confirm")
    page.wait_for_selector("#star-panel .production-queue .queue-item")


def canvas_is_non_blank(page, selector):
    """True when the 2D canvas holds non-uniform pixel data."""
    return page.evaluate(
        f"() => {{"
        f"  const canvas = document.querySelector({selector!r});"
        f"  if (!canvas || !canvas.width || !canvas.height) return false;"
        f"  const ctx = canvas.getContext('2d');"
        f"  const data = ctx.getImageData(0, 0, canvas.width,"
        f"                                canvas.height).data;"
        f"  const first = [data[0], data[1], data[2], data[3]];"
        f"  for (let i = 4; i < data.length; i += 4) {{"
        f"    if (data[i] !== first[0] || data[i + 1] !== first[1]"
        f"        || data[i + 2] !== first[2]"
        f"        || data[i + 3] !== first[3]) return true;"
        f"  }}"
        f"  return false;"
        f"}}")
