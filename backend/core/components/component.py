"""
Stars Nova Web - Component
Ported from Common/Components/Component.cs and property classes.

Component class defining features common to all component types.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from enum import Enum

from ..data_structures.resources import Resources
from ..data_structures.tech_level import TechLevel
from ..game_objects.item import Item, ItemType
from ..race.traits import RaceRestriction


# Property type keys matching C# Component.PropertyKeys
PROPERTY_KEYS = [
    "Armor", "Beam Deflector", "Bomb", "Battle Movement", "Capacitor", "Cargo",
    "Cloak", "Colonizer", "Computer", "Defense", "Deflector", "Energy Dampener",
    "Engine", "Fuel", "Gate", "Hull", "Hull Affinity", "Jammer", "Mass Driver",
    "Mine Layer", "Mine Layer Efficiency", "Robot", "Orbital Adjuster",
    "Radiation", "Scanner", "Shield", "Tachyon Detector", "Terraforming",
    "Transport Ships Only", "Weapon"
]


class WeaponType(Enum):
    """Enumeration of weapon types."""
    STANDARD_BEAM = "standardBeam"
    SHIELD_SAPPER = "shieldSapper"
    GATLING_GUN = "gatlingGun"
    TORPEDO = "torpedo"
    MISSILE = "missile"


@dataclass
class ComponentProperty:
    """
    Base class for component properties.

    Stores property data as a flexible dictionary to handle all property types.
    Ported from ComponentProperty.cs and derived classes.
    """
    property_type: str = ""
    values: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a property value."""
        return self.values.get(key, default)

    def set(self, key: str, value: Any):
        """Set a property value."""
        self.values[key] = value

    def clone(self) -> 'ComponentProperty':
        """Create a copy of this property."""
        return ComponentProperty(
            property_type=self.property_type,
            values=dict(self.values)
        )

    # Weapon-specific properties
    @property
    def is_beam(self) -> bool:
        """Check if weapon is a beam type."""
        if self.property_type != "Weapon":
            return False
        group = self.values.get("Group", "")
        return group in ["standardBeam", "shieldSapper", "gatlingGun"]

    @property
    def is_missile(self) -> bool:
        """Check if weapon is a missile type."""
        if self.property_type != "Weapon":
            return False
        group = self.values.get("Group", "")
        return group in ["torpedo", "missile"]

    def beam_dispersal(self, distance_squared: float) -> float:
        """
        Calculate beam dispersal at distance.

        Ported from Weapon.cs beamDispersal().
        90% at max range, 100% at same location.
        """
        weapon_range = self.values.get("Range", 1)
        return 100.0 - 10 * (distance_squared / (weapon_range * weapon_range))

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "property_type": self.property_type,
            "values": dict(self.values)
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ComponentProperty':
        """Deserialize from dictionary."""
        return cls(
            property_type=data.get("property_type", ""),
            values=dict(data.get("values", {}))
        )


@dataclass
class Component(Item):
    """
    Component class defining features common to all component types.

    One or more specific component properties are contained in the
    properties collection.

    Ported from Component.cs.
    """
    mass: int = 0
    cost: Resources = field(default_factory=Resources)
    required_tech: TechLevel = field(default_factory=TechLevel)
    description: str = ""
    image_file: str = ""
    restrictions: RaceRestriction = field(default_factory=RaceRestriction)
    properties: Dict[str, ComponentProperty] = field(default_factory=dict)

    def get_property(self, property_type: str) -> Optional[ComponentProperty]:
        """Get a property by type."""
        return self.properties.get(property_type)

    def has_property(self, property_type: str) -> bool:
        """Check if component has a property."""
        return property_type in self.properties

    def add_property(self, prop: ComponentProperty):
        """Add a property to this component."""
        self.properties[prop.property_type] = prop

    # Convenience accessors for common properties
    @property
    def armor_value(self) -> int:
        """Get armor value if component has armor property."""
        prop = self.get_property("Armor")
        return prop.values.get("Value", 0) if prop else 0

    @property
    def shield_value(self) -> int:
        """Get shield value if component has shield property."""
        prop = self.get_property("Shield")
        return prop.values.get("Value", 0) if prop else 0

    @property
    def fuel_capacity(self) -> int:
        """Get fuel capacity if component has fuel property."""
        prop = self.get_property("Fuel")
        return prop.values.get("Capacity", 0) if prop else 0

    @property
    def cargo_capacity(self) -> int:
        """Get cargo capacity if component has cargo property."""
        prop = self.get_property("Cargo")
        return prop.values.get("Value", 0) if prop else 0

    @property
    def cloak_percent(self) -> float:
        """Get cloak percentage if component has cloak property."""
        prop = self.get_property("Cloak")
        return prop.values.get("Value", 0.0) if prop else 0.0

    @property
    def scan_range_normal(self) -> int:
        """Get normal scan range if component has scanner property."""
        prop = self.get_property("Scanner")
        return prop.values.get("NormalScan", 0) if prop else 0

    @property
    def scan_range_penetrating(self) -> int:
        """Get penetrating scan range if component has scanner property."""
        prop = self.get_property("Scanner")
        return prop.values.get("PenetratingScan", 0) if prop else 0

    def is_available_to_race(self, race_traits: list) -> bool:
        """Check if this component is available to a race with given traits."""
        return self.restrictions.is_available_to_race(race_traits)

    def meets_tech_requirements(self, tech_level: TechLevel) -> bool:
        """Check if tech level meets requirements."""
        return tech_level >= self.required_tech

    def clone(self) -> 'Component':
        """Create a deep copy of this component."""
        new_component = Component(
            name=self.name,
            item_type=self.item_type,
            mass=self.mass,
            cost=Resources(
                self.cost.ironium,
                self.cost.boranium,
                self.cost.germanium,
                self.cost.energy
            ),
            required_tech=self.required_tech.clone(),
            description=self.description,
            image_file=self.image_file,
            restrictions=RaceRestriction(dict(self.restrictions.restrictions)),
            properties={}
        )
        # Copy key using the property setter
        new_component.key = self.key
        for prop_type, prop in self.properties.items():
            new_component.properties[prop_type] = prop.clone()
        return new_component

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "key": self.key,
            "name": self.name,
            "item_type": self.item_type.name,
            "owner": self.owner,
            "mass": self.mass,
            "cost": self.cost.to_dict(),
            "required_tech": self.required_tech.to_dict(),
            "description": self.description,
            "image_file": self.image_file,
            "restrictions": self.restrictions.to_dict(),
            "properties": {
                k: v.to_dict() for k, v in self.properties.items()
            }
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Component':
        """Deserialize from dictionary."""
        component = cls(
            name=data.get("name", ""),
            item_type=ItemType[data.get("item_type", "NONE")],
            mass=data.get("mass", 0),
            cost=Resources.from_dict(data.get("cost", {})),
            required_tech=TechLevel.from_dict(data.get("required_tech", {})),
            description=data.get("description", ""),
            image_file=data.get("image_file", ""),
            restrictions=RaceRestriction.from_dict(data.get("restrictions", {})),
            properties={}
        )
        # Set key using property setter
        if "key" in data:
            component.key = data["key"]
        for prop_type, prop_data in data.get("properties", {}).items():
            component.properties[prop_type] = ComponentProperty.from_dict(prop_data)
        return component
