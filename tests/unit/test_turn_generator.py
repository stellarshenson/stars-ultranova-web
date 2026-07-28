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
from backend.core.data_structures.cargo import Cargo
from backend.core.game_objects.fleet import Fleet, ShipToken
from backend.core.game_objects.star import Star
from backend.core.waypoints.waypoint import (
    Waypoint, WaypointTask, get_task_type, CargoMode, InvadeTaskObj,
    NoTaskObj, CargoTaskObj, ColoniseTaskObj, ScrapTaskObj, SplitMergeTaskObj, LayMinesTaskObj
)
from backend.core.globals import STARTING_YEAR, NOBODY


# --------------------------------------------------------------------------
# Mock objects for testing
# --------------------------------------------------------------------------

@dataclass
class MockFleetToken:
    """Mock ship token for fleet tokens."""
    quantity: int = 1
    design: Optional[object] = None
    design_key: int = 1
    scan_range_normal: int = 0
    scan_range_penetrating: int = 0
    can_colonize: bool = False
    mass: int = 0

    def __post_init__(self):
        # Copy scan ranges from design if provided
        if self.design is not None:
            if hasattr(self.design, 'scan_range'):
                self.scan_range_normal = self.design.scan_range
            if hasattr(self.design, 'pen_scan_range'):
                self.scan_range_penetrating = self.design.pen_scan_range


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
    colonists_in_kilotons: int = 0

    @property
    def colonist_numbers(self) -> int:
        return self.colonists_in_kilotons * 100


@dataclass
class MockFleet:
    """Mock fleet for testing."""
    key: int = 1
    name: str = "Test Fleet"
    owner: int = 0
    position: NovaPoint = field(default_factory=lambda: NovaPoint(0, 0))
    waypoints: List[Waypoint] = field(default_factory=list)
    tokens: Dict[int, MockFleetToken] = field(default_factory=dict)
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
    tokens: Dict[int, MockFleetToken] = field(default_factory=lambda: {1: MockFleetToken(quantity=1)})


@dataclass
class MockStar:
    """Mock star for testing."""
    name: str = "Test Star"
    owner: int = NOBODY
    position: NovaPoint = field(default_factory=lambda: NovaPoint(100, 100))
    colonists: int = 0
    resources_on_hand: MockResourceStockpile = field(default_factory=MockResourceStockpile)
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
    defense_type: str = "None"
    scanner_type: str = "None"
    scan_range: int = 0
    pen_scan_range: int = 0
    resources_per_year: int = 0
    research_allocation: int = 0
    max_population: int = 1000000
    manufacturing_queue: Optional[object] = None
    this_race: Optional[object] = None
    only_leftover: bool = False

    def update_minerals(self):
        pass

    def update_research(self, budget: int):
        self.research_allocation = 0

    def update_resources(self):
        pass

    def update_population(self, race):
        self.colonists += int(self.colonists * 0.15)


@dataclass
class MockRace:
    """Mock race for testing."""
    name: str = "Mock Race"
    growth_rate: int = 15
    factory_output: int = 10
    primary_trait: str = "JOAT"
    traits: set = field(default_factory=set)
    research_costs: dict = field(
        default_factory=lambda: {
            key: 100 for key in
            ("Biotechnology", "Electronics", "Energy",
             "Propulsion", "Weapons", "Construction")
        })

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
        fleet_empty = MockFleet(key=1, owner=0, tokens={})
        fleet_with_ships = MockFleet(
            key=2, owner=0,
            tokens={1: MockFleetToken(quantity=5)}
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
            tokens={1: token}
        )
        empire.owned_fleets = {1: fleet}
        data.all_empires = {0: empire}

        step = ScrapFleetStep()
        messages = step.process(data)

        # 75% of (100*2) = 150 ironium
        # 75% of (50*2) = 75 boranium
        # 75% of (25*2) = 37 germanium
        assert star.resources_on_hand.ironium == 150
        assert star.resources_on_hand.boranium == 75
        assert star.resources_on_hand.germanium == 37
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
            tokens={1: token}
        )
        empire.owned_fleets = {1: fleet}
        data.all_empires = {0: empire}

        step = ScrapFleetStep()
        step.process(data)

        # 33% of 100 = 33
        assert star.resources_on_hand.ironium == 33
        assert star.resources_on_hand.boranium == 33
        assert star.resources_on_hand.germanium == 33


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
            tokens={1: MockFleetToken(quantity=5)}
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
            tokens={1: MockFleetToken(quantity=5)}
        )
        empire.owned_fleets = {1: fleet}
        data.all_empires = {0: empire}

        step = SplitFleetStep()
        step.process(data)

        # Should have a restored NoTask waypoint
        assert len(fleet.waypoints) == 1
        assert get_task_type(fleet.waypoints[0].task) == WaypointTask.NO_TASK


# --------------------------------------------------------------------------
# Waypoint CargoTask execution tests (CargoTask.cs:145-228 port)
# --------------------------------------------------------------------------

def _cargo_state(star_owner=1, capacity=200, minerals=(100, 100, 100),
                 colonists=200000):
    """ServerData with one star and one owned fleet in orbit."""
    server_data = ServerData()

    star = Star()
    star.name = "Depot"
    star.owner = star_owner
    star.colonists = colonists
    star.resources_on_hand.ironium = minerals[0]
    star.resources_on_hand.boranium = minerals[1]
    star.resources_on_hand.germanium = minerals[2]
    star.position = NovaPoint(100.0, 100.0)
    server_data.all_stars[star.name] = star

    empire = EmpireData(id=1)
    server_data.all_empires[1] = empire

    fleet = Fleet()
    fleet.key = empire.get_next_fleet_key()
    fleet.name = "Hauler #1"
    fleet.owner = 1
    fleet.position = NovaPoint(100.0, 100.0)
    fleet.in_orbit_name = star.name
    fleet.tokens[1] = ShipToken(design_key=1, quantity=1,
                                cargo_capacity=capacity)
    empire.owned_fleets[fleet.key] = fleet

    return server_data, star, fleet


def _cargo_waypoint(mode, amount, destination="Depot",
                    position=(100.0, 100.0)):
    return Waypoint(
        position_x=position[0], position_y=position[1],
        destination=destination,
        task=CargoTaskObj(mode=mode, amount=amount,
                          target_name=destination))


class TestCargoTaskExecution:
    """Waypoint-zero CargoTask execution in SplitFleetStep."""

    def test_wp0_load(self):
        """LOAD moves minerals and colonists star -> fleet
        (CargoTask.cs:216-228)."""
        server_data, star, fleet = _cargo_state()
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.LOAD, Cargo(ironium=50, colonists_in_kilotons=10)))

        messages = SplitFleetStep().process(server_data)

        assert fleet.cargo.ironium == 50
        assert fleet.cargo.colonists_in_kilotons == 10
        assert star.resources_on_hand.ironium == 50
        assert star.colonists == 200000 - 1000  # 10 kT x 100/kT
        # Waypoint consumed; a NoTask placeholder remains
        assert len(fleet.waypoints) == 1
        assert get_task_type(fleet.waypoints[0].task) == WaypointTask.NO_TASK
        assert any("has loaded cargo from Depot" in m.text
                   for m in messages)

    def test_wp0_unload(self):
        """UNLOAD moves minerals and colonists fleet -> star
        (CargoTask.cs:198-210), colonists as kT x 100 headcount."""
        server_data, star, fleet = _cargo_state()
        fleet.cargo = Cargo(ironium=30, colonists_in_kilotons=5)
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.UNLOAD, Cargo(ironium=30, colonists_in_kilotons=5)))

        messages = SplitFleetStep().process(server_data)

        assert fleet.cargo.ironium == 0
        assert fleet.cargo.colonists_in_kilotons == 0
        assert star.resources_on_hand.ironium == 130
        assert star.colonists == 200000 + 500
        assert any("has unloaded its cargo at Depot" in m.text
                   for m in messages)

    def test_load_clamps_to_star_stock(self):
        """Loading more than the star holds moves only the stock."""
        server_data, star, fleet = _cargo_state(minerals=(100, 0, 0))
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.LOAD, Cargo(ironium=500)))

        SplitFleetStep().process(server_data)

        assert fleet.cargo.ironium == 100
        assert star.resources_on_hand.ironium == 0

    def test_load_clamps_to_free_capacity(self):
        """Loading beyond capacity fills the hold exactly."""
        server_data, star, fleet = _cargo_state(capacity=60)
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.LOAD, Cargo(ironium=100)))

        SplitFleetStep().process(server_data)

        assert fleet.cargo.ironium == 60
        assert fleet.cargo.mass == fleet.total_cargo_capacity
        assert star.resources_on_hand.ironium == 40

    def test_unload_clamps_to_hold(self):
        """Unloading more than aboard moves only what is aboard."""
        server_data, star, fleet = _cargo_state()
        fleet.cargo = Cargo(ironium=10)
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.UNLOAD, Cargo(ironium=50)))

        SplitFleetStep().process(server_data)

        assert fleet.cargo.ironium == 0
        assert star.resources_on_hand.ironium == 110

    def test_set_mode_loads_up(self):
        """SET above the current hold loads the difference
        (canonical rule - no C# equivalent)."""
        server_data, star, fleet = _cargo_state()
        fleet.cargo = Cargo(ironium=30)
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.SET, Cargo(ironium=50)))

        SplitFleetStep().process(server_data)

        assert fleet.cargo.ironium == 50
        assert star.resources_on_hand.ironium == 80

    def test_set_mode_unloads_down(self):
        """SET below the current hold unloads the difference."""
        server_data, star, fleet = _cargo_state()
        fleet.cargo = Cargo(ironium=30)
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.SET, Cargo(ironium=10)))

        SplitFleetStep().process(server_data)

        assert fleet.cargo.ironium == 10
        assert star.resources_on_hand.ironium == 120

    def test_deep_space_produces_warning(self):
        """CargoTask with no orbiting star warns and moves nothing
        (CargoTask.cs:147-154)."""
        server_data, star, fleet = _cargo_state()
        fleet.in_orbit_name = None
        fleet.position = NovaPoint(5.0, 5.0)
        fleet.cargo = Cargo(ironium=10)
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.UNLOAD, Cargo(ironium=10),
            destination="Space at 5,5", position=(5.0, 5.0)))

        messages = SplitFleetStep().process(server_data)

        assert fleet.cargo.ironium == 10
        assert star.resources_on_hand.ironium == 100
        assert any("attempted to unload cargo while not in orbit"
                   in m.text for m in messages)

    def test_foreign_star_colonist_unload_becomes_invasion(self):
        """Unloading colonists at a foreign star delegates to the
        invade task (CargoTask.cs:159-173); PostBombingStep resolves
        it with the invasion math (InvadeTask.cs:143-243)."""
        server_data, star, fleet = _cargo_state(star_owner=2,
                                                colonists=2000)
        empire2 = EmpireData(id=2)
        empire2.owned_stars[star.name] = star
        server_data.all_empires[2] = empire2

        fleet.cargo = Cargo(colonists_in_kilotons=100)  # 10000 troops
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.UNLOAD, Cargo(colonists_in_kilotons=100)))

        SplitFleetStep().process(server_data)

        # Task converted in place; the waypoint stays for PostBombingStep
        assert get_task_type(fleet.waypoints[0].task) == WaypointTask.INVADE
        assert fleet.cargo.colonists_in_kilotons == 100

        PostBombingStep().process(server_data)

        # 10000 troops x 1.1 vs 2000 defenders: attackers win with
        # max(int((11000 - 2000) / 1.1), 100) colonists surviving
        assert star.owner == 1
        assert star.colonists == int((11000 - 2000) / 1.1)
        assert fleet.cargo.colonists_in_kilotons == 0
        assert star.name in server_data.all_empires[1].owned_stars

    def test_foreign_star_mineral_load_refused(self):
        """Mineral-only transfer at a foreign-owned star is refused."""
        server_data, star, fleet = _cargo_state(star_owner=2,
                                                colonists=2000)
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.LOAD, Cargo(ironium=50)))

        messages = SplitFleetStep().process(server_data)

        assert fleet.cargo.ironium == 0
        assert star.resources_on_hand.ironium == 100
        assert any("owned by another empire" in m.text for m in messages)

    def test_nobody_star_minerals_move_colonist_unload_refused(self):
        """At an uninhabited star minerals transfer but colonist
        unload is refused (colonization/invasion path)."""
        server_data, star, fleet = _cargo_state(star_owner=NOBODY,
                                                colonists=0)
        fleet.cargo = Cargo(ironium=20, colonists_in_kilotons=5)
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.UNLOAD, Cargo(ironium=20, colonists_in_kilotons=5)))

        messages = SplitFleetStep().process(server_data)

        assert fleet.cargo.ironium == 0
        assert star.resources_on_hand.ironium == 120
        assert fleet.cargo.colonists_in_kilotons == 5
        assert star.colonists == 0
        assert any("cannot unload colonists" in m.text for m in messages)

    def test_nobody_star_colonist_load_clamps_to_zero(self):
        """Loading colonists off an uninhabited star yields nothing."""
        server_data, star, fleet = _cargo_state(star_owner=NOBODY,
                                                colonists=0)
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.LOAD, Cargo(ironium=10, colonists_in_kilotons=5)))

        SplitFleetStep().process(server_data)

        assert fleet.cargo.ironium == 10
        assert fleet.cargo.colonists_in_kilotons == 0

    def test_arrival_executes_and_clears_cargo_task(self):
        """A cargo task on a travel waypoint executes on arrival and
        the task is cleared to NoTask (TurnGenerator.cs:454-465)."""
        server_data, star, fleet = _cargo_state()

        dest = Star()
        dest.name = "Outpost"
        dest.owner = 1
        dest.position = NovaPoint(150.0, 100.0)
        server_data.all_stars[dest.name] = dest
        server_data.all_empires[1].owned_stars[dest.name] = dest

        fleet.cargo = Cargo(ironium=20)
        fleet.fuel_available = 1000
        fleet.waypoints.append(Waypoint(
            position_x=100.0, position_y=100.0,
            destination="Depot", task=NoTaskObj()))
        fleet.waypoints.append(Waypoint(
            position_x=150.0, position_y=100.0, warp_factor=9,
            destination="Outpost",
            task=CargoTaskObj(mode=CargoMode.UNLOAD,
                              amount=Cargo(ironium=20),
                              target_name="Outpost")))

        TurnGenerator(server_data)._update_fleet(fleet)

        assert fleet.in_orbit_name == "Outpost"
        assert fleet.cargo.ironium == 0
        assert dest.resources_on_hand.ironium == 20
        assert get_task_type(fleet.waypoints[0].task) == WaypointTask.NO_TASK
        assert any("has unloaded its cargo at Outpost" in m.text
                   for m in server_data.all_messages)

    def test_ai_shaped_load_order_executes(self):
        """Regression: the AI appends its colonist/germanium LOAD
        waypoint after the current-position waypoint; the old stub
        silently dropped it every turn."""
        server_data, star, fleet = _cargo_state()
        fleet.waypoints.append(Waypoint(
            position_x=100.0, position_y=100.0,
            destination="Depot", task=NoTaskObj()))
        fleet.waypoints.append(_cargo_waypoint(
            CargoMode.LOAD, Cargo(germanium=25, colonists_in_kilotons=40)))

        SplitFleetStep().process(server_data)

        assert fleet.cargo.germanium == 25
        assert fleet.cargo.colonists_in_kilotons == 40
        assert star.resources_on_hand.germanium == 75
        assert star.colonists == 200000 - 4000
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
            tokens={1: MockFleetToken(quantity=1, design=scanner_design)}
        )
        empire0.owned_fleets = {1: scanner_fleet}

        empire1 = EmpireData(id=1)
        enemy_fleet = MockFleet(
            key=(1 << 32) + 1, owner=1,
            position=NovaPoint(150, 150),  # Within 200 ly
            tokens={1: MockFleetToken(quantity=3)}
        )
        empire1.owned_fleets = {(1 << 32) + 1: enemy_fleet}

        data.all_empires = {0: empire0, 1: empire1}

        step = ScanStep()
        step.process(data)

        # Enemy fleet should be in empire0's reports
        assert (1 << 32) + 1 in empire0.fleet_reports


# --------------------------------------------------------------------------
# ScanStep cloaking and design learning tests
# --------------------------------------------------------------------------

@dataclass
class SSRace:
    """Race with the Super Stealth PRT for cloak tests."""
    name: str = "Sneaks"

    def has_trait(self, trait_code: str) -> bool:
        return trait_code == "SS"


@dataclass
class ISBRace:
    """Race with the Improved Starbases LRT."""
    name: str = "Basers"

    def has_trait(self, trait_code: str) -> bool:
        return trait_code == "ISB"


def _scan_fleet(key: int, owner: int, x: float, y: float,
                scan_range: int = 0, cloak_units: int = 0,
                tachyon_detectors: int = 0, mass: int = 25,
                quantity: int = 1) -> Fleet:
    """Real fleet with one token for cloak-detection tests."""
    fleet = Fleet(name=f"Fleet #{key}", position=NovaPoint(x, y))
    fleet._key = (owner << 32) | key
    fleet.owner = owner
    fleet.tokens[1] = ShipToken(
        design_key=1, design_name="Testship", quantity=quantity,
        mass=mass, armor=20, scan_range_normal=scan_range,
        cloak_units=cloak_units, tachyon_detectors=tachyon_detectors,
    )
    return fleet


def _scan_state(scanner: Fleet, target: Fleet,
                target_race=None) -> 'ServerData':
    data = ServerData()
    data.turn_year = 2400
    empire0 = EmpireData(id=1)
    empire0.owned_fleets = {scanner.key: scanner}
    empire1 = EmpireData(id=2)
    empire1.race = target_race
    empire1.owned_fleets = {target.key: target}
    data.all_empires = {1: empire0, 2: empire1}
    return data


class TestScanStepCloaking:
    """Cloak detection-range reduction, tachyon counter and design
    learning (canonical Stars! rules - C# cloak is a stub,
    ScanStep.cs:165)."""

    def test_cloaked_fleet_evades_detection(self):
        """35% cloak (70 u/kT) shrinks a 66 ly scanner to 42.9 ly."""
        scanner = _scan_fleet(1, 1, 0, 0, scan_range=66)
        target = _scan_fleet(1, 2, 50, 0, cloak_units=70)
        data = _scan_state(scanner, target)

        ScanStep().process(data)
        assert target.key not in data.all_empires[1].fleet_reports

    def test_uncloaked_fleet_detected_at_same_distance(self):
        scanner = _scan_fleet(1, 1, 0, 0, scan_range=66)
        target = _scan_fleet(1, 2, 50, 0, cloak_units=0)
        data = _scan_state(scanner, target)

        ScanStep().process(data)
        assert target.key in data.all_empires[1].fleet_reports

    def test_cloaked_fleet_always_detected_at_distance_zero(self):
        scanner = _scan_fleet(1, 1, 0, 0, scan_range=66)
        target = _scan_fleet(1, 2, 0, 0, cloak_units=5000)
        data = _scan_state(scanner, target)

        ScanStep().process(data)
        assert target.key in data.all_empires[1].fleet_reports

    def test_cargo_dilutes_cloak(self):
        """Cargo mass in the divisor halves the units/kT: the same
        cloaked ship becomes detectable once loaded."""
        scanner = _scan_fleet(1, 1, 0, 0, scan_range=66)
        # 70 u/kT on 60 kT ship: hidden at 50 ly (35% -> 42.9 ly)
        target = _scan_fleet(1, 2, 50, 0, cloak_units=70, mass=60)
        data = _scan_state(scanner, target)
        ScanStep().process(data)
        assert target.key not in data.all_empires[1].fleet_reports

        # Loaded with 60 kT cargo: 70*60/120 = 35 u/kT = 17.5% ->
        # effective range 54.45 ly, detected at 50 ly
        scanner = _scan_fleet(1, 1, 0, 0, scan_range=66)
        target = _scan_fleet(1, 2, 50, 0, cloak_units=70, mass=60)
        target.cargo = Cargo(ironium=60)
        data = _scan_state(scanner, target)
        ScanStep().process(data)
        assert target.key in data.all_empires[1].fleet_reports

    def test_ss_built_in_cloak_and_cargo_exclusion(self):
        """SS ships have 300 u/kT (75%) built in; cargo does not
        dilute SS cloak (PrimaryTraits.cs:54)."""
        target = _scan_fleet(1, 2, 50, 0, cloak_units=0, mass=25)
        target.cargo = Cargo(ironium=100)
        data = _scan_state(_scan_fleet(1, 1, 0, 0, scan_range=66),
                           target, target_race=SSRace())

        step = ScanStep()
        pct = step._fleet_cloak_percent(target, data.all_empires[2])
        assert pct == pytest.approx(75.0)

    def test_tachyon_detectors_counter_cloak(self):
        """N detectors cut cloak by 0.95 ** (N ** 0.25): a target
        hidden from a plain scanner is detected by one with 16
        detectors (multiplier 0.95^2 = 0.9025)."""
        # 35% cloak, scanner 66 ly, distance 44.5:
        # N=1: 35 * 0.95 = 33.25% -> 44.05 ly, still hidden
        scanner = _scan_fleet(1, 1, 0, 0, scan_range=66,
                              tachyon_detectors=1)
        target = _scan_fleet(1, 2, 44.5, 0, cloak_units=70)
        data = _scan_state(scanner, target)
        ScanStep().process(data)
        assert target.key not in data.all_empires[1].fleet_reports

        # N=16: 35 * 0.9025 = 31.5875% -> 45.15 ly, detected
        scanner = _scan_fleet(1, 1, 0, 0, scan_range=66,
                              tachyon_detectors=16)
        target = _scan_fleet(1, 2, 44.5, 0, cloak_units=70)
        data = _scan_state(scanner, target)
        ScanStep().process(data)
        assert target.key in data.all_empires[1].fleet_reports

    def test_isb_starbase_cloak_floor(self):
        """fleet.cloaked acts as a floor (Manufacture.cs:133)."""
        target = _scan_fleet(1, 2, 50, 0, cloak_units=0)
        target.cloaked = 20.0
        data = _scan_state(_scan_fleet(1, 1, 0, 0, scan_range=66), target)

        step = ScanStep()
        pct = step._fleet_cloak_percent(target, data.all_empires[2])
        assert pct == 20.0

    def test_detection_teaches_hull_only_design(self):
        """Port of ScanStep.cs:170-183: a detected fleet teaches the
        observer a hull-only design record."""
        from backend.services.ship_specs import SimpleDesign

        scanner = _scan_fleet(1, 1, 0, 0, scan_range=66)
        target = _scan_fleet(1, 2, 50, 0)
        data = _scan_state(scanner, target)
        data.all_empires[2].designs[1] = SimpleDesign(
            key=1, name="Testship", hull_name="Scout")

        ScanStep().process(data)
        empire0 = data.all_empires[1]
        designs = empire0.empire_reports[2]["designs"]
        record = designs[hex(1)]
        assert record["scope"] == "hull"
        assert record["name"] == "Testship"
        assert record["hull_name"] == "Scout"
        assert record["owner"] == 2
        # Hull-only: no component payload on a scan record
        assert "design" not in record

        # Fleet report reveals composition (FleetIntel.cs:206-217)
        report = empire0.fleet_reports[target.key]
        assert report["composition"] == [
            {"design_key": hex(1), "design_name": "Testship",
             "quantity": 1}
        ]

    def test_known_full_record_not_downgraded(self):
        """An existing (battle-learned) full record survives a scan."""
        scanner = _scan_fleet(1, 1, 0, 0, scan_range=66)
        target = _scan_fleet(1, 2, 50, 0)
        data = _scan_state(scanner, target)
        empire0 = data.all_empires[1]
        empire0.empire_reports[2] = {
            "designs": {hex(1): {"key": hex(1), "scope": "full"}}
        }

        ScanStep().process(data)
        assert empire0.empire_reports[2]["designs"][hex(1)]["scope"] == "full"


class TestStarbaseCloakISB:
    """ISB starbases are built 20% cloaked (Manufacture.cs:126-134)."""

    def _build_starbase(self, race):
        from backend.core.production.production_queue import (
            ProductionOrder, ProductionType
        )
        from backend.services.ship_specs import SimpleDesign

        empire = EmpireData(id=1)
        empire.race = race
        design = SimpleDesign(key=7, name="Starbase", is_starbase=True)
        empire.designs[7] = design
        star = MockStar(name="Home", owner=1)
        order = ProductionOrder(production_type=ProductionType.STARBASE,
                                quantity=1, name="Starbase", design_key=7)

        StarUpdateStep()._build_ships(order, star, empire, 1)
        return next(iter(empire.owned_fleets.values()))

    def test_isb_starbase_built_cloaked(self):
        fleet = self._build_starbase(ISBRace())
        assert fleet.cloaked == 20

    def test_non_isb_starbase_not_cloaked(self):
        fleet = self._build_starbase(MockRace())
        assert fleet.cloaked == 0


class TestEmpireReportsPersistence:
    """empire_reports (learned enemy designs) survive the game
    manager's serialize/deserialize round-trip."""

    def test_empire_reports_roundtrip(self, tmp_path):
        import backend.services.game_manager as gm_module
        from backend.services.game_manager import GameManager
        from backend.services.ship_specs import SimpleDesign

        gm_module._game_manager = None
        try:
            manager = GameManager(str(tmp_path / "reports.db"))
            game = manager.create_game("Reports Test", 2, "small",
                                       seed=424242)
            server_data = manager._load_game_state(game["id"])

            design = SimpleDesign(key=(2 << 32) | 1, name="Raider",
                                  hull_name="Scout")
            server_data.all_empires[1].empire_reports = {
                2: {"designs": {
                    hex(design.key): {
                        "key": hex(design.key), "name": "Raider",
                        "hull_name": "Scout", "owner": 2,
                        "scope": "full", "year": 2400,
                        "design": design.to_dict(),
                    }
                }}
            }

            restored = manager._deserialize_state(
                manager._serialize_state(server_data))
            reports = restored.all_empires[1].empire_reports
            assert 2 in reports  # int keys restored
            record = reports[2]["designs"][hex(design.key)]
            assert record["scope"] == "full"
            assert record["design"]["name"] == "Raider"
        finally:
            gm_module._game_manager = None


# --------------------------------------------------------------------------
# BombingStep tests
# --------------------------------------------------------------------------

class TestBombingStep:
    """Tests for BombingStep."""

    def test_bombing_kills_colonists(self):
        """Bombing reduces colonist population per Bombing.cs formulas."""
        from backend.core.components.ship_design import Bomb

        data = ServerData()

        star = MockStar(name="Target", owner=1, colonists=100000)
        data.all_stars = {"Target": star}

        @dataclass
        class BomberDesign:
            key: int = 1
            conventional_bombs: object = None
            smart_bombs: object = None

        design = BomberDesign(
            conventional_bombs=Bomb(pop_kill=2.5, installations=10,
                                    minimum_kill=300, is_smart=False),
            smart_bombs=Bomb(is_smart=True),
        )

        empire0 = EmpireData(id=0)
        empire0.designs[1] = design
        token = MockFleetToken(quantity=2, design_key=1)
        fleet = MockFleet(
            key=1, owner=0,
            in_orbit=star,
            has_bombers=True,
            tokens={1: token}
        )
        empire0.owned_fleets = {1: fleet}

        empire1 = EmpireData(id=1)

        data.all_empires = {0: empire0, 1: empire1}

        step = BombingStep()
        messages = step.process(data)

        # 2 bombers x 2.5% pop kill, no defenses: 5% of 100,000 = 5,000
        assert star.colonists == 95000
        assert len(messages) > 0

    def test_bombing_blocked_by_starbase(self):
        """A starbase protects the planet from bombing (Bombing.cs)."""
        from backend.core.components.ship_design import Bomb

        data = ServerData()
        star = MockStar(name="Target", owner=1, colonists=100000)
        data.all_stars = {"Target": star}

        @dataclass
        class BomberDesign:
            key: int = 1
            conventional_bombs: object = None
            smart_bombs: object = None

        empire0 = EmpireData(id=0)
        empire0.designs[1] = BomberDesign(
            conventional_bombs=Bomb(pop_kill=2.5, installations=10,
                                    minimum_kill=300, is_smart=False),
            smart_bombs=Bomb(is_smart=True),
        )
        fleet = MockFleet(key=1, owner=0, in_orbit=star, has_bombers=True,
                          tokens={1: MockFleetToken(quantity=2)})
        empire0.owned_fleets = {1: fleet}

        empire1 = EmpireData(id=1)
        starbase = MockFleet(key=(1 << 32) | 9, owner=1, is_starbase=True,
                             tokens={1: MockFleetToken(quantity=1)})
        starbase.in_orbit_name = "Target"
        empire1.owned_fleets = {starbase.key: starbase}

        data.all_empires = {0: empire0, 1: empire1}

        BombingStep().process(data)
        assert star.colonists == 100000  # untouched

    def test_defense_coverage_formula(self):
        """Defense coverage follows Defenses.cs exponential formula."""
        from backend.server.turn_steps.bombing_step import (
            compute_defense_coverage
        )
        star = MockStar(name="D", owner=1, colonists=1000, defenses=50,
                        defense_type="SDI")
        cov = compute_defense_coverage(star)
        expected = 1.0 - (1.0 - 0.0099) ** 50
        assert cov["population"] == pytest.approx(expected)
        assert cov["buildings"] == pytest.approx(expected * 0.5)

    def test_defense_type_none_gives_zero_coverage_bombing(self):
        """The star's CURRENT defense type feeds bombing: identical
        defenses with type "None" take the full kill, with "SDI" a
        reduced one (Defenses.cs:60-72)."""
        from backend.core.components.ship_design import Bomb

        @dataclass
        class BomberDesign:
            key: int = 1
            conventional_bombs: object = None
            smart_bombs: object = None

        survivors = {}
        for defense_type in ("None", "SDI"):
            data = ServerData()
            star = MockStar(name="Target", owner=1, colonists=100000,
                            defenses=100, defense_type=defense_type)
            data.all_stars = {"Target": star}

            empire0 = EmpireData(id=0)
            empire0.designs[1] = BomberDesign(
                conventional_bombs=Bomb(pop_kill=2.5, installations=0,
                                        minimum_kill=0, is_smart=False),
                smart_bombs=Bomb(is_smart=True),
            )
            fleet = MockFleet(key=1, owner=0, in_orbit=star,
                              has_bombers=True,
                              tokens={1: MockFleetToken(quantity=2,
                                                        design_key=1)})
            empire0.owned_fleets = {1: fleet}
            data.all_empires = {0: empire0, 1: EmpireData(id=1)}

            BombingStep().process(data)
            survivors[defense_type] = star.colonists

        # "None": full 5% kill; "SDI": kill reduced by pop coverage
        assert survivors["None"] == 95000
        pop_coverage = 1.0 - (1.0 - 0.0099) ** 100
        expected_dead = int(100000 * 0.05 * (1.0 - pop_coverage))
        assert survivors["SDI"] == 100000 - expected_dead
        assert survivors["SDI"] > survivors["None"]


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
            cargo=MockCargo(colonists_in_kilotons=100, ironium=500),
            can_colonize=True,
            tokens={1: MockFleetToken(quantity=1)}
        )
        empire.owned_fleets = {1: fleet}
        data.all_empires = {0: empire}

        step = PostBombingStep()
        messages = step.process(data)

        assert star.owner == 0
        assert star.colonists == 10000
        assert star.resources_on_hand.ironium == 500
        assert fleet.cargo.colonists_in_kilotons == 0
        assert any("colonized" in m.text.lower() for m in messages)

    def _colonize_fleet(self, owner=0, target="Contested"):
        return MockFleet(
            key=1, owner=owner,
            position=NovaPoint(100, 100),
            waypoints=[Waypoint(
                position_x=100, position_y=100,
                destination=target,
                task=WaypointTask.COLONIZE
            )],
            cargo=MockCargo(colonists_in_kilotons=100, ironium=500),
            can_colonize=True,
            tokens={1: MockFleetToken(quantity=1, can_colonize=True)}
        )

    def test_colonize_occupied_foreign_planet_aborts(self):
        """COLONIZE on a foreign-owned planet aborts with the C#
        'already occupied' message (ColoniseTask.cs:88-92) - it must
        NOT convert into an invasion (run100 DEF-12: Kapteyn's Star
        was auto-invaded on stale intel)."""
        data = ServerData()

        star = MockStar(name="Contested", owner=2, colonists=50000)
        data.all_stars = {"Contested": star}

        defender = EmpireData(id=2)
        defender.owned_stars = {"Contested": star}
        attacker = EmpireData(id=0)
        fleet = self._colonize_fleet(owner=0)
        attacker.owned_fleets = {1: fleet}
        data.all_empires = {0: attacker, 2: defender}

        messages = PostBombingStep().process(data)

        # No invasion, no ownership change, defenders untouched
        assert star.owner == 2
        assert star.colonists == 50000
        # Colonists stay aboard, colonizer token intact
        assert fleet.cargo.colonists_in_kilotons == 100
        assert len(fleet.tokens) == 1
        assert any("already occupied" in m.text for m in messages)
        assert not any(m.message_type == "Invasion" for m in messages)
        # The waypoint task was consumed (C# clears it to NoTask)
        assert len(fleet.waypoints) == 0

    def test_colonize_own_planet_aborts(self):
        """COLONIZE on an already-colonized OWN planet aborts too -
        star.Colonists != 0 covers ANY occupant (ColoniseTask.cs:88-92)
        - instead of overwriting the population."""
        data = ServerData()

        star = MockStar(name="Home", owner=0, colonists=250000)
        data.all_stars = {"Home": star}

        empire = EmpireData(id=0)
        empire.owned_stars = {"Home": star}
        fleet = self._colonize_fleet(owner=0, target="Home")
        empire.owned_fleets = {1: fleet}
        data.all_empires = {0: empire}

        messages = PostBombingStep().process(data)

        assert star.colonists == 250000  # not overwritten
        assert fleet.cargo.colonists_in_kilotons == 100
        assert any("already occupied" in m.text for m in messages)


# --------------------------------------------------------------------------
# Fleet movement fuel-time cap (DEF-13) and in-transit warp (DEF-11)
# --------------------------------------------------------------------------

# Quick Jump 5 per-warp fuel factors (components.xml, warp 1..10)
QJ5_TABLE = [0, 25, 100, 100, 100, 180, 500, 800, 900, 1080]


def _real_fleet(fuel=100.0, warp=8, distance=100.0, free_warp=1,
                table=None, mass=25):
    """Real Fleet with one token, one leg east of length `distance`."""
    fleet = Fleet(name="Scout #1")
    fleet.key = (1 << 32) | 1  # owner 1, id 1 (owner lives in the key)
    fleet.position = NovaPoint(0, 0)
    token = ShipToken(design_key=1, mass=mass, quantity=1)
    token.fuel_table = list(table if table is not None else QJ5_TABLE)
    token.free_warp_speed = free_warp
    fleet.tokens = {1: token}
    fleet.fuel_available = fuel
    fleet.waypoints = [Waypoint(
        position_x=distance, position_y=0.0, warp_factor=warp,
        destination="Deep Space", task=NoTaskObj())]
    return fleet


class TestMoveFleetFuelCap:
    """_move_fleet ports the Fleet.cs Move three-way travel-time min
    (target time / available time / fuel time, lines 520-546): an
    empty tank moves a fleet zero light years and fuel can never go
    negative (DEF-13 regression - run100 Santa Maria #64 moved 4.0 ly
    on an empty tank then deadlocked silently)."""

    def _gen(self):
        return TurnGenerator(ServerData())

    def test_arrival_within_fuel(self):
        """Target time smallest: fleet arrives, burns the leg's fuel
        (warp 5, 25 ly = one year, rate 3.125 -> int 3)."""
        fleet = _real_fleet(fuel=100.0, warp=5, distance=25.0)
        messages = []
        status = self._gen()._move_fleet(fleet, 1.0, None, messages)
        assert status == "arrived"
        assert fleet.position.x == 25.0
        assert fleet.fuel_available == 97.0
        assert messages == []

    def test_year_cap_partial_move(self):
        """Available time smallest: one year of travel at warp 5
        covers 25 of 100 ly."""
        fleet = _real_fleet(fuel=100.0, warp=5, distance=100.0)
        status = self._gen()._move_fleet(fleet, 1.0, None, [])
        assert status == "in_transit"
        assert fleet.position.x == 25.0
        assert fleet.fuel_available == 97.0

    def test_fuel_cap_limits_distance(self):
        """Fuel time smallest: 10 mg at warp 8 (rate 64/yr) buys
        exactly 10 ly of the 100 ly leg, then the fleet drops to its
        free warp - silently (Fleet.cs:570-576)."""
        fleet = _real_fleet(fuel=10.0, warp=8, distance=100.0)
        messages = []
        status = self._gen()._move_fleet(fleet, 1.0, None, messages)
        assert status == "in_transit"
        assert abs(fleet.position.x - 10.0) < 1e-9
        assert fleet.fuel_available == 0
        # Dropped to Quick Jump 5's free warp 1, no message here (the
        # canonical per-turn message is _process_fleet's)
        assert fleet.waypoints[0].warp_factor == 1
        assert messages == []

    def test_exactly_sufficient_fuel_reports_in_transit(self):
        """C# compares travelTime >= fuelTime (Fleet.cs:542), so fuel
        exactly covering the leg still reports InTransit."""
        fleet = _real_fleet(fuel=32.0, warp=8, distance=32.0)
        status = self._gen()._move_fleet(fleet, 1.0, None, [])
        assert status == "in_transit"
        assert abs(fleet.position.x - 32.0) < 1e-9
        assert fleet.fuel_available == 0

    def test_zero_fuel_moves_zero_distance(self):
        """An empty tank moves the fleet 0 ly (fuelTime 0) - the
        DEF-13 core regression."""
        fleet = _real_fleet(fuel=0.0, warp=8, distance=100.0)
        status = self._gen()._move_fleet(fleet, 1.0, None, [])
        assert status == "in_transit"
        assert fleet.position.x == 0.0
        assert fleet.fuel_available == 0
        assert fleet.waypoints[0].warp_factor == 1  # free warp

    def test_zero_fuel_zero_free_warp_stranded_message(self):
        """No free warp: the fleet clamps to warp 0 and the player is
        told it is stranded (web addition; C# strands silently)."""
        fleet = _real_fleet(fuel=0.0, warp=8, distance=100.0,
                            free_warp=0, table=[100] * 10)
        messages = []
        status = self._gen()._move_fleet(fleet, 1.0, None, messages)
        assert status == "in_transit"
        assert fleet.position.x == 0.0
        assert fleet.waypoints[0].warp_factor == 0
        assert any("stranded" in m.text for m in messages)

        # Next turn, warp already 0: still in transit, still told
        messages2 = []
        status = self._gen()._move_fleet(fleet, 1.0, None, messages2)
        assert status == "in_transit"
        assert fleet.position.x == 0.0
        assert any("stranded" in m.text for m in messages2)


class TestInTransitWarp:
    """DEF-11: the in-transit placeholder carries the real leg's warp
    (TurnGenerator.cs:430-436) and warp edits made in transit reach
    the destination waypoint instead of dying with the placeholder."""

    def test_placeholder_inherits_leg_warp(self):
        """_update_fleet's placeholder copies waypointZero.WarpFactor
        - not the dataclass default 6."""
        data = ServerData()
        empire = EmpireData(id=1)
        fleet = _real_fleet(fuel=100.0, warp=5, distance=100.0)
        empire.owned_fleets = {fleet.key: fleet}
        data.all_empires = {1: empire}

        gen = TurnGenerator(data)
        destroyed = gen._update_fleet(fleet)

        assert destroyed is False
        assert len(fleet.waypoints) == 2
        placeholder = fleet.waypoints[0]
        assert get_task_type(placeholder.task) == WaypointTask.NO_TASK
        assert placeholder.position_x == fleet.position.x
        assert placeholder.warp_factor == 5
        # fleet.speed (waypoints[0]) now reports the true warp
        assert fleet.speed == 5

    def test_speed_setter_writes_through_placeholder(self):
        """fleet.speed = N on an in-transit fleet also updates the
        destination waypoint (web deviation - the placeholder is
        popped next turn)."""
        fleet = _real_fleet(fuel=100.0, warp=5, distance=100.0)
        fleet.position = NovaPoint(25.0, 0.0)
        fleet.waypoints.insert(0, Waypoint(
            position_x=25.0, position_y=0.0, warp_factor=5,
            destination="Space at 25,0", task=NoTaskObj()))

        fleet.speed = 8
        assert fleet.waypoints[0].warp_factor == 8
        assert fleet.waypoints[1].warp_factor == 8

    def test_speed_setter_leaves_real_waypoint_zero_alone(self):
        """Without a placeholder (fleet parked before a real leg) the
        setter touches only waypoints[0]."""
        fleet = _real_fleet(fuel=100.0, warp=5, distance=100.0)
        fleet.waypoints.append(Waypoint(
            position_x=200.0, position_y=0.0, warp_factor=6,
            destination="Farther", task=NoTaskObj()))

        fleet.speed = 8
        assert fleet.waypoints[0].warp_factor == 8
        assert fleet.waypoints[1].warp_factor == 6

    def test_waypoint_edit_at_placeholder_reaches_destination(self):
        """A WaypointCommand Edit at index 0 while in transit copies
        the new warp onto the destination waypoint."""
        from backend.core.commands.base import CommandMode
        from backend.core.commands.waypoint import WaypointCommand

        empire = EmpireData(id=1)
        fleet = _real_fleet(fuel=100.0, warp=5, distance=100.0)
        fleet.position = NovaPoint(25.0, 0.0)
        fleet.waypoints.insert(0, Waypoint(
            position_x=25.0, position_y=0.0, warp_factor=5,
            destination="Space at 25,0", task=NoTaskObj()))
        empire.owned_fleets = {fleet.key: fleet}

        command = WaypointCommand(
            mode=CommandMode.EDIT,
            waypoint=Waypoint(
                position_x=25.0, position_y=0.0, warp_factor=9,
                destination="Space at 25,0", task=NoTaskObj()),
            fleet_key=fleet.key, index=0)
        ok, _ = command.is_valid(empire)
        assert ok
        assert command.apply_to_state(empire) is None

        # Edited placeholder AND the surviving destination waypoint
        assert fleet.waypoints[0].warp_factor == 9
        assert fleet.waypoints[1].warp_factor == 9


class TestFreeWarpSaveMigration:
    """Pre-DEF-7 saves store token free_warp_speed 0 and an all-zero
    fuel_table; loading refreshes both from the empire's design
    (DEF-11 migration)."""

    def _roundtrip(self, tmp_path, mutate):
        import backend.services.game_manager as gm_module
        from backend.services.game_manager import GameManager

        gm_module._game_manager = None
        try:
            manager = GameManager(str(tmp_path / "migrate.db"))
            game = manager.create_game("Migrate Test", 2, "small",
                                       seed=424242)
            server_data = manager._load_game_state(game["id"])
            state_dict = manager._serialize_state(server_data)
            mutate(state_dict)
            return manager._deserialize_state(state_dict)
        finally:
            gm_module._game_manager = None

    @staticmethod
    def _scout_token_dicts(state_dict):
        """All non-starbase token dicts of empire 1's fleets."""
        empire = state_dict["all_empires"]["1"]
        tokens = []
        for fleet in empire["owned_fleets"].values():
            for token in fleet["tokens"].values():
                if not token["is_starbase"]:
                    tokens.append(token)
        return tokens

    def test_stale_token_refreshed_from_design(self, tmp_path):
        """free_warp 0 + all-zero table -> both refreshed from the
        owning empire's design."""
        def mutate(state_dict):
            for token in self._scout_token_dicts(state_dict):
                token["free_warp_speed"] = 0
                token["fuel_table"] = [0] * 10

        restored = self._roundtrip(tmp_path, mutate)
        for fleet in restored.all_empires[1].owned_fleets.values():
            for token in fleet.tokens.values():
                if token.is_starbase:
                    continue
                design = restored.all_empires[1].designs[token.design_key]
                assert token.fuel_table == list(design.fuel_table)
                assert any(token.fuel_table)
                assert token.free_warp_speed == design.free_warp_speed
                assert token.free_warp_speed > 0

    def test_missing_design_derives_from_stored_table(self, tmp_path):
        """Design gone but the token kept a real table: free warp is
        derived from the table (Engine.cs free-warp semantics)."""
        def mutate(state_dict):
            empire = state_dict["all_empires"]["1"]
            empire["designs"] = {}
            for token in self._scout_token_dicts(state_dict):
                token["free_warp_speed"] = 0
                token["fuel_table"] = [0, 25, 100, 100, 100, 180,
                                       500, 800, 900, 1080]

        restored = self._roundtrip(tmp_path, mutate)
        for fleet in restored.all_empires[1].owned_fleets.values():
            for token in fleet.tokens.values():
                if token.is_starbase:
                    continue
                assert token.free_warp_speed == 1  # QJ5: warp 1 free

    def test_missing_design_all_zero_table_keeps_zero(self, tmp_path):
        """No design AND no table data: nothing to derive from - the
        token keeps free warp 0 (all zeros also = starbase)."""
        def mutate(state_dict):
            empire = state_dict["all_empires"]["1"]
            empire["designs"] = {}
            for token in self._scout_token_dicts(state_dict):
                token["free_warp_speed"] = 0
                token["fuel_table"] = [0] * 10

        restored = self._roundtrip(tmp_path, mutate)
        for fleet in restored.all_empires[1].owned_fleets.values():
            for token in fleet.tokens.values():
                if token.is_starbase:
                    continue
                assert token.free_warp_speed == 0
                assert token.fuel_table == [0] * 10


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


# --------------------------------------------------------------------------
# RegenerateFleet tests (repair/refuel)
# Port of: ServerState/TurnGenerator.cs RegenerateFleet (lines 301-380)
# --------------------------------------------------------------------------

class TestRegenerateFleet:
    """Tests for the situational repair table and starbase refuel."""

    def _make_fleet(self, key=1, owner=1, armor=100, quantity=1,
                    fuel_capacity=100, heals_others_percent=0,
                    is_bomber=False):
        """Build a minimal real fleet with one token."""
        fleet = Fleet(name=f"Fleet #{key}", position=NovaPoint(100, 100))
        fleet.owner = owner
        fleet.id = key
        fleet.tokens[1] = ShipToken(
            design_key=1, design_name="Testship", quantity=quantity,
            mass=10, armor=armor, fuel_capacity=fuel_capacity,
            heals_others_percent=heals_others_percent,
            is_bomber=is_bomber,
        )
        fleet.fuel_available = fuel_capacity
        return fleet

    def _make_starbase(self, key=100, owner=1, can_refuel=True,
                       damage_percent=0.0):
        """Build a starbase fleet (dock decides can_refuel)."""
        sb = Fleet(name="Starbase #1", position=NovaPoint(100, 100))
        sb.owner = owner
        sb.id = key
        sb.tokens[1] = ShipToken(
            design_key=2, design_name="Starbase", quantity=1,
            armor=500, is_starbase=True, can_refuel=can_refuel,
            dock_capacity=200 if can_refuel else 0,
            damage_percent=damage_percent,
        )
        return sb

    def _make_star(self, name="Home", owner=NOBODY):
        star = Star(name=name, position=NovaPoint(100, 100))
        if owner != NOBODY:
            star.owner = owner
        return star

    def _make_state(self, *fleets, stars=()):
        data = ServerData()
        for fleet in fleets:
            eid = fleet.owner
            if eid not in data.all_empires:
                data.all_empires[eid] = EmpireData(id=eid)
            data.all_empires[eid].owned_fleets[fleet.key] = fleet
        for star in stars:
            data.all_stars[star.name] = star
        return data

    def _orbit(self, fleet, star):
        fleet.in_orbit = star
        fleet.in_orbit_name = star.name
        fleet.position = NovaPoint(star.position.x, star.position.y)

    # -- rate table (TurnGenerator.cs:323-367) --------------------------

    def test_rate_moving_through_space(self):
        fleet = self._make_fleet()
        fleet.waypoints.append(Waypoint(
            position_x=500, position_y=500,
            destination="Space at 500,500", task=NoTaskObj()))
        gen = TurnGenerator(self._make_state(fleet))
        assert gen._get_repair_rate(fleet, None) == 1

    def test_rate_stopped_in_space(self):
        fleet = self._make_fleet()
        gen = TurnGenerator(self._make_state(fleet))
        assert gen._get_repair_rate(fleet, None) == 2

    def test_rate_orbiting_foreign_planet(self):
        fleet = self._make_fleet(owner=1)
        star = self._make_star(owner=2)
        gen = TurnGenerator(self._make_state(fleet, stars=(star,)))
        assert gen._get_repair_rate(fleet, star) == 3

    def test_rate_orbiting_unowned_planet(self):
        fleet = self._make_fleet(owner=1)
        star = self._make_star(owner=NOBODY)
        gen = TurnGenerator(self._make_state(fleet, stars=(star,)))
        assert gen._get_repair_rate(fleet, star) == 3

    def test_rate_own_planet_no_starbase(self):
        fleet = self._make_fleet(owner=1)
        star = self._make_star(owner=1)
        gen = TurnGenerator(self._make_state(fleet, stars=(star,)))
        assert gen._get_repair_rate(fleet, star) == 5

    def test_rate_own_planet_starbase_no_dock(self):
        fleet = self._make_fleet(owner=1)
        sb = self._make_starbase(owner=1, can_refuel=False)
        star = self._make_star(owner=1)
        star.starbase_key = sb.key
        gen = TurnGenerator(self._make_state(fleet, sb, stars=(star,)))
        assert gen._get_repair_rate(fleet, star) == 8

    def test_rate_own_planet_starbase_with_dock(self):
        fleet = self._make_fleet(owner=1)
        sb = self._make_starbase(owner=1, can_refuel=True)
        star = self._make_star(owner=1)
        star.starbase_key = sb.key
        gen = TurnGenerator(self._make_state(fleet, sb, stars=(star,)))
        assert gen._get_repair_rate(fleet, star) == 20

    def test_rate_zero_while_bombing_enemy_planet(self):
        """0% while bombing (TurnGenerator.cs:290 remark, canonical)."""
        fleet = self._make_fleet(owner=1, is_bomber=True)
        star = self._make_star(owner=2)
        gen = TurnGenerator(self._make_state(fleet, stars=(star,)))
        assert gen._get_repair_rate(fleet, star) == 0

    def test_rate_bomber_over_unowned_planet_repairs(self):
        """A bomber over an unowned planet is not bombing - 3%."""
        fleet = self._make_fleet(owner=1, is_bomber=True)
        star = self._make_star(owner=NOBODY)
        gen = TurnGenerator(self._make_state(fleet, stars=(star,)))
        assert gen._get_repair_rate(fleet, star) == 3

    # -- heals-others bonus (TurnGenerator.cs:297 remark, canonical) ----

    def test_heal_bonus_stopped_in_space(self):
        fleet = self._make_fleet(heals_others_percent=5)
        gen = TurnGenerator(self._make_state(fleet))
        assert gen._get_repair_rate(fleet, None) == 7

    def test_heal_bonus_orbiting_own_planet_with_dock(self):
        fleet = self._make_fleet(owner=1, heals_others_percent=5)
        sb = self._make_starbase(owner=1, can_refuel=True)
        star = self._make_star(owner=1)
        star.starbase_key = sb.key
        gen = TurnGenerator(self._make_state(fleet, sb, stars=(star,)))
        assert gen._get_repair_rate(fleet, star) == 25

    def test_heal_bonus_not_applied_while_moving(self):
        fleet = self._make_fleet(heals_others_percent=10)
        fleet.waypoints.append(Waypoint(
            position_x=500, position_y=500,
            destination="Space at 500,500", task=NoTaskObj()))
        gen = TurnGenerator(self._make_state(fleet))
        assert gen._get_repair_rate(fleet, None) == 1

    def test_heal_bonus_not_applied_while_bombing(self):
        fleet = self._make_fleet(owner=1, is_bomber=True,
                                 heals_others_percent=10)
        star = self._make_star(owner=2)
        gen = TurnGenerator(self._make_state(fleet, stars=(star,)))
        assert gen._get_repair_rate(fleet, star) == 0

    # -- repair application (TurnGenerator.cs:370-379) ------------------

    def test_repair_at_own_dock_reduces_damage_by_20_points(self):
        fleet = self._make_fleet(owner=1)
        fleet.tokens[1].damage_percent = 50.0
        sb = self._make_starbase(owner=1, can_refuel=True)
        star = self._make_star(owner=1)
        star.starbase_key = sb.key
        self._orbit(fleet, star)
        gen = TurnGenerator(self._make_state(fleet, sb, stars=(star,)))

        gen._regenerate_fleet(fleet)
        assert fleet.tokens[1].damage_percent == 30.0

        gen._regenerate_fleet(fleet)
        assert fleet.tokens[1].damage_percent == 10.0

        # Never goes negative - floors at 0.0
        gen._regenerate_fleet(fleet)
        assert fleet.tokens[1].damage_percent == 0.0

    def test_repair_minimum_one_armor_point(self):
        """C# repairs at least 1 armor point: 100/armor percent."""
        fleet = self._make_fleet(armor=20)
        fleet.tokens[1].damage_percent = 50.0
        fleet.waypoints.append(Waypoint(
            position_x=500, position_y=500,
            destination="Space at 500,500", task=NoTaskObj()))
        gen = TurnGenerator(self._make_state(fleet))

        # Rate 1 (moving) would be 1 point of 20 armor = 5 percent
        gen._regenerate_fleet(fleet)
        assert fleet.tokens[1].damage_percent == 45.0

    def test_repair_leaves_undamaged_token_unchanged(self):
        fleet = self._make_fleet(owner=1)
        star = self._make_star(owner=1)
        self._orbit(fleet, star)
        gen = TurnGenerator(self._make_state(fleet, stars=(star,)))

        gen._regenerate_fleet(fleet)
        assert fleet.tokens[1].damage_percent == 0.0

    def test_repair_does_not_mutate_cached_design_stats(self):
        fleet = self._make_fleet(owner=1, armor=100)
        fleet.tokens[1].shields = 40
        fleet.tokens[1].damage_percent = 50.0
        star = self._make_star(owner=1)
        self._orbit(fleet, star)
        gen = TurnGenerator(self._make_state(fleet, stars=(star,)))

        gen._regenerate_fleet(fleet)
        assert fleet.tokens[1].armor == 100
        assert fleet.tokens[1].shields == 40

    # -- refuel (TurnGenerator.cs:316-319) -------------------------------

    def test_refuel_at_own_starbase_with_dock(self):
        fleet = self._make_fleet(owner=1, fuel_capacity=100)
        fleet.fuel_available = 10
        sb = self._make_starbase(owner=1, can_refuel=True)
        star = self._make_star(owner=1)
        star.starbase_key = sb.key
        self._orbit(fleet, star)
        gen = TurnGenerator(self._make_state(fleet, sb, stars=(star,)))

        gen._regenerate_fleet(fleet)
        assert fleet.fuel_available == fleet.total_fuel_capacity == 100

    def test_no_refuel_at_foreign_starbase(self):
        fleet = self._make_fleet(owner=1, fuel_capacity=100)
        fleet.fuel_available = 10
        sb = self._make_starbase(owner=2, can_refuel=True)
        star = self._make_star(owner=2)
        star.starbase_key = sb.key
        self._orbit(fleet, star)
        gen = TurnGenerator(self._make_state(fleet, sb, stars=(star,)))

        gen._regenerate_fleet(fleet)
        assert fleet.fuel_available == 10

    def test_no_refuel_at_own_planet_without_starbase(self):
        fleet = self._make_fleet(owner=1, fuel_capacity=100)
        fleet.fuel_available = 10
        star = self._make_star(owner=1)
        self._orbit(fleet, star)
        gen = TurnGenerator(self._make_state(fleet, stars=(star,)))

        gen._regenerate_fleet(fleet)
        assert fleet.fuel_available == 10

    def test_no_refuel_at_own_starbase_without_dock(self):
        fleet = self._make_fleet(owner=1, fuel_capacity=100)
        fleet.fuel_available = 10
        sb = self._make_starbase(owner=1, can_refuel=False)
        star = self._make_star(owner=1)
        star.starbase_key = sb.key
        self._orbit(fleet, star)
        gen = TurnGenerator(self._make_state(fleet, sb, stars=(star,)))

        gen._regenerate_fleet(fleet)
        assert fleet.fuel_available == 10

    # -- starbase self-repair through generate() -------------------------

    def test_starbase_self_repairs_during_generate(self):
        """generate() regenerates starbases too (TurnGenerator.cs:115-117):
        a damaged dock starbase at its own planet repairs 20%/yr."""
        sb = self._make_starbase(owner=1, can_refuel=True,
                                 damage_percent=40.0)
        star = self._make_star(owner=1)
        star.starbase_key = sb.key
        self._orbit(sb, star)

        data = self._make_state(sb, stars=(star,))
        data.all_empires[1].race = MockRace()

        gen = TurnGenerator(data)
        gen.generate()

        assert sb.tokens[1].damage_percent == 20.0

    # -- out-of-fuel notice (TurnGenerator.cs:270-279) --------------------

    def test_out_of_fuel_notice(self):
        fleet = self._make_fleet(owner=1, fuel_capacity=100)
        fleet.fuel_available = 0
        data = self._make_state(fleet)
        gen = TurnGenerator(data)

        gen._process_fleet(fleet)
        assert any(m.audience == 1 and "has run out of fuel" in m.text
                   for m in data.all_messages)

    def test_no_out_of_fuel_notice_for_starbase(self):
        sb = self._make_starbase(owner=1)
        sb.fuel_available = 0
        data = self._make_state(sb)
        gen = TurnGenerator(data)

        gen._process_fleet(sb)
        assert not any("has run out of fuel" in m.text
                       for m in data.all_messages)


# --------------------------------------------------------------------------
# Battle loss summary in messages (DEF-15)
# --------------------------------------------------------------------------

class TestBattleLossSummary:
    """_execute_battles appends the C# per-empire loss summary to the
    battle message (ReportBattle, BattleEngine.cs:945-953)."""

    def _run(self, losses):
        from backend.server.battle.battle_report import BattleReport
        from backend.server.battle.stack import Stack

        data = ServerData()
        for empire_id in (1, 2):
            empire = EmpireData()
            empire.id = empire_id
            data.all_empires[empire_id] = empire

        report = BattleReport()
        report.location = "Sabik"
        report.losses = dict(losses)
        for empire_id in (1, 2):
            stack = Stack()
            stack.key = (empire_id << 32) | 1
            stack.owner = empire_id
            report.stacks[stack.key] = stack

        class FakeEngine:
            def __init__(self, server_state, battle_reports):
                self.battle_reports = battle_reports

            def run(self):
                self.battle_reports.append(report)

        TurnGenerator(data)._execute_battles(FakeEngine)
        return data

    def test_loss_summary_per_empire(self):
        data = self._run({1: 0, 2: 3})

        msgs1 = [m for m in data.all_messages if m.audience == 1]
        msgs2 = [m for m in data.all_messages if m.audience == 2]
        assert len(msgs1) == 1 and len(msgs2) == 1
        assert "A battle took place at Sabik" in msgs1[0].text
        assert "None of your ships were destroyed." in msgs1[0].text
        assert "3 of your ships were destroyed." in msgs2[0].text
        # star_name carries the location for the client Goto
        assert msgs1[0].star_name == "Sabik"

        # The full report still reaches both empires' battle_reports
        assert len(data.all_empires[1].battle_reports) == 1
        assert len(data.all_empires[2].battle_reports) == 1
        assert data.all_empires[1].battle_reports[0]["losses"] == {
            "1": 0, "2": 3}
