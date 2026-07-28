"""
Stars Nova Web - Turn Generator
Ported from ServerState/TurnGenerator.cs (749 lines)

Processes a new turn by reading player orders, applying them,
and generating the new game state.
"""

import random
import math
import logging
from typing import List, Dict, Optional, TYPE_CHECKING

from .turn_steps import (
    ITurnStep,
    FirstStep,
    ScanStep,
    BombingStep,
    PostBombingStep,
    StarUpdateStep,
    SplitFleetStep,
    ScrapFleetStep,
    RemoteMineStep
)
from .scores import Scores
from .victory_check import VictoryCheck
from ..core.commands.base import Message
from ..core.globals import (
    NOBODY, EVERYONE, STARTING_YEAR,
    NEBULA_SPEED_PENALTY, NEBULA_MIN_SPEED_FACTOR,
    STORM_DAMAGE_PER_TURN, STORM_SAFE_WARP, STORM_WARP_RISK_PER_WARP,
    STORM_MISHAP_RISK_CAP, STORM_MISHAP_DAMAGE, STORM_COLONIST_DEATH,
    COLONISTS_PER_KILOTON,
    PACKET_DECAY_RATES, PACKET_MIN_DECAY, PACKET_OVERFLING_MAX,
    PACKET_DAMAGE_DIVISOR, PACKET_UNCAUGHT_RECOVERY,
    MT_MIN_YEARS, MT_LATE_YEARS, MT_SPAWN_CHANCE,
    MT_MAX_ACTIVE_EARLY, MT_MAX_ACTIVE_LATE, MT_WARP_MIN, MT_WARP_MAX,
    MT_GIFT_THRESHOLD, MT_TIER2_GIFT, MT_TIER3_GIFT,
    MT_MINERAL_BOUNTY_FACTOR,
    GATE_HULL_SIZE, GATE_ALLOWED_HULL_SIZES,
    GATE_SPECTRAL_RANGE_FACTOR, GATE_MAX_BASE_RANGE
)
from ..core.data_structures.cargo import Cargo
from ..core.data_structures.tech_level import RESEARCH_KEYS
from ..core.defenses import compute_defense_coverage
from ..core.game_objects.fleet import is_mineral_packet
from ..core.waypoints.waypoint import WaypointTask, get_task_type, Waypoint, NoTaskObj

if TYPE_CHECKING:
    from .server_data import ServerData
    from ..core.game_objects.fleet import Fleet
    from ..core.race.race import Race


logger = logging.getLogger(__name__)


# Mystery Trader hidden-technology items (canonical Stars! MT items;
# components.xml carries each with the "Mystery Trader Item" marker
# property). Sorted so self.rand.choice over the not-yet-owned
# remainder is deterministic.
MT_ITEMS = [
    "Anti-Matter Torpedo",
    "Genesis Device",
    "Mega Poly Shell",
    "Multi-Function Pod",
]


# Turn step ordering constants (from TurnGenerator.cs)
FIRST_STEP = 0
# Web extension (no C# step): remote mining runs just before the star
# update, mirroring the canonical order of events where remote mining
# precedes planetary mining/production
REMOTE_MINE_STEP = 11
STAR_STEP = 12
BOMBING_STEP = 19
COLONISE_STEP = 92
SCAN_STEP = 99


class TurnGenerator:
    """
    Processes turn generation.

    Turn sequence (must match C# exactly):
    1. Read player orders
    2. Parse commands (waypoint 0)
    3. Split/merge fleets
    4. Lay mines
    5. Scrap fleets
    6. Move fleets
    7. Check minefields
    8. Resolve battles
    9. Victory check
    10. Increment turn year
    11. Run turn steps (star update, bombing, colonize, scan)
    12. Move mineral packets
    13. Update minefield visibility
    14. Generate intel

    Ported from TurnGenerator.cs.
    """

    def __init__(self, server_state: 'ServerData'):
        """
        Initialize turn generator.

        Args:
            server_state: The game state to process.
        """
        self.server_state = server_state
        # Seed derived from the global random module: seeded games
        # re-seed the module per turn (GameManager.generate_turn), which
        # makes this instance deterministic too; unseeded games keep
        # the original random behaviour.
        self.rand = random.Random(random.getrandbits(64))

        # Warp each fleet actually travelled at this turn (0 when it
        # never moved), recorded by the movement loop for the storm
        # warp-risk check
        self._fleet_travel_warp: Dict[int, int] = {}

        # Turn steps keyed by priority; run order is the sorted key
        # order (C# TurnGenerator.cs holds them in a SortedList)
        self.turn_steps: Dict[int, ITurnStep] = {}
        self.turn_steps[REMOTE_MINE_STEP] = RemoteMineStep()
        self.turn_steps[STAR_STEP] = StarUpdateStep()
        self.turn_steps[BOMBING_STEP] = BombingStep()
        self.turn_steps[COLONISE_STEP] = PostBombingStep()
        self.turn_steps[SCAN_STEP] = ScanStep()

    def generate(self):
        """
        Generate a new turn.

        Reads player orders, processes the turn sequence,
        and updates the game state for the new year.
        """
        # Parse and apply commands
        self._parse_commands()

        # Process waypoint zero actions
        messages = SplitFleetStep().process(self.server_state)
        self.server_state.all_messages.extend(messages)

        # Lay mines
        messages = FirstStep().process(self.server_state)
        self.server_state.all_messages.extend(messages)

        # Scrap fleets
        messages = ScrapFleetStep().process(self.server_state)
        self.server_state.all_messages.extend(messages)

        # Mystery Trader: resolve gifts, move/exit, spawn, retarget
        # intercept waypoints. Must run BEFORE the fleet move loop so
        # fleets chase the trader's post-move position and co-locate at
        # the turn boundary.
        self._process_traders()

        # Move fleets; minefield check follows each fleet's move, as in
        # the original TurnGenerator.UpdateFleet -> CheckForMinefields.Check
        destroyed_fleets: List['Fleet'] = []
        for fleet in list(self.server_state.iterate_all_fleets()):
            # Packets move in their own step (_move_mineral_packets);
            # the old exact-match name check let "Mineral Packet #N"
            # fleets move twice
            if is_mineral_packet(fleet):
                continue
            if getattr(fleet, 'is_starbase', False):
                # C# TurnGenerator.cs:115-117 runs ProcessFleet for every
                # fleet, starbases included - a starbase repairs itself
                # via the same RegenerateFleet table. Movement and
                # minefields stay skipped since starbases cannot move.
                self._regenerate_fleet(fleet)
                continue

            start_x, start_y = fleet.position.x, fleet.position.y
            ordered_warp = (fleet.waypoints[0].warp_factor
                            if fleet.waypoints else 0)
            if self._process_fleet(fleet):
                destroyed_fleets.append(fleet)
                continue

            self._check_minefield(fleet, start_x, start_y)
            self._check_wormhole_transit(fleet)

            # Record the travel warp for the storm warp-risk check
            moved = (fleet.position.x != start_x
                     or fleet.position.y != start_y)
            self._fleet_travel_warp[fleet.key] = ordered_warp if moved else 0

        self.server_state.cleanup_fleets()

        # Galactic storms: drift and damage ships caught inside
        self._process_storms()

        # Wormhole endpoints drift
        self._process_wormholes()

        # SD minefields flagged to detonate go off right after fleet
        # movement, before battles (canonical order of events)
        self._detonate_minefields()

        self.server_state.cleanup_fleets()

        # Clear old battle reports
        for empire in self.server_state.all_empires.values():
            if hasattr(empire, 'battle_reports'):
                empire.battle_reports.clear()

        # Run battle engine
        if self.server_state.use_ron_battle_engine:
            self._run_ron_battle_engine()
        else:
            self._run_battle_engine()

        self.server_state.cleanup_fleets()

        # Victory check
        self._victory_check()

        # Increment turn year
        self.server_state.turn_year += 1

        for empire in self.server_state.all_empires.values():
            empire.turn_year = self.server_state.turn_year
            empire.turn_submitted = False
            # The per-year orders log covers exactly one turn; a fresh
            # year starts with an empty log (correspondence play)
            if hasattr(empire, 'orders_log'):
                empire.orders_log.clear()

        # Run turn steps in priority order
        for _priority, step in sorted(self.turn_steps.items()):
            messages = step.process(self.server_state)
            if messages:
                self.server_state.all_messages.extend(messages)

        # Move mineral packets
        self._move_mineral_packets()

        self.server_state.cleanup_fleets()

        # Beam-armed fleets sweep enemy minefields near the end of the
        # turn (canonical order of events), before visibility so swept
        # fields vanish from this turn's view
        self._sweep_minefields()

        # Update minefield and wormhole visibility
        self._update_minefield_visibility()
        self._update_wormhole_visibility()

        # Record this turn's scores into each empire's history (year
        # already incremented, intel fresh - IntelWriter.cs:79-89
        # snapshot timing)
        self._record_score_history()

        # Return all generated messages
        return self.server_state.all_messages

    def assemble_empire_data(self):
        """
        Utility function to set intel for the first turn.
        """
        messages = FirstStep().process(self.server_state)
        self.server_state.all_messages.extend(messages)

        messages = ScanStep().process(self.server_state)
        self.server_state.all_messages.extend(messages)

        self._update_wormhole_visibility()

    def _parse_commands(self):
        """
        Validate and apply all commands sent by clients.
        """
        for empire in self.server_state.all_empires.values():
            if empire.id not in self.server_state.all_commands:
                continue

            command_stack = self.server_state.all_commands[empire.id]

            while command_stack:
                command = command_stack.pop()

                valid, message = command.is_valid(empire)

                if valid:
                    if message is not None:
                        self.server_state.all_messages.append(message)

                    result = command.apply_to_state(empire)
                    if result is not None:
                        self.server_state.all_messages.append(result)
                else:
                    # A rejection with no message is benign (e.g. a
                    # no-change research command) - skip silently
                    if message is not None:
                        self.server_state.all_messages.append(message)
                        error_msg = Message(
                            audience=empire.id,
                            text=f"Invalid {type(command).__name__} command for {empire.race.name if empire.race else 'Unknown'}",
                            message_type="Invalid Command"
                        )
                        self.server_state.all_messages.append(error_msg)

            self.server_state.cleanup_fleets()

            # Sync owned stars with all_stars
            for star in empire.owned_stars.values():
                self.server_state.all_stars[star.name] = star

    def _process_fleet(self, fleet: 'Fleet') -> bool:
        """
        Process the elapse of one year for a fleet.

        Args:
            fleet: The fleet to process.

        Returns:
            True if the fleet was destroyed.
        """
        if fleet is None:
            return True

        # Update fleet (movement)
        destroyed = self._update_fleet(fleet)

        if destroyed:
            return True

        # Refuel and repair
        self._regenerate_fleet(fleet)

        # Check for no fuel (TurnGenerator.cs:270-279; original text
        # reads "has ran out of fuel" - normalized to match the web's
        # existing fuel message style). Mineral packets coast without
        # fuel and never warn.
        if fleet.fuel_available == 0 and not fleet.is_starbase \
                and not is_mineral_packet(fleet):
            self.server_state.all_messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} has run out of fuel.",
                message_type="Fuel", fleet_key=fleet.key))

        return False

    def _update_fleet(self, fleet: 'Fleet') -> bool:
        """
        Update fleet position and handle waypoint movement.

        Args:
            fleet: The fleet to update.

        Returns:
            True if destroyed.
        """
        if len(fleet.waypoints) == 0:
            return False

        empire = self.server_state.all_empires.get(fleet.owner)
        if empire is None:
            return False

        race = empire.race

        # Get current position waypoint
        first_waypoint = fleet.waypoints[0]

        # Remove useless waypoints at start (same position, no task)
        while (len(fleet.waypoints) > 0 and
               get_task_type(fleet.waypoints[0].task) == WaypointTask.NO_TASK and
               self._same_position(fleet.position, fleet.waypoints[0])):
            fleet.waypoints.pop(0)

        if len(fleet.waypoints) == 0:
            return False

        waypoint_zero = fleet.waypoints[0]

        # Check for Cheap Engines failure (packets have no engines)
        if race is not None and race.has_trait("CE") \
                and not is_mineral_packet(fleet):
            if waypoint_zero.warp_factor > 6 and self.rand.randint(0, 9) == 0:
                # Engine failure
                msg = Message(
                    audience=fleet.owner,
                    text=f"Fleet {fleet.name}'s engines failed to start. "
                         "Fleet has not moved this turn.",
                    message_type="Cheap Engines",
                    fleet_key=fleet.key
                )
                self.server_state.all_messages.append(msg)
                return False

        # Stargate travel: a warp-10 order between two friendly gated
        # starbases is an instant jump (gate components existed in the
        # original but travel was never implemented; canonical rules).
        # Mineral packets fly, they never gate.
        if waypoint_zero.warp_factor >= 10 and not is_mineral_packet(fleet):
            if self._gate_travel(fleet, waypoint_zero, empire):
                return False

        # Calculate movement
        available_time = 1.0
        messages = []

        travel_status = self._move_fleet(fleet, available_time, race, messages)
        self.server_state.all_messages.extend(messages)

        if travel_status == "in_transit":
            # Still moving. The placeholder inherits the real leg's
            # warp factor (TurnGenerator.cs:430-436 copies
            # waypointZero.WarpFactor) - _move_fleet may already have
            # clamped waypoint_zero to the free warp, and the clamped
            # value is what C# copies too
            new_position = Waypoint(
                position_x=fleet.position.x,
                position_y=fleet.position.y,
                warp_factor=waypoint_zero.warp_factor,
                destination=f"Space at {fleet.position.x:.0f},{fleet.position.y:.0f}",
                task=NoTaskObj()
            )
            fleet.waypoints.insert(0, new_position)
            fleet.in_orbit = None
            fleet.in_orbit_name = None
        else:
            # Arrived
            self.server_state.set_fleet_orbit(fleet)

            if fleet.in_orbit is not None:
                fleet.waypoints[0].position_x = fleet.in_orbit.position.x
                fleet.waypoints[0].position_y = fleet.in_orbit.position.y
                fleet.waypoints[0].destination = fleet.in_orbit.name

            # Execute a cargo task on arrival, then clear it
            # (TurnGenerator.cs:454-465: Task.IsValid/Perform followed
            # by `waypointZero.Task = new NoTask();`). Other task types
            # keep their dedicated turn steps.
            if get_task_type(fleet.waypoints[0].task) == \
                    WaypointTask.TRANSFER_CARGO:
                from .turn_steps.split_fleet_step import perform_cargo_task
                star = None
                if fleet.in_orbit is not None:
                    star = self.server_state.all_stars.get(
                        fleet.in_orbit.name)
                self.server_state.all_messages.extend(perform_cargo_task(
                    self.server_state, fleet, fleet.waypoints[0], star))
                # The foreign-star colonist delegation leaves an
                # InvadeTaskObj in place for PostBombingStep to pop
                if get_task_type(fleet.waypoints[0].task) == \
                        WaypointTask.TRANSFER_CARGO:
                    fleet.waypoints[0].task = NoTaskObj()

        # Update bearing for next waypoint
        if len(fleet.waypoints) > 1:
            next_wp = fleet.waypoints[1]
            dx = fleet.position.x - next_wp.position_x
            dy = fleet.position.y - next_wp.position_y
            fleet.bearing = math.degrees(math.atan2(dy, dx)) + 90

        return False

    def _move_fleet(self, fleet: 'Fleet', available_time: float,
                    race: Optional['Race'], messages: List[Message]) -> str:
        """
        Move fleet towards next waypoint, capped by available fuel.

        Port of Fleet.cs Move (lines 509-577): travel time is the
        smallest of target time (arrival), available time (year end)
        and fuel time (tank empty, Fleet.cs:526 and 542-546 with the
        C# >= comparison), so an empty tank moves a fleet zero light
        years. The burn rate is Fleet.fuel_consumption - the canonical
        per-engine per-warp table formula (ShipDesign.cs:721-744 with
        Fleet.cs:586-608 cargo distribution) - so live burn and client
        estimate stay one formula. Fuel used is int-truncated
        (Fleet.cs:567) and the out-of-fuel drop to free warp is silent
        (Fleet.cs:570-576); the canonical per-turn "has run out of
        fuel." message is emitted by _process_fleet
        (TurnGenerator.cs:270-279).

        Deliberate web deviations:
        - dust nebulae slow effective speed (web extension); the fuel
          rate is scaled by the same factor so burn per light year at
          the ordered warp is unchanged by dust
        - a fleet left in transit at effective warp 0 gets a per-turn
          "stranded" message - C# leaves warp-0 strandings silent
          forever (run100 DEF-13)

        Args:
            fleet: Fleet to move.
            available_time: Time available for movement (1.0 = full turn).
            race: Fleet owner's race.
            messages: List to append messages to.

        Returns:
            Travel status: "arrived" or "in_transit".
        """
        if len(fleet.waypoints) == 0:
            return "arrived"

        waypoint = fleet.waypoints[0]
        target_x = waypoint.position_x
        target_y = waypoint.position_y

        # Calculate distance
        dx = target_x - fleet.position.x
        dy = target_y - fleet.position.y
        distance = math.sqrt(dx * dx + dy * dy)

        if distance < 0.01:
            return "arrived"

        # Calculate speed (warp factor squared = ly per turn)
        warp = waypoint.warp_factor
        speed = warp * warp  # ly per turn

        if speed <= 0:
            # Zero-warp with a leg still to travel: the fleet is
            # stranded (out of fuel with free warp 0, or ordered to
            # stop) - say so instead of deadlocking silently
            self._stranded_message(fleet, messages)
            return "in_transit"

        # Dust nebulae impede travel: sample dust density along this
        # turn's path segment and slow the fleet proportionally
        nebula_factor = 1.0
        nebula = getattr(self.server_state, 'nebula_field', None)
        if nebula is not None:
            segment = min(speed * available_time, distance)
            seg_x = fleet.position.x + dx / distance * segment
            seg_y = fleet.position.y + dy / distance * segment
            dust = nebula.get_average_dust_density_along_path(
                fleet.position.x, fleet.position.y, seg_x, seg_y
            )
            if dust > 0.01:
                nebula_factor = max(NEBULA_MIN_SPEED_FACTOR,
                                    1.0 - NEBULA_SPEED_PENALTY * dust)
                speed *= nebula_factor

        # Fuel consumption rate (mg per year). Mineral packets coast
        # without fuel (canonical Stars! rule). The nebula factor
        # scales the rate so a dust-slowed year burns fuel for the
        # distance actually covered, not a full year at the ordered
        # warp (web extension, keeps burn per ly constant)
        fuel_rate = 0.0
        if not is_mineral_packet(fleet):
            fuel_rate = fleet.fuel_consumption(warp, race) * nebula_factor

        # Travel time: min of target time, available time and fuel
        # time (Fleet.cs:520-546)
        target_time = distance / speed
        fuel_time = float('inf')
        if fuel_rate > 0:
            fuel_time = fleet.fuel_available / fuel_rate

        travel_time = target_time
        status = "arrived"

        if travel_time > available_time:
            travel_time = available_time
            status = "in_transit"

        # C# compares >= (Fleet.cs:542), so exactly-sufficient fuel
        # still reports InTransit
        if travel_time >= fuel_time:
            travel_time = fuel_time
            status = "in_transit"

        # Update position (Fleet.cs:552-565)
        if status == "arrived":
            fleet.position.x = target_x
            fleet.position.y = target_y
        else:
            travelled = speed * travel_time
            ratio = travelled / distance
            fleet.position.x += dx * ratio
            fleet.position.y += dy * ratio

        # Consume fuel, int-truncated (Fleet.cs:567). travel_time is
        # capped at fuel_time so the tank never goes negative
        if fuel_rate > 0:
            fuel_used = int(fuel_rate * travel_time)
            fleet.fuel_available = max(0, fleet.fuel_available - fuel_used)

        # Out of fuel: drop to the free warp speed, silently - C#
        # Fleet.cs:570-576 emits nothing here; the canonical per-turn
        # message comes from _process_fleet (TurnGenerator.cs:270-279)
        if status == "in_transit" and fuel_rate > fleet.fuel_available:
            free_warp = fleet.free_warp_speed
            if waypoint.warp_factor > free_warp:
                waypoint.warp_factor = free_warp
            if free_warp <= 0:
                # No free warp - the fleet is going nowhere (web
                # addition, see docstring)
                self._stranded_message(fleet, messages)

        return status

    def _stranded_message(self, fleet: 'Fleet', messages: List[Message]):
        """
        Per-turn stranded notice for a fleet stuck in transit at warp 0.

        Web addition (run100 DEF-13): C# leaves a warp-0 in-transit
        fleet silent forever; the web tells the player each turn so a
        stranded fleet is never a silent deadlock.
        """
        messages.append(Message(
            audience=fleet.owner,
            text=f"{fleet.name} is stranded in deep space - out of fuel.",
            message_type="Fuel", fleet_key=fleet.key))

    def _regenerate_fleet(self, fleet: 'Fleet'):
        """
        Refuel and repair fleet.

        Args:
            fleet: Fleet to regenerate.
        """
        if fleet is None:
            return

        # Resolve the orbited star (TurnGenerator.cs:308-313). The C#
        # keeps fleet.InOrbit linked at all times; the web's runtime
        # in_orbit reference is only set on arrival or on deserialize,
        # so fall back to the persisted in_orbit_name for fleets that
        # have been parked since the state was created or cached.
        star = fleet.in_orbit
        if star is not None:
            star = self.server_state.all_stars.get(star.name)
        elif fleet.in_orbit_name:
            star = self.server_state.all_stars.get(fleet.in_orbit_name)

        # Refuel if at friendly starbase with dock: own star, or one
        # whose owner has declared the fleet's empire a Friend
        starbase = self._get_starbase(star)
        if (star is not None and
                self._friendly_star(star, fleet) and
                starbase is not None and
                starbase.can_refuel):
            fleet.fuel_available = fleet.total_fuel_capacity

        # Repair (TurnGenerator.cs:370-379). The C# restores
        # token.Shields to full every turn (line 372); the web ShipToken
        # caches shields as an immutable design stat and no shield
        # damage persists between turns, so that restore is a no-op
        # here. Armor: C# repairs max(maxArmor * rate / 100, 1)
        # absolute points of the token's total armor per year, capped
        # at max. The web tracks damage as damage_percent (percent of
        # max armor), so the reduction is repair_rate percentage points
        # with a floor equal to the C# 1-point minimum
        # (100 / token.armor, the cached token-total design armor).
        repair_rate = self._get_repair_rate(fleet, star)

        if repair_rate > 0:
            for token in fleet.tokens.values():
                if token.damage_percent <= 0:
                    continue
                reduction = max(float(repair_rate),
                                100.0 / max(1, token.armor))
                token.damage_percent = max(
                    0.0, token.damage_percent - reduction)

    def _get_repair_rate(self, fleet: 'Fleet', star) -> int:
        """
        Get repair rate based on location.

        Args:
            fleet: Fleet to check.
            star: Star fleet is orbiting (or None).

        Returns:
            Repair rate percentage.

        Port of: TurnGenerator.cs RegenerateFleet lines 323-367
        (situation table documented in the remarks at lines 283-300:
        0/1/2/3/5/8/20, "+repair% if stopped or orbiting").
        """
        if star is not None:
            if self._friendly_star(star, fleet):
                starbase = self._get_starbase(star)
                if starbase is not None:
                    if starbase.can_refuel:
                        rate = 20  # Orbiting own planet with dock
                    else:
                        rate = 8  # Own planet with starbase but no dock
                else:
                    rate = 5  # Orbiting own planet, no starbase
            else:
                # 0% while bombing: C# remark TurnGenerator.cs:290,
                # left as a TODO in the body at :349; canonical Stars!
                # rule - a fleet bombing an enemy planet repairs nothing
                if star.owner != NOBODY and fleet.has_bombers:
                    return 0
                rate = 3  # Orbiting enemy planet, not bombing
        else:
            if len(fleet.waypoints) == 0:
                rate = 2  # Stopped in space
            else:
                return 1  # Moving through space - no heal bonus

        # "+repair% if stopped or orbiting" (C# remark
        # TurnGenerator.cs:297, unimplemented in the C# body).
        # Canonical Stars!: Fuel Transport +5%/yr, Super-Fuel Xport
        # +10%/yr, encoded as HealsOthersPercent in components.xml.
        return rate + fleet.heals_others_percent

    def _friendly_star(self, star, fleet: 'Fleet') -> bool:
        """
        Own star, or one whose owner has declared the fleet's empire
        a Friend.

        The C# RegenerateFleet (TurnGenerator.cs:308-379) only ever
        checks own planets; canonical Stars! extends docking rights
        (refuel and starbase repair rates) to fleets of players the
        BASE OWNER has declared Friend.
        """
        if star.owner == fleet.owner:
            return True
        owner_empire = self.server_state.all_empires.get(star.owner)
        return (owner_empire is not None
                and owner_empire.empire_reports.get(
                    fleet.owner, {}).get("relation", "Enemy") == "Friend")

    def _get_starbase(self, star) -> Optional['Fleet']:
        """Resolve the starbase fleet orbiting a star, if any."""
        if star is None or not getattr(star, 'starbase_key', None):
            return None
        empire = self.server_state.all_empires.get(star.owner)
        if empire is None:
            return None
        return empire.owned_fleets.get(star.starbase_key)

    def _same_position(self, pos1, waypoint) -> bool:
        """Check if position matches waypoint position."""
        return (abs(pos1.x - waypoint.position_x) < 0.01 and
                abs(pos1.y - waypoint.position_y) < 0.01)

    def _star_gate(self, star) -> Optional[tuple]:
        """
        Find a stargate at a star: (safe_mass, effective_range) or None.

        The gate lives on the owner's starbase fleet in orbit. The
        effective range is star-fuelled (user directive 2026-07-13):
        the gate model's SafeRange - with "any" (-1) clamped to
        GATE_MAX_BASE_RANGE, so no gate is ever unlimited - is
        multiplied by the host star's spectral class factor
        (GATE_SPECTRAL_RANGE_FACTOR: O throws farthest, M shortest).
        """
        if star is None or star.owner == NOBODY:
            return None
        empire = self.server_state.all_empires.get(star.owner)
        if empire is None:
            return None
        for fleet in empire.owned_fleets.values():
            if not getattr(fleet, 'is_starbase', False):
                continue
            if fleet.in_orbit_name != star.name:
                continue
            for token in fleet.tokens.values():
                if getattr(token, 'has_gate', False):
                    base_range = token.gate_range
                    if base_range < 0 or base_range > GATE_MAX_BASE_RANGE:
                        base_range = GATE_MAX_BASE_RANGE
                    factor = GATE_SPECTRAL_RANGE_FACTOR.get(
                        getattr(star, 'spectral_class', 'G'), 1.0)
                    return (token.gate_mass, base_range * factor)
        return None

    def _gate_travel(self, fleet: 'Fleet', waypoint, empire) -> bool:
        """
        Attempt stargate travel for a warp-10 order.

        Both the origin (orbited star) and the destination star must
        carry a friendly gated starbase. Stargate rework (user
        directive 2026-07-13, deliberate deviations from canonical):

        - only small and medium hulls may gate (GATE_HULL_SIZE);
          large and capital hulls are refused outright, no over-limit
          gamble for them
        - gate range is star-fuelled and never unlimited (_star_gate)
        - mineral cargo never gates - loose mineral logistics stay
          with freighters and mass drivers; colonists gate only for
          Interstellar Traveler (IT) races (canonical cargo rule) and
          fuel always travels free (canonical)
        - exceeding safe mass or range with an allowed hull keeps the
          canonical 25% loss / 50% damage gamble

        Returns True if the order was handled (jump or failure).
        """
        origin = fleet.in_orbit
        if origin is not None:
            origin = self.server_state.all_stars.get(origin.name)
        dest = self.server_state.all_stars.get(waypoint.destination)

        origin_gate = self._star_gate(origin) if (
            origin is not None and origin.owner == fleet.owner) else None
        dest_gate = self._star_gate(dest) if (
            dest is not None and dest.owner == fleet.owner) else None

        if origin_gate is None or dest_gate is None:
            self.server_state.all_messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} cannot make a stargate jump: both "
                     f"origin and destination need your own starbase "
                     f"with a stargate.",
                message_type="Invalid Command", fleet_key=fleet.key))
            waypoint.warp_factor = min(waypoint.warp_factor, 9)
            return False

        # Hull size limit: any large/capital (or unclassified) hull in
        # the fleet blocks the whole jump - refused outright
        for token in fleet.tokens.values():
            size = GATE_HULL_SIZE.get(token.hull_name)
            if size not in GATE_ALLOWED_HULL_SIZES:
                hull = token.hull_name or token.design_name
                self.server_state.all_messages.append(Message(
                    audience=fleet.owner,
                    text=f"{fleet.name} cannot make a stargate jump: "
                         f"the {hull} hull is too large for gate "
                         f"transit - only small and medium hulls may "
                         f"use stargates.",
                    message_type="Invalid Command", fleet_key=fleet.key))
                waypoint.warp_factor = min(waypoint.warp_factor, 9)
                return False

        # No minerals through gates: mineral cargo aboard blocks the
        # jump for everyone. Colonists are cargo too - canonical Stars!
        # lets only IT races gate cargo - while fuel is not cargo and
        # always travels
        cargo = fleet.cargo
        if (cargo.ironium > 0 or cargo.boranium > 0 or
                cargo.germanium > 0 or cargo.silicoxium > 0):
            self.server_state.all_messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} cannot make a stargate jump: "
                     f"mineral cargo cannot pass through a stargate. "
                     f"Unload the minerals or ship them by freighter.",
                message_type="Invalid Command", fleet_key=fleet.key))
            waypoint.warp_factor = min(waypoint.warp_factor, 9)
            return False
        if cargo.colonists_in_kilotons > 0 and not empire.has_trait("IT"):
            self.server_state.all_messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} cannot make a stargate jump: only "
                     f"Interstellar Traveler races can gate fleets "
                     f"carrying colonists.",
                message_type="Invalid Command", fleet_key=fleet.key))
            waypoint.warp_factor = min(waypoint.warp_factor, 9)
            return False

        distance = math.hypot(dest.position.x - fleet.position.x,
                              dest.position.y - fleet.position.y)

        def limit(a, b) -> float:
            vals = [v for v in (a, b) if v >= 0]  # -1 means unlimited mass
            return min(vals) if vals else float('inf')

        safe_mass = limit(origin_gate[0], dest_gate[0])
        # Ranges from _star_gate are always finite (star-fuelled)
        safe_range = min(origin_gate[1], dest_gate[1])

        over_range = distance > safe_range
        ships_lost = 0
        for token in list(fleet.tokens.values()):
            over_mass = token.mass > safe_mass
            if not over_mass and not over_range:
                continue
            # Over-limit transit: each ship risks destruction and the
            # survivors arrive damaged
            survivors = 0
            for _ in range(token.quantity):
                if self.rand.random() < 0.25:
                    ships_lost += 1
                else:
                    survivors += 1
            token.quantity = survivors
            token.damage_percent = min(99.0, token.damage_percent + 50.0)
            if token.quantity <= 0:
                del fleet.tokens[token.design_key]

        if not fleet.tokens:
            self.server_state.all_messages.append(Message(
                audience=fleet.owner,
                text=f"{fleet.name} was torn apart in a stargate jump "
                     f"beyond the gate's limits!",
                message_type="Fleet Destroyed", fleet_key=fleet.key))
            empire.owned_fleets.pop(fleet.key, None)
            return True

        # Instant jump, no fuel used
        fleet.position.x = dest.position.x
        fleet.position.y = dest.position.y
        self.server_state.set_fleet_orbit(fleet)
        waypoint.position_x = dest.position.x
        waypoint.position_y = dest.position.y
        waypoint.warp_factor = 0

        if ships_lost > 0:
            text = (f"{fleet.name} gated to {dest.name}, losing "
                    f"{ships_lost} ship(s) beyond the gate's limits!")
        else:
            text = f"{fleet.name} has gated safely to {dest.name}."
        self.server_state.all_messages.append(Message(
            audience=fleet.owner, text=text,
            message_type="Stargate", fleet_key=fleet.key))
        return True

    def _check_wormhole_transit(self, fleet: 'Fleet'):
        """
        Pull a fleet through a wormhole it has flown into.

        Transit requires the fleet's waypoint to target the endpoint
        (by name) and the fleet to be at the endpoint's current
        position; the fleet emerges at the opposite end.
        """
        if not fleet.waypoints:
            return
        waypoint = fleet.waypoints[0]
        destination = waypoint.destination or ""
        if not destination.startswith("Wormhole"):
            return

        for wormhole in self.server_state.all_wormholes.values():
            for end_index, end_name, x, y in wormhole.endpoints():
                if destination != end_name:
                    continue
                # Endpoints drift, so allow a small catch radius
                if math.hypot(fleet.position.x - x,
                              fleet.position.y - y) > 5.0:
                    continue

                out_x, out_y = wormhole.other_end(end_index)
                fleet.position.x = out_x
                fleet.position.y = out_y
                fleet.in_orbit = None
                fleet.waypoints.pop(0)
                if not fleet.waypoints:
                    fleet.waypoints.append(Waypoint(
                        position_x=out_x, position_y=out_y,
                        warp_factor=0,
                        destination=f"{wormhole.name} "
                                    f"({'B' if end_index == 0 else 'A'})",
                        task=NoTaskObj()))
                self.server_state.set_fleet_orbit(fleet)
                self.server_state.all_messages.append(Message(
                    audience=fleet.owner,
                    text=f"{fleet.name} has passed through "
                         f"{wormhole.name} and emerged at "
                         f"({out_x:.0f}, {out_y:.0f})!",
                    message_type="Wormhole", fleet_key=fleet.key))
                return

    def _process_wormholes(self):
        """Drift wormhole endpoints (less stable ones drift more)."""
        nebula = self.server_state.nebula_field
        width = nebula.universe_width if nebula else 600
        height = nebula.universe_height if nebula else 600
        for wormhole in self.server_state.all_wormholes.values():
            wormhole.drift(self.rand, width, height)

    def _process_traders(self):
        """
        Mystery Trader turn processing.

        Canonical Stars! Mystery Trader - the C# reference has only a
        TODO (GameInitialiser.cs:180 "Mystery Trader Items ... hidden
        technology"); built from canonical rules per user directive
        (acc-crit Mystery Trader section).

        Order: (a) resolve accumulated gifts on the seeded per-turn
        RNG, (b) move every trader along its straight-line course and
        broadcast departures, (c) roll a spawn once eligible (year
        gate, active cap), (d) retarget fleet waypoints naming a
        trader so the intercept course recomputes every turn. Runs
        BEFORE the fleet move loop: a fleet whose warp covers the
        distance arrives exactly at the trader's end-of-turn position
        and can gift until the next generation.

        The trader is not a Fleet and belongs to no empire, so battle
        engines, minefield checks, storm damage and scans never touch
        it by construction (untouchable criterion). All randomness
        rides self.rand; dict iteration is over sorted keys.
        """
        if not getattr(self.server_state, 'mystery_trader_enabled', True):
            return

        traders = self.server_state.all_traders
        nebula = self.server_state.nebula_field
        width = nebula.universe_width if nebula else 600
        height = nebula.universe_height if nebula else 600

        # (a) Resolve gifts. Below-threshold balances persist (an
        # empire may top up over several gifts while it can still
        # reach the trader); the trader always keeps the cargo.
        for trader_key in sorted(traders):
            trader = traders[trader_key]
            for empire_id in sorted(trader.gifts):
                entry = trader.gifts[empire_id]
                total = entry.get("total", 0)
                if total <= 0:
                    continue
                if total < MT_GIFT_THRESHOLD:
                    self.server_state.all_messages.append(Message(
                        audience=empire_id,
                        text=f"{trader.name} accepts your {total} kT "
                             f"gift with a courteous nod, but offers "
                             f"nothing in return. It expects at least "
                             f"{MT_GIFT_THRESHOLD} kT before parting "
                             f"with its secrets.",
                        message_type="Mystery Trader"))
                    continue
                self._grant_trader_reward(trader, empire_id, entry)
                entry["total"] = 0

        # (b) Move and exit (spawn points sit ON an edge with inward
        # velocity, so the first out-of-bounds step is the exit)
        for trader_key in sorted(traders):
            trader = traders[trader_key]
            if trader.move(width, height):
                del traders[trader_key]
                self._retarget_departed_trader(trader)
                self.server_state.all_messages.append(Message(
                    audience=EVERYONE,
                    text=f"{trader.name} has left the galaxy.",
                    message_type="Mystery Trader"))

        # (c) Spawn roll: eligible from STARTING_YEAR + MT_MIN_YEARS,
        # cap 1 active early, MT_MAX_ACTIVE_LATE from MT_LATE_YEARS on
        years_in = self.server_state.turn_year - STARTING_YEAR
        if years_in >= MT_MIN_YEARS:
            cap = MT_MAX_ACTIVE_LATE if years_in >= MT_LATE_YEARS \
                else MT_MAX_ACTIVE_EARLY
            if len(traders) < cap \
                    and self.rand.random() < MT_SPAWN_CHANCE:
                self._spawn_trader(width, height)

        # (d) Retarget moving waypoints to the post-move positions.
        # C# waypoints are position-only (Common/Waypoints/Waypoint.cs:
        # 36-60, no moving-object targeting anywhere); the web resolves
        # the destination name against the live trader every turn -
        # that IS the moving-waypoint targeting (web extension).
        by_name = {t.name: t for t in traders.values()}
        if by_name:
            for fleet in self.server_state.iterate_all_fleets():
                for wp in fleet.waypoints:
                    trader = by_name.get(wp.destination or "")
                    if trader is not None:
                        wp.position_x = trader.x
                        wp.position_y = trader.y

    def _spawn_trader(self, width: int, height: int):
        """Spawn a trader ON a random edge, targeting a random point on
        the OPPOSITE edge: a straight-line crossing at warp 7-13
        (canonical band; velocity = unit heading * warp^2, so the
        trader may outrun every player drive)."""
        from .server_data import MysteryTrader

        edge = self.rand.randint(0, 3)  # 0=W, 1=E, 2=N, 3=S
        if edge == 0:    # west -> east
            x, y = 0.0, self.rand.uniform(0, height)
            tx, ty = float(width), self.rand.uniform(0, height)
        elif edge == 1:  # east -> west
            x, y = float(width), self.rand.uniform(0, height)
            tx, ty = 0.0, self.rand.uniform(0, height)
        elif edge == 2:  # north -> south
            x, y = self.rand.uniform(0, width), 0.0
            tx, ty = self.rand.uniform(0, width), float(height)
        else:            # south -> north
            x, y = self.rand.uniform(0, width), float(height)
            tx, ty = self.rand.uniform(0, width), 0.0

        warp = self.rand.randint(MT_WARP_MIN, MT_WARP_MAX)
        heading_len = math.hypot(tx - x, ty - y) or 1.0
        speed = warp * warp
        self.server_state.trader_counter += 1
        trader = MysteryTrader(
            key=self.server_state.trader_counter, x=x, y=y,
            velocity_x=(tx - x) / heading_len * speed,
            velocity_y=(ty - y) / heading_len * speed,
            warp=warp)
        self.server_state.all_traders[trader.key] = trader
        self.server_state.all_messages.append(Message(
            audience=EVERYONE,
            text=f"{trader.name} has entered the galaxy at "
                 f"({x:.0f}, {y:.0f}) and is crossing at warp {warp}. "
                 f"Meet it with a generous gift and it may part with "
                 f"its secrets.",
            message_type="Mystery Trader"))

    def _retarget_departed_trader(self, trader):
        """Waypoints chasing a departed trader finish their leg as
        plain positional waypoints: position stays as-is, destination
        rewritten to the space-at style (turn_generator "Space at"
        convention)."""
        for fleet in self.server_state.iterate_all_fleets():
            for wp in fleet.waypoints:
                if wp.destination == trader.name:
                    wp.destination = (f"Space at {wp.position_x:.0f},"
                                      f"{wp.position_y:.0f}")

    # Mystery Trader reward table (chosen numbers - authoritative,
    # mirrored verbatim in the encyclopedia entry). Tier by the
    # unrewarded gift balance G (kT of minerals + colonist kT):
    #   tier 1 (1000-1999): 40% MT component, 30% research boost
    #     (+1 level in 2 distinct fields), 30% mineral bounty
    #     (2x G kT split evenly, loaded onto the gifting fleet up to
    #     free cargo space, fuel topped to full)
    #   tier 2 (2000-3999): 50% component, 25% research (+1 in 4
    #     fields), 15% mineral bounty (3x G), 10% gifted ship
    #   tier 3 (>= 4000):   55% component, 20% research (+2 in 3
    #     fields), 25% gifted ship
    # One self.rand.random() roll against cumulative odds decides the
    # band. If every MT item is already owned the component band falls
    # through to the tier's research boost; a dead gifting fleet
    # converts a mineral bounty to a research boost (+1 in 2 fields).
    def _grant_trader_reward(self, trader, empire_id: int, entry: dict):
        """Roll and grant one reward for an at/above-threshold gift."""
        empire = self.server_state.all_empires.get(empire_id)
        if empire is None:
            return
        total = entry.get("total", 0)
        roll = self.rand.random()
        if total >= MT_TIER3_GIFT:
            if roll < 0.55:
                self._mt_grant_component(trader, empire, 3, 2)
            elif roll < 0.75:
                self._mt_grant_research(trader, empire, 3, 2)
            else:
                self._mt_grant_ship(trader, empire, entry)
        elif total >= MT_TIER2_GIFT:
            if roll < 0.50:
                self._mt_grant_component(trader, empire, 4, 1)
            elif roll < 0.75:
                self._mt_grant_research(trader, empire, 4, 1)
            elif roll < 0.90:
                self._mt_grant_minerals(trader, empire, entry,
                                        MT_MINERAL_BOUNTY_FACTOR + 1)
            else:
                self._mt_grant_ship(trader, empire, entry)
        else:
            if roll < 0.40:
                self._mt_grant_component(trader, empire, 2, 1)
            elif roll < 0.70:
                self._mt_grant_research(trader, empire, 2, 1)
            else:
                self._mt_grant_minerals(trader, empire, entry,
                                        MT_MINERAL_BOUNTY_FACTOR)

    def _mt_grant_component(self, trader, empire, res_fields: int,
                            res_levels: int):
        """Hidden-technology grant: one MT item the empire does not
        own yet (the C# TODO GameInitialiser.cs:180 names 'hidden
        technology' as the intended mechanism - realized as the
        per-empire mt_components grant list gating design_builder)."""
        owned = getattr(empire, 'mt_components', [])
        available = [name for name in MT_ITEMS if name not in owned]
        if not available:
            self._mt_grant_research(trader, empire, res_fields,
                                    res_levels)
            return
        item = self.rand.choice(available)
        empire.mt_components.append(item)
        self.server_state.all_messages.append(Message(
            audience=empire.id,
            text=f"{trader.name} rewards your gift with the secret "
                 f"plans for the {item}! Your shipyards may now "
                 f"build it.",
            message_type="Mystery Trader"))

    def _mt_grant_research(self, trader, empire, fields_n: int,
                           levels: int):
        """Research boost: +levels in fields_n distinct random
        fields."""
        fields = self.rand.sample(RESEARCH_KEYS, fields_n)
        for field_name in fields:
            empire.research_levels.levels[field_name] = \
                empire.research_levels.levels.get(field_name, 0) + levels
        self.server_state.all_messages.append(Message(
            audience=empire.id,
            text=f"{trader.name} rewards your gift with a trove of "
                 f"research: +{levels} level(s) in "
                 f"{', '.join(sorted(fields))}.",
            message_type="Mystery Trader"))

    def _mt_grant_minerals(self, trader, empire, entry: dict,
                           factor: int):
        """Mineral bounty: factor x gift kT split evenly across the
        three minerals, loaded onto the gifting fleet clamped to its
        free cargo space, and fuel topped to full ("minerals/fuel")."""
        fleet = empire.owned_fleets.get(entry.get("fleet_key"))
        if fleet is None:
            # Gifting fleet gone - convert to a research boost
            self._mt_grant_research(trader, empire, 2, 1)
            return
        bounty = factor * entry.get("total", 0)
        free = max(0, fleet.total_cargo_capacity - fleet.cargo.mass)
        loaded = min(bounty, free)
        per_mineral = loaded // 3
        fleet.cargo.ironium += per_mineral
        fleet.cargo.boranium += per_mineral
        fleet.cargo.germanium += loaded - 2 * per_mineral
        fleet.fuel_available = fleet.total_fuel_capacity
        self.server_state.all_messages.append(Message(
            audience=empire.id,
            text=f"{trader.name} rewards your gift with {loaded} kT "
                 f"of refined minerals and a full load of fuel for "
                 f"{fleet.name}.",
            message_type="Mystery Trader", fleet_key=fleet.key))

    def _mt_grant_ship(self, trader, empire, entry: dict):
        """Gifted ship: a Trader Marauder warship materializes at the
        gifting fleet's position (or the trader's, if the fleet is
        gone), fully fueled, owned by the giver."""
        from ..core.data_structures import NovaPoint
        from ..services.ship_specs import (
            SimpleDesign, find_design, make_token)
        from ..core.data_structures.resources import Resources
        from ..core.components.ship_design import Weapon
        from ..core.game_objects.fleet import Fleet

        design = find_design(empire, "Trader Marauder")
        if design is None:
            design = SimpleDesign(
                key=empire.get_next_design_key(),
                name="Trader Marauder", hull_name="Trader Marauder",
                cost=Resources(200, 150, 120, 400),
                mass=400, armor=2000, shields=800,
                fuel_capacity=2000, cargo_capacity=500,
                battle_speed=1.0, initiative=4, optimal_speed=9,
                has_weapons=True,
                # Anti-Matter Torpedo battery
                weapons=[Weapon(power=60, range=6, initiative=4,
                                accuracy=85, group="torpedo")
                         for _ in range(4)])
            empire.designs[design.key] = design

        giver = empire.owned_fleets.get(entry.get("fleet_key"))
        if giver is not None:
            position = NovaPoint(giver.position.x, giver.position.y)
        else:
            position = NovaPoint(trader.x, trader.y)

        key = empire.get_next_fleet_key()
        fleet = Fleet(name=f"Trader Gift #{key & 0xFFFFFFFF}",
                      position=position)
        fleet.key = key
        token = make_token(design, 1)
        fleet.tokens[token.design_key] = token
        fleet.fuel_available = fleet.total_fuel_capacity
        fleet.turn_year = self.server_state.turn_year
        empire.add_or_update_fleet(fleet)
        self.server_state.all_messages.append(Message(
            audience=empire.id,
            text=f"{trader.name} rewards your gift with a warship! "
                 f"{fleet.name} has joined your empire.",
            message_type="Mystery Trader", fleet_key=fleet.key))

    def _process_storms(self):
        """
        Drift galactic storms and apply their hazards to fleets inside.

        Web extension - not in original Stars! (user directive
        2026-07-13). Every effect scales with the LOCAL storm intensity
        at the fleet's position (0 at the blob boundary, the storm's
        intensity at the core): hull damage per turn, a warp mishap
        risk for fleets moving above STORM_SAFE_WARP (the
        minefield-strike analogue) and colonist attrition. Ships whose
        damage reaches 100% are destroyed.

        Orbit safe harbor (user directive, wave 4): storms never affect
        planets, and never affect fleets or starbases in orbit of a
        planet - a fleet whose position coincides with a star is
        sheltered in the planet's magnetosphere and skipped entirely.
        Scan dampening is NOT sheltered: the storm disturbs the medium,
        so a scanner inside a storm still scans worse (ScanStep).

        Storm protection (user directive, wave 4): every effect scales
        by (1 - fleet.storm_protection(race)); at protection 1.0 the
        fleet is fully immune and skipped without a message.
        """
        storms = getattr(self.server_state, 'all_storms', None)
        if not storms:
            return

        nebula = self.server_state.nebula_field
        width = nebula.universe_width if nebula else 600
        height = nebula.universe_height if nebula else 600

        for storm in storms.values():
            storm.drift(width, height)

        for fleet in list(self.server_state.iterate_all_fleets()):
            if getattr(fleet, 'is_starbase', False):
                continue  # starbases shelter in a planet's magnetosphere
            if is_mineral_packet(fleet):
                continue
            # Orbit safe harbor: a fleet parked at a star is untouched
            if self.server_state.get_star_at_position(
                    fleet.position.x, fleet.position.y) is not None:
                continue

            empire = self.server_state.all_empires.get(fleet.owner)
            race = getattr(empire, 'race', None)
            protection = fleet.storm_protection(race)
            if protection >= 1.0:
                continue  # total immunity - zero damage, mishap, attrition

            for storm in storms.values():
                local = storm.get_intensity_at(
                    fleet.position.x, fleet.position.y)
                if local <= 0.0:
                    continue

                ships_lost = self._apply_storm_damage(
                    fleet, STORM_DAMAGE_PER_TURN * local * (1.0 - protection))

                if ships_lost > 0:
                    text = (f"{fleet.name} was caught in a galactic storm - "
                            f"{ships_lost} ship(s) torn apart!")
                else:
                    text = (f"{fleet.name} is riding out a galactic storm "
                            f"and taking hull damage")
                self.server_state.all_messages.append(Message(
                    audience=fleet.owner, text=text,
                    message_type="Storm", fleet_key=fleet.key
                ))

                self._check_storm_mishap(fleet, local, protection)
                self._apply_storm_attrition(fleet, local, protection)
                break  # one storm hit per fleet per turn

    def _apply_storm_damage(self, fleet: 'Fleet', damage: float) -> int:
        """
        Add hull damage percent to every token in the fleet; each
        accumulated 100% destroys one ship.

        Returns:
            Number of ships destroyed.
        """
        ships_lost = 0
        for token in list(fleet.tokens.values()):
            token.damage_percent += damage
            while token.damage_percent >= 100 and token.quantity > 0:
                token.quantity -= 1
                ships_lost += 1
                token.damage_percent -= 100
            if token.quantity <= 0:
                del fleet.tokens[token.design_key]
        return ships_lost

    def _check_storm_mishap(self, fleet: 'Fleet', local: float,
                            protection: float = 0.0):
        """
        Warp-risk check for a fleet that moved through a storm.

        Moving above STORM_SAFE_WARP risks a mishap with chance
        STORM_WARP_RISK_PER_WARP per warp above safe, scaled by the
        local intensity and capped at STORM_MISHAP_RISK_CAP, rolled
        once per turn on the seeded RNG. A mishap deals
        STORM_MISHAP_DAMAGE * local extra damage to every token and
        stops the fleet in the storm, waypoint preserved - the
        minefield-strike analogue (user directive 2026-07-13). Storm
        protection scales BOTH the mishap chance and the mishap damage
        by (1 - protection) (user directive, wave 4).
        """
        warp = self._fleet_travel_warp.get(fleet.key)
        if warp is None:
            warp = (fleet.waypoints[0].warp_factor
                    if fleet.waypoints else 0)
        speeding = warp - STORM_SAFE_WARP
        if speeding <= 0:
            return

        probability = min(STORM_MISHAP_RISK_CAP,
                          STORM_WARP_RISK_PER_WARP * speeding * local) \
            * (1.0 - protection)
        if self.rand.random() >= probability:
            return

        ships_lost = self._apply_storm_damage(
            fleet, STORM_MISHAP_DAMAGE * local * (1.0 - protection))

        # Fleet is stopped dead in the storm, as with a minefield strike
        if fleet.waypoints:
            fleet.waypoints[0].warp_factor = 0

        if ships_lost > 0:
            text = (f"{fleet.name} suffered a warp mishap in a galactic "
                    f"storm - {ships_lost} ship(s) torn apart! The fleet "
                    f"is stopped dead in space.")
        else:
            text = (f"{fleet.name} suffered a warp mishap in a galactic "
                    f"storm and is stopped dead in space!")
        self.server_state.all_messages.append(Message(
            audience=fleet.owner, text=text,
            message_type="Storm", fleet_key=fleet.key
        ))

    def _apply_storm_attrition(self, fleet: 'Fleet', local: float,
                               protection: float = 0.0):
        """
        Colonists carried through a storm die off, scaled by the local
        intensity (user directive 2026-07-13) and by (1 - protection)
        (user directive, wave 4; a fully protected fleet never reaches
        this - _process_storms skips it). Cargo stores colonists in
        kilotons; the loss rounds up so any unprotected exposure costs
        at least one kiloton.
        """
        col_kt = fleet.cargo.colonists_in_kilotons
        if col_kt <= 0:
            return

        deaths_kt = min(col_kt, math.ceil(
            col_kt * STORM_COLONIST_DEATH * local * (1.0 - protection)))
        fleet.cargo.colonists_in_kilotons = col_kt - deaths_kt
        self.server_state.all_messages.append(Message(
            audience=fleet.owner,
            text=(f"{fleet.name} lost "
                  f"{deaths_kt * COLONISTS_PER_KILOTON} colonists to a "
                  f"galactic storm!"),
            message_type="Storm", fleet_key=fleet.key
        ))

    # Mine stats per type, from the Mine Layer component properties in
    # the reference components.xml (Mine Dispenser / Heavy Dispenser /
    # Speed Trap). hit_chance is per light year per warp above safe
    # speed. damage_per_ship approximates DamagePerEngine with one
    # engine per ship (engine counts are not tracked per token).
    MINE_STATS = {
        0: {"safe_speed": 4, "hit_chance": 0.003,
            "damage_per_ship": 100, "min_fleet_damage": 500},
        1: {"safe_speed": 6, "hit_chance": 0.010,
            "damage_per_ship": 50, "min_fleet_damage": 2000},
        2: {"safe_speed": 5, "hit_chance": 0.035,
            "damage_per_ship": 0, "min_fleet_damage": 0},
    }

    def _check_minefield(self, fleet: 'Fleet', start_x: float, start_y: float):
        """
        Check whether a fleet's movement this turn strikes a minefield.

        Ported from CheckForMinefields.cs. The original implementation
        was a stub with hardcoded values; this follows the canonical
        rules its comments describe, using the Mine Layer constants
        from components.xml: chance per light year travelled inside
        the field, per warp above the field's safe speed.
        """
        warp = 0
        if fleet.waypoints:
            warp = fleet.waypoints[0].warp_factor

        for minefield in list(self.server_state.all_minefields.values()):
            if minefield.owner == fleet.owner:
                continue

            # Canonical Stars! rule (the C# CheckForMinefields.cs
            # stub has no owner or relation check at all): a minefield
            # never detonates against fleets of empires the FIELD
            # OWNER has declared Friend; Neutral and Enemy are struck
            # normally. Direction matters: it is the field owner's
            # declared relation toward the traveling empire.
            field_owner = self.server_state.all_empires.get(minefield.owner)
            if (field_owner is not None
                    and field_owner.empire_reports.get(
                        fleet.owner, {}).get("relation", "Enemy")
                    == "Friend"):
                continue

            stats = self.MINE_STATS.get(minefield.mine_type, self.MINE_STATS[0])

            # Travelling at or below the safe speed never triggers mines
            speeding = warp - stats["safe_speed"]
            if speeding <= 0:
                continue

            dist_in_field = self._chord_length(
                start_x, start_y, fleet.position.x, fleet.position.y,
                minefield.position_x, minefield.position_y, minefield.radius
            )
            if dist_in_field <= 0:
                continue

            probability = min(
                1.0, stats["hit_chance"] * speeding * dist_in_field
            )
            if self.rand.random() < probability:
                self._strike_minefield(fleet, minefield, stats)
                break  # one strike per fleet per turn

    def _chord_length(self, x1: float, y1: float, x2: float, y2: float,
                      cx: float, cy: float, radius: float) -> float:
        """Length of the segment (x1,y1)-(x2,y2) inside a circle."""
        dx, dy = x2 - x1, y2 - y1
        seg_len = math.hypot(dx, dy)
        if seg_len < 1e-9:
            # Stationary: inside or not
            return 1.0 if math.hypot(x1 - cx, y1 - cy) < radius else 0.0

        # Project circle center onto the segment line (parametric t)
        fx, fy = x1 - cx, y1 - cy
        a = dx * dx + dy * dy
        b = 2 * (fx * dx + fy * dy)
        c = fx * fx + fy * fy - radius * radius
        disc = b * b - 4 * a * c
        if disc <= 0:
            return 0.0
        sqrt_disc = math.sqrt(disc)
        t1 = max(0.0, (-b - sqrt_disc) / (2 * a))
        t2 = min(1.0, (-b + sqrt_disc) / (2 * a))
        if t2 <= t1:
            return 0.0
        return (t2 - t1) * seg_len

    def _apply_mine_damage(self, fleet: 'Fleet', stats: dict) -> int:
        """
        Spread the mine damage model over a fleet's tokens.

        Shared by minefield strikes and SD detonations: total damage is
        max(min_fleet_damage, damage_per_ship x ships), spread evenly
        per ship; each 100% of a token's armor kills one ship.

        Returns:
            Number of ships destroyed.
        """
        ships = sum(t.quantity for t in fleet.tokens.values())

        ships_lost = 0
        if stats["damage_per_ship"] > 0 and ships > 0:
            total_damage = max(stats["min_fleet_damage"],
                               stats["damage_per_ship"] * ships)
            per_ship = total_damage / ships
            for token in list(fleet.tokens.values()):
                armor = max(1, token.armor)
                token.damage_percent += per_ship / armor * 100
                while token.damage_percent >= 100 and token.quantity > 0:
                    token.quantity -= 1
                    ships_lost += 1
                    token.damage_percent -= 100
                if token.quantity <= 0:
                    del fleet.tokens[token.design_key]
        return ships_lost

    def _strike_minefield(self, fleet: 'Fleet', minefield, stats: dict):
        """
        Apply a minefield strike: stop the fleet, damage ships,
        expend detonated mines.
        """
        # Fleet is stopped dead, as in the original (fleet.Speed = 0)
        if fleet.waypoints:
            fleet.waypoints[0].warp_factor = 0

        ships_lost = self._apply_mine_damage(fleet, stats)

        # Detonated mines are expended
        minefield.number_of_mines = max(0, minefield.number_of_mines - 10)
        if minefield.number_of_mines <= 10:
            self.server_state.all_minefields.pop(minefield.key, None)

        descriptor = minefield.mine_descriptor
        if stats["damage_per_ship"] == 0:
            text = (f"{fleet.name} has been caught in a {descriptor} "
                    f"minefield and is stopped dead in space!")
        elif ships_lost > 0:
            text = (f"{fleet.name} has struck a {descriptor} minefield! "
                    f"{ships_lost} ship(s) were destroyed.")
        else:
            text = (f"{fleet.name} has struck a {descriptor} minefield "
                    f"and taken damage!")
        self.server_state.all_messages.append(Message(
            audience=fleet.owner, text=text,
            message_type="Minefield Hit", fleet_key=fleet.key
        ))
        if minefield.owner != NOBODY:
            self.server_state.all_messages.append(Message(
                audience=minefield.owner,
                text=f"An enemy fleet has struck our {descriptor} "
                     f"minefield at ({int(minefield.position_x)}, "
                     f"{int(minefield.position_y)})!",
                message_type="Minefield Hit", fleet_key=fleet.key
            ))

    def _detonate_minefields(self):
        """
        Detonate SD minefields flagged to detonate.

        C# has no detonation code - the SD trait text is
        PrimaryTraits.cs:58 ("you have the ability to remotely detonate
        your own standard mine fields"); canonical Stars! rules per
        project directive: standard fields only, a per-field yearly
        toggle; while set, the field detonates each year damaging EVERY
        fleet inside its radius - friend and foe, including the owner's
        own ships - using the standard-mine damage model. Runs right
        after fleet movement (fleets that just moved through are hit)
        and before battles, per the canonical order of events. Unlike a
        strike, detonation does not stop fleets.
        """
        for minefield in list(self.server_state.all_minefields.values()):
            if not minefield.detonate or minefield.mine_type != 0:
                continue

            stats = self.MINE_STATS[0]
            descriptor = minefield.mine_descriptor
            caught_enemy = False
            # The field detonates as a whole: containment uses the
            # radius at detonation time, not the radius shrinking as
            # mines are expended per fleet below
            radius = minefield.radius

            for fleet in list(self.server_state.iterate_all_fleets()):
                if is_mineral_packet(fleet):
                    continue
                distance = math.hypot(
                    fleet.position.x - minefield.position_x,
                    fleet.position.y - minefield.position_y)
                if distance > radius:
                    continue

                ships_lost = self._apply_mine_damage(fleet, stats)
                # Detonated mines are expended per fleet damaged, as
                # in a strike
                minefield.number_of_mines = max(
                    0, minefield.number_of_mines - 10)
                if fleet.owner != minefield.owner:
                    caught_enemy = True

                if ships_lost > 0:
                    text = (f"{fleet.name} has been caught in a "
                            f"detonating {descriptor} minefield! "
                            f"{ships_lost} ship(s) were destroyed.")
                else:
                    text = (f"{fleet.name} has been caught in a "
                            f"detonating {descriptor} minefield and "
                            f"taken damage!")
                self.server_state.all_messages.append(Message(
                    audience=fleet.owner, text=text,
                    message_type="Minefield Detonation",
                    fleet_key=fleet.key
                ))

            if caught_enemy and minefield.owner != NOBODY:
                self.server_state.all_messages.append(Message(
                    audience=minefield.owner,
                    text=f"Enemy fleets have been caught in our "
                         f"detonating {descriptor} minefield at "
                         f"({int(minefield.position_x)}, "
                         f"{int(minefield.position_y)})!",
                    message_type="Minefield Detonation"
                ))

            if minefield.number_of_mines <= 10:
                self.server_state.all_minefields.pop(minefield.key, None)

    def _sweep_minefields(self):
        """
        Beam-armed fleets automatically sweep enemy minefields.

        C# has no sweeping code (no .cs file mentions it); canonical
        Stars! rules per project directive: fleets sweep only fields
        of empires the SWEEPING player has declared Enemy, no order
        needed, while inside of or orbiting within the field; mines
        swept per year = sum over beam weapons of
        (weapon power x range^2); gatling-type weapons sweep as if
        range 16 (power x 256) regardless of actual range; torpedoes
        and missiles sweep nothing. Runs near the end of the turn,
        after battles and bombing, per the canonical order of events.
        """
        for fleet in list(self.server_state.iterate_all_fleets()):
            if is_mineral_packet(fleet):
                continue

            empire = self.server_state.all_empires.get(fleet.owner)
            if empire is None:
                continue

            capacity = 0
            for token in fleet.tokens.values():
                design = empire.designs.get(token.design_key)
                if design is None:
                    continue
                # Mirror battle_engine.py stack setup: refresh stale
                # aggregates; SimpleDesign has no _needs_update and its
                # weapons list is static
                if getattr(design, '_needs_update', False):
                    design.update()
                for weapon in design.weapons:
                    if not weapon.is_beam:
                        continue
                    # Weapon.power is already multiplied by the slot's
                    # component count (ship_design.py _sum_property)
                    sweep_range = 16 if weapon.group == "gatlingGun" \
                        else weapon.range
                    capacity += (weapon.power * sweep_range * sweep_range
                                 * token.quantity)

            if capacity <= 0:
                continue

            for minefield in list(self.server_state.all_minefields.values()):
                if minefield.owner == fleet.owner:
                    continue
                # Canonical Stars!: only fields of empires the SWEEPER
                # has declared Enemy are swept (sweeper-side relation;
                # sweeping is absent from the C# reference). Default
                # relation is Enemy, so pre-relations behavior holds.
                if empire.empire_reports.get(
                        minefield.owner, {}).get("relation", "Enemy") \
                        != "Enemy":
                    continue
                distance = math.hypot(
                    fleet.position.x - minefield.position_x,
                    fleet.position.y - minefield.position_y)
                if distance > minefield.radius:
                    continue

                swept = min(minefield.number_of_mines, capacity)
                if swept <= 0:
                    continue
                minefield.number_of_mines -= swept

                descriptor = minefield.mine_descriptor
                self.server_state.all_messages.append(Message(
                    audience=fleet.owner,
                    text=f"{fleet.name} has swept {swept} mines from "
                         f"a {descriptor} minefield.",
                    message_type="Minefield Swept", fleet_key=fleet.key
                ))
                if minefield.owner != NOBODY:
                    self.server_state.all_messages.append(Message(
                        audience=minefield.owner,
                        text=f"An enemy fleet has swept {swept} mines "
                             f"from our {descriptor} minefield at "
                             f"({int(minefield.position_x)}, "
                             f"{int(minefield.position_y)})!",
                        message_type="Minefield Swept",
                        fleet_key=fleet.key
                    ))

                if minefield.number_of_mines <= 10:
                    self.server_state.all_minefields.pop(
                        minefield.key, None)

    def _run_battle_engine(self):
        """Run standard battle engine."""
        from .battle.battle_engine import BattleEngine
        self._execute_battles(BattleEngine)

    def _run_ron_battle_engine(self):
        """Run Ron's battle engine variant."""
        from .battle.ron_battle_engine import RonBattleEngine
        self._execute_battles(RonBattleEngine)

    def _execute_battles(self, engine_cls):
        """Run a battle engine and distribute reports and messages."""
        battle_reports = []
        try:
            engine = engine_cls(self.server_state, battle_reports)
            engine.run()
        except Exception:
            logger.exception("Battle engine failed")
            return

        announced = set()
        for battle in battle_reports:
            participants = set()
            for stack in battle.stacks.values():
                participants.add(stack.key >> 32)

            for empire_id in participants:
                empire = self.server_state.all_empires.get(empire_id)
                if empire is None:
                    continue
                empire.battle_reports.append(
                    battle.to_dict() if hasattr(battle, 'to_dict') else {}
                )
                # One message per empire per location per turn
                if (empire_id, battle.location) in announced:
                    continue
                announced.add((empire_id, battle.location))
                # star_name carries the battle location for the client
                # Goto (C# attaches the BattleReport itself as
                # Message.Event, BattleEngine.cs:936-943). The loss
                # summary ports ReportBattle (BattleEngine.cs:945-953);
                # losses is initialized 0 for every participant at
                # _position_stacks, so .get only covers malformed
                # reports.
                losses = battle.losses.get(empire_id, 0)
                if losses == 0:
                    loss_text = "None of your ships were destroyed."
                else:
                    loss_text = f"{losses} of your ships were destroyed."
                self.server_state.all_messages.append(Message(
                    audience=empire_id,
                    text=f"A battle took place at {battle.location}. "
                         f"{loss_text}",
                    message_type="Battle",
                    star_name=battle.location
                ))

    def _victory_check(self):
        """
        Check for a victor against the game's victory settings.

        Full port of ServerState/VictoryCheck.cs (see
        backend/server/victory_check.py), invoked at the C# call site:
        after battles and fleet cleanup, before the year increment
        (TurnGenerator.cs:131-133).
        """
        if not self.server_state.all_stars:
            return
        scores = Scores(self.server_state)
        VictoryCheck(self.server_state, scores).victor()

    def _record_score_history(self):
        """
        Append this turn's ScoreRecord to each empire's score history.

        Snapshot timing mirrors IntelWriter.cs:79-89, which fills
        Intel.AllScores at intel-writing time every generated turn
        (never at game creation, when TurnYear == StartingYear). The
        per-year history itself is a web extension (user directive,
        wave 4); C# keeps only the current turn's records.
        """
        for record in Scores(self.server_state).get_scores():
            empire = self.server_state.all_empires.get(record.empire_id)
            if empire is None:
                continue
            empire.score_history.append(
                {**record.to_dict(), "year": self.server_state.turn_year}
            )

    def _move_mineral_packets(self):
        """
        Move mineral packets, decay overflung ones and resolve catch
        or impact on arrival.

        Canonical Stars! mass-driver rules - the C# reference is a
        stub: MassDriver.cs holds only the component property and
        TurnGenerator.cs (505 lines) has no packet code. The previous
        web remnant here (3/4 population kill, flat 5% erosion) came
        from an older stars-nova revision and is replaced by the
        canonical formulas (constants in globals.py):

          spdPacket = packetWarp^2, spdReceiver = receiverDriver^2
          caught safely when spdReceiver >= spdPacket
          else recovered fraction = pct + (1 - pct) / 3
               with pct = spdReceiver / spdPacket
          rawDamage = (spdPacket - spdReceiver) * kT / 160
          dmg = rawDamage * (1 - defense population coverage)
          colonists killed = max(dmg * pop / 1000, dmg * 100)
          defenses destroyed = max(defs * dmg / 1000, dmg / 20)
          in flight: +1/+2/+3 warp over the flinging driver's rating
          decays 10/25/50 percent per year, minimum 10 kT per mineral
        """
        exploded_packets: List['Fleet'] = []

        for fleet in self.server_state.iterate_all_fleets():
            if not is_mineral_packet(fleet):
                continue

            # Move packet
            self._process_fleet(fleet)
            self.server_state.set_fleet_orbit(fleet)

            if fleet.in_orbit is not None:
                self._resolve_packet_arrival(fleet, fleet.in_orbit)
                exploded_packets.append(fleet)
            else:
                # In-flight decay for overflung packets; packets at or
                # below the driver's rating fly forever undiminished
                over = min(
                    max(fleet.packet_warp - fleet.packet_safe_warp, 0),
                    PACKET_OVERFLING_MAX)
                if over > 0:
                    rate = PACKET_DECAY_RATES[over]
                    for mineral in ("ironium", "boranium", "germanium"):
                        kt = getattr(fleet.cargo, mineral)
                        if kt <= 0:
                            continue
                        decay = min(kt, max(int(kt * rate),
                                            PACKET_MIN_DECAY))
                        setattr(fleet.cargo, mineral, kt - decay)
                    if fleet.cargo.mass == 0:
                        self.server_state.all_messages.append(Message(
                            audience=fleet.owner,
                            text=f"{fleet.name} has decayed to nothing.",
                            message_type="Star", fleet_key=fleet.key))
                        exploded_packets.append(fleet)

            # Update fleet report
            empire = self.server_state.all_empires.get(fleet.owner)
            if empire is not None and fleet.key in empire.fleet_reports:
                empire.fleet_reports[fleet.key] = {
                    "key": fleet.key,
                    "name": fleet.name,
                    "position_x": fleet.position.x,
                    "position_y": fleet.position.y,
                    "year": self.server_state.turn_year
                }

        # Remove exploded packets
        for packet in exploded_packets:
            for empire in self.server_state.all_empires.values():
                if packet.key in empire.fleet_reports:
                    del empire.fleet_reports[packet.key]

            empire = self.server_state.all_empires.get(packet.owner)
            if empire is not None and packet.key in empire.owned_fleets:
                del empire.owned_fleets[packet.key]

    def _resolve_packet_arrival(self, fleet: 'Fleet', star):
        """
        Catch or impact of a mineral packet at its destination star.

        Canonical Stars! packet formulas (C# absent) - see
        _move_mineral_packets for the formula block.
        """
        # Receiving driver rating: the star owner's starbase, if any
        rating = 0
        if star.owner != NOBODY and star.starbase_key:
            owner_empire = self.server_state.all_empires.get(star.owner)
            starbase = owner_empire.owned_fleets.get(star.starbase_key) \
                if owner_empire is not None else None
            rating = starbase.mass_driver if starbase is not None else 0

        # Remnant-era packets carry no packet_warp - fall back to the
        # ordered waypoint warp
        packet_warp = fleet.packet_warp
        if packet_warp <= 0 and fleet.waypoints:
            packet_warp = fleet.waypoints[0].warp_factor
        spd_packet = packet_warp * packet_warp
        spd_receiver = rating * rating
        total_kt = (fleet.cargo.ironium + fleet.cargo.boranium
                    + fleet.cargo.germanium)

        if spd_packet <= 0 or spd_receiver >= spd_packet:
            # Caught safely - every kT lands on the surface
            star.add_cargo(Cargo(ironium=fleet.cargo.ironium,
                                 boranium=fleet.cargo.boranium,
                                 germanium=fleet.cargo.germanium))
            self.server_state.all_messages.append(Message(
                audience=fleet.owner,
                text=f"The mass driver at {star.name} has caught your "
                     f"{total_kt} kT mineral packet.",
                message_type="Star", fleet_key=fleet.key,
                star_name=star.name))
            if star.owner != NOBODY:
                self.server_state.all_messages.append(Message(
                    audience=star.owner,
                    text=f"Your mass driver at {star.name} has caught "
                         f"a {total_kt} kT mineral packet.",
                    message_type="Star", star_name=star.name))
            return

        # Impact: part is caught, a third of the rest is recovered
        caught_pct = spd_receiver / spd_packet
        recovered_fraction = caught_pct + \
            (1.0 - caught_pct) * PACKET_UNCAUGHT_RECOVERY
        recovered = Cargo(
            ironium=int(fleet.cargo.ironium * recovered_fraction),
            boranium=int(fleet.cargo.boranium * recovered_fraction),
            germanium=int(fleet.cargo.germanium * recovered_fraction))
        star.add_cargo(recovered)

        if star.owner == NOBODY or star.colonists <= 0:
            # Uninhabited target: recovery only, no damage
            self.server_state.all_messages.append(Message(
                audience=fleet.owner,
                text=f"Your {total_kt} kT mineral packet has crashed "
                     f"on uninhabited {star.name}; {recovered.mass} kT "
                     f"of minerals were recovered on the surface.",
                message_type="Star", fleet_key=fleet.key,
                star_name=star.name))
            return

        raw_damage = (spd_packet - spd_receiver) * total_kt \
            / PACKET_DAMAGE_DIVISOR
        coverage = compute_defense_coverage(star)["population"]
        dmg = raw_damage * (1.0 - coverage)

        killed = min(star.colonists,
                     int(round(max(dmg * star.colonists / 1000.0,
                                   dmg * 100.0) / 100.0)) * 100)
        star.colonists -= killed
        destroyed = min(star.defenses,
                        int(max(star.defenses * dmg / 1000.0,
                                dmg / 20.0)))
        star.defenses -= destroyed

        self.server_state.all_messages.append(Message(
            audience=fleet.owner,
            text=f"Your {total_kt} kT mineral packet has struck "
                 f"{star.name}, killing {killed} colonists and "
                 f"destroying {destroyed} defenses.",
            message_type="Star", fleet_key=fleet.key,
            star_name=star.name))
        self.server_state.all_messages.append(Message(
            audience=star.owner,
            text=f"A {total_kt} kT mineral packet has struck "
                 f"{star.name}! {killed} colonists were killed and "
                 f"{destroyed} defenses destroyed; {recovered.mass} kT "
                 f"of minerals were recovered on the surface.",
            message_type="Star", star_name=star.name))

    def _update_wormhole_visibility(self):
        """
        Discover wormholes that come within scanner range.

        Once discovered, a wormhole stays on the empire's charts
        (endpoint positions still drift).
        """
        wormholes = self.server_state.all_wormholes
        if not wormholes:
            return

        for empire in self.server_state.all_empires.values():
            known = getattr(empire, 'known_wormholes', None)
            if known is None:
                known = set()
                empire.known_wormholes = known

            scanners = []
            for fleet in empire.owned_fleets.values():
                scan = max((getattr(t, 'scan_range_normal', 0)
                            for t in fleet.tokens.values()), default=0)
                if scan > 0:
                    scanners.append((fleet.position.x, fleet.position.y,
                                     scan))
            for star in empire.owned_stars.values():
                scan = getattr(star, 'scan_range', 0)
                if scan > 0:
                    scanners.append((star.position.x, star.position.y,
                                     scan))

            for wormhole in wormholes.values():
                if wormhole.key in known:
                    continue
                for _, _, wx, wy in wormhole.endpoints():
                    if any(math.hypot(wx - sx, wy - sy) <= srange
                           for sx, sy, srange in scanners):
                        known.add(wormhole.key)
                        self.server_state.all_messages.append(Message(
                            audience=empire.id,
                            text=f"Our scanners have discovered "
                                 f"{wormhole.name}!",
                            message_type="Wormhole"))
                        break

    def _update_minefield_visibility(self):
        """Update which minefields are visible to each empire."""
        for empire in self.server_state.all_empires.values():
            empire.visible_minefields = {}

            # Own minefields are always visible
            for minefield in self.server_state.all_minefields.values():
                if minefield.owner == empire.id:
                    empire.visible_minefields[minefield.key] = minefield

            # Minefields within scan range
            for fleet in empire.owned_fleets.values():
                scan_range = 0
                for token in fleet.tokens.values():
                    # Use cached scan_range_normal from ShipToken
                    token_scan = getattr(token, 'scan_range_normal', 0)
                    scan_range = max(scan_range, token_scan)

                for minefield in self.server_state.all_minefields.values():
                    dx = fleet.position.x - minefield.position_x
                    dy = fleet.position.y - minefield.position_y
                    distance = math.sqrt(dx * dx + dy * dy)

                    if distance <= scan_range + minefield.radius:
                        empire.visible_minefields[minefield.key] = minefield

            # Minefields within planetary scan range
            for star in empire.owned_stars.values():
                scan_range = getattr(star, 'scan_range', 0)

                for minefield in self.server_state.all_minefields.values():
                    dx = star.position.x - minefield.position_x
                    dy = star.position.y - minefield.position_y
                    distance = math.sqrt(dx * dx + dy * dy)

                    if distance <= scan_range + minefield.radius:
                        empire.visible_minefields[minefield.key] = minefield
