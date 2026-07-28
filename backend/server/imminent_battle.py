"""
Stars Nova Web - Imminent battle forecast

Which of an empire's fleets are about to fight, computed for the
pre-generation window. Combat resolves inside turn generation with no
player input during the fight, so this window is the last moment a
commander still has: it is what makes an engagement override an
informed choice rather than a guess.

C# absent - Nova never showed the player an approaching battle.

Honest limits, stated rather than hidden:

- an enemy's orders are secret, so nothing here predicts where a
  hostile fleet is going. A hostile counts only where the empire's own
  intel already places it, and only from a report scanned THIS year -
  a stale report is a memory, not evidence of presence
- the fleet's own forecast covers the one leg turn generation will
  actually run (TurnGenerator._update_fleet moves a fleet toward
  waypoint zero once, capped at one year), ignoring fuel exhaustion
  and dust drag. Both only ever shorten the leg, so the forecast can
  warn about an engagement the fleet falls short of - it never misses
  one it reaches
"""

import math
from typing import TYPE_CHECKING, List, Tuple

from ..core.game_objects.fleet import Fleet
from .battle.battle_plan import BattlePlan

if TYPE_CHECKING:
    from .server_data import ServerData
    from ..core.data_structures.empire_data import EmpireData

# Two fleets fight when they share a position. RonBattleEngine groups
# by exact equality and admits stacks within a squared distance of 2
# (ron_battle_engine._generate_stacks), so a forecast one light year
# wide covers every co-location the engine will call a battle
COLOCATION_LY = 1.0


def plan_engages_relation(plan: BattlePlan, relation: str,
                          owner: int) -> bool:
    """
    Whether a battle plan would open fire on an empire.

    Mirrors the engine's own gate (RonBattleEngine._are_enemies) at
    empire level, where the forecast works - it has fleets, not stacks.
    """
    if plan.attack == "Everyone":
        return True
    if plan.target_id == owner:
        return True
    if plan.attack == "Enemies and Neutrals":
        return relation in ("Enemy", "Neutral")
    return relation == "Enemy"


def project_fleet_position(fleet: Fleet) -> Tuple[float, float]:
    """
    Where a fleet will be when this turn's movement is done.

    One leg at warp^2 light years per year, capped at the leg's own
    length - the movement turn generation runs (Fleet.cs:509-577 via
    TurnGenerator._update_fleet, available_time 1.0). Fuel and dust
    are deliberately not modelled; see the module docstring.
    """
    x, y = fleet.position.x, fleet.position.y

    for waypoint in fleet.waypoints:
        dx = waypoint.position_x - x
        dy = waypoint.position_y - y
        distance = math.hypot(dx, dy)
        if distance < 0.01:
            # Waypoint zero is the fleet's own position
            continue
        speed = waypoint.warp_factor * waypoint.warp_factor
        if speed <= 0:
            break
        travelled = min(float(speed), distance)
        return (x + dx / distance * travelled,
                y + dy / distance * travelled)

    return x, y


def _location_name(server_data: 'ServerData', x: float, y: float) -> str:
    """Star name at a point, else the deep-space label battles use."""
    star = server_data.get_star_at_position(x, y)
    if star is not None:
        return star.name
    return f"deep space ({int(x)}, {int(y)})"


def _hostile_reports(empire: 'EmpireData', year: int) -> List[dict]:
    """
    Fleet reports scanned this year that belong to another empire.

    Whether each one is actually hostile depends on the forecasting
    fleet's own plan, so the relation gate stays with the caller.
    """
    reports = []
    for report in empire.fleet_reports.values():
        owner = report.get("owner")
        if owner is None or owner == empire.id:
            continue
        if report.get("year") != year:
            continue
        if not report.get("ship_count", 0):
            continue
        reports.append(report)
    return reports


def forecast_imminent_battles(server_data: 'ServerData',
                              empire_id: int) -> List[dict]:
    """
    The empire's fleets that are about to meet hostile forces.

    One entry per fleet, carrying the forecast battle position, whether
    the fleet is arriving there or already sitting in it, and the
    hostile fleets it will meet. The client renders this as the
    imminent battle warning and offers an engagement override per
    entry.
    """
    empire = server_data.all_empires.get(empire_id)
    if empire is None:
        return []

    year = server_data.turn_year
    relations = {
        other: rep.get("relation", "Enemy")
        for other, rep in empire.empire_reports.items()
    }
    race_names = {
        other: rep.get("race_name", f"Empire {other}")
        for other, rep in empire.empire_reports.items()
    }
    hostiles = _hostile_reports(empire, year)
    if not hostiles:
        return []

    forecasts: List[dict] = []
    for fleet in empire.owned_fleets.values():
        if not fleet.tokens:
            continue
        plan = empire.battle_plans.get(
            fleet.engagement_plan or fleet.battle_plan) or BattlePlan()

        end_x, end_y = project_fleet_position(fleet)
        met = []
        for report in hostiles:
            owner = report["owner"]
            relation = relations.get(owner, "Enemy")
            if not plan_engages_relation(plan, relation, owner):
                continue
            if math.hypot(report.get("position_x", 0.0) - end_x,
                          report.get("position_y", 0.0) - end_y) \
                    > COLOCATION_LY:
                continue
            met.append({
                "key": report.get("key"),
                "name": report.get("name", ""),
                "owner": owner,
                "race_name": race_names.get(owner, f"Empire {owner}"),
                "relation": relation,
                "ship_count": report.get("ship_count", 0),
            })

        if not met:
            continue

        moved = math.hypot(end_x - fleet.position.x,
                           end_y - fleet.position.y) > COLOCATION_LY
        forecasts.append({
            "fleet_key": fleet.key,
            "fleet_name": fleet.name,
            "battle_plan": fleet.battle_plan,
            "engagement_plan": fleet.engagement_plan,
            "position_x": end_x,
            "position_y": end_y,
            "location": _location_name(server_data, end_x, end_y),
            "arriving": moved,
            "hostiles": met,
            "hostile_ships": sum(h["ship_count"] for h in met),
        })

    forecasts.sort(key=lambda f: f["fleet_key"])
    return forecasts
