"""
Unit tests for PRT starting conditions at game creation.

Covers the per-PRT starting tech grants (GameInitialiser.cs
ProcessPrimaryTraits/ProcessSecondaryTraits), starting population
(Race.cs GetStartingPopulation), leftover advantage-point spend on the
homeworld (HomeStarLeftoverpointsAdjuster.cs), per-PRT starting fleets,
and the race wizard mapping of the new fields.
"""
import pytest

from backend.core.data_structures import Resources
from backend.core.data_structures.tech_level import RESEARCH_KEYS
from backend.core.game_objects.star import Star
from backend.core.race.race import Race
from backend.services.galaxy_generator import GalaxyGenerator
from backend.services.game_manager import _race_from_wizard


def _race(prt: str, traits=None, **kwargs) -> Race:
    race = Race(**kwargs)
    race.name = "Testers"
    race.primary_trait = prt
    race.traits = set(traits or [])
    return race


def _generate(race: Race, accelerated_start: bool = False):
    """Generate a small seeded game with the race as empire 1."""
    generator = GalaxyGenerator(seed=42)
    server = generator.generate(
        player_count=2, universe_size="tiny", player_race=race,
        accelerated_start=accelerated_start)
    empire = server.all_empires[1]
    home_star = next(iter(empire.owned_stars.values()))
    return server, empire, home_star


# =============================================================================
# PRT starting tech (through full generation)
# =============================================================================

class TestPrtStartingTech:
    """GameInitialiser.cs ProcessPrimaryTraits (lines 187-254)."""

    EXPECTED = {
        "HE": {},
        "SS": {"Electronics": 5},
        "WM": {"Propulsion": 1, "Energy": 1},
        "CA": {"Weapons": 1, "Propulsion": 1, "Energy": 1,
               "Biotechnology": 6},
        "IS": {},
        "SD": {"Propulsion": 2, "Biotechnology": 2},
        "PP": {"Energy": 4},
        "IT": {"Propulsion": 5, "Construction": 5},
        "AR": {"Energy": 1},
        "JOAT": {key: 3 for key in RESEARCH_KEYS},
    }

    @pytest.mark.parametrize("prt", sorted(EXPECTED))
    def test_prt_starting_tech(self, prt):
        _, empire, _ = _generate(_race(prt))
        for key in RESEARCH_KEYS:
            assert empire.research_levels.levels[key] == \
                self.EXPECTED[prt].get(key, 0), f"{prt} {key}"

    def test_ai_empires_get_prt_grants(self):
        # Empire 2 is the Rabbitoids HE AI template: all tech zero
        server, _, _ = _generate(_race("JOAT"))
        ai_empire = server.all_empires[2]
        assert ai_empire.race.primary_trait == "HE"
        assert all(level == 0 for level in ai_empire.research_levels)


class TestIfeExtratechStacking:
    """LRT grants stack on top of PRT grants
    (GameInitialiser.cs:123-124, 267-275, 355-376)."""

    def test_joat_ife_extratech(self):
        _, empire, _ = _generate(_race("JOAT", traits={"IFE", "ExtraTech"}))
        assert empire.research_levels.levels["Propulsion"] == 5  # 3+1+1
        assert all(empire.research_levels.levels[key] == 4
                   for key in RESEARCH_KEYS if key != "Propulsion")

    def test_ss_extratech(self):
        _, empire, _ = _generate(_race("SS", traits={"ExtraTech"}))
        assert empire.research_levels.levels["Electronics"] == 8  # 5+3
        assert all(empire.research_levels.levels[key] == 3
                   for key in RESEARCH_KEYS if key != "Electronics")

    def test_he_ife(self):
        _, empire, _ = _generate(_race("HE", traits={"IFE"}))
        assert empire.research_levels.levels["Propulsion"] == 1
        assert all(empire.research_levels.levels[key] == 0
                   for key in RESEARCH_KEYS if key != "Propulsion")


# =============================================================================
# Starting population (Race.cs GetStartingPopulation, lines 340-355)
# =============================================================================

class TestStartingPopulation:

    def test_default(self):
        assert _race("JOAT").get_starting_population() == 25000

    def test_lsp(self):
        assert _race("JOAT", traits={"LSP"}).get_starting_population() \
            == 17500

    def test_accelerated(self):
        assert _race("JOAT").get_starting_population(accelerated=True) \
            == 100000

    def test_accelerated_lsp(self):
        assert _race("JOAT", traits={"LSP"}).get_starting_population(
            accelerated=True) == 70000

    def test_homeworld_population_normal(self):
        _, _, home_star = _generate(_race("JOAT"))
        assert home_star.colonists == 25000

    def test_homeworld_population_accelerated(self):
        _, _, home_star = _generate(_race("JOAT"), accelerated_start=True)
        assert home_star.colonists == 100000


# =============================================================================
# Leftover advantage-point spend (HomeStarLeftoverpointsAdjuster.cs:12-82)
# =============================================================================

class TestLeftoverPoints:

    def _adjust(self, star: Star, target: str, points: int) -> None:
        race = _race("JOAT")
        race.leftover_point_target = target
        race.leftover_points = points
        GalaxyGenerator(seed=1)._adjust_homeworld_leftover_points(star, race)

    def test_mineral_concentration_poorest(self):
        # C# StarMapInitialiserTest CorrectMineralConcentration:
        # poorest mineral gains points/3
        star = Star()
        star.boranium_concentration = 10
        star.germanium_concentration = 10
        star.ironium_concentration = 0
        self._adjust(star, "Mineral concentration", 50)
        assert star.ironium_concentration == 16
        assert star.boranium_concentration == 10
        assert star.germanium_concentration == 10

    def test_mines(self):
        star = Star()
        star.mines = 10
        self._adjust(star, "Mines", 50)
        assert star.mines == 35  # +50//2

    def test_factories(self):
        star = Star()
        star.factories = 10
        self._adjust(star, "Factories", 50)
        assert star.factories == 20  # +50//5

    def test_defenses(self):
        star = Star()
        self._adjust(star, "Defenses", 50)
        assert star.defenses == 5  # 50//10

    def test_surface_minerals_equal_split(self):
        # Equal surface minerals: 500 kT splits evenly, round(500/3)=167
        star = Star()
        star.resources_on_hand = Resources(
            ironium=300, boranium=300, germanium=300, energy=0)
        self._adjust(star, "Surface minerals", 50)
        assert star.resources_on_hand.ironium == 467
        assert star.resources_on_hand.boranium == 467
        assert star.resources_on_hand.germanium == 467

    def test_surface_minerals_weighted_to_rarest(self):
        # Exact max(1,...)/round formula from the C# adjuster
        star = Star()
        star.resources_on_hand = Resources(
            ironium=100, boranium=400, germanium=500, energy=0)
        total = 500
        dividend = 100 + 400 + 500
        factors = {"ironium": dividend / 100, "boranium": dividend / 400,
                   "germanium": dividend / 500}
        distributed = sum(factors.values())
        self._adjust(star, "Surface minerals", 50)
        assert star.resources_on_hand.ironium == \
            100 + int(round(factors["ironium"] / distributed * total))
        assert star.resources_on_hand.boranium == \
            400 + int(round(factors["boranium"] / distributed * total))
        assert star.resources_on_hand.germanium == \
            500 + int(round(factors["germanium"] / distributed * total))

    def test_zero_points_no_change(self):
        star = Star()
        star.mines = 10
        self._adjust(star, "Mines", 0)
        assert star.mines == 10

    def test_points_clamped_to_50(self):
        star = Star()
        self._adjust(star, "Mines", 80)
        assert star.mines == 25  # behaves as 50

    def test_negative_points_clamped_to_zero(self):
        star = Star()
        star.factories = 10
        self._adjust(star, "Factories", -20)
        assert star.factories == 10


# =============================================================================
# Per-PRT starting fleets
# =============================================================================

class TestPrtStartingFleets:

    def _fleet_names(self, empire) -> list:
        return sorted(f.name for f in empire.owned_fleets.values())

    def test_he_fleets(self):
        _, empire, _ = _generate(_race("HE"))
        names = self._fleet_names(empire)
        assert names.count("Spore Cloud #1") == 1
        assert "Spore Cloud #2" in names and "Spore Cloud #3" in names
        assert "Armed Probe #1" in names
        colonizers = [f for f in empire.owned_fleets.values()
                      if f.can_colonize]
        assert len(colonizers) == 3
        # Colony ships pre-loaded to Mini-Colony cargo capacity (10 kT)
        assert all(f.cargo.colonists_in_kilotons == 10 for f in colonizers)

    def test_joat_fleets(self):
        _, empire, _ = _generate(_race("JOAT"))
        names = self._fleet_names(empire)
        assert "Long Range Scout #1" in names
        assert "Long Range Scout #2" in names
        assert "Santa Maria #1" in names
        assert "Teamster #1" in names
        assert "Cotton Picker #1" in names
        assert "Stalwart Defender #1" in names
        # 6 ships + starbase
        assert len(names) == 7

    def test_sd_mine_layers(self):
        _, empire, _ = _generate(_race("SD"))
        fleets = {f.name: f for f in empire.owned_fleets.values()}
        assert "Little Hen #1" in fleets
        assert "Speed Turtle #1" in fleets
        hen_token = next(iter(fleets["Little Hen #1"].tokens.values()))
        turtle_token = next(iter(fleets["Speed Turtle #1"].tokens.values()))
        assert hen_token.mine_count == 40
        assert turtle_token.speed_bump_mine_count == 20

    def test_arm_adds_two_miners(self):
        _, empire, _ = _generate(_race("IS", traits={"ARM"}))
        names = self._fleet_names(empire)
        assert "Cotton Picker #1" in names
        assert "Cotton Picker #2" in names

    def test_pp_two_shielded_scouts(self):
        _, empire, _ = _generate(_race("PP"))
        names = self._fleet_names(empire)
        assert "Shielded Scout #1" in names
        assert "Shielded Scout #2" in names

    def test_it_destroyer_and_privateer(self):
        _, empire, _ = _generate(_race("IT"))
        names = self._fleet_names(empire)
        assert "Stalwart Defender #1" in names
        assert "Swashbuckler #1" in names


# =============================================================================
# Homeworld leftover spend through full generation
# =============================================================================

class TestHomeworldLeftoverIntegration:

    def test_mines_target_applied_to_homeworld(self):
        race = _race("JOAT")
        race.leftover_point_target = "Mines"
        race.leftover_points = 50
        _, _, home_star = _generate(race)
        assert home_star.mines == 10 + 25

    def test_surface_minerals_default_target(self):
        # Default target adds 500 kT total on top of the 300-500 rolls
        race = _race("JOAT")
        race.leftover_points = 50
        _, _, home_star = _generate(race)
        total = (home_star.resources_on_hand.ironium
                 + home_star.resources_on_hand.boranium
                 + home_star.resources_on_hand.germanium)
        assert 900 + 499 <= total <= 1500 + 501


# =============================================================================
# Race wizard mapping of the new fields
# =============================================================================

class TestRaceFromWizardNewFields:

    def test_new_fields(self):
        race = _race_from_wizard({
            "name": "Boffins",
            "prt": "IT",
            "startAtLevel3": True,
            "leftoverPointTarget": "Factories",
        })
        assert "ExtraTech" in race.traits
        assert race.leftover_point_target == "Factories"

    def test_wizard_advantage_points_ignored(self):
        # The leftover budget is computed server-side from the ported
        # RaceAdvantagePointCalculator at game creation (create_game);
        # any wizard-supplied point total is ignored
        race = _race_from_wizard({"name": "Plain"})
        assert race.leftover_point_target == "Surface minerals"
        assert race.leftover_points == 0

        race = _race_from_wizard({"name": "Rich", "advantagePoints": 80})
        assert race.leftover_points == 0

    def test_round_trip_serialization(self):
        race = _race("JOAT")
        race.leftover_point_target = "Defenses"
        race.leftover_points = 12
        loaded = Race.from_dict(race.to_dict())
        assert loaded.leftover_point_target == "Defenses"
        assert loaded.leftover_points == 12
