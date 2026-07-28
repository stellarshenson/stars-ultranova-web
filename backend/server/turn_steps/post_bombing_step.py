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
from ...core.defenses import best_defense_type, best_planetary_scanner, \
    compute_defense_coverage, race_trait_codes
from ...core.waypoints.waypoint import WaypointTask, get_task_type
from ...core.globals import NOBODY, COLONISTS_PER_KILOTON

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

                # Handle colonization. An occupied target aborts
                # inside _perform_colonization (ColoniseTask.cs
                # IsValid) - colonize NEVER converts to an invasion;
                # taking an inhabited planet requires an explicit
                # INVADE order
                if task_type == WaypointTask.COLONIZE:
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

        # Validity guards in the C# order (ColoniseTask.cs IsValid,
        # lines 71-108: occupied, colonists aboard, colonization
        # module) - an invalid task aborts with no state change, so
        # colonists stay aboard (TurnGenerator.cs:457-465 skips
        # Perform on IsValid failure)

        # Occupied planet - ANY occupant, foreign or own
        # (ColoniseTask.cs:88-92; run100 DEF-12: this guard was
        # missing and a foreign-owned target auto-invaded instead)
        if star.colonists != 0:
            messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} attempted to colonise {star.name} "
                     f"but it is already occupied.",
                message_type="Colonization Failed",
                fleet_key=fleet.key
            ))
            return messages

        # Check if there are colonists to drop (ColoniseTask.cs:94-98)
        colonists_to_drop = fleet.cargo.colonist_numbers

        if colonists_to_drop <= 0:
            messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} attempted to colonise {star.name} "
                     f"but no colonists were on board.",
                message_type="Colonization Failed",
                fleet_key=fleet.key
            ))
            return messages

        # Check if fleet can colonize (ColoniseTask.cs:100-104)
        if not getattr(fleet, 'can_colonize', False):
            messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} attempted to colonise {star.name} "
                     f"but no ships with colonization module were "
                     f"present.",
                message_type="Colonization Failed",
                fleet_key=fleet.key
            ))
            return messages

        # Perform colonization
        star.owner = fleet.owner
        star.colonists = colonists_to_drop
        star.this_race = sender.race
        fleet.cargo.colonists_in_kilotons = 0

        # Transfer cargo to planet
        star.resources_on_hand.ironium += fleet.cargo.ironium
        fleet.cargo.ironium = 0
        star.resources_on_hand.boranium += fleet.cargo.boranium
        fleet.cargo.boranium = 0
        star.resources_on_hand.germanium += fleet.cargo.germanium
        fleet.cargo.germanium = 0

        # Add star to sender's owned stars
        sender.owned_stars[star.name] = star

        # New colony installations take the empire's best researched
        # types (canonical rule - the C# reference leaves DefenseType
        # "None", zeroing coverage of any defenses built later, and
        # colonies keep ScannerType "None" until the next scanner
        # unlock sweeps every owned star; the web applies the best
        # usable types at colonize time so colonies defend and scan
        # consistently with the homeworld)
        race_traits = race_trait_codes(sender.race)
        star.defense_type = best_defense_type(
            sender.research_levels, race_traits)
        best_scanner = best_planetary_scanner(
            race_traits, sender.research_levels)
        if best_scanner is not None:
            star.scanner_type = best_scanner.name
            star.scan_range = best_scanner.scan_range_normal
            star.pen_scan_range = best_scanner.scan_range_penetrating

        messages.append(Message(
            audience=fleet.owner,
            text=f"You have colonized {star.name}. {colonists_to_drop:,} "
                 f"colonists are now living there.",
            message_type="Colonization",
            fleet_key=fleet.key
        ))

        # Deliberate web deviation from C# (adjudicated better than
        # canon in the run100 forensics): only the colonizer tokens
        # are consumed and their hull mass is half-salvaged as
        # ironium, where ColoniseTask.cs:119-127 clears the ENTIRE
        # fleet (Composition.Clear()) and salvages 0.75 * fleet
        # TotalCost as surface resources - escorts survive here.
        consumed = []
        for token_key, token in fleet.tokens.items():
            if token.can_colonize:
                star.resources_on_hand.ironium += token.mass // 2
                consumed.append(token_key)
        for token_key in consumed:
            del fleet.tokens[token_key]

        return messages

    def _has_starbase(self, star, server_state) -> bool:
        """A starbase kills all invading troops (InvadeTask.cs:134-138)."""
        owner_empire = server_state.all_empires.get(star.owner)
        if owner_empire is None:
            return False
        for fleet in owner_empire.owned_fleets.values():
            if (getattr(fleet, 'is_starbase', False)
                    and fleet.in_orbit_name == star.name):
                return True
        return False

    def _perform_invasion(self, fleet, star, sender, receiver, server_state) -> List[Message]:
        """
        Perform invasion of an inhabited planet.

        Port of InvadeTask.cs IsValid (lines 66-141) and Perform
        (lines 143-243), including the Friend/Neutral relation
        cancellation (InvadeTask.cs:110-131).

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
        prefix = f"Fleet {fleet.name} has waypoint orders to invade "

        # IsValid checks (InvadeTask.cs:66-141)
        troops = fleet.cargo.colonist_numbers
        if troops <= 0:
            messages.append(Message(
                audience=fleet.owner,
                text=prefix + "but there are no troops on board.",
                message_type="Invasion",
                fleet_key=fleet.key
            ))
            return messages

        if star.owner == fleet.owner:
            # Already own this planet - colonists beam down safely
            # (InvadeTask.cs:93-101)
            star.colonists += troops
            fleet.cargo.colonists_in_kilotons = 0
            messages.append(Message(
                audience=fleet.owner,
                text=prefix + f"{star.name} but it is already ours. "
                     f"Troops have joined the local populace.",
                message_type="Invasion",
                fleet_key=fleet.key
            ))
            return messages

        if star.owner == NOBODY:
            # Not colonised - can't invade (InvadeTask.cs:103-108)
            messages.append(Message(
                audience=fleet.owner,
                text=prefix + f"{star.name} but it is not colonised. "
                     f"You must send a ship with a colony module and "
                     f"orders to colonise to take this system.",
                message_type="Invasion",
                fleet_key=fleet.key
            ))
            return messages

        # Friend/Neutral relation cancels the invasion
        # (InvadeTask.cs:110-131). The check sits before the troop
        # commit below - IsValid runs before Perform in C# - so a
        # cancelled invasion keeps its colonists aboard
        relation = sender.empire_reports.get(
            star.owner, {}).get("relation", "Enemy")
        if relation in ("Friend", "Neutral"):
            race_name = (sender.empire_reports.get(
                star.owner, {}).get("race_name")
                or getattr(receiver, 'race_name', '')
                or f"empire {star.owner}")
            messages.append(Message(
                audience=fleet.owner,
                text=prefix + f"{star.name} but the {race_name} are "
                     f"not our enemies. Order has been cancelled.",
                message_type="Invasion",
                fleet_key=fleet.key
            ))
            return messages

        if self._has_starbase(star, server_state):
            messages.append(Message(
                audience=fleet.owner,
                text=prefix + f"{star.name} but the starbase at "
                     f"{star.name} would kill all invading troops. "
                     f"Order has been cancelled.",
                message_type="Invasion",
                fleet_key=fleet.key
            ))
            return messages

        # Perform (InvadeTask.cs:143-243). The troops are now
        # committed to take the star or die trying
        fleet.cargo.colonists_in_kilotons = 0
        defender_id = star.owner

        # Take into account the defenses (InvadeTask.cs:158-159)
        coverage = compute_defense_coverage(star)
        troops_on_ground = int(troops * (1.0 - coverage["invasion"]))

        # Attacker and defender bonuses (InvadeTask.cs:162-172)
        attacker_bonus = 1.1
        if sender.race is not None and sender.race.has_trait("WM"):
            attacker_bonus *= 1.5
        defender_bonus = 1.0
        if (receiver is not None and receiver.race is not None
                and receiver.race.has_trait("IS")):
            defender_bonus *= 2.0

        defender_strength = int(star.colonists * defender_bonus)
        attacker_strength = int(troops_on_ground * attacker_bonus)
        survivor_strength = defender_strength - attacker_strength

        text = (f"{fleet.owner}'s fleet {fleet.name} attacked "
                f"{star.name} with {troops} troops. ")

        if survivor_strength > 0:
            # Defenders win (InvadeTask.cs:181-198)
            remaining_defenders = max(
                int(survivor_strength / defender_bonus),
                COLONISTS_PER_KILOTON)
            defenders_killed = star.colonists - remaining_defenders
            star.colonists = remaining_defenders

            text += (f"The attackers were slain but {defenders_killed}"
                     f" colonists were killed in the attack.")
            # Identical text to wolf and lamb, as in the original
            messages.append(Message(
                audience=fleet.owner, text=text,
                message_type="Invasion", fleet_key=fleet.key))
            messages.append(Message(
                audience=defender_id, text=text,
                message_type="Invasion"))
        elif survivor_strength < 0:
            # Attackers win (InvadeTask.cs:199-222)
            if getattr(star, 'manufacturing_queue', None) is not None:
                star.manufacturing_queue.orders.clear()
            remaining_attackers = max(
                int(-survivor_strength / attacker_bonus),
                COLONISTS_PER_KILOTON)
            attackers_killed = troops - remaining_attackers
            star.colonists = remaining_attackers

            if receiver is not None and star.name in receiver.owned_stars:
                del receiver.owned_stars[star.name]
            star.owner = fleet.owner
            sender.owned_stars[star.name] = star
            star.this_race = sender.race
            # The new owner's researched defense type now governs the
            # captured installations (canonical rule, see
            # core/defenses.best_defense_type)
            star.defense_type = best_defense_type(
                sender.research_levels, race_trait_codes(sender.race))

            text += (f"The defenders were slain but {attackers_killed}"
                     f" troops were killed in the attack.")
            messages.append(Message(
                audience=fleet.owner, text=text,
                message_type="Invasion", fleet_key=fleet.key))
            messages.append(Message(
                audience=defender_id, text=text,
                message_type="Invasion"))
        else:
            # No survivors - clear out the colony (InvadeTask.cs:223-240)
            text += ("Both sides fought to the last and none were left"
                     " to claim the planet!")
            messages.append(Message(
                audience=fleet.owner, text=text,
                message_type="Invasion", fleet_key=fleet.key))
            messages.append(Message(
                audience=defender_id, text=text,
                message_type="Invasion"))

            if getattr(star, 'manufacturing_queue', None) is not None:
                star.manufacturing_queue.orders.clear()
            star.colonists = 0
            star.mines = 0
            star.factories = 0
            star.owner = NOBODY

        return messages
