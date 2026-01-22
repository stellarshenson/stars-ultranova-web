"""
Stars Nova Web - Race Traits
Ported from Common/RaceDefinition/AllTraits.cs

Trait definitions and restriction system.
"""

from enum import IntEnum
from dataclasses import dataclass, field
from typing import Dict


class RaceAvailability(IntEnum):
    """
    Enumeration of ways a trait can affect component availability.

    Ported from RaceRestriction.cs.
    """
    NOT_AVAILABLE = 0  # Race with trait cannot use the component
    NOT_REQUIRED = 1   # Trait has no effect on availability
    REQUIRED = 2       # Only races with trait can use the component


# Primary Racial Traits (PRTs) - 10 total
PRIMARY_TRAIT_KEYS = [
    "HE",   # Hyper Expansion
    "SS",   # Super Stealth
    "WM",   # War Monger
    "CA",   # Claim Adjuster
    "IS",   # Inner Strength
    "SD",   # Space Demolition
    "PP",   # Packet Physics
    "IT",   # Interstellar Traveler
    "AR",   # Artificial Reality
    "JOAT"  # Jack of all Trades
]

# Lesser Racial Traits (LRTs) - 14 total
SECONDARY_TRAIT_KEYS = [
    "IFE",  # Improved Fuel Efficiency
    "TT",   # Total Terraforming
    "ARM",  # Advanced Remote Mining
    "ISB",  # Improved Star Bases
    "GR",   # Generalised Research
    "UR",   # Ultimate Recycling
    "MA",   # Mineral Alchemy
    "NRSE", # No Ram Scoop Engines
    "OBRM", # Cheap Engines (Only Basic Remote Mining in C#)
    "CE",   # Cheap Engines
    "NAS",  # No Advanced Scanners
    "LSP",  # Low Starting Population
    "BET",  # Bleeding Edge Technology
    "RS"    # Regenerating Shields
]

# All trait keys combined
ALL_TRAIT_KEYS = PRIMARY_TRAIT_KEYS + SECONDARY_TRAIT_KEYS

NUMBER_OF_PRIMARY_TRAITS = 10
NUMBER_OF_SECONDARY_TRAITS = 14

# Human-readable names for traits
TRAIT_NAMES = {
    "HE": "Hyper Expansion",
    "SS": "Super Stealth",
    "WM": "War Monger",
    "CA": "Claim Adjuster",
    "IS": "Inner Strength",
    "SD": "Space Demolition",
    "PP": "Packet Physics",
    "IT": "Interstellar Traveler",
    "AR": "Artificial Reality",
    "JOAT": "Jack of all Trades",
    "IFE": "Improved Fuel Efficiency",
    "TT": "Total Terraforming",
    "ARM": "Advanced Remote Mining",
    "ISB": "Improved Star Bases",
    "GR": "Generalised Research",
    "UR": "Ultimate Recycling",
    "MA": "Mineral Alchemy",
    "NRSE": "No Ram Scoop Engines",
    "OBRM": "Only Basic Remote Mining",
    "CE": "Cheap Engines",
    "NAS": "No Advanced Scanners",
    "LSP": "Low Starting Population",
    "BET": "Bleeding Edge Technology",
    "RS": "Regenerating Shields"
}


@dataclass
class RaceRestriction:
    """
    Component restriction based on race traits.

    Ported from RaceRestriction.cs.
    """
    restrictions: Dict[str, RaceAvailability] = field(default_factory=dict)

    def __post_init__(self):
        """Initialize all traits to not_required if not provided."""
        for trait in ALL_TRAIT_KEYS:
            if trait not in self.restrictions:
                self.restrictions[trait] = RaceAvailability.NOT_REQUIRED

    def set_restriction(self, trait: str, availability: RaceAvailability):
        """Set the availability for a particular trait."""
        self.restrictions[trait] = availability

    def availability(self, trait: str) -> RaceAvailability:
        """Get the affect on availability of the given trait."""
        return self.restrictions.get(trait, RaceAvailability.NOT_REQUIRED)

    def is_available_to_race(self, race_traits: list) -> bool:
        """
        Check if a component is available to a race with the given traits.

        Args:
            race_traits: List of trait codes the race has

        Returns:
            True if component is available, False otherwise
        """
        for trait, availability in self.restrictions.items():
            has_trait = trait in race_traits

            if availability == RaceAvailability.REQUIRED and not has_trait:
                return False
            if availability == RaceAvailability.NOT_AVAILABLE and has_trait:
                return False

        return True

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        # Only include non-default restrictions
        return {
            trait: int(avail)
            for trait, avail in self.restrictions.items()
            if avail != RaceAvailability.NOT_REQUIRED
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'RaceRestriction':
        """Deserialize from dictionary."""
        restrictions = {}
        for trait, avail in data.items():
            restrictions[trait] = RaceAvailability(int(avail))
        return cls(restrictions=restrictions)

    def __str__(self) -> str:
        """String representation of restrictions."""
        parts = []
        for trait, availability in self.restrictions.items():
            if availability == RaceAvailability.REQUIRED:
                parts.append(f"Requires {TRAIT_NAMES.get(trait, trait)}")
            elif availability == RaceAvailability.NOT_AVAILABLE:
                parts.append(f"Not available with {TRAIT_NAMES.get(trait, trait)}")
        return "; ".join(parts) if parts else "No restrictions"
