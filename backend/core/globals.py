"""
Global constants for Stars Nova.
Port of: Common/GlobalDefinitions.cs
"""
from enum import IntEnum


class Victims(IntEnum):
    """Target priority for combat."""
    STARBASE = 0
    CAPITAL_SHIP = 1
    BOMBER = 2
    ESCORT = 3
    SUPPORT_SHIP = 4
    ARMED_SHIP = 5
    ANY_SHIP = 6


class Strategy(IntEnum):
    """Combat strategy options."""
    MAX_DAMAGE_RATIO = 0
    MAXIMISE_DAMAGE = 1
    RUN_AWAY = 2
    SCATTER_AND_RUN = 3
    MIN_DAMAGE_TO_SELF = 4
    KAMAKAZI = 5
    HUMAN_SHIELD = 6
    AR = 7


# Colonists
COLONISTS_PER_KILOTON = 100
LOW_STARTING_POPULATION_FACTOR = 0.7
BASE_CROWDING_FACTOR = 16.0 / 9.0  # From Stars technical FAQ
STARTING_COLONISTS = 25000
STARTING_COLONISTS_ACCELERATED_BBS = 100000
NOMINAL_MAXIMUM_PLANETARY_POPULATION = 1000000
POPULATION_FACTOR_HYPER_EXPANSION = 0.5
GROWTH_FACTOR_HYPER_EXPANSION = 2.0
POPULATION_FACTOR_JACK_OF_ALL_TRADES = 1.2
POPULATION_FACTOR_ONLY_BASIC_REMOTE_MINING = 1.1

# Combat
MAX_WEAPON_RANGE = 7  # Doom/Armageddon on station
MAX_DEFENSES = 100
CAPACITOR_MAXIMUM = 250  # Capacitor.cs:41 - caps beam multiplier at x3.5

# Environment
GRAVITY_MINIMUM = 0.0
GRAVITY_MAXIMUM = 8.0
RADIATION_MINIMUM = 0.0
RADIATION_MAXIMUM = 100.0
TEMPERATURE_MINIMUM = -200.0
TEMPERATURE_MAXIMUM = 200.0

# Production constants
COLONISTS_PER_OPERABLE_FACTORY_UNIT = 10000
FACTORIES_PER_FACTORY_PRODUCTION_UNIT = 10
COLONISTS_PER_OPERABLE_MINING_UNIT = 10000
MINES_PER_MINE_PRODUCTION_UNIT = 10

DEFENSE_IRONIUM_COST = 5
DEFENSE_BORANIUM_COST = 5
DEFENSE_GERMANIUM_COST = 5
DEFENSE_ENERGY_COST = 15

# Mineral alchemy. The C# AlchemyProductionUnit.cs is a stub (all
# methods throw NotImplementedException), so these are the canonical
# Stars! values: 100 resources per unit, 25 with the Mineral Alchemy
# LRT (GameInitialiser.cs:315-318 "One instance of mineral alchemy
# costs 25 resources instead of 100"; SecondaryTraits.cs:66 "four
# times more efficiently"), producing 1 kT of EACH mineral per unit
ALCHEMY_RESOURCE_COST = 100
ALCHEMY_RESOURCE_COST_MA = 25
ALCHEMY_MINERALS_PER_UNIT = 1

# Research constants
DEFAULT_RESEARCH_PERCENTAGE = 10

# Format
SHIP_ICON_NUMBERING_LENGTH = 4

# Turn data
STARTING_YEAR = 2100
DISCARD_FLEET_REPORT_AGE = 1

# Limits
MAX_FLEET_AMOUNT = 51200
MAX_DESIGNS_AMOUNT = 1600
MAX_STARBASE_DESIGNS_AMOUNT = 1000

# Defaults
NOBODY = 0x00000000  # Empire ID 0 = no owner
EVERYONE = NOBODY
NONE = NOBODY
UNSET = -10000

# Minefield
MINE_FIELD_SNAP_TO_GRID_SIZE = 5
MINEFIELD_SNAP_TO_GRID_SIZE = 5  # Alias for consistency

# Stargate rework (user directive 2026-07-13 - deliberate deviations
# from canonical Stars! gate rules, acc-crit "Minefields, Gates,
# Wormholes"):
# 1) Hull size limit: only small and medium hulls may gate; large and
#    capital hulls are REFUSED OUTRIGHT - no over-limit gamble for
#    them (canonical Stars! lets any hull gamble an over-mass jump).
#    Classification is by hull blueprint name (components.xml); hulls
#    absent from the table (starbases, Mineral Packet, S A L V A G E,
#    unknown hulls) are refused.
GATE_HULL_SIZE = {
    # small - couriers, escorts and utility minors
    "Scout": "small",
    "Frigate": "small",
    "Destroyer": "small",
    "Mini-Colony Ship": "small",
    "Colony Ship": "small",
    "Small Freighter": "small",
    "Fuel Transport": "small",
    "Mini Mine Layer": "small",
    "Midget Miner": "small",
    "Mini Bomber": "small",
    # medium - cruiser-weight warships and mid logistics
    "Cruiser": "medium",
    "Privateer": "medium",
    "Rogue": "medium",
    "Medium Freighter": "medium",
    "Super-Fuel Transport": "medium",
    "Mini Miner": "medium",
    "Miner": "medium",
    "Super Mine Layer": "medium",
    "Stealth Bomber": "medium",
    "B-17 Bomber": "medium",
    "Meta Morph": "medium",
    # large - refused at the gate
    "Battle Cruiser": "large",
    "Galleon": "large",
    "Large Freighter": "large",
    "Super Freighter": "large",
    "B-52 Bomber": "large",
    "Maxi Miner": "large",
    "Ultra Miner": "large",
    # capital - refused at the gate
    "Battleship": "capital",
    "Dreadnought": "capital",
    "Nubian": "capital",
}
GATE_ALLOWED_HULL_SIZES = ("small", "medium")
# 2) Star-fuelled range: a gate draws its power from its host star, so
#    its safe range is multiplied by the star's spectral class factor
#    (galaxy_generator assigns classes O..M; O/B giants throw farthest,
#    M dwarfs barely reach). NO gate has unlimited range: "any"-range
#    models (SafeRange -1 in components.xml) clamp to
#    GATE_MAX_BASE_RANGE before the star factor applies. Over-range
#    jumps for small/medium hulls keep the canonical 25% loss / 50%
#    damage gamble.
GATE_SPECTRAL_RANGE_FACTOR = {
    "O": 2.0,
    "B": 1.6,
    "A": 1.3,
    "F": 1.1,
    "G": 1.0,
    "K": 0.8,
    "M": 0.6,
}
GATE_MAX_BASE_RANGE = 800  # ly cap for "any"-range gate models, before the star factor

# Cloaking and tachyon detection
# Canonical Stars! rules - the C# reference is a stub: Fleet.Cloaked is
# only ever SET for ISB starbases (Manufacture.cs:126-134) and no
# detection logic reads it (ScanStep.cs:165 has no cloak term)
MAX_CLOAK_PERCENT = 98           # documented Stars! maximum cloak
SS_BUILT_IN_CLOAK_UNITS = 300    # SS ships: 75% built-in cloak (PrimaryTraits.cs:54)
ISB_STARBASE_CLOAK = 20          # ISB starbases 20% cloaked (Manufacture.cs:133)
TACHYON_DETECTOR_FACTOR = 0.95   # 5% cloak-effectiveness cut per detector (canonical, C# absent)

# Spatial phenomena (web extension - not in original Stars!)
# Dust nebulae impede travel and dampen sensors; galactic storms damage ships
NEBULA_SPEED_PENALTY = 0.4       # Max fractional speed loss in dense dust (density 1.0)
NEBULA_MIN_SPEED_FACTOR = 0.6    # Speed never drops below this fraction
NEBULA_SCAN_PENALTY = 0.5        # Max fractional scanner range loss in dense dust
NEBULA_GLARE_SCAN_PENALTY = 0.15 # Max fractional scanner range loss in emission glow (user directive 2026-07-13; far milder than dust, no speed effect)
STORM_DAMAGE_PER_TURN = 20       # Armor damage percent per turn at LOCAL intensity 1.0

# Galactic storm hazards and shape (user directive 2026-07-13). Storms
# are irregular blobs with a radial intensity field: local intensity is
# 0 at the blob boundary and rises smoothly to the storm's intensity at
# the core; ALL storm effects scale with the local intensity at the
# affected fleet's position.
STORM_SAFE_WARP = 6              # Max warp with no storm mishap risk
STORM_WARP_RISK_PER_WARP = 0.10  # Mishap chance per warp above safe, at local intensity 1.0
STORM_MISHAP_RISK_CAP = 0.75     # Mishap chance never exceeds this
STORM_MISHAP_DAMAGE = 25         # Extra damage percent per token on a mishap, at local intensity 1.0
STORM_SCAN_PENALTY = 0.7         # Max fractional scanner range loss at a storm core (stronger than dust)
STORM_COLONIST_DEATH = 0.10      # Fraction of carried colonists lost per turn at local intensity 1.0
STORM_SHAPE_POINTS = 32          # Radial samples defining the storm blob perimeter
STORM_SHAPE_AMPLITUDE = 0.35     # Max fractional radial deviation of the blob from its base radius

# Storm protection (user directive, wave 4). Fleet storm_protection in
# [0, 1] is computed per token and fleet-min'd (a convoy is only as
# protected as its weakest ship). The sources below are ADDITIVE and
# the sum clamps at 1.0 = total immunity; storm-shield components add
# their own tier value (0.40/0.70/1.00 in components.xml). Hull damage,
# warp-mishap chance, mishap damage and colonist attrition all scale by
# (1 - protection); scan dampening is environmental and never reduced.
# All four constants are provisional - the wave-6 storm balance
# calibration pass will tune them.
STORM_SHIELD_PROTECTION = 0.35   # Conventional shields aboard, at full shield coverage
STORM_ARMOR_PROTECTION = 0.15    # Armor components mounted (hull base armor does not count)
STORM_RAD_RACE_PROTECTION = 0.25 # Radiation-hardened race (immune, or optimum in the extreme band)
STORM_RAD_EXTREME_OPTIMUM = 85   # Radiation optimum at/above this hab click is the extreme band

# Mystery Trader (canonical Stars! feature - the C# reference has only
# a TODO: GameInitialiser.cs:180 "Mystery Trader Items - probably need
# to implement the idea of 'hidden' technology"; built from canonical
# rules per user directive, acc-crit Mystery Trader section). The
# chosen thresholds and odds below are the authoritative numbers,
# mirrored verbatim in the encyclopedia entry (encyclopedia.js).
MT_MIN_YEARS = 40            # First spawn possible at STARTING_YEAR + 40 (mid-game)
MT_LATE_YEARS = 100          # From STARTING_YEAR + 100 the late-game cap applies
MT_SPAWN_CHANCE = 0.0625     # Per-turn spawn roll (1 in 16) while below the active cap
MT_MAX_ACTIVE_EARLY = 1
MT_MAX_ACTIVE_LATE = 3       # "multiple possible late game"
MT_WARP_MIN = 7              # Canonical trader warp band; speed = warp^2 ly/yr
MT_WARP_MAX = 13             # May exceed player warp caps - the trader is special
MT_GIFT_THRESHOLD = 1000     # kT (minerals + colonist kT) for any reward
MT_TIER2_GIFT = 2000
MT_TIER3_GIFT = 4000
MT_MINERAL_BOUNTY_FACTOR = 2 # tier1 mineral reward = 2x gift; tier2 = 3x (factor + 1)

# Mineral packets and mass drivers
# Canonical Stars! mass-driver/packet rules - the C# reference is a
# stub: MassDriver.cs holds only the component property (the driver
# warp rating) and TurnGenerator.cs has no packet code at all. A
# packet flies in a straight line at warp^2 ly/year; flinging above
# the driver's rating decays it in flight; a receiving driver at or
# above the packet's warp catches it safely, anything less takes the
# canonical impact damage (PP halves decay and adds +1 safe warp -
# out of scope, noted).
PACKET_DECAY_RATES = {1: 0.10, 2: 0.25, 3: 0.50}  # fraction lost per year in flight, per warp over the flinging driver's rating (clamped at 3 over)
PACKET_MIN_DECAY = 10            # kT minimum decay per mineral type per decaying year
PACKET_OVERFLING_MAX = 3         # fling allowed up to driver rating + 3
PACKET_MAX_WARP = 13             # absolute fling cap (Ultra Driver 13)
PACKET_DAMAGE_DIVISOR = 160      # rawDamage = (spdPacket - spdReceiver) * kT / 160
PACKET_UNCAUGHT_RECOVERY = 1.0 / 3.0  # uncaught fraction still recovered on the surface

# Beam rating multiplier table [battlespeed_index][range]
# From direct observation of Stars! 2.70j using Hyper Expansion Race
# battlespeed: 0, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5
# range: 3, 2, 1, 0
BEAM_RATING_MULTIPLIER = [
    [0.9, 0.75, 0.6, 0.365],    # 0 battlespeed
    [0.9, 0.75, 0.6, 0.365],    # 0.25
    [1.0, 0.875, 0.7, 0.45],    # 0.5
    [1.05, 0.875, 0.7, 0.524],  # 0.75
    [1.2, 1.0, 0.8, 0.6],       # 1.0
    [1.35, 1.125, 0.9, 0.675],  # 1.25
    [1.5, 1.25, 1.0, 0.749],    # 1.5
    [1.65, 1.375, 1.1, 0.82],   # 1.75
    [1.8, 1.50, 1.2, 0.897],    # 2.0
    [1.95, 1.625, 1.3, 0.973],  # 2.25
    [2.1, 1.75, 1.4, 1.047],    # 2.5
]

# AI ship name prefixes
AI_SMALL_FREIGHTER = " Wheely Bin"
AI_FREIGHTER = " Wheelbarrow"
AI_REPAIRER = " Grease Monkey"
AI_REFUELER = " Mobile Mobil"
AI_DEFENSIVE_DESTROYER = " Tharunka"
AI_DEFENSIVE_CRUISER = " Nulla Nulla"
AI_DEFENSIVE_BATTLE_CRUISER = " Woomera"
AI_BOMBER_COVER_FRIGATE = " Mosquito"
AI_BOMBER_COVER_CRUISER = " Green Hornet"
AI_BOMBER_COVER_BATTLE_CRUISER = " Dr Death"
AI_BOMBER = " Dr Euthanasia"
AI_COLONY_SHIP = " Santa Maria"
AI_SCOUT = " Walkabout"
AI_MINE_LAYER = " Pidgeon"
AI_MINE_SWEEPER = " Pool Guy"
AI_STARBASE = " Death Star"
AI_BEAM_HULL = " Athena"
AI_TORPEDO_HULL = " Spear Fish"

VICTIM_NAMES = [
    "Starbase", "Capital Ship", "Bomber", "Escort",
    "Support ship", "Any Armed ship", "Any ship"
]

STRATEGY_NAMES = [
    "Maximise Damage Ratio", "Maximise Damage", "Run away",
    "Scatter and run in different directions", "Minimise damage to self",
    "Move to enemy centre of mass and self destruct",
    "Shield the bombers", "Shield the Starbase"
]
