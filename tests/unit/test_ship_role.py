"""
Unit tests for the battle role cascade and battle-report legibility.

Roles are inferred from a design's own capability aggregates (web-only
extension - the C# reference tests raw booleans inline in
BattleEngine.cs and never names a class), so a player's own designs
classify without a hull table. The replay carries the priority tier
and matched role of every target choice, a withdrawal step, and each
stack's plan name.
"""

import pytest

from backend.core.components.ship_role import (
    CAPITAL_SHIP_POWER_RATING, ShipRole, battle_role_of, infer_battle_role)
from backend.core.components import ShipDesign
from backend.server.battle.battle_plan import (
    BattlePlan, PRIORITY_TIER_LABELS, VICTIMS_LABELS, Victims)
from backend.server.battle.battle_report import BattleReport
from backend.server.battle.battle_step import (
    BattleStepTarget, BattleStepWithdraw)
from backend.server.battle.ron_battle_engine import RonBattleEngine
from backend.server.battle.stack import Stack, StackToken
from backend.services.ship_specs import SimpleDesign, Weapon

from .test_battle_engine import (
    MockEmpire, MockServerData, _make_battle_stack)


def _armed(power):
    """A SimpleDesign whose power_rating lands on `power`."""
    design = SimpleDesign(name="Warship", has_weapons=True)
    design.weapons = [Weapon(power=power // 10, range=3, initiative=5,
                             accuracy=75, group="standardBeam")]
    return design


class TestRoleCascade:
    """Every design falls into exactly one role, deterministically."""

    def test_starbase_outranks_everything(self):
        design = SimpleDesign(name="Base", is_starbase=True,
                              has_weapons=True, can_refuel=True,
                              cargo_capacity=500)
        assert battle_role_of(design) == ShipRole.STARBASE

    def test_bomber_outranks_its_own_weapons(self):
        design = SimpleDesign(name="B-17", is_bomber=True,
                              has_weapons=True)
        assert battle_role_of(design) == ShipRole.BOMBER

    def test_capital_ship_above_the_power_threshold(self):
        design = _armed(CAPITAL_SHIP_POWER_RATING * 2)
        assert design.power_rating > CAPITAL_SHIP_POWER_RATING
        assert battle_role_of(design) == ShipRole.CAPITAL

    def test_escort_at_or_below_the_power_threshold(self):
        design = _armed(100)
        assert design.power_rating <= CAPITAL_SHIP_POWER_RATING
        assert battle_role_of(design) == ShipRole.ESCORT

    def test_fuel_transport_is_logistics(self):
        design = SimpleDesign(name="Tanker", can_refuel=True)
        assert battle_role_of(design) == ShipRole.LOGISTICS

    def test_freighter_is_logistics(self):
        design = SimpleDesign(name="Teamster", cargo_capacity=70)
        assert battle_role_of(design) == ShipRole.LOGISTICS

    def test_coloniser_is_support_not_logistics(self):
        """A colony ship carries a hold, so the colonisation module has
        to outrank the cargo signal."""
        design = SimpleDesign(name="Santa Maria", cargo_capacity=25,
                              can_colonize=True)
        assert battle_role_of(design) == ShipRole.SUPPORT

    def test_repair_hull_is_support_not_logistics(self):
        design = SimpleDesign(name="Tender", cargo_capacity=40,
                              heals_others_percent=10)
        assert battle_role_of(design) == ShipRole.SUPPORT

    def test_scout_is_support(self):
        design = SimpleDesign(name="Long Range Scout", can_scan=True)
        assert battle_role_of(design) == ShipRole.SUPPORT

    def test_bare_unarmed_design_still_gets_a_role(self):
        assert battle_role_of(SimpleDesign(name="Hulk")) == ShipRole.SUPPORT

    def test_every_capability_combination_yields_exactly_one_role(self):
        """The cascade is total and deterministic: 2^6 capability
        combinations, every one classified, every call identical."""
        flags = ("is_starbase", "is_bomber", "has_weapons", "can_refuel",
                 "can_colonize")
        seen = set()
        for mask in range(1 << (len(flags) + 1)):
            kwargs = {name: bool(mask & (1 << i))
                      for i, name in enumerate(flags)}
            kwargs["cargo_capacity"] = 100 * bool(mask & (1 << len(flags)))
            role = infer_battle_role(**kwargs)
            assert isinstance(role, ShipRole)
            assert role == infer_battle_role(**kwargs)
            seen.add(role)
        # Every role except Capital is reachable without a power rating
        assert ShipRole.CAPITAL not in seen
        assert seen == {ShipRole.STARBASE, ShipRole.BOMBER,
                        ShipRole.ESCORT, ShipRole.LOGISTICS,
                        ShipRole.SUPPORT}

    def test_starting_designs_classify_distinctly(self):
        """The shipped starting designs land on the roles a commander
        would name them (backend/services/ship_specs.py)."""
        from backend.services.ship_specs import (
            STARTING_DESIGN_SPECS, _design_from_spec)
        roles = {spec["name"]: battle_role_of(_design_from_spec(spec))
                 for spec in STARTING_DESIGN_SPECS}
        assert roles["Starbase"] == ShipRole.STARBASE
        assert roles["Stalwart Defender"] == ShipRole.ESCORT
        assert roles["Teamster"] == ShipRole.LOGISTICS
        assert roles["Swashbuckler"] == ShipRole.LOGISTICS
        assert roles["Santa Maria"] == ShipRole.SUPPORT
        assert roles["Long Range Scout"] == ShipRole.SUPPORT


class TestRoleOnDesign:
    """The role is exposed on the design so the client can show it."""

    def test_simple_design_exposes_and_serializes_its_role(self):
        design = SimpleDesign(name="Teamster", cargo_capacity=70)
        assert design.battle_role == ShipRole.LOGISTICS
        assert design.to_dict()["battle_role"] == "Logistics"

    def test_full_ship_design_exposes_and_serializes_its_role(self):
        design = ShipDesign(name="Hulk")
        assert design.battle_role == ShipRole.SUPPORT
        assert design.to_dict()["battle_role"] == "Support Ship"

    def test_role_survives_a_simple_design_round_trip(self):
        design = SimpleDesign(name="Tanker", can_refuel=True)
        restored = SimpleDesign.from_dict(design.to_dict())
        assert restored.battle_role == ShipRole.LOGISTICS

    def test_stack_exposes_the_role_of_its_token(self):
        stack = _make_battle_stack(1, 1, 100, 100, has_weapons=False,
                                   is_bomber=True)
        assert stack.battle_role == ShipRole.BOMBER


class TestRoleTargeting:
    """Target tiers name roles, so orders may hunt real classes."""

    def _engine(self):
        server = MockServerData()
        for i in range(2):
            empire = MockEmpire(id=i)
            empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
            server.all_empires[i] = empire
        return RonBattleEngine(server, [])

    def test_logistics_tier_exists_and_is_labelled(self):
        assert int(Victims.LOGISTICS) == 7
        assert VICTIMS_LABELS[Victims.LOGISTICS] == "Logistics"

    def test_support_tier_no_longer_matches_a_freighter(self):
        """The gap this closes: SUPPORT_SHIP used to mean nothing more
        than unarmed, so freighters and scouts were indistinguishable."""
        engine = self._engine()
        freighter = _make_battle_stack(1, 2, 800, 200, has_weapons=False)
        freighter.token.battle_role = ShipRole.LOGISTICS
        scout = _make_battle_stack(1, 3, 800, 300, has_weapons=False)
        scout.token.battle_role = ShipRole.SUPPORT

        assert engine._target_matches_priority(
            int(Victims.LOGISTICS), freighter)
        assert not engine._target_matches_priority(
            int(Victims.SUPPORT_SHIP), freighter)
        assert engine._target_matches_priority(
            int(Victims.SUPPORT_SHIP), scout)
        assert not engine._target_matches_priority(
            int(Victims.LOGISTICS), scout)

    def test_logistics_hunter_ignores_the_escort(self):
        engine = self._engine()
        engine.server_state.all_empires[0].battle_plans["Raider"] = \
            BattlePlan(name="Raider", attack="Everyone",
                       primary_target=int(Victims.LOGISTICS),
                       secondary_target=int(Victims.LOGISTICS),
                       tertiary_target=int(Victims.LOGISTICS),
                       quaternary_target=int(Victims.LOGISTICS),
                       quinary_target=int(Victims.LOGISTICS))

        wolf = _make_battle_stack(0, 1, 200, 200, battle_plan="Raider")
        freighter = _make_battle_stack(1, 2, 800, 200, has_weapons=False)
        freighter.token.battle_role = ShipRole.LOGISTICS
        escort = _make_battle_stack(1, 3, 800, 300, armor=10.0)

        assert engine._select_targets([wolf, freighter, escort]) > 0
        assert wolf.target is freighter
        assert escort not in wolf.target_list

    def test_capital_tier_uses_the_power_threshold(self):
        engine = self._engine()
        heavy = _make_battle_stack(1, 2, 800, 200)
        heavy.token.design.power_rating = CAPITAL_SHIP_POWER_RATING + 1
        light = _make_battle_stack(1, 3, 800, 300)
        light.token.design.power_rating = CAPITAL_SHIP_POWER_RATING

        assert engine._target_matches_priority(
            int(Victims.CAPITAL_SHIP), heavy)
        assert engine._target_matches_priority(int(Victims.ESCORT), light)
        assert not engine._target_matches_priority(
            int(Victims.ESCORT), heavy)


class TestBattleLegibility:
    """The replay explains itself."""

    def test_target_step_carries_priority_tier_and_role(self):
        assert PRIORITY_TIER_LABELS[7] == "Primary"
        assert PRIORITY_TIER_LABELS[3] == "Quinary"

        step = BattleStepTarget()
        step.stack_key = 1
        step.target_key = 2
        step.priority = 7
        step.target_role = ShipRole.LOGISTICS
        data = step.to_dict()
        assert data["priority"] == 7
        assert data["target_role"] == "Logistics"
        assert BattleStepTarget.from_dict(data).priority == 7
        assert BattleStepTarget.from_dict(data).target_role == "Logistics"

    def test_withdrawal_is_its_own_step(self):
        step = BattleStepWithdraw()
        step.stack_key = 5
        assert step.to_dict() == {"type": "Withdraw", "stack_key": 5}

        report = BattleReport.from_dict(
            {"steps": [step.to_dict()], "year": 2100})
        assert isinstance(report.steps[0], BattleStepWithdraw)
        assert report.steps[0].stack_key == 5

    def test_stack_report_carries_plan_name_and_role(self):
        stack = _make_battle_stack(1, 1, 100, 100, battle_plan="Raider",
                                   has_weapons=False)
        stack.token.battle_role = ShipRole.LOGISTICS
        data = stack.to_dict()
        assert data["battle_plan"] == "Raider"
        assert data["battle_role"] == "Logistics"
        assert Stack.from_dict(data).battle_role == ShipRole.LOGISTICS

    def test_engine_records_the_tier_that_picked_the_target(self):
        server = MockServerData()
        for i in range(2):
            empire = MockEmpire(id=i)
            empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
            server.all_empires[i] = empire
        server.all_empires[0].battle_plans["Raider"] = BattlePlan(
            name="Raider", attack="Everyone",
            primary_target=int(Victims.LOGISTICS),
            secondary_target=int(Victims.ARMED_SHIP))
        engine = RonBattleEngine(server, [])

        wolf = _make_battle_stack(0, 1, 500, 500, battle_plan="Raider",
                                  weapon_range=3)
        freighter = _make_battle_stack(1, 2, 500, 500, has_weapons=False,
                                       armor=50.0)
        freighter.token.battle_role = ShipRole.LOGISTICS

        battle = BattleReport()
        engine._select_targets([wolf, freighter])
        for attack in engine._generate_attacks([wolf, freighter]):
            engine._process_attack(attack, battle)

        targets = [s for s in battle.steps if s.step_type == "Target"]
        assert targets, "no target step recorded"
        assert targets[0].priority == 7
        assert targets[0].target_role == ShipRole.LOGISTICS

    def test_engine_records_a_withdrawal_step(self):
        server = MockServerData()
        for i in range(2):
            empire = MockEmpire(id=i)
            empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
            server.all_empires[i] = empire
        server.all_empires[1].battle_plans["Runner"] = BattlePlan(
            name="Runner", attack="Everyone", tactic="Disengage")
        engine = RonBattleEngine(server, [])

        wolf = _make_battle_stack(0, 1, 200, 200)
        runner = _make_battle_stack(1, 2, 800, 200, battle_plan="Runner")

        battle = BattleReport()
        engine._select_targets([wolf, runner])
        for battle_round in range(5, 5 + RonBattleEngine.DISENGAGE_MOVES):
            engine._move_stacks([wolf, runner], battle_round, battle)

        assert runner.disengaged
        withdrawals = [s for s in battle.steps if s.step_type == "Withdraw"]
        assert len(withdrawals) == 1
        assert withdrawals[0].stack_key == runner.key


class TestSaveCompatibility:
    """Saved games written before the role cascade still load."""

    def test_legacy_target_step_without_priority(self):
        step = BattleStepTarget.from_dict(
            {"type": "Target", "stack_key": 1, "target_key": 2,
             "percent_to_fire": 50})
        assert step.priority == 0
        assert step.target_role == ""

    def test_legacy_report_stack_without_role(self):
        stack = Stack.from_dict({
            "key": 1, "owner": 1, "parent_key": 0, "name": "Stack #1",
            "battle_plan": "Default",
            "position": {"x": 100, "y": 100},
            "token": {"key": 1, "design_key": 1, "design_name": "Teamster",
                      "quantity": 1, "shields": 0.0, "armor": 100.0,
                      "mass": 60},
            "cargo": {},
        })
        # No cached role and no design aboard: the cascade still names
        # one from the token's own flags
        assert stack.battle_role == ShipRole.SUPPORT

    def test_legacy_simple_design_without_role(self):
        design = SimpleDesign.from_dict(
            {"key": "0x1", "name": "Teamster", "cargo_capacity": 70})
        assert design.battle_role == ShipRole.LOGISTICS

    def test_legacy_battle_plan_without_logistics_tier(self):
        plan = BattlePlan.from_dict(
            {"name": "Old", "primary_target": 0, "quinary_target": 6})
        assert plan.quinary_target == int(Victims.SUPPORT_SHIP)
