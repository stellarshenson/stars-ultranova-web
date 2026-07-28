"""
Seeded e2e: imminent battle warning and engagement override.

Combat resolves inside turn generation with no player input during the
fight, so the pre-generation window is the last moment a commander
still has. This walks the whole loop through the real API: a hostile
fleet is scanned, the warning names the fleet that is about to meet
it, the commander switches that fleet to a different plan for that
battle only, the battle is fought under the override, and the fleet
reverts to its standing plan afterwards.

Fleets are placed by state surgery with the parking waypoint stack
from test_battle_plans.py.
"""

from .test_battle_plans import _fleet_named, _spawn_fleet

SEED = 20260728


def _set_course(harness, empire_id, fleet_key, x, y, warp=4):
    """Order a fleet to (x, y) by state surgery.

    Two waypoints keep the default AI's hands off the fleet, the same
    reason _spawn_fleet parks with two.
    """
    from backend.core.waypoints.waypoint import Waypoint, NoTaskObj
    from backend.services.game_manager import get_game_manager

    manager = get_game_manager()
    server_data = manager._load_game_state(harness.game_id)
    fleet = server_data.all_empires[empire_id].owned_fleets[fleet_key]
    fleet.waypoints = [
        Waypoint(position_x=fleet.position.x, position_y=fleet.position.y,
                 warp_factor=warp, destination="here", task=NoTaskObj()),
        Waypoint(position_x=x, position_y=y, warp_factor=warp,
                 destination="intercept", task=NoTaskObj()),
    ]
    manager._save_game_state(harness.game_id, server_data)


def _battlefield(harness):
    """A deep-space point a short hop from empire 1's homeworld, so the
    planetary scanner sees anything parked there."""
    home = harness.my_stars(1)[0]
    return home["position_x"] + 3.5, home["position_y"] + 0.5


def _set_engagement_plan(harness, empire_id, fleet_key, plan):
    return harness._request(
        "POST",
        f"/api/games/{harness.game_id}/fleets/{fleet_key}/battle-plan",
        {"empire_id": empire_id, "plan": plan, "engagement": True})


def _standoff(harness):
    """Empire 2 blockades a point empire 1 can see but has not reached."""
    harness.create_game(seed=SEED, size="tiny", players=2)
    px, py = _battlefield(harness)

    _spawn_fleet(harness, 2, "Stalwart Defender", "Blockade", px, py,
                 quantity=2, parked=True)
    home = harness.my_stars(1)[0]
    guard = _spawn_fleet(harness, 1, "Stalwart Defender", "Vanguard",
                         home["position_x"], home["position_y"],
                         quantity=2, battle_plan="Balanced", parked=True)

    # One turn so the scanners report the blockade
    harness.generate_turn()
    return guard, px, py


class TestImminentBattleWarning:

    def test_a_parked_fleet_out_of_contact_is_not_warned_about(self,
                                                              harness):
        guard, px, py = _standoff(harness)
        state = harness.state(1)
        assert any(f["owner"] == 2 for f in state["foreign_fleets"]), \
            "empire 1 never scanned the blockade"
        assert state["imminent_battles"] == []

    def test_a_fleet_sailing_into_hostiles_is_named(self, harness):
        guard, px, py = _standoff(harness)
        _set_course(harness, 1, guard, px, py)

        warnings = harness.state(1)["imminent_battles"]
        assert len(warnings) == 1
        entry = warnings[0]
        assert entry["fleet_key"] == guard
        assert entry["fleet_name"] == "Vanguard"
        assert entry["arriving"] is True
        assert entry["battle_plan"] == "Balanced"
        assert entry["engagement_plan"] == ""
        assert entry["hostile_ships"] == 2
        assert entry["hostiles"][0]["owner"] == 2

    def test_the_warning_is_right_the_battle_happens(self, harness):
        guard, px, py = _standoff(harness)
        _set_course(harness, 1, guard, px, py)
        assert harness.state(1)["imminent_battles"]

        harness.generate_turn()
        reports = harness._request(
            "GET", f"/api/games/{harness.game_id}/empires/1/battles")
        assert reports, "the warning promised a battle that never came"


class TestEngagementOverride:

    def test_the_battle_is_fought_under_the_override_and_reverts(
            self, harness):
        guard, px, py = _standoff(harness)
        _set_course(harness, 1, guard, px, py)

        result = _set_engagement_plan(harness, 1, guard, "Defensive Hold")
        assert result["battle_plan"] == "Balanced"
        assert result["engagement_plan"] == "Defensive Hold"

        fleet = _fleet_named(harness, "Vanguard", 1)
        assert fleet["battle_plan"] == "Balanced"
        assert fleet["engagement_plan"] == "Defensive Hold"
        assert harness.state(1)["imminent_battles"][0]["engagement_plan"] \
            == "Defensive Hold"

        harness.generate_turn()

        reports = harness._request(
            "GET", f"/api/games/{harness.game_id}/empires/1/battles")
        assert reports, "no battle report"
        mine = [s for s in reports[0]["stacks"].values()
                if (s["key"] >> 32) == 1]
        assert mine, "empire 1 did not appear in the battle"
        assert all(s["battle_plan"] == "Defensive Hold" for s in mine)

        # Reverted: the standing plan is untouched and the override is
        # gone, whatever the battle did
        survivor = _fleet_named(harness, "Vanguard", 1)
        if survivor is not None:
            assert survivor["battle_plan"] == "Balanced"
            assert survivor["engagement_plan"] == ""

    def test_an_override_never_survives_a_turn_without_a_battle(self,
                                                               harness):
        """The revert is unconditional: a fleet that never met anyone
        still starts the next turn on its standing plan."""
        guard, px, py = _standoff(harness)
        assert _set_engagement_plan(harness, 1, guard, "Aggressive Assault")[
            "engagement_plan"] == "Aggressive Assault"

        harness.generate_turn()

        fleet = _fleet_named(harness, "Vanguard", 1)
        assert fleet["battle_plan"] == "Balanced"
        assert fleet["engagement_plan"] == ""

    def test_an_override_can_be_cancelled(self, harness):
        guard, px, py = _standoff(harness)
        _set_engagement_plan(harness, 1, guard, "Fighting Retreat")
        assert _set_engagement_plan(harness, 1, guard, "")[
            "engagement_plan"] == ""
        assert _fleet_named(harness, "Vanguard", 1)["engagement_plan"] == ""

    def test_an_unknown_plan_is_rejected(self, harness):
        guard, px, py = _standoff(harness)
        response = harness.client.post(
            f"/api/games/{harness.game_id}/fleets/{guard}/battle-plan",
            json={"empire_id": 1, "plan": "Ghost Doctrine",
                  "engagement": True})
        assert response.status_code == 400
        assert _fleet_named(harness, "Vanguard", 1)["engagement_plan"] == ""
