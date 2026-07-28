"""
Seeded e2e: fleet battle doctrine.

The six admiralty standard plans ship in every empire's plan list -
they ARE the doctrine, there is no separate doctrine object - and an
empire-wide default is inherited by every fleet production builds, so
a commander who never opens the battle screen still fights coherently.

Withdrawal is no longer a battle-local flag. A fleet that breaks off
carries damage away and loses its remaining orders, so it cannot sail
straight back into the engagement it just fled.

Fleets are placed by state surgery and parked with the waypoint stack
from test_relations.py, the harness pattern reused from
test_battle_plans.py.
"""

from .test_battle_plans import (
    _deep_space_point, _fleet_named, _spawn_fleet)

SEED = 20260728

STANDARD_PLANS = [
    "Aggressive Assault", "Balanced", "Defensive Hold",
    "Commerce Raid", "Escort Screen", "Fighting Retreat",
]


class TestAdmiraltyPlansShipWithEveryEmpire:

    def test_standard_plans_are_present_and_survive_a_turn(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)

        for empire_id in (1, 2):
            plans = harness.state(empire_id)["battle_plans"]
            for name in STANDARD_PLANS:
                assert name in plans, f"empire {empire_id} lacks {name}"
            # The doctrine axes ride on the plan itself
            hold = plans["Defensive Hold"]
            assert (hold["stance"], hold["posture"], hold["withdraw"]) == (
                "Defensive", "Brace", "Half Armour")

        harness.generate_turn()
        plans = harness.state(1)["battle_plans"]
        assert all(name in plans for name in STANDARD_PLANS)
        assert plans["Commerce Raid"]["posture"] == "Scatter"

    def test_a_standard_plan_cannot_be_deleted(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)
        result = harness.submit(1, "battle_plan",
                                {"mode": "delete", "name": "Escort Screen"})
        assert result["status"] == "error"

    def test_a_commander_designs_plans_alongside_the_standards(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)
        result = harness.submit(1, "battle_plan", {"mode": "set", "plan": {
            "name": "Wolfpack", "primary_target": 7, "tactic": "Disengage",
            "stance": "Aggressive", "posture": "Scatter",
            "withdraw": "Outnumbered"}})
        assert result["status"] == "applied"

        plans = harness.state(1)["battle_plans"]
        assert plans["Wolfpack"]["stance"] == "Aggressive"
        assert all(name in plans for name in STANDARD_PLANS)

        # Unknown axis values are rejected
        for bad in ({"stance": "Berserk"}, {"posture": "Wedge"},
                    {"withdraw": "Whenever"}):
            result = harness.submit(1, "battle_plan", {
                "mode": "set", "plan": dict(bad, name="Bad")})
            assert result["status"] == "error", bad


class TestEmpireDefaultPlan:

    def test_new_empires_default_to_a_standard_plan(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)
        assert harness.state(1)["default_battle_plan"] == "Balanced"

    def test_production_hands_new_fleets_the_empire_default(self, harness):
        """Production used to set no plan at all - every fleet silently
        took the Fleet dataclass default."""
        harness.create_game(seed=SEED, size="tiny", players=2)
        assert harness.submit(1, "battle_plan", {
            "mode": "default", "name": "Escort Screen"})["status"] == "applied"

        star = harness.my_stars(1)[0]
        before = {f["key"] for f in harness.my_fleets(1)}
        design = next(d for d in harness.state(1)["designs"]
                      if d["name"] == "Long Range Scout")
        assert harness.submit(1, "production", {
            "mode": "Add", "star_key": star["name"], "index": 0,
            "production_order": {"production_type": "SHIP", "quantity": 1,
                                 "name": "Long Range Scout",
                                 "design_key": design["key"]},
        })["status"] == "applied"

        built = []
        for _ in range(6):
            harness.generate_turn()
            built = [f for f in harness.my_fleets(1)
                     if f["key"] not in before]
            if built:
                break
        assert built, "nothing was built"
        for fleet in built:
            assert fleet["battle_plan"] == "Escort Screen"

    def test_unknown_default_is_rejected(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)
        result = harness.submit(1, "battle_plan",
                                {"mode": "default", "name": "Ghost"})
        assert result["status"] == "error"


class TestWithdrawalConsequences:

    def test_a_fleet_that_flees_pays_for_it(self, harness):
        """A withdrawal used to be free: the same fleet fought again the
        next turn with full orders and no damage."""
        harness.create_game(seed=SEED, size="tiny", players=2)
        px, py = _deep_space_point(harness)

        assert harness.submit(2, "battle_plan", {"mode": "set", "plan": {
            "name": "Runner", "tactic": "Disengage",
            "attack": "Enemies"}})["status"] == "applied"

        _spawn_fleet(harness, 1, "Stalwart Defender", "Raider", px, py,
                     quantity=2)
        _spawn_fleet(harness, 2, "Swashbuckler", "Convoy", px, py,
                     battle_plan="Runner", parked=True)
        _spawn_fleet(harness, 2, "Stalwart Defender", "Escort Wing", px, py,
                     parked=True)

        harness.generate_turn()

        convoy = _fleet_named(harness, "Convoy", 2)
        assert convoy is not None, "the freighter should have escaped"
        # Charged in hull damage and in strategic position: the parking
        # waypoint stack is cut back to waypoint zero
        assert convoy["withdrawn_year"] == harness.state(2)["turn_year"] - 1
        assert len(convoy["waypoints"]) == 1
        assert any(t["damage_percent"] >= 15.0
                   for t in convoy["tokens"])
        assert any("withdrew" in m["text"]
                   for m in harness.state(2)["messages"])

    def test_a_fleet_that_stood_its_ground_pays_nothing(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)
        px, py = _deep_space_point(harness)

        _spawn_fleet(harness, 1, "Stalwart Defender", "Raider", px, py,
                     quantity=2)
        _spawn_fleet(harness, 2, "Stalwart Defender", "Escort Wing", px, py,
                     parked=True)

        harness.generate_turn()

        escort = _fleet_named(harness, "Escort Wing", 2)
        if escort is not None:
            assert escort["withdrawn_year"] == -1
            assert len(escort["waypoints"]) == 2
