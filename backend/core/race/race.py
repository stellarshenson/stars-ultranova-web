"""
Race class defining player race characteristics.
Port of: Common/RaceDefinition/Race.cs (partial - key methods for Star operations)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Set, Optional, TYPE_CHECKING

from ..data_structures.tech_level import RESEARCH_KEYS
from ..globals import (
    NOMINAL_MAXIMUM_PLANETARY_POPULATION,
    COLONISTS_PER_OPERABLE_FACTORY_UNIT,
    COLONISTS_PER_OPERABLE_MINING_UNIT,
    FACTORIES_PER_FACTORY_PRODUCTION_UNIT,
    MINES_PER_MINE_PRODUCTION_UNIT,
    STARTING_COLONISTS,
    STARTING_COLONISTS_ACCELERATED_BBS,
    LOW_STARTING_POPULATION_FACTOR,
    STORM_RAD_EXTREME_OPTIMUM
)

if TYPE_CHECKING:
    from ..game_objects.star import Star


@dataclass
class Race:
    """
    Race definition containing all race-specific parameters.

    Port of: Common/RaceDefinition/Race.cs
    """
    name: str = ""

    # Population and growth
    growth_rate: float = 15.0  # Base growth rate percentage
    max_population: int = NOMINAL_MAXIMUM_PLANETARY_POPULATION
    colonists_per_resource: int = 1000  # Colonists needed to generate 1 resource

    # Factory parameters
    operable_factories: int = 10  # Factories per 10k colonists
    factory_production: int = 10  # Resources per 10 factories
    factory_cost: int = 10  # Germanium cost per factory

    # Mine parameters
    operable_mines: int = 10  # Mines per 10k colonists
    mine_production_rate: int = 10  # kT per 10 mines at 100% concentration
    mine_cost: int = 5  # Resources to build a mine

    # Habitability ranges (0-100 representing percentage of range)
    # Values represent the race's ideal range within the environment spectrum
    gravity_min: int = 15
    gravity_max: int = 85
    temperature_min: int = 15
    temperature_max: int = 85
    radiation_min: int = 15
    radiation_max: int = 85

    # Environment immunities (EnvironmentTolerance.cs:44 Immune flag).
    # The wizard flattens an immune dimension's min/max to 0/100 for the
    # simplified hab_value below; the advantage-point calculator needs
    # the real flag (RaceAdvantagePointCalculator.cs:95, Race.cs:598-610)
    immune_gravity: bool = False
    immune_temperature: bool = False
    immune_radiation: bool = False

    # AI production proclivities (C# Race AI weighting knobs)
    # 50 = neutral weighting for the interceptor ratio (divided by 50)
    ai_proclivities_interceptors: int = 50
    ai_proclivities_bombers: float = 1.0
    ai_proclivities_escorts: float = 1.0
    ai_proclivities_starbases: float = 1.0

    # Per-field research cost factor as an integer percent, keyed by
    # RESEARCH_KEYS field name. Port of Race.cs:44 ResearchCosts (a
    # TechLevel of percents); the race designer writes 50 (cheap),
    # 100 (standard) or 175 (expensive) per ControlLibrary/
    # ResearchCost.cs:160-176; legacy value 150 is also expensive
    # (ResearchCost.cs:210-211).
    research_costs: Dict[str, int] = field(
        default_factory=lambda: {key: 100 for key in RESEARCH_KEYS})

    # Race icon (RaceIcon.cs stores a bitmap + source name; the web
    # keeps an index into the client's 16 standard SVG emblems plus an
    # optional player-uploaded custom icon as a base64 data URI - user
    # directive, wave 5)
    icon: int = 0
    custom_icon: str = ""

    # Race password HASH (Race.cs:50 stores the hash string produced by
    # PasswordUtility.CalculateHash - MD5 over ASCII bytes as an
    # uppercase hex dash-joined string). Empty = no password. The C#
    # CheckPassword/PasswordUtility gate has no live call sites in the
    # reference (scaffolding only); the web port wires the canonical
    # intent: the hash gates opening the empire's view and submitting
    # its orders (backend/services/game_manager.py).
    password: str = ""

    # Traits
    traits: Set[str] = field(default_factory=set)

    # Primary racial trait (PRT) - one of: HE, SS, WM, CA, IS, SD, PP, IT, AR, JOAT
    primary_trait: str = "JOAT"

    # Leftover advantage-point spend at game start.
    # Target strings match Race.cs LeftoverPointTarget (default
    # "Surface minerals", Race.cs:436-438); the point budget is
    # clamp(advantage points, 0, 50) per Race.cs GetLeftoverAdvantagePoints
    # (lines 215-221), computed server-side from the ported
    # RaceAdvantagePointCalculator (backend/services/race_points.py)
    # at game creation.
    leftover_point_target: str = "Surface minerals"
    leftover_points: int = 0

    def get_starting_population(self, accelerated: bool = False) -> int:
        """
        Starting homeworld population for this race.

        Port of: Race.cs GetStartingPopulation (lines 340-355).
        Normal 25000, accelerated BBS 100000; LSP multiplies by 0.7
        (truncated): 17500 / 70000.
        """
        population = STARTING_COLONISTS
        if accelerated:
            population = STARTING_COLONISTS_ACCELERATED_BBS
        if self.has_trait("LSP"):
            population = int(population * LOW_STARTING_POPULATION_FACTOR)
        return population

    def has_trait(self, trait: str) -> bool:
        """Check if race has a specific trait."""
        # Port of: Race.cs HasTrait method
        if trait.upper() == self.primary_trait.upper():
            return True
        return trait.upper() in {t.upper() for t in self.traits}

    @property
    def is_radiation_hardened(self) -> bool:
        """
        Radiation-hardened race check for storm protection.

        Web-only extension (galactic storm protection, user directive -
        no C# equivalent). A race qualifies when its radiation
        habitability is immune, or its radiation optimum (the center of
        the habitable range) lies in the extreme band at/above
        STORM_RAD_EXTREME_OPTIMUM. Derived entirely from existing
        habitability data - no new race-wizard fields.
        """
        if self.immune_radiation:
            return True
        optimum = (self.radiation_min + self.radiation_max) / 2
        return optimum >= STORM_RAD_EXTREME_OPTIMUM

    def hab_value(self, star: Star) -> float:
        """
        Calculate habitability value for a star.
        Returns a value from -1.0 (deadly) to 1.0 (perfect).

        Port of: Race.cs HabValue method (simplified)
        """
        # Calculate how well each environment parameter fits the race's preferences
        grav_value = self._calc_hab_component(
            star.gravity, self.gravity_min, self.gravity_max
        )
        temp_value = self._calc_hab_component(
            star.temperature, self.temperature_min, self.temperature_max
        )
        rad_value = self._calc_hab_component(
            star.radiation, self.radiation_min, self.radiation_max
        )

        # If any value is negative, the planet is hostile
        if grav_value < 0 or temp_value < 0 or rad_value < 0:
            # Calculate negative habitability
            total_negative = 0.0
            if grav_value < 0:
                total_negative += grav_value
            if temp_value < 0:
                total_negative += temp_value
            if rad_value < 0:
                total_negative += rad_value
            return total_negative / 3.0

        # All positive - calculate combined habitability
        # Stars! uses geometric mean for positive hab
        import math
        combined = math.sqrt(grav_value * temp_value * rad_value)
        return combined

    def _calc_hab_component(
        self, value: int, min_range: int, max_range: int
    ) -> float:
        """
        Calculate habitability component for a single environment parameter.
        Returns 1.0 if value is within ideal range, decreasing toward edges,
        negative if outside tolerable range.
        """
        # Value is within ideal range
        if min_range <= value <= max_range:
            # Calculate how close to center of range
            center = (min_range + max_range) / 2.0
            half_width = (max_range - min_range) / 2.0
            if half_width == 0:
                return 1.0
            distance_from_center = abs(value - center) / half_width
            return 1.0 - (distance_from_center * 0.1)  # Slight penalty for edge

        # Value outside ideal range - calculate negative habitability
        if value < min_range:
            distance_out = min_range - value
        else:
            distance_out = value - max_range

        # Each point outside reduces habitability
        return -distance_out / 100.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "growth_rate": self.growth_rate,
            "max_population": self.max_population,
            "colonists_per_resource": self.colonists_per_resource,
            "operable_factories": self.operable_factories,
            "factory_production": self.factory_production,
            "factory_cost": self.factory_cost,
            "operable_mines": self.operable_mines,
            "mine_production_rate": self.mine_production_rate,
            "mine_cost": self.mine_cost,
            "gravity_min": self.gravity_min,
            "gravity_max": self.gravity_max,
            "temperature_min": self.temperature_min,
            "temperature_max": self.temperature_max,
            "radiation_min": self.radiation_min,
            "radiation_max": self.radiation_max,
            "immune_gravity": self.immune_gravity,
            "immune_temperature": self.immune_temperature,
            "immune_radiation": self.immune_radiation,
            "icon": self.icon,
            "custom_icon": self.custom_icon,
            "password": self.password,
            "research_costs": dict(self.research_costs),
            "traits": list(self.traits),
            "primary_trait": self.primary_trait,
            "leftover_point_target": self.leftover_point_target,
            "leftover_points": self.leftover_points
        }

    @classmethod
    def from_dict(cls, data: dict) -> Race:
        """Create Race from dictionary."""
        race = cls()
        race.name = data.get("name", "")
        race.growth_rate = data.get("growth_rate", 15.0)
        race.max_population = data.get("max_population", NOMINAL_MAXIMUM_PLANETARY_POPULATION)
        race.colonists_per_resource = data.get("colonists_per_resource", 1000)
        race.operable_factories = data.get("operable_factories", 10)
        race.factory_production = data.get("factory_production", 10)
        race.factory_cost = data.get("factory_cost", 10)
        race.operable_mines = data.get("operable_mines", 10)
        race.mine_production_rate = data.get("mine_production_rate", 10)
        race.mine_cost = data.get("mine_cost", 5)
        race.gravity_min = data.get("gravity_min", 15)
        race.gravity_max = data.get("gravity_max", 85)
        race.temperature_min = data.get("temperature_min", 15)
        race.temperature_max = data.get("temperature_max", 85)
        race.radiation_min = data.get("radiation_min", 15)
        race.radiation_max = data.get("radiation_max", 85)
        race.immune_gravity = data.get("immune_gravity", False)
        race.immune_temperature = data.get("immune_temperature", False)
        race.immune_radiation = data.get("immune_radiation", False)
        race.icon = data.get("icon", 0)
        race.custom_icon = data.get("custom_icon", "")
        race.password = data.get("password", "")
        race.research_costs = {
            key: int(data.get("research_costs", {}).get(key, 100))
            for key in RESEARCH_KEYS
        }
        race.traits = set(data.get("traits", []))
        race.primary_trait = data.get("primary_trait", "JOAT")
        race.leftover_point_target = data.get(
            "leftover_point_target", "Surface minerals")
        race.leftover_points = data.get("leftover_points", 0)
        return race
