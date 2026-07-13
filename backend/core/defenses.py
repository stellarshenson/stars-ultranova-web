"""
Stars Nova Web - Planetary Defenses and Planetary Scanners
Ported from Common/Defenses.cs

Defense coverage math plus the best-available selection rules for
planetary defense types and planetary scanners. The C# reference never
upgrades either installation type (see the per-function notes); the
selection helpers implement the canonical Stars! rules using the
component catalog data as-is.
"""

from typing import List, Optional

from .components.component import Component
from .components.component_loader import get_component_loader
from .data_structures.tech_level import TechLevel
from .game_objects.item import ItemType
from .globals import MAX_DEFENSES

# Component catalog path (duplicated from services/design_builder.py -
# core must not import from services)
COMPONENTS_XML = "backend/data/components.xml"


# Base defense coverage per installed defense unit, by defense type.
# Ported from Defenses.cs static constructor (lines 44-51). The C#
# table is keyed by short names ("Missile"/"Laser"/"Planet"/"Neutron");
# the web keys by the full component names stored in star.defense_type.
DEFENSE_BASE_COVERAGE = {
    "SDI": 0.0099,
    "Missile Battery": 0.0199,
    "Laser Battery": 0.0239,
    "Planetary Shield": 0.0299,
    "Neutron Shield": 0.0379,
    "None": 0.0,
}

# Defense type unlock ladder: (component name, Energy tech required)
# from the PlanetaryInstallations entries in components.xml.
DEFENSE_TYPE_LADDER = [
    ("SDI", 0),
    ("Missile Battery", 5),
    ("Laser Battery", 10),
    ("Planetary Shield", 16),
    ("Neutron Shield", 23),
]


def _catalog():
    """Lazily loaded component catalog singleton."""
    loader = get_component_loader()
    if not loader.is_loaded:
        loader.load(COMPONENTS_XML)
    return loader


def race_trait_codes(race) -> List[str]:
    """
    Trait codes (LRTs + PRT) for component availability checks
    (mirrors services/design_builder._race_traits; the PRT lives in
    race.primary_trait, not in the race.traits set).
    """
    if race is None:
        return []
    return list(race.traits) + [getattr(race, 'primary_trait', '')]


def compute_defense_coverage(star) -> dict:
    """
    Compute a star's defense coverage factors from its CURRENT
    defense type.

    Ported from Defenses.cs ComputeDefenseCoverage (lines 58-85):
        PopulationCoverage = 1 - (1 - base)^defenses
        BuildingCoverage   = PopulationCoverage * 0.5
        InvasionCoverage   = PopulationCoverage * 0.75
        SmartBombCoverage  = 1 - (1 - base*0.5)^defenses
        SummaryCoverage    = int(((buildings + pop + invasion)/3) * 100)

    A defense type of "None" (or unknown) gives zero coverage
    (Defenses.cs lines 60-68).
    """
    defenses = min(MAX_DEFENSES, getattr(star, 'defenses', 0))
    defense_type = getattr(star, 'defense_type', "None")
    base = DEFENSE_BASE_COVERAGE.get(defense_type, 0.0)

    if defenses <= 0 or base <= 0:
        return {"population": 0.0, "buildings": 0.0, "invasion": 0.0,
                "smart": 0.0, "summary": 0}

    population = 1.0 - (1.0 - base) ** defenses
    buildings = population * 0.5
    invasion = population * 0.75
    smart = 1.0 - (1.0 - base * 0.5) ** defenses
    summary = int(((buildings + population + invasion) / 3) * 100)
    return {"population": population, "buildings": buildings,
            "invasion": invasion, "smart": smart, "summary": summary}


def best_defense_type(research_levels: TechLevel,
                      race_traits: Optional[List[str]] = None) -> str:
    """
    Best planetary defense type the owner can research and use.

    Canonical Stars! rule - the C# reference is a stub: DefenseType is
    assigned exactly once, "SDI" on the homeworld at game creation
    (StarMapInitialiser.cs:463, "TODO get from component list"), and is
    never upgraded by research nor set on colonies, so their built
    defenses give zero coverage. Canonically all of a player's
    planetary defenses are always of the best researched type.

    Race restrictions follow the components.xml data as-is: AR races
    get no planetary defenses; WM races cannot use Laser Battery,
    Planetary Shield or Neutron Shield (canonical Stars! forbids WM
    only the two shields; the XML is ported unmodified per project
    rules). Returns "None" when no defense type is usable.
    """
    loader = _catalog()
    traits = list(race_traits) if race_traits is not None else []
    best = "None"
    best_base = 0.0
    for name, _energy_req in DEFENSE_TYPE_LADDER:
        component = loader.get_component(name)
        if component is None:
            continue
        if not component.meets_tech_requirements(research_levels):
            continue
        if not component.is_available_to_race(traits):
            continue
        base = DEFENSE_BASE_COVERAGE.get(name, 0.0)
        if base > best_base:
            best = name
            best_base = base
    return best


def best_planetary_scanner(race_traits: Optional[List[str]],
                           research_levels: TechLevel
                           ) -> Optional[Component]:
    """
    Best planetary scanner the owner can research and use.

    Deviation from C# (which is a stub): StarUpdateStep.cs:209-225
    replaces every owned star's ScannerType with whichever planetary
    scanner just unlocked - no better-than check, no race-restriction
    filtering, and star.ScanRange is never updated (it stays 50
    forever, StarMapInitialiser.cs:464 TODO). Canonical Stars! keeps
    every planet on the best usable planetary scanner and its ranges;
    NAS races cannot use the Snoopers and AR races get no planetary
    scanners (components.xml restrictions). Picks the highest
    NormalScan (PenetratingScan breaks ties); returns None when no
    scanner is usable.
    """
    loader = _catalog()
    traits = list(race_traits) if race_traits is not None else []
    best = None
    for component in loader.get_components_by_type(
            ItemType.PLANETARY_INSTALLATIONS):
        if not component.has_property("Scanner"):
            continue
        if not component.is_available_to_race(traits):
            continue
        if not component.meets_tech_requirements(research_levels):
            continue
        if best is None or (
                (component.scan_range_normal,
                 component.scan_range_penetrating)
                > (best.scan_range_normal, best.scan_range_penetrating)):
            best = component
    return best
