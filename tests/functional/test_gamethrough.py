"""
Functional: THE COMPLETE GAMETHROUGH on a fixed seed.

Creates a game with seed 4242 (2 players, small) through the New Game
dialog, then advances 30 turns through the Turn menu, asserting each
year increments with no console errors (console forensics fail the
test via the page fixture).

Golden-outcome bootstrap: at the end a snapshot (year, own planet
count, fleet count, score) is read from the exposed GameState and
compared against tests/functional/golden/gamethrough_seed4242.json.
On the FIRST run (file absent) the snapshot is WRITTEN as the golden
record; every subsequent run must reproduce it exactly. Turn
generation is seeded per (seed, year), so an identical seed must
reproduce identical outcomes deterministically.
"""

import json
from pathlib import Path

from .helpers import create_game, generate_turn

SEED = 4242
TURNS = 30
GOLDEN_PATH = (Path(__file__).resolve().parent / "golden"
               / "gamethrough_seed4242.json")


def test_gamethrough_seed4242(page, server):
    create_game(page, server, seed=SEED, players=2, size="small",
                name="Gamethrough 4242")
    start_year = page.evaluate("() => GameState.game.turn")

    for i in range(1, TURNS + 1):
        year = generate_turn(page)
        assert year == start_year + i, \
            f"turn {i}: expected year {start_year + i}, got {year}"
        indicator = page.locator("#turn-indicator").inner_text()
        assert f"Year {year}" in indicator

    snapshot = page.evaluate(
        "() => ({"
        "  year: GameState.game.turn,"
        "  planets: GameState.stars.filter("
        "s => s.intel === 'owned').length,"
        "  fleets: GameState.fleets.length,"
        "  score: (GameState.scores.find("
        "s => s.empire_id === GameState.empireId) || {}).score ?? null"
        "})")

    assert snapshot["year"] == start_year + TURNS
    assert snapshot["planets"] >= 1

    if not GOLDEN_PATH.exists():
        GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(GOLDEN_PATH, "w") as f:
            json.dump(snapshot, f, indent=2, sort_keys=True)
            f.write("\n")
        return  # bootstrap run: golden recorded

    with open(GOLDEN_PATH) as f:
        golden = json.load(f)
    assert snapshot == golden, (
        f"gamethrough outcome diverged from golden record:\n"
        f"  golden:   {golden}\n"
        f"  observed: {snapshot}")
