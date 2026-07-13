"""
Stars Nova Web - Remote Mine Step

No C# equivalent - remote mining is a stub in the reference
(ServerState/TurnSteps/ has no mining step, Common/Waypoints/ no
mining task; GameInitialiser.cs:284 only grants ARM the hulls and
robots "implemented in component definitions"). This step applies
canonical Stars! remote mining rules:

- A fleet whose waypoint-0 task is Remote Mine, orbiting an
  UNINHABITED planet, mines every year it stays with the task
- Per mineral: mined = int(total_robot_rate * concentration / 100.0)
- Minerals are deposited on the planet SURFACE, not in fleet cargo
- Concentration depletes exactly like planetary mining
  (Star.cs:443-476: drops 1 point per 12500/concentration kT mined,
  floor 1)
- Runs before StarUpdateStep (canonical order of events: remote
  mining precedes planetary mining/production)
"""

from typing import List, TYPE_CHECKING

from .base import ITurnStep
from ...core.commands.base import Message
from ...core.globals import NOBODY
from ...core.waypoints.waypoint import WaypointTask, get_task_type

if TYPE_CHECKING:
    from ..server_data import ServerData


class RemoteMineStep(ITurnStep):
    """Remote mining turn step (canonical rules - C# stub)."""

    def process(self, server_state: 'ServerData') -> List[Message]:
        """
        Execute remote mining for every fleet with the task.

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
            if get_task_type(waypoint_zero.task) != WaypointTask.REMOTE_MINE:
                continue

            rate = fleet.total_mining_rate
            if rate <= 0:
                continue

            star = server_state.all_stars.get(fleet.in_orbit_name or "")
            if star is None:
                messages.append(Message(
                    audience=fleet.owner,
                    text=f"{fleet.name} cannot remote mine in deep space",
                    message_type="Remote Mining",
                    fleet_key=fleet.key
                ))
                continue

            # Canonical rule: only UNINHABITED planets may be remote
            # mined - never an owned or foreign colony
            if star.owner != NOBODY or star.colonists > 0:
                messages.append(Message(
                    audience=fleet.owner,
                    text=f"{fleet.name} cannot remote mine {star.name} - "
                         f"the planet is inhabited",
                    message_type="Remote Mining",
                    fleet_key=fleet.key
                ))
                continue

            total_mined = 0
            for mineral in ("ironium", "boranium", "germanium"):
                concentration = getattr(star.mineral_concentration, mineral)
                mined = int(rate * concentration / 100.0)
                setattr(star.resources_on_hand, mineral,
                        getattr(star.resources_on_hand, mineral) + mined)
                total_mined += mined

                # Deplete concentration with the planetary mining rule
                # (Star.cs:443-476 / star.py _mine_mineral): drops 1
                # point per 12500/concentration kT mined, floor 1 -
                # applied to remote mining per canonical rules
                if concentration > 0:
                    new_concentration = (
                        concentration - (mined * concentration // 12500))
                    if new_concentration < 1:
                        new_concentration = 1
                    setattr(star.mineral_concentration, mineral,
                            new_concentration)

            messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} has mined {total_mined} kT of minerals "
                     f"from {star.name}",
                message_type="Remote Mining",
                fleet_key=fleet.key
            ))

        return messages
