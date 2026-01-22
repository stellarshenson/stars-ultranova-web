"""
Stars Nova Web - Bombing Step
Ported from ServerState/TurnSteps/BombingStep.cs (33 lines)

Processes orbital bombardment of enemy planets.
"""

from typing import List, TYPE_CHECKING

from .base import ITurnStep
from ...core.commands.base import Message
from ...core.globals import NOBODY

if TYPE_CHECKING:
    from ..server_data import ServerData


class BombingStep(ITurnStep):
    """
    Bombing turn step.

    Processes orbital bombardment for fleets with bombers that are
    orbiting enemy planets.

    Ported from BombingStep.cs.
    """

    def process(self, server_state: 'ServerData') -> List[Message]:
        """
        Process orbital bombardment.

        Args:
            server_state: Current game state.

        Returns:
            List of messages generated.
        """
        messages: List[Message] = []

        for fleet in server_state.iterate_all_fleets():
            # Check if fleet is in orbit and has bombers
            if fleet.in_orbit is None:
                continue

            if not getattr(fleet, 'has_bombers', False):
                continue

            # Get the star being orbited
            star = server_state.all_stars.get(fleet.in_orbit.name)
            if star is None:
                continue

            # Check if star is enemy-owned
            if star.owner == fleet.owner:
                continue
            if star.owner == NOBODY:
                continue

            # Check if owner considers star owner an enemy
            fleet_empire = server_state.all_empires.get(fleet.owner)
            if fleet_empire is None:
                continue

            # Check enemy status (simplified - actual implementation would check relations)
            is_enemy = self._is_enemy(fleet_empire, star.owner)
            if not is_enemy:
                continue

            # Perform bombing
            bombing_messages = self._bomb(fleet, star, server_state)
            messages.extend(bombing_messages)

        return messages

    def _is_enemy(self, empire, target_owner: int) -> bool:
        """
        Check if empire considers target_owner an enemy.

        Args:
            empire: The empire data.
            target_owner: Owner ID of target.

        Returns:
            True if target is an enemy.
        """
        # Simplified enemy check - actual implementation would use relations
        # For now, any other empire is considered enemy
        return empire.id != target_owner

    def _bomb(self, fleet, star, server_state: 'ServerData') -> List[Message]:
        """
        Perform bombing operation.

        Args:
            fleet: Attacking fleet.
            star: Target star.
            server_state: Game state.

        Returns:
            List of messages from bombing.
        """
        messages: List[Message] = []

        # Calculate bombing damage
        # Simplified implementation - actual would use bomb types, defenses, etc.

        # Count bombers and calculate kill rate
        total_kill_rate = 0
        for token in fleet.tokens.values():
            if token.design is not None:
                # Check if design has bombs
                bomb_count = getattr(token.design, 'bomb_count', 0)
                bomb_kill_rate = getattr(token.design, 'bomb_kill_rate', 0)
                total_kill_rate += bomb_count * bomb_kill_rate * token.quantity

        if total_kill_rate <= 0:
            return messages

        # Calculate casualties (percentage of population)
        # Actual formula from Stars! is more complex, accounting for defenses
        defense_coverage = getattr(star, 'defense_coverage', 0.0)
        effective_kill_rate = total_kill_rate * (1 - defense_coverage)

        # Calculate killed colonists
        killed = int(star.colonists * effective_kill_rate / 100)
        killed = min(killed, star.colonists)

        if killed > 0:
            star.colonists -= killed

            messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} has killed {killed} colonists on {star.name}.",
                message_type="Bombing",
                fleet_key=fleet.key
            ))

            messages.append(Message(
                audience=star.owner,
                text=f"Enemy fleet has killed {killed} of your colonists on {star.name}.",
                message_type="Bombing"
            ))

            # Check if planet is now uninhabited
            if star.colonists <= 0:
                star.colonists = 0
                star.owner = NOBODY

                messages.append(Message(
                    audience=fleet.owner,
                    text=f"{star.name} has been completely depopulated by your bombing.",
                    message_type="Planet Depopulated"
                ))

        return messages
