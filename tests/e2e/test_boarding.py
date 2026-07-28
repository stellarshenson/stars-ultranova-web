"""
Seeded e2e: a boarding ship designed, ordered and flown.

The whole path through the real server: the commander researches the
boarding line, designs an Assault Transport with marines aboard, the
role cascade files it as a Boarding Ship, a plan tells it to board,
and a deep-space engagement produces a boarding action in the replay.

Fleets are placed by state surgery and parked with the waypoint stack
from test_relations.py, the established harness pattern reused from
test_battle_plans.py and test_battle_roles.py.
"""

from .test_battle_plans import _deep_space_point, _spawn_fleet

SEED = 20260728

BOARDER_TIER = 8

BOARDER_SLOTS = [
    {"cell_number": 1, "component": "Long Hump 6", "count": 1},
    # The hull's ONE general purpose mount is the whole of its
    # armament - it takes ships rather than killing them
    {"cell_number": 2, "component": "Laser", "count": 1},
    {"cell_number": 3, "component": "Marine Barracks", "count": 1},
    {"cell_number": 4, "component": "Marine Barracks", "count": 1},
    {"cell_number": 5, "component": "Marine Barracks", "count": 1},
    {"cell_number": 6, "component": "Marine Barracks", "count": 1},
]


def _grant_tech(harness, empire_id):
    """Research the boarding line the hull and marines need."""
    from backend.core.data_structures.tech_level import TechLevel
    from backend.services.game_manager import get_game_manager

    manager = get_game_manager()
    server_data = manager._load_game_state(harness.game_id)
    empire = server_data.all_empires[empire_id]
    empire.research_levels = TechLevel.from_values(20, 20, 20, 20, 20, 20)
    manager._save_game_state(harness.game_id, server_data)


def _design_named(harness, empire_id, name):
    for design in harness.state(empire_id).get("designs", []):
        if design["name"] == name:
            return design
    return None


# An armed prize with no shields: a Frigate with a gun and nothing in
# its shield-or-armour slot. Shields are the airlock, so a design that
# never fitted any can be boarded the moment a boarder is alongside
PRIZE_SLOTS = [
    {"cell_number": 10, "component": "Long Hump 6", "count": 1},
    {"cell_number": 12, "component": "Laser", "count": 1},
]


def _boarding_engagement(harness):
    """One-turn deep-space battle: a fitted boarder against a picket
    that never fitted a shield generator. Shields are the airlock, so
    an unshielded design can be boarded the moment the marines are
    alongside - which is the fight a boarding hull is built for."""
    harness.create_game(seed=SEED, size="tiny", players=2)
    px, py = _deep_space_point(harness)

    _grant_tech(harness, 1)
    _grant_tech(harness, 2)
    assert harness.submit(1, "design", {"mode": "Add", "design": {
        "name": "Grapnel", "hull": "Assault Transport",
        "slots": BOARDER_SLOTS}})["status"] == "applied"

    assert harness.submit(1, "battle_plan", {"mode": "set", "plan": {
        "name": "Take Her", "tactic": "Maximise Damage",
        "attack": "Everyone", "board": "When Able",
        "primary_target": 5, "secondary_target": 5, "tertiary_target": 5,
        "quaternary_target": 5, "quinary_target": 5,
    }})["status"] == "applied"

    assert harness.submit(2, "design", {"mode": "Add", "design": {
        "name": "Cutter", "hull": "Frigate",
        "slots": PRIZE_SLOTS}})["status"] == "applied"

    harness.generate_turn()

    _spawn_fleet(harness, 1, "Grapnel", "Boarding Party", px, py,
                 quantity=3, battle_plan="Take Her")
    _spawn_fleet(harness, 2, "Cutter", "Picket", px, py,
                 quantity=6, parked=True)

    harness.generate_turn()
    reports = harness._request(
        "GET", f"/api/games/{harness.game_id}/empires/1/battles")
    assert reports, "no battle report for empire 1"
    return reports[0]


class TestBoardingShipDesign:

    def test_a_designed_boarder_is_buildable_and_classified(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2)
        _grant_tech(harness, 1)
        assert harness.submit(1, "design", {"mode": "Add", "design": {
            "name": "Grapnel", "hull": "Assault Transport",
            "slots": BOARDER_SLOTS}})["status"] == "applied"
        harness.generate_turn()

        design = _design_named(harness, 1, "Grapnel")
        assert design is not None, "the boarder was not registered"
        # The role cascade files it as its own class, so a target-class
        # order can hunt or screen against it
        assert design["battle_role"] == "Boarding Ship"

    def test_marines_cannot_be_fitted_without_the_research(self, harness):
        """The gear sits behind the tech tree like every component."""
        harness.create_game(seed=SEED, size="tiny", players=2)
        result = harness.submit(1, "design", {"mode": "Add", "design": {
            "name": "Premature", "hull": "Assault Transport",
            "slots": BOARDER_SLOTS}})
        assert "error" in result


class TestBoardingInBattle:

    def test_a_boarding_order_produces_a_boarding_action(self, harness):
        report = _boarding_engagement(harness)
        boards = [s for s in report["steps"] if s["type"] == "Board"]
        assert boards, "the boarder never attempted a capture"
        # One party per stack, whatever the outcome
        assert len(boards) == 1
        step = boards[0]
        assert 0.05 <= step["chance"] <= 0.85
        assert step["design_name"]

    def test_the_outcome_is_paid_for(self, harness):
        """Success takes a battered prize; failure cripples the
        boarder. Seeded, so exactly one of the two is asserted."""
        report = _boarding_engagement(harness)
        step = [s for s in report["steps"] if s["type"] == "Board"][0]
        fleets = harness.my_fleets(1)

        if step["success"]:
            prizes = [f for f in fleets if f["name"].startswith("Prize")]
            assert prizes, "a successful boarding produced no prize fleet"
            token = prizes[0]["tokens"][0]
            assert token["quantity"] == 1
            assert token["damage_percent"] == 50.0
            captured = _design_named(harness, 1, step["design_name"]
                                     + " (captured)")
            assert captured is not None
            assert captured["obsolete"] is True
            # The prize survives the next turn as an ordinary fleet
            harness.generate_turn()
            assert [f for f in harness.my_fleets(1)
                    if f["name"].startswith("Prize")]
        else:
            boarder = [f for f in fleets if f["name"] == "Boarding Party"]
            # Either crippled or destroyed outright - both are the
            # documented price of a failed attempt
            if boarder:
                damage = max(t.get("damage_percent", 0.0)
                             for t in boarder[0]["tokens"])
                assert damage >= 50.0

    def test_a_plan_that_never_boards_produces_no_action(self, harness):
        """The default. A commander who never opens the battle screen
        never gambles a crew."""
        harness.create_game(seed=SEED, size="tiny", players=2)
        px, py = _deep_space_point(harness)
        _grant_tech(harness, 1)
        assert harness.submit(1, "design", {"mode": "Add", "design": {
            "name": "Grapnel", "hull": "Assault Transport",
            "slots": BOARDER_SLOTS}})["status"] == "applied"
        harness.generate_turn()

        _spawn_fleet(harness, 1, "Grapnel", "Boarding Party", px, py,
                     quantity=3)
        _spawn_fleet(harness, 2, "Teamster", "Convoy", px, py,
                     quantity=2, parked=True)
        harness.generate_turn()

        reports = harness._request(
            "GET", f"/api/games/{harness.game_id}/empires/1/battles")
        for report in reports:
            assert not [s for s in report["steps"] if s["type"] == "Board"]
