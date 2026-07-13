"""
Stars Nova Web - Research
Ported from Common/Research.cs

Static research cost calculation, including the per-field race cost
factor from the race designer (50 / 100 / 175 percent).
"""

from typing import Optional, TYPE_CHECKING

from .data_structures.tech_level import ResearchField, TechLevel, RESEARCH_KEYS

if TYPE_CHECKING:
    from .race.race import Race


def fibonacci(n: int) -> int:
    """
    Nth term of the Fibonacci series (F(0)=0, F(1)=1).

    Port of Research.cs:71-78 (naive recursion there; iterative here
    for the same values without exponential runtime).
    """
    if n < 2:
        return n
    a, b = 0, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b


def research_cost(field: ResearchField, race: Optional['Race'],
                  total_levels: TechLevel, level: int) -> int:
    """
    Total (cumulative) energy cost to attain a research level.

    Port of Research.cs:43-62:
    - techAdjustment = 10 points per tech level attained in ALL fields
      (Research.cs:45-50)
    - baseCost = Fibonacci(level + 5) * 10 + techAdjustment
      (Research.cs:58)
    - costFactor = race.ResearchCosts[field], an integer percent set by
      the race designer: 50 (cheap), 100 (standard), 175 (expensive;
      legacy saves may carry 150) (Research.cs:59, Race.cs:44)
    - result = (baseCost * costFactor) / 100 with C# integer division
      (Research.cs:61)

    Args:
        field: Research field being costed.
        race: Owning race (None falls back to standard 100% cost).
        total_levels: Currently attained levels in all fields.
        level: Level whose attainment cost is wanted.

    Returns:
        Cumulative resource threshold for the level.
    """
    tech_adjustment = 0
    for level_attained in total_levels:
        tech_adjustment += level_attained * 10

    base_cost = fibonacci(level + 5) * 10 + tech_adjustment

    cost_factor = 100
    if race is not None:
        cost_factor = race.research_costs.get(RESEARCH_KEYS[field.value], 100)

    return (base_cost * cost_factor) // 100
