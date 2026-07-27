"""
Functional: New Game -> Design Custom Race -> Save Race.

Verifies the race designer wizard through the real UI: name the race,
pick an emblem, save, and see the race offered in the New Game race
selector.
"""

from .helpers import open_app, open_new_game_dialog

RACE_NAME = "Functional Testers"


def test_race_designer_saves_race(page, server):
    open_app(page, server)
    open_new_game_dialog(page)

    # Enter the race designer
    page.click("#btn-design-race")
    page.wait_for_selector("#race-wizard:not(.hidden)")

    # Name the race. Each change event re-renders the whole wizard
    # (RaceWizard.updateField -> render), so commit one field at a
    # time and wait for the model before touching the next control.
    page.fill("#race-name", RACE_NAME)
    page.locator("#race-name").blur()
    page.wait_for_function(
        f"() => RaceWizard.raceData.name === {RACE_NAME!r}")
    page.fill("#race-plural", RACE_NAME)
    page.locator("#race-plural").blur()
    page.wait_for_function(
        f"() => RaceWizard.raceData.pluralName === {RACE_NAME!r}")

    # Pick an emblem from the standard set
    page.locator("#race-wizard .icon-option").nth(5).click()
    page.wait_for_function("() => RaceWizard.raceData.icon === 5")
    assert "selected" in (page.locator("#race-wizard .icon-option")
                          .nth(5).get_attribute("class") or "")

    # Save once the server-computed advantage points arrive (the
    # debounced /races/validate round-trip re-enables the button)
    page.wait_for_function(
        "() => RaceWizard.advantagePoints !== null"
        " && RaceWizard.advantagePoints >= 0")
    save_btn = page.locator("#race-wizard button", has_text="Save Race")
    save_btn.click()

    # Wizard closes and the New Game dialog reopens with the race
    page.wait_for_selector("#race-wizard.hidden", state="attached")
    page.wait_for_selector("#player-race")
    options = page.locator("#player-race option").all_inner_texts()
    assert any(RACE_NAME in text for text in options), \
        f"saved race not in selector: {options}"
