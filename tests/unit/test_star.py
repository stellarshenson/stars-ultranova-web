"""
Unit tests for Star class.
Tests verify parity with C# implementation in Common/GameObjects/Star.cs
"""
import pytest
from backend.core.game_objects import Star, ItemType
from backend.core.data_structures import Resources, NovaPoint
from backend.core.race import Race
from backend.core.globals import (
    COLONISTS_PER_OPERABLE_FACTORY_UNIT,
    COLONISTS_PER_OPERABLE_MINING_UNIT,
    FACTORIES_PER_FACTORY_PRODUCTION_UNIT,
    MINES_PER_MINE_PRODUCTION_UNIT,
    BASE_CROWDING_FACTOR,
    POPULATION_FACTOR_HYPER_EXPANSION,
    GROWTH_FACTOR_HYPER_EXPANSION,
    MAX_DEFENSES
)


class TestStar:
    """Tests for Star class."""

    def create_default_star(self) -> Star:
        """Create a star with default test values."""
        star = Star()
        star.name = "Test Star"
        star.colonists = 100000
        star.factories = 50
        star.mines = 30
        star.gravity = 50
        star.temperature = 50
        star.radiation = 50
        star.mineral_concentration = Resources.from_ibge(50, 50, 50, 0)
        star.resources_on_hand = Resources.from_ibge(100, 100, 100, 0)
        return star

    def create_default_race(self) -> Race:
        """Create a race with default test values."""
        race = Race()
        race.name = "Test Race"
        race.growth_rate = 15.0
        race.colonists_per_resource = 1000
        race.operable_factories = 10
        race.factory_production = 10
        race.operable_mines = 10
        race.mine_production_rate = 10
        race.gravity_min = 15
        race.gravity_max = 85
        race.temperature_min = 15
        race.temperature_max = 85
        race.radiation_min = 15
        race.radiation_max = 85
        return race

    def test_default_constructor(self):
        """Test default constructor sets correct type."""
        star = Star()
        assert star.item_type == ItemType.STAR
        assert star.colonists == 0
        assert star.factories == 0

    def test_key_is_name(self):
        """Test that star key is the name."""
        # Port of: Star.cs lines 593-599
        star = Star()
        star.name = "Alpha Centauri"
        assert star.key == "Alpha Centauri"

    def test_defenses_capped(self):
        """Test defenses are capped at MAX_DEFENSES."""
        # Port of: Star.cs lines 526-552
        star = Star()
        star.defenses = 200
        assert star.defenses == MAX_DEFENSES

    def test_get_operable_factories_no_race(self):
        """Test operable factories returns 0 without race."""
        # Port of: Star.cs lines 94-108
        star = self.create_default_star()
        assert star.get_operable_factories() == 0

    def test_get_operable_factories(self):
        """Test operable factories calculation."""
        # Port of: Star.cs lines 94-108
        # Formula: colonists / COLONISTS_PER_OPERABLE_FACTORY_UNIT * race.operable_factories
        star = self.create_default_star()
        race = self.create_default_race()
        star.this_race = race

        # 100000 / 10000 * 10 = 100
        assert star.get_operable_factories() == 100

    def test_get_factories_in_use(self):
        """Test factories in use is min of actual and operable."""
        # Port of: Star.cs lines 166-170
        star = self.create_default_star()
        race = self.create_default_race()
        star.this_race = race

        # Operable = 100, actual = 50 -> in use = 50
        assert star.get_factories_in_use() == 50

    def test_get_operable_mines(self):
        """Test operable mines calculation."""
        # Port of: Star.cs lines 132-142
        star = self.create_default_star()
        race = self.create_default_race()
        star.this_race = race

        # 100000 / 10000 * 10 = 100
        assert star.get_operable_mines() == 100

    def test_get_resource_rate(self):
        """Test resource rate calculation."""
        # Port of: Star.cs lines 186-199
        star = self.create_default_star()
        race = self.create_default_race()
        star.this_race = race

        # From colonists: 100000 / 1000 = 100
        # From factories: (50 / 10) * 10 = 50
        # Total: 150
        assert star.get_resource_rate() == 150

    def test_get_mining_rate(self):
        """Test mining rate calculation."""
        # Port of: Star.cs lines 227-242
        star = self.create_default_star()
        race = self.create_default_race()
        star.this_race = race

        # Mines in use = 30 (actual < operable)
        # Rate = (30 / 10) * 10 * (50 / 100.0) = 3 * 10 * 0.5 = 15
        assert star.get_mining_rate(50) == 15

    def test_capacity(self):
        """Test capacity calculation."""
        # Port of: Star.cs lines 299-317
        star = self.create_default_star()
        race = self.create_default_race()

        # 100000 / 1000000 * 100 = 10%
        assert star.capacity(race) == 10

    def test_capacity_hyper_expansion(self):
        """Test capacity with Hyper Expansion trait."""
        star = self.create_default_star()
        race = self.create_default_race()
        race.traits.add("HyperExpansion")

        # max_pop = 1000000 * 0.5 = 500000
        # capacity = 100000 / 500000 * 100 = 20%
        assert star.capacity(race) == 20

    def test_calculate_growth_low_pop(self):
        """Test growth calculation for low population."""
        # Port of: Star.cs lines 346-350
        star = self.create_default_star()
        star.colonists = 10000
        race = self.create_default_race()

        # Full growth rate applies: colonists * growth_rate / 100 * hab_value
        hab_value = race.hab_value(star)
        expected = int(10000 * 15.0 / 100 * hab_value)
        expected = (expected // 100) * 100  # Round to 100s

        assert star.calculate_growth(race) == expected

    def test_calculate_growth_crowded(self):
        """Test growth with crowding penalty."""
        # Port of: Star.cs lines 351-357
        star = self.create_default_star()
        star.colonists = 500000  # 50% capacity
        race = self.create_default_race()

        capacity = star.capacity(race) / 100.0
        hab_value = race.hab_value(star)
        base_growth = star.colonists * race.growth_rate / 100.0 * hab_value
        crowding_factor = BASE_CROWDING_FACTOR * (1.0 - capacity) ** 2
        expected = int(base_growth * crowding_factor)
        expected = (expected // 100) * 100

        assert star.calculate_growth(race) == expected

    def test_calculate_growth_full_planet(self):
        """Test no growth at full capacity."""
        # Port of: Star.cs lines 358-362
        star = self.create_default_star()
        star.colonists = 1000000  # 100% capacity
        race = self.create_default_race()

        assert star.calculate_growth(race) == 0

    def test_calculate_growth_over_capacity(self):
        """Test population loss over capacity."""
        # Port of: Star.cs lines 363-367
        star = self.create_default_star()
        star.colonists = 2000000  # 200% capacity
        race = self.create_default_race()

        # 4% loss per 1% over 100%
        capacity = star.capacity(race) / 100.0  # 2.0
        expected = int(star.colonists * (capacity - 1) * -4.0 / 100.0)
        expected = (expected // 100) * 100

        assert star.calculate_growth(race) == expected

    def test_update_population(self):
        """Test population update."""
        # Port of: Star.cs lines 413-416
        star = self.create_default_star()
        race = self.create_default_race()
        star.this_race = race

        initial = star.colonists
        expected_growth = star.calculate_growth(race)
        star.update_population(race)

        assert star.colonists == initial + expected_growth

    def test_update_research(self):
        """Test research allocation update."""
        # Port of: Star.cs lines 422-435
        star = self.create_default_star()
        race = self.create_default_race()
        star.this_race = race

        resource_rate = star.get_resource_rate()
        star.update_research(20)  # 20% budget

        assert star.research_allocation == (resource_rate * 20) // 100

    def test_update_research_only_leftover(self):
        """Test research with only_leftover flag."""
        star = self.create_default_star()
        race = self.create_default_race()
        star.this_race = race
        star.only_leftover = True

        star.update_research(20)
        assert star.research_allocation == 0

    def test_update_resources(self):
        """Test resource update."""
        # Port of: Star.cs lines 443-461
        star = self.create_default_star()
        race = self.create_default_race()
        star.this_race = race

        resource_rate = star.get_resource_rate()
        star.research_allocation = 30
        star.update_resources()

        assert star.resources_on_hand.energy == resource_rate - 30

    def test_serialization_roundtrip(self):
        """Test to_dict/from_dict roundtrip."""
        star = self.create_default_star()
        star.position = NovaPoint(x=100, y=200)

        data = star.to_dict()
        star2 = Star.from_dict(data)

        assert star2.name == star.name
        assert star2.colonists == star.colonists
        assert star2.factories == star.factories
        assert star2.position.x == star.position.x
        assert star2.position.y == star.position.y
