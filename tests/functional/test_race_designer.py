"""
Functional: New Game -> Design Custom Race -> Save Race.

Verifies the race designer wizard through the real UI: name the race,
pick an emblem, save, and see the race offered in the New Game race
selector.
"""

from .helpers import open_app, open_new_game_dialog

RACE_NAME = "Functional Testers"
SINGULAR = "Antaran"
PLURAL = "Antarans"


def test_race_designer_saves_race(page, server):
    open_app(page, server)
    open_new_game_dialog(page)

    # Enter the race designer
    page.click("#btn-design-race")
    page.wait_for_selector("#race-wizard:not(.hidden)")

    # Name the race, committing each field with a blur and waiting for
    # the model before touching the next control.
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


def test_race_designer_keeps_typed_input_across_fields(page, server):
    """DEF-2: typing two fields in a row must not lose the second.

    Types Race Name, then clicks straight into Plural Name and types
    it - the way a human fills a form. A full wizard re-render on the
    first field's change event destroys the focused Plural Name input,
    so the second value never lands in the model.
    """
    open_app(page, server)
    open_new_game_dialog(page)
    page.click("#btn-design-race")
    page.wait_for_selector("#race-wizard:not(.hidden)")

    page.click("#race-name")
    page.keyboard.press("Control+a")
    page.keyboard.type(SINGULAR)

    # Click into the next field: this blurs Race Name and fires its
    # change event while the caret is already in Plural Name
    page.click("#race-plural")
    page.keyboard.press("Control+a")
    page.keyboard.type(PLURAL)
    page.keyboard.press("Tab")

    page.wait_for_function(
        f"() => RaceWizard.raceData.name === {SINGULAR!r}")
    assert page.input_value("#race-name") == SINGULAR
    assert page.input_value("#race-plural") == PLURAL, \
        "Plural Name input was reset by a re-render"
    assert page.evaluate("() => RaceWizard.raceData.pluralName") == PLURAL, \
        "Plural Name never committed to the model"


def test_race_designer_save_click_during_validate(page, server):
    """DEF-2: a Save click inside the validate debounce is not lost.

    Changes a field and clicks Save Race immediately, while the
    debounced /races/validate round-trip is still pending. The click
    must still save rather than land on a disabled button.
    """
    open_app(page, server)
    open_new_game_dialog(page)
    page.click("#btn-design-race")
    page.wait_for_selector("#race-wizard:not(.hidden)")

    # Commit the field and click Save in the same synchronous step, so
    # the click provably lands inside the debounce window (Playwright's
    # own click waits for the button to become enabled again and would
    # hide the defect). btn.click() is a real activation: the browser
    # drops it if the button is disabled, exactly as a user's click.
    state = page.evaluate(
        "() => {"
        f"  const input = document.getElementById('race-name');"
        f"  input.value = {SINGULAR!r};"
        "   input.dispatchEvent(new Event('change'));"
        "   const btn = [...document.querySelectorAll('#race-wizard button')]"
        "     .find(b => b.textContent.includes('Save Race'));"
        "   const disabled = btn.disabled;"
        "   btn.click();"
        "   return {pending: RaceWizard.advantagePoints === null, disabled};"
        "}")
    assert state["pending"], "validation was not pending after the change"
    assert not state["disabled"], \
        "Save Race disabled while /races/validate is pending"

    page.wait_for_selector("#race-wizard.hidden", state="attached")
    saved = page.evaluate(
        "() => JSON.parse(localStorage.getItem('customRaces') || '[]')"
        ".map(r => r.name)")
    assert SINGULAR in saved, f"race not saved: {saved}"
