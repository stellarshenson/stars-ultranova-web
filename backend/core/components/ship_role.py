"""
Stars Nova Web - Ship Battle Role
Web-only extension (no C# equivalent - BattleEngine.cs never derives a
class from a design; its target tiers test raw booleans inline).

Players design their own ships, so a battle role cannot come from a
fixed hull list. It is inferred from the capability aggregates every
design already exposes, in one documented precedence order, so that
every design falls into exactly one role.
"""

from enum import Enum


# Power rating above which an armed design counts as a capital ship.
# Previously an inline literal in RonBattleEngine._target_matches_priority.
CAPITAL_SHIP_POWER_RATING = 2000


class ShipRole(str, Enum):
    """
    The battle role a design is classified into.

    Exactly one role per design. String-valued so the wire format and
    the client read the label directly.
    """
    STARBASE = "Starbase"
    BOMBER = "Bomber"
    BOARDER = "Boarding Ship"
    CAPITAL = "Capital Ship"
    ESCORT = "Escort"
    LOGISTICS = "Logistics"
    SUPPORT = "Support Ship"

    # Enum.__str__ would render "ShipRole.LOGISTICS"; the label is the
    # wire format, so str() must give it
    __str__ = str.__str__


def infer_battle_role(
    is_starbase: bool = False,
    is_bomber: bool = False,
    is_boarder: bool = False,
    has_weapons: bool = False,
    power_rating: int = 0,
    can_refuel: bool = False,
    can_colonize: bool = False,
    heals_others_percent: int = 0,
    cargo_capacity: int = 0,
) -> ShipRole:
    """
    Classify a design into exactly one battle role.

    The cascade is ordered, first match wins, and every design reaches
    a role (the last branch is unconditional):

    1. Starbase      - is_starbase (an immobile base is its own class)
    2. Bomber        - is_bomber (bomb racks make the design a bomber
                       whether or not it also carries weapons)
    3. Boarding Ship - is_boarder (fitted boarding gear multiplying the
                       ship's party by BOARDER_MULTIPLIER_THRESHOLD or
                       more, boarding.py). A specialisation this deep
                       costs the slots it is fitted in, so it outranks
                       whatever the design is otherwise armed with -
                       which is what lets a target-class order hunt or
                       screen against boarders
    4. Capital Ship  - armed with power_rating > CAPITAL_SHIP_POWER_RATING
    5. Escort        - armed with power_rating at or below the threshold
    6. Logistics     - a fuel transport (can_refuel); the tanker fitting
                       is specialised enough to outrank any other cargo
                       signal
    7. Support Ship  - a colonisation module (can_colonize); a colony
                       ship carries a hold, so this must outrank cargo
    8. Support Ship  - a fleet repair hull (heals_others_percent), for
                       the same reason
    9. Logistics     - a cargo hold (cargo_capacity), i.e. a freighter
    10. Support Ship - anything else unarmed (scouts, minelayers,
                       gate tenders)
    """
    if is_starbase:
        return ShipRole.STARBASE
    if is_bomber:
        return ShipRole.BOMBER
    if is_boarder:
        return ShipRole.BOARDER
    if has_weapons:
        if power_rating > CAPITAL_SHIP_POWER_RATING:
            return ShipRole.CAPITAL
        return ShipRole.ESCORT
    if can_refuel:
        return ShipRole.LOGISTICS
    if can_colonize:
        return ShipRole.SUPPORT
    if heals_others_percent > 0:
        return ShipRole.SUPPORT
    if cargo_capacity > 0:
        return ShipRole.LOGISTICS
    return ShipRole.SUPPORT


def battle_role_of(design) -> ShipRole:
    """
    Infer the battle role of any design object.

    Reads the capability aggregates by name so both the full
    ShipDesign and the lightweight SimpleDesign classify identically;
    a missing aggregate simply does not contribute a signal.
    """
    return infer_battle_role(
        is_starbase=bool(getattr(design, 'is_starbase', False)),
        is_bomber=bool(getattr(design, 'is_bomber', False)),
        is_boarder=bool(getattr(design, 'is_boarder', False)),
        has_weapons=bool(getattr(design, 'has_weapons', False)),
        power_rating=int(getattr(design, 'power_rating', 0) or 0),
        can_refuel=bool(getattr(design, 'can_refuel', False)),
        can_colonize=bool(getattr(design, 'can_colonize', False)),
        heals_others_percent=int(
            getattr(design, 'heals_others_percent', 0) or 0),
        cargo_capacity=int(getattr(design, 'cargo_capacity', 0) or 0),
    )
