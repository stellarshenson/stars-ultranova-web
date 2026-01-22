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
