"""
Stars Nova Web - Post Bombing Step (Colonization)
Ported from ServerState/TurnSteps/PostBombingStep.cs (118 lines)

Processes colonization tasks after bombing step.
Colonization is performed after bombing so players can bomb then colonize
in the same turn.
"""

from typing import List, TYPE_CHECKING

from .base import ITurnStep
from ...core.commands.base import Message
from ...core.waypoints.waypoint import WaypointTask, get_task_type
from ...core.globals import NOBODY

if TYPE_CHECKING:
    from ..server_data import ServerData


class PostBombingStep(ITurnStep):
    """
    Post-bombing colonization turn step.

    Colonise tasks are performed after bombing steps. In Stars! it was
    necessary to perform multiple SplitMerge steps to ensure the ID of
    the colonizer was higher than the bomber fleet ID.

    Ported from PostBombingStep.cs.
    """

    def process(self, server_state: 'ServerData') -> List[Message]:
        """
        Process colonization tasks.

        Args:
            server_state: Current game state.

        Returns:
            List of messages generated.
        """
        messages: List[Message] = []

        for fleet in server_state.iterate_all_fleets():
            # Skip starbases
            if getattr(fleet, 'is_starbase', False):
                continue

            if len(fleet.waypoints) == 0:
                continue

            dest_zero = fleet.waypoints[0].destination
            index = 0
            max_index = len(fleet.waypoints) - 1

            while index <= max_index:
                if index >= len(fleet.waypoints):
                    break

                waypoint = fleet.waypoints[index]

                # Only process waypoints at current location
                if waypoint.destination != dest_zero:
                    index += 1
                    continue

                # Check for colonize or invade task
                task_type = get_task_type(waypoint.task)
                if task_type not in (WaypointTask.COLONIZE, WaypointTask.INVADE):
                    index += 1
                    continue

                # Find target star
                target = None
                for star in server_state.all_stars.values():
                    if star.name == dest_zero:
                        target = star
                        break

                if target is None:
                    index += 1
                    continue

                sender = server_state.all_empires.get(fleet.owner)
                if sender is None:
                    index += 1
                    continue

                receiver = None
                if target.owner != NOBODY:
                    receiver = server_state.all_empires.get(target.owner)

                # Handle colonization
                if task_type == WaypointTask.COLONIZE:
                    if receiver is not None and receiver.id != fleet.owner:
                        # Planet is occupied - convert to invasion
                        invade_messages = self._perform_invasion(
                            fleet, target, sender, receiver, server_state
                        )
                        messages.extend(invade_messages)
                    else:
                        # Perform colonization
                        colonize_messages = self._perform_colonization(
                            fleet, target, sender, server_state
                        )
                        messages.extend(colonize_messages)

                    # Remove the waypoint
                    if index < len(fleet.waypoints):
                        fleet.waypoints.pop(index)
                        max_index -= 1
                    continue

                elif task_type == WaypointTask.INVADE:
                    invade_messages = self._perform_invasion(
                        fleet, target, sender, receiver, server_state
                    )
                    messages.extend(invade_messages)

                    if index < len(fleet.waypoints):
                        fleet.waypoints.pop(index)
                        max_index -= 1
                    continue

                index += 1

        # Cleanup empty fleets
        server_state.cleanup_fleets()

        return messages

    def _perform_colonization(self, fleet, star, sender, server_state) -> List[Message]:
        """
        Perform colonization of an uninhabited planet.

        Args:
            fleet: Colonizing fleet.
            star: Target star.
            sender: Sending empire.
            server_state: Game state.

        Returns:
            List of messages.
        """
        messages: List[Message] = []

        # Check if fleet can colonize
        if not getattr(fleet, 'can_colonize', False):
            messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} cannot colonize - no colonization module.",
                message_type="Colonization Failed",
                fleet_key=fleet.key
            ))
            return messages

        # Check if there are colonists to drop
        colonists_to_drop = fleet.cargo.colonists if hasattr(fleet.cargo, 'colonists') else 0

        if colonists_to_drop <= 0:
            messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} cannot colonize - no colonists aboard.",
                message_type="Colonization Failed",
                fleet_key=fleet.key
            ))
            return messages

        # Perform colonization
        star.owner = fleet.owner
        star.colonists = colonists_to_drop
        fleet.cargo.colonists = 0

        # Transfer cargo to planet
        if hasattr(fleet.cargo, 'ironium'):
            star.resource_stockpile.ironium += fleet.cargo.ironium
            fleet.cargo.ironium = 0
        if hasattr(fleet.cargo, 'boranium'):
            star.resource_stockpile.boranium += fleet.cargo.boranium
            fleet.cargo.boranium = 0
        if hasattr(fleet.cargo, 'germanium'):
            star.resource_stockpile.germanium += fleet.cargo.germanium
            fleet.cargo.germanium = 0

        # Add star to sender's owned stars
        sender.owned_stars[star.name] = star

        messages.append(Message(
            audience=fleet.owner,
            text=f"{star.name} has been colonized with {colonists_to_drop} colonists.",
            message_type="Colonization",
            fleet_key=fleet.key
        ))

        # Scrap the colonizer module ship (typically)
        # In actual Stars!, the colony ship is consumed
        # For now, we just remove colonists - ship handling varies

        return messages

    def _perform_invasion(self, fleet, star, sender, receiver, server_state) -> List[Message]:
        """
        Perform invasion of an inhabited planet.

        Args:
            fleet: Invading fleet.
            star: Target star.
            sender: Attacking empire.
            receiver: Defending empire (may be None).
            server_state: Game state.

        Returns:
            List of messages.
        """
        messages: List[Message] = []

        # Check if there are colonists to drop
        invaders = fleet.cargo.colonists if hasattr(fleet.cargo, 'colonists') else 0

        if invaders <= 0:
            messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} cannot invade - no colonists aboard.",
                message_type="Invasion Failed",
                fleet_key=fleet.key
            ))
            return messages

        defenders = star.colonists

        # Simple invasion calculation
        # Actual Stars! formula is more complex with ground combat mechanics
        # Invaders have advantage, typically 1.1:1 kill ratio

        invader_strength = invaders * 1.1  # Invaders have slight advantage
        defender_strength = defenders

        if invader_strength > defender_strength:
            # Invasion successful
            casualties_ratio = defender_strength / invader_strength
            surviving_invaders = int(invaders * (1 - casualties_ratio * 0.9))
            surviving_invaders = max(surviving_invaders, 1)

            star.colonists = surviving_invaders
            old_owner = star.owner
            star.owner = fleet.owner
            fleet.cargo.colonists = 0

            # Update ownership
            if receiver is not None and star.name in receiver.owned_stars:
                del receiver.owned_stars[star.name]
            sender.owned_stars[star.name] = star

            messages.append(Message(
                audience=fleet.owner,
                text=f"Invasion of {star.name} successful! {surviving_invaders} colonists remain.",
                message_type="Invasion Successful",
                fleet_key=fleet.key
            ))

            if old_owner != NOBODY:
                messages.append(Message(
                    audience=old_owner,
                    text=f"{star.name} has been invaded and captured by enemy forces.",
                    message_type="Planet Lost"
                ))
        else:
            # Invasion failed
            casualties_ratio = invader_strength / defender_strength
            surviving_defenders = int(defenders * (1 - casualties_ratio * 0.9))
            surviving_defenders = max(surviving_defenders, 1)

            star.colonists = surviving_defenders
            fleet.cargo.colonists = 0  # All invaders killed

            messages.append(Message(
                audience=fleet.owner,
                text=f"Invasion of {star.name} failed! All invaders killed.",
                message_type="Invasion Failed",
                fleet_key=fleet.key
            ))

            messages.append(Message(
                audience=star.owner,
                text=f"Your colonists on {star.name} repelled an invasion. "
                     f"{surviving_defenders} colonists survived.",
                message_type="Invasion Repelled"
            ))

        return messages
