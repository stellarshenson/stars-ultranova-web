"""
Stars Nova Web - Bombing Step
Ported from ServerState/TurnSteps/BombingStep.cs + ServerState/Bombing.cs
+ Common/Defenses.cs

Processes orbital bombardment of enemy planets.
"""

from typing import List, Optional, TYPE_CHECKING

from .base import ITurnStep
from ...core.commands.base import Message
# Coverage math lives in core.defenses (shared with invasion and the
# API); re-exported here for existing importers
from ...core.defenses import DEFENSE_BASE_COVERAGE, compute_defense_coverage
from ...core.globals import NOBODY

if TYPE_CHECKING:
    from ..server_data import ServerData


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
        """Only Enemy-relation planets are bombed (Bombing.cs:61 via
        EmpireData.cs IsEnemy, lines 173-176). Unknown empires default
        to Enemy (PlayerRelation enum member 0, EmpireData.cs:34-39)."""
        return empire.empire_reports.get(
            target_owner, {}).get("relation", "Enemy") == "Enemy"

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

    def _fleet_retro_points(self, fleet, server_state: 'ServerData') -> int:
        """
        Retro Bomb points: the fleet's summed negative Orbital Adjuster
        value (Retro Bomb carries "Orbital Adjuster" Value -1,
        components.xml; SimpleDesign lacks the attribute - default 0).
        """
        empire = server_state.all_empires.get(fleet.owner)
        designs = empire.designs if empire else {}

        points = 0
        for token in fleet.tokens.values():
            design = designs.get(token.design_key)
            if design is None:
                continue
            adjuster = getattr(design, 'orbital_adjuster', 0)
            if adjuster < 0:
                points += -adjuster * token.quantity
        return points

    def _bomb(self, fleet, star, server_state: 'ServerData') -> List[Message]:
        """Perform bombing. Ported from Bombing.cs Bomb()."""
        messages: List[Message] = []
        coverage = compute_defense_coverage(star)
        conv, smart = self._fleet_bombs(fleet, server_state)
        retro_points = self._fleet_retro_points(fleet, server_state)
        defender = star.owner

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
        if dead <= 0 and conv[1] <= 0 and retro_points <= 0:
            return messages

        if dead > 0 or conv[1] > 0:
            messages.extend(
                self._apply_kill_bombing(fleet, star, coverage, conv, dead))

        # Retro Bombs (canonical - C# has no implementation): each
        # point moves the environment variable with the largest
        # |current - original| 1 click back toward its original value;
        # no population or installation damage, and defenses do not
        # reduce it (it is not a kill weapon)
        if retro_points > 0:
            from ...services.terraforming import retro_terraform_one_point
            moved = 0
            for _ in range(retro_points):
                if retro_terraform_one_point(star) is None:
                    break
                moved += 1
            if moved > 0:
                messages.append(Message(
                    audience=fleet.owner,
                    text=f"{fleet.name} has un-terraformed {star.name} "
                         f"back toward its original environment.",
                    message_type="Bombing", fleet_key=fleet.key))
                messages.append(Message(
                    audience=defender,
                    text=f"Enemy fleet {fleet.name} has un-terraformed "
                         f"{star.name} back toward its original "
                         f"environment.",
                    message_type="Bombing"))

        return messages

    def _apply_kill_bombing(self, fleet, star, coverage, conv,
                            dead: int) -> List[Message]:
        """Apply population/installation losses and report them."""
        messages: List[Message] = []
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
