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
    assert "static/css/main.css?v=8" in index.text
