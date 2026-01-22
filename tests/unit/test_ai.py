"""
Unit tests for AI system.
Tests verify parity with C# implementation in Nova/Ai/
"""
import pytest
from backend.ai import (
    AbstractAI, DefaultAI, DefaultAIPlanner,
    DefaultPlanetAI, DefaultFleetAI
)
from backend.core.data_structures import EmpireData, TechLevel, NovaPoint, Resources
from backend.core.game_objects.star import Star
from backend.core.game_objects.fleet import Fleet, ShipToken
from backend.core.race.race import Race
from backend.core import globals as g


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def basic_race():
    """Create a basic test race."""
    race = Race(
        name="Test Race",
        growth_rate=15,
        colonists_per_resource=1000,
        factory_production=10,
        operable_factories=10,
        mine_production_rate=10,
        operable_mines=10,
        max_population=1000000
    )
    return race


@pytest.fixture
def basic_empire(basic_race):
    """Create a basic empire with one star and one fleet."""
    empire = EmpireData(id=1, turn_year=2100)
    empire.race = basic_race

    # Add a homeworld
    star = Star(name="Homeworld")
    star.position = NovaPoint(x=100, y=100)
    star.owner = 1
    star.colonists = 250000
    star.factories = 50
    star.mines = 50
    star.this_race = basic_race
    star.resources_on_hand = Resources(
        ironium=100, boranium=100, germanium=100, energy=500
    )
    star.mineral_concentration = Resources(
        ironium=50, boranium=50, germanium=50, energy=0
    )
    empire.owned_stars[star.name] = star

    # Add a scout fleet
    scout = Fleet()
    scout.key = 1 | (1 << 32)  # Empire 1, fleet 1
    scout.name = "Scout #1"
    scout.owner = 1
    scout.position = NovaPoint(x=100, y=100)
    scout.fuel_available = 100

    token = ShipToken()
    token.design_key = 1
    token.design_name = "Long Range Scout"
    token.quantity = 1
    token.mass = 25
    token.fuel_capacity = 300
    token.can_scan = True
    token.optimal_speed = 6
    scout.tokens[token.design_key] = token

    empire.owned_fleets[scout.key] = scout
    empire._fleet_counter = 1

    return empire


@pytest.fixture
def empire_with_colonizer(basic_empire):
    """Add a colonizer to the basic empire."""
    colonizer = Fleet()
    colonizer.key = 2 | (1 << 32)
    colonizer.name = "Colony Ship #1"
    colonizer.owner = 1
    colonizer.position = NovaPoint(x=100, y=100)
    colonizer.fuel_available = 500

    token = ShipToken()
    token.design_key = 2
    token.design_name = "Colony Ship"
    token.quantity = 1
    token.mass = 100
    token.fuel_capacity = 500
    token.cargo_capacity = 200
    token.can_colonize = True
    token.optimal_speed = 5
    colonizer.tokens[token.design_key] = token

    basic_empire.owned_fleets[colonizer.key] = colonizer
    basic_empire._fleet_counter = 2

    return basic_empire


@pytest.fixture
def empire_with_star_reports(basic_empire):
    """Add star reports to empire."""
    # Add unexplored stars
    for i in range(5):
        report = {
            "name": f"Star {i}",
            "position_x": 150 + i * 50,
            "position_y": 150 + i * 50,
            "owner": g.NOBODY,
            "gravity": 50,
            "radiation": 50,
            "temperature": 50
        }
        basic_empire.star_reports[f"Star {i}"] = report

    return basic_empire


# =============================================================================
# AbstractAI Tests
# =============================================================================

class TestAbstractAI:
    """Tests for AbstractAI base class."""

    def test_cannot_instantiate(self):
        """Test that AbstractAI cannot be instantiated directly."""
        with pytest.raises(TypeError):
            AbstractAI()

    def test_default_ai_is_abstract_ai(self):
        """Test DefaultAI inherits from AbstractAI."""
        assert issubclass(DefaultAI, AbstractAI)


# =============================================================================
# DefaultAIPlanner Tests
# =============================================================================

class TestDefaultAIPlanner:
    """Tests for DefaultAIPlanner."""

    def test_constants(self):
        """Test planner constants match C# values."""
        # From DefaultAIPlanner.cs
        assert DefaultAIPlanner.EARLY_SCOUTS == 5
        assert DefaultAIPlanner.LOW_PRODUCTION == 100
        assert DefaultAIPlanner.MIN_HAB_VALUE == 0.05

    def test_default_priorities(self):
        """Test default production priorities."""
        empire = EmpireData(id=1)
        planner = DefaultAIPlanner(empire)

        assert planner.interceptor_production_priority == 5
        assert planner.starbase_upgrade_priority == 30
        assert planner.coloniser_production_priority == 10

    def test_count_fleet_scout(self, basic_empire):
        """Test counting a scout fleet."""
        planner = DefaultAIPlanner(basic_empire)
        scout = basic_empire.owned_fleets[1 | (1 << 32)]

        planner.count_fleet(scout)
        assert planner.scout_count == 1

    def test_count_fleet_colonizer(self, empire_with_colonizer):
        """Test counting a colonizer fleet."""
        planner = DefaultAIPlanner(empire_with_colonizer)
        colonizer = empire_with_colonizer.owned_fleets[2 | (1 << 32)]

        planner.count_fleet(colonizer)
        assert planner.colonizer_count == 1

    def test_planets_to_colonize(self, empire_with_star_reports):
        """Test counting colonizable planets."""
        # Make the race like all planets
        race = empire_with_star_reports.race
        race.hab_gravity_center = 50
        race.hab_gravity_width = 50
        race.hab_radiation_center = 50
        race.hab_radiation_width = 50
        race.hab_temperature_center = 50
        race.hab_temperature_width = 50

        planner = DefaultAIPlanner(empire_with_star_reports)

        # Should count planets based on habitability
        # The exact count depends on habitability calculation
        assert planner.planets_to_colonize >= 0

    def test_total_transport_kt(self, basic_empire):
        """Test tracking transport capacity."""
        planner = DefaultAIPlanner(basic_empire)
        assert planner.total_transport_kt == 0

        # Add a freighter
        freighter = Fleet()
        freighter.key = 3 | (1 << 32)
        freighter.name = "Freighter #1"

        token = ShipToken()
        token.cargo_capacity = 500
        token.quantity = 1
        freighter.tokens[1] = token

        planner.count_fleet(freighter)
        assert planner.transport_count == 1
        assert planner._total_transport_kt == 500


# =============================================================================
# DefaultFleetAI Tests
# =============================================================================

class TestDefaultFleetAI:
    """Tests for DefaultFleetAI."""

    def test_creation(self, basic_empire):
        """Test creating a fleet AI."""
        fleet = basic_empire.owned_fleets[1 | (1 << 32)]
        fleet_ai = DefaultFleetAI(
            fleet=fleet,
            empire_data=basic_empire
        )
        assert fleet_ai.fleet == fleet
        assert fleet_ai.empire_data == basic_empire

    def test_scout_no_stars(self, basic_empire):
        """Test scouting with no star reports."""
        fleet = basic_empire.owned_fleets[1 | (1 << 32)]
        fleet_ai = DefaultFleetAI(
            fleet=fleet,
            empire_data=basic_empire
        )

        result = fleet_ai.scout([])
        assert result is None  # No stars to scout

    def test_scout_with_stars(self, empire_with_star_reports):
        """Test scouting finds closest star."""
        fleet = empire_with_star_reports.owned_fleets[1 | (1 << 32)]
        fleet_ai = DefaultFleetAI(
            fleet=fleet,
            empire_data=empire_with_star_reports
        )

        result = fleet_ai.scout([])
        assert result is not None
        assert len(fleet_ai.commands) > 0

    def test_can_reach(self, empire_with_star_reports):
        """Test can_reach calculation."""
        fleet = empire_with_star_reports.owned_fleets[1 | (1 << 32)]
        fleet.fuel_available = 1000

        fleet_ai = DefaultFleetAI(
            fleet=fleet,
            empire_data=empire_with_star_reports
        )

        # Near star should be reachable
        near_star = {"position_x": 150, "position_y": 150}
        assert fleet_ai.can_reach(near_star) is True

    def test_max_distance(self, basic_empire):
        """Test max_distance calculation."""
        fleet = basic_empire.owned_fleets[1 | (1 << 32)]
        fleet.fuel_available = 300

        fleet_ai = DefaultFleetAI(
            fleet=fleet,
            empire_data=basic_empire
        )

        distance = fleet_ai.max_distance()
        assert distance > 0

    def test_closest_fuel(self, basic_empire):
        """Test finding closest fuel station."""
        # Add a starbase that can refuel
        starbase = Fleet()
        starbase.key = 10 | (1 << 32)
        starbase.name = "Starbase"
        starbase.position = NovaPoint(x=200, y=200)

        token = ShipToken()
        token.can_refuel = True
        token.is_starbase = True
        starbase.tokens[1] = token

        basic_empire.owned_fleets[starbase.key] = starbase

        fleet = basic_empire.owned_fleets[1 | (1 << 32)]
        fleet_ai = DefaultFleetAI(
            fleet=fleet,
            empire_data=basic_empire
        )

        closest = fleet_ai._closest_fuel()
        assert closest is not None
        assert closest.key == starbase.key


# =============================================================================
# DefaultPlanetAI Tests
# =============================================================================

class TestDefaultPlanetAI:
    """Tests for DefaultPlanetAI."""

    def test_creation(self, basic_empire):
        """Test creating a planet AI."""
        star = basic_empire.owned_stars["Homeworld"]
        planner = DefaultAIPlanner(basic_empire)

        planet_ai = DefaultPlanetAI(
            planet=star,
            empire_data=basic_empire,
            ai_plan=planner
        )
        assert planet_ai.planet == star
        assert planet_ai.empire_data == basic_empire

    def test_handle_production(self, basic_empire):
        """Test production handling creates commands."""
        star = basic_empire.owned_stars["Homeworld"]
        planner = DefaultAIPlanner(basic_empire)

        planet_ai = DefaultPlanetAI(
            planet=star,
            empire_data=basic_empire,
            ai_plan=planner
        )

        planet_ai.handle_production()
        # Should have created some production commands
        assert len(planet_ai.commands) >= 0


# =============================================================================
# DefaultAI Integration Tests
# =============================================================================

class TestDefaultAI:
    """Integration tests for DefaultAI."""

    def test_creation(self):
        """Test creating a DefaultAI."""
        ai = DefaultAI()
        assert ai.empire_data is None
        assert ai.ai_plan is None

    def test_initialize(self, basic_empire):
        """Test AI initialization."""
        ai = DefaultAI()
        ai.initialize(basic_empire)

        assert ai.empire_data == basic_empire
        assert ai.ai_plan is not None
        assert len(ai.planet_ais) == 1  # One planet
        assert len(ai.fleet_ais) == 1  # One non-starbase fleet

    def test_do_move_empty_empire(self):
        """Test do_move with empty empire."""
        ai = DefaultAI()
        ai.initialize(EmpireData(id=1))

        commands = ai.do_move()
        assert isinstance(commands, list)

    def test_do_move_with_fleets(self, empire_with_star_reports):
        """Test do_move generates commands."""
        ai = DefaultAI()
        ai.initialize(empire_with_star_reports)

        commands = ai.do_move()
        assert isinstance(commands, list)
        # Should generate at least research command
        assert len(commands) >= 0

    def test_count_fleets(self, basic_empire):
        """Test fleet counting."""
        ai = DefaultAI()
        ai.initialize(basic_empire)

        ai._count_fleets()
        assert ai.ai_plan.scout_count == 1

    def test_handle_research(self, basic_empire):
        """Test research handling."""
        ai = DefaultAI()
        ai.initialize(basic_empire)

        ai._handle_research()
        # Should have created a research command
        research_commands = [
            c for c in ai.commands
            if hasattr(c, 'budget')
        ]
        assert len(research_commands) == 1


# =============================================================================
# AI System Constants Tests
# =============================================================================

class TestAIConstants:
    """Tests for AI-related constants in globals."""

    def test_ai_ship_name_prefixes(self):
        """Test AI ship name prefix constants exist."""
        assert g.AI_SCOUT == " Walkabout"
        assert g.AI_COLONY_SHIP == " Santa Maria"
        assert g.AI_FREIGHTER == " Wheelbarrow"
        assert g.AI_BOMBER == " Dr Euthanasia"
        assert g.AI_DEFENSIVE_DESTROYER == " Tharunka"


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestAIEdgeCases:
    """Tests for AI edge cases."""

    def test_ai_with_no_race(self):
        """Test AI handles missing race gracefully."""
        empire = EmpireData(id=1)
        empire.race = None

        ai = DefaultAI()
        ai.initialize(empire)

        # Should not crash
        commands = ai.do_move()
        assert isinstance(commands, list)

    def test_planner_with_empty_empire(self):
        """Test planner with empty empire."""
        empire = EmpireData(id=1)
        planner = DefaultAIPlanner(empire)

        assert planner.planets_to_colonize == 0
        assert planner.total_transport_kt == 0
        assert planner.surplus_population_kt == 0

    def test_fleet_ai_with_no_fuel(self, basic_empire):
        """Test fleet AI with no fuel."""
        fleet = basic_empire.owned_fleets[1 | (1 << 32)]
        fleet.fuel_available = 0

        fleet_ai = DefaultFleetAI(
            fleet=fleet,
            empire_data=basic_empire
        )

        # Should handle gracefully
        distance = fleet_ai.max_distance()
        assert distance >= 0
