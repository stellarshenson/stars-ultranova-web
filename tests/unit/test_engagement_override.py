"""
Tests for the imminent battle warning and the engagement override.

Combat resolves inside turn generation with no player input during the
fight, so "change doctrine when battle begins" is implemented as the
last moment the player still has: the pre-generation window. The
warning is what makes the window usable - it names the fleets that are
about to fight - and the override is the one order it accepts, good
for that battle only.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

import pytest

from backend.core.data_structures import NovaPoint
from backend.core.game_objects import Fleet, ShipToken
from backend.core.waypoints.waypoint import Waypoint, NoTaskObj
from backend.server.battle.battle_plan import BattlePlan, seed_admiralty_plans
from backend.server.battle.stack import Stack
from backend.server.imminent_battle import (
    COLOCATION_LY,
    forecast_imminent_battles,
    plan_engages_relation,
    project_fleet_position,
)

from .test_battle_engine import MockEmpire


@dataclass
class ForecastServer:
    """ServerData surface the forecast reads."""
    all_empires: Dict = field(default_factory=dict)
    all_stars: Dict = field(default_factory=dict)
    turn_year: int = 2400

    def get_star_at_position(self, x: float, y: float) -> Optional[object]:
        return self.all_stars.get((x, y))


def _fleet(empire, name, x, y, waypoints=None, plan="Balanced",
           engagement=""):
    fleet = Fleet()
    fleet.key = empire.get_next_fleet_key()
    fleet.owner = empire.id
    fleet.name = name
    fleet.position = NovaPoint(x, y)
    fleet.battle_plan = plan
    fleet.engagement_plan = engagement
    fleet.tokens[1] = ShipToken(design_key=1, quantity=1, armor=50)
    fleet.waypoints = waypoints or [
        Waypoint(position_x=x, position_y=y, warp_factor=0,
                 task=NoTaskObj())
    ]
    empire.owned_fleets[fleet.key] = fleet
    return fleet


def _setup(relation="Enemy", report_year=2400, hostile_at=(100.0, 100.0)):
    server = ForecastServer()
    for i in (1, 2):
        empire = MockEmpire(id=i)
        seed_admiralty_plans(empire.battle_plans)
        empire.battle_plans["Default"] = BattlePlan()
        server.all_empires[i] = empire

    mine = server.all_empires[1]
    mine.empire_reports[2] = {"relation": relation, "race_name": "Ferrets"}
    mine.fleet_reports[99] = {
        "key": 99, "name": "Blockade", "owner": 2,
        "position_x": hostile_at[0], "position_y": hostile_at[1],
        "year": report_year, "ship_count": 3,
    }
    return server, mine


class TestPositionForecast:
    """The forecast covers the one leg turn generation will run."""

    def test_a_parked_fleet_stays_put(self):
        empire = MockEmpire(id=1)
        fleet = _fleet(empire, "Home Guard", 100.0, 100.0)
        assert project_fleet_position(fleet) == (100.0, 100.0)

    def test_a_reachable_leg_arrives(self):
        empire = MockEmpire(id=1)
        fleet = _fleet(empire, "Vanguard", 100.0, 100.0, waypoints=[
            Waypoint(position_x=100, position_y=100, warp_factor=0),
            Waypoint(position_x=110, position_y=100, warp_factor=4),
        ])
        # warp 4 covers 16 ly a year, the leg is 10
        assert project_fleet_position(fleet) == (110.0, 100.0)

    def test_a_long_leg_stops_at_warp_squared(self):
        empire = MockEmpire(id=1)
        fleet = _fleet(empire, "Vanguard", 100.0, 100.0, waypoints=[
            Waypoint(position_x=100, position_y=100, warp_factor=0),
            Waypoint(position_x=200, position_y=100, warp_factor=5),
        ])
        assert project_fleet_position(fleet) == (125.0, 100.0)

    def test_a_zero_warp_order_goes_nowhere(self):
        empire = MockEmpire(id=1)
        fleet = _fleet(empire, "Stranded", 100.0, 100.0, waypoints=[
            Waypoint(position_x=200, position_y=100, warp_factor=0),
        ])
        assert project_fleet_position(fleet) == (100.0, 100.0)


class TestImminentBattleWarning:

    def test_hostiles_already_here_are_reported(self):
        server, mine = _setup()
        fleet = _fleet(mine, "Home Guard", 100.0, 100.0)

        forecast = forecast_imminent_battles(server, 1)
        assert len(forecast) == 1
        entry = forecast[0]
        assert entry["fleet_key"] == fleet.key
        assert entry["fleet_name"] == "Home Guard"
        assert entry["arriving"] is False
        assert entry["hostile_ships"] == 3
        assert entry["hostiles"][0]["race_name"] == "Ferrets"
        assert entry["location"] == "deep space (100, 100)"

    def test_a_fleet_sailing_into_them_is_reported_as_arriving(self):
        server, mine = _setup()
        _fleet(mine, "Vanguard", 90.0, 100.0, waypoints=[
            Waypoint(position_x=90, position_y=100, warp_factor=0),
            Waypoint(position_x=100, position_y=100, warp_factor=4),
        ])

        forecast = forecast_imminent_battles(server, 1)
        assert len(forecast) == 1
        assert forecast[0]["arriving"] is True
        assert forecast[0]["position_x"] == pytest.approx(100.0)

    def test_a_fleet_that_falls_short_is_not_reported(self):
        server, mine = _setup(hostile_at=(200.0, 100.0))
        _fleet(mine, "Vanguard", 100.0, 100.0, waypoints=[
            Waypoint(position_x=100, position_y=100, warp_factor=0),
            Waypoint(position_x=200, position_y=100, warp_factor=4),
        ])
        assert forecast_imminent_battles(server, 1) == []

    def test_stale_intel_is_not_evidence_of_presence(self):
        """A report from an earlier year is a memory, not a sighting."""
        server, mine = _setup(report_year=2399)
        _fleet(mine, "Home Guard", 100.0, 100.0)
        assert forecast_imminent_battles(server, 1) == []

    def test_the_plan_decides_who_counts_as_hostile(self):
        server, mine = _setup(relation="Friend")
        fleet = _fleet(mine, "Home Guard", 100.0, 100.0)
        # The Balanced plan attacks Enemies only
        assert forecast_imminent_battles(server, 1) == []

        mine.battle_plans["Crusade"] = BattlePlan(name="Crusade",
                                                  attack="Everyone")
        fleet.battle_plan = "Crusade"
        assert len(forecast_imminent_battles(server, 1)) == 1

    def test_a_star_names_the_engagement(self):
        server, mine = _setup()

        class FakeStar:
            name = "Kapteyn's Star"
        server.all_stars[(100.0, 100.0)] = FakeStar()
        _fleet(mine, "Home Guard", 100.0, 100.0)

        assert forecast_imminent_battles(server, 1)[0]["location"] == \
            "Kapteyn's Star"

    def test_an_override_in_force_is_shown_with_the_warning(self):
        server, mine = _setup()
        _fleet(mine, "Home Guard", 100.0, 100.0, plan="Balanced",
               engagement="Defensive Hold")

        entry = forecast_imminent_battles(server, 1)[0]
        assert entry["battle_plan"] == "Balanced"
        assert entry["engagement_plan"] == "Defensive Hold"

    def test_the_override_decides_who_counts_as_hostile(self):
        """The forecast reads the plan the fleet will actually fight
        under, not the one it is standing on."""
        server, mine = _setup(relation="Neutral")
        _fleet(mine, "Home Guard", 100.0, 100.0, plan="Balanced",
               engagement="Crusade")
        mine.battle_plans["Crusade"] = BattlePlan(name="Crusade",
                                                  attack="Everyone")
        assert len(forecast_imminent_battles(server, 1)) == 1


class TestRelationGate:

    def test_attack_options(self):
        enemies = BattlePlan(attack="Enemies")
        both = BattlePlan(attack="Enemies and Neutrals")
        everyone = BattlePlan(attack="Everyone")

        assert plan_engages_relation(enemies, "Enemy", 2) is True
        assert plan_engages_relation(enemies, "Neutral", 2) is False
        assert plan_engages_relation(both, "Neutral", 2) is True
        assert plan_engages_relation(both, "Friend", 2) is False
        assert plan_engages_relation(everyone, "Friend", 2) is True

    def test_a_named_target_empire_is_always_engaged(self):
        plan = BattlePlan(attack="Enemies", target_id=2)
        assert plan_engages_relation(plan, "Friend", 2) is True
        assert plan_engages_relation(plan, "Friend", 3) is False


class TestOverrideAppliesToTheBattle:

    def test_the_stack_fights_under_the_override(self):
        fleet = Fleet()
        fleet.key = 1
        fleet.owner = 1
        fleet.battle_plan = "Balanced"
        fleet.engagement_plan = "Defensive Hold"
        token = ShipToken(design_key=1, quantity=1, armor=50)

        stack = Stack.from_fleet(fleet, 0, token)
        assert stack.battle_plan == "Defensive Hold"

    def test_no_override_leaves_the_standing_plan(self):
        fleet = Fleet()
        fleet.key = 1
        fleet.owner = 1
        fleet.battle_plan = "Balanced"
        token = ShipToken(design_key=1, quantity=1, armor=50)

        assert Stack.from_fleet(fleet, 0, token).battle_plan == "Balanced"


class TestSaveCompatibility:

    def test_fleet_without_engagement_plan_loads(self):
        fleet = Fleet()
        fleet.key = 1
        data = fleet.to_dict()
        del data["engagement_plan"]
        assert Fleet.from_dict(data).engagement_plan == ""

    def test_fleet_round_trip_keeps_the_override(self):
        fleet = Fleet()
        fleet.key = 1
        fleet.engagement_plan = "Fighting Retreat"
        assert Fleet.from_dict(fleet.to_dict()).engagement_plan == \
            "Fighting Retreat"


def test_colocation_window_matches_the_engine():
    """The engine admits stacks within a squared distance of 2 of the
    battle location (RonBattleEngine._generate_stacks), so a one light
    year forecast window covers every battle it will call."""
    assert COLOCATION_LY >= 2 ** 0.5 / 2
