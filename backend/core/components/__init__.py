"""
Stars Nova Web - Components Package
"""

from .boarding import (
    BOARDER_MULTIPLIER_THRESHOLD, BOARDING_MULTIPLIER_MAXIMUM,
    base_boarding_strength)
from .component import Component, ComponentProperty
from .component_loader import ComponentLoader, get_component_loader, load_components
from .hull import Hull
from .hull_module import HullModule
from .engine import Engine
from .ship_design import ShipDesign, Weapon, Bomb, MineLayer
from .ship_role import (
    CAPITAL_SHIP_POWER_RATING, ShipRole, battle_role_of, infer_battle_role)

__all__ = [
    'BOARDER_MULTIPLIER_THRESHOLD',
    'BOARDING_MULTIPLIER_MAXIMUM',
    'base_boarding_strength',
    'Component',
    'ComponentProperty',
    'ComponentLoader',
    'get_component_loader',
    'load_components',
    'Hull',
    'HullModule',
    'Engine',
    'ShipDesign',
    'Weapon',
    'Bomb',
    'MineLayer',
    'CAPITAL_SHIP_POWER_RATING',
    'ShipRole',
    'battle_role_of',
    'infer_battle_role'
]
