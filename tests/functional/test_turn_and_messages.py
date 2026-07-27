"""
Functional: turn generation, message pane, message Goto.

Generates turns via the Turn menu, checks the year increments in the
footer indicator, that the messages pane populates, and that Goto on a
star-linked message selects and centers that star.
"""

from .helpers import (add_factory_to_queue, create_game, generate_turn,
                      select_owned_star)

MAX_TURNS_FOR_STAR_MESSAGE = 10


def test_turn_generation_and_message_goto(page, server):
    create_game(page, server, seed=5555, players=2, size="small",
                name="Functional Turns")
    start_year = page.evaluate("() => GameState.game.turn")

    # Queue a Factory on the homeworld so the next turn deterministically
    # produces a star-linked message ("<star> has built 1 factory")
    select_owned_star(page)
    add_factory_to_queue(page, quantity=1)

    # Generate one turn via the Turn menu: year increments in the UI
    year = generate_turn(page)
    assert year == start_year + 1
    assert f"Year {year}" in page.locator("#turn-indicator").inner_text()

    # Advance until a star-linked message arrives (linkage:
    # star_name); not every early turn produces messages
    for _ in range(MAX_TURNS_FOR_STAR_MESSAGE):
        if page.evaluate(
                "() => GameState.messages.some(m => m.star_name"
                " && GameState.stars.some("
                "s => s.name === m.star_name))"):
            break
        generate_turn(page)
    else:
        raise AssertionError(
            "no star-linked message within "
            f"{MAX_TURNS_FOR_STAR_MESSAGE} turns")

    # Messages pane populates when a turn carries messages
    page.wait_for_selector("#message-panel:not(.hidden)")
    count = page.evaluate("() => GameState.messages.length")
    assert count >= 1
    assert f"of {count}" in page.locator("#message-panel").inner_text()

    # Walk to the star-linked message with the real nav buttons
    target_index = page.evaluate(
        "() => GameState.messages.findIndex(m => m.star_name"
        " && GameState.stars.some(s => s.name === m.star_name))")
    star_name = page.evaluate(
        f"() => GameState.messages[{target_index}].star_name")
    current = page.evaluate("() => MessagePanel.currentIndex")
    for _ in range(current, target_index):
        page.click("#message-panel button:has-text('Next >')")
    for _ in range(target_index, current):
        page.click("#message-panel button:has-text('< Prev')")

    # Goto selects and centers the star
    goto_btn = page.locator("#message-panel button", has_text="Goto")
    assert goto_btn.is_enabled(), "Goto disabled on star-linked message"
    goto_btn.click()

    page.wait_for_selector("#star-panel:not(.hidden)")
    assert star_name in page.locator("#star-panel").inner_text()
    selected = page.evaluate(
        "() => GameState.selectedStar && GameState.selectedStar.name")
    assert selected == star_name
