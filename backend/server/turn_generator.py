"""
Stars Nova Web - Turn Generator
Ported from ServerState/TurnGenerator.cs (749 lines)

Processes a new turn by reading player orders, applying them,
and generating the new game state.
"""

import random
import math
from typing import List, Dict, Optional, TYPE_CHECKING
from collections import OrderedDict

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
    NOBODY, NEBULA_SPEED_PENALTY, NEBULA_MIN_SPEED_FACTOR,
    STORM_DAMAGE_PER_TURN, STORM_SAFE_WARP, STORM_WARP_RISK_PER_WARP,
    STORM_MISHAP_RISK_CAP, STORM_MISHAP_DAMAGE, STORM_COLONIST_DEATH,
    COLONISTS_PER_KILOTON
)
from ..core.waypoints.waypoint import WaypointTask, get_task_type, Waypoint, NoTaskObj

if TYPE_CHECKING:
    from .server_data import ServerData
    from ..core.game_objects.fleet import Fleet
    from ..core.race.race import Race


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

        # Turn steps ordered by priority
        self.turn_steps: Dict[int, ITurnStep] = OrderedDict()
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

        # Move fleets; minefield check follows each fleet's move, as in
        # the original TurnGenerator.UpdateFleet -> CheckForMinefields.Check
        destroyed_fleets: List['Fleet'] = []
        for fleet in list(self.server_state.iterate_all_fleets()):
            if fleet.name == "Mineral Packet":
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

        # Run turn steps in priority order
        for step in self.turn_steps.values():
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
        # existing fuel message style)
        if fleet.fuel_available == 0 and not fleet.is_starbase:
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

        # Check for Cheap Engines failure
        if race is not None and race.has_trait("CE"):
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
        # original but travel was never implemented; canonical rules)
        if waypoint_zero.warp_factor >= 10:
            if self._gate_travel(fleet, waypoint_zero, empire):
                return False

        # Calculate movement
        available_time = 1.0
        messages = []

        travel_status = self._move_fleet(fleet, available_time, race, messages)
        self.server_state.all_messages.extend(messages)

        if travel_status == "in_transit":
            # Still moving
            new_position = Waypoint(
                position_x=fleet.position.x,
                position_y=fleet.position.y,
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
        Move fleet towards next waypoint.

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
            return "in_transit"

        # Dust nebulae impede travel: sample dust density along this
        # turn's path segment and slow the fleet proportionally
        nebula = getattr(self.server_state, 'nebula_field', None)
        if nebula is not None:
            segment = min(speed * available_time, distance)
            seg_x = fleet.position.x + dx / distance * segment
            seg_y = fleet.position.y + dy / distance * segment
            dust = nebula.get_average_dust_density_along_path(
                fleet.position.x, fleet.position.y, seg_x, seg_y
            )
            if dust > 0.01:
                factor = max(NEBULA_MIN_SPEED_FACTOR,
                             1.0 - NEBULA_SPEED_PENALTY * dust)
                speed *= factor

        # Calculate how far we can travel this turn
        travel_distance = speed * available_time

        if travel_distance >= distance:
            # Arrive at destination
            fleet.position.x = target_x
            fleet.position.y = target_y

            # Consume fuel
            self._consume_fuel(fleet, distance, warp)

            return "arrived"
        else:
            # Partial movement
            ratio = travel_distance / distance
            fleet.position.x += dx * ratio
            fleet.position.y += dy * ratio

            # Consume fuel
            self._consume_fuel(fleet, travel_distance, warp)

            return "in_transit"

    def _consume_fuel(self, fleet: 'Fleet', distance: float, warp: int):
        """
        Calculate and consume fuel for movement.

        Uses each design's engine fuel table when available
        (ShipDesign.fuel_consumption - port of ShipDesign.cs lines
        721-744: (mass + cargo) * table[warp]/100 * warp^2 / 200,
        IFE x0.85). Designs without engine data (starting
        SimpleDesigns) fall back to mass * warp/200 per light year.
        Out of fuel drops the fleet to its free warp speed, as in
        Fleet.cs Move (lines 456-463).
        """
        if warp <= 0 or distance <= 0:
            return

        empire = self.server_state.all_empires.get(fleet.owner)
        designs = empire.designs if empire else {}
        race = empire.race if empire else None

        speed = warp * warp  # ly per year
        years = distance / speed

        # Cargo mass distributed over tokens by cargo capacity,
        # as in Fleet.cs FuelConsumption
        cargo_mass = fleet.cargo.mass
        total_capacity = fleet.total_cargo_capacity

        fuel_per_year = 0.0
        for token in fleet.tokens.values():
            token_cargo = 0.0
            if cargo_mass > 0 and token.cargo_capacity > 0 and total_capacity:
                token_cargo = (cargo_mass * token.cargo_capacity
                               * token.quantity / total_capacity)

            design = designs.get(token.design_key)
            if design is not None and getattr(design, 'engine', None) \
                    is not None:
                per_ship_cargo = token_cargo / max(1, token.quantity)
                fuel_per_year += design.fuel_consumption(
                    warp, race, per_ship_cargo) * token.quantity
            else:
                # Simplified model: mass * warp / 200 per ly at
                # warp^2 ly/year -> mass * warp^3 / 200 per year
                fuel_per_year += ((token.mass * token.quantity + token_cargo)
                                  * (warp ** 3) / 200.0)

        fuel_consumed = int(fuel_per_year * years)
        fleet.fuel_available = max(0, fleet.fuel_available - fuel_consumed)

        if fleet.fuel_available <= 0 and fleet.waypoints:
            free_warp = fleet.free_warp_speed
            if fleet.waypoints[0].warp_factor > free_warp:
                fleet.waypoints[0].warp_factor = free_warp
                self.server_state.all_messages.append(Message(
                    audience=fleet.owner,
                    text=f"{fleet.name} has run out of fuel and dropped "
                         f"to warp {free_warp}.",
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
        Find a stargate at a star: (safe_mass, safe_range) or None.

        The gate lives on the owner's starbase fleet in orbit.
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
                    return (token.gate_mass, token.gate_range)
        return None

    def _gate_travel(self, fleet: 'Fleet', waypoint, empire) -> bool:
        """
        Attempt stargate travel for a warp-10 order.

        Both the origin (orbited star) and the destination star must
        carry a friendly gated starbase. Exceeding the gates' safe
        hull mass or safe range risks losing ships in transit
        (canonical rule; the original never implemented gate travel,
        so limit handling is an approximation).

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

        distance = math.hypot(dest.position.x - fleet.position.x,
                              dest.position.y - fleet.position.y)

        def limit(a: int, b: int) -> float:
            vals = [v for v in (a, b) if v >= 0]  # -1 means unlimited
            return min(vals) if vals else float('inf')

        safe_mass = limit(origin_gate[0], dest_gate[0])
        safe_range = limit(origin_gate[1], dest_gate[1])

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

    def _process_storms(self):
        """
        Drift galactic storms and apply their hazards to fleets inside.

        Web extension - not in original Stars! (user directive
        2026-07-13). Every effect scales with the LOCAL storm intensity
        at the fleet's position (0 at the blob boundary, the storm's
        intensity at the core): hull damage per turn, a warp mishap
        risk for fleets moving above STORM_SAFE_WARP (the
        minefield-strike analogue) and colonist attrition. Ships whose
        damage reaches 100% are destroyed; starbases are immune.
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
            if fleet.name == "Mineral Packet":
                continue

            for storm in storms.values():
                local = storm.get_intensity_at(
                    fleet.position.x, fleet.position.y)
                if local <= 0.0:
                    continue

                ships_lost = self._apply_storm_damage(
                    fleet, STORM_DAMAGE_PER_TURN * local)

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

                self._check_storm_mishap(fleet, local)
                self._apply_storm_attrition(fleet, local)
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

    def _check_storm_mishap(self, fleet: 'Fleet', local: float):
        """
        Warp-risk check for a fleet that moved through a storm.

        Moving above STORM_SAFE_WARP risks a mishap with chance
        STORM_WARP_RISK_PER_WARP per warp above safe, scaled by the
        local intensity and capped at STORM_MISHAP_RISK_CAP, rolled
        once per turn on the seeded RNG. A mishap deals
        STORM_MISHAP_DAMAGE * local extra damage to every token and
        stops the fleet in the storm, waypoint preserved - the
        minefield-strike analogue (user directive 2026-07-13).
        """
        warp = self._fleet_travel_warp.get(fleet.key)
        if warp is None:
            warp = (fleet.waypoints[0].warp_factor
                    if fleet.waypoints else 0)
        speeding = warp - STORM_SAFE_WARP
        if speeding <= 0:
            return

        probability = min(STORM_MISHAP_RISK_CAP,
                          STORM_WARP_RISK_PER_WARP * speeding * local)
        if self.rand.random() >= probability:
            return

        ships_lost = self._apply_storm_damage(
            fleet, STORM_MISHAP_DAMAGE * local)

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

    def _apply_storm_attrition(self, fleet: 'Fleet', local: float):
        """
        Colonists carried through a storm die off, scaled by the local
        intensity (user directive 2026-07-13). Cargo stores colonists
        in kilotons; the loss rounds up so any exposure costs at least
        one kiloton.
        """
        col_kt = fleet.cargo.colonists_in_kilotons
        if col_kt <= 0:
            return

        deaths_kt = min(col_kt, math.ceil(
            col_kt * STORM_COLONIST_DEATH * local))
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
                if fleet.name == "Mineral Packet":
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
            if fleet.name == "Mineral Packet":
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
            import logging
            logging.getLogger(__name__).exception("Battle engine failed")
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
                self.server_state.all_messages.append(Message(
                    audience=empire_id,
                    text=f"A battle took place at {battle.location}",
                    message_type="Battle"
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
        """Move mineral packets after they are created."""
        exploded_packets: List['Fleet'] = []

        for fleet in self.server_state.iterate_all_fleets():
            if "Mineral Packet" not in fleet.name:
                continue

            # Move packet
            self._process_fleet(fleet)
            self.server_state.set_fleet_orbit(fleet)

            if fleet.in_orbit is not None:
                # Packet arrived - destroy population
                star = fleet.in_orbit
                msg1 = Message(
                    audience=fleet.owner,
                    text=f"Your Mineral Packet destroyed 3/4 of the population of {star.name}",
                    message_type="Star",
                    fleet_key=fleet.key
                )
                self.server_state.all_messages.append(msg1)

                if star.owner != NOBODY:
                    msg2 = Message(
                        audience=star.owner,
                        text=f"A Mineral Packet destroyed 3/4 of your population on {star.name}",
                        message_type="Star"
                    )
                    self.server_state.all_messages.append(msg2)

                star.colonists = star.colonists // 4
                exploded_packets.append(fleet)
            else:
                # Erode packet in space (5% loss)
                if hasattr(fleet.cargo, 'scale'):
                    fleet.cargo.scale(0.95)

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
