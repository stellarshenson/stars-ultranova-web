"""
Stars Nova Web - Victory Check
Ported from ServerState/VictoryCheck.cs (366 lines)

Check for a victor (doesn't mean the end of a game, though). Invoked
after the battle engine and fleet cleanup, before the turn year
increment (TurnGenerator.cs:131-133).
"""

from typing import TYPE_CHECKING

from ..core.commands.base import Message
from ..core.globals import STARTING_YEAR, NOBODY, EVERYONE

if TYPE_CHECKING:
    from .server_data import ServerData
    from .scores import Scores
    from ..core.data_structures import EmpireData


class VictoryCheck:
    """
    Check for a victor.

    Ported from VictoryCheck.cs:33-108. Announce-once: the C# instance
    keeps a per-instance messageSent flag (and its last-man-standing
    branch has no guard at all, re-announcing every turn); the web
    builds a fresh TurnGenerator each turn, so it uses the persisted
    server_state.victor flag instead - the victory is declared exactly
    once and survives restarts (deviation from C#, same intent).
    """

    def __init__(self, server_state: 'ServerData', scores: 'Scores'):
        self.server_state = server_state
        self.scores = scores

    def victor(self):
        """Check for victor (VictoryCheck.cs:48-108)."""
        if self.server_state.victor is not None:
            return

        settings = self.server_state.victory_settings

        # Last man standing - doesn't matter the year
        # (VictoryCheck.cs:50-73)
        remaining_empires = []
        for star in self.server_state.all_stars.values():
            if star.owner == NOBODY:
                continue
            if star.owner not in remaining_empires:
                remaining_empires.append(star.owner)

        if len(remaining_empires) == 1:
            empire = self.server_state.all_empires[remaining_empires[0]]
            self._declare_winner(empire)
            return

        game_time = self.server_state.turn_year - STARTING_YEAR
        if game_time < settings.minimum_game_time:
            return

        for empire in self.server_state.all_empires.values():
            targets_met = 0
            targets_met += self._occupied_planets(empire.id)
            targets_met += self._attained_tech_level(empire.id)
            targets_met += self._score_exceeded(empire.id)
            targets_met += self._production_capacity(empire.id)
            targets_met += self._capital_ships(empire.id)
            targets_met += self._highest_score(empire.id, game_time)
            targets_met += self._exceeds_second_place(empire.id)

            if targets_met >= settings.targets_to_meet:
                # First empire in iteration order wins ties
                # (VictoryCheck.cs:95-104)
                self._declare_winner(empire)
                return

    def status(self, empire_id: int) -> dict:
        """
        Progress toward each victory target for one empire.

        Web extension feeding the client's victory-conditions status
        dialog; the C# reference only ever reports the winner. Progress
        values reuse the exact check arithmetic (int divisions) above.
        """
        settings = self.server_state.victory_settings
        game_time = self.server_state.turn_year - STARTING_YEAR

        own_score = 0
        own_capitals = 0
        second_place = 0
        top_score = 0
        for record in self.scores.get_scores():
            top_score = max(top_score, record.score)
            if record.empire_id == empire_id:
                own_score = record.score
                own_capitals = record.capital_ships
            if record.rank == 2:
                second_place = record.score

        empire = self.server_state.all_empires[empire_id]
        total_stars = len(self.server_state.all_stars)
        stars_owned = 0
        capacity = 0
        for star in self.server_state.all_stars.values():
            if star.owner == empire_id:
                stars_owned += 1
                capacity += int(star.resources_on_hand.energy) // 1000
        planet_pct = ((stars_owned * 100) // total_stars) if total_stars else 0
        fields_at_level = sum(
            1 for level in empire.research_levels
            if level >= settings.tech_levels.value)
        fields_needed = (settings.number_of_fields.value
                         if settings.number_of_fields.enabled else 1)

        def target(ev, progress, met, **extra):
            return {"enabled": ev.enabled, "value": ev.value,
                    "progress": progress, "met": bool(met), **extra}

        return {
            "game_time": game_time,
            "minimum_game_time": settings.minimum_game_time,
            "targets_to_meet": settings.targets_to_meet,
            "targets": {
                "planets_owned": target(
                    settings.planets_owned, planet_pct,
                    self._occupied_planets(empire_id)),
                "tech_levels": target(
                    settings.tech_levels, fields_at_level,
                    self._attained_tech_level(empire_id),
                    fields_needed=fields_needed),
                "total_score": target(
                    settings.total_score, own_score,
                    self._score_exceeded(empire_id)),
                "second_place_score": target(
                    settings.second_place_score, own_score,
                    self._exceeds_second_place(empire_id),
                    second_place=second_place),
                "production_capacity": target(
                    settings.production_capacity, capacity,
                    self._production_capacity(empire_id)),
                "capital_ships": target(
                    settings.capital_ships, own_capitals,
                    self._capital_ships(empire_id)),
                "highest_score": target(
                    settings.highest_score, own_score,
                    self._highest_score(empire_id, game_time),
                    top_score=top_score),
            },
        }

    def _declare_winner(self, empire: 'EmpireData'):
        """Set the victor and announce to everyone (VictoryCheck.cs:66-72,
        :98-104)."""
        self.server_state.victor = empire.id
        # C# text uses Race.PluralName (VictoryCheck.cs:69/:101);
        # plural_name is a dynamic attribute in the web (not persisted
        # by Race.to_dict), so fall back to the race name
        race = empire.race
        plural = (getattr(race, 'plural_name', None)
                  or (race.name if race else f"Empire {empire.id}"))
        self.server_state.all_messages.append(Message(
            audience=EVERYONE,
            text=f"The {plural} have won the game",
            message_type="Victory"
        ))

    def _occupied_planets(self, empire_id: int) -> int:
        """Owns the required percentage of ALL planets
        (VictoryCheck.cs:115-143)."""
        settings = self.server_state.victory_settings
        if not settings.planets_owned.enabled:
            return 0

        stars_owned = 0
        for star in self.server_state.all_stars.values():
            if star.owner == empire_id:
                stars_owned += 1

        # Int division (VictoryCheck.cs:134-135)
        percentage = (stars_owned * 100) // len(self.server_state.all_stars)

        if percentage >= settings.planets_owned.value:
            return 1
        return 0

    def _attained_tech_level(self, empire_id: int) -> int:
        """Attained the required tech level in the required number of
        fields (VictoryCheck.cs:151-188)."""
        settings = self.server_state.victory_settings
        if not settings.tech_levels.enabled:
            return 0

        target_level = settings.tech_levels.value
        # NumberOfFields is a sub-option; unchecked means one field
        # suffices (VictoryCheck.cs:166-169)
        number_of_fields = (settings.number_of_fields.value
                            if settings.number_of_fields.enabled else 1)

        highest_fields = 0
        for level in self.server_state.all_empires[empire_id].research_levels:
            if level >= target_level:
                highest_fields += 1

        if highest_fields >= number_of_fields:
            return 1
        return 0

    def _score_exceeded(self, empire_id: int) -> int:
        """Exceeded the required score (VictoryCheck.cs:195-217)."""
        settings = self.server_state.victory_settings
        if not settings.total_score.enabled:
            return 0

        for score_detail in self.scores.get_scores():
            if score_detail.empire_id == empire_id:
                if score_detail.score >= settings.total_score.value:
                    return 1
                break
        return 0

    def _production_capacity(self, empire_id: int) -> int:
        """Exceeded the required production capacity in K resources
        (VictoryCheck.cs:227-250)."""
        settings = self.server_state.victory_settings
        if not settings.production_capacity.enabled:
            return 0

        capacity = 0
        for star in self.server_state.all_stars.values():
            if star.owner == empire_id:
                # Int division applied PER STAR (VictoryCheck.cs:240)
                capacity += int(star.resources_on_hand.energy) // 1000

        if capacity >= settings.production_capacity.value:
            return 1
        return 0

    def _capital_ships(self, empire_id: int) -> int:
        """Met the required number of capital ships
        (VictoryCheck.cs:257-280)."""
        settings = self.server_state.victory_settings
        if not settings.capital_ships.enabled:
            return 0

        for score_detail in self.scores.get_scores():
            if score_detail.empire_id == empire_id:
                if score_detail.capital_ships >= settings.capital_ships.value:
                    return 1
                break
        return 0

    def _highest_score(self, empire_id: int, years: int) -> int:
        """Has the highest score after the specified number of years
        (VictoryCheck.cs:289-322)."""
        settings = self.server_state.victory_settings
        if not settings.highest_score.enabled:
            return 0

        if years < settings.highest_score.value:
            return 0

        all_scores = self.scores.get_scores()

        # C# DEFECT (VictoryCheck.cs:304-311): the own-score lookup
        # loop has an unconditional break, so raceScore stays 0 unless
        # the empire happens to be first in the list. Ported as the
        # intent: find the empire's own record.
        race_score = 0
        for score_detail in all_scores:
            if score_detail.empire_id == empire_id:
                race_score = score_detail.score
                break

        for score_detail in all_scores:
            if score_detail.score > race_score:
                return 0
        return 1

    def _exceeds_second_place(self, empire_id: int) -> int:
        """Exceeds the second-place score by the specified percentage
        (VictoryCheck.cs:330-363)."""
        settings = self.server_state.victory_settings
        # C# DEFECT (VictoryCheck.cs:332): gates on
        # CapitalShips.IsChecked instead of SecondPlaceScore.IsChecked.
        # Ported with the SecondPlaceScore gate.
        if not settings.second_place_score.enabled:
            return 0

        # C# uses an else-if here (VictoryCheck.cs:344-354), which
        # leaves secondPlaceScore at 0 when the checked empire is
        # itself the rank-2 record - under the corrected gate that
        # would let any runner-up with a nonzero score win instantly.
        # The rank-2 record is therefore found unconditionally: the
        # second-highest score overall is the canonical reference.
        our_score = 0
        second_place_score = 0
        for score_detail in self.scores.get_scores():
            if score_detail.empire_id == empire_id:
                our_score = score_detail.score
            if score_detail.rank == 2:
                second_place_score = score_detail.score

        # C# multiplies bare (secondPlaceScore *= NumericValue,
        # VictoryCheck.cs:356), which is degenerate with the (false, 0)
        # default. Canonical Stars! semantics is "exceeds the
        # second-place score by N%": win when
        # ourScore * 100 > secondPlace * (100 + N). With value 0 this
        # reduces to "strictly above second place".
        if (our_score * 100
                > second_place_score * (100 + settings.second_place_score.value)):
            return 1
        return 0
