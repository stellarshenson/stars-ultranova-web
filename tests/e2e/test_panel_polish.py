"""
Seeded e2e: left-column panel polish (user directive, acc-crit
"Panel polish").

The star/fleet panels render their sections directly into .panel,
which the classic layout strips to padding 0 - so panel text sat
flush against the panel borders. The polish rules restore consistent
inner padding on the left-column panels, separate the fleet panel
header like the star panel header, and keep the empire summary rows
on the 8px vertical rhythm. A browser pass verifies the rendered
result outside this workflow; here a seeded game proves the app
serves the polished stylesheet alongside a playable state.
"""

SEED = 20260714


def test_left_column_panel_polish_served(harness):
    harness.create_game(SEED, size="small", players=2)

    # The seeded game exposes the state the left-column panels render
    state = harness.state(1)
    assert state["stars"], "seeded game must expose stars for the star panel"
    assert harness.my_fleets(1), "seeded game must expose fleets for the fleet panel"

    # Served stylesheet carries the panel polish rules
    css = harness.client.get("/static/css/main.css")
    assert css.status_code == 200
    text = css.text

    # Inner padding: no text flush against left-column panel borders
    assert "#left-column > .panel {" in text
    polish = text.split("#left-column > .panel {", 1)[1]
    assert "padding: 0.75rem 1rem 1rem;" in polish.split("}")[0]

    # Last section relies on the panel padding for its bottom gap
    assert "#left-column .star-section:last-child" in text
    assert "#left-column .fleet-section:last-child" in text

    # Fleet panel header separated like the star panel header
    fleet_header = text.split(".fleet-panel-header {", 1)[1].split("}")[0]
    assert "padding-bottom: 0.75rem;" in fleet_header
    assert "border-bottom: 1px solid #333;" in fleet_header

    # Empire summary keeps an 8px row gap when sections wrap
    summary = text.split("#left-column #empire-summary {", 1)[1].split("}")[0]
    assert "gap: 0.5rem 1.25rem;" in summary

    # Cache-buster bumped so clients pick up the polished stylesheet
    index = harness.client.get("/")
    assert index.status_code == 200
    assert "static/css/main.css?v=10" in index.text


def test_left_column_spacing_scale(harness):
    """The polish block normalizes off-scale values (0.35rem items,
    1.25rem sections, 0.15rem badge padding) to the 4/8/12/16px scale
    within #left-column, leaving dialogs and reports untouched."""
    harness.create_game(SEED, size="small", players=2)

    css = harness.client.get("/static/css/main.css")
    assert css.status_code == 200
    text = css.text

    def rule(selector):
        assert selector in text, f"missing polish rule for {selector}"
        # Return the declaration block that follows the selector's rule
        # opening (selector may share a rule via a comma group)
        idx = text.index(selector)
        return text[idx:].split("{", 1)[1].split("}", 1)[0]

    # Sections separated by 16px inside the left column
    assert "margin-bottom: 1rem;" in rule("#left-column .star-section,")

    # Bars and mineral rows on the 8px rhythm
    assert "margin: 0.5rem 0;" in rule("#left-column .progress-bar")
    assert "margin-bottom: 0.5rem;" in rule("#left-column .resource-row,")

    # List rows: 8px inner padding
    assert "padding: 0.5rem;" in rule("#left-column .ship-item,")
    assert "padding: 0.5rem 0.75rem;" in rule(
        "#left-column .waypoint-leg-details")

    # Habitability badge: 4px/8px padding
    assert "padding: 0.25rem 0.5rem;" in rule(
        "#left-column .habitability-indicator")

    # Empire summary label-value gap on the 8px step
    section = text.split(
        "#left-column #empire-summary .summary-section {", 1)[1].split("}")[0]
    assert "gap: 0.5rem;" in section

    # Base rules outside the left column keep their original values
    # (polish is scoped, not a redesign)
    base_item = text.split("\n.ship-item,", 1)[1].split("}")[0]
    assert "padding: 0.35rem 0.5rem;" in base_item
