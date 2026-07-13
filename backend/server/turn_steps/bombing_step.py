"""
Stars Nova Web - Bombing Step
Ported from ServerState/TurnSteps/BombingStep.cs + ServerState/Bombing.cs
+ Common/Defenses.cs

Processes orbital bombardment of enemy planets.
"""

from typing import List, Optional, TYPE_CHECKING

from .base import ITurnStep
from ...core.commands.base import Message
from ...core.globals import NOBODY

if TYPE_CHECKING:
    from ..server_data import ServerData


# Base defense coverage per installed defense unit, by defense type.
# Ported from Defenses.cs ComputeDefenseCoverage (lines 46-85).
DEFENSE_BASE_COVERAGE = {
    "SDI": 0.0099,
    "Missile Battery": 0.0199,
    "Laser Battery": 0.0239,
    "Planetary Shield": 0.0299,
    "Neutron Shield": 0.0379,
    "None": 0.0,
}


def compute_defense_coverage(star) -> dict:
    """
    Compute a star's defense coverage factors.

    Ported from Defenses.cs:
        PopulationCoverage = 1 - (1 - base)^defenses
        BuildingCoverage   = PopulationCoverage * 0.5
        SmartBombCoverage  uses half the base level
    """
    defenses = min(100, getattr(star, 'defenses', 0))
    defense_type = getattr(star, 'defense_type', "SDI")
    base = DEFENSE_BASE_COVERAGE.get(defense_type, 0.0099)

    if defenses <= 0 or base <= 0:
        return {"population": 0.0, "buildings": 0.0, "smart": 0.0}

    population = 1.0 - (1.0 - base) ** defenses
    smart = 1.0 - (1.0 - base * 0.5) ** defenses
    return {
        "population": population,
        "buildings": population * 0.5,
        "smart": smart,
    }


class BombingStep(ITurnStep):
    """
    Bombing turn step.

    Fleets with bombers orbiting an enemy planet bomb it: population
    killed by bomb PopKill percent (reduced by defense coverage, with
    a defense-reduced minimum kill), installations destroyed evenly
    across mines/factories/defenses.

    Ported from Bombing.cs Bomb() (lines 48-156). The original's
    smart-bomb path was dead code (Fleet.BombCapability only summed
    conventional bombs); here smart bombs are wired as the code
    intended, using SmartBombCoverage.
    """

    def process(self, server_state: 'ServerData') -> List[Message]:
        messages: List[Message] = []

        for fleet in server_state.iterate_all_fleets():
            if fleet.in_orbit is None:
                continue
            if not getattr(fleet, 'has_bombers', False):
                continue

            star = server_state.all_stars.get(fleet.in_orbit.name)
            if star is None:
                continue

            # Preconditions from Bombing.cs: an occupied enemy planet
            # without a protecting starbase
            if star.owner == fleet.owner or star.owner == NOBODY:
                continue
            if star.colonists <= 0:
                continue
            if self._has_starbase(star, server_state):
                continue

            fleet_empire = server_state.all_empires.get(fleet.owner)
            if fleet_empire is None:
                continue
            if not self._is_enemy(fleet_empire, star.owner):
                continue

            messages.extend(self._bomb(fleet, star, server_state))

        return messages

    def _has_starbase(self, star, server_state: 'ServerData') -> bool:
        """A starbase protects the planet from bombing (Bombing.cs)."""
        owner_empire = server_state.all_empires.get(star.owner)
        if owner_empire is None:
            return False
        for fleet in owner_empire.owned_fleets.values():
            if (getattr(fleet, 'is_starbase', False)
                    and fleet.in_orbit_name == star.name):
                return True
        return False

    def _is_enemy(self, empire, target_owner: int) -> bool:
        """All other empires are enemies (relations default to Enemy)."""
        return empire.id != target_owner

    def _fleet_bombs(self, fleet, server_state: 'ServerData'):
        """
        Aggregate the fleet's bomb capability from its designs.

        Returns (conventional, smart) tuples of
        (pop_kill, installations, minimum_kill) scaled by ship counts.
        """
        empire = server_state.all_empires.get(fleet.owner)
        designs = empire.designs if empire else {}

        conv = [0.0, 0, 0]   # pop_kill %, installations, minimum_kill
        smart = [0.0, 0, 0]
        for token in fleet.tokens.values():
            design = designs.get(token.design_key)
            if design is None:
                continue
            c = getattr(design, 'conventional_bombs', None)
            if c is not None and (c.pop_kill > 0 or c.installations > 0):
                conv[0] += c.pop_kill * token.quantity
                conv[1] += c.installations * token.quantity
                conv[2] = max(conv[2], c.minimum_kill)
            s = getattr(design, 'smart_bombs', None)
            if s is not None and s.pop_kill > 0:
                smart[0] += s.pop_kill * token.quantity
        return conv, smart

    def _bomb(self, fleet, star, server_state: 'ServerData') -> List[Message]:
        """Perform bombing. Ported from Bombing.cs Bomb()."""
        messages: List[Message] = []
        coverage = compute_defense_coverage(star)
        conv, smart = self._fleet_bombs(fleet, server_state)

        dead = 0
        # Conventional bombs: kill % reduced by population coverage,
        # with a defense-reduced minimum kill
        if conv[0] > 0 or conv[2] > 0:
            kill_factor = conv[0] / 100.0
            population_kill = kill_factor * (1.0 - coverage["population"])
            killed = star.colonists * population_kill
            min_killed = conv[2] * (1.0 - coverage["population"])
            dead += int(max(killed, min_killed))

        # Smart bombs: penetrate defenses better, no minimum kill
        if smart[0] > 0:
            kill_factor = smart[0] / 100.0
            dead += int(star.colonists * kill_factor
                        * (1.0 - coverage["smart"]))

        dead = min(dead, star.colonists)
        if dead <= 0 and conv[1] <= 0:
            return messages

        star.colonists -= dead

        # Installations: same damage percent applied to defenses,
        # factories, and mines (Bombing.cs lines 100-121)
        defenses_destroyed = factories_destroyed = mines_destroyed = 0
        total_buildings = (getattr(star, 'mines', 0)
                           + getattr(star, 'factories', 0)
                           + getattr(star, 'defenses', 0))
        if conv[1] > 0 and total_buildings > 0:
            building_kills = conv[1] * (1.0 - coverage["buildings"])
            damage_percent = min(1.0, building_kills / total_buildings)
            defenses_destroyed = int(star.defenses * damage_percent)
            factories_destroyed = int(star.factories * damage_percent)
            mines_destroyed = int(star.mines * damage_percent)
            star.defenses -= defenses_destroyed
            star.factories -= factories_destroyed
            star.mines -= mines_destroyed

        summary = (f"killed {dead:,} colonists and destroyed "
                   f"{defenses_destroyed} defenses, "
                   f"{factories_destroyed} factories and "
                   f"{mines_destroyed} mines on {star.name}")

        if star.colonists <= 0:
            # Complete depopulation: the planet reverts to unowned
            star.colonists = 0
            star.mines = 0
            star.factories = 0
            defender = star.owner
            star.owner = NOBODY
            if getattr(star, 'manufacturing_queue', None) is not None:
                try:
                    star.manufacturing_queue.orders.clear()
                except AttributeError:
                    pass
            messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} has bombed {star.name}, "
                     f"killing all of the colonists.",
                message_type="Bombing", fleet_key=fleet.key))
            messages.append(Message(
                audience=defender,
                text=f"Enemy bombers have wiped out our colony "
                     f"on {star.name}!",
                message_type="Bombing"))
        else:
            # Identical text to wolf and lamb, as in the original
            messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} has {summary}.",
                message_type="Bombing", fleet_key=fleet.key))
            messages.append(Message(
                audience=star.owner,
                text=f"Enemy fleet {fleet.name} has {summary}.",
                message_type="Bombing"))

        return messages
