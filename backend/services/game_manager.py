"""
Stars Nova Web - Game Manager

Central service for game lifecycle management.
"""

import json
import logging
from typing import Dict, List, Optional, Any

from ..persistence.database import Database, get_database
from ..persistence.game_repository import GameRepository
from ..server.server_data import ServerData
from ..server.turn_generator import TurnGenerator
from ..core.data_structures.empire_data import EmpireData
from ..core.data_structures.tech_level import RESEARCH_KEYS
from ..core.game_objects.star import Star
from ..core.game_objects.fleet import Fleet
from ..core.race.race import Race
from ..core.commands.base import Command, Message
from ..core.commands.waypoint import WaypointCommand
from ..core.commands.design import DesignCommand
from ..core.commands.production import ProductionCommand
from ..core.commands.research import ResearchCommand
from ..core.globals import NOBODY, NEBULA_SCAN_PENALTY
from .galaxy_generator import GalaxyGenerator
from .ship_specs import design_from_dict

logger = logging.getLogger(__name__)


# Maps submitted command_type strings to Command classes
COMMAND_TYPES = {
    "waypoint": WaypointCommand,
    "design": DesignCommand,
    "production": ProductionCommand,
    "research": ResearchCommand,
}


def _race_from_wizard(data: dict) -> Race:
    """
    Build a Race from the race wizard's payload.

    Wizard fields map onto the Race dataclass (RaceDefinition/Race.cs);
    per-field research cost multipliers are not yet modelled.
    """
    race = Race(
        name=data.get("name") or "Custom",
        growth_rate=float(data.get("growthRate", 15)),
        colonists_per_resource=int(data.get("colonistsPerResource", 1000)),
        operable_factories=int(data.get("factoryNumberPer10k", 10)),
        factory_production=int(data.get("factoryEfficiency", 10)),
        factory_cost=int(data.get("factoryCost", 10)),
        operable_mines=int(data.get("mineNumberPer10k", 10)),
        mine_production_rate=int(data.get("mineEfficiency", 10)),
        mine_cost=int(data.get("mineCost", 5)),
        gravity_min=0 if data.get("immuneGravity")
        else int(data.get("gravityMin", 15)),
        gravity_max=100 if data.get("immuneGravity")
        else int(data.get("gravityMax", 85)),
        temperature_min=0 if data.get("immuneTemperature")
        else int(data.get("temperatureMin", 15)),
        temperature_max=100 if data.get("immuneTemperature")
        else int(data.get("temperatureMax", 85)),
        radiation_min=0 if data.get("immuneRadiation")
        else int(data.get("radiationMin", 15)),
        radiation_max=100 if data.get("immuneRadiation")
        else int(data.get("radiationMax", 85)),
        primary_trait=data.get("prt", "JOAT"),
        traits=set(data.get("lrts") or []),
    )
    race.plural_name = data.get("pluralName") or race.name
    race.icon = data.get("icon") or "humanoid"
    return race


def _copy_token(token, quantity: int):
    """Copy a ShipToken for a split, moving armor/shield pools
    proportionally with the ships that leave."""
    import copy
    moved = copy.copy(token)
    fraction = quantity / token.quantity if token.quantity else 0
    moved.quantity = quantity
    moved.armor = int(token.armor * fraction)
    moved.shields = int(token.shields * fraction)
    return moved


class GameManager:
    """
    Central service for game lifecycle management.

    Handles game creation, loading, saving, turn generation,
    and command processing.
    """

    def __init__(self, db_path: str = "stars_nova.db"):
        """
        Initialize game manager.

        Args:
            db_path: Path to SQLite database.
        """
        self.db = get_database(db_path)
        self.repository = GameRepository(self.db)

        # In-memory cache of loaded games
        self._game_cache: Dict[str, ServerData] = {}

        # Last turn's messages per game (survives until next turn)
        self._last_messages: Dict[str, List[Message]] = {}

        # Component catalog must be available so persisted custom
        # designs can re-resolve their hull module allocations
        try:
            from .design_builder import ensure_components_loaded
            ensure_components_loaded()
        except Exception:
            logger.exception("Component catalog failed to load")

    # =========================================================================
    # Game Lifecycle
    # =========================================================================

    def create_game(
        self,
        name: str,
        player_count: int = 2,
        universe_size: str = "medium",
        seed: Optional[int] = None,
        race: Optional[dict] = None
    ) -> dict:
        """
        Create a new game.

        Args:
            name: Game name.
            player_count: Number of players.
            universe_size: Universe size (tiny/small/medium/large/huge).
            seed: Random seed for galaxy generation.
            race: Optional custom race definition from the race wizard
                (used for the human player, empire 1).

        Returns:
            Game metadata dict.
        """
        # Create game record
        game_record = self.repository.create_game(name, player_count, universe_size)
        game_id = game_record["id"]

        # Generate galaxy
        generator = GalaxyGenerator(seed)
        player_race = _race_from_wizard(race) if race else None
        server_data = generator.generate(player_count, universe_size,
                                         player_race=player_race)

        # Initial scan so empires start with intel about their surroundings
        TurnGenerator(server_data).assemble_empire_data()
        server_data.all_messages.clear()

        # Save game state
        self._save_game_state(game_id, server_data)

        # Update status to active
        self.repository.update_game(game_id, status="active")

        # Cache the game
        self._game_cache[game_id] = server_data

        return {
            **game_record,
            "status": "active",
            "turn": server_data.turn_year,
        }

    def get_game(self, game_id: str) -> Optional[dict]:
        """
        Get game metadata.

        Args:
            game_id: Game identifier.

        Returns:
            Game metadata or None.
        """
        game_record = self.repository.get_game(game_id)
        if not game_record:
            return None

        # Get turn year from state
        server_data = self._load_game_state(game_id)
        if server_data:
            game_record["turn"] = server_data.turn_year
        else:
            game_record["turn"] = 0

        return game_record

    def list_games(self) -> List[dict]:
        """
        List all games.

        Returns:
            List of game metadata dicts.
        """
        games = self.repository.list_games()

        # Add turn info from cached states
        for game in games:
            if game["id"] in self._game_cache:
                game["turn"] = self._game_cache[game["id"]].turn_year
            else:
                # Check persisted state
                state_dict = self.repository.load_game_state(game["id"])
                if state_dict:
                    game["turn"] = state_dict.get("turn_year", 0)
                else:
                    game["turn"] = 0

        return games

    def delete_game(self, game_id: str) -> bool:
        """
        Delete a game.

        Args:
            game_id: Game identifier.

        Returns:
            True if deleted.
        """
        # Remove from cache
        if game_id in self._game_cache:
            del self._game_cache[game_id]
        self._last_messages.pop(game_id, None)

        return self.repository.delete_game(game_id)

    # =========================================================================
    # Turn Processing
    # =========================================================================

    def generate_turn(self, game_id: str) -> dict:
        """
        Generate next turn for a game.

        Deserializes queued player commands, runs AI empires, then
        the turn generator, and persists the result.

        Args:
            game_id: Game identifier.

        Returns:
            Turn generation result.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return {"error": "Game not found"}

        # Fresh message list and command stacks for this turn
        server_data.all_messages = []
        server_data.all_commands = {}

        # Player commands were applied at submission time; only AI
        # empires push commands through the turn-time command stacks.
        self._run_ai_empires(server_data)

        # Run turn generator
        turn_generator = TurnGenerator(server_data)
        messages = turn_generator.generate()

        # Keep messages for later retrieval
        self._last_messages[game_id] = list(messages)

        # Save updated state
        self._save_game_state(game_id, server_data)

        return {
            "turn": server_data.turn_year,
            "messages": [m.to_dict() for m in messages],
        }

    def _deserialize_command(self, command_type: str,
                             command_data: dict) -> Optional[Command]:
        """Build a Command object from a stored command record."""
        cls = COMMAND_TYPES.get((command_type or "").strip().lower())
        if cls is None:
            return None
        try:
            command = cls.from_dict(command_data)
        except Exception:
            logger.exception("Failed to deserialize %s command", command_type)
            return None

        # Player-designed ships arrive without engine aggregation;
        # SimpleDesign records are resolved by design_from_dict inside
        # DesignCommand handling below.
        return command

    def _run_ai_empires(self, server_data: ServerData):
        """Run the AI for every computer-controlled empire."""
        from ..ai.default_ai import DefaultAI

        ai_players = {
            p.player_number: p.ai_program
            for p in server_data.all_players
        }

        for empire_id, empire in server_data.all_empires.items():
            program = ai_players.get(empire_id, "Human")
            if program == "Human":
                continue

            try:
                ai = DefaultAI()
                ai.initialize(empire)
                # The AI applies its commands to its own empire state as
                # it generates them; the returned list exists only for
                # the original client-server round trip and must NOT be
                # applied a second time.
                ai.do_move()
            except Exception:
                logger.exception("AI move failed for empire %s", empire_id)
                continue

            # Keep the global star registry in sync with AI changes
            for star in empire.owned_stars.values():
                server_data.all_stars[star.name] = star

    # =========================================================================
    # Game State Access
    # =========================================================================

    def get_stars(self, game_id: str) -> List[dict]:
        """
        Get all stars for a game.

        Args:
            game_id: Game identifier.

        Returns:
            List of star data dicts.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return []

        return [
            self._star_to_dict(star)
            for star in server_data.all_stars.values()
        ]

    def get_star(self, game_id: str, star_name: str) -> Optional[dict]:
        """
        Get specific star.

        Args:
            game_id: Game identifier.
            star_name: Star name.

        Returns:
            Star data or None.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None

        star = server_data.all_stars.get(star_name)
        if not star:
            return None

        return self._star_to_dict(star)

    def get_nebula_field(self, game_id: str) -> Optional[dict]:
        """
        Get nebula density field for a game.

        Args:
            game_id: Game identifier.

        Returns:
            Nebula field data or None.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None

        if not server_data.nebula_field:
            return {"regions": [], "universe_width": 600, "universe_height": 600}

        return server_data.nebula_field.to_dict()

    def get_fleets(self, game_id: str, empire_id: Optional[int] = None) -> List[dict]:
        """
        Get fleets for a game.

        Args:
            game_id: Game identifier.
            empire_id: Optional empire filter.

        Returns:
            List of fleet data dicts.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return []

        fleets = []
        for fleet in server_data.iterate_all_fleets():
            if empire_id is None or fleet.owner == empire_id:
                fleets.append(self._fleet_to_dict(fleet))

        return fleets

    def get_fleet(self, game_id: str, fleet_key: int) -> Optional[dict]:
        """
        Get specific fleet.

        Args:
            game_id: Game identifier.
            fleet_key: Fleet key.

        Returns:
            Fleet data or None.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None

        for fleet in server_data.iterate_all_fleets():
            if fleet.key == fleet_key:
                return self._fleet_to_dict(fleet)

        return None

    def get_empire(self, game_id: str, empire_id: int) -> Optional[dict]:
        """
        Get empire data.

        Args:
            game_id: Game identifier.
            empire_id: Empire ID.

        Returns:
            Empire data or None.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None

        empire = server_data.all_empires.get(empire_id)
        if not empire:
            return None

        return {
            "id": empire_id,
            "race_name": empire.race_name,
            "turn_year": empire.turn_year,
            "star_count": len(empire.owned_stars),
            "fleet_count": len(empire.owned_fleets),
            "design_count": len(empire.designs),
        }

    def get_empires(self, game_id: str) -> List[dict]:
        """
        Get all empires for a game.

        Args:
            game_id: Game identifier.

        Returns:
            List of empire summaries.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return []

        return [
            {
                "id": empire_id,
                "race_name": empire.race_name,
                "turn_year": empire.turn_year,
                "star_count": len(empire.owned_stars),
                "fleet_count": len(empire.owned_fleets),
            }
            for empire_id, empire in server_data.all_empires.items()
        ]

    # =========================================================================
    # Player-Scoped State (fog of war)
    # =========================================================================

    def get_player_state(self, game_id: str, empire_id: int) -> Optional[dict]:
        """
        Get the full game state as seen by one empire.

        Owned objects are reported in full; foreign objects only through
        the empire's intel reports (scan results). This is the primary
        payload the game client renders from.

        Args:
            game_id: Game identifier.
            empire_id: Viewing empire.

        Returns:
            Player-scoped state dict or None.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None

        empire = server_data.all_empires.get(empire_id)
        if empire is None:
            return None

        race = empire.race

        # Stars: own = full detail; known via reports = report detail;
        # everything else = position and classification only.
        stars = []
        for star in server_data.all_stars.values():
            base = {
                "name": star.name,
                "position_x": star.position.x,
                "position_y": star.position.y,
                "spectral_class": star.spectral_class,
                "luminosity_class": star.luminosity_class,
                "star_temperature": star.star_temperature,
                "star_radius": star.star_radius,
            }
            if star.owner == empire_id:
                base.update(self._star_full_view(star, race))
                base["intel"] = "owned"
            else:
                report = empire.star_reports.get(star.name)
                if report and report.get("scan_level") in ("deep_scan", "owned"):
                    base.update({
                        "owner": report.get("owner", 0),
                        "colonists": report.get("colonists", 0),
                        "gravity": report.get("gravity"),
                        "temperature": report.get("temperature"),
                        "radiation": report.get("radiation"),
                        "ironium_concentration": report.get("ironium_concentration"),
                        "boranium_concentration": report.get("boranium_concentration"),
                        "germanium_concentration": report.get("germanium_concentration"),
                        "report_year": report.get("year"),
                    })
                    if race is not None:
                        base["habitability"] = round(race.hab_value(star) * 100)
                    base["intel"] = "scanned"
                else:
                    base["owner"] = 0
                    base["intel"] = "unknown"
            stars.append(base)

        # Fleets: own in full, foreign only via fleet reports
        nebula_field = getattr(server_data, 'nebula_field', None)
        fleets = [
            self._fleet_to_dict(fleet, nebula_field)
            for fleet in empire.owned_fleets.values()
        ]
        foreign_fleets = [
            {
                "key": report.get("key"),
                "name": report.get("name"),
                "owner": report.get("owner"),
                "position_x": report.get("position_x"),
                "position_y": report.get("position_y"),
                "ship_count": report.get("ship_count", 0),
                "report_year": report.get("year"),
                "intel": "scanned",
            }
            for report in empire.fleet_reports.values()
            if (report.get("key", 0) >> 32) != empire_id
        ]

        # Messages from the last generated turn, audience-filtered
        messages = [
            m.to_dict()
            for m in self._last_messages.get(game_id, [])
            if m.audience in (empire_id, NOBODY, -1)
        ]

        # Research state
        research = {
            "budget": empire.research_budget,
            "levels": empire.research_levels.to_dict().get("levels", {}),
            "progress": empire.research_resources.to_dict().get("levels", {}),
            "topics": empire.research_topics.to_dict().get("levels", {}),
            "next_costs": {
                key: int(50 * (1.75 ** (empire.research_levels.levels.get(key, 0) + 1)))
                for key in RESEARCH_KEYS
            },
        }

        # Ship designs
        designs = [
            {
                "key": design.key,
                "name": design.name,
                "hull_name": getattr(design, 'hull_name', '') or (
                    design.blueprint.name
                    if getattr(design, 'blueprint', None) else ''),
                "cost": getattr(design, 'cost').to_dict() if getattr(design, 'cost', None) else {},
                "mass": getattr(design, 'mass', 0),
                "armor": getattr(design, 'armor', 0),
                "shields": getattr(design, 'shields', getattr(design, 'shield', 0)),
                "fuel_capacity": getattr(design, 'fuel_capacity', 0),
                "cargo_capacity": getattr(design, 'cargo_capacity', 0),
                "can_colonize": getattr(design, 'can_colonize', False),
                "is_starbase": getattr(design, 'is_starbase', False),
                "has_weapons": getattr(design, 'has_weapons', False),
                "obsolete": getattr(design, 'obsolete', False),
            }
            for design in empire.designs.values()
        ]

        # Wormholes the empire has discovered
        known_wormholes = getattr(empire, 'known_wormholes', set())
        wormholes = [
            {
                "key": w.key, "name": w.name,
                "x1": w.x1, "y1": w.y1, "x2": w.x2, "y2": w.y2,
                "stability": w.stability,
            }
            for w in getattr(server_data, 'all_wormholes', {}).values()
            if w.key in known_wormholes
        ]

        # Galactic storms are visible to everyone (natural phenomena)
        storms = [
            {
                "key": s.key, "x": s.x, "y": s.y,
                "radius": s.radius, "intensity": s.intensity,
            }
            for s in getattr(server_data, 'all_storms', {}).values()
        ]

        # Minefields the empire knows about
        minefields = [
            {
                "key": mf.key, "owner": mf.owner,
                "x": mf.position_x, "y": mf.position_y,
                "radius": mf.radius,
                "mine_type": mf.mine_type,
                "mine_descriptor": mf.mine_descriptor,
            }
            for mf in getattr(empire, 'visible_minefields', {}).values()
        ]

        return {
            "game_id": game_id,
            "turn_year": server_data.turn_year,
            "victor": getattr(server_data, 'victor', None),
            "empire": {
                "id": empire_id,
                "race_name": empire.race_name,
                "race": race.to_dict() if race else None,
            },
            "stars": stars,
            "fleets": fleets,
            "foreign_fleets": foreign_fleets,
            "messages": messages,
            "research": research,
            "designs": designs,
            "storms": storms,
            "minefields": minefields,
            "wormholes": wormholes,
        }

    def _star_full_view(self, star: Star, race: Optional[Race]) -> dict:
        """Full owner-visible view of a star."""
        view = {
            "owner": star.owner,
            "colonists": star.colonists,
            "factories": star.factories,
            "mines": star.mines,
            "defenses": star.defenses,
            "gravity": star.gravity,
            "temperature": star.temperature,
            "radiation": star.radiation,
            "ironium_concentration": star.ironium_concentration,
            "boranium_concentration": star.boranium_concentration,
            "germanium_concentration": star.germanium_concentration,
            "ironium": star.resources_on_hand.ironium,
            "boranium": star.resources_on_hand.boranium,
            "germanium": star.resources_on_hand.germanium,
            "resources_per_year": star.resources_per_year,
            "scan_range": star.scan_range,
            "scanner_type": star.scanner_type,
            "starbase_key": star.starbase_key,
            "production_queue": [
                order.to_dict() for order in star.manufacturing_queue.orders
            ],
            "only_leftover": star.only_leftover,
        }
        if race is not None:
            view["habitability"] = round(race.hab_value(star) * 100)
            view["max_population"] = star.max_population(race)
            view["operable_factories"] = star.get_operable_factories()
            view["operable_mines"] = star.get_operable_mines()
        return view

    # =========================================================================
    # Command Submission
    # =========================================================================

    def submit_command(
        self,
        game_id: str,
        empire_id: int,
        command_type: str,
        command_data: dict
    ) -> dict:
        """
        Submit a player command.

        Args:
            game_id: Game identifier.
            empire_id: Empire submitting command.
            command_type: Type of command.
            command_data: Command parameters.

        Returns:
            Submission result.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return {"error": "Game not found"}

        empire = server_data.all_empires.get(empire_id)
        if empire is None:
            return {"error": "Empire not found"}

        ctype = (command_type or "").strip().lower()
        if ctype == "design":
            # Design commands need the empire: the design is built and
            # validated server-side from the light client payload
            command = self._build_design_command(empire, command_data)
            if isinstance(command, dict):
                return command  # validation error
        else:
            command = self._deserialize_command(command_type, command_data)
        if command is None:
            return {"error": f"Unknown or malformed command type '{command_type}'"}

        # Orders apply to the player's own state immediately (as in the
        # original client); the turn generator executes their effects.
        valid, message = command.is_valid(empire)
        if not valid:
            if message is None:
                # Benign rejection (e.g. no-change research) - treat as no-op
                return {"turn_year": server_data.turn_year, "status": "unchanged"}
            return {"error": message.text}

        result = command.apply_to_state(empire)
        if result is not None and result.message_type == "Error":
            return {"error": result.text}

        # Keep global star registry in sync with owned-star changes
        for star in empire.owned_stars.values():
            server_data.all_stars[star.name] = star

        self._save_game_state(game_id, server_data)

        return {
            "turn_year": server_data.turn_year,
            "status": "applied"
        }

    def get_battle_reports(self, game_id: str,
                           empire_id: int) -> Optional[List[dict]]:
        """Battle reports the empire witnessed last turn."""
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None
        empire = server_data.all_empires.get(empire_id)
        if empire is None:
            return None
        return list(getattr(empire, 'battle_reports', []))

    def _build_design_command(self, empire, data: dict):
        """
        Build a DesignCommand from a client design payload.

        Add payloads carry {mode:'Add', design:{name, hull, slots}} and
        are aggregated/validated server-side by the design builder.
        Delete/Edit carry {mode, key}. Returns a DesignCommand, or an
        error dict.
        """
        from ..core.commands.base import CommandMode
        from .design_builder import build_ship_design

        mode_str = (data.get("mode") or "Add").strip().lower()
        if mode_str == "add":
            design_data = data.get("design") or {}
            design, error = build_ship_design(
                empire,
                design_data.get("name", ""),
                design_data.get("hull", ""),
                design_data.get("slots") or [],
            )
            if error:
                return {"error": error}
            return DesignCommand(mode=CommandMode.ADD, design=design)

        key = data.get("key", data.get("design_key", 0))
        if isinstance(key, str):
            key = int(key, 16) if key.startswith("0x") else int(key)
        mode = CommandMode.DELETE if mode_str == "delete" else CommandMode.EDIT
        return DesignCommand(mode=mode, design_key=key)

    def split_fleet(self, game_id: str, empire_id: int, fleet_key: int,
                    keep_composition: Dict[int, int]) -> dict:
        """
        Split a fleet: ships not in keep_composition move to a new fleet.

        Ported from SplitMergeTask.cs Perform/MakeNewFleet/ReassignShips:
        the new fleet shares the source's position and orbit, receives
        the moved tokens, and cargo/fuel move only as overflow beyond
        the source's remaining capacity (ReassignCargo, lines 334-417).

        Args:
            keep_composition: {design_key: quantity to KEEP in source}.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return {"error": "Game not found"}
        empire = server_data.all_empires.get(empire_id)
        if empire is None:
            return {"error": "Empire not found"}
        fleet = empire.owned_fleets.get(fleet_key)
        if fleet is None:
            return {"error": "Fleet not found or not owned"}
        if getattr(fleet, 'is_starbase', False):
            return {"error": "Starbases cannot be split"}

        # Validate composition and compute what moves
        moves: Dict[int, int] = {}
        for design_key, token in fleet.tokens.items():
            keep = keep_composition.get(design_key, token.quantity)
            if keep < 0 or keep > token.quantity:
                return {"error": f"Invalid quantity for {token.design_name}"}
            if token.quantity - keep > 0:
                moves[design_key] = token.quantity - keep

        if not moves:
            return {"error": "Nothing to split off"}
        if all(keep_composition.get(k, t.quantity) == 0
               for k, t in fleet.tokens.items()):
            return {"error": "Cannot move every ship out of the fleet"}

        # New fleet at the same location (MakeNewFleet)
        new_fleet = Fleet(
            name="", position=fleet.position.copy()
        )
        new_fleet.key = empire.get_next_fleet_key()
        new_fleet.name = f"New Fleet #{new_fleet.key & 0xFFFFFFFF}"
        new_fleet.in_orbit_name = fleet.in_orbit_name
        new_fleet.in_orbit = fleet.in_orbit
        new_fleet.battle_plan = fleet.battle_plan
        new_fleet.turn_year = fleet.turn_year

        # Move tokens (ReassignShips); armor is a per-token pool, so it
        # moves proportionally with quantity
        for design_key, qty in moves.items():
            token = fleet.tokens[design_key]
            moved = _copy_token(token, qty)
            new_fleet.tokens[design_key] = moved
            token.armor -= moved.armor
            token.shields -= moved.shields
            token.quantity -= qty
            if token.quantity <= 0:
                del fleet.tokens[design_key]

        # Overflow-driven cargo/fuel redistribution (ReassignCargo)
        self._spill_overflow(fleet, new_fleet)

        empire.owned_fleets[new_fleet.key] = new_fleet
        self._save_game_state(game_id, server_data)
        return {
            "status": "applied",
            "new_fleet_key": new_fleet.key,
            "new_fleet_name": new_fleet.name,
        }

    def merge_fleets(self, game_id: str, empire_id: int,
                     fleet_key: int, other_fleet_key: int) -> dict:
        """
        Merge another fleet into this one.

        Ported from SplitMergeTask.cs MergeFleets (lines 208-276):
        tokens combine (quantity and armor pools add), fuel and cargo
        add, and the emptied source fleet is removed.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return {"error": "Game not found"}
        empire = server_data.all_empires.get(empire_id)
        if empire is None:
            return {"error": "Empire not found"}
        target = empire.owned_fleets.get(fleet_key)
        other = empire.owned_fleets.get(other_fleet_key)
        if target is None or other is None:
            return {"error": "Fleet not found or not owned"}
        if target is other:
            return {"error": "Cannot merge a fleet with itself"}
        if getattr(target, 'is_starbase', False) or \
                getattr(other, 'is_starbase', False):
            return {"error": "Starbases cannot be merged"}

        # Fleets must be at the same location
        dx = target.position.x - other.position.x
        dy = target.position.y - other.position.y
        if (dx * dx + dy * dy) > 1.0:
            return {"error": "Fleets must be at the same location to merge"}

        for design_key, token in other.tokens.items():
            existing = target.tokens.get(design_key)
            if existing is None:
                target.tokens[design_key] = token
            else:
                existing.quantity += token.quantity
                existing.armor += token.armor
                existing.shields += token.shields

        target.fuel_available += other.fuel_available
        target.cargo.ironium += other.cargo.ironium
        target.cargo.boranium += other.cargo.boranium
        target.cargo.germanium += other.cargo.germanium
        target.cargo.colonists_in_kilotons += \
            other.cargo.colonists_in_kilotons

        other.tokens.clear()
        del empire.owned_fleets[other_fleet_key]
        empire.fleet_reports.pop(other_fleet_key, None)

        self._save_game_state(game_id, server_data)
        return {"status": "applied", "fleet_key": fleet_key}

    def _spill_overflow(self, from_fleet: Fleet, to_fleet: Fleet):
        """
        Move cargo/fuel that no longer fits after a split.

        Ported from SplitMergeTask.cs ReassignCargo: only the overflow
        beyond the source's remaining capacity moves, mineral by
        mineral, then excess fuel.
        """
        capacity = from_fleet.total_cargo_capacity
        excess = from_fleet.cargo.mass - capacity
        if excess > 0:
            for attr in ("ironium", "boranium", "germanium",
                         "colonists_in_kilotons"):
                if excess <= 0:
                    break
                amount = getattr(from_fleet.cargo, attr)
                move = min(amount, excess)
                setattr(from_fleet.cargo, attr, amount - move)
                setattr(to_fleet.cargo, attr,
                        getattr(to_fleet.cargo, attr) + move)
                excess -= move

        fuel_capacity = from_fleet.total_fuel_capacity
        if from_fleet.fuel_available > fuel_capacity:
            spill = from_fleet.fuel_available - fuel_capacity
            from_fleet.fuel_available = fuel_capacity
            to_fleet.fuel_available += spill
        # The new fleet cannot exceed its own capacity either
        to_cap = to_fleet.total_fuel_capacity
        if to_fleet.fuel_available > to_cap:
            to_fleet.fuel_available = to_cap

    def rename_fleet(self, game_id: str, empire_id: int,
                     fleet_key: int, name: str) -> dict:
        """Rename an owned fleet."""
        server_data = self._load_game_state(game_id)
        if not server_data:
            return {"error": "Game not found"}

        empire = server_data.all_empires.get(empire_id)
        if empire is None:
            return {"error": "Empire not found"}

        fleet = empire.owned_fleets.get(fleet_key)
        if fleet is None:
            return {"error": "Fleet not found or not owned"}

        name = (name or "").strip()
        if not name:
            return {"error": "Name cannot be empty"}

        fleet.name = name
        self._save_game_state(game_id, server_data)
        return {"status": "ok", "name": name}

    def transfer_cargo(
        self,
        game_id: str,
        empire_id: int,
        fleet_key: int,
        cargo_delta: dict
    ) -> dict:
        """
        Transfer cargo between a fleet and the star it orbits.

        Positive values load from star to fleet; negative unload.
        Applied immediately (waypoint-zero semantics, as in the
        original client).

        Args:
            game_id: Game identifier.
            empire_id: Acting empire.
            fleet_key: Fleet to load/unload.
            cargo_delta: {ironium, boranium, germanium, colonists} deltas.
                colonists is in colonist headcount (100 per kT).

        Returns:
            Result with updated cargo, or error.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return {"error": "Game not found"}

        empire = server_data.all_empires.get(empire_id)
        if empire is None:
            return {"error": "Empire not found"}

        fleet = empire.owned_fleets.get(fleet_key)
        if fleet is None:
            return {"error": "Fleet not found or not owned"}

        star = server_data.all_stars.get(fleet.in_orbit_name or "")
        if star is None:
            return {"error": "Fleet is not orbiting a star"}
        if star.owner != empire_id:
            return {"error": "Cannot transfer cargo at a foreign star"}

        d_iron = int(cargo_delta.get("ironium", 0))
        d_bor = int(cargo_delta.get("boranium", 0))
        d_germ = int(cargo_delta.get("germanium", 0))
        d_col = int(cargo_delta.get("colonists", 0))
        d_col_kt = d_col // 100

        # Validate availability on both sides
        if d_iron > star.resources_on_hand.ironium or -d_iron > fleet.cargo.ironium:
            return {"error": "Not enough ironium"}
        if d_bor > star.resources_on_hand.boranium or -d_bor > fleet.cargo.boranium:
            return {"error": "Not enough boranium"}
        if d_germ > star.resources_on_hand.germanium or -d_germ > fleet.cargo.germanium:
            return {"error": "Not enough germanium"}
        if d_col > star.colonists or -d_col_kt > fleet.cargo.colonists_in_kilotons:
            return {"error": "Not enough colonists"}

        new_mass = (fleet.cargo.mass + d_iron + d_bor + d_germ + d_col_kt)
        if new_mass > fleet.total_cargo_capacity:
            return {"error": "Cargo capacity exceeded"}

        star.resources_on_hand.ironium -= d_iron
        fleet.cargo.ironium += d_iron
        star.resources_on_hand.boranium -= d_bor
        fleet.cargo.boranium += d_bor
        star.resources_on_hand.germanium -= d_germ
        fleet.cargo.germanium += d_germ
        star.colonists -= d_col_kt * 100
        fleet.cargo.colonists_in_kilotons += d_col_kt

        self._save_game_state(game_id, server_data)

        return {
            "status": "ok",
            "fleet": self._fleet_to_dict(fleet),
            "star": self._star_to_dict(star),
        }

    # =========================================================================
    # Waypoint Management
    # =========================================================================

    def get_fleet_waypoints(self, game_id: str, fleet_key: int) -> List[dict]:
        """
        Get waypoints for a fleet.

        Args:
            game_id: Game identifier.
            fleet_key: Fleet key.

        Returns:
            List of waypoint dicts.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return []

        for fleet in server_data.iterate_all_fleets():
            if fleet.key == fleet_key:
                return [
                    {
                        "position_x": wp.position.x,
                        "position_y": wp.position.y,
                        "warp_factor": wp.warp_factor,
                        "destination": wp.destination or "",
                        "task_type": str(wp.task.__class__.__name__) if wp.task else "NoTask",
                    }
                    for wp in fleet.waypoints
                ]

        return []

    # =========================================================================
    # Internal Methods
    # =========================================================================

    def _load_game_state(self, game_id: str) -> Optional[ServerData]:
        """Load game state from cache or database."""
        # Check cache first
        if game_id in self._game_cache:
            return self._game_cache[game_id]

        # Load from database
        state_dict = self.repository.load_game_state(game_id)
        if not state_dict:
            return None

        # Deserialize
        server_data = self._deserialize_state(state_dict)

        # Restore last messages
        self._last_messages[game_id] = [
            Message.from_dict(m) for m in state_dict.get("last_messages", [])
        ]

        # Cache it
        self._game_cache[game_id] = server_data

        return server_data

    def _save_game_state(self, game_id: str, server_data: ServerData) -> None:
        """Save game state to database."""
        state_dict = self._serialize_state(server_data)
        state_dict["last_messages"] = [
            m.to_dict() for m in self._last_messages.get(game_id, [])
        ]
        self.repository.save_game_state(game_id, state_dict)

        # Update star cache
        stars = [
            {
                "name": star.name,
                "position_x": star.position.x,
                "position_y": star.position.y,
                "owner": star.owner,
                "colonists": star.colonists,
            }
            for star in server_data.all_stars.values()
        ]
        self.repository.save_stars(game_id, stars)

        # Update cache
        self._game_cache[game_id] = server_data

    def _serialize_state(self, server_data: ServerData) -> dict:
        """Serialize ServerData to dict using the engine serializers."""
        state = server_data.to_dict()

        state["all_stars"] = {
            name: star.to_dict()
            for name, star in server_data.all_stars.items()
        }

        state["all_empires"] = {}
        for empire_id, empire in server_data.all_empires.items():
            empire_dict = empire.to_dict()
            empire_dict["race_name"] = empire.race_name
            empire_dict["owned_stars"] = list(empire.owned_stars.keys())
            empire_dict["owned_fleets"] = {
                str(k): f.to_dict() for k, f in empire.owned_fleets.items()
            }
            empire_dict["designs"] = {
                str(k): d.to_dict() for k, d in empire.designs.items()
            }
            empire_dict["star_reports"] = empire.star_reports
            empire_dict["fleet_reports"] = {
                str(k): v for k, v in empire.fleet_reports.items()
            }
            empire_dict["battle_plans"] = {
                name: (plan.to_dict() if hasattr(plan, 'to_dict') else plan)
                for name, plan in empire.battle_plans.items()
            }
            empire_dict["battle_reports"] = list(
                getattr(empire, 'battle_reports', []))
            empire_dict["known_wormholes"] = sorted(
                getattr(empire, 'known_wormholes', set()))
            state["all_empires"][str(empire_id)] = empire_dict

        state["all_races"] = {
            name: race.to_dict()
            for name, race in server_data.all_races.items()
        }

        if server_data.nebula_field is not None:
            state["nebula_field"] = server_data.nebula_field.to_dict()

        return state

    def _deserialize_state(self, state_dict: dict) -> ServerData:
        """Deserialize dict to ServerData, relinking object references."""
        from ..server.server_data import NebulaField

        server_data = ServerData.from_dict(state_dict)

        # Restore races first so they can be relinked
        for name, race_dict in state_dict.get("all_races", {}).items():
            server_data.all_races[name] = Race.from_dict(race_dict)

        # Restore stars
        for name, star_dict in state_dict.get("all_stars", {}).items():
            star = Star.from_dict(star_dict)
            race_name = star_dict.get("this_race_name")
            if race_name and race_name in server_data.all_races:
                star.this_race = server_data.all_races[race_name]
            server_data.all_stars[name] = star

        # Restore empires
        for empire_id_str, empire_dict in state_dict.get("all_empires", {}).items():
            empire_id = int(empire_id_str)
            empire = EmpireData.from_dict(empire_dict)
            empire.race_name = empire_dict.get("race_name", "")
            if empire.race_name in server_data.all_races:
                empire.race = server_data.all_races[empire.race_name]

            for star_name in empire_dict.get("owned_stars", []):
                if star_name in server_data.all_stars:
                    star = server_data.all_stars[star_name]
                    empire.owned_stars[star_name] = star
                    if star.this_race is None:
                        star.this_race = empire.race

            for fleet_dict in empire_dict.get("owned_fleets", {}).values():
                fleet = Fleet.from_dict(fleet_dict)
                empire.owned_fleets[fleet.key] = fleet

            for design_dict in empire_dict.get("designs", {}).values():
                design = design_from_dict(design_dict)
                empire.designs[design.key] = design

            empire.star_reports = dict(empire_dict.get("star_reports", {}))
            empire.fleet_reports = {
                int(k): v
                for k, v in empire_dict.get("fleet_reports", {}).items()
            }
            from ..server.battle.battle_plan import BattlePlan
            empire.battle_plans = {
                name: BattlePlan.from_dict(plan)
                for name, plan in empire_dict.get("battle_plans", {}).items()
            }
            if "Default" not in empire.battle_plans:
                empire.battle_plans["Default"] = BattlePlan(attack="Everyone")

            empire.battle_reports = list(
                empire_dict.get("battle_reports", []))
            empire.known_wormholes = set(
                empire_dict.get("known_wormholes", []))

            server_data.all_empires[empire_id] = empire

        # Restore nebula field
        if "nebula_field" in state_dict:
            server_data.nebula_field = NebulaField.from_dict(
                state_dict["nebula_field"]
            )

        # Relink fleet orbit references
        for fleet in server_data.iterate_all_fleets():
            if fleet.in_orbit_name:
                fleet.in_orbit = server_data.all_stars.get(fleet.in_orbit_name)

        return server_data

    def _star_to_dict(self, star: Star) -> dict:
        """Convert Star to API response dict."""
        return {
            "name": star.name,
            "position_x": star.position.x,
            "position_y": star.position.y,
            "owner": star.owner,
            "colonists": star.colonists,
            "factories": star.factories,
            "mines": star.mines,
            "defenses": star.defenses,
            "gravity": star.gravity,
            "temperature": star.temperature,
            "radiation": star.radiation,
            "ironium_concentration": star.ironium_concentration,
            "boranium_concentration": star.boranium_concentration,
            "germanium_concentration": star.germanium_concentration,
            "ironium": star.resources_on_hand.ironium,
            "boranium": star.resources_on_hand.boranium,
            "germanium": star.resources_on_hand.germanium,
            "resources_per_year": star.resources_per_year,
            "production_queue": [
                order.to_dict() for order in star.manufacturing_queue.orders
            ],
            # Star classification for visual rendering
            "spectral_class": star.spectral_class,
            "luminosity_class": star.luminosity_class,
            "star_temperature": star.star_temperature,
            "star_radius": star.star_radius,
        }

    def _fleet_to_dict(self, fleet: Fleet, nebula_field=None) -> dict:
        """Convert Fleet to API response dict."""
        warp = 0
        if fleet.waypoints:
            warp = fleet.waypoints[0].warp_factor

        # Effective scanner range, dampened by dust nebulae at the
        # fleet's position (mirrors ScanStep)
        scan_range = 0
        for token in fleet.tokens.values():
            scan_range = max(scan_range, getattr(token, 'scan_range_normal', 0))
        in_dust = 0.0
        if nebula_field is not None:
            in_dust = nebula_field.get_dust_density_at(
                fleet.position.x, fleet.position.y
            )
            if in_dust > 0.01:
                scan_range = int(scan_range * (1.0 - NEBULA_SCAN_PENALTY * in_dust))

        return {
            "scan_range": scan_range,
            "in_dust": round(in_dust, 2),
            "key": fleet.key,
            "name": fleet.name,
            "owner": fleet.owner,
            "position_x": fleet.position.x,
            "position_y": fleet.position.y,
            "fuel_available": fleet.fuel_available,
            "fuel_capacity": fleet.total_fuel_capacity,
            "cargo_mass": fleet.cargo.mass,
            "cargo_capacity": fleet.total_cargo_capacity,
            "cargo": {
                "ironium": fleet.cargo.ironium,
                "boranium": fleet.cargo.boranium,
                "germanium": fleet.cargo.germanium,
                "colonists": fleet.cargo.colonist_numbers,
            },
            "in_orbit": fleet.in_orbit_name,
            "is_starbase": fleet.is_starbase,
            "can_colonize": fleet.can_colonize,
            "warp_factor": warp,
            "tokens": [
                {
                    "design_key": token.design_key,
                    "design_name": token.design_name,
                    "quantity": token.quantity,
                    "armor": token.armor,
                    "shields": token.shields,
                    "mass": token.mass,
                }
                for token in fleet.tokens.values()
            ],
            "token_count": len(fleet.tokens),
            "waypoints": [
                {
                    "position_x": wp.position.x,
                    "position_y": wp.position.y,
                    "warp_factor": wp.warp_factor,
                    "destination": wp.destination or "",
                    "task_type": str(wp.task.__class__.__name__) if wp.task else "NoTask",
                }
                for wp in fleet.waypoints
            ],
            "waypoint_count": len(fleet.waypoints),
        }


# Global game manager instance
_game_manager: Optional[GameManager] = None


def get_game_manager(db_path: str = "stars_nova.db") -> GameManager:
    """
    Get or create global game manager instance.

    Args:
        db_path: Path to SQLite database.

    Returns:
        GameManager instance.
    """
    global _game_manager
    if _game_manager is None:
        _game_manager = GameManager(db_path)
    return _game_manager
