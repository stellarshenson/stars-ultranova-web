"""
Stars Nova Web - Boarding Strength
Web-only extension (C# absent - the Nova reference has no boarding of
any kind; acc-crit "Universal boarding capability" and "Boarding
components").

Every ship musters a boarding party out of the crew it already
carries, so boarding strength is DERIVED from what a hull is rather
than read from a hand-written per-hull table. Components multiply that
party; they never create it.
"""


# Crew a hull musters per module slot. The slot count is the only size
# signal the Hull property carries that rises monotonically across the
# whole catalog: hull MASS does not (the shipped Small Freighter is
# recorded at 255 kT, heavier than a Battleship at 222), so a mass term
# would hand a freighter the biggest boarding party in the game. On the
# shipped hulls this gives a Scout 30, a Frigate 40, a Destroyer 70, a
# Battleship 110 and a Dreadnought 130 - a Dreadnought's crew outmuscles
# a Scout's by 4.3 to 1.
BOARDING_CREW_PER_SLOT = 10

# Extra crew a dedicated troop bay carries. A Boarding-only slot holds
# marines whether or not gear has been fitted into it, and that is the
# entire "high crew capacity" of the boarding hull class - the one
# thing a general-purpose hull with free slots cannot buy.
BOARDING_CREW_PER_TROOP_BAY = 30

# Boarding components multiply the party geometrically, per slot and
# across slots, exactly as capacitors multiply beam damage. The clamp
# is the same device as CAPACITOR_MAXIMUM: without it a hull with many
# free slots buys a boarding fight it cannot lose.
BOARDING_MULTIPLIER_MAXIMUM = 6.0

# A design whose fitted gear multiplies its party by at least this much
# has specialised, and the role cascade files it as a Boarding Ship.
# No single component reaches it; the cheapest pair (1.4 x 2.5) does.
BOARDER_MULTIPLIER_THRESHOLD = 3.0

# Hull slot type that accepts boarding gear and nothing else. A hull
# whose ComponentType is exactly this is a troop bay.
TROOP_BAY_SLOT = "Boarding"


def base_boarding_strength(total_slots: int, troop_bays: int = 0) -> int:
    """
    The party a hull musters before any gear is fitted.

    Args:
        total_slots: number of module slots on the hull
        troop_bays: how many of those are Boarding-only slots

    Returns:
        Crew strength, in the arbitrary units the odds model compares.
    """
    return (max(0, int(total_slots)) * BOARDING_CREW_PER_SLOT
            + max(0, int(troop_bays)) * BOARDING_CREW_PER_TROOP_BAY)


def clamp_boarding_multiplier(value: float) -> float:
    """Hold a component multiplier inside [1.0, the maximum]."""
    return max(1.0, min(float(value), BOARDING_MULTIPLIER_MAXIMUM))


def is_boarding_specialist(multiplier: float) -> bool:
    """Whether fitted gear multiplies the party enough to be a class."""
    return float(multiplier) >= BOARDER_MULTIPLIER_THRESHOLD


def troop_bay_count(modules) -> int:
    """Count Boarding-only slots in a list of hull modules."""
    return sum(1 for m in modules
               if (getattr(m, 'component_type', '') or '').strip()
               == TROOP_BAY_SLOT)
