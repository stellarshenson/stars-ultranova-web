"""
Stars Nova Web - Terraforming

The C# reference is a stub: Common/Production/TerraformProductionUnit.cs
throws NotImplementedException in IsSkipped/Construct/NeededResources/
ToXml (lines 61-86); its doc comment (lines 27-29) only states the
intent "constructing terraform 1%". No server-side terraform,
instaform, or retro-bomb logic exists in ServerState/. This module
therefore implements the canonical Stars! rules, documented per
function, anchored on the data the C# port does define:

- Star environment fields Gravity/Temperature/Radiation plus
  OriginalGravity/OriginalTemperature/OriginalRadiation (Star.cs:61-66,
  all 0-100 "percentage of permissible range"); the Original* values
  are the pristine pre-terraform environment - the anchor for both the
  terraform tech limit and Retro Bomb reversal.
- Terraforming components in backend/data/components.xml (identical
  set in references/original-game/components.xml): dedicated
  "Gravity/Temp/Radiation +-N" components cost 100 resources/point;
  "Total +-N" components (Race_Restrictions TT=2 = required trait,
  RaceRestriction.cs:44-48) cost 70/point - the TT 30% discount is
  "implemented in component definitions" (GameInitialiser.cs:280).
  DEVIATION NOTE: C# Terraform.cs would carry MaxModifiedGravity/
  Temperature/Radiation payloads (lines 35-37), but neither data file
  contains a single MaxModified* element - the +-N capability is
  encoded only in the component Name, so it is parsed from the name
  here. The data file also has no "Gravity +-11" step (canonical
  Stars! has one); the data file is authoritative for the port.
"""

import re
from typing import Dict, List, Optional, Tuple

from ..core.game_objects.item import ItemType

# Environment variables in fixed tie-break order
VARIABLES = ("gravity", "temperature", "radiation")

# Component names use "Temp" (not Temperature) and the Unicode
# plus-minus sign U+00B1, e.g. "Total ±30", "Temp ±11"
NAME_RE = re.compile(r"^(Gravity|Temp|Radiation|Total) ±(\d+)$")
NAME_TO_VAR = {
    "Gravity": "gravity",
    "Temp": "temperature",
    "Radiation": "radiation",
}


def terraform_ability(race, tech_levels) -> Dict[str, Tuple[int, int]]:
    """
    Best terraform capability per environment variable.

    Returns {variable: (max_n, cost_per_point)} where max_n is the
    largest +-N among Terraforming components the race can use (trait
    restrictions pass, component tech <= tech_levels) and cost is the
    resource cost per point of the component granting it. "Total"
    components apply to all three variables. On equal N the cheaper
    component wins - net effect: TT races pay 70/point via Total
    components, everyone else 100/point.
    """
    from .design_builder import ensure_components_loaded

    loader = ensure_components_loaded()
    traits = [race.primary_trait] + list(race.traits)

    ability = {var: (0, 0) for var in VARIABLES}
    for comp in loader.get_components_by_type(ItemType.TERRAFORMING):
        match = NAME_RE.match(comp.name)
        if match is None:
            continue
        if not comp.is_available_to_race(traits):
            continue
        if not comp.meets_tech_requirements(tech_levels):
            continue

        kind, n = match.group(1), int(match.group(2))
        cost = comp.cost.energy
        targets = VARIABLES if kind == "Total" else (NAME_TO_VAR[kind],)
        for var in targets:
            best_n, best_cost = ability[var]
            if n > best_n or (n == best_n and cost < best_cost):
                ability[var] = (n, cost)

    return ability


def optimum(race, variable: str) -> Optional[int]:
    """
    Race optimum for an environment variable, or None if immune.

    The web port's simplified hab model centres on (min+max)//2 -
    exactly how galaxy_generator seeds homeworlds (galaxy_generator.py
    homeworld block; C# StarMapInitialiser.cs:441-443 uses
    race.OptimumRadiationLevel etc. = tolerance centre). Immune
    variables are never terraformed.
    """
    if getattr(race, f"immune_{variable}"):
        return None
    return (getattr(race, f"{variable}_min")
            + getattr(race, f"{variable}_max")) // 2


def _can_shift(star, race, ability, variable: str) -> bool:
    """One click toward optimum is legal for this variable."""
    opt = optimum(race, variable)
    if opt is None:
        return False
    current = getattr(star, variable)
    if current == opt:
        return False
    new = current + (1 if current < opt else -1)
    if not 0 <= new <= 100:
        return False
    original = getattr(star, f"original_{variable}")
    max_n = ability[variable][0]
    return abs(new - original) <= max_n


def select_terraform_target(star, race, ability) -> Optional[str]:
    """
    Pick the variable a terraform point should improve.

    Canonical rule: the improvable variable (not immune, not at
    optimum, not capped at original +- max_n) with the largest
    habitability deficit |current - optimum|; ties broken in fixed
    order gravity, temperature, radiation.
    """
    best_var = None
    best_deficit = -1
    for var in VARIABLES:
        if not _can_shift(star, race, ability, var):
            continue
        deficit = abs(getattr(star, var) - optimum(race, var))
        if deficit > best_deficit:
            best_var = var
            best_deficit = deficit
    return best_var


def terraform_one_point(star, race, ability) -> Optional[str]:
    """
    Apply one terraform point: shift the selected variable 1 click
    toward the race optimum. Returns the variable shifted, or None
    when nothing is improvable (hab recomputes lazily via
    race.hab_value which reads the star fields live).
    """
    var = select_terraform_target(star, race, ability)
    if var is None:
        return None
    current = getattr(star, var)
    step = 1 if current < optimum(race, var) else -1
    setattr(star, var, current + step)
    return var


def instaform(star, race, ability) -> List[Tuple[str, int, int]]:
    """
    CA instaforming: one free 1-click shift toward optimum per
    environment variable, within the race's terraform tech limit.

    Canonical Stars! CA rule (per task direction); C# has no
    implementation - PrimaryTraits.cs:56 is description-only
    ("Terraforming costs you nothing...").

    Returns [(variable, old, new), ...] for the variables shifted.
    """
    shifts = []
    for var in VARIABLES:
        if not _can_shift(star, race, ability, var):
            continue
        old = getattr(star, var)
        step = 1 if old < optimum(race, var) else -1
        setattr(star, var, old + step)
        shifts.append((var, old, old + step))
    return shifts


def retro_terraform_one_point(star) -> Optional[str]:
    """
    Retro Bomb point (canonical): move the variable with the largest
    |current - original| 1 click back toward its original value.
    Returns the variable, or None when the environment is pristine.
    """
    best_var = None
    best_delta = 0
    for var in VARIABLES:
        delta = abs(getattr(star, var) - getattr(star, f"original_{var}"))
        if delta > best_delta:
            best_var = var
            best_delta = delta
    if best_var is None:
        return None
    current = getattr(star, best_var)
    original = getattr(star, f"original_{best_var}")
    step = 1 if current < original else -1
    setattr(star, best_var, current + step)
    return best_var


def update_empire_terraform_capability(empire) -> None:
    """
    Refresh the EmpireData terraform capability fields (empire_data.py
    gravity/radiation/temperature_mod_capability, port of
    EmpireData.cs) from the race's current component tech.
    """
    if empire.race is None:
        return
    ability = terraform_ability(empire.race, empire.research_levels)
    empire.gravity_mod_capability = ability["gravity"][0]
    empire.temperature_mod_capability = ability["temperature"][0]
    empire.radiation_mod_capability = ability["radiation"][0]
