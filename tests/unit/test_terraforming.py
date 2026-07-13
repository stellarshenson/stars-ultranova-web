"""
Unit tests for terraforming.

The C# TerraformProductionUnit.cs is a stub (all methods throw
NotImplementedException), so these tests verify the canonical Stars!
rules implemented in backend/services/terraforming.py: click math,
component tech gating, the original +- max cap, CA instaforming, the
Retro Bomb path, and original_* environment initialization.
"""

import pytest
from dataclasses import dataclass, field
from typing import Dict, Optional

from backend.core.data_structures import EmpireData, Resources, TechLevel
from backend.core.game_objects.star import Star
from backend.core.production.production_queue import (
    ProductionOrder, ProductionType
)
from backend.core.race.race import Race
from backend.server import ServerData
from backend.server.turn_steps import BombingStep, StarUpdateStep
from backend.services.terraforming import (
    instaform, optimum, retro_terraform_one_point,
    select_terraform_target, terraform_ability, terraform_one_point,
    update_empire_terraform_capability
)


def make_star(name="Testworld", owner=1, gravity=50, temperature=50,
              radiation=50, colonists=100000) -> Star:
    star = Star()
    star.name = name
    star.owner = owner
    star.colonists = colonists
    star.gravity = gravity
    star.temperature = temperature
    star.radiation = radiation
    star.original_gravity = gravity
    star.original_temperature = temperature
    star.original_radiation = radiation
    return star


class TestTerraformAbility:
    """Component tech gating (names/tech from backend/data/components.xml)."""

    def test_terraform_ability_tech_table(self):
        race = Race()  # JOAT, no LRTs; hab 15-85 each

        # Bio 1 + Prop/Energy/Weapons 1 -> the dedicated +-3 tier at
        # 100 resources/point
        ability = terraform_ability(race, TechLevel.from_values(
            biotechnology=1, propulsion=1, energy=1, weapons=1))
        assert ability == {"gravity": (3, 100), "temperature": (3, 100),
                           "radiation": (3, 100)}

        # Gravity +-7 at Bio 2 / Prop 5
        ability = terraform_ability(race, TechLevel.from_values(
            biotechnology=2, propulsion=5))
        assert ability["gravity"] == (7, 100)

        # Gravity +-15 at Bio 3 / Prop 16
        ability = terraform_ability(race, TechLevel.from_values(
            biotechnology=3, propulsion=16))
        assert ability["gravity"] == (15, 100)

        # Temp +-15 at Bio 4 / Energy 16
        ability = terraform_ability(race, TechLevel.from_values(
            biotechnology=4, energy=16))
        assert ability["temperature"] == (15, 100)

        # No Gravity +-11 step in the data file (canonical Stars! has
        # one; the data file is authoritative): Bio 3 / Prop 10 stays
        # at the +-7 tier
        ability = terraform_ability(race, TechLevel.from_values(
            biotechnology=3, propulsion=10))
        assert ability["gravity"] == (7, 100)

    def test_terraform_ability_tt(self):
        tt_race = Race()
        tt_race.traits.add("TT")

        # Total +-3 has no tech requirement (GameInitialiser.cs:275-277)
        # and costs 70/point - the TT 30% discount is in the component
        # definitions (GameInitialiser.cs:280)
        ability = terraform_ability(tt_race, TechLevel())
        assert ability == {"gravity": (3, 70), "temperature": (3, 70),
                           "radiation": (3, 70)}

        # Total +-30 at Bio 25
        ability = terraform_ability(tt_race, TechLevel.from_values(
            biotechnology=25))
        assert ability == {"gravity": (30, 70), "temperature": (30, 70),
                           "radiation": (30, 70)}

        # Non-TT races never see Total components (TT=2 = required
        # trait, RaceRestriction.cs:44-48)
        ability = terraform_ability(Race(), TechLevel.from_values(
            biotechnology=25))
        assert ability == {"gravity": (0, 0), "temperature": (0, 0),
                           "radiation": (0, 0)}

    def test_update_empire_terraform_capability(self):
        empire = EmpireData(id=1)
        empire.race = Race()
        empire.research_levels = TechLevel.from_values(
            biotechnology=2, propulsion=5, energy=5, weapons=1)
        update_empire_terraform_capability(empire)
        assert empire.gravity_mod_capability == 7
        assert empire.temperature_mod_capability == 7
        assert empire.radiation_mod_capability == 3


class TestTargetSelection:
    """Click math, the original +- max cap, and deficit ordering."""

    ABILITY_3 = {"gravity": (3, 100), "temperature": (3, 100),
                 "radiation": (3, 100)}

    def test_select_target_and_limits(self):
        race = Race()  # optimum 50/50/50
        assert optimum(race, "gravity") == 50

        star = make_star(gravity=40)
        # Three points move gravity 41, 42, 43 ...
        for expected in (41, 42, 43):
            assert terraform_one_point(star, race, self.ABILITY_3) == "gravity"
            assert star.gravity == expected
        # ... then gravity is capped at |43 - 40| = 3 = max_n
        assert select_terraform_target(star, race, self.ABILITY_3) is None
        assert terraform_one_point(star, race, self.ABILITY_3) is None
        assert star.gravity == 43

    def test_largest_deficit_selected(self):
        race = Race()
        # temperature deficit 8 beats radiation deficit 4
        star = make_star(gravity=50, temperature=58, radiation=46)
        assert select_terraform_target(star, race, self.ABILITY_3) == "temperature"
        assert terraform_one_point(star, race, self.ABILITY_3) == "temperature"
        assert star.temperature == 57

    def test_immune_variable_never_selected(self):
        race = Race()
        race.immune_gravity = True
        # gravity would have the largest deficit if not immune
        star = make_star(gravity=10, temperature=48, radiation=50)
        assert optimum(race, "gravity") is None
        assert select_terraform_target(star, race, self.ABILITY_3) == "temperature"


class TestTerraformProduction:
    """The Terraform production queue item in StarUpdateStep."""

    def _empire(self, tech=None) -> EmpireData:
        empire = EmpireData(id=1)
        empire.race = Race()
        empire.research_levels = tech or TechLevel.from_values(
            biotechnology=1, propulsion=1, energy=1, weapons=1)
        empire.research_budget = 0
        return empire

    def test_terraform_production_unit(self):
        empire = self._empire()
        star = make_star(gravity=40)
        star.this_race = empire.race
        star.resources_on_hand = Resources(ironium=50, boranium=50,
                                           germanium=50, energy=500)
        star.manufacturing_queue.add(ProductionOrder(
            production_type=ProductionType.TERRAFORM, quantity=3,
            name="Terraform"))
        hab_before = empire.race.hab_value(star)

        step = StarUpdateStep()
        messages = step._manufacture_items(star, empire)

        # 3 points x 100 resources, no minerals
        assert star.gravity == 43
        assert star.resources_on_hand.energy == 200
        assert star.resources_on_hand.ironium == 50
        assert star.resources_on_hand.boranium == 50
        assert star.resources_on_hand.germanium == 50
        assert len(star.manufacturing_queue.orders) == 0
        assert any("has been terraformed" in m.text for m in messages)
        assert empire.race.hab_value(star) > hab_before

    def test_terraform_skip_when_complete(self):
        # IsSkipped semantics (TerraformProductionUnit.cs:61-64 stub):
        # nothing improvable -> spend nothing, drop the order
        empire = self._empire()
        star = make_star()  # already at optimum 50/50/50
        star.this_race = empire.race
        star.resources_on_hand = Resources(energy=500)
        star.manufacturing_queue.add(ProductionOrder(
            production_type=ProductionType.TERRAFORM, quantity=3,
            name="Terraform"))

        step = StarUpdateStep()
        messages = step._manufacture_items(star, empire)

        assert star.resources_on_hand.energy == 500
        assert (star.gravity, star.temperature, star.radiation) == (50, 50, 50)
        assert len(star.manufacturing_queue.orders) == 0
        assert any("has completed terraforming" in m.text for m in messages)

    def test_ca_instaforming(self):
        # Canonical CA rule (PrimaryTraits.cs:56 is description-only):
        # 1 free click per variable per year within tech limits
        ca_empire = EmpireData(id=1)
        ca_empire.race = Race()
        ca_empire.race.primary_trait = "CA"
        ca_empire.research_levels = TechLevel.from_values(
            biotechnology=1, propulsion=1, energy=1, weapons=1)
        ca_empire.research_budget = 0

        plain_empire = EmpireData(id=2)
        plain_empire.race = Race()
        plain_empire.research_levels = TechLevel.from_values(
            biotechnology=1, propulsion=1, energy=1, weapons=1)
        plain_empire.research_budget = 0

        ca_star = make_star(name="CAWorld", owner=1, gravity=45,
                            temperature=45, colonists=10000)
        plain_star = make_star(name="PlainWorld", owner=2, gravity=45,
                               temperature=45, colonists=10000)

        data = ServerData()
        data.all_stars = {ca_star.name: ca_star, plain_star.name: plain_star}
        data.all_empires = {1: ca_empire, 2: plain_empire}

        messages = StarUpdateStep().process(data)

        # Two off-optimum variables each moved exactly 1 click, free
        assert ca_star.gravity == 46
        assert ca_star.temperature == 46
        assert ca_star.radiation == 50
        assert any("instaformed" in m.text for m in messages)
        # Non-CA empire star untouched
        assert plain_star.gravity == 45
        assert plain_star.temperature == 45


@dataclass
class RetroToken:
    quantity: int = 1
    design_key: int = 1


@dataclass
class RetroFleet:
    key: int = 1
    name: str = "Retro Fleet"
    owner: int = 1
    in_orbit: Optional[object] = None
    in_orbit_name: str = ""
    has_bombers: bool = True
    is_starbase: bool = False
    tokens: Dict[int, RetroToken] = field(default_factory=dict)


class TestRetroBomb:
    """Orbital Adjuster aggregation and the retro-bombing path."""

    def _retro_design(self, bomb_count=2):
        """Real ShipDesign with Retro Bombs resolved from the catalog."""
        from backend.core.components import (
            Component, ComponentProperty, ShipDesign
        )
        from backend.core.game_objects.item import ItemType
        from backend.services.design_builder import ensure_components_loaded

        ensure_components_loaded()
        blueprint = Component()
        blueprint.name = "Retro Hull"
        blueprint.item_type = ItemType.HULL
        blueprint.mass = 50
        blueprint.cost = Resources(10, 5, 3, 25)
        hull_prop = ComponentProperty()
        hull_prop.property_type = "Hull"
        hull_prop.values = {
            "fuel_capacity": 200, "armor_strength": 50,
            "modules": [{
                "cell_number": 1, "component_maximum": 4,
                "component_type": "Bomb",
                "component_count": bomb_count,
                "allocated_component": "Retro Bomb",
            }],
        }
        blueprint.add_property(hull_prop)
        design = ShipDesign(blueprint=blueprint)
        design.name = "Retro Bomber"
        design.key = 1
        design.update()
        return design

    def test_orbital_adjuster_aggregation(self):
        design = self._retro_design(bomb_count=2)
        # Orbital Adjuster sums (ShipDesign.cs:628): 2 x -1 = -2
        assert design.orbital_adjuster == -2
        assert design.is_bomber is True

    def test_retro_bomb(self):
        design = self._retro_design(bomb_count=2)

        # Enemy star terraformed +4 gravity over original
        star = make_star(name="Target", owner=2, gravity=54,
                         colonists=50000)
        star.original_gravity = 50
        star.mines = 20
        star.factories = 20

        attacker = EmpireData(id=1)
        attacker.designs[1] = design
        fleet = RetroFleet(owner=1, in_orbit=star, in_orbit_name="Target",
                           tokens={1: RetroToken(quantity=1, design_key=1)})
        attacker.owned_fleets = {1: fleet}
        defender = EmpireData(id=2)

        data = ServerData()
        data.all_stars = {"Target": star}
        data.all_empires = {1: attacker, 2: defender}

        step = BombingStep()

        # Year 1: adjuster -2 moves gravity 2 clicks back toward
        # original; no population or installation damage
        messages = step.process(data)
        assert star.gravity == 52
        assert star.colonists == 50000
        assert star.mines == 20
        assert star.factories == 20
        assert sum(1 for m in messages if "un-terraformed" in m.text) == 2
        assert {m.audience for m in messages
                if "un-terraformed" in m.text} == {1, 2}

        # Year 2: the remaining 2 clicks
        step.process(data)
        assert star.gravity == 50

        # Year 3: no-op at the original environment
        messages = step.process(data)
        assert star.gravity == 50
        assert messages == []

    def test_retro_terraform_one_point_order(self):
        # Largest |current - original| reversed first
        star = make_star(gravity=53, temperature=48)
        star.original_gravity = 50
        star.original_temperature = 50
        assert retro_terraform_one_point(star) == "gravity"
        assert star.gravity == 52


class TestOriginalEnvironment:
    """original_* initialization and legacy-save migration."""

    def test_original_env_initialized(self):
        from backend.services.galaxy_generator import GalaxyGenerator

        generator = GalaxyGenerator(seed=1234)
        server_data = generator.generate(
            player_count=2, universe_size="small")
        assert len(server_data.all_stars) > 0
        for star in server_data.all_stars.values():
            assert star.original_gravity == star.gravity
            assert star.original_temperature == star.temperature
            assert star.original_radiation == star.radiation

    def test_from_dict_legacy_defaults_to_current(self):
        # Saves from before terraforming lack original_* keys: they
        # must default to the current environment, not 0
        star = make_star(gravity=61, temperature=32, radiation=77)
        data = star.to_dict()
        for key in ("original_gravity", "original_temperature",
                    "original_radiation"):
            del data[key]
        loaded = Star.from_dict(data)
        assert loaded.original_gravity == 61
        assert loaded.original_temperature == 32
        assert loaded.original_radiation == 77

    def test_instaform_respects_original_cap(self):
        race = Race()
        ability = {"gravity": (3, 100), "temperature": (3, 100),
                   "radiation": (3, 100)}
        star = make_star(gravity=43)
        star.original_gravity = 40  # already +3 from original
        assert instaform(star, race, ability) == []
        assert star.gravity == 43
