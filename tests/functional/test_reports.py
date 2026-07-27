"""
Functional: score report renders with the empire row.

Opens the score report from the Report menu after one generated turn
and verifies the table renders one row per empire, including the
player's race.
"""

from .helpers import create_game, generate_turn, menu_action


def test_score_report_renders_empire_row(page, server):
    create_game(page, server, seed=6666, players=2, size="small",
                name="Functional Reports")
    generate_turn(page)  # ensure score records exist

    menu_action(page, "report", "scoreHistory")
    page.wait_for_selector("#reports-panel:not(.hidden)")
    page.wait_for_selector("#reports-panel .report-table")

    rows = page.locator("#reports-panel .report-table tbody tr")
    empire_count = page.evaluate("() => GameState.scores.length")
    assert empire_count >= 2
    assert rows.count() == empire_count

    my_race = page.evaluate(
        "() => (GameState.scores.find("
        "s => s.empire_id === GameState.empireId) || {}).race_name")
    assert my_race, "player empire missing from score records"
    table_text = page.locator("#reports-panel .report-table").inner_text()
    assert my_race in table_text
