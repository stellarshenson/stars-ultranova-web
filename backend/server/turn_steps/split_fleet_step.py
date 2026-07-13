"""
Stars Nova Web - Split Fleet Step
Ported from ServerState/TurnSteps/SplitFleetStep.cs (118 lines)

Processes fleet split/merge operations and cargo transfers at waypoint zero.
"""

from typing import List, TYPE_CHECKING

from .base import ITurnStep
from ...core.commands.base import Message
from ...core.data_structures.cargo import Cargo
from ...core.globals import NOBODY, COLONISTS_PER_KILOTON
from ...core.waypoints.waypoint import (
    WaypointTask, WaypointTaskBase, get_task_type, NoTaskObj, Waypoint,
    CargoMode, InvadeTaskObj
)

if TYPE_CHECKING:
    from ..server_data import ServerData


def _clamp_to_free_capacity(moved: Cargo, free: int) -> None:
    """
    Reduce a load amount so it fits the fleet's free cargo capacity.

    Reduction order Ironium, Boranium, Germanium, colonists - the same
    order the split overflow spill uses (SplitMergeTask.cs ReassignCargo
    / game_manager._spill_overflow).
    """
    excess = moved.mass - free
    if excess <= 0:
        return
    for attr in ("ironium", "boranium", "germanium",
                 "colonists_in_kilotons"):
        if excess <= 0:
            break
        amount = getattr(moved, attr)
        cut = min(amount, excess)
        setattr(moved, attr, amount - cut)
        excess -= cut


def _load_cargo(fleet, star, amount: Cargo) -> Cargo:
    """
    Load cargo star -> fleet (CargoTask.cs Load, lines 216-228).

    C# performs `fleet.Cargo.Add(Amount); star.Remove(Amount);` without
    clamping (the client dialog pre-clamps). The server-authoritative
    port clamps defensively to what the star holds and to the fleet's
    free cargo capacity, because state can change between order and
    execution.
    """
    available = Cargo(
        ironium=max(0, star.resources_on_hand.ironium),
        boranium=max(0, star.resources_on_hand.boranium),
        germanium=max(0, star.resources_on_hand.germanium),
        colonists_in_kilotons=max(0, star.colonists // COLONISTS_PER_KILOTON)
    )
    moved = Cargo.min(amount, available)
    _clamp_to_free_capacity(
        moved, fleet.total_cargo_capacity - fleet.cargo.mass)
    fleet.cargo.add(moved)
    star.remove_cargo(moved)
    return moved


def _unload_cargo(fleet, star, amount: Cargo) -> Cargo:
    """
    Unload cargo fleet -> star (CargoTask.cs Unload, lines 198-210).

    C# performs `star.Add(Amount); fleet.Cargo.Remove(Amount);` without
    clamping; the server port defensively clamps to what is aboard.
    """
    moved = Cargo.min(amount, fleet.cargo)
    star.add_cargo(moved)
    fleet.cargo.remove(moved)
    return moved


def perform_cargo_task(server_state: 'ServerData', fleet, waypoint,
                       star) -> List[Message]:
    """
    Execute a waypoint CargoTask against the star the fleet orbits.

    Port of CargoTask.cs IsValid (lines 145-176) and Perform (lines
    180-228). The task object stays pure data (wave-2 pattern, as with
    RemoteMineStep); the server layer executes it.

    Web-authority deviations from C#, documented per commodity:
    - Amounts are clamped defensively (C# relies on client pre-clamping)
    - SET mode is a canonical Stars! "Set Amount To" rule with no C#
      equivalent (CargoMode has only Load/Unload, CargoTask.cs:31-35):
      per commodity, positive delta follows the Load path, negative
      the Unload path, with the same clamps
    - Unloading colonists at a foreign-owned star delegates to the
      invasion task (CargoTask.cs:159-173 creates an InvadeTask and
      performs it): the waypoint's task is replaced with InvadeTaskObj
      so PostBombingStep - the established invade site - resolves it
      this same turn. Non-colonist transfers at a foreign star are
      refused (there is no legitimate mineral transfer at a foreign
      star in C# either)
    - At an uninhabited (NOBODY) star minerals move freely (matching
      game_manager.transfer_cargo policy) but colonist unload is
      refused - dropping colonists is colonization or invasion, not
      cargo transfer (mirrors game_manager.transfer_cargo)

    Args:
        server_state: Current game state.
        fleet: Fleet performing the task.
        waypoint: The waypoint carrying the CargoTaskObj; its task may
            be replaced with InvadeTaskObj (foreign-star delegation).
        star: Star the fleet orbits, or None when in deep space.

    Returns:
        List of messages generated.
    """
    messages: List[Message] = []
    task = waypoint.task

    # A bare enum task carries no amount - nothing to transfer
    if not isinstance(task, WaypointTaskBase) or \
            getattr(task, 'amount', None) is None:
        return messages

    # Not in orbit of a star (CargoTask.cs:147-154)
    if star is None:
        messages.append(Message(
            audience=fleet.owner,
            text=f"Fleet {fleet.name} attempted to unload cargo "
                 f"while not in orbit.",
            message_type="Cargo",
            fleet_key=fleet.key
        ))
        return messages

    # Resolve per-commodity load/unload sub-amounts. LOAD and UNLOAD
    # carry the amount directly; SET derives signed deltas from the
    # current hold (canonical rule - no C# equivalent).
    load_amount = Cargo()
    unload_amount = Cargo()
    if task.mode == CargoMode.LOAD:
        load_amount = task.amount.copy()
    elif task.mode == CargoMode.UNLOAD:
        unload_amount = task.amount.copy()
    else:  # CargoMode.SET
        for attr in ("ironium", "boranium", "germanium",
                     "colonists_in_kilotons"):
            delta = getattr(task.amount, attr) - getattr(fleet.cargo, attr)
            if delta > 0:
                setattr(load_amount, attr, delta)
            elif delta < 0:
                setattr(unload_amount, attr, -delta)

    # Foreign-owned star: C# delegates the whole task to InvadeTask
    # (CargoTask.cs:159-173) - unloading colonists onto a foreign star
    # IS an invasion; there is no legitimate mineral transfer there.
    if star.owner != fleet.owner and star.owner != NOBODY:
        if unload_amount.colonists_in_kilotons > 0:
            waypoint.task = InvadeTaskObj()
            return messages
        messages.append(Message(
            audience=fleet.owner,
            text=f"Fleet {fleet.name} cannot transfer cargo at "
                 f"{star.name} - the planet is owned by another empire.",
            message_type="Cargo",
            fleet_key=fleet.key
        ))
        return messages

    # Uninhabited star: colonist unload is colonization/invasion, not
    # cargo transfer (mirrors game_manager.transfer_cargo policy);
    # colonist load clamps to zero anyway (nobody to beam up)
    if star.owner == NOBODY and unload_amount.colonists_in_kilotons > 0:
        unload_amount.colonists_in_kilotons = 0
        messages.append(Message(
            audience=fleet.owner,
            text=f"Fleet {fleet.name} cannot unload colonists at "
                 f"uninhabited {star.name}.",
            message_type="Cargo",
            fleet_key=fleet.key
        ))

    if unload_amount.mass > 0:
        _unload_cargo(fleet, star, unload_amount)
        # Message text from CargoTask.cs:203
        messages.append(Message(
            audience=fleet.owner,
            text=f"Fleet {fleet.name} has unloaded its cargo "
                 f"at {star.name}.",
            message_type="Cargo",
            fleet_key=fleet.key
        ))

    if load_amount.mass > 0:
        _load_cargo(fleet, star, load_amount)
        # Message text from CargoTask.cs:221
        messages.append(Message(
            audience=fleet.owner,
            text=f"Fleet {fleet.name} has loaded cargo from {star.name}.",
            message_type="Cargo",
            fleet_key=fleet.key
        ))

    return messages


class SplitFleetStep(ITurnStep):
    """
    Split/merge fleet turn step.

    The CargoTask and SplitMergeTask commands were pre-processed in sequence
    but not removed (during ParseCommands) to keep indices aligned between
    server and client. This step removes the already processed waypoints.

    Pre-existing waypoint zero tasks are also executed here.

    Ported from SplitFleetStep.cs.
    """

    def process(self, server_state: 'ServerData') -> List[Message]:
        """
        Process split/merge and cargo transfer cleanup.

        Args:
            server_state: Current game state.

        Returns:
            List of messages generated.
        """
        messages: List[Message] = []

        for fleet in server_state.iterate_all_fleets():
            if len(fleet.waypoints) == 0:
                continue

            # Store original waypoint zero for restoration if needed
            original_waypoint = fleet.waypoints[0].copy() if hasattr(fleet.waypoints[0], 'copy') else fleet.waypoints[0]
            waypoint_zero_destination = fleet.waypoints[0].destination

            index = 0
            while index < len(fleet.waypoints) and fleet.waypoints[index].destination == waypoint_zero_destination:
                current_task = get_task_type(fleet.waypoints[index].task)

                if current_task == WaypointTask.SPLIT_MERGE:
                    # Remove waypoints that have already been processed
                    fleet.waypoints.pop(index)
                    # Don't increment index since we removed an element

                elif current_task == WaypointTask.TRANSFER_CARGO:
                    waypoint = fleet.waypoints[index]
                    task = waypoint.task

                    # Only waypoint-ZERO cargo orders execute here: the
                    # waypoint must sit at the fleet's current position
                    # (in C# the client copies cargo waypoints from
                    # Waypoints[0], CargoDialog.cs:183-191, so this is
                    # implicit there). A cargo waypoint at a remote
                    # destination travels and executes on arrival
                    # (TurnGenerator._update_fleet).
                    dx = waypoint.position_x - fleet.position.x
                    dy = waypoint.position_y - fleet.position.y
                    if (dx * dx + dy * dy) > 1.0:
                        index += 1
                        continue

                    # Spent Load/Unload tasks (amount 0) are just
                    # removed; SET with a zero amount is a legitimate
                    # "empty the hold" order and still executes
                    if (isinstance(task, WaypointTaskBase)
                            and getattr(task, 'amount', None) is not None
                            and (task.amount.mass != 0
                                 or task.mode == CargoMode.SET)):
                        # Resolve the star at the fleet's location:
                        # the orbit reference first, else the waypoint
                        # destination when it names the star the fleet
                        # is actually at
                        star = server_state.all_stars.get(
                            fleet.in_orbit_name or "")
                        if star is None:
                            candidate = server_state.all_stars.get(
                                waypoint.destination or "")
                            if candidate is not None:
                                dx = candidate.position.x - fleet.position.x
                                dy = candidate.position.y - fleet.position.y
                                if (dx * dx + dy * dy) <= 1.0:
                                    star = candidate

                        messages.extend(perform_cargo_task(
                            server_state, fleet, waypoint, star))

                        if get_task_type(waypoint.task) == \
                                WaypointTask.INVADE:
                            # Foreign-star colonist unload delegated to
                            # the invade task (CargoTask.cs:159-173);
                            # PostBombingStep resolves and pops it
                            index += 1
                            continue

                    fleet.waypoints.pop(index)
                else:
                    index += 1

            # Stars! always has at least a NoTask waypoint for current position
            if len(fleet.waypoints) == 0:
                from ...core.waypoints.waypoint import Waypoint
                restored_waypoint = Waypoint(
                    position_x=fleet.position.x,
                    position_y=fleet.position.y,
                    destination=original_waypoint.destination if hasattr(original_waypoint, 'destination') else "",
                    task=WaypointTask.NO_TASK
                )
                fleet.waypoints.append(restored_waypoint)

        # Cleanup empty fleets
        server_state.cleanup_fleets()

        return messages
