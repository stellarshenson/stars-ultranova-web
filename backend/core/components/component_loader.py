"""
Stars Nova Web - Component Loader
Parses components.xml and loads all game components.

Ported from Component.cs XML loading logic.
"""

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional
import logging

from .component import Component, ComponentProperty
from ..data_structures.resources import Resources
from ..data_structures.tech_level import TechLevel, RESEARCH_KEYS
from ..game_objects.item import ItemType
from ..race.traits import RaceRestriction, RaceAvailability, ALL_TRAIT_KEYS

logger = logging.getLogger(__name__)


# Map from XML Type values to ItemType enum
ITEM_TYPE_MAP = {
    "planetaryinstallations": ItemType.PLANETARY_INSTALLATIONS,
    "terraforming": ItemType.TERRAFORMING,
    "bomb": ItemType.BOMB,
    "beamweapons": ItemType.BEAM_WEAPONS,
    "miningrobot": ItemType.MINING_ROBOT,
    "armor": ItemType.ARMOR,
    "shield": ItemType.SHIELD,
    "scanner": ItemType.SCANNER,
    "electrical": ItemType.ELECTRICAL,
    "mechanical": ItemType.MECHANICAL,
    "engine": ItemType.ENGINE,
    "torpedoes": ItemType.TORPEDOES,
    "hull": ItemType.HULL,
    "starbase": ItemType.STARBASE,
    "orbital": ItemType.ORBITAL,
    "gate": ItemType.GATE,
    "defense": ItemType.DEFENSE,
    "weapon": ItemType.WEAPON,
}


class ComponentLoader:
    """
    Loads and manages game components from components.xml.

    Provides access to all component definitions used in the game.
    """

    def __init__(self):
        self.components: Dict[str, Component] = {}
        self.components_by_type: Dict[ItemType, List[Component]] = {}
        self._loaded = False

    def load(self, xml_path: str) -> int:
        """
        Load components from XML file.

        Args:
            xml_path: Path to components.xml

        Returns:
            Number of components loaded
        """
        path = Path(xml_path)
        if not path.exists():
            raise FileNotFoundError(f"Components file not found: {xml_path}")

        tree = ET.parse(xml_path)
        root = tree.getroot()

        count = 0
        for component_node in root.findall("Component"):
            try:
                component = self._parse_component(component_node)
                if component:
                    # Use name as key for lookup
                    self.components[component.name] = component

                    # Index by type
                    if component.item_type not in self.components_by_type:
                        self.components_by_type[component.item_type] = []
                    self.components_by_type[component.item_type].append(component)

                    count += 1
            except Exception as e:
                logger.error(f"Error parsing component: {e}")

        self._loaded = True
        logger.info(f"Loaded {count} components from {xml_path}")
        return count

    def _parse_component(self, node: ET.Element) -> Optional[Component]:
        """Parse a single component from XML element."""
        component = Component()

        for child in node:
            tag = child.tag.lower()

            if tag == "item":
                self._parse_item(child, component)
            elif tag == "mass":
                component.mass = int(child.text or 0)
            elif tag == "cost":
                component.cost = self._parse_cost(child)
            elif tag == "tech":
                component.required_tech = self._parse_tech(child)
            elif tag == "description":
                component.description = child.text or ""
            elif tag == "race_restrictions":
                component.restrictions = self._parse_restrictions(child)
            elif tag == "image":
                component.image_file = (child.text or "").replace("/", "\\")
            elif tag == "property":
                prop = self._parse_property(child)
                if prop:
                    component.add_property(prop)

        return component

    def _parse_item(self, node: ET.Element, component: Component):
        """Parse the Item sub-element."""
        for child in node:
            tag = child.tag.lower()
            if tag == "key":
                component.key = int(child.text or 0)
            elif tag == "name":
                component.name = child.text or ""
            elif tag == "type":
                type_str = (child.text or "").lower()
                component.item_type = ITEM_TYPE_MAP.get(type_str, ItemType.NONE)

    def _parse_cost(self, node: ET.Element) -> Resources:
        """Parse cost resources."""
        ironium = 0
        boranium = 0
        germanium = 0
        energy = 0

        for child in node:
            tag = child.tag.lower()
            value = int(child.text or 0)
            if tag == "ironium":
                ironium = value
            elif tag == "boranium":
                boranium = value
            elif tag == "germanium":
                germanium = value
            elif tag == "energy":
                energy = value

        return Resources(ironium, boranium, germanium, energy)

    def _parse_tech(self, node: ET.Element) -> TechLevel:
        """Parse technology requirements."""
        levels = {}
        for child in node:
            # Match case-insensitive with research keys
            for key in RESEARCH_KEYS:
                if child.tag.lower() == key.lower():
                    levels[key] = int(child.text or 0)
                    break
        return TechLevel(levels=levels)

    def _parse_restrictions(self, node: ET.Element) -> RaceRestriction:
        """Parse race restrictions."""
        restrictions = {}
        for child in node:
            # Match trait key case-insensitive
            for trait in ALL_TRAIT_KEYS:
                if child.tag.lower() == trait.lower():
                    value = int(child.text or 1)
                    restrictions[trait] = RaceAvailability(value)
                    break
        return RaceRestriction(restrictions=restrictions)

    def _parse_property(self, node: ET.Element) -> Optional[ComponentProperty]:
        """Parse a component property."""
        prop = ComponentProperty()
        property_type = None

        for child in node:
            tag = child.tag.lower()
            text = child.text or ""

            if tag == "type":
                property_type = text
                prop.property_type = text
            else:
                # Try to parse as number, fall back to string
                try:
                    if "." in text:
                        prop.values[child.tag] = float(text)
                    else:
                        prop.values[child.tag] = int(text)
                except ValueError:
                    # Handle boolean strings
                    if text.lower() == "true":
                        prop.values[child.tag] = True
                    elif text.lower() == "false":
                        prop.values[child.tag] = False
                    else:
                        prop.values[child.tag] = text

        return prop if property_type else None

    def get_component(self, name: str) -> Optional[Component]:
        """Get a component by name."""
        return self.components.get(name)

    def get_components_by_type(self, item_type: ItemType) -> List[Component]:
        """Get all components of a specific type."""
        return self.components_by_type.get(item_type, [])

    def get_available_components(self, race_traits: List[str],
                                  tech_level: TechLevel) -> List[Component]:
        """
        Get all components available to a race with given traits and tech.

        Args:
            race_traits: List of trait codes the race has
            tech_level: Current tech level of the race

        Returns:
            List of available components
        """
        available = []
        for component in self.components.values():
            if (component.is_available_to_race(race_traits) and
                component.meets_tech_requirements(tech_level)):
                available.append(component)
        return available

    def get_all_hulls(self) -> List[Component]:
        """Get all hull components."""
        return self.get_components_by_type(ItemType.HULL)

    def get_all_engines(self) -> List[Component]:
        """Get all engine components."""
        return self.get_components_by_type(ItemType.ENGINE)

    def get_all_weapons(self) -> List[Component]:
        """Get all weapon components (beams and torpedoes)."""
        weapons = self.get_components_by_type(ItemType.BEAM_WEAPONS)
        weapons.extend(self.get_components_by_type(ItemType.TORPEDOES))
        return weapons

    def get_all_scanners(self) -> List[Component]:
        """Get all scanner components."""
        return self.get_components_by_type(ItemType.SCANNER)

    def get_all_defenses(self) -> List[Component]:
        """Get all defense components (armor and shields)."""
        defenses = self.get_components_by_type(ItemType.ARMOR)
        defenses.extend(self.get_components_by_type(ItemType.SHIELD))
        return defenses

    @property
    def is_loaded(self) -> bool:
        """Check if components have been loaded."""
        return self._loaded

    @property
    def component_count(self) -> int:
        """Get total number of loaded components."""
        return len(self.components)

    def get_stats(self) -> Dict[str, int]:
        """Get component count statistics by type."""
        return {
            item_type.name: len(components)
            for item_type, components in self.components_by_type.items()
        }


# Singleton instance for global access
_loader: Optional[ComponentLoader] = None


def get_component_loader() -> ComponentLoader:
    """Get the global component loader instance."""
    global _loader
    if _loader is None:
        _loader = ComponentLoader()
    return _loader


def load_components(xml_path: str) -> ComponentLoader:
    """
    Load components from XML and return the loader.

    Convenience function that loads into the global instance.
    """
    loader = get_component_loader()
    if not loader.is_loaded:
        loader.load(xml_path)
    return loader
