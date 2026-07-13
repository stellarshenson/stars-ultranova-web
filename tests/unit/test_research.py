"""
Unit tests for research fidelity.

Covers the Research.Cost port (Fibonacci base table, race cost
multipliers, tech adjustment, integer division), cumulative-bank
spillover on level-up, leftover contribution from every star,
PRT/IFE/ExtraTech starting tech, and the race wizard mapping.
"""

from types import SimpleNamespace

from backend.core.research import fibonacci, research_cost
from backend.core.data_structures.tech_level import (
    TechLevel, ResearchField, RESEARCH_KEYS
)
from backend.core.data_structures.empire_data import EmpireData
from backend.core.data_structures.resources import Resources
from backend.core.game_objects.star import Star
from backend.core.race.race import Race
from backend.server.turn_steps.star_update_step import StarUpdateStep
from backend.services.galaxy_generator import GalaxyGenerator
from backend.services.game_manager import _race_from_wizard


def _topics_energy() -> TechLevel:
    """Research topics targeting Energy."""
    topics = TechLevel()
    topics.set_level(ResearchField.ENERGY, 1)
    return topics


def _step_with_state() -> StarUpdateStep:
    """StarUpdateStep wired to a minimal server state."""
    step = StarUpdateStep()
    step.server_state = SimpleNamespace(all_messages=[])
    return step


# =============================================================================
# Research.Cost port
# =============================================================================

class TestResearchCost:
    """research_cost matches Research.cs:43-62."""

    def test_cost_base_values(self):
        """Standard race, zero levels: cost is F(L+5)*10."""
        race = Race()
        levels = TechLevel()

        assert research_cost(ResearchField.ENERGY, race, levels, 1) == 80
        assert research_cost(ResearchField.ENERGY, race, levels, 2) == 130
        assert research_cost(ResearchField.ENERGY, race, levels, 5) == 550
        assert research_cost(ResearchField.ENERGY, race, levels, 26) == 13462690

    def test_fibonacci(self):
        """Iterative Fibonacci matches Research.cs:71-78."""
        assert fibonacci(0) == 0
        assert fibonacci(1) == 1
        assert fibonacci(6) == 8
        assert fibonacci(31) == 1346269

    def test_cost_multipliers(self):
        """Cost factor is a per-field integer percent."""
        race = Race()
        race.research_costs["Energy"] = 50
        levels = TechLevel()

        assert research_cost(ResearchField.ENERGY, race, levels, 1) == 40
        # Multiplier is per-field: Weapons stays standard
        assert research_cost(ResearchField.WEAPONS, race, levels, 1) == 80

        race.research_costs["Energy"] = 175
        assert research_cost(ResearchField.ENERGY, race, levels, 1) == 140

        # Legacy 150 percent is used as stored (only the C# UI
        # normalizes it to 175)
        race.research_costs["Energy"] = 150
        assert research_cost(ResearchField.ENERGY, race, levels, 1) == 120

    def test_cost_tech_adjustment(self):
        """10 points per attained level in ALL fields, integer division."""
        race = Race()
        levels = TechLevel.from_level(1)  # sum of levels = 6

        assert research_cost(ResearchField.ENERGY, race, levels, 2) == 190

        race.research_costs["Energy"] = 175
        # (130 + 60) * 175 // 100 = 332 (integer division)
        assert research_cost(ResearchField.ENERGY, race, levels, 2) == 332

    def test_cost_none_race_defaults_to_standard(self):
        assert research_cost(ResearchField.ENERGY, None, TechLevel(), 1) == 80


# =============================================================================
# Spillover / cumulative bank
# =============================================================================

class TestSpillover:
    """Level-up never deducts the bank; thresholds are cumulative."""

    def _empire(self) -> EmpireData:
        empire = EmpireData()
        empire.id = 1
        empire.race = Race()
        empire.research_topics = _topics_energy()
        return empire

    def test_level_up_no_deduction(self):
        step = _step_with_state()
        empire = self._empire()
        empire.research_resources.set_level(ResearchField.ENERGY, 80)

        step._check_tech_level_up(ResearchField.ENERGY, empire)

        assert empire.research_levels.get_level(ResearchField.ENERGY) == 1
        # Bank is cumulative - NOT deducted (StarUpdateStep.cs:186-237)
        assert empire.research_resources.get_level(ResearchField.ENERGY) == 80

    def test_multi_level_spillover(self):
        """One call climbs multiple levels while the bank clears each
        cumulative threshold (L1=80, L2=140, L3=230 with growing
        tech adjustment)."""
        step = _step_with_state()
        empire = self._empire()
        empire.research_resources.set_level(ResearchField.ENERGY, 250)

        step._check_tech_level_up(ResearchField.ENERGY, empire)

        assert empire.research_levels.get_level(ResearchField.ENERGY) == 3
        assert empire.research_resources.get_level(ResearchField.ENERGY) == 250
        # A TechAdvance message per level (newly available components
        # add their own NewComponentMessages, StarUpdateStep.cs:200-236)
        tech_advances = [m for m in step.server_state.all_messages
                         if m.message_type == "TechAdvance"]
        assert len(tech_advances) == 3

    def test_leftover_contribution_all_stars(self):
        """Leftover energy contributes from EVERY owned star, not only
        only_leftover ones (StarUpdateStep.cs:83)."""
        step = _step_with_state()
        empire = self._empire()

        star = Star()
        star.name = "Test"
        star.owner = 1
        star.only_leftover = False
        star.resources_on_hand = Resources(energy=42)

        step._contribute_leftover_research(star, empire)

        assert empire.research_resources.get_level(ResearchField.ENERGY) == 42
        assert star.resources_on_hand.energy == 0


# =============================================================================
# Starting tech
# =============================================================================

class TestStartingTech:
    """GameInitialiser.cs ProcessPrimaryTraits/ProcessSecondaryTraits."""

    def _empire_for(self, prt: str, traits=None) -> EmpireData:
        generator = GalaxyGenerator(seed=1)
        race = Race()
        race.name = "Testers"
        race.primary_trait = prt
        race.traits = set(traits or [])
        star = Star()
        star.name = "Home"
        return generator._create_empire(1, race, star)

    def test_starting_tech_prt(self):
        expected = {
            "HE": {},
            "IS": {},
            "SS": {"Electronics": 5},
            "WM": {"Propulsion": 1, "Energy": 1},
            "CA": {"Weapons": 1, "Propulsion": 1, "Energy": 1,
                   "Biotechnology": 6},
            "SD": {"Propulsion": 2, "Biotechnology": 2},
            "PP": {"Energy": 4},
            "IT": {"Propulsion": 5, "Construction": 5},
            "AR": {"Energy": 1},
            "JOAT": {key: 3 for key in RESEARCH_KEYS},
        }
        for prt, levels in expected.items():
            empire = self._empire_for(prt)
            for key in RESEARCH_KEYS:
                assert empire.research_levels.levels[key] == \
                    levels.get(key, 0), f"{prt} {key}"

    def test_starting_tech_ife(self):
        empire = self._empire_for("JOAT", traits={"IFE"})
        assert empire.research_levels.levels["Propulsion"] == 4

    def test_starting_tech_extratech(self):
        # Non-JOAT: +3 to ALL fields (GameInitialiser.cs:355-376; C#
        # Nova boosts all fields, not only expensive ones)
        empire = self._empire_for("HE", traits={"ExtraTech"})
        assert all(empire.research_levels.levels[key] == 3
                   for key in RESEARCH_KEYS)

        # JOAT: +1 to all fields -> 4
        empire = self._empire_for("JOAT", traits={"ExtraTech"})
        assert all(empire.research_levels.levels[key] == 4
                   for key in RESEARCH_KEYS)


# =============================================================================
# Race wizard mapping
# =============================================================================

class TestRaceFromWizard:
    """_race_from_wizard maps researchCosts and startAtLevel3."""

    def test_research_cost_mapping(self):
        race = _race_from_wizard({
            "name": "Boffins",
            "researchCosts": {"energy": "cheap", "weapons": "expensive"},
            "startAtLevel3": True,
        })
        assert race.research_costs["Energy"] == 50
        assert race.research_costs["Weapons"] == 175
        for key in ("Propulsion", "Construction", "Electronics",
                    "Biotechnology"):
            assert race.research_costs[key] == 100
        assert "ExtraTech" in race.traits

    def test_defaults_without_wizard_fields(self):
        race = _race_from_wizard({"name": "Plain"})
        assert all(race.research_costs[key] == 100 for key in RESEARCH_KEYS)
        assert "ExtraTech" not in race.traits

    def test_research_costs_round_trip(self):
        race = _race_from_wizard({
            "name": "Boffins",
            "researchCosts": {"energy": "cheap", "weapons": "expensive"},
        })
        restored = Race.from_dict(race.to_dict())
        assert restored.research_costs == race.research_costs
