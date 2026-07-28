"""
Seeded e2e: unarmed-vs-unarmed co-location never battles (DEF-14) and
battle messages carry the loss summary (DEF-15).

Before the DEF-14 fix the Ron engine counted unarmed flee-targets as
battle triggers, so two stranded unarmed ships (run100 Sabik: e1
Teamster vs e2 Long Range Scout) fought a 60-round movement-only
battle with zero possible attacks EVERY turn for 12 years. C#
SelectTargets skips unarmed wolves entirely (BattleEngine.cs:412-415)
so such a standoff produces no battle, no report, no message.

Fleets are placed by state surgery at a deep-space point with the AI
empire's fleet parked (established harness pattern,
test_electronics_battle.py).
"""

import re

SEED = 20260728


def _spawn_fleet(harness, empire_id, design_name, name, x, y,
                 parked=False):
    """Create a one-ship fleet at (x, y) by state surgery (pattern
    from test_electronics_battle.py); returns its key."""
    from backend.core.data_structures import NovaPoint
    from backend.core.game_objects import Fleet
    from backend.core.waypoints.waypoint import (
        Waypoint, LayMinesTaskObj, NoTaskObj)
    from backend.services.game_manager import get_game_manager
    from backend.services.ship_specs import find_design, make_token

    manager = get_game_manager()
    server_data = manager._load_game_state(harness.game_id)
    empire = server_data.all_empires[empire_id]
    design = find_design(empire, design_name)
    assert design is not None, f"no design '{design_name}'"

    fleet = Fleet()
    fleet.key = empire.get_next_fleet_key()
    fleet.name = name
    fleet.turn_year = empire.turn_year
    fleet.position = NovaPoint(x, y)
    fleet.battle_plan = "Default"
    token = make_token(design, 1)
    fleet.tokens[token.design_key] = token
    fleet.fuel_available = fleet.total_fuel_capacity
    if parked:
        # AI-held fleets: >1 waypoints keeps DefaultAI hands off
        fleet.waypoints = [
            Waypoint(position_x=x, position_y=y, warp_factor=4,
                     destination="park", task=LayMinesTaskObj()),
            Waypoint(position_x=x, position_y=y, warp_factor=4,
                     destination="park", task=NoTaskObj()),
        ]
    empire.owned_fleets[fleet.key] = fleet
    manager._save_game_state(harness.game_id, server_data)
    return fleet.key


def _deep_space_point(harness):
    """Fractional-coordinate point midway between the homeworlds."""
    home1 = harness.my_stars(1)[0]
    home2 = harness.my_stars(2)[0]
    return ((home1["position_x"] + home2["position_x"]) / 2 + 0.5,
            (home1["position_y"] + home2["position_y"]) / 2 + 0.5)


def _battle_messages(harness, empire_id):
    return [m for m in harness.state(empire_id)["messages"]
            if m.get("type") == "Battle"]


class TestPhantomBattles:

    def test_unarmed_standoff_never_battles(self, harness):
        """The run100 Sabik reproduction: two co-located unarmed
        hostile ships, three turns, zero battles."""
        harness.create_game(seed=SEED, size="tiny", players=2)

        px, py = _deep_space_point(harness)
        _spawn_fleet(harness, 1, "Teamster", "Standoff Teamster",
                     px, py)
        _spawn_fleet(harness, 2, "Long Range Scout", "Standoff Scout",
                     px, py, parked=True)

        for _ in range(3):
            harness.generate_turn()
            assert _battle_messages(harness, 1) == []
            assert _battle_messages(harness, 2) == []

        for empire_id in (1, 2):
            reports = harness._request(
                "GET",
                f"/api/games/{harness.game_id}"
                f"/empires/{empire_id}/battles")
            assert reports == []

    def test_armed_vs_unarmed_battles_with_loss_summary(self, harness):
        """An armed ship meeting the unarmed one still battles, and
        both battle messages carry a loss summary. The C# bare count
        (BattleEngine.cs:945-953) grew into the per-design outcome
        ledger with per-ship attrition (DEF-35), so the summary now
        reads 'N x Design -> K destroyed, M survived at X% damage'."""
        harness.create_game(seed=SEED, size="tiny", players=2)

        px, py = _deep_space_point(harness)
        _spawn_fleet(harness, 1, "Stalwart Defender", "Hunter",
                     px, py)
        _spawn_fleet(harness, 2, "Long Range Scout", "Prey",
                     px, py, parked=True)

        harness.generate_turn()

        pattern = re.compile(
            r"\d+ x .+ -> \d+ destroyed, \d+ survived at \d+% damage")
        for empire_id in (1, 2):
            msgs = _battle_messages(harness, empire_id)
            assert len(msgs) == 1
            assert "A battle took place at" in msgs[0]["text"]
            assert pattern.search(msgs[0]["text"]), msgs[0]["text"]
