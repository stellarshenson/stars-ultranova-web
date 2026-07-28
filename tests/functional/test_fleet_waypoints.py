"""
Functional: fleet selection and waypoint editing.

Selects one of the player's fleets, adds a waypoint through the Add
Waypoint dialog (destination, warp, task), changes the leg's warp with
the slider (keyboard, firing real input/change events) and its task
with the selector, then reloads state from the server and verifies the
edits persisted.
"""

from .helpers import create_game, select_own_fleet


def test_fleet_waypoint_editing(page, server):
    create_game(page, server, seed=3333, players=2, size="small",
                name="Functional Waypoints")

    select_own_fleet(page)
    panel = page.locator("#fleet-panel")
    assert panel.is_visible()

    # Add a waypoint: nearest star, warp 7, task None
    page.click("#btn-add-waypoint")
    page.wait_for_selector("#select-dialog-value")
    page.select_option("#select-dialog-value", "0")
    page.click("#btn-select-confirm")

    page.wait_for_selector("#prompt-dialog-value")
    page.fill("#prompt-dialog-value", "7")
    page.click("#btn-prompt-confirm")

    page.wait_for_selector("#select-dialog-value")  # task picker
    page.select_option("#select-dialog-value", "0")  # None
    page.click("#btn-select-confirm")

    page.wait_for_selector("#fleet-panel .waypoint-item")
    assert "Warp 7" in page.locator(
        "#fleet-panel .waypoint-item").first.inner_text()

    # Change warp via the slider (7 -> 6): ArrowLeft fires input+change
    slider = page.locator("#wp-warp-slider")
    slider.focus()
    slider.press("ArrowLeft")
    page.wait_for_function(
        "() => document.getElementById('wp-warp-value')"
        " && document.getElementById('wp-warp-value').textContent === '6'")

    # Change the task via the selector
    page.wait_for_selector("#wp-task-select")
    page.select_option("#wp-task-select", "Lay Mines")

    # Reload the fleet from server state; the edits must persist
    page.wait_for_function(
        "() => GameState.fleets[0].waypoints.length === 1"
        " && GameState.fleets[0].waypoints[0].warp_factor === 6")
    page.evaluate(
        "async () => {"
        "  await GameState.refreshState();"
        "  GameState.selectFleet(GameState.fleets[0]);"
        "}")
    page.wait_for_selector("#fleet-panel .waypoint-item")
    item_text = page.locator("#fleet-panel .waypoint-item").first.inner_text()
    assert "Warp 6" in item_text
    assert "Lay Mines" in item_text

    wp = page.evaluate("() => GameState.fleets[0].waypoints[0]")
    assert wp["warp_factor"] == 6
    # The server reports the task in the command vocabulary, so the
    # value read back is exactly what the edit command sent (DEF-1)
    assert wp["task_type"] == "LayMines"
