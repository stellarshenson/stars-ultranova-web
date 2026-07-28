"""
Tests for fleet battle doctrine.

The doctrine lives on the battle plan itself - there is no separate
doctrine object. Six admiralty standard plans ship in every empire's
list, an empire-wide default is inherited by newly built fleets, and
each plan carries three axes on top of the canonical target tiers and
tactic: stance, posture and a withdrawal threshold.

Canonical Stars! tactics carry no stat modifiers at all
(docs/research-battle-doctrine.md section 1), so the tactic stays the
positional layer and stance is the only statistical one. Its modifiers
are deliberately asymmetric - initiative front-loads fire, accuracy is
missile-only, the shield multiplier never touches armour - and its
sharpest cost is that Aggressive forfeits disengagement entirely.
"""

import pytest

from backend.core.data_structures import NovaPoint
from backend.core.game_objects import Fleet, ShipToken
from backend.server.battle import BattleReport, RonBattleEngine
from backend.server.battle.battle_plan import (
    ADMIRALTY_PLANS,
    DEFAULT_EMPIRE_PLAN,
    MIN_DISENGAGE_MOVES,
    POSTURES,
    POSTURE_MODIFIERS,
    STANCES,
    STANCE_MODIFIERS,
    WITHDRAWAL_DAMAGE_PERCENT,
    WITHDRAW_OPTIONS,
    BattlePlan,
    seed_admiralty_plans,
)

from .test_battle_engine import (
    MockDesign, MockEmpire, MockServerData, MockWeapon, _make_battle_stack)


def _doctrine_setup(plan, stacks_owner_one=None):
    """Two empires; empire 1 fights under `plan`, empire 0 under stock."""
    server = MockServerData()
    for i in range(2):
        empire = MockEmpire(id=i)
        empire.battle_plans["Default"] = BattlePlan(attack="Everyone")
        server.all_empires[i] = empire
    plan.attack = "Everyone"
    server.all_empires[1].battle_plans[plan.name] = plan
    return server, RonBattleEngine(server, [])


# =============================================================================
# Admiralty standard plans
# =============================================================================

class TestAdmiraltyPlans:

    def test_six_standard_plans_exist(self):
        assert sorted(ADMIRALTY_PLANS) == sorted([
            "Aggressive Assault", "Balanced", "Defensive Hold",
            "Commerce Raid", "Escort Screen", "Fighting Retreat"])
        for name, plan in ADMIRALTY_PLANS.items():
            assert plan.name == name
            assert plan.stance in STANCES
            assert plan.posture in POSTURES
            assert plan.withdraw in WITHDRAW_OPTIONS

    def test_standard_plan_parameters(self):
        """The doctrine axes each standard plan commits to. The tactic
        column is the engagement-range order each plan carries
        (docs/research-engagement-range.md, panel-refined shape on the
        existing tactic field)."""
        expected = {
            "Aggressive Assault": ("Maximise Damage",
                                   "Aggressive", "Standard", "Never"),
            "Balanced": ("Salvo then Close",
                         "Balanced", "Standard", "Never"),
            "Defensive Hold": ("Maximise Damage Ratio",
                               "Defensive", "Brace", "Half Armour"),
            "Commerce Raid": ("Salvo then Close",
                              "Balanced", "Scatter", "Outnumbered"),
            "Escort Screen": ("Maximise Damage Ratio",
                              "Defensive", "Standard", "Never"),
            "Fighting Retreat": ("Minimise Damage to Self",
                                 "Defensive", "Scatter", "On Damage"),
        }
        for name, (tactic, stance, posture, withdraw) in expected.items():
            plan = ADMIRALTY_PLANS[name]
            assert (plan.tactic, plan.stance, plan.posture,
                    plan.withdraw) == (tactic, stance, posture, withdraw)

    def test_balanced_matches_the_legacy_default_plan(self):
        """A remapped empire hunts the same things: Balanced keeps the
        legacy Default targeting tiers, attack and no-modifier axes.
        Its TACTIC deliberately differs - Salvo then Close is the
        engagement-range doctrine (docs/research-engagement-range.md),
        where legacy Default always closed to contact."""
        legacy = BattlePlan(attack="Enemies")
        balanced = ADMIRALTY_PLANS["Balanced"]
        for field in ("primary_target", "secondary_target",
                      "tertiary_target", "quaternary_target",
                      "quinary_target", "attack"):
            assert getattr(balanced, field) == getattr(legacy, field)
        assert balanced.stance_modifiers == STANCE_MODIFIERS["Balanced"]
        assert balanced.posture_modifiers == POSTURE_MODIFIERS["Standard"]
        assert legacy.tactic == "Maximise Damage"
        assert balanced.tactic == "Salvo then Close"

    def test_seeding_is_idempotent_and_never_overwrites(self):
        plans = {"Balanced": BattlePlan(name="Balanced", tactic="Disengage")}
        seed_admiralty_plans(plans)
        seed_admiralty_plans(plans)
        assert len(plans) == len(ADMIRALTY_PLANS)
        # The commander's edit under a standard name survives seeding
        assert plans["Balanced"].tactic == "Disengage"
        # Seeded copies are independent of the module-level templates
        plans["Commerce Raid"].tactic = "Disengage"
        assert ADMIRALTY_PLANS["Commerce Raid"].tactic == "Salvo then Close"


# =============================================================================
# Stance
# =============================================================================

class TestStanceModifiers:

    def test_modifier_table(self):
        aggressive = STANCE_MODIFIERS["Aggressive"]
        balanced = STANCE_MODIFIERS["Balanced"]
        defensive = STANCE_MODIFIERS["Defensive"]

        assert (aggressive.initiative, aggressive.missile_accuracy,
                aggressive.shields, aggressive.may_disengage) == (
                    2, 1.10, 0.80, False)
        assert (balanced.initiative, balanced.missile_accuracy,
                balanced.shields, balanced.may_disengage,
                balanced.disengage_moves) == (0, 1.0, 1.0, True, 7)
        assert (defensive.initiative, defensive.missile_accuracy,
                defensive.shields, defensive.may_disengage,
                defensive.disengage_moves) == (-2, 0.90, 1.25, True, 5)

    def test_shield_pool_scaled_at_battle_start_armour_untouched(self):
        for stance, factor in (("Aggressive", 0.80), ("Balanced", 1.0),
                               ("Defensive", 1.25)):
            plan = BattlePlan(name="P", stance=stance)
            server, engine = _doctrine_setup(plan)
            stack = _make_battle_stack(1, 1, 200, 200, armor=200.0,
                                       shields=100.0, battle_plan="P")
            engine._apply_doctrine([stack])
            assert stack.token.shields == pytest.approx(100.0 * factor)
            assert stack.token.armor == 200.0

    def test_aggressive_forfeits_disengagement(self):
        """The sharpest cost of the stance: an Aggressive plan cannot
        run, even when its tactic says Disengage outright."""
        plan = BattlePlan(name="P", tactic="Disengage", stance="Aggressive")
        server, engine = _doctrine_setup(plan)
        wolf = _make_battle_stack(0, 1, 200, 200)
        runner = _make_battle_stack(1, 2, 600, 200, battle_plan="P")
        battle = BattleReport()

        assert engine._effective_tactic(runner) == "Maximise Damage"
        engine._select_targets([wolf, runner])
        engine._move_stacks([wolf, runner], 5, battle)
        assert runner.flee_rounds == 0
        assert runner.position.x < 600  # closed instead of fleeing

    def test_defensive_leaves_the_board_two_moves_sooner(self):
        plan = BattlePlan(name="P", tactic="Disengage", stance="Defensive")
        server, engine = _doctrine_setup(plan)
        wolf = _make_battle_stack(0, 1, 200, 200)
        runner = _make_battle_stack(1, 2, 600, 200, battle_plan="P")
        stacks = [wolf, runner]
        battle = BattleReport()

        assert engine._disengage_moves_required(runner) == 5
        for battle_round in range(5, 10):
            engine._select_targets(stacks)
            engine._move_stacks(stacks, battle_round, battle)
        assert runner.flee_rounds == 5
        assert runner.disengaged is True

    def test_initiative_shifts_firing_order(self):
        """A stack killed before it fires contributes nothing, so
        firing order is not a symmetric damage multiplier."""
        plan = BattlePlan(name="P", stance="Aggressive")
        server, engine = _doctrine_setup(plan)
        slow = _make_battle_stack(0, 1, 200, 200, weapon_range=9)
        fast = _make_battle_stack(1, 2, 300, 200, weapon_range=9,
                                  battle_plan="P")
        # Identical weapons: only the stance separates them
        engine._select_targets([slow, fast])
        attacks = engine._generate_attacks([slow, fast])

        assert [a.source_stack.owner for a in attacks] == [1, 0]
        assert attacks[0].initiative_bonus == 2
        assert attacks[1].initiative_bonus == 0

    def test_missile_accuracy_scaled_by_stance(self):
        for stance, factor in (("Aggressive", 1.10), ("Balanced", 1.0),
                               ("Defensive", 0.90)):
            plan = BattlePlan(name="P", stance=stance)
            server, engine = _doctrine_setup(plan)
            attacker = _make_battle_stack(1, 1, 200, 200, battle_plan="P")
            target = _make_battle_stack(0, 2, 200, 200, shields=0.0,
                                        armor=1000.0)
            attacker.token.design.weapons = [
                MockWeapon(group="torpedo", power=100, range=5,
                           accuracy=50)]
            engine._select_targets([attacker, target])
            attacks = [a for a
                       in engine._generate_attacks([attacker, target])
                       if a.source_stack is attacker]
            assert attacks

            seen = {}
            original = engine._fire_missile

            def capture(a, t, power, accuracy, b):
                seen["accuracy"] = accuracy
                return original(a, t, power, accuracy, b)

            engine._fire_missile = capture
            engine._execute_attack(attacks[0], BattleReport())
            assert seen["accuracy"] == pytest.approx(0.5 * factor)


# =============================================================================
# Postures
# =============================================================================

class TestPostures:

    def test_brace_holds_position(self):
        plan = BattlePlan(name="P", posture="Brace")
        server, engine = _doctrine_setup(plan)
        wolf = _make_battle_stack(0, 1, 200, 200)
        bracer = _make_battle_stack(1, 2, 600, 200, battle_plan="P")
        stacks = [wolf, bracer]
        battle = BattleReport()

        for battle_round in range(1, 10):
            engine._select_targets(stacks)
            engine._move_stacks(stacks, battle_round, battle)

        assert (bracer.position.x, bracer.position.y) == (600, 200)
        assert bracer.flee_rounds == 0
        assert bracer.disengaged is False

    def test_brace_pays_for_its_survivability_in_gunnery(self):
        """Brace fires deliberately, not aggressively.

        Holding position turned out to cost almost nothing once the
        engine stopped overshooting (DEF-30): an emplaced line fights
        concentrated in one square while a manoeuvring force disperses
        and arrives piecemeal, so Brace won every matchup in the
        anti-degeneracy round-robin. The price is charged in the same
        currency Scatter already pays - the posture's own hit power.
        """
        assert POSTURE_MODIFIERS["Brace"].damage_dealt == 0.80

        plan = BattlePlan(name="P", posture="Brace")
        server, engine = _doctrine_setup(plan)
        bracer = _make_battle_stack(1, 1, 200, 200, battle_plan="P")
        victim = _make_battle_stack(0, 2, 200, 200, armor=100000.0)
        engine._select_targets([bracer, victim])

        battle = BattleReport()
        before = victim.token.armor
        for attack in engine._generate_attacks([bracer, victim]):
            engine._process_attack(attack, battle)
        braced_damage = before - victim.token.armor

        plan.posture = "Standard"
        victim.token.armor = before
        engine._select_targets([bracer, victim])
        for attack in engine._generate_attacks([bracer, victim]):
            engine._process_attack(attack, battle)
        standard_damage = before - victim.token.armor

        assert braced_damage == pytest.approx(standard_damage * 0.80)

    def test_brace_does_not_pin_the_unarmed_hulls(self):
        """Brace fixes a FIRING position, and an unarmed hull has none.

        The order is "hold the line", not "park the freighters in the
        open": canonically an unarmed ship keeps out of weapon range
        (BATTLE.TXT gives new unarmed fleets Default-Defense, whose
        "initial behavior is to try to avoid combat entirely"). Pinning
        them made Brace the worst posture in the anti-degeneracy matrix
        by a distance, because a third of every task force sat still to
        be shot (DEF-31).
        """
        plan = BattlePlan(name="P", posture="Brace")
        server, engine = _doctrine_setup(plan)
        wolf = _make_battle_stack(0, 1, 200, 200)
        freighter = _make_battle_stack(1, 2, 600, 200, has_weapons=False,
                                       battle_plan="P")
        stacks = [wolf, freighter]
        battle = BattleReport()

        for battle_round in range(5, 10):
            engine._select_targets(stacks)
            engine._move_stacks(stacks, battle_round, battle)

        assert freighter.position.x > 600, \
            "a braced fleet's freighters must still run from the guns"

    def test_brace_raises_shields(self):
        plan = BattlePlan(name="P", posture="Brace")
        server, engine = _doctrine_setup(plan)
        stack = _make_battle_stack(1, 1, 200, 200, shields=100.0,
                                   battle_plan="P")
        engine._apply_doctrine([stack])
        assert stack.token.shields == pytest.approx(130.0)

    def test_brace_fires_a_square_further(self):
        """A braced stack fights from a fixed emplacement, so it gets
        the range bonus canonical Stars! gives a starbase. It is the
        other half of what the posture buys - the half that makes
        never closing survivable."""
        plan = BattlePlan(name="P", posture="Brace")
        server, engine = _doctrine_setup(plan)
        # Two squares apart, weapons reaching one square
        bracer = _make_battle_stack(1, 1, 200, 200, weapon_range=1,
                                    battle_plan="P")
        target = _make_battle_stack(0, 2, 400, 200, armor=1000.0)

        engine._select_targets([bracer, target])
        assert [a for a in engine._generate_attacks([bracer, target])
                if a.source_stack is bracer]

        plan.posture = "Standard"
        assert not [a for a in engine._generate_attacks([bracer, target])
                    if a.source_stack is bracer]

    def test_scatter_cuts_its_own_damage(self):
        plan = BattlePlan(name="P", posture="Scatter")
        server, engine = _doctrine_setup(plan)
        attacker = _make_battle_stack(1, 1, 200, 200, battle_plan="P")

        def one_volley(target):
            engine._select_targets([attacker, target])
            attacks = [a for a
                       in engine._generate_attacks([attacker, target])
                       if a.source_stack is attacker]
            assert attacks
            engine._execute_attack(attacks[0], BattleReport())
            return 1000.0 - target.token.armor

        scattered = one_volley(
            _make_battle_stack(0, 2, 200, 200, armor=1000.0))
        plan.posture = "Standard"
        standard = one_volley(
            _make_battle_stack(0, 3, 200, 200, armor=1000.0))

        assert standard > 0
        assert scattered == pytest.approx(standard * 0.85)

    def test_scatter_is_harder_to_hit_with_missiles_only(self):
        """A spread-out formation is harder to guide a torpedo into
        and does nothing at all against beams, so the enemy's weapon
        class decides what the posture is worth."""
        plan = BattlePlan(name="P", posture="Scatter")
        server, engine = _doctrine_setup(plan)
        attacker = _make_battle_stack(0, 1, 200, 200)
        attacker.token.design.weapons = [
            MockWeapon(group="torpedo", power=100, range=5, accuracy=50)]
        scattered = _make_battle_stack(1, 2, 200, 200, shields=0.0,
                                       armor=1000.0, battle_plan="P")

        seen = []
        original = engine._fire_missile

        def capture(a, t, power, accuracy, b):
            seen.append(accuracy)
            return original(a, t, power, accuracy, b)

        engine._fire_missile = capture

        def one_volley():
            engine._select_targets([attacker, scattered])
            attacks = [a for a
                       in engine._generate_attacks([attacker, scattered])
                       if a.source_stack is attacker]
            assert attacks
            engine._execute_attack(attacks[0], BattleReport())

        one_volley()
        plan.posture = "Standard"
        one_volley()

        assert seen[0] == pytest.approx(seen[1] * 0.85)

    def test_scatter_halves_missile_splash_taken(self):
        plan = BattlePlan(name="P", posture="Scatter")
        server, engine = _doctrine_setup(plan)
        attacker = _make_battle_stack(0, 1, 200, 200)
        scattered = _make_battle_stack(1, 2, 200, 200, shields=1000.0,
                                       battle_plan="P")
        battle = BattleReport()

        # accuracy 0 makes every point of damage splash
        engine._fire_missile(attacker, scattered, 800.0, 0.0, battle)
        splash_scattered = 1000.0 - scattered.token.shields

        scattered.battle_plan = "Default"
        scattered.token.shields = 1000.0
        engine._fire_missile(attacker, scattered, 800.0, 0.0, battle)
        splash_standard = 1000.0 - scattered.token.shields

        assert splash_scattered == pytest.approx(splash_standard * 0.5)

    def test_scatter_shortens_the_disengage(self):
        plan = BattlePlan(name="P", posture="Scatter")
        server, engine = _doctrine_setup(plan)
        runner = _make_battle_stack(1, 1, 600, 200, battle_plan="P")
        assert engine._disengage_moves_required(runner) == 5

        plan.stance = "Defensive"  # 5 - 2 = 3, at the floor
        assert engine._disengage_moves_required(runner) == MIN_DISENGAGE_MOVES


# =============================================================================
# Withdrawal
# =============================================================================

class TestWithdrawalThresholds:

    def test_never_is_the_default(self):
        plan = BattlePlan(name="P")
        assert plan.withdraw == "Never"
        server, engine = _doctrine_setup(plan)
        stack = _make_battle_stack(1, 1, 200, 200, battle_plan="P")
        stack.damage_taken = True
        stack.token.armor = 1.0
        assert engine._withdraw_threshold_met(stack) is False

    def test_on_damage(self):
        plan = BattlePlan(name="P", withdraw="On Damage")
        server, engine = _doctrine_setup(plan)
        stack = _make_battle_stack(1, 1, 200, 200, battle_plan="P")
        assert engine._withdraw_threshold_met(stack) is False
        stack.damage_taken = True
        assert engine._withdraw_threshold_met(stack) is True

    def test_half_armour(self):
        plan = BattlePlan(name="P", withdraw="Half Armour")
        server, engine = _doctrine_setup(plan)
        stack = _make_battle_stack(1, 1, 200, 200, armor=200.0,
                                   battle_plan="P")
        stack.token.armor = 101.0
        assert engine._withdraw_threshold_met(stack) is False
        stack.token.armor = 100.0
        assert engine._withdraw_threshold_met(stack) is True

    def test_outnumbered(self):
        plan = BattlePlan(name="P", withdraw="Outnumbered")
        server, engine = _doctrine_setup(plan)
        lone = _make_battle_stack(1, 1, 600, 200, battle_plan="P")
        pack = _make_battle_stack(0, 2, 200, 200, quantity=2)
        engine._apply_doctrine([lone, pack])
        assert lone.outnumbered is True
        assert pack.outnumbered is False
        assert engine._withdraw_threshold_met(lone) is True

    def test_threshold_turns_any_tactic_into_disengage(self):
        plan = BattlePlan(name="P", tactic="Maximise Damage",
                          withdraw="On Damage")
        server, engine = _doctrine_setup(plan)
        wolf = _make_battle_stack(0, 1, 200, 200)
        runner = _make_battle_stack(1, 2, 600, 200, battle_plan="P")
        stacks = [wolf, runner]
        battle = BattleReport()

        engine._select_targets(stacks)
        engine._move_stacks(stacks, 5, battle)
        assert runner.flee_rounds == 0  # undamaged: still fighting

        engine._damage_armor(wolf, runner, 10.0, battle)
        x_before = runner.position.x
        engine._select_targets(stacks)
        engine._move_stacks(stacks, 6, battle)
        assert runner.position.x > x_before
        assert runner.flee_rounds == 1


class TestWithdrawalConsequences:
    """A withdrawal used to be a battle-local flag: the fleet stopped
    firing and sailed on to fight again next turn for free."""

    def _fleet_with_orders(self, empire, position):
        from backend.core.waypoints.waypoint import Waypoint

        fleet = Fleet()
        fleet.key = empire.get_next_fleet_key()
        fleet.owner = empire.id
        fleet.name = "Runner"
        fleet.position = NovaPoint(position, 200)
        fleet.tokens[1] = ShipToken(design_key=1, quantity=2, armor=50)
        fleet.waypoints = [
            Waypoint(position_x=position, position_y=200, warp_factor=0),
            Waypoint(position_x=900, position_y=200, warp_factor=6),
        ]
        empire.owned_fleets[fleet.key] = fleet
        return fleet

    def _withdrawn(self):
        plan = BattlePlan(name="P", tactic="Disengage")
        server, engine = _doctrine_setup(plan)
        server.all_messages = []
        fleet = self._fleet_with_orders(server.all_empires[1], 600)

        stack = _make_battle_stack(1, 1, 600, 200, battle_plan="P")
        stack.parent_key = fleet.key
        stack.disengaged = True

        battle = BattleReport()
        battle.location = "deep space (1, 1)"
        engine._apply_withdrawal_consequences([stack], battle)
        return server, fleet

    def test_orders_are_cancelled_and_ships_damaged(self):
        server, fleet = self._withdrawn()

        assert fleet.withdrawn_year == server.turn_year
        # Waypoint zero is the fleet's own position and is kept
        assert len(fleet.waypoints) == 1
        for token in fleet.tokens.values():
            assert token.damage_percent == WITHDRAWAL_DAMAGE_PERCENT

    def test_the_player_is_told(self):
        server, fleet = self._withdrawn()
        assert len(server.all_messages) == 1
        message = server.all_messages[0]
        assert message.audience == 1
        assert message.message_type == "Battle"
        assert "withdrew" in message.text
        assert message.fleet_key == fleet.key

    def test_a_fleet_that_stayed_pays_nothing(self):
        plan = BattlePlan(name="P")
        server, engine = _doctrine_setup(plan)
        server.all_messages = []
        fleet = self._fleet_with_orders(server.all_empires[1], 600)
        stack = _make_battle_stack(1, 1, 600, 200, battle_plan="P")
        stack.parent_key = fleet.key

        engine._apply_withdrawal_consequences([stack], BattleReport())

        assert fleet.withdrawn_year == -1
        assert len(fleet.waypoints) == 2
        assert server.all_messages == []


class TestBattleDamageCarriesOut:
    """Armour lost in a battle used to be discarded: the engine wrote
    back destruction alone, so a fleet shot to one armour point was
    whole again next turn and no order that traded damage for position
    could ever be worth giving."""

    def _damaged(self, remaining, already=0.0):
        plan = BattlePlan(name="P")
        server, engine = _doctrine_setup(plan)
        empire = server.all_empires[1]

        fleet = Fleet()
        fleet.key = empire.get_next_fleet_key()
        fleet.owner = empire.id
        fleet.name = "Survivor"
        fleet.position = NovaPoint(600, 200)
        fleet.tokens[1] = ShipToken(design_key=1, quantity=2, armor=50,
                                    damage_percent=already)
        empire.owned_fleets[fleet.key] = fleet

        stack = _make_battle_stack(1, 1, 600, 200, armor=200.0,
                                   battle_plan="P")
        stack.token.design_key = 1
        stack.parent_key = fleet.key
        stack.token.armor = 200.0 * remaining

        engine._write_back_damage([stack])
        return fleet.tokens[1]

    def test_lost_armour_lands_on_the_fleet_token(self):
        assert self._damaged(0.4).damage_percent == pytest.approx(60.0)

    def test_an_untouched_survivor_is_left_alone(self):
        assert self._damaged(1.0).damage_percent == 0.0

    def test_damage_compounds_with_what_the_token_carried(self):
        # Half of the armour that was left, on a token already at 50%
        assert self._damaged(0.5, already=50.0).damage_percent == \
            pytest.approx(75.0)

    def test_a_wreck_is_capped_short_of_total(self):
        assert self._damaged(0.0).damage_percent == pytest.approx(99.0)

    def test_a_destroyed_stack_writes_nothing_back(self):
        plan = BattlePlan(name="P")
        server, engine = _doctrine_setup(plan)
        stack = _make_battle_stack(1, 1, 600, 200, battle_plan="P")
        stack.token = None
        engine._write_back_damage([stack])  # no fleet, no crash


# =============================================================================
# Save compatibility
# =============================================================================

class TestSaveCompatibility:

    def test_plan_without_doctrine_keys_loads_with_no_modifiers(self):
        legacy = {
            "name": "Old", "primary_target": 0, "secondary_target": 1,
            "tertiary_target": 3, "quaternary_target": 5,
            "quinary_target": 6, "tactic": "Maximise Damage",
            "attack": "Enemies", "target_id": 0,
        }
        plan = BattlePlan.from_dict(legacy)
        assert (plan.stance, plan.posture, plan.withdraw) == (
            "Balanced", "Standard", "Never")
        assert plan.stance_modifiers == STANCE_MODIFIERS["Balanced"]
        assert plan.posture_modifiers == POSTURE_MODIFIERS["Standard"]

    def test_plan_round_trip_keeps_the_doctrine_axes(self):
        plan = BattlePlan(name="P", stance="Defensive", posture="Scatter",
                          withdraw="Outnumbered")
        restored = BattlePlan.from_dict(plan.to_dict())
        assert (restored.stance, restored.posture, restored.withdraw) == (
            "Defensive", "Scatter", "Outnumbered")

    def test_fleet_without_withdrawn_year_loads(self):
        fleet = Fleet()
        fleet.key = 1
        data = fleet.to_dict()
        del data["withdrawn_year"]
        assert Fleet.from_dict(data).withdrawn_year == -1

    def test_fleet_round_trip_keeps_withdrawn_year(self):
        fleet = Fleet()
        fleet.key = 1
        fleet.withdrawn_year = 2412
        assert Fleet.from_dict(fleet.to_dict()).withdrawn_year == 2412

    def test_unknown_stance_or_posture_is_inert(self):
        """A plan naming an axis value this build does not know must
        never change the fight."""
        plan = BattlePlan(name="P", stance="Berserk", posture="Wedge")
        assert plan.stance_modifiers == STANCE_MODIFIERS["Balanced"]
        assert plan.posture_modifiers == POSTURE_MODIFIERS["Standard"]

    def test_default_empire_plan_is_a_standard_plan(self):
        assert DEFAULT_EMPIRE_PLAN in ADMIRALTY_PLANS


# =============================================================================
# Empire default plan
# =============================================================================

class TestEmpireDefaultPlan:

    def _star_update_step(self):
        from backend.server.turn_steps.star_update_step import StarUpdateStep
        return StarUpdateStep()

    def test_production_assigns_the_empire_default(self):
        empire = MockEmpire(id=1)
        seed_admiralty_plans(empire.battle_plans)
        empire.default_battle_plan = "Commerce Raid"
        step = self._star_update_step()
        assert step._default_battle_plan(empire) == "Commerce Raid"

    def test_unknown_default_falls_back_to_the_legacy_plan(self):
        empire = MockEmpire(id=1)
        empire.battle_plans["Default"] = BattlePlan()
        empire.default_battle_plan = "Deleted Plan"
        step = self._star_update_step()
        assert step._default_battle_plan(empire) == "Default"

    def test_missing_attribute_falls_back_to_the_legacy_plan(self):
        """An empire deserialized from a save written before the
        empire default existed."""
        empire = MockEmpire(id=1)
        empire.battle_plans["Default"] = BattlePlan()
        step = self._star_update_step()
        assert step._default_battle_plan(empire) == "Default"


# =============================================================================
# Legacy save migration (DEF-36)
# =============================================================================

class TestLegacySaveDoctrineMigration:
    """DEF-36: a save written before the doctrine wave bypassed it -
    seed_admiralty_plans only adds missing plans, and the empire
    default 'Default' (tactic Maximise Damage) made every fleet in a
    loaded game close to contact regardless of the doctrine layer.
    Loading now seeds the missing admiralty plans and remaps a
    'Default' empire default to the admiralty default, without
    clobbering a commander's own plans."""

    def _reload(self, tmp_path, mutate):
        import backend.services.game_manager as gm_module
        from backend.services.game_manager import GameManager

        gm_module._game_manager = None
        try:
            manager = GameManager(str(tmp_path / "migrate.db"))
            game = manager.create_game("Doctrine Migrate", 2, "small",
                                       seed=424242)
            server_data = manager._load_game_state(game["id"])
            state_dict = manager._serialize_state(server_data)
            mutate(state_dict)
            return manager._deserialize_state(state_dict)
        finally:
            gm_module._game_manager = None

    def test_legacy_default_remaps_and_missing_plans_seed(self, tmp_path):
        def mutate(state_dict):
            for empire in state_dict["all_empires"].values():
                # A pre-doctrine save: only the legacy Default plan,
                # empire default "Default"
                empire["battle_plans"] = {
                    "Default": BattlePlan(attack="Enemies").to_dict()}
                empire["default_battle_plan"] = "Default"

        restored = self._reload(tmp_path, mutate)
        for empire in restored.all_empires.values():
            for name in ADMIRALTY_PLANS:
                assert name in empire.battle_plans
            assert empire.default_battle_plan == DEFAULT_EMPIRE_PLAN
            # The legacy plan itself survives untouched for fleets
            # that still reference it by name
            assert empire.battle_plans["Default"].tactic == \
                "Maximise Damage"

    def test_customised_plans_and_named_defaults_survive(self, tmp_path):
        def mutate(state_dict):
            for empire in state_dict["all_empires"].values():
                # A commander's own edits under two standard names,
                # and an explicitly chosen empire default
                empire["battle_plans"] = {
                    "Default": BattlePlan(attack="Enemies").to_dict(),
                    "Balanced": BattlePlan(
                        name="Balanced", tactic="Disengage").to_dict(),
                    "Escort Screen": BattlePlan(
                        name="Escort Screen", posture="Brace").to_dict(),
                }
                empire["default_battle_plan"] = "Escort Screen"

        restored = self._reload(tmp_path, mutate)
        for empire in restored.all_empires.values():
            # Seeding never overwrites a plan the commander edited
            # under a standard name
            assert empire.battle_plans["Balanced"].tactic == "Disengage"
            assert empire.battle_plans["Escort Screen"].posture == "Brace"
            # A named default that is not "Default" is honoured
            assert empire.default_battle_plan == "Escort Screen"
            # The other admiralty plans still seed in
            assert "Commerce Raid" in empire.battle_plans
