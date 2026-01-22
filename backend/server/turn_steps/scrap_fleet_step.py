"""
Stars Nova Web - Scrap Fleet Step
Ported from ServerState/TurnSteps/ScrapFleetStep.cs (65 lines)

Processes fleet scrap orders at waypoint zero.
"""

from typing import List, TYPE_CHECKING

from .base import ITurnStep
from ...core.commands.base import Message
from ...core.waypoints.waypoint import WaypointTask, get_task_type

if TYPE_CHECKING:
    from ..server_data import ServerData


class ScrapFleetStep(ITurnStep):
    """
    Scrap fleet turn step.

    Processes ScrapTask waypoints at position zero, allowing fleets
    to be scrapped for resources at a star.

    Ported from ScrapFleetStep.cs.
    """

    def process(self, server_state: 'ServerData') -> List[Message]:
        """
        Process fleet scrap orders.

        Args:
            server_state: Current game state.

        Returns:
            List of messages generated.
        """
        messages: List[Message] = []

        for fleet in server_state.iterate_all_fleets():
            if len(fleet.waypoints) == 0:
                continue

            waypoint_zero = fleet.waypoints[0]

            # Check if task is ScrapTask
            if get_task_type(waypoint_zero.task) != WaypointTask.SCRAP:
                continue

            # Find target star
            target_star = server_state.all_stars.get(waypoint_zero.destination)

            if target_star is not None:
                fleet.in_orbit = target_star

            # Get sender empire
            sender = server_state.all_empires.get(fleet.owner)
            if sender is None:
                continue

            # Perform scrap operation
            # Calculate scrap value (typically 75% of build cost if at starbase,
            # 33% if at planet without starbase, 0% in deep space)
            scrap_percent = 0.0
            if target_star is not None:
                if target_star.starbase is not None:
                    scrap_percent = 0.75  # 75% at starbase
                else:
                    scrap_percent = 0.33  # 33% at planet without starbase

            # Calculate resources recovered
            total_recovered = 0
            for token in list(fleet.tokens.values()):
                if token.design is not None:
                    cost = token.design.cost
                    recovered_ironium = int(cost.ironium * token.quantity * scrap_percent)
                    recovered_boranium = int(cost.boranium * token.quantity * scrap_percent)
                    recovered_germanium = int(cost.germanium * token.quantity * scrap_percent)

                    if target_star is not None:
                        target_star.resources_on_hand.ironium += recovered_ironium
                        target_star.resources_on_hand.boranium += recovered_boranium
                        target_star.resources_on_hand.germanium += recovered_germanium
                        total_recovered += recovered_ironium + recovered_boranium + recovered_germanium

            # Clear fleet composition (marks it for cleanup)
            fleet.tokens.clear()

            if total_recovered > 0:
                messages.append(Message(
                    audience=fleet.owner,
                    text=f"{fleet.name} has been scrapped at {target_star.name if target_star else 'deep space'}. "
                         f"Recovered {total_recovered} minerals.",
                    message_type="Fleet Scrapped",
                    fleet_key=fleet.key
                ))
            else:
                messages.append(Message(
                    audience=fleet.owner,
                    text=f"{fleet.name} has been scrapped in deep space. No resources recovered.",
                    message_type="Fleet Scrapped",
                    fleet_key=fleet.key
                ))

        # Cleanup empty fleets
        server_state.cleanup_fleets()

        return messages
