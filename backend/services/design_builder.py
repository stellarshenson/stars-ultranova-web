"""
Stars Nova Web - Ship Design Builder

Builds a ShipDesign from a light client payload (hull name + slot
allocations), validating slot compatibility, capacity, and tech
requirements. Mirrors the original ShipDesignDialog rules: the hull
grid enforces slot type/capacity structurally, and a non-starbase
design must have an engine (ShipDesignDialog.cs OK_Click).
"""

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..core.components import ShipDesign
from ..core.components.component_loader import (
    get_component_loader, load_components
)
from ..core.game_objects.item import ItemType

COMPONENTS_XML = str(Path(__file__).resolve().parents[1] / "data" / "components.xml")

# Slot ComponentType token -> acceptable component ItemTypes.
# Slot types in components.xml are phrases like "Shield or Armor" or
# "Scanner Electrical Mechanical"; each recognized token widens the set.
SLOT_TOKEN_TYPES = {
    "weapon": {ItemType.WEAPON, ItemType.BEAM_WEAPONS, ItemType.TORPEDOES},
    "engine": {ItemType.ENGINE},
    "shield": {ItemType.SHIELD},
    "armor": {ItemType.ARMOR},
    "electrical": {ItemType.ELECTRICAL},
    "elect": {ItemType.ELECTRICAL},
    "mechanical": {ItemType.MECHANICAL},
    "mech": {ItemType.MECHANICAL},
    "scanner": {ItemType.SCANNER},
    "bomb": {ItemType.BOMB},
    "orbital": {ItemType.ORBITAL, ItemType.GATE},
    "miner": {ItemType.MINING_ROBOT},  # "Robot Miner"
    # Web-only: a "Boarding" slot is a troop bay and takes boarding
    # gear only (backend/core/components/boarding.py)
    "boarding": {ItemType.BOARDING},
}

# "Mine Layer" is two tokens; handled as a phrase
MINE_LAYER_TYPES = {ItemType.MINE_LAYER}

# General purpose slots accept everything except engines and orbitals
GENERAL_PURPOSE_TYPES = (
    SLOT_TOKEN_TYPES["weapon"] | SLOT_TOKEN_TYPES["shield"]
    | SLOT_TOKEN_TYPES["armor"] | SLOT_TOKEN_TYPES["electrical"]
    | SLOT_TOKEN_TYPES["mechanical"] | SLOT_TOKEN_TYPES["scanner"]
    | SLOT_TOKEN_TYPES["bomb"] | SLOT_TOKEN_TYPES["miner"]
    | SLOT_TOKEN_TYPES["boarding"]
    | MINE_LAYER_TYPES
)


def ensure_components_loaded():
    """Load the component catalog if not already loaded."""
    loader = get_component_loader()
    if not loader.is_loaded:
        load_components(COMPONENTS_XML)
    return loader


def slot_accepts(slot_type: str, item_type: ItemType) -> bool:
    """Check whether a hull slot accepts a component item type."""
    lowered = slot_type.lower()
    if "general purpose" in lowered:
        return item_type in GENERAL_PURPOSE_TYPES
    if "mine layer" in lowered and item_type in MINE_LAYER_TYPES:
        return True
    for token in lowered.replace(" or ", " ").split():
        accepted = SLOT_TOKEN_TYPES.get(token)
        if accepted and item_type in accepted:
            return True
    return False


def build_ship_design(
    empire, name: str, hull_name: str, slots: List[dict]
) -> Tuple[Optional[ShipDesign], Optional[str]]:
    """
    Build and validate a ShipDesign from a client design payload.

    Args:
        empire: The designing empire (for tech levels and key allocation).
        name: Design name.
        hull_name: Hull component name (e.g. "Destroyer").
        slots: [{"cell_number": int, "component": str, "count": int}, ...]

    Returns:
        (design, None) on success, (None, error message) on failure.
    """
    loader = ensure_components_loaded()

    if not name or not name.strip():
        return None, "Design name is required"

    hull_comp = loader.get_component(hull_name)
    if hull_comp is None or hull_comp.get_property("Hull") is None:
        return None, f"Unknown hull: {hull_name}"
    if not _tech_ok(empire, hull_comp):
        return None, f"Insufficient tech for hull {hull_name}"
    race_traits = _race_traits(empire)
    if not hull_comp.is_available_to_race(race_traits):
        return None, f"{hull_comp.name} is not available to your race"
    if not _mt_granted(empire, hull_comp):
        return None, f"{hull_comp.name} requires a Mystery Trader grant"

    # Deep copy: Component.clone shares the nested modules list with
    # the catalog, and slot allocation must never mutate the catalog
    import copy
    blueprint = copy.deepcopy(hull_comp)
    hull_values = blueprint.get_property("Hull").values
    module_dicts = {
        m.get("cell_number"): m for m in hull_values.get("modules", [])
    }

    for slot in slots or []:
        cell = slot.get("cell_number")
        comp_name = slot.get("component")
        count = int(slot.get("count", 1))
        if count <= 0 or not comp_name:
            continue

        module = module_dicts.get(cell)
        if module is None:
            return None, f"Hull {hull_name} has no slot {cell}"

        comp = loader.get_component(comp_name)
        if comp is None:
            return None, f"Unknown component: {comp_name}"
        if not slot_accepts(module.get("component_type", ""), comp.item_type):
            return None, (f"Slot {cell} ({module.get('component_type')}) "
                          f"does not accept {comp_name}")
        if count > module.get("component_maximum", 1):
            return None, (f"Slot {cell} holds at most "
                          f"{module.get('component_maximum', 1)} components")
        if not _tech_ok(empire, comp):
            return None, f"Insufficient tech for {comp_name}"
        if not comp.is_available_to_race(race_traits):
            return None, f"{comp.name} is not available to your race"
        if not _mt_granted(empire, comp):
            return None, f"{comp.name} requires a Mystery Trader grant"

        module["allocated_component"] = comp.name
        module["component_count"] = count

    design = ShipDesign()
    design.name = name.strip()
    design.blueprint = blueprint
    design.key = empire.get_next_design_key()
    design.update()

    # Original rule: a ship design must have an engine (starbases exempt)
    if not design.is_starbase and design.engine is None:
        return None, "A ship design must have an engine"

    return design, None


def _mt_granted(empire, component) -> bool:
    """
    Gate Mystery Trader hidden-technology items on a per-empire grant.

    Canonical Stars! hidden technology - the C# reference has only a
    TODO naming the mechanism (GameInitialiser.cs:180 "Mystery Trader
    Items - probably need to implement the idea of 'hidden'
    technology"). Components carrying the "Mystery Trader Item"
    catalog property (components.xml) can never be researched (their
    Tech is all zero) and are buildable only once the trader has
    granted them (empire.mt_components, TurnGenerator reward table).
    """
    if not component.has_property("Mystery Trader Item"):
        return True
    return component.name in getattr(empire, 'mt_components', [])


def _race_traits(empire) -> list:
    """
    Trait codes (PRT + LRTs) for component availability checks.

    RaceRestriction.cs:44-49 semantics: required(2) hulls (e.g. the
    ARM-only miner hulls) need the trait present; not_available(0)
    (e.g. Maxi Miner for OBRM) fails when the trait is present.
    """
    race = getattr(empire, 'race', None)
    if race is None:
        return []
    return list(race.traits) + [race.primary_trait]


def _tech_ok(empire, component) -> bool:
    """Check the empire's research levels against a component's tech."""
    required = getattr(component, 'required_tech', None)
    if required is None:
        return True
    levels = getattr(empire, 'research_levels', None)
    if levels is None:
        return True
    have = levels.levels if hasattr(levels, 'levels') else {}
    for field_name, needed in getattr(required, 'levels', {}).items():
        if needed > 0 and have.get(field_name, 0) < needed:
            return False
    return True
