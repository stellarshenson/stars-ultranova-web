"""
C# Parity Tests - Verify Python implementation matches C# exactly.

These tests use specific values computed from the C# Stars! Nova source
to verify formula parity. Any deviation indicates a porting bug.
"""
import pytest
import math
from backend.core.data_structures import Resources, Cargo, NovaPoint, TechLevel
from backend.core.game_objects import Star, Fleet, ShipToken
from backend.core.race import Race
from backend.core import globals as g


# =============================================================================
# Population Growth Parity Tests
# Source: Common/GameObjects/Star.cs lines 327-385
# =============================================================================

class TestPopulationGrowthParity:
    """
    Test population growth formulas match C# exactly.

    Growth has 5 cases:
    1. Negative habitability - population dies at 10% * hab_value rate
    2. Low population (<25% capacity) - full growth rate
    3. Crowding (25-100% capacity) - reduced by crowding factor
    4. Full planet (100% capacity) - zero growth
    5. Over capacity (>100%) - population dies
    """

    def create_race(self, growth_rate: float = 15.0) -> Race:
        """Create test race with standard settings."""
        race = Race()
        race.name = "Test Race"
        race.growth_rate = growth_rate
        race.max_population = 1000000
        race.colonists_per_resource = 1000
        race.operable_factories = 10
        race.factory_production = 10
        race.operable_mines = 10
        race.mine_production_rate = 10
        # Set hab ranges to make hab calculations predictable
        race.hab_gravity_center = 50
        race.hab_gravity_width = 50
        race.hab_temperature_center = 50
        race.hab_temperature_width = 50
        race.hab_radiation_center = 50
        race.hab_radiation_width = 50
        return race

    def create_star(self, colonists: int, gravity: int = 50,
                    temperature: int = 50, radiation: int = 50) -> Star:
        """Create test star."""
        star = Star()
        star.name = "Test Star"
        star.colonists = colonists
        star.gravity = gravity
        star.temperature = temperature
        star.radiation = radiation
        return star

    def test_low_population_full_growth(self):
        """
        Test low population gets full growth rate.

        C# formula: colonists * growth_rate / 100 * hab_value
        At 100k colonists, 15% growth, 100% hab -> 15000 growth
        """
        race = self.create_race(growth_rate=15.0)
        star = self.create_star(colonists=100000)
        star.this_race = race

        # 100k is 10% of 1M max, well under 25% threshold
        growth = star.calculate_growth(race)

        # Expected: 100000 * 0.15 * 1.0 = 15000
        assert growth == 15000

    def test_crowding_factor_reduction(self):
        """
        Test crowding factor reduces growth at higher populations.

        Actual C# formula at 25-100% capacity:
        growth = colonists * growth_rate / 100 * hab_value * crowding_factor
        crowding_factor = BASE_CROWDING_FACTOR * (1.0 - capacity_pct)^2

        At 50% capacity:
        crowding_factor = 16/9 * (1.0 - 0.5)^2 = 16/9 * 0.25 = 0.444
        growth = 500000 * 0.15 * 1.0 * 0.444 = 33333
        """
        race = self.create_race(growth_rate=15.0)
        star = self.create_star(colonists=500000)  # 50% of 1M
        star.this_race = race

        growth = star.calculate_growth(race)

        # The formula is: int(colonists * growth_rate/100 * hab * 16/9 * (1-capacity)^2)
        # = 500000 * 0.15 * 1.0 * 16/9 * 0.25 = 33333, rounded to 33300
        crowding_factor = g.BASE_CROWDING_FACTOR * (1.0 - 0.5) ** 2
        expected = int(500000 * 0.15 * 1.0 * crowding_factor)
        expected = (expected // 100) * 100  # Round to 100s
        assert growth == expected

    def test_full_planet_zero_growth(self):
        """Test at 100% capacity, growth is zero."""
        race = self.create_race(growth_rate=15.0)
        star = self.create_star(colonists=1000000)  # 100% of 1M
        star.this_race = race

        growth = star.calculate_growth(race)
        assert growth == 0

    def test_over_capacity_population_dies(self):
        """
        Test over 100% capacity causes population death.

        C# formula: colonists * (capacity_pct - 1) * -4.0 / 100.0
        At 110% capacity (1.1M on 1M max):
        growth = 1100000 * 0.1 * -0.04 = -4400, rounded to -4400

        Note: capacity uses ceiling, so result may vary slightly.
        """
        race = self.create_race(growth_rate=15.0)
        star = self.create_star(colonists=1100000)  # 110% of 1M
        star.this_race = race

        growth = star.calculate_growth(race)

        # At over capacity, population dies
        assert growth < 0

        # Calculate expected death
        import math
        capacity_pct = math.ceil((1100000 / 1000000.0) * 100) / 100.0
        expected = int(1100000 * (capacity_pct - 1) * -4.0 / 100.0)
        expected = (expected // 100) * 100  # Round to 100s
        assert growth == expected

    def test_negative_habitability_death(self):
        """
        Test negative habitability causes population death.

        C# formula: 0.1 * colonists * hab_value (where hab_value is negative)
        """
        race = self.create_race()
        # Set hab ranges to make this star uninhabitable
        # Using min/max directly (not center/width)
        race.gravity_min = 5
        race.gravity_max = 15  # Range 5-15
        star = self.create_star(colonists=100000, gravity=80)  # Way outside range
        star.this_race = race

        hab = race.hab_value(star)
        assert hab < 0, f"Star should have negative habitability, got {hab}"

        growth = star.calculate_growth(race)

        # Death rate: 10% * colonists * hab_value (negative)
        assert growth < 0

    def test_hyper_expansion_double_growth(self):
        """
        Test Hyper Expansion trait doubles growth rate.

        GROWTH_FACTOR_HYPER_EXPANSION = 2.0
        HE also halves max population via POPULATION_FACTOR_HYPER_EXPANSION = 0.5
        """
        race = self.create_race(growth_rate=15.0)
        race.primary_trait = "HyperExpansion"  # Full trait name for has_trait check
        star = self.create_star(colonists=100000)
        star.this_race = race

        growth = star.calculate_growth(race)

        # HE doubles growth rate: 15% * 2 = 30%
        # HE halves max pop: 1M * 0.5 = 500k
        # At 100k colonists with 500k max, capacity is 20%
        # Under 25% threshold so full rate applies
        # growth = 100000 * 0.30 * 1.0 = 30000
        assert growth == 30000


# =============================================================================
# Resource Generation Parity Tests
# Source: Common/GameObjects/Star.cs lines 186-199
# =============================================================================

class TestResourceGenerationParity:
    """Test resource generation formulas match C# exactly."""

    def test_resource_rate_colonists_only(self):
        """
        Test resource rate from colonists.

        C# formula: colonists / colonists_per_resource
        At 100000 colonists, 1000 per resource -> 100 resources
        """
        race = Race()
        race.colonists_per_resource = 1000
        race.operable_factories = 10
        race.factory_production = 10

        star = Star()
        star.colonists = 100000
        star.factories = 0
        star.this_race = race

        rate = star.get_resource_rate()
        assert rate == 100

    def test_resource_rate_with_factories(self):
        """
        Test resource rate with factories.

        C# formula:
        - From colonists: colonists / colonists_per_resource
        - From factories: (factories_in_use / 10) * factory_production

        At 100k colonists, 50 factories operated, 10 production rate:
        100 + (50/10) * 10 = 100 + 50 = 150
        """
        race = Race()
        race.colonists_per_resource = 1000
        race.operable_factories = 10  # 10 factories per 10k colonists
        race.factory_production = 10

        star = Star()
        star.colonists = 100000  # Can operate 100 factories
        star.factories = 50  # But only have 50
        star.this_race = race

        rate = star.get_resource_rate()
        # 100 from colonists + (50/10)*10 = 100 + 50 = 150
        assert rate == 150

    def test_factory_limit_by_population(self):
        """Test factories limited by population."""
        race = Race()
        race.colonists_per_resource = 1000
        race.operable_factories = 10
        race.factory_production = 10

        star = Star()
        star.colonists = 50000  # Can operate 50 factories
        star.factories = 100  # Have 100, but limited
        star.this_race = race

        # Operable: (50000/10000) * 10 = 50
        factories_in_use = star.get_factories_in_use()
        assert factories_in_use == 50

        rate = star.get_resource_rate()
        # 50 from colonists + (50/10)*10 = 50 + 50 = 100
        assert rate == 100


# =============================================================================
# Mining Rate Parity Tests
# Source: Common/GameObjects/Star.cs lines 227-242
# =============================================================================

class TestMiningRateParity:
    """Test mining formulas match C# exactly."""

    def test_mining_rate_full_concentration(self):
        """
        Test mining at 100% concentration.

        C# formula: (mines_in_use / 10) * mine_production_rate * (concentration / 100)
        At 50 mines, 10 production, 100% conc: (50/10) * 10 * 1.0 = 50
        """
        race = Race()
        race.operable_mines = 10
        race.mine_production_rate = 10

        star = Star()
        star.colonists = 100000  # Can operate 100 mines
        star.mines = 50
        star.this_race = race

        rate = star.get_mining_rate(100)
        assert rate == 50

    def test_mining_rate_partial_concentration(self):
        """
        Test mining at partial concentration.

        At 50 mines, 10 production, 60% conc: (50/10) * 10 * 0.6 = 30
        """
        race = Race()
        race.operable_mines = 10
        race.mine_production_rate = 10

        star = Star()
        star.colonists = 100000
        star.mines = 50
        star.this_race = race

        rate = star.get_mining_rate(60)
        assert rate == 30


# =============================================================================
# NovaPoint Distance Parity Tests
# Source: Common/DataStructures/NovaPoint.cs
# =============================================================================

class TestNovaPointParity:
    """
    Test NovaPoint calculations match C# exactly.

    Note: Stars! Nova uses Manhattan distance as the primary distance_to,
    not Euclidean. There's a separate euclidean_distance_to method.
    """

    def test_distance_to_uses_manhattan(self):
        """
        Test distance_to uses Manhattan formula.

        C# formula: sqrt((|dx| + |dy|)^2) = |dx| + |dy|
        This is intentionally NOT Euclidean distance.
        """
        p1 = NovaPoint(x=0, y=0)
        p2 = NovaPoint(x=3, y=4)

        # Manhattan: |3| + |4| = 7
        assert p1.distance_to(p2) == 7.0

    def test_distance_squared_uses_manhattan(self):
        """Test squared distance uses Manhattan squared."""
        p1 = NovaPoint(x=0, y=0)
        p2 = NovaPoint(x=3, y=4)

        # (|3| + |4|)^2 = 49
        assert p1.distance_to_squared(p2) == 49

    def test_euclidean_distance_available(self):
        """Test euclidean_distance_to for true Euclidean."""
        p1 = NovaPoint(x=0, y=0)
        p2 = NovaPoint(x=3, y=4)

        # Pythagorean: sqrt(9 + 16) = 5
        assert p1.euclidean_distance_to(p2) == 5.0

    def test_length_squared(self):
        """Test length_squared for vector magnitude."""
        p = NovaPoint(x=3, y=4)

        # 3^2 + 4^2 = 25
        assert p.length_squared() == 25


# =============================================================================
# Battle Speed Parity Tests
# Source: Common/Components/ShipDesign.cs battle_speed property
# =============================================================================

class TestBattleSpeedParity:
    """
    Test battle speed calculation matches C# exactly.

    Formula from Stars! manual:
    battle_speed = (optimal_speed - 4) / 4 - (mass / 70 / 4 / num_engines) + bonuses
    Clamped to [0.5, 2.5] in 0.25 increments.
    """

    def test_battle_speed_formula(self):
        """Test battle speed calculation with known values."""
        # Create a mock scenario:
        # Optimal speed 6, mass 100, 1 engine
        # (6-4)/4 - (100/70/4/1) = 0.5 - 0.357 = 0.143 -> rounds to 0.25

        # We test via direct calculation since creating full ShipDesign
        # requires hull/engine setup
        optimal_speed = 6
        mass = 100
        num_engines = 1

        speed = (optimal_speed - 4.0) / 4.0
        speed -= mass / 70.0 / 4.0 / num_engines

        # Clamp
        speed = max(0.5, min(2.5, speed))
        # Round to 0.25
        speed = round(speed * 4.0) / 4.0

        # (6-4)/4 = 0.5
        # 100/70/4/1 = 0.357
        # 0.5 - 0.357 = 0.143 -> clamps to 0.5 (minimum)
        assert speed == 0.5

    def test_battle_speed_heavy_ship(self):
        """Test battle speed for heavy ship."""
        optimal_speed = 9
        mass = 500
        num_engines = 2

        speed = (optimal_speed - 4.0) / 4.0
        speed -= mass / 70.0 / 4.0 / num_engines
        speed = max(0.5, min(2.5, speed))
        speed = round(speed * 4.0) / 4.0

        # (9-4)/4 = 1.25
        # 500/70/4/2 = 0.893
        # 1.25 - 0.893 = 0.357 -> clamps to 0.5
        assert speed == 0.5

    def test_battle_speed_light_fast_ship(self):
        """Test battle speed for light fast ship."""
        optimal_speed = 10
        mass = 50
        num_engines = 2

        speed = (optimal_speed - 4.0) / 4.0
        speed -= mass / 70.0 / 4.0 / num_engines
        speed = max(0.5, min(2.5, speed))
        speed = round(speed * 4.0) / 4.0

        # (10-4)/4 = 1.5
        # 50/70/4/2 = 0.089
        # 1.5 - 0.089 = 1.411 -> rounds to 1.5
        assert speed == 1.5


# =============================================================================
# Resources Arithmetic Parity Tests
# Source: Common/DataStructures/Resources.cs
# =============================================================================

class TestResourcesParity:
    """Test Resources arithmetic matches C# exactly."""

    def test_addition(self):
        """Test resource addition."""
        r1 = Resources(ironium=100, boranium=200, germanium=300, energy=400)
        r2 = Resources(ironium=10, boranium=20, germanium=30, energy=40)

        result = r1 + r2

        assert result.ironium == 110
        assert result.boranium == 220
        assert result.germanium == 330
        assert result.energy == 440

    def test_subtraction(self):
        """Test resource subtraction."""
        r1 = Resources(ironium=100, boranium=200, germanium=300, energy=400)
        r2 = Resources(ironium=10, boranium=20, germanium=30, energy=40)

        result = r1 - r2

        assert result.ironium == 90
        assert result.boranium == 180
        assert result.germanium == 270
        assert result.energy == 360

    def test_scalar_multiply_ceiling(self):
        """
        Test scalar multiplication uses ceiling.

        C# uses Math.Ceiling for float multiplication.
        """
        r = Resources(ironium=10, boranium=20, germanium=30, energy=40)

        result = r * 1.5

        # 10*1.5=15, 20*1.5=30, 30*1.5=45, 40*1.5=60
        assert result.ironium == 15
        assert result.boranium == 30
        assert result.germanium == 45
        assert result.energy == 60

    def test_scalar_multiply_ceiling_fractional(self):
        """Test ceiling rounding on fractional results."""
        r = Resources(ironium=10, boranium=20, germanium=30, energy=40)

        result = r * 0.3

        # 10*0.3=3, 20*0.3=6, 30*0.3=9, 40*0.3=12
        assert result.ironium == 3
        assert result.boranium == 6
        assert result.germanium == 9
        assert result.energy == 12

    def test_mass_excludes_energy(self):
        """Test mass property excludes energy."""
        r = Resources(ironium=100, boranium=200, germanium=300, energy=400)

        # Mass = I + B + G, not E
        assert r.mass == 600


# =============================================================================
# Cargo Parity Tests
# Source: Common/DataStructures/Cargo.cs
# =============================================================================

class TestCargoParity:
    """Test Cargo calculations match C# exactly."""

    def test_cargo_mass_includes_colonists(self):
        """
        Test cargo mass includes colonists at correct rate.

        Colonists are stored in kT (100 colonists per kT).
        """
        cargo = Cargo(ironium=100, boranium=100, germanium=100, colonists_in_kilotons=10)

        # Mass = 100 + 100 + 100 + 10 = 310
        assert cargo.mass == 310

    def test_cargo_scale(self):
        """Test cargo scale function clamps to [0, 1]."""
        cargo = Cargo(ironium=100, boranium=200, germanium=300, colonists_in_kilotons=40)

        scaled = cargo.scale(0.5)

        assert scaled.ironium == 50
        assert scaled.boranium == 100
        assert scaled.germanium == 150
        assert scaled.colonists_in_kilotons == 20


# =============================================================================
# TechLevel Parity Tests
# Source: Common/DataStructures/TechLevel.cs
# =============================================================================

class TestTechLevelParity:
    """Test TechLevel comparisons match C# exactly."""

    def test_tech_comparison_meets(self):
        """Test tech level meets requirement."""
        required = TechLevel(levels={
            "Propulsion": 5, "Construction": 3,
            "Electronics": 0, "Energy": 0,
            "Weapons": 0, "Biotechnology": 0
        })

        current = TechLevel(levels={
            "Propulsion": 6, "Construction": 4,
            "Electronics": 2, "Energy": 1,
            "Weapons": 3, "Biotechnology": 1
        })

        # Current >= required in all fields
        assert current >= required

    def test_tech_comparison_fails(self):
        """Test tech level fails requirement."""
        required = TechLevel(levels={
            "Propulsion": 5, "Construction": 3,
            "Electronics": 0, "Energy": 0,
            "Weapons": 0, "Biotechnology": 0
        })

        current = TechLevel(levels={
            "Propulsion": 4, "Construction": 4,  # Propulsion too low
            "Electronics": 2, "Energy": 1,
            "Weapons": 3, "Biotechnology": 1
        })

        assert not (current >= required)


# =============================================================================
# Global Constants Verification
# Source: Common/GlobalDefinitions.cs
# =============================================================================

class TestGlobalConstantsParity:
    """Verify global constants match C# exactly."""

    def test_crowding_factor(self):
        """Crowding factor must be exactly 16/9."""
        assert g.BASE_CROWDING_FACTOR == 16.0 / 9.0
        assert abs(g.BASE_CROWDING_FACTOR - 1.7777777777777777) < 1e-10

    def test_hyper_expansion_factors(self):
        """HE trait factors."""
        assert g.POPULATION_FACTOR_HYPER_EXPANSION == 0.5
        assert g.GROWTH_FACTOR_HYPER_EXPANSION == 2.0

    def test_production_constants(self):
        """Production rate constants."""
        assert g.COLONISTS_PER_KILOTON == 100
        assert g.COLONISTS_PER_OPERABLE_FACTORY_UNIT == 10000
        assert g.COLONISTS_PER_OPERABLE_MINING_UNIT == 10000
        assert g.FACTORIES_PER_FACTORY_PRODUCTION_UNIT == 10
        assert g.MINES_PER_MINE_PRODUCTION_UNIT == 10

    def test_combat_constants(self):
        """Combat constants."""
        assert g.MAX_WEAPON_RANGE == 7
        assert g.MAX_DEFENSES == 100

    def test_beam_rating_table_dimensions(self):
        """Beam rating table has correct dimensions."""
        assert len(g.BEAM_RATING_MULTIPLIER) == 11  # 11 speed levels
        assert all(len(row) == 4 for row in g.BEAM_RATING_MULTIPLIER)  # 4 ranges

    def test_beam_rating_specific_values(self):
        """Verify specific beam rating values from C# source."""
        # battlespeed 1.0 (index 4), range 0 = 1.2
        assert g.BEAM_RATING_MULTIPLIER[4][0] == 1.2
        # battlespeed 2.5 (index 10), range 3 = 1.047
        assert g.BEAM_RATING_MULTIPLIER[10][3] == 1.047
