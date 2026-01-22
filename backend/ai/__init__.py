"""
Stars Nova Web - AI Module
Ported from Nova/Ai/*.cs

Computer opponent implementation with planet and fleet management.
"""

from .abstract_ai import AbstractAI
from .default_ai import DefaultAI
from .default_ai_planner import DefaultAIPlanner
from .default_planet_ai import DefaultPlanetAI
from .default_fleet_ai import DefaultFleetAI

__all__ = [
    "AbstractAI",
    "DefaultAI",
    "DefaultAIPlanner",
    "DefaultPlanetAI",
    "DefaultFleetAI"
]
