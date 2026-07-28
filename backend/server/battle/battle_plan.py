"""
Stars Nova Web - Battle Plan
Ported from Common/DataStructures/BattlePlan.cs

Player-defined battle tactics and targeting priorities.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Dict


class Victims(IntEnum):
    """
    Target priority types for battle plans.

    Ported from Global.Victims enum.
    """
    STARBASE = 0
    BOMBER = 1
    CAPITAL_SHIP = 2
    ESCORT = 3
    ARMED_SHIP = 4
    ANY_SHIP = 5
    SUPPORT_SHIP = 6
    # Web-only tier: freighters and fuel transports were previously
    # indistinguishable from every other unarmed ship under
    # SUPPORT_SHIP (see backend/core/components/ship_role.py)
    LOGISTICS = 7
    # Web-only tier: a boarding ship is armed but is not the escort or
    # capital its power rating would otherwise file it as, so an order
    # can hunt boarders or screen a prize crew off a convoy
    BOARDER = 8


# Tactic strings, exactly as in the C# BattlePlans dialog
# (BattlePlans.Designer.cs:168-174). BattleEngine.cs never consumes
# Tactic (its line 603 TODO admits fleeing is unimplemented); the Ron
# engine honors these per canonical Stars! rules.
TACTICS = [
    "Disengage",
    "Disengage if Challenged",
    "Maximise Damage",
    "Maximise Damage Ratio",
    "Maximise Net Damage",
    "Minimise Damage to Self",
    # Web-only tactic (user requirement "long distance + closeup
    # finishoff"; docs/research-engagement-range.md section 3): hold
    # at longest range like Maximise Damage Ratio, then close like
    # Maximise Damage once the close-for-the-kill trigger fires -
    # the one genuinely new mechanic of the engagement-range decision
    "Salvo then Close",
]

# "Salvo then Close" commits to the run-in when its target's armour
# falls to or below this percent of what it entered the battle with,
# or when the target begins disengaging. Deliberately a module
# constant rather than a per-plan dial: a threshold the commander
# must tune is a dial on the primary path, which the governing
# cognitive-load principle rules out
# (docs/research-engagement-range.md:57)
CLOSE_FOR_KILL_ARMOUR_PERCENT = 50.0

# Attack-who strings, exactly as in the C# dialog
# (BattlePlans.Designer.cs:147-150). "Enemies and Neutrals" exists in
# the dialog but BattleEngine.cs:479-493 never checks it - honored here
# per canonical Stars! rules.
ATTACK_OPTIONS = [
    "Enemies",
    "Enemies and Neutrals",
    "Everyone",
]

# Display labels for the web dialog's five target tiers. The C# dialog
# offers a different 7-string list ("Any", "Armed Ships", "Bombers",
# "Freighters", "None", "Starbase", "Unarmed Ships",
# BattlePlans.Designer.cs:131-138) tied to the 2-tier string model
# (BattlePlan.cs:37-45); the web port keeps the later stars-nova trunk
# 5-tier Victims model the Ron engine consumes.
VICTIMS_LABELS = {
    Victims.STARBASE: "Starbase",
    Victims.BOMBER: "Bomber",
    Victims.CAPITAL_SHIP: "Capital Ship",
    Victims.ESCORT: "Escort",
    Victims.ARMED_SHIP: "Armed Ship",
    Victims.ANY_SHIP: "Any Ship",
    Victims.SUPPORT_SHIP: "Support Ship",
    Victims.LOGISTICS: "Logistics",
    Victims.BOARDER: "Boarding Ship",
}

# Tier numbers returned by RonBattleEngine._get_priority, carried into
# BattleStepTarget so a replay can name the tier that picked a target.
PRIORITY_TIER_LABELS = {
    7: "Primary",
    6: "Secondary",
    5: "Tertiary",
    4: "Quaternary",
    3: "Quinary",
}

# Stance - the one doctrine axis added on top of the canonical tactic
# list. Canonical Stars! tactics carry no stat modifiers at all (they
# are pure movement AI, docs/research-battle-doctrine.md section 1),
# so the tactic stays the POSITIONAL layer and stance is the only
# statistical layer. The research rejected symmetric damage-dealt
# versus damage-taken multipliers with a reason: in a fight to
# annihilation they change only the round count. These modifiers are
# therefore deliberately asymmetric in what they buy:
#
#   - initiative front-loads fire inside a round; a stack killed
#     before it fires contributes nothing, so firing order is not a
#     symmetric scaling
#   - accuracy applies to MISSILES ONLY, so it is worth nothing to a
#     beam fleet - the enemy's weapon class decides its value
#   - the shield multiplier touches SHIELDS ONLY, never armour; beams
#     are stopped by shields first while missiles split their damage,
#     so again the enemy's build decides what it is worth
#   - the sharpest cost: Aggressive forfeits disengagement entirely
#
STANCES = [
    "Aggressive",
    "Balanced",
    "Defensive",
]


@dataclass(frozen=True)
class StanceModifiers:
    """The four levers a stance moves. Balanced moves none of them."""
    initiative: int = 0
    missile_accuracy: float = 1.0
    shields: float = 1.0
    may_disengage: bool = True
    disengage_moves: int = 7


STANCE_MODIFIERS: Dict[str, StanceModifiers] = {
    "Aggressive": StanceModifiers(
        initiative=2, missile_accuracy=1.10, shields=0.80,
        may_disengage=False, disengage_moves=7),
    "Balanced": StanceModifiers(),
    "Defensive": StanceModifiers(
        initiative=-2, missile_accuracy=0.90, shields=1.25,
        may_disengage=True, disengage_moves=5),
}


# Posture - the formation layer, orthogonal to stance. Brace is a
# positional commitment (it never closes), which a longer-ranged
# enemy punishes for free; Scatter buys survivability against area
# effects and escape speed with concentration of fire.
POSTURES = [
    "Standard",
    "Brace",
    "Scatter",
]


@dataclass(frozen=True)
class PostureModifiers:
    """
    holds_position - the stack never moves, so it never closes and
        can never accumulate the moves a disengagement needs
    shields - multiplier on the shield pool, stacking with stance
    splash_taken - multiplier on missile MISS damage (the engine's
        area effect, RonBattleEngine._fire_missile)
    incoming_missile_accuracy - multiplier on the accuracy of MISSILES
        fired at this stack; a spread-out formation is harder to guide
        a torpedo into and beams are unaffected, so what this buys is
        decided by the enemy's weapon class, not by its size
    damage_dealt - multiplier on this stack's own hit power
    weapon_range_bonus - squares added to every weapon's reach, the
        bonus canonical Stars! gives a starbase for fighting from a
        fixed emplacement, which is what a braced stack is
    disengage_moves_delta - change to the moves a disengage needs
    """
    holds_position: bool = False
    shields: float = 1.0
    splash_taken: float = 1.0
    incoming_missile_accuracy: float = 1.0
    damage_dealt: float = 1.0
    weapon_range_bonus: int = 0
    disengage_moves_delta: int = 0


POSTURE_MODIFIERS: Dict[str, PostureModifiers] = {
    "Standard": PostureModifiers(),
    # Brace fights as an emplacement: a bigger shield pool and the
    # starbase range bonus, paid for by never closing - a braced beam
    # line facing a stand-off enemy never fires a shot - and by firing
    # deliberately rather than pressing the attack. The gunnery price
    # is not decoration: never closing turned out to cost almost
    # nothing once the engine stopped overshooting its targets
    # (DEF-30), because an emplaced line fights concentrated in one
    # square while a manoeuvring force disperses and arrives
    # piecemeal. Without it Brace won every matchup in the
    # anti-degeneracy round-robin (tests/unit/test_battle_degeneracy)
    "Brace": PostureModifiers(
        holds_position=True, shields=1.30, weapon_range_bonus=1,
        damage_dealt=0.80),
    # Scatter is spread out: harder to guide a torpedo into, half the
    # splash from a missile that misses, and two fewer board moves to
    # break off - paid for with concentration of fire. The evasion is
    # worth nothing against beams, so the enemy's weapon class decides
    # what the posture buys
    "Scatter": PostureModifiers(
        splash_taken=0.5, incoming_missile_accuracy=0.85,
        damage_dealt=0.85, disengage_moves_delta=-2),
}

# Never fewer than this many board moves to leave a battle, however
# many reductions stance and posture stack up
MIN_DISENGAGE_MOVES = 3


# Withdrawal threshold - when a stack breaks off and runs, generalising
# the canonical "Disengage if Challenged" tactic (which is the "On
# Damage" threshold in tactic form).
WITHDRAW_OPTIONS = [
    "Never",
    "On Damage",
    "Half Armour",
    "Outnumbered",
]

# A withdrawal is a disorderly break-off, not a free exit: every
# surviving ship in the fleet carries this much damage away from the
# battle (percent of armour, healed by the normal repair step) and the
# fleet's remaining waypoint orders are cancelled
WITHDRAWAL_DAMAGE_PERCENT = 15.0

# "Outnumbered" fires when the hostile side fields at least this
# multiple of the stack's own side in armed ships
OUTNUMBERED_RATIO = 2.0


# Boarding order - whether the fleet will try to take a prize instead
# of only shooting at one. Web-only extension (user directive, "add
# boarding ships and boarding battle plans - to take over ships - but
# at great risk to self"; the C# reference has no boarding). "Never" is
# the default and the whole of the old behaviour, so a plan written
# before boarding existed, and a commander who never opens the battle
# screen, never gambles a crew.
BOARDING_ORDERS = [
    "Never",
    "When Able",
]

# Boarding is not a free action, and these three numbers are what stop
# it becoming one:
#
# - the odds are a strength ratio, so a like-for-like attempt is a coin
#   flip, and they are clamped at both ends: overwhelming marines still
#   lose one attempt in seven, and a hopeless one still gets a chance
# - a failed attempt costs the boarder half the armour it entered the
#   battle with, applied at once and able to kill it outright
# - the prize is taken battered, not intact
BOARDING_MIN_CHANCE = 0.05
BOARDING_MAX_CHANCE = 0.85
BOARDING_FAILURE_ARMOR_PERCENT = 50.0
BOARDING_PRIZE_DAMAGE_PERCENT = 50.0


# Battle plan cap: the canonical Stars! allowance of 14 player plans
# (C# absent - the Nova dialog never implemented plan editing,
# BattlePlans.Designer.cs newPlan/modifyPlan buttons are disabled)
# plus the six admiralty standard plans, which are seeded into every
# empire and must not eat the commander's own allowance.
MAX_BATTLE_PLANS = 20


@dataclass
class BattlePlan:
    """
    Player-defined battle tactics and targeting priorities.

    Ported from BattlePlan.cs (139 lines).
    """
    name: str = "Default"
    primary_target: int = 0  # Victims enum value
    secondary_target: int = 1
    tertiary_target: int = 3
    quaternary_target: int = 5
    quinary_target: int = 6
    tactic: str = "Maximise Damage"
    attack: str = "Enemies"  # "Everyone", "Enemies", or specific
    target_id: int = 0  # Empire ID to target when attack is specific
    # Doctrine axes. The defaults are the no-modifier values, so a plan
    # deserialized from a save written before doctrine existed behaves
    # exactly as it did (see from_dict).
    stance: str = "Balanced"
    posture: str = "Standard"
    withdraw: str = "Never"
    board: str = "Never"

    @property
    def stance_modifiers(self) -> StanceModifiers:
        """Modifier table row for this plan's stance."""
        return STANCE_MODIFIERS.get(self.stance, STANCE_MODIFIERS["Balanced"])

    @property
    def posture_modifiers(self) -> PostureModifiers:
        """Modifier table row for this plan's posture."""
        return POSTURE_MODIFIERS.get(self.posture, POSTURE_MODIFIERS["Standard"])

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "primary_target": self.primary_target,
            "secondary_target": self.secondary_target,
            "tertiary_target": self.tertiary_target,
            "quaternary_target": self.quaternary_target,
            "quinary_target": self.quinary_target,
            "tactic": self.tactic,
            "attack": self.attack,
            "target_id": self.target_id,
            "stance": self.stance,
            "posture": self.posture,
            "withdraw": self.withdraw,
            "board": self.board,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BattlePlan':
        """Deserialize from dictionary."""
        return cls(
            name=data.get("name", "Default"),
            primary_target=data.get("primary_target", 0),
            secondary_target=data.get("secondary_target", 1),
            tertiary_target=data.get("tertiary_target", 3),
            quaternary_target=data.get("quaternary_target", 5),
            quinary_target=data.get("quinary_target", 6),
            tactic=data.get("tactic", "Maximise Damage"),
            attack=data.get("attack", "Enemies"),
            target_id=data.get("target_id", 0),
            # Saves written before doctrine existed carry none of these
            # three keys and load as the no-modifier values
            stance=data.get("stance", "Balanced"),
            posture=data.get("posture", "Standard"),
            withdraw=data.get("withdraw", "Never"),
            board=data.get("board", "Never"),
        )


# The six admiralty standard plans. These ARE the doctrine - there is
# no separate doctrine object; every empire's plan list is seeded with
# them and a commander designs further plans alongside them.
#
# The tactic column IS each plan's engagement-range order - the panel
# review of docs/research-engagement-range.md rejected a separate
# axis field as a second movement authority (its O1/D1) and put the
# doctrine on the tactic the engine already obeys: Maximise Damage
# closes to contact, Maximise Damage Ratio stands off at longest
# range, Minimise Damage to Self stands off and falls back
# shieldless, Salvo then Close opens at range then commits.
#
# Tiers below the last meaningful one repeat it: the Victims enum has
# no "None" value, so repeating is how a plan says "nothing further".
ADMIRALTY_PLANS = {
    "Aggressive Assault": BattlePlan(
        name="Aggressive Assault",
        primary_target=int(Victims.CAPITAL_SHIP),
        secondary_target=int(Victims.ARMED_SHIP),
        tertiary_target=int(Victims.STARBASE),
        quaternary_target=int(Victims.BOMBER),
        quinary_target=int(Victims.ANY_SHIP),
        tactic="Maximise Damage",
        stance="Aggressive",
        posture="Standard",
        withdraw="Never",
    ),
    # Balanced keeps the legacy "Default" plan's tiers, attack and
    # no-modifier axes, so a remapped empire hunts the same things.
    # Its TACTIC deliberately differs: Salvo then Close is the
    # engagement-range doctrine - free opening shots, then the kill -
    # where legacy Default always closed to contact
    "Balanced": BattlePlan(
        name="Balanced",
        primary_target=int(Victims.STARBASE),
        secondary_target=int(Victims.BOMBER),
        tertiary_target=int(Victims.ESCORT),
        quaternary_target=int(Victims.ANY_SHIP),
        quinary_target=int(Victims.SUPPORT_SHIP),
        tactic="Salvo then Close",
        stance="Balanced",
        posture="Standard",
        withdraw="Never",
    ),
    "Defensive Hold": BattlePlan(
        name="Defensive Hold",
        primary_target=int(Victims.ARMED_SHIP),
        secondary_target=int(Victims.BOMBER),
        tertiary_target=int(Victims.ANY_SHIP),
        quaternary_target=int(Victims.ANY_SHIP),
        quinary_target=int(Victims.ANY_SHIP),
        tactic="Maximise Damage Ratio",
        stance="Defensive",
        posture="Brace",
        withdraw="Half Armour",
    ),
    "Commerce Raid": BattlePlan(
        name="Commerce Raid",
        primary_target=int(Victims.LOGISTICS),
        secondary_target=int(Victims.SUPPORT_SHIP),
        tertiary_target=int(Victims.BOMBER),
        quaternary_target=int(Victims.ESCORT),
        quinary_target=int(Victims.ESCORT),
        tactic="Salvo then Close",
        stance="Balanced",
        posture="Scatter",
        withdraw="Outnumbered",
    ),
    "Escort Screen": BattlePlan(
        name="Escort Screen",
        primary_target=int(Victims.BOMBER),
        secondary_target=int(Victims.ESCORT),
        tertiary_target=int(Victims.ARMED_SHIP),
        quaternary_target=int(Victims.CAPITAL_SHIP),
        quinary_target=int(Victims.ANY_SHIP),
        tactic="Maximise Damage Ratio",
        stance="Defensive",
        posture="Standard",
        withdraw="Never",
    ),
    "Fighting Retreat": BattlePlan(
        name="Fighting Retreat",
        primary_target=int(Victims.ARMED_SHIP),
        secondary_target=int(Victims.ESCORT),
        tertiary_target=int(Victims.ANY_SHIP),
        quaternary_target=int(Victims.ANY_SHIP),
        quinary_target=int(Victims.ANY_SHIP),
        tactic="Minimise Damage to Self",
        stance="Defensive",
        posture="Scatter",
        withdraw="On Damage",
    ),
}

# The plan a fresh empire hands to every fleet it builds
DEFAULT_EMPIRE_PLAN = "Balanced"


def seed_admiralty_plans(battle_plans: dict) -> dict:
    """
    Ensure every admiralty standard plan is present in a plan list.

    A plan the commander has edited under a standard name is left
    alone - seeding never overwrites. Used both when an empire is
    created and when an older save is loaded.
    """
    for name, plan in ADMIRALTY_PLANS.items():
        if name not in battle_plans:
            battle_plans[name] = BattlePlan.from_dict(plan.to_dict())
    return battle_plans
