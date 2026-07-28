"""
Seeded e2e: battle plans - CRUD, fleet assignment, engine honoring.

Plans live per empire keyed by name (EmpireData.cs:91) and fleets
reference them by name (Fleet.cs:60). No C# battle-plan command exists
(the Nova dialog's New/Modify buttons are disabled,
BattlePlans.Designer.cs:94,104); the web "battle_plan" command is the
transport for the client edit, like the relation command. The Ron
engine honors the plan's attack-who (BattleEngine.cs:468-494 plus the
dialog-only "Enemies and Neutrals" option), five target tiers
(stars-nova trunk Victims model) and tactic (canonical Stars! rules -
the C# engine never consumed Tactic, BattleEngine.cs:603 TODO).

Battle scenario: an empire-1 raider pair meets an empire-2 convoy
(unarmed privateer freighter + armed escort) on a deep-space point.
With the freighter on a "Disengage" plan it flees the board (7 flee
moves, canonical) and survives while its escort fights; in the control
game (same seed, same fleets, default plan) the raiders hunt the
freighter down after destroying the escort. Fleets are placed by state
surgery (the established harness pattern, see test_cloaking_intel.py)
and empire 2's fleets carry the parking waypoint stack from
test_relations.py so the AI leaves them alone.
"""

SEED = 20260713

FIVE_TIERS = ("primary_target", "secondary_target", "tertiary_target",
              "quaternary_target", "quinary_target")


def _spawn_fleet(harness, empire_id, design_name, name, x, y,
                 quantity=1, battle_plan="Default", parked=False):
    """Create a fleet at (x, y) by state surgery; returns its key."""
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
    fleet.battle_plan = battle_plan
    token = make_token(design, quantity)
    fleet.tokens[token.design_key] = token
    fleet.fuel_available = fleet.total_fuel_capacity
    if parked:
        # AI-held fleets: >1 waypoints keeps DefaultAI hands off; the
        # LayMines waypoint at the fleet's own position never pops
        # (parking stack pattern from test_relations.py)
        fleet.waypoints = [
            Waypoint(position_x=x, position_y=y, warp_factor=4,
                     destination="park", task=LayMinesTaskObj()),
            Waypoint(position_x=x, position_y=y, warp_factor=4,
                     destination="park", task=NoTaskObj()),
        ]
    empire.owned_fleets[fleet.key] = fleet
    manager._save_game_state(harness.game_id, server_data)
    return fleet.key


def _fleet_named(harness, name, empire_id):
    for fleet in harness.my_fleets(empire_id):
        if fleet["name"] == name:
            return fleet
    return None


def _deep_space_point(harness):
    """Fractional-coordinate point midway between the homeworlds."""
    home1 = harness.my_stars(1)[0]
    home2 = harness.my_stars(2)[0]
    return ((home1["position_x"] + home2["position_x"]) / 2 + 0.5,
            (home1["position_y"] + home2["position_y"]) / 2 + 0.5)


class TestBattlePlanCrud:

    def test_plan_crud_and_fleet_assignment(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)

        # Every empire starts with the Default plan (EmpireData.cs:160)
        plans = harness.state(1)["battle_plans"]
        assert "Default" in plans

        # Create a fully customized plan and round-trip it
        sniper = {
            "name": "Sniper",
            "primary_target": 2,     # Capital Ship
            "secondary_target": 0,   # Starbase
            "tertiary_target": 1,    # Bomber
            "quaternary_target": 3,  # Escort
            "quinary_target": 6,     # Support Ship
            "tactic": "Maximise Damage Ratio",
            "attack": "Enemies and Neutrals",
            "target_id": 0,
        }
        result = harness.submit(1, "battle_plan",
                                {"mode": "set", "plan": sniper})
        assert result["status"] == "applied"
        stored = harness.state(1)["battle_plans"]["Sniper"]
        for key, value in sniper.items():
            assert stored[key] == value

        # Validation: bad tactic / attack / tier are rejected
        for bad_plan in (
            {"name": "Bad", "tactic": "Ramming Speed"},
            {"name": "Bad", "attack": "Nobody"},
            {"name": "Bad", "primary_target": 9},
        ):
            result = harness.submit(1, "battle_plan",
                                    {"mode": "set", "plan": bad_plan})
            assert result["status"] == "error", bad_plan
        result = harness.submit(1, "battle_plan",
                                {"mode": "set", "plan": {"name": "  "}})
        assert result["status"] == "error"

        # Default cannot be deleted; unknown names are rejected
        result = harness.submit(1, "battle_plan",
                                {"mode": "delete", "name": "Default"})
        assert result["status"] == "error"
        result = harness.submit(1, "battle_plan",
                                {"mode": "delete", "name": "Ghost"})
        assert result["status"] == "error"

        # Cap: the canonical 14 player plans plus the six admiralty
        # standard plans seeded into every empire. Default and Sniper
        # already occupy two of the player slots
        from backend.server.battle.battle_plan import MAX_BATTLE_PLANS
        existing = len(harness.state(1)["battle_plans"])
        for i in range(existing, MAX_BATTLE_PLANS):
            result = harness.submit(1, "battle_plan", {
                "mode": "set", "plan": {"name": f"Plan {i}"}})
            assert result["status"] == "applied"
        assert len(harness.state(1)["battle_plans"]) == MAX_BATTLE_PLANS
        result = harness.submit(1, "battle_plan", {
            "mode": "set", "plan": {"name": "One Too Many"}})
        assert result["status"] == "error"
        # Editing an existing plan is still allowed at the cap
        result = harness.submit(1, "battle_plan", {
            "mode": "set", "plan": dict(sniper, tactic="Disengage")})
        assert result["status"] == "applied"

        # Assign the plan to an owned fleet (Fleet.cs:60)
        fleet = harness.my_fleets(1)[0]
        result = harness._request(
            "POST",
            f"/api/games/{harness.game_id}/fleets/{fleet['key']}"
            f"/battle-plan",
            {"empire_id": 1, "plan": "Sniper"})
        assert result["battle_plan"] == "Sniper"
        updated = [f for f in harness.my_fleets(1)
                   if f["key"] == fleet["key"]][0]
        assert updated["battle_plan"] == "Sniper"

        # Unknown plan and foreign fleet are rejected with 400
        response = harness.client.post(
            f"/api/games/{harness.game_id}/fleets/{fleet['key']}"
            f"/battle-plan",
            json={"empire_id": 1, "plan": "Ghost"})
        assert response.status_code == 400
        foreign = harness.my_fleets(2)[0]
        response = harness.client.post(
            f"/api/games/{harness.game_id}/fleets/{foreign['key']}"
            f"/battle-plan",
            json={"empire_id": 1, "plan": "Sniper"})
        assert response.status_code == 400

        # Plans and the assignment survive turn generation (and the
        # DB round-trip inside it)
        harness.generate_turn()
        state = harness.state(1)
        assert state["battle_plans"]["Sniper"]["tactic"] == "Disengage"
        persisted = [f for f in state["fleets"]
                     if f["key"] == fleet["key"]][0]
        assert persisted["battle_plan"] == "Sniper"

        # Deleting an assigned plan reassigns its fleets to the empire
        # default plan (canonical safety, C# absent)
        result = harness.submit(1, "battle_plan",
                                {"mode": "delete", "name": "Sniper"})
        assert result["status"] == "applied"
        state = harness.state(1)
        assert "Sniper" not in state["battle_plans"]
        reassigned = [f for f in state["fleets"]
                      if f["key"] == fleet["key"]][0]
        assert reassigned["battle_plan"] == state["default_battle_plan"]


def _run_convoy_battle(harness, freighter_tactic):
    """One-turn deep-space battle: 2x raider vs freighter + escort.

    The freighter's plan carries `freighter_tactic`; returns the turn
    result dict."""
    harness.create_game(seed=SEED, size="tiny", players=2)
    px, py = _deep_space_point(harness)

    result = harness.submit(2, "battle_plan", {"mode": "set", "plan": {
        "name": "Runner", "tactic": freighter_tactic,
        "attack": "Enemies"}})
    assert result["status"] == "applied"

    _spawn_fleet(harness, 1, "Stalwart Defender", "Raider", px, py,
                 quantity=2)
    _spawn_fleet(harness, 2, "Swashbuckler", "Convoy", px, py,
                 battle_plan="Runner", parked=True)
    _spawn_fleet(harness, 2, "Stalwart Defender", "Escort Wing", px, py,
                 parked=True)

    return harness.generate_turn()


class TestBattlePlanTactics:

    def test_disengage_freighter_escapes_while_escort_fights(self, harness):
        result = _run_convoy_battle(harness, "Disengage")

        # The battle happened at the rendezvous
        battles = [m for m in result["messages"] if m["type"] == "Battle"]
        assert any(m["audience"] == 2 for m in battles)
        reports = harness._request(
            "GET", f"/api/games/{harness.game_id}/empires/2/battles")
        assert reports, "no battle report for empire 2"

        # The escort (armed, default Maximise Damage plan) fought:
        # weapons fire from an empire-2 stack is on record
        steps = reports[0]["steps"]
        assert any(s["type"] == "Weapons"
                   and (s["weapon_target"]["stack_key"] >> 32) == 2
                   for s in steps), "escort never fired"

        # The disengaging freighter left the battle and survived
        assert _fleet_named(harness, "Convoy", 2) is not None, \
            "disengaging freighter was destroyed"
        # The raiders won the stand-up fight
        assert _fleet_named(harness, "Raider", 1) is not None

    def test_control_freighter_without_disengage_is_destroyed(self, harness):
        """Same seed, same fleets, default closing tactic: the raiders
        hunt the freighter down - the discriminating outcome for the
        Disengage tactic."""
        result = _run_convoy_battle(harness, "Maximise Damage")

        battles = [m for m in result["messages"] if m["type"] == "Battle"]
        assert any(m["audience"] == 2 for m in battles)
        assert _fleet_named(harness, "Convoy", 2) is None, \
            "freighter survived without Disengage"
        assert _fleet_named(harness, "Raider", 1) is not None

    def test_scenario_is_deterministic(self, harness):
        """Same seed + same commands -> identical state digests."""
        digests = []
        for _ in range(2):
            _run_convoy_battle(harness, "Disengage")
            digests.append((harness.state_digest(1),
                            harness.state_digest(2)))
        assert digests[0] == digests[1]
