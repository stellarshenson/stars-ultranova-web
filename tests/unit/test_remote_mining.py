"""
Tests for remote mining: mining-rate aggregation, the RemoteMineTask
waypoint task, the RemoteMineStep turn step (uninhabited-only rule,
extraction, concentration depletion), hauling from uninhabited stars,
and race-restriction gating of the miner hulls.

No C# equivalent for the executable mechanics - remote mining is a
stub in the reference; canonical Stars! rules apply. The depletion
formula mirrors planetary mining (Star.cs:443-476).
"""

import os
import tempfile

import pytest

from backend.core.data_structures import EmpireData
from backend.core.data_structures.tech_level import TechLevel
from backend.core.game_objects.fleet import Fleet, ShipToken
from backend.core.game_objects.star import Star
from backend.core.globals import NOBODY
from backend.core.race.race import Race
from backend.core.waypoints.waypoint import (
    Waypoint, WaypointTask, WaypointTaskBase, RemoteMineTaskObj,
    get_task_type,
)
from backend.server.server_data import ServerData
from backend.server.turn_steps import RemoteMineStep
from backend.services.design_builder import (
    build_ship_design, ensure_components_loaded
)
from backend.services.ship_specs import SimpleDesign, make_token


def _make_empire(empire_id=1, prt="JOAT", lrts=(), tech=26):
    """Empire with a race and flat tech levels for design building."""
    empire = EmpireData(id=empire_id)
    empire.race = Race(name="Testers", primary_trait=prt, traits=set(lrts))
    empire.research_levels = TechLevel.from_level(tech)
    return empire


def _mini_miner_design(empire, robots=1):
    """Mini Miner: QJ5 engine (cell 11), Robo-Midget Miners in the
    two Robot Miner slots (cells 7 and 17)."""
    slots = [{"cell_number": 11, "component": "Quick Jump 5", "count": 1}]
    if robots >= 1:
        slots.append({"cell_number": 7, "component": "Robo-Midget Miner",
                      "count": 1})
    if robots >= 2:
        slots.append({"cell_number": 17, "component": "Robo-Midget Miner",
                      "count": 1})
    return build_ship_design(empire, "Test Miner", "Mini Miner", slots)


class TestMiningRateAggregation:
    """ShipDesign sums the Mining Robot property across slots."""

    def test_mini_miner_two_midget_robots(self):
        ensure_components_loaded()
        empire = _make_empire()
        design, error = _mini_miner_design(empire, robots=2)
        assert error is None
        # 2 x Robo-Midget Miner (Value 5) = 10 kT/mineral/year at 100%
        assert design.mining_rate == 10

    def test_midget_miner_hull_stacked_robots(self):
        ensure_components_loaded()
        empire = _make_empire(lrts={"ARM"})  # Midget Miner is ARM-only
        design, error = build_ship_design(
            empire, "Rock Chewer", "Midget Miner", [
                {"cell_number": 11, "component": "Quick Jump 5", "count": 1},
                {"cell_number": 12, "component": "Robo-Midget Miner",
                 "count": 2},
            ])
        assert error is None
        assert design.mining_rate == 10

    def test_design_without_robots_mines_nothing(self):
        ensure_components_loaded()
        empire = _make_empire()
        design, error = _mini_miner_design(empire, robots=0)
        assert error is None
        assert design.mining_rate == 0

    def test_orbital_adjuster_contributes_zero(self):
        """The Orbital Adjuster shares the MiningRobot item type but
        has no Mining Robot property - it must not add mining rate."""
        ensure_components_loaded()
        empire = _make_empire(prt="CA")  # Orbital Adjuster is CA-only
        design, error = build_ship_design(
            empire, "Adjuster", "Mini Miner", [
                {"cell_number": 11, "component": "Quick Jump 5", "count": 1},
                {"cell_number": 7, "component": "Orbital Adjuster",
                 "count": 1},
            ])
        assert error is None
        assert design.mining_rate == 0


class TestTokenAndFleetAggregation:
    """make_token caches mining_rate; fleets multiply by quantity."""

    def test_make_token_caches_mining_rate(self):
        design = SimpleDesign(key=1, name="Digger", mining_rate=10)
        token = make_token(design, quantity=3)
        assert token.mining_rate == 10

    def test_fleet_total_mining_rate(self):
        fleet = Fleet()
        fleet.tokens[1] = ShipToken(design_key=1, quantity=3, mining_rate=10)
        fleet.tokens[2] = ShipToken(design_key=2, quantity=2, mining_rate=0)
        assert fleet.total_mining_rate == 30

    def test_ship_token_round_trip(self):
        token = ShipToken(design_key=1, quantity=2, mining_rate=25)
        restored = ShipToken.from_dict(token.to_dict())
        assert restored.mining_rate == 25

    def test_simple_design_round_trip(self):
        design = SimpleDesign(key=1, name="Digger", mining_rate=12)
        restored = SimpleDesign.from_dict(design.to_dict())
        assert restored.mining_rate == 12


class TestRemoteMineTask:
    """Waypoint task enum, object, and serialization."""

    def test_task_object(self):
        task = RemoteMineTaskObj()
        assert task.name == "RemoteMineTask"
        assert task.task_type == WaypointTask.REMOTE_MINE
        assert get_task_type(task) == WaypointTask.REMOTE_MINE

    def test_round_trip(self):
        task = RemoteMineTaskObj()
        assert task.to_dict() == {"type": "RemoteMineTask"}
        restored = WaypointTaskBase.from_dict(task.to_dict())
        assert restored.task_type == WaypointTask.REMOTE_MINE

    def test_client_short_name_parses(self):
        restored = WaypointTaskBase.from_dict({"type": "RemoteMine"})
        assert restored.task_type == WaypointTask.REMOTE_MINE


def _mining_setup(rate=100, concentrations=(80, 50, 1)):
    """ServerData with one uninhabited star and one miner fleet in
    orbit with a Remote Mine waypoint-0 task."""
    server_data = ServerData()

    star = Star()
    star.name = "Kirk"
    star.owner = NOBODY
    star.colonists = 0
    star.mineral_concentration.ironium = concentrations[0]
    star.mineral_concentration.boranium = concentrations[1]
    star.mineral_concentration.germanium = concentrations[2]
    server_data.all_stars[star.name] = star

    empire = EmpireData(id=1)
    server_data.all_empires[1] = empire

    fleet = Fleet()
    fleet.key = empire.get_next_fleet_key()
    fleet.name = "Digger #1"
    fleet.owner = 1
    fleet.in_orbit_name = star.name
    fleet.tokens[1] = ShipToken(design_key=1, quantity=1, mining_rate=rate)
    fleet.waypoints.append(Waypoint(
        destination=star.name, task=RemoteMineTaskObj()))
    empire.owned_fleets[fleet.key] = fleet

    return server_data, star, fleet


class TestRemoteMineStep:
    """The turn step extracts, deposits on the surface, depletes."""

    def test_extracts_and_deposits_on_surface(self):
        server_data, star, fleet = _mining_setup(rate=100)
        messages = RemoteMineStep().process(server_data)

        # mined = int(rate * concentration / 100)
        assert star.resources_on_hand.ironium == 80
        assert star.resources_on_hand.boranium == 50
        assert star.resources_on_hand.germanium == 1
        # Nothing goes into fleet cargo
        assert fleet.cargo.mass == 0
        # Small hauls do not visibly deplete: 80*80//12500 == 0
        assert star.mineral_concentration.ironium == 80
        assert star.mineral_concentration.boranium == 50
        assert star.mineral_concentration.germanium == 1

        mining = [m for m in messages if m.message_type == "Remote Mining"]
        assert len(mining) == 1
        assert mining[0].audience == 1
        assert "131 kT" in mining[0].text  # 80 + 50 + 1

    def test_large_rate_depletes_concentration(self):
        server_data, star, _ = _mining_setup(rate=3000)
        RemoteMineStep().process(server_data)
        # ironium: mined 2400, depletion 2400*80//12500 = 15 -> 65
        assert star.resources_on_hand.ironium == 2400
        assert star.mineral_concentration.ironium == 65

    def test_depletion_clamps_at_one(self):
        server_data, star, _ = _mining_setup(
            rate=1_000_000, concentrations=(100, 100, 100))
        RemoteMineStep().process(server_data)
        assert star.mineral_concentration.ironium == 1
        assert star.mineral_concentration.boranium == 1
        assert star.mineral_concentration.germanium == 1

    def test_mines_every_turn_it_stays(self):
        server_data, star, _ = _mining_setup(rate=100)
        RemoteMineStep().process(server_data)
        RemoteMineStep().process(server_data)
        assert star.resources_on_hand.ironium == 160

    def test_refuses_inhabited_star(self):
        server_data, star, _ = _mining_setup(rate=100)
        star.owner = 2
        star.colonists = 10000
        messages = RemoteMineStep().process(server_data)

        assert star.resources_on_hand.ironium == 0
        assert star.mineral_concentration.ironium == 80
        assert any("inhabited" in m.text for m in messages)

    def test_refuses_own_colony(self):
        server_data, star, _ = _mining_setup(rate=100)
        star.owner = 1
        star.colonists = 10000
        messages = RemoteMineStep().process(server_data)
        assert star.resources_on_hand.ironium == 0
        assert any("inhabited" in m.text for m in messages)

    def test_deep_space_produces_warning(self):
        server_data, star, fleet = _mining_setup(rate=100)
        fleet.in_orbit_name = None
        messages = RemoteMineStep().process(server_data)
        assert star.resources_on_hand.ironium == 0
        assert any("deep space" in m.text for m in messages)

    def test_zero_rate_fleet_is_skipped(self):
        server_data, star, _ = _mining_setup(rate=0)
        messages = RemoteMineStep().process(server_data)
        assert star.resources_on_hand.ironium == 0
        assert messages == []


class TestCargoAtUninhabitedStar:
    """transfer_cargo allows mineral hauling at NOBODY-owned stars."""

    @pytest.fixture
    def game(self):
        import backend.services.game_manager as gm_module
        from backend.services.game_manager import GameManager

        gm_module._game_manager = None
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            manager = GameManager(db_path)
            game = manager.create_game("Remote Mining Test", 2, "small",
                                       seed=424242)
            yield manager, game["id"]
        finally:
            gm_module._game_manager = None
            if os.path.exists(db_path):
                os.unlink(db_path)

    def _park_freighter(self, manager, game_id):
        """Owned freighter in orbit of an uninhabited star with 100 kT
        of remote-mined ironium on the surface."""
        server_data = manager._load_game_state(game_id)
        empire = server_data.all_empires[1]
        star = next(s for s in server_data.all_stars.values()
                    if s.owner == NOBODY)
        star.resources_on_hand.ironium = 100

        fleet = Fleet()
        fleet.key = empire.get_next_fleet_key()
        fleet.name = "Hauler #1"
        fleet.owner = 1
        fleet.position = star.position.copy()
        fleet.in_orbit_name = star.name
        fleet.tokens[1] = ShipToken(design_key=1, quantity=1,
                                    cargo_capacity=70)
        empire.owned_fleets[fleet.key] = fleet
        return star, fleet

    def test_loads_minerals(self, game):
        manager, game_id = game
        star, fleet = self._park_freighter(manager, game_id)
        result = manager.transfer_cargo(game_id, 1, fleet.key,
                                        {"ironium": 20})
        assert result.get("status") == "ok"
        assert fleet.cargo.ironium == 20
        assert star.resources_on_hand.ironium == 80

    def test_rejects_colonists(self, game):
        manager, game_id = game
        _, fleet = self._park_freighter(manager, game_id)
        result = manager.transfer_cargo(game_id, 1, fleet.key,
                                        {"colonists": -100})
        assert "error" in result

    def test_still_rejects_foreign_owned_star(self, game):
        manager, game_id = game
        star, fleet = self._park_freighter(manager, game_id)
        star.owner = 2
        result = manager.transfer_cargo(game_id, 1, fleet.key,
                                        {"ironium": 20})
        assert result.get("error") == "Cannot transfer cargo at a foreign star"


class TestDesignBuilderRaceRestrictions:
    """ARM=2 gates the miner hulls; OBRM=0 blocks the Maxi Miner
    (RaceRestriction.cs:44-49 semantics)."""

    ARM_HULLS = ["Midget Miner", "Miner", "Ultra Miner"]

    def _build_hull(self, empire, hull):
        # Engine slot differs per hull: Midget Miner 11, Miner 10,
        # Ultra Miner 10, Maxi Miner 10, Mini Miner 11
        cell = 11 if hull in ("Midget Miner", "Mini Miner") else 10
        return build_ship_design(empire, f"Test {hull}", hull, [
            {"cell_number": cell, "component": "Quick Jump 5", "count": 1},
        ])

    def test_non_arm_cannot_build_arm_hulls(self):
        ensure_components_loaded()
        empire = _make_empire(prt="JOAT")
        for hull in self.ARM_HULLS:
            design, error = self._build_hull(empire, hull)
            assert design is None
            assert "not available to your race" in error

    def test_arm_can_build_arm_hulls(self):
        ensure_components_loaded()
        empire = _make_empire(prt="JOAT", lrts={"ARM"})
        for hull in self.ARM_HULLS:
            design, error = self._build_hull(empire, hull)
            assert error is None, f"{hull}: {error}"

    def test_obrm_cannot_build_maxi_miner(self):
        ensure_components_loaded()
        empire = _make_empire(prt="JOAT", lrts={"OBRM"})
        design, error = self._build_hull(empire, "Maxi Miner")
        assert design is None
        assert "not available to your race" in error

    def test_non_obrm_can_build_maxi_miner(self):
        ensure_components_loaded()
        empire = _make_empire(prt="JOAT")
        design, error = self._build_hull(empire, "Maxi Miner")
        assert error is None
