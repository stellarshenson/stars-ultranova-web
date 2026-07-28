"""
Functional: turn generation, message pane, message Goto.

Generates turns via the Turn menu, checks the year increments in the
footer indicator, that the messages pane populates, and that Goto on a
star-linked message selects and centers that star.
"""

from .helpers import (add_factory_to_queue, close_dialog_if_open,
                      create_game, current_year, generate_turn,
                      menu_action, select_owned_star)

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


def test_turn_report_only_opens_with_messages(page, server):
    """DEF-3: no turn report dialog on a turn that carried no messages.

    Early turns of an untouched game produce no messages at all, and an
    empty "No messages this turn" report forced a dismiss every year.
    The dialog must open exactly on the turns that have messages.
    """
    create_game(page, server, seed=7777, players=2, size="small",
                name="Functional Report Gate")

    saw_empty_turn = False
    saw_message_turn = False
    for turn in range(MAX_TURNS_FOR_STAR_MESSAGE):
        # Queue a Factory partway through so a message turn is reached
        if turn == 2:
            select_owned_star(page)
            add_factory_to_queue(page, quantity=1)

        year_before = current_year(page)
        menu_action(page, "turn", "generateTurn")
        page.wait_for_function(
            "() => GameState.game && GameState.game.turn === "
            f"{year_before + 1}", timeout=120000)
        page.wait_for_timeout(300)  # let the report dialog open if it will

        count = page.evaluate("() => GameState.messages.length")
        overlay_open = page.evaluate(
            "() => !document.getElementById('dialog-overlay')"
            ".classList.contains('hidden')")

        if count == 0:
            saw_empty_turn = True
            assert not overlay_open, \
                f"turn report opened on year {year_before + 1} with no messages"
        else:
            saw_message_turn = True
            assert overlay_open, \
                f"no turn report on year {year_before + 1} with {count} messages"
            assert "Report" in page.locator("#dialog-overlay").inner_text()
            close_dialog_if_open(page)
            break

    assert saw_empty_turn, "no zero-message turn observed"
    assert saw_message_turn, "no turn with messages observed"
