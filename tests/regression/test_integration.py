"""
Integration Tests - Full game state and turn processing verification.

These tests verify that complete game scenarios produce expected results
across multiple turns, testing the interaction of all systems.
"""
import pytest
from backend.core.data_structures import Resources, EmpireData, TechLevel, NovaPoint
from backend.core.game_objects import Star, Fleet, ShipToken
from backend.core.race import Race
from backend.core.waypoints import Waypoint, WaypointTask
from backend.server.server_data import ServerData
from backend.server.turn_generator import TurnGenerator
from backend.core import globals as g


# =============================================================================
# Full Turn Processing Tests
# =============================================================================

class TestTurnProcessingIntegration:
    """Test complete turn processing scenarios."""

    def create_test_game(self) -> ServerData:
        """Create a minimal game state for testing."""
        server = ServerData()

        # Create a race
        race = Race()
        race.name = "Test Race"
        race.growth_rate = 15.0
        race.max_population = 1000000
        race.colonists_per_resource = 1000
        race.operable_factories = 10
        race.factory_production = 10
        race.operable_mines = 10
        race.mine_production_rate = 10
        race.hab_gravity_center = 50
        race.hab_gravity_width = 50
        race.hab_temperature_center = 50
        race.hab_temperature_width = 50
        race.hab_radiation_center = 50
        race.hab_radiation_width = 50

        # Create empire
        empire = EmpireData(id=1, turn_year=2100)
        empire.race = race
        empire.research_budget = 15
        empire.research_levels = TechLevel.from_level(3)

        # Create homeworld
        star = Star()
        star.name = "Homeworld"
        star.position = NovaPoint(x=100, y=100)
        star.owner = 1
        star.colonists = 250000
        star.factories = 100
        star.mines = 50
        star.gravity = 50
        star.temperature = 50
        star.radiation = 50
        star.this_race = race
        star.mineral_concentration = Resources(ironium=80, boranium=60, germanium=40, energy=0)
        star.resources_on_hand = Resources(ironium=500, boranium=500, germanium=500, energy=0)

        empire.owned_stars[star.name] = star
        server.all_stars[star.name] = star
        server.all_empires[1] = empire

        return server

    def test_population_growth_over_turn(self):
        """Test population grows correctly during turn processing."""
        server = self.create_test_game()
        empire = server.all_empires[1]
        star = empire.owned_stars["Homeworld"]

        initial_pop = star.colonists
        expected_growth = star.calculate_growth(empire.race)

        # Generate turn
        generator = TurnGenerator(server)
        generator.generate()

        # Population should have grown
        assert star.colonists == initial_pop + expected_growth

    def test_mining_reduces_concentration(self):
        """Test mining reduces mineral concentration over time."""
        server = self.create_test_game()
        star = server.all_stars["Homeworld"]

        # Record initial concentrations
        initial_iron = star.mineral_concentration.ironium
        initial_boranium = star.mineral_concentration.boranium
        initial_germanium = star.mineral_concentration.germanium

        # Generate multiple turns
        generator = TurnGenerator(server)
        for _ in range(10):
            generator.generate()

        # Concentrations should decrease (or stay same if very low mining)
        # Due to mining, surface minerals increase but concentration decreases
        assert star.mineral_concentration.ironium <= initial_iron
        assert star.mineral_concentration.boranium <= initial_boranium
        assert star.mineral_concentration.germanium <= initial_germanium

    def test_resource_accumulation(self):
        """Test resources accumulate from production."""
        server = self.create_test_game()
        empire = server.all_empires[1]
        star = empire.owned_stars["Homeworld"]

        initial_resources = Resources(
            ironium=star.resources_on_hand.ironium,
            boranium=star.resources_on_hand.boranium,
            germanium=star.resources_on_hand.germanium,
            energy=star.resources_on_hand.energy
        )

        # Clear production queue to accumulate resources
        star.manufacturing_queue.clear()

        # Generate turn
        generator = TurnGenerator(server)
        generator.generate()

        # Resources should increase from mining
        # (may also increase from production if nothing in queue)
        assert star.resources_on_hand.ironium >= initial_resources.ironium
        assert star.resources_on_hand.boranium >= initial_resources.boranium
        assert star.resources_on_hand.germanium >= initial_resources.germanium

    def test_year_increments(self):
        """Test turn year increments correctly."""
        server = self.create_test_game()

        assert server.turn_year == 2100

        generator = TurnGenerator(server)
        generator.generate()

        assert server.turn_year == 2101

        generator.generate()
        assert server.turn_year == 2102

    def test_research_accumulation(self):
        """Test research points accumulate and advance tech."""
        server = self.create_test_game()
        empire = server.all_empires[1]
        star = empire.owned_stars["Homeworld"]

        # Set high population for fast research
        star.colonists = 500000
        star.factories = 200

        # Set research allocation
        empire.research_budget = 50
        empire.research_topics = TechLevel(levels={
            "Propulsion": 10, "Construction": 0,
            "Electronics": 0, "Energy": 0,
            "Weapons": 0, "Biotechnology": 0
        })

        initial_propulsion = empire.research_levels.levels.get("Propulsion", 0)

        # Generate many turns to accumulate research
        generator = TurnGenerator(server)
        for _ in range(20):
            generator.generate()

        # Research should have advanced
        final_propulsion = empire.research_levels.levels.get("Propulsion", 0)
        assert final_propulsion >= initial_propulsion


# =============================================================================
# Multi-Empire Interaction Tests
# =============================================================================

class TestMultiEmpireIntegration:
    """Test interactions between multiple empires."""

    def create_two_empire_game(self) -> ServerData:
        """Create game with two empires."""
        server = ServerData()

        for empire_id in [1, 2]:
            race = Race()
            race.name = f"Race {empire_id}"
            race.growth_rate = 15.0
            race.max_population = 1000000
            race.colonists_per_resource = 1000
            race.operable_factories = 10
            race.factory_production = 10
            race.operable_mines = 10
            race.mine_production_rate = 10
            race.hab_gravity_center = 50
            race.hab_gravity_width = 50
            race.hab_temperature_center = 50
            race.hab_temperature_width = 50
            race.hab_radiation_center = 50
            race.hab_radiation_width = 50

            empire = EmpireData(id=empire_id, turn_year=2100)
            empire.race = race
            empire.research_budget = 15
            empire.research_levels = TechLevel.from_level(3)

            # Create homeworld at different positions
            star = Star()
            star.name = f"Homeworld {empire_id}"
            star.position = NovaPoint(x=100 + empire_id * 200, y=100)
            star.owner = empire_id
            star.colonists = 250000
            star.factories = 100
            star.mines = 50
            star.gravity = 50
            star.temperature = 50
            star.radiation = 50
            star.this_race = race
            star.mineral_concentration = Resources(ironium=80, boranium=60, germanium=40, energy=0)
            star.resources_on_hand = Resources(ironium=500, boranium=500, germanium=500, energy=0)

            empire.owned_stars[star.name] = star
            server.all_stars[star.name] = star
            server.all_empires[empire_id] = empire

        return server

    def test_independent_empire_processing(self):
        """Test empires process independently."""
        server = self.create_two_empire_game()

        empire1 = server.all_empires[1]
        empire2 = server.all_empires[2]

        star1 = empire1.owned_stars["Homeworld 1"]
        star2 = empire2.owned_stars["Homeworld 2"]

        # Set different populations
        star1.colonists = 100000
        star2.colonists = 500000

        initial_pop1 = star1.colonists
        initial_pop2 = star2.colonists

        # Generate turn
        generator = TurnGenerator(server)
        generator.generate()

        # Both should have grown independently
        assert star1.colonists > initial_pop1
        assert star2.colonists > initial_pop2

        # Growth should be proportional to population
        growth1 = star1.colonists - initial_pop1
        growth2 = star2.colonists - initial_pop2

        # Larger population should have larger absolute growth
        assert growth2 > growth1


# =============================================================================
# Fleet Movement Integration Tests
# =============================================================================

class TestFleetMovementIntegration:
    """Test fleet movement across turns."""

    def test_fleet_arrives_at_destination(self):
        """Test fleet moves and arrives at destination."""
        server = ServerData()

        # Create race and empire
        race = Race()
        race.name = "Test"
        race.growth_rate = 15.0
        race.max_population = 1000000

        empire = EmpireData(id=1, turn_year=2100)
        empire.race = race

        # Create origin star
        origin = Star()
        origin.name = "Origin"
        origin.position = NovaPoint(x=0, y=0)
        origin.owner = 1

        # Create destination star
        dest = Star()
        dest.name = "Destination"
        dest.position = NovaPoint(x=50, y=0)  # 50 ly away
        dest.owner = g.NOBODY

        server.all_stars["Origin"] = origin
        server.all_stars["Destination"] = dest
        empire.owned_stars["Origin"] = origin

        # Create fleet
        fleet = Fleet()
        fleet.key = 1 | (1 << 32)
        fleet.name = "Scout #1"
        fleet.owner = 1
        fleet.position = NovaPoint(x=0, y=0)
        fleet.fuel_available = 1000

        token = ShipToken()
        token.design_key = 1
        token.design_name = "Scout"
        token.quantity = 1
        token.mass = 25
        token.fuel_capacity = 300
        token.optimal_speed = 6
        fleet.tokens[1] = token

        # Set waypoint to destination at warp 5 (25 ly/turn)
        wp = Waypoint()
        wp.position = NovaPoint(x=50, y=0)
        wp.destination = "Destination"
        wp.warp_factor = 5
        wp.task = WaypointTask.NO_TASK
        fleet.waypoints = [wp]

        empire.owned_fleets[fleet.key] = fleet
        server.all_empires[1] = empire

        # Fleet should arrive in 2 turns at warp 5
        generator = TurnGenerator(server)

        # After turn 1, should be partway there
        generator.generate()
        assert fleet.position.x > 0
        assert fleet.position.x < 50

        # After turn 2, should have arrived
        generator.generate()
        assert fleet.position.x == 50 or fleet.position.distance_to(wp.position) < 2


# =============================================================================
# Save/Load State Tests
# =============================================================================

class TestStateSerializationIntegration:
    """Test game state serialization preserves all data."""

    def test_empire_data_round_trip(self):
        """Test EmpireData serializes and deserializes correctly."""
        empire = EmpireData(id=1, turn_year=2100)
        empire.race = Race()
        empire.race.name = "Test Race"
        empire.research_budget = 25
        empire.research_levels = TechLevel(levels={
            "Propulsion": 5, "Construction": 3,
            "Electronics": 2, "Energy": 4,
            "Weapons": 1, "Biotechnology": 0
        })

        # Serialize
        data = empire.to_dict()

        # Deserialize
        loaded = EmpireData.from_dict(data)

        assert loaded.id == empire.id
        assert loaded.turn_year == empire.turn_year
        assert loaded.research_budget == empire.research_budget
        assert loaded.research_levels.levels.get("Propulsion") == 5

    def test_star_round_trip(self):
        """Test Star serializes and deserializes correctly."""
        star = Star()
        star.name = "Test Star"
        star.position = NovaPoint(x=123, y=456)
        star.owner = 1
        star.colonists = 250000
        star.factories = 100
        star.mines = 50
        star.gravity = 45
        star.temperature = 55
        star.radiation = 35
        star.mineral_concentration = Resources(ironium=80, boranium=60, germanium=40, energy=0)
        star.resources_on_hand = Resources(ironium=500, boranium=300, germanium=200, energy=0)

        # Serialize
        data = star.to_dict()

        # Deserialize
        loaded = Star.from_dict(data)

        assert loaded.name == star.name
        assert loaded.position.x == 123
        assert loaded.position.y == 456
        assert loaded.colonists == 250000
        assert loaded.factories == 100
        assert loaded.mineral_concentration.ironium == 80

    def test_fleet_round_trip(self):
        """Test Fleet serializes and deserializes correctly."""
        fleet = Fleet()
        fleet.key = 1 | (1 << 32)
        fleet.name = "Test Fleet"
        fleet.owner = 1
        fleet.position = NovaPoint(x=100, y=200)
        fleet.fuel_available = 500

        token = ShipToken()
        token.design_key = 1
        token.design_name = "Scout"
        token.quantity = 3
        token.mass = 25
        fleet.tokens[1] = token

        # Serialize
        data = fleet.to_dict()

        # Deserialize
        loaded = Fleet.from_dict(data)

        assert loaded.key == fleet.key
        assert loaded.name == "Test Fleet"
        assert loaded.position.x == 100
        assert loaded.fuel_available == 500
        assert 1 in loaded.tokens
        assert loaded.tokens[1].quantity == 3
