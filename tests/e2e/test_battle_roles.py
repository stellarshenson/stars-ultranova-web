"""
Seeded e2e: target classes and battle legibility.

Roles are inferred from each design's own capabilities
(backend/core/components/ship_role.py), so a battle plan can name a
real class to hunt. A raider whose five tiers are all Logistics
destroys the convoy's freighter and never engages its escort - and the
replay says why: every targeting entry carries the tier that matched
and the role it matched, a withdrawal is its own step, and each stack
in the report names its role and the plan it fought under.

Fleets are placed by state surgery and parked with the waypoint stack
from test_relations.py, the established harness pattern reused from
test_battle_plans.py.
"""

from .test_battle_plans import (
    _deep_space_point, _fleet_named, _spawn_fleet)

SEED = 20260728

FIVE_TIERS = ("primary_target", "secondary_target", "tertiary_target",
              "quaternary_target", "quinary_target")

LOGISTICS_TIER = 7


def _raider_battle(harness, raider_plan, freighter_tactic="Maximise Damage"):
    """One-turn deep-space battle: 2x raider vs freighter + escort.

    `raider_plan` is a plan dict for empire 1 (None keeps Default).
    Returns the empire-1 battle report."""
    harness.create_game(seed=SEED, size="tiny", players=2)
    px, py = _deep_space_point(harness)

    plan_name = "Default"
    if raider_plan is not None:
        assert harness.submit(1, "battle_plan", {
            "mode": "set", "plan": raider_plan})["status"] == "applied"
        plan_name = raider_plan["name"]

    assert harness.submit(2, "battle_plan", {"mode": "set", "plan": {
        "name": "Runner", "tactic": freighter_tactic,
        "attack": "Enemies"}})["status"] == "applied"

    _spawn_fleet(harness, 1, "Stalwart Defender", "Raider", px, py,
                 quantity=2, battle_plan=plan_name)
    _spawn_fleet(harness, 2, "Teamster", "Convoy", px, py,
                 battle_plan="Runner", parked=True)
    _spawn_fleet(harness, 2, "Stalwart Defender", "Escort Wing", px, py,
                 parked=True)

    harness.generate_turn()
    reports = harness._request(
        "GET", f"/api/games/{harness.game_id}/empires/1/battles")
    assert reports, "no battle report for empire 1"
    return reports[0]


class TestTargetClasses:

    def test_logistics_hunter_kills_the_freighter_and_spares_the_escort(
            self, harness):
        """The discriminating outcome: the freighter (Logistics) dies
        while the escort (Escort) is never engaged, because no tier of
        the raider's plan matches its role."""
        plan = dict({tier: LOGISTICS_TIER for tier in FIVE_TIERS},
                    name="Commerce Raid", tactic="Maximise Damage",
                    attack="Everyone")
        report = _raider_battle(harness, plan)

        assert _fleet_named(harness, "Convoy", 2) is None, \
            "the freighter survived a plan that hunts logistics"
        assert _fleet_named(harness, "Escort Wing", 2) is not None, \
            "the escort was engaged by a logistics-only plan"

        # Every shot the raider called was at the freighter's class
        raider_targets = [s for s in report["steps"]
                          if s["type"] == "Target"
                          and (s["stack_key"] >> 32) == 1]
        assert raider_targets, "the raider never picked a target"
        assert all(s["target_role"] == "Logistics" for s in raider_targets)
        assert all(s["priority"] == 7 for s in raider_targets)

    def test_default_plan_engages_the_escort(self, harness):
        """Control, same seed and fleets: on the Default plan (which
        carries an Any Ship tier) the raiders do shoot the escort."""
        report = _raider_battle(harness, None)

        raider_targets = [s for s in report["steps"]
                          if s["type"] == "Target"
                          and (s["stack_key"] >> 32) == 1]
        assert any(s["target_role"] == "Escort" for s in raider_targets), \
            "the default plan never engaged the escort"


class TestBattleLegibility:

    def test_report_stacks_name_their_role_and_plan(self, harness):
        report = _raider_battle(harness, None)
        by_role = {s["battle_role"]: s for s in report["stacks"].values()}
        assert "Logistics" in by_role, "freighter not filed as logistics"
        assert "Escort" in by_role, "warship not filed as an escort"
        assert by_role["Logistics"]["battle_plan"] == "Runner"

    def test_withdrawal_is_recorded_as_its_own_step(self, harness):
        """A disengaging freighter leaves the board, and the replay
        says so instead of showing movement that silently stops."""
        report = _raider_battle(harness, None,
                                freighter_tactic="Disengage")

        withdrawals = [s for s in report["steps"]
                       if s["type"] == "Withdraw"]
        assert withdrawals, "no withdrawal step recorded"
        convoy = [key for key, stack in report["stacks"].items()
                  if stack["battle_role"] == "Logistics"]
        assert convoy, "no logistics stack in the report"
        assert str(withdrawals[0]["stack_key"]) in convoy
        assert _fleet_named(harness, "Convoy", 2) is not None
