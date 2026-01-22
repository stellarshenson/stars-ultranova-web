"""
Tests for turn processing (TurnGenerator and turn steps).
Ported/inspired by tests for TurnGenerator.cs and turn steps.
"""

import pytest
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.server import ServerData, TurnGenerator
from backend.server.server_data import Minefield, PlayerSettings
from backend.server.turn_steps import (
    ITurnStep, FirstStep, ScrapFleetStep, SplitFleetStep,
    BombingStep, PostBombingStep, ScanStep, StarUpdateStep
)
from backend.core.data_structures import EmpireData, Resources, TechLevel, NovaPoint
from backend.core.waypoints.waypoint import (
    Waypoint, WaypointTask, get_task_type,
    NoTaskObj, CargoTaskObj, ColoniseTaskObj, ScrapTaskObj, SplitMergeTaskObj, LayMinesTaskObj
)
from backend.core.globals import STARTING_YEAR, NOBODY


# --------------------------------------------------------------------------
# Mock objects for testing
# --------------------------------------------------------------------------

@dataclass
class MockFleetToken:
    """Mock ship token for fleet composition."""
    quantity: int = 1
    design: Optional[object] = None


@dataclass
class MockDesign:
    """Mock ship design."""
    name: str = "Scout"
    cost: Resources = field(default_factory=lambda: Resources(ironium=10, boranium=5, germanium=3))
    bomb_count: int = 0
    bomb_kill_rate: float = 0.0
    scan_range: int = 100
    pen_scan_range: int = 50


@dataclass
class MockCargo:
    """Mock cargo container."""
    ironium: int = 0
    boranium: int = 0
    germanium: int = 0
    colonists: int = 0


@dataclass
class MockFleet:
    """Mock fleet for testing."""
    key: int = 1
    name: str = "Test Fleet"
    owner: int = 0
    position: NovaPoint = field(default_factory=lambda: NovaPoint(0, 0))
    waypoints: List[Waypoint] = field(default_factory=list)
    composition: Dict[int, MockFleetToken] = field(default_factory=dict)
    cargo: MockCargo = field(default_factory=MockCargo)
    in_orbit: Optional[object] = None
    is_starbase: bool = False
    can_colonize: bool = False
    has_bombers: bool = False
    number_of_mines: int = 0
    number_of_heavy_mines: int = 0
    number_of_speed_bump_mines: int = 0
    turn_year: int = 0  # For salvage decay tracking


@dataclass
class MockResourceStockpile:
    """Mock resource stockpile."""
    ironium: int = 0
    boranium: int = 0
    germanium: int = 0
    energy: int = 0


@dataclass
class MockStarbase:
    """Mock starbase for testing."""
    composition: Dict[int, MockFleetToken] = field(default_factory=lambda: {1: MockFleetToken(quantity=1)})


@dataclass
class MockStar:
    """Mock star for testing."""
    name: str = "Test Star"
    owner: int = NOBODY
    position: NovaPoint = field(default_factory=lambda: NovaPoint(100, 100))
    colonists: int = 0
    resource_stockpile: MockResourceStockpile = field(default_factory=MockResourceStockpile)
    starbase: Optional[object] = None
    gravity: int = 50
    temperature: int = 50
    radiation: int = 50
    ironium_concentration: int = 50
    boranium_concentration: int = 50
    germanium_concentration: int = 50
    factories: int = 0
    mines: int = 0
    defenses: int = 0
    defense_coverage: float = 0.0
    scan_range: int = 0
    pen_scan_range: int = 0
    resources_per_year: int = 0
    research_allocation: int = 0
    max_population: int = 1000000
    manufacturing_queue: Optional[object] = None


@dataclass
class MockRace:
    """Mock race for testing."""
    growth_rate: int = 15
    factory_output: int = 10

    def has_trait(self, trait_code: str) -> bool:
        return False

    def hab_value(self, gravity: int, temperature: int, radiation: int) -> int:
        return 50  # Default moderate habitability


# --------------------------------------------------------------------------
# ServerData tests
# --------------------------------------------------------------------------

class TestServerData:
    """Tests for ServerData class."""

    def test_server_data_initialization(self):
        """ServerData initializes with expected defaults."""
        data = ServerData()

        assert data.turn_year == STARTING_YEAR
        assert len(data.all_empires) == 0
        assert len(data.all_stars) == 0
        assert len(data.all_minefields) == 0
        assert len(data.all_messages) == 0

    def test_iterate_all_fleets(self):
        """iterate_all_fleets yields fleets from all empires."""
        data = ServerData()

        empire1 = EmpireData(id=0)
        fleet1 = MockFleet(key=1, owner=0)
        fleet2 = MockFleet(key=2, owner=0)
        empire1.owned_fleets = {1: fleet1, 2: fleet2}

        empire2 = EmpireData(id=1)
        fleet3 = MockFleet(key=(1 << 32) + 1, owner=1)
        empire2.owned_fleets = {(1 << 32) + 1: fleet3}

        data.all_empires = {0: empire1, 1: empire2}

        fleets = list(data.iterate_all_fleets())
        assert len(fleets) == 3
        assert fleet1 in fleets
        assert fleet2 in fleets
        assert fleet3 in fleets

    def test_cleanup_fleets_removes_empty(self):
        """cleanup_fleets removes fleets with no ships."""
        data = ServerData()

        empire = EmpireData(id=0)
        fleet_empty = MockFleet(key=1, owner=0, composition={})
        fleet_with_ships = MockFleet(
            key=2, owner=0,
            composition={1: MockFleetToken(quantity=5)}
        )
        empire.owned_fleets = {1: fleet_empty, 2: fleet_with_ships}
        data.all_empires = {0: empire}

        data.cleanup_fleets()

        assert 1 not in empire.owned_fleets
        assert 2 in empire.owned_fleets


# --------------------------------------------------------------------------
# FirstStep tests (mine laying and decay)
# --------------------------------------------------------------------------

class TestFirstStep:
    """Tests for FirstStep (mine laying)."""

    def test_minefield_decay(self):
        """Minefields decay by 1% per year."""
        data = ServerData()
        data.all_empires = {0: EmpireData(id=0)}

        # Create a minefield with 1000 mines
        minefield = Minefield(
            key=1, owner=0, position_x=100, position_y=100,
            number_of_mines=1000, mine_type=0
        )
        data.all_minefields = {1: minefield}

        step = FirstStep()
        step.process(data)

        # Should decay by 1% (10 mines)
        assert minefield.number_of_mines == 990

    def test_small_minefield_removed(self):
        """Minefields with <= 10 mines are removed."""
        data = ServerData()
        data.all_empires = {0: EmpireData(id=0)}

        minefield = Minefield(
            key=1, owner=0, position_x=100, position_y=100,
            number_of_mines=10, mine_type=0
        )
        data.all_minefields = {1: minefield}

        step = FirstStep()
        step.process(data)

        assert 1 not in data.all_minefields

    def test_lay_mines_creates_minefield(self):
        """Fleet with LayMines task creates new minefield."""
        data = ServerData()

        empire = EmpireData(id=0)
        fleet = MockFleet(
            key=1, owner=0,
            position=NovaPoint(100, 100),
            waypoints=[Waypoint(
                position_x=100, position_y=100,
                destination="Mine Location",
                task=WaypointTask.LAY_MINES
            )],
            number_of_mines=50
        )
        empire.owned_fleets = {1: fleet}
        data.all_empires = {0: empire}

        step = FirstStep()
        messages = step.process(data)

        assert len(data.all_minefields) == 1
        assert any("created" in m.text.lower() for m in messages)


# --------------------------------------------------------------------------
# ScrapFleetStep tests
# --------------------------------------------------------------------------

class TestScrapFleetStep:
    """Tests for ScrapFleetStep."""

    def test_scrap_at_starbase_75_percent(self):
        """Scrapping at starbase returns 75% of resources."""
        data = ServerData()

        star = MockStar(name="Home", starbase=MockStarbase())  # Has starbase
        data.all_stars = {"Home": star}

        design = MockDesign(cost=Resources(ironium=100, boranium=50, germanium=25))
        token = MockFleetToken(quantity=2, design=design)

        empire = EmpireData(id=0)
        fleet = MockFleet(
            key=1, owner=0,
            waypoints=[Waypoint(
                position_x=100, position_y=100,
                destination="Home",
                task=WaypointTask.SCRAP
            )],
            composition={1: token}
        )
        empire.owned_fleets = {1: fleet}
        data.all_empires = {0: empire}

        step = ScrapFleetStep()
        messages = step.process(data)

        # 75% of (100*2) = 150 ironium
        # 75% of (50*2) = 75 boranium
        # 75% of (25*2) = 37 germanium
        assert star.resource_stockpile.ironium == 150
        assert star.resource_stockpile.boranium == 75
        assert star.resource_stockpile.germanium == 37
        assert len(messages) > 0

    def test_scrap_at_planet_33_percent(self):
        """Scrapping at planet without starbase returns 33%."""
        data = ServerData()

        star = MockStar(name="Colony", starbase=None)
        data.all_stars = {"Colony": star}

        design = MockDesign(cost=Resources(ironium=100, boranium=100, germanium=100))
        token = MockFleetToken(quantity=1, design=design)

        empire = EmpireData(id=0)
        fleet = MockFleet(
            key=1, owner=0,
            waypoints=[Waypoint(
                position_x=100, position_y=100,
                destination="Colony",
                task=WaypointTask.SCRAP
            )],
            composition={1: token}
        )
        empire.owned_fleets = {1: fleet}
        data.all_empires = {0: empire}

        step = ScrapFleetStep()
        step.process(data)

        # 33% of 100 = 33
        assert star.resource_stockpile.ironium == 33
        assert star.resource_stockpile.boranium == 33
        assert star.resource_stockpile.germanium == 33


# --------------------------------------------------------------------------
# SplitFleetStep tests
# --------------------------------------------------------------------------

class TestSplitFleetStep:
    """Tests for SplitFleetStep."""

    def test_removes_split_merge_waypoints(self):
        """SplitMerge waypoints at position zero are removed."""
        data = ServerData()

        empire = EmpireData(id=0)
        fleet = MockFleet(
            key=1, owner=0,
            position=NovaPoint(100, 100),
            waypoints=[
                Waypoint(position_x=100, position_y=100, destination="Here", task=WaypointTask.SPLIT_MERGE),
                Waypoint(position_x=200, position_y=200, destination="There", task=WaypointTask.NO_TASK),
            ],
            composition={1: MockFleetToken(quantity=5)}
        )
        empire.owned_fleets = {1: fleet}
        data.all_empires = {0: empire}

        step = SplitFleetStep()
        step.process(data)

        # Split/merge waypoint should be removed
        assert len(fleet.waypoints) == 1
        assert fleet.waypoints[0].destination == "There"

    def test_restores_no_task_waypoint_if_all_removed(self):
        """If all waypoints removed, a NoTask waypoint is created."""
        data = ServerData()

        empire = EmpireData(id=0)
        fleet = MockFleet(
            key=1, owner=0,
            position=NovaPoint(100, 100),
            waypoints=[
                Waypoint(position_x=100, position_y=100, destination="Here", task=WaypointTask.SPLIT_MERGE),
            ],
            composition={1: MockFleetToken(quantity=5)}
        )
        empire.owned_fleets = {1: fleet}
        data.all_empires = {0: empire}

        step = SplitFleetStep()
        step.process(data)

        # Should have a restored NoTask waypoint
        assert len(fleet.waypoints) == 1
        assert get_task_type(fleet.waypoints[0].task) == WaypointTask.NO_TASK


# --------------------------------------------------------------------------
# ScanStep tests
# --------------------------------------------------------------------------

class TestScanStep:
    """Tests for ScanStep."""

    def test_owned_stars_added_to_reports(self):
        """Owned stars are added to star reports."""
        data = ServerData()

        star = MockStar(name="Home", owner=0)
        data.all_stars = {"Home": star}

        empire = EmpireData(id=0)
        data.all_empires = {0: empire}

        step = ScanStep()
        step.process(data)

        assert "Home" in empire.star_reports
        assert empire.star_reports["Home"]["scan_level"] == "owned"

    def test_fleet_detection_within_range(self):
        """Enemy fleets within scan range are detected."""
        data = ServerData()
        data.turn_year = 2400

        empire0 = EmpireData(id=0)
        scanner_design = MockDesign(scan_range=200, pen_scan_range=100)
        scanner_fleet = MockFleet(
            key=1, owner=0,
            position=NovaPoint(100, 100),
            composition={1: MockFleetToken(quantity=1, design=scanner_design)}
        )
        empire0.owned_fleets = {1: scanner_fleet}

        empire1 = EmpireData(id=1)
        enemy_fleet = MockFleet(
            key=(1 << 32) + 1, owner=1,
            position=NovaPoint(150, 150),  # Within 200 ly
            composition={1: MockFleetToken(quantity=3)}
        )
        empire1.owned_fleets = {(1 << 32) + 1: enemy_fleet}

        data.all_empires = {0: empire0, 1: empire1}

        step = ScanStep()
        step.process(data)

        # Enemy fleet should be in empire0's reports
        assert (1 << 32) + 1 in empire0.fleet_reports


# --------------------------------------------------------------------------
# BombingStep tests
# --------------------------------------------------------------------------

class TestBombingStep:
    """Tests for BombingStep."""

    def test_bombing_kills_colonists(self):
        """Bombing reduces colonist population."""
        data = ServerData()

        star = MockStar(name="Target", owner=1, colonists=100000, defense_coverage=0.0)
        data.all_stars = {"Target": star}

        bomber_design = MockDesign(bomb_count=10, bomb_kill_rate=1.0)  # 10% kill rate
        token = MockFleetToken(quantity=1, design=bomber_design)

        empire0 = EmpireData(id=0)
        fleet = MockFleet(
            key=1, owner=0,
            in_orbit=star,
            has_bombers=True,
            composition={1: token}
        )
        empire0.owned_fleets = {1: fleet}

        empire1 = EmpireData(id=1)

        data.all_empires = {0: empire0, 1: empire1}

        step = BombingStep()
        messages = step.process(data)

        assert star.colonists < 100000
        assert len(messages) > 0


# --------------------------------------------------------------------------
# PostBombingStep tests (colonization)
# --------------------------------------------------------------------------

class TestPostBombingStep:
    """Tests for PostBombingStep (colonization)."""

    def test_colonization_transfers_colonists(self):
        """Colonization transfers colonists to planet."""
        data = ServerData()

        star = MockStar(name="New World", owner=NOBODY)
        data.all_stars = {"New World": star}

        empire = EmpireData(id=0)
        fleet = MockFleet(
            key=1, owner=0,
            position=NovaPoint(100, 100),
            waypoints=[Waypoint(
                position_x=100, position_y=100,
                destination="New World",
                task=WaypointTask.COLONIZE
            )],
            cargo=MockCargo(colonists=10000, ironium=500),
            can_colonize=True,
            composition={1: MockFleetToken(quantity=1)}
        )
        empire.owned_fleets = {1: fleet}
        data.all_empires = {0: empire}

        step = PostBombingStep()
        messages = step.process(data)

        assert star.owner == 0
        assert star.colonists == 10000
        assert star.resource_stockpile.ironium == 500
        assert fleet.cargo.colonists == 0
        assert any("colonized" in m.text.lower() for m in messages)


# --------------------------------------------------------------------------
# TurnGenerator tests
# --------------------------------------------------------------------------

class TestTurnGenerator:
    """Tests for TurnGenerator."""

    def test_turn_increments_year(self):
        """generate() increments turn year."""
        data = ServerData()
        data.turn_year = 2400
        data.all_empires = {0: EmpireData(id=0)}

        gen = TurnGenerator(data)
        gen.generate()

        assert data.turn_year == 2401

    def test_turn_steps_executed(self):
        """Turn steps are executed during generation."""
        data = ServerData()

        empire = EmpireData(id=0)
        empire.race = MockRace()
        star = MockStar(name="Home", owner=0, colonists=50000, mines=10, factories=10)
        data.all_stars = {"Home": star}
        empire.owned_stars = {"Home": star}
        data.all_empires = {0: empire}

        gen = TurnGenerator(data)
        gen.generate()

        # ScanStep should have run - owned star should be in star_reports
        assert "Home" in empire.star_reports
        assert empire.star_reports["Home"]["scan_level"] == "owned"

    def test_generate_with_multiple_empires(self):
        """Turn processes multiple empires correctly."""
        data = ServerData()

        empire0 = EmpireData(id=0)
        empire0.race = MockRace()
        star0 = MockStar(name="Alpha", owner=0, colonists=10000)
        empire0.owned_stars = {"Alpha": star0}
        empire0.owned_fleets = {}

        empire1 = EmpireData(id=1)
        empire1.race = MockRace()
        star1 = MockStar(name="Beta", owner=1, colonists=10000)
        empire1.owned_stars = {"Beta": star1}
        empire1.owned_fleets = {}

        data.all_stars = {"Alpha": star0, "Beta": star1}
        data.all_empires = {0: empire0, 1: empire1}

        gen = TurnGenerator(data)
        gen.generate()

        # Both empires should have star reports
        assert "Alpha" in empire0.star_reports
        assert "Beta" in empire1.star_reports


# --------------------------------------------------------------------------
# WaypointTask and get_task_type tests
# --------------------------------------------------------------------------

class TestWaypointTaskHelpers:
    """Tests for waypoint task type handling."""

    def test_get_task_type_with_enum(self):
        """get_task_type returns enum value for enum input."""
        assert get_task_type(WaypointTask.NO_TASK) == WaypointTask.NO_TASK
        assert get_task_type(WaypointTask.COLONIZE) == WaypointTask.COLONIZE
        assert get_task_type(WaypointTask.LAY_MINES) == WaypointTask.LAY_MINES

    def test_get_task_type_with_task_objects(self):
        """get_task_type returns correct enum for task objects."""
        assert get_task_type(NoTaskObj()) == WaypointTask.NO_TASK
        assert get_task_type(ColoniseTaskObj()) == WaypointTask.COLONIZE
        assert get_task_type(ScrapTaskObj()) == WaypointTask.SCRAP
        assert get_task_type(SplitMergeTaskObj()) == WaypointTask.SPLIT_MERGE

    def test_get_task_type_with_none(self):
        """get_task_type returns NO_TASK for None."""
        assert get_task_type(None) == WaypointTask.NO_TASK

    def test_waypoint_with_enum_task(self):
        """Waypoint with enum task works correctly."""
        wp = Waypoint(
            position_x=0, position_y=0,
            destination="Test",
            task=WaypointTask.COLONIZE
        )
        assert get_task_type(wp.task) == WaypointTask.COLONIZE

    def test_waypoint_with_object_task(self):
        """Waypoint with object task works correctly."""
        wp = Waypoint(
            position_x=0, position_y=0,
            destination="Test",
            task=ColoniseTaskObj()
        )
        assert get_task_type(wp.task) == WaypointTask.COLONIZE
