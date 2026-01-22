"""
Stars Nova Web - Battle Module

Combat resolution system ported from C# BattleEngine.cs and RonBattleEngine.cs.
"""

from .battle_step import (
    BattleStep,
    BattleStepMovement,
    BattleStepTarget,
    BattleStepWeapons,
    BattleStepDestroy,
    TokenDefence,
    WeaponTarget,
)
from .battle_report import BattleReport
from .battle_plan import BattlePlan, Victims
from .stack import Stack, StackToken
from .weapon_details import WeaponDetails, TargetPercent
from .space_allocator import SpaceAllocator
from .battle_engine import BattleEngine
from .ron_battle_engine import RonBattleEngine

__all__ = [
    'BattleStep',
    'BattleStepMovement',
    'BattleStepTarget',
    'BattleStepWeapons',
    'BattleStepDestroy',
    'TokenDefence',
    'WeaponTarget',
    'BattleReport',
    'BattlePlan',
    'Victims',
    'Stack',
    'StackToken',
    'WeaponDetails',
    'TargetPercent',
    'SpaceAllocator',
    'BattleEngine',
    'RonBattleEngine',
]
