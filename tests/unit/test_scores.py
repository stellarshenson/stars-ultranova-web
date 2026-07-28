"""
Tests for the score formula (backend/server/scores.py, port of
ServerState/Scores.cs) and the victory check
(backend/server/victory_check.py, port of ServerState/VictoryCheck.cs).
"""

import pytest

from backend.core.data_structures import EmpireData, Resources, TechLevel
from backend.core.game_objects.fleet import Fleet, ShipToken
from backend.core.game_objects.star import Star
from backend.core.globals import STARTING_YEAR, EVERYONE
from backend.core.race.race import Race
from backend.server.scores import Scores, ScoreRecord
from backend.server.server_data import (
    ServerData, VictorySettings, EnabledValue
)
from backend.server.victory_check import VictoryCheck
from backend.services.ship_specs import SimpleDesign


# --------------------------------------------------------------------------
# Fixture helpers
# --------------------------------------------------------------------------

def make_empire(empire_id: int, race_name: str = "Humanoids") -> EmpireData:
    empire = EmpireData(id=empire_id)
    empire.race = Race(name=race_name)
    empire.race_name = race_name
    return empire


def make_server(*empires: EmpireData) -> ServerData:
    server = ServerData()
    for empire in empires:
        server.all_empires[empire.id] = empire
    return server


def add_star(server: ServerData, name: str, owner: int,
             colonists: int = 0, energy: int = 0) -> Star:
    star = Star(name=name)
    star.owner = owner
    star.colonists = colonists
    star.resources_on_hand = Resources(energy=energy)
    server.all_stars[name] = star
    if owner in server.all_empires:
        server.all_empires[owner].owned_stars[name] = star
    return star


def make_design(empire: EmpireData, name: str, has_weapons: bool = False,
                armor: int = 0) -> SimpleDesign:
    # SimpleDesign.power_rating = weapon power * 10 + armor + shields;
    # with no weapons listed, armor alone sets the rating (armor=100
    # -> escort, armor=5000 -> capital)
    design = SimpleDesign(key=empire.get_next_design_key(), name=name,
                          has_weapons=has_weapons, armor=armor)
    empire.designs[design.key] = design
    return design


def add_fleet(empire: EmpireData, design: SimpleDesign, quantity: int,
              name: str = None) -> Fleet:
    fleet = Fleet()
    fleet.key = empire.get_next_fleet_key()
    fleet.name = name or f"Fleet #{fleet.key}"
    token = ShipToken(design_key=design.key, design_name=design.name,
                      quantity=quantity)
    fleet.tokens[token.design_key] = token
    empire.owned_fleets[fleet.key] = fleet
    return fleet


def score_for(server: ServerData, empire_id: int) -> ScoreRecord:
    for record in Scores(server).get_scores():
        if record.empire_id == empire_id:
            return record
    raise AssertionError(f"no score record for empire {empire_id}")


# --------------------------------------------------------------------------
# Score formula (Scores.cs:62-171)
# --------------------------------------------------------------------------

class TestScoreFormula:

    def test_planets_and_colonist_points_per_star(self):
        # Colonist points use int division PER STAR (Scores.cs:87):
        # 250000//100000 + 90000//100000 = 2 + 0
        empire = make_empire(1)
        server = make_server(empire)
        add_star(server, "A", 1, colonists=250_000)
        add_star(server, "B", 1, colonists=90_000)

        record = score_for(server, 1)
        assert record.planets == 2
        # 2 colonist points + tech bucket (sum 0 < 4 -> +1)
        assert record.score == 3

    def test_starbase_bonus(self):
        empire = make_empire(1)
        server = make_server(empire)
        star = add_star(server, "A", 1)
        design = make_design(empire, "Starbase")
        fleet = add_fleet(empire, design, 1, name="Starbase A")
        star.starbase_key = fleet.key

        record = score_for(server, 1)
        assert record.starbases == 1
        # +3 starbase, +0.5 its unarmed token (counted as a ship, as
        # the C# fleet loop does), +1 tech bucket -> 4.5 truncated
        assert record.unarmed_ships == 1
        assert record.score == 4

    def test_resources_divided_on_the_sum(self):
        # 45 + 50 = 95 -> 95//30 = 3 (per-star division would give 2)
        empire = make_empire(1)
        server = make_server(empire)
        add_star(server, "A", 1, energy=45)
        add_star(server, "B", 1, energy=50)

        record = score_for(server, 1)
        assert record.resources == 95
        assert record.score == 3 + 1  # +1 tech bucket

    def test_ship_classes_counted_per_ship(self):
        # The C# ServerState/Scores.cs:108-127 counts tokens; the web
        # counts per ship (token quantity) like the legacy
        # Common/Scores.cs:92-111 and canonical Stars!. Ship points in
        # the unarmed/escort categories are capped at one scoring ship
        # per owned planet (DEF-8 web mod): here 2 planets cap the 3
        # unarmed scouts to 2 scoring ships; the 2 escorts are at cap
        empire = make_empire(1)
        server = make_server(empire)
        add_star(server, "A", 1)
        add_star(server, "B", 1)

        unarmed = make_design(empire, "Scout", has_weapons=False)
        escort = make_design(empire, "Frigate", has_weapons=True, armor=100)
        capital = make_design(empire, "Battleship", has_weapons=True,
                              armor=5000)
        add_fleet(empire, unarmed, 3)
        add_fleet(empire, escort, 2)
        add_fleet(empire, capital, 2)

        record = score_for(server, 1)
        assert record.unarmed_ships == 3
        assert record.escort_ships == 2
        assert record.capital_ships == 2
        # min(3,2)*0.5 + min(2,2)*2 + capital bonus (8*2*2)//(2+2)=8
        # + tech +1 = 1.0 + 4 + 8 + 1 = 14
        assert record.score == 14

    def test_total_score_truncates(self):
        # One planet, one unarmed ship: 0.5 + colonist 0 + tech
        # bucket 1 = 1.5 -> 1 ((int)totalScore, Scores.cs:168)
        empire = make_empire(1)
        server = make_server(empire)
        add_star(server, "A", 1)
        design = make_design(empire, "Scout")
        add_fleet(empire, design, 1)

        assert score_for(server, 1).score == 1

    def test_escort_points_capped_at_planet_count(self):
        # DEF-8 web mod: escort points awarded for at most one ship
        # per owned planet - 5 escorts on 2 planets score 2*2, not 2*5
        empire = make_empire(1)
        server = make_server(empire)
        add_star(server, "A", 1)
        add_star(server, "B", 1)
        escort = make_design(empire, "Frigate", has_weapons=True, armor=100)
        add_fleet(empire, escort, 5)

        record = score_for(server, 1)
        # Raw report count stays uncapped
        assert record.escort_ships == 5
        # 2 planets * 2 points + tech bucket 1
        assert record.score == 5

    def test_unarmed_points_capped_at_planet_count(self):
        # DEF-8 web mod, unarmed category: 5 scouts on 2 planets
        # score min(5,2)*0.5 = 1.0
        empire = make_empire(1)
        server = make_server(empire)
        add_star(server, "A", 1)
        add_star(server, "B", 1)
        unarmed = make_design(empire, "Scout", has_weapons=False)
        add_fleet(empire, unarmed, 5)

        record = score_for(server, 1)
        assert record.unarmed_ships == 5
        # min(5,2)*0.5 = 1.0 + tech 1 = 2
        assert record.score == 2

    def test_zero_planet_empire_scores_no_ship_points(self):
        # DEF-8 web mod boundary: with no planets, unarmed/escort
        # points are min(N, 0) = 0
        empire = make_empire(1)
        server = make_server(empire)
        unarmed = make_design(empire, "Scout", has_weapons=False)
        escort = make_design(empire, "Frigate", has_weapons=True, armor=100)
        add_fleet(empire, unarmed, 3)
        add_fleet(empire, escort, 4)

        record = score_for(server, 1)
        assert record.unarmed_ships == 3
        assert record.escort_ships == 4
        assert record.score == 1  # tech bucket only

    def test_capital_harmonic_unchanged_by_cap(self):
        # The capital term (Scores.cs:135-139) already saturates at
        # 8*planets and is NOT touched by the DEF-8 cap: 6 capitals on
        # 2 planets -> (8*6*2)//(6+2) = 12, alongside capped escorts
        empire = make_empire(1)
        server = make_server(empire)
        add_star(server, "A", 1)
        add_star(server, "B", 1)
        capital = make_design(empire, "Battleship", has_weapons=True,
                              armor=5000)
        escort = make_design(empire, "Frigate", has_weapons=True, armor=100)
        add_fleet(empire, capital, 6)
        add_fleet(empire, escort, 5)

        record = score_for(server, 1)
        assert record.capital_ships == 6
        # capitals 12 + escorts min(5,2)*2=4 + tech 1 = 17
        assert record.score == 17

    @pytest.mark.parametrize("levels,expected", [
        ((1, 1, 1, 0, 0, 0), 1),   # sum 3 < 4 -> +1
        ((1, 1, 1, 1, 1, 1), 2),   # sum 6 in 4..6 -> +2
        ((2, 2, 2, 1, 1, 1), 3),   # sum 9 in 7..9 -> +3
        ((2, 2, 2, 2, 1, 1), 4),   # sum 10 > 9 -> +4
    ])
    def test_tech_level_buckets(self, levels, expected):
        empire = make_empire(1)
        empire.research_levels = TechLevel.from_values(*levels)
        server = make_server(empire)

        record = score_for(server, 1)
        assert record.tech_level == sum(levels)
        assert record.score == expected

    def test_ranks_sorted_descending(self):
        empires = [make_empire(1), make_empire(2), make_empire(3)]
        server = make_server(*empires)
        # Scores via colonist points: 10 / 30 / 20 (+1 tech each)
        add_star(server, "A", 1, colonists=1_000_000)
        add_star(server, "B", 2, colonists=3_000_000)
        add_star(server, "C", 3, colonists=2_000_000)

        ranks = {r.empire_id: r.rank for r in Scores(server).get_scores()}
        assert ranks == {2: 1, 3: 2, 1: 3}

    def test_rank_tie_keeps_empire_order(self):
        empires = [make_empire(1), make_empire(2)]
        server = make_server(*empires)
        add_star(server, "A", 1, colonists=1_000_000)
        add_star(server, "B", 2, colonists=1_000_000)

        records = Scores(server).get_scores()
        assert [r.empire_id for r in records] == [1, 2]
        assert [r.rank for r in records] == [1, 2]

    def test_mineral_packet_pseudo_fleet_excluded(self):
        empire = make_empire(1)
        server = make_server(empire)
        design = make_design(empire, "Packet")
        add_fleet(empire, design, 5, name="Mineral Packet")

        record = score_for(server, 1)
        assert record.unarmed_ships == 0
        assert record.score == 1  # tech bucket only


# --------------------------------------------------------------------------
# Victory check (VictoryCheck.cs:48-363)
# --------------------------------------------------------------------------

def all_disabled_settings(**overrides) -> VictorySettings:
    """VictorySettings with every target disabled, then overridden."""
    settings = VictorySettings(
        planets_owned=EnabledValue(False, 60),
        tech_levels=EnabledValue(False, 22),
        number_of_fields=EnabledValue(False, 4),
        total_score=EnabledValue(False, 1000),
        second_place_score=EnabledValue(False, 0),
        production_capacity=EnabledValue(False, 1000),
        capital_ships=EnabledValue(False, 100),
        highest_score=EnabledValue(False, 100),
        targets_to_meet=1,
        minimum_game_time=0,
    )
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def run_victory_check(server: ServerData):
    VictoryCheck(server, Scores(server)).victor()


class TestVictoryCheck:

    def test_last_man_standing_ignores_minimum_time(self):
        # VictoryCheck.cs:50-73: sole star owner wins regardless of year
        empire1 = make_empire(1)
        empire2 = make_empire(2)
        server = make_server(empire1, empire2)
        server.victory_settings = all_disabled_settings(minimum_game_time=50)
        add_star(server, "A", 1)
        server.turn_year = STARTING_YEAR  # game_time 0 < 50

        run_victory_check(server)

        assert server.victor == 1
        message = server.all_messages[-1]
        assert message.audience == EVERYONE
        assert message.text == "The Humanoids have won the game"
        assert message.message_type == "Victory"

    def test_minimum_game_time_gates_target_victories(self):
        # VictoryCheck.cs:76-81
        empire1 = make_empire(1)
        empire2 = make_empire(2)
        server = make_server(empire1, empire2)
        server.victory_settings = all_disabled_settings(
            planets_owned=EnabledValue(True, 1), minimum_game_time=50)
        add_star(server, "A", 1)
        add_star(server, "B", 2)

        server.turn_year = STARTING_YEAR + 10
        run_victory_check(server)
        assert server.victor is None

        server.turn_year = STARTING_YEAR + 50
        run_victory_check(server)
        assert server.victor == 1

    def test_occupied_planets_int_division_boundary(self):
        # 3 of 5 stars = 60 >= 60 wins; 2 of 5 = 40 loses
        # (VictoryCheck.cs:134-137)
        for owned, expected_victor in ((3, 1), (2, None)):
            empire1 = make_empire(1)
            empire2 = make_empire(2)
            server = make_server(empire1, empire2)
            server.victory_settings = all_disabled_settings(
                planets_owned=EnabledValue(True, 60))
            for i in range(owned):
                add_star(server, f"A{i}", 1)
            add_star(server, "B0", 2)
            add_star(server, "B1", 2)
            for i in range(5 - owned - 2):
                add_star(server, f"N{i}", 0)

            run_victory_check(server)
            assert server.victor == expected_victor

    def test_attained_tech_level_single_field_default(self):
        # NumberOfFields unchecked -> one field suffices
        # (VictoryCheck.cs:166-169)
        empire1 = make_empire(1)
        empire2 = make_empire(2)
        empire1.research_levels = TechLevel.from_values(energy=10)
        server = make_server(empire1, empire2)
        server.victory_settings = all_disabled_settings(
            tech_levels=EnabledValue(True, 10))
        add_star(server, "A", 1)
        add_star(server, "B", 2)

        run_victory_check(server)
        assert server.victor == 1

    def test_attained_tech_level_number_of_fields(self):
        # With the sub-option on, 4 fields must reach the level
        for fields_at_level, expected_victor in ((3, None), (4, 1)):
            empire1 = make_empire(1)
            empire2 = make_empire(2)
            values = [10] * fields_at_level + [0] * (6 - fields_at_level)
            empire1.research_levels = TechLevel.from_values(*values)
            server = make_server(empire1, empire2)
            server.victory_settings = all_disabled_settings(
                tech_levels=EnabledValue(True, 10),
                number_of_fields=EnabledValue(True, 4))
            add_star(server, "A", 1)
            add_star(server, "B", 2)

            run_victory_check(server)
            assert server.victor == expected_victor

    def test_score_exceeded(self):
        # Empire 1 score: 1_000_000 colonists -> 10 + tech bucket 1 = 11
        for threshold, expected_victor in ((11, 1), (12, None)):
            empire1 = make_empire(1)
            empire2 = make_empire(2)
            server = make_server(empire1, empire2)
            server.victory_settings = all_disabled_settings(
                total_score=EnabledValue(True, threshold))
            add_star(server, "A", 1, colonists=1_000_000)
            add_star(server, "B", 2)

            run_victory_check(server)
            assert server.victor == expected_victor

    def test_production_capacity_int_division_per_star(self):
        # Two stars of 1500 energy each -> 1 + 1 = 2 K, not 3000//1000
        # (VictoryCheck.cs:240)
        for threshold, expected_victor in ((2, 1), (3, None)):
            empire1 = make_empire(1)
            empire2 = make_empire(2)
            server = make_server(empire1, empire2)
            server.victory_settings = all_disabled_settings(
                production_capacity=EnabledValue(True, threshold))
            add_star(server, "A", 1, energy=1500)
            add_star(server, "B", 1, energy=1500)
            add_star(server, "C", 2)

            run_victory_check(server)
            assert server.victor == expected_victor

    def test_capital_ships_target(self):
        for quantity, expected_victor in ((2, 1), (1, None)):
            empire1 = make_empire(1)
            empire2 = make_empire(2)
            server = make_server(empire1, empire2)
            server.victory_settings = all_disabled_settings(
                capital_ships=EnabledValue(True, 2))
            add_star(server, "A", 1)
            add_star(server, "B", 2)
            capital = make_design(empire1, "Battleship", has_weapons=True,
                                  armor=5000)
            add_fleet(empire1, capital, quantity)

            run_victory_check(server)
            assert server.victor == expected_victor

    def test_highest_score_year_threshold_and_top_scorer(self):
        # Returns 0 before its year threshold; only the top scorer
        # wins (the C# own-score lookup defect at VictoryCheck.cs:304-311
        # is ported as the intent - empire 2 must win despite not being
        # first in the list)
        empire1 = make_empire(1)
        empire2 = make_empire(2, race_name="Silicanoids")
        server = make_server(empire1, empire2)
        server.victory_settings = all_disabled_settings(
            highest_score=EnabledValue(True, 10))
        add_star(server, "A", 1)
        add_star(server, "B", 2, colonists=2_000_000)  # top scorer

        server.turn_year = STARTING_YEAR + 5  # years 5 < 10
        run_victory_check(server)
        assert server.victor is None

        server.turn_year = STARTING_YEAR + 10
        run_victory_check(server)
        assert server.victor == 2

    def test_exceeds_second_place_by_percent(self):
        # Canonical percent rule: win when
        # ourScore * 100 > secondPlace * (100 + N); the C# bare
        # multiply (VictoryCheck.cs:356) and CapitalShips gate
        # (VictoryCheck.cs:332) are documented defects.
        # 121 vs 100 at 20% -> 12100 > 12000 wins; 120 -> loses.
        for colonists, expected_victor in ((12_000_000, 1),
                                           (11_900_000, None)):
            empire1 = make_empire(1)
            empire2 = make_empire(2)
            server = make_server(empire1, empire2)
            server.victory_settings = all_disabled_settings(
                second_place_score=EnabledValue(True, 20))
            add_star(server, "A", 1, colonists=colonists)
            add_star(server, "B", 2, colonists=9_900_000)  # score 100

            run_victory_check(server)
            assert server.victor == expected_victor

    def test_targets_to_meet_requires_multiple(self):
        # planets target met, score target not -> 1 of 2 -> no victor;
        # both met -> victor
        for colonists, expected_victor in ((0, None), (400_000, 1)):
            empire1 = make_empire(1)
            empire2 = make_empire(2)
            server = make_server(empire1, empire2)
            server.victory_settings = all_disabled_settings(
                planets_owned=EnabledValue(True, 60),
                total_score=EnabledValue(True, 5),
                targets_to_meet=2)
            add_star(server, "A0", 1, colonists=colonists)
            add_star(server, "A1", 1)
            add_star(server, "A2", 1)
            add_star(server, "B0", 2)
            add_star(server, "B1", 2)

            run_victory_check(server)
            assert server.victor == expected_victor

    def test_victory_announced_once(self):
        # The web replaces C#'s per-instance messageSent flag (and the
        # unguarded last-man-standing branch) with the persisted victor
        empire1 = make_empire(1)
        empire2 = make_empire(2)
        server = make_server(empire1, empire2)
        server.victory_settings = all_disabled_settings()
        add_star(server, "A", 1)

        run_victory_check(server)
        assert server.victor == 1
        message_count = len(server.all_messages)

        run_victory_check(server)
        assert len(server.all_messages) == message_count

    def test_disabled_gates_return_zero(self):
        # A dominating empire does not win while every target is off
        empire1 = make_empire(1)
        empire2 = make_empire(2)
        empire1.research_levels = TechLevel.from_level(26)
        server = make_server(empire1, empire2)
        server.victory_settings = all_disabled_settings()
        for i in range(4):
            add_star(server, f"A{i}", 1, colonists=10_000_000, energy=9000)
        add_star(server, "B", 2)

        run_victory_check(server)
        assert server.victor is None


# --------------------------------------------------------------------------
# Serialization round-trips (restart safety)
# --------------------------------------------------------------------------

class TestSerialization:

    def test_victory_settings_and_victor_round_trip(self):
        server = ServerData()
        server.victory_settings = VictorySettings.from_dict({
            "planets_owned": {"enabled": False, "value": 75},
            "capital_ships": {"enabled": True, "value": 7},
            "targets_to_meet": 3,
            "minimum_game_time": 25,
        })
        server.victor = 2

        restored = ServerData.from_dict(server.to_dict())

        assert restored.victor == 2
        settings = restored.victory_settings
        assert settings.planets_owned == EnabledValue(False, 75)
        assert settings.capital_ships == EnabledValue(True, 7)
        # Untouched targets keep the C# defaults (GameSettings.cs:49-58)
        assert settings.tech_levels == EnabledValue(False, 22)
        assert settings.second_place_score == EnabledValue(False, 0)
        assert settings.targets_to_meet == 3
        assert settings.minimum_game_time == 25

    def test_victory_settings_default_when_absent(self):
        restored = ServerData.from_dict({})
        assert restored.victor is None
        assert restored.victory_settings.planets_owned == EnabledValue(True, 60)
        assert restored.victory_settings.minimum_game_time == 50

    def test_score_history_round_trip(self):
        empire = make_empire(1)
        entry = {**ScoreRecord(empire_id=1, rank=1, score=12).to_dict(),
                 "year": STARTING_YEAR + 1}
        empire.score_history.append(entry)

        restored = EmpireData.from_dict(empire.to_dict())
        assert restored.score_history == [entry]

    def test_clear_resets_victory_state(self):
        server = ServerData()
        server.victor = 1
        server.victory_settings.targets_to_meet = 5
        server.clear()
        assert server.victor is None
        assert server.victory_settings.targets_to_meet == 1
