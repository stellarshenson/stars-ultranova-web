"""
Tests for player relations (Enemy/Neutral/Friend).

C# model: per-opponent EmpireIntel.Relation in EmpireData.EmpireReports
(EmpireData.cs:89), default Enemy (enum member 0, EmpireData.cs:34-39),
initialized for every wolf/lamb pair at game creation
(GameInitialiser.cs:132-143). Consumers: battle targeting
(BattleEngine.cs:468-494), invasion legality (InvadeTask.cs:110-131),
bombing (Bombing.cs:59-64 via EmpireData.IsEnemy). Minefield strikes,
sweeping and friendly-starbase docking follow canonical Stars! rules
(absent or stubbed in the C# reference).
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

import pytest

from backend.core.commands.relation import RelationCommand
from backend.core.data_structures import EmpireData, NovaPoint
from backend.core.data_structures.cargo import Cargo
from backend.core.game_objects.fleet import Fleet, ShipToken
from backend.core.globals import NOBODY
from backend.server.server_data import ServerData, Minefield
from backend.server.turn_generator import TurnGenerator
from backend.server.turn_steps import BombingStep, PostBombingStep
from backend.services.galaxy_generator import GalaxyGenerator
from backend.services.game_manager import COMMAND_TYPES


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

@dataclass
class MockStar:
    """Minimal star for relation-gated consumers."""
    name: str = "Target"
    owner: int = NOBODY
    colonists: int = 0
    defenses: int = 0
    defense_type: str = "None"
    factories: int = 0
    mines: int = 0
    starbase_key: Optional[int] = None
    manufacturing_queue: Optional[object] = None
    this_race: Optional[object] = None


def make_empire(empire_id: int, race_name: str = "") -> EmpireData:
    empire = EmpireData(id=empire_id)
    empire.race_name = race_name
    return empire


def set_relation(empire: EmpireData, other_id: int, relation: str):
    empire.empire_reports.setdefault(other_id, {})["relation"] = relation


def make_fleet(key: int, owner: int, x: float = 100, y: float = 100,
               quantity: int = 1, armor: int = 100) -> Fleet:
    """Minimal real fleet with one token (as in test_mine_sweeping)."""
    fleet = Fleet(name=f"Fleet #{key}", position=NovaPoint(x, y))
    fleet._key = (owner << 32) | key
    fleet.owner_int = owner
    fleet.owner = owner
    fleet.tokens[1] = ShipToken(
        design_key=1, design_name="Testship", quantity=quantity,
        mass=10, armor=armor, fuel_capacity=500,
    )
    fleet.fuel_available = 100
    return fleet


# --------------------------------------------------------------------------
# RelationCommand
# --------------------------------------------------------------------------

class TestRelationCommand:
    """Web transport for the PlayerRelations dialog edit
    (PlayerRelations.cs:104-120; no C# server command exists)."""

    def _empire(self) -> EmpireData:
        empire = make_empire(1)
        empire.empire_reports[2] = {"id": 2, "race_name": "Foes",
                                    "relation": "Enemy", "designs": {}}
        return empire

    def test_invalid_relation_rejected(self):
        empire = self._empire()
        command = RelationCommand(target_empire_id=2, relation="Ally")
        valid, message = command.is_valid(empire)
        assert valid is False
        assert "not a valid player relation" in message.text

    def test_unknown_target_rejected(self):
        empire = self._empire()
        command = RelationCommand(target_empire_id=9, relation="Friend")
        valid, message = command.is_valid(empire)
        assert valid is False
        assert "Unknown empire 9" in message.text

    def test_self_target_rejected(self):
        empire = self._empire()
        empire.empire_reports[1] = {"relation": "Enemy"}
        command = RelationCommand(target_empire_id=1, relation="Friend")
        valid, message = command.is_valid(empire)
        assert valid is False
        assert "Unknown empire 1" in message.text

    def test_no_change_is_benign_noop(self):
        empire = self._empire()
        command = RelationCommand(target_empire_id=2, relation="Enemy")
        valid, message = command.is_valid(empire)
        assert valid is False
        assert message is None

    def test_apply_sets_relation(self):
        empire = self._empire()
        command = RelationCommand(target_empire_id=2, relation="Friend")
        valid, message = command.is_valid(empire)
        assert valid is True and message is None
        assert command.apply_to_state(empire) is None
        assert empire.empire_reports[2]["relation"] == "Friend"

    def test_dict_round_trip(self):
        command = RelationCommand(target_empire_id=3, relation="Neutral")
        data = command.to_dict()
        assert data["type"] == "Relation"
        restored = RelationCommand.from_dict(data)
        assert restored.target_empire_id == 3
        assert restored.relation == "Neutral"

    def test_registered_command_type(self):
        assert COMMAND_TYPES["relation"] is RelationCommand


# --------------------------------------------------------------------------
# Initial relations (GameInitialiser.cs:132-143)
# --------------------------------------------------------------------------

class TestInitialRelations:

    def test_every_pair_starts_enemy(self):
        server = GalaxyGenerator(seed=42).generate(
            player_count=3, universe_size="tiny")
        for wolf in server.all_empires.values():
            others = [e for e in server.all_empires.values()
                      if e.id != wolf.id]
            assert set(wolf.empire_reports.keys()) == \
                {e.id for e in others}
            for lamb in others:
                report = wolf.empire_reports[lamb.id]
                assert report["relation"] == "Enemy"
                assert report["race_name"] == lamb.race_name

    def test_default_battle_plan_attacks_enemies(self):
        """Attack="Enemies" (BattlePlan.cs:44) so relations govern
        battle eligibility; all-Enemy init keeps fresh games hostile."""
        server = GalaxyGenerator(seed=42).generate(
            player_count=2, universe_size="tiny")
        for empire in server.all_empires.values():
            assert empire.battle_plans["Default"].attack == "Enemies"


# --------------------------------------------------------------------------
# Bombing gate (Bombing.cs:59-64 via EmpireData.cs IsEnemy :173-176)
# --------------------------------------------------------------------------

class TestBombingRelationGate:

    def _bomb_run(self, relation: Optional[str]) -> int:
        """Bomber of empire 1 over empire 2's colony; returns the
        surviving colonists."""
        from backend.core.components.ship_design import Bomb

        @dataclass
        class BomberDesign:
            key: int = 1
            conventional_bombs: object = None
            smart_bombs: object = None

        @dataclass
        class BomberFleet:
            key: int = 1
            name: str = "Bomber"
            owner: int = 1
            in_orbit: object = None
            has_bombers: bool = True
            is_starbase: bool = False
            tokens: Dict[int, object] = field(default_factory=dict)

        @dataclass
        class BomberToken:
            quantity: int = 2
            design_key: int = 1

        data = ServerData()
        star = MockStar(name="Target", owner=2, colonists=100000)
        data.all_stars = {"Target": star}

        empire1 = make_empire(1)
        empire1.designs[1] = BomberDesign(
            conventional_bombs=Bomb(pop_kill=2.5, installations=10,
                                    minimum_kill=300, is_smart=False),
            smart_bombs=Bomb(is_smart=True),
        )
        if relation is not None:
            set_relation(empire1, 2, relation)
        fleet = BomberFleet(in_orbit=star, tokens={1: BomberToken()})
        empire1.owned_fleets = {1: fleet}

        data.all_empires = {1: empire1, 2: make_empire(2)}
        BombingStep().process(data)
        return star.colonists

    def test_friend_not_bombed(self):
        assert self._bomb_run("Friend") == 100000

    def test_neutral_not_bombed(self):
        assert self._bomb_run("Neutral") == 100000

    def test_enemy_bombed(self):
        assert self._bomb_run("Enemy") == 95000

    def test_missing_report_defaults_enemy(self):
        assert self._bomb_run(None) == 95000


# --------------------------------------------------------------------------
# Invasion cancel (InvadeTask.cs:110-131)
# --------------------------------------------------------------------------

class TestInvasionRelationCancel:

    def _invade(self, relation: str):
        data = ServerData()
        star = MockStar(name="Held", owner=2, colonists=1000)
        data.all_stars = {"Held": star}

        sender = make_empire(1)
        set_relation(sender, 2, relation)
        sender.empire_reports[2]["race_name"] = "Foes"
        receiver = make_empire(2, race_name="Foes")
        receiver.owned_stars["Held"] = star
        data.all_empires = {1: sender, 2: receiver}

        fleet = make_fleet(1, 1)
        fleet.cargo = Cargo(colonists_in_kilotons=100)  # 10000 troops
        sender.owned_fleets[fleet.key] = fleet

        messages = PostBombingStep()._perform_invasion(
            fleet, star, sender, receiver, data)
        return star, fleet, messages

    @pytest.mark.parametrize("relation", ["Friend", "Neutral"])
    def test_non_enemy_invasion_cancelled(self, relation):
        star, fleet, messages = self._invade(relation)
        assert any("are not our enemies. Order has been cancelled."
                   in m.text for m in messages)
        assert any("Foes" in m.text for m in messages)
        # Cancel precedes the troop commit: colonists stay aboard
        assert fleet.cargo.colonists_in_kilotons == 100
        assert star.owner == 2
        assert star.colonists == 1000

    def test_enemy_invasion_proceeds(self):
        star, fleet, messages = self._invade("Enemy")
        # 10000 troops x 1.1 vs 1000 defenders: attackers take the star
        assert star.owner == 1
        assert fleet.cargo.colonists_in_kilotons == 0


# --------------------------------------------------------------------------
# Minefield strike friend-skip (canonical; CheckForMinefields.cs is a
# stub with no owner/relation check)
# --------------------------------------------------------------------------

class TestMinefieldStrikeFriendSkip:

    def _cross_field(self, field_owner_relation: Optional[str] = None,
                     traveler_relation: Optional[str] = None):
        """Empire 1 fleet crosses empire 2's standard field at warp 9
        (guaranteed hit). Returns (fleet, state)."""
        from backend.core.waypoints.waypoint import Waypoint

        fleet = make_fleet(1, 1, x=200, y=100, quantity=5)
        fleet.waypoints.append(Waypoint(
            position_x=200, position_y=100, warp_factor=9,
            destination="wp"))

        state = ServerData()
        empire1 = make_empire(1)
        empire1.owned_fleets[fleet.key] = fleet
        empire2 = make_empire(2)
        if field_owner_relation is not None:
            set_relation(empire2, 1, field_owner_relation)
        if traveler_relation is not None:
            set_relation(empire1, 2, traveler_relation)
        state.all_empires = {1: empire1, 2: empire2}

        state.all_minefields[1] = Minefield(
            key=1, owner=2, position_x=100, position_y=100,
            number_of_mines=2500, mine_type=0)  # radius 50

        gen = TurnGenerator(state)
        gen.rand.seed(42)
        gen._check_minefield(fleet, 0, 100)
        return fleet, state

    def _hit(self, state) -> bool:
        return any(m.message_type == "Minefield Hit"
                   for m in state.all_messages)

    def test_field_owner_friend_skips_strike(self):
        fleet, state = self._cross_field(field_owner_relation="Friend")
        assert not self._hit(state)
        assert fleet.waypoints[0].warp_factor == 9

    def test_neutral_still_struck(self):
        fleet, state = self._cross_field(field_owner_relation="Neutral")
        assert self._hit(state)

    def test_enemy_still_struck(self):
        fleet, state = self._cross_field(field_owner_relation="Enemy")
        assert self._hit(state)

    def test_direction_is_field_owner_side(self):
        """The traveler declaring Friend does not protect it; only the
        FIELD OWNER's declared relation counts."""
        fleet, state = self._cross_field(traveler_relation="Friend")
        assert self._hit(state)


# --------------------------------------------------------------------------
# Sweep enemy-only (canonical; sweeping absent from the C# reference)
# --------------------------------------------------------------------------

class TestSweepEnemyOnly:

    def _sweep(self, relation: Optional[str]) -> int:
        """Empire 1 beam fleet inside empire 2's field; returns the
        mines left after the sweep pass."""
        from backend.core.components.ship_design import ShipDesign, Weapon

        fleet = make_fleet(1, 1, x=100, y=100)
        state = ServerData()
        empire1 = make_empire(1)
        empire1.owned_fleets[fleet.key] = fleet
        if relation is not None:
            set_relation(empire1, 2, relation)
        design = ShipDesign()
        design.key = 1
        design.weapons = [Weapon(power=10, range=2, group="standardBeam")]
        design._needs_update = False
        empire1.designs[1] = design
        state.all_empires = {1: empire1, 2: make_empire(2)}

        state.all_minefields[1] = Minefield(
            key=1, owner=2, position_x=100, position_y=100,
            number_of_mines=1000, mine_type=0)
        TurnGenerator(state)._sweep_minefields()
        return state.all_minefields[1].number_of_mines

    def test_friend_field_not_swept(self):
        assert self._sweep("Friend") == 1000

    def test_neutral_field_not_swept(self):
        assert self._sweep("Neutral") == 1000

    def test_enemy_field_swept(self):
        assert self._sweep("Enemy") == 960  # 10 x 2^2 = 40 swept

    def test_default_relation_sweeps(self):
        assert self._sweep(None) == 960


# --------------------------------------------------------------------------
# Refuel/repair at friendly starbases (canonical; C# RegenerateFleet
# only checks own planets, TurnGenerator.cs:308-379)
# --------------------------------------------------------------------------

class TestFriendlyStarbaseDocking:

    def _dock(self, relation: Optional[str]):
        """Empire 1 fleet parked at empire 2's starbase world.
        Returns (fleet, generator, star)."""
        star = MockStar(name="Base", owner=2, starbase_key=(2 << 32) | 9)

        state = ServerData()
        state.all_stars = {"Base": star}
        empire1 = make_empire(1)
        empire2 = make_empire(2)
        if relation is not None:
            set_relation(empire2, 1, relation)

        starbase = make_fleet(9, 2, x=100, y=100)
        starbase.tokens[1].is_starbase = True
        starbase.tokens[1].can_refuel = True
        starbase.in_orbit_name = "Base"
        empire2.owned_fleets[starbase.key] = starbase

        fleet = make_fleet(1, 1, x=100, y=100)
        fleet.in_orbit_name = "Base"
        fleet.tokens[1].damage_percent = 50
        empire1.owned_fleets[fleet.key] = fleet

        state.all_empires = {1: empire1, 2: empire2}
        gen = TurnGenerator(state)
        gen._regenerate_fleet(fleet)
        return fleet, gen, star

    def test_friend_base_refuels_and_repairs_at_dock_rate(self):
        fleet, gen, star = self._dock("Friend")
        assert fleet.fuel_available == fleet.total_fuel_capacity
        # Dock rate 20%/yr: 50 - 20 = 30
        assert fleet.tokens[1].damage_percent == pytest.approx(30.0)

    def test_neutral_base_does_not_refuel(self):
        fleet, gen, star = self._dock("Neutral")
        assert fleet.fuel_available == 100
        # Foreign orbit rate 3%/yr: 50 - 3 = 47
        assert fleet.tokens[1].damage_percent == pytest.approx(47.0)

    def test_enemy_base_does_not_refuel(self):
        fleet, gen, star = self._dock("Enemy")
        assert fleet.fuel_available == 100
        assert fleet.tokens[1].damage_percent == pytest.approx(47.0)


# --------------------------------------------------------------------------
# Player state exposure and command flow (GameManager)
# --------------------------------------------------------------------------

class TestPlayerStateRelations:

    def test_relations_exposed_and_command_applied(self, tmp_path):
        from backend.services.game_manager import GameManager

        manager = GameManager(str(tmp_path / "test.db"))
        game = manager.create_game("t", 2, "tiny", seed=99)
        game_id = game["id"]

        state = manager.get_player_state(game_id, 1)
        assert len(state["relations"]) == 1
        entry = state["relations"][0]
        assert entry["id"] == 2
        assert entry["relation"] == "Enemy"
        assert entry["race_name"]

        result = manager.submit_command(
            game_id, 1, "relation",
            {"target_empire_id": 2, "relation": "Friend"})
        assert result["status"] == "applied"
        state = manager.get_player_state(game_id, 1)
        assert state["relations"][0]["relation"] == "Friend"

        # The other side keeps its own (unchanged) relation
        state2 = manager.get_player_state(game_id, 2)
        assert state2["relations"][0]["relation"] == "Enemy"

    def test_invalid_relation_rejected(self, tmp_path):
        from backend.services.game_manager import GameManager

        manager = GameManager(str(tmp_path / "test.db"))
        game = manager.create_game("t", 2, "tiny", seed=99)
        result = manager.submit_command(
            game["id"], 1, "relation",
            {"target_empire_id": 2, "relation": "Ally"})
        assert "not a valid player relation" in result["error"]
