"""
Stars Nova Web - Scores
Ported from ServerState/Scores.cs (a legacy pre-rewrite copy exists at
Common/Scores.cs; ServerState/Scores.cs is the authoritative version).

Builds one ScoreRecord per empire from the live server state. Every
division in the formula is C# int division (truncation), preserved
here with //.
"""

from dataclasses import dataclass
from typing import List, TYPE_CHECKING

from ..core.game_objects.fleet import is_mineral_packet

if TYPE_CHECKING:
    from .server_data import ServerData


@dataclass
class ScoreRecord:
    """
    Data needed for the Score report.

    Ported from Common/DataStructures/ScoreRecord.cs:36-45.
    """
    empire_id: int = 0
    rank: int = 0
    score: int = 0
    planets: int = 0
    starbases: int = 0
    unarmed_ships: int = 0
    escort_ships: int = 0
    capital_ships: int = 0
    tech_level: int = 0
    resources: int = 0

    def to_dict(self) -> dict:
        return {
            "empire_id": self.empire_id,
            "rank": self.rank,
            "score": self.score,
            "planets": self.planets,
            "starbases": self.starbases,
            "unarmed_ships": self.unarmed_ships,
            "escort_ships": self.escort_ships,
            "capital_ships": self.capital_ships,
            "tech_level": self.tech_level,
            "resources": self.resources,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ScoreRecord':
        return cls(
            empire_id=data.get("empire_id", 0),
            rank=data.get("rank", 0),
            score=data.get("score", 0),
            planets=data.get("planets", 0),
            starbases=data.get("starbases", 0),
            unarmed_ships=data.get("unarmed_ships", 0),
            escort_ships=data.get("escort_ships", 0),
            capital_ships=data.get("capital_ships", 0),
            tech_level=data.get("tech_level", 0),
            resources=data.get("resources", 0),
        )


class Scores:
    """
    Provides score data for all empires.

    Ported from ServerState/Scores.cs:31-187.
    """

    def __init__(self, server_state: 'ServerData'):
        # Mirror of the C# ctor (Scores.cs:35-38)
        self.server_state = server_state

    def get_scores(self) -> List[ScoreRecord]:
        """Return a list of all scores (Scores.cs:43-55)."""
        scores = [
            self._get_score_record(empire_id)
            for empire_id in self.server_state.all_empires
        ]
        self._set_ranks(scores)
        return scores

    def _get_score_record(self, empire_id: int) -> ScoreRecord:
        """Build a ScoreRecord for a given empire (Scores.cs:62-171)."""
        total_score = 0.0
        score = ScoreRecord(empire_id=empire_id)
        empire = self.server_state.all_empires[empire_id]

        # Star-specific values (Scores.cs:74-89)
        starbases = 0
        resources = 0

        for star in self.server_state.all_stars.values():
            if star.owner != empire_id:
                continue
            score.planets += 1
            resources += int(star.resources_on_hand.energy)

            # Starbase presence: the web resolves star.starbase_key to a
            # fleet on the owner's roster (the C# Star carries a direct
            # Starbase reference, Scores.cs:81)
            starbase_key = getattr(star, 'starbase_key', None)
            if starbase_key and starbase_key in empire.owned_fleets:
                starbases += 1
                total_score += 3

            # Int division applied PER STAR (Scores.cs:87)
            total_score += star.colonists // 100000

        score.starbases = starbases
        score.resources = resources
        # Int division on the summed total (Scores.cs:93)
        total_score += resources // 30

        # Ship-specific values (Scores.cs:104-133). The C# loop counts
        # TOKENS, ignoring token.Quantity - but the legacy
        # Common/Scores.cs:92-111 counted per Ship, and canonical
        # Stars! counts ships, so the web counts PER SHIP (multiply by
        # token.quantity). The C# loop iterates all fleets including
        # starbases (their tokens live in Composition too), so starbase
        # tokens are counted as ships here as well; the +3 starbase
        # term above is separate.
        unarmed_ships = 0
        escort_ships = 0
        capital_ships = 0

        for fleet in empire.owned_fleets.values():
            # Mineral-packet pseudo-fleets are a web-only construct
            # (no C# equivalent) - exclude them from ship counts
            if is_mineral_packet(fleet):
                continue
            for token in fleet.tokens.values():
                design = empire.designs.get(token.design_key)
                if design is None:
                    continue
                if not design.has_weapons:
                    unarmed_ships += token.quantity
                    total_score += 0.5 * token.quantity
                elif design.power_rating < 2000:
                    # C# ShipDesign.PowerRating is a stub returning 0
                    # (Common/Components/ShipDesign.cs:141-150), so the
                    # C# build could never count capital ships. The web
                    # uses its real power_rating port (ship_design.py
                    # power_rating; SimpleDesign.power_rating in
                    # ship_specs.py), the same 2000 threshold the Ron
                    # battle engine applies.
                    escort_ships += token.quantity
                    total_score += 2 * token.quantity
                else:
                    capital_ships += token.quantity

        score.unarmed_ships = unarmed_ships
        score.escort_ships = escort_ships
        score.capital_ships = capital_ships

        if capital_ships != 0:
            # All-int expression with int division (Scores.cs:135-139)
            stars = score.planets
            total_score += (8 * capital_ships * stars) // (capital_ships + stars)

        # Tech level (Scores.cs:145-166). C# reads
        # serverState.AllTechLevels - "Sum of a player's techlevels,
        # for scoring purposes" (ServerData.cs:49) - which nothing in
        # the reference ever writes; the web computes the sum of the 6
        # research fields directly.
        tech_level = sum(empire.research_levels)
        score.tech_level = tech_level
        if tech_level < 4:
            total_score += 1
        if tech_level > 9:
            total_score += 4
        if 3 < tech_level < 7:
            total_score += 2
        if 6 < tech_level < 10:
            total_score += 3

        # Truncate (C# (int) cast, Scores.cs:168)
        score.score = int(total_score)

        return score

    def _set_ranks(self, scores: List[ScoreRecord]):
        """
        Set the rank for all empires (Scores.cs:176-186).

        Sort descending by score (ScoreRecord.CompareTo,
        ScoreRecord.cs:58-62), rank = 1-based position. Ties: .NET
        List.Sort is unstable; Python's stable sort keeps empire
        insertion order, which is acceptable.
        """
        scores.sort(key=lambda record: -record.score)
        for i, record in enumerate(scores):
            record.rank = i + 1
