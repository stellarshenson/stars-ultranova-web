"""
Stars Nova Web - Game Manager

Central service for game lifecycle management.
"""

import base64
import binascii
import hashlib
import json
import logging
import random
from typing import Dict, List, Optional, Any

from ..persistence.database import Database
from ..persistence.game_repository import GameRepository
from ..server.server_data import ServerData, VictorySettings
from ..server.scores import Scores
from ..server.victory_check import VictoryCheck
from ..server.turn_generator import TurnGenerator
from ..core.data_structures.empire_data import EmpireData
from ..core.data_structures.tech_level import RESEARCH_KEYS, ResearchField
from ..core.defenses import compute_defense_coverage
from ..core.research import research_cost
from ..core.game_objects.star import Star
from ..core.game_objects.fleet import Fleet
from ..core.race.race import Race
from ..core.commands.base import Command, Message
from ..core.commands.waypoint import WaypointCommand
from ..core.commands.design import DesignCommand
from ..core.commands.production import ProductionCommand
from ..core.commands.research import ResearchCommand
from ..core.commands.relation import RelationCommand
from ..core.data_structures.cargo import Cargo
from ..core.game_objects.fleet import is_mineral_packet
from ..core.globals import (
    NOBODY, NEBULA_SCAN_PENALTY, PACKET_OVERFLING_MAX, PACKET_MAX_WARP,
    MT_GIFT_THRESHOLD, TURN_PACKAGE_FORMAT, ORDERS_FILE_FORMAT,
    GAME_FILE_FORMAT, CORRESPONDENCE_FILE_VERSION
)
from ..core.waypoints.waypoint import Waypoint, NoTaskObj
from .galaxy_generator import GalaxyGenerator
from .race_points import calculate_advantage_points
from .ship_specs import (
    _free_warp_from_table, design_from_dict, find_design, make_token,
    SimpleDesign
)

logger = logging.getLogger(__name__)


# Maps submitted command_type strings to Command classes
COMMAND_TYPES = {
    "waypoint": WaypointCommand,
    "design": DesignCommand,
    "production": ProductionCommand,
    "research": ResearchCommand,
    "relation": RelationCommand,
}


# Wizard research cost choices -> integer percent (the race designer
# radio buttons, ControlLibrary/ResearchCost.cs:160-176)
_RESEARCH_COST_PERCENTS = {"cheap": 50, "normal": 100, "expensive": 175}


# Custom race icon upload limits (user directive, wave 5: PNG, JPEG or
# SVG up to 128 kB, stored with the race as a base64 data URI)
RACE_ICON_MAX_BYTES = 128 * 1024
RACE_ICON_MIME_TYPES = ("image/png", "image/jpeg", "image/svg+xml")


def _validate_custom_icon(data_uri: str) -> str:
    """
    Validate a custom race icon data URI (user directive, wave 5).

    Accepts only base64 data URIs of type image/png, image/jpeg or
    image/svg+xml whose decoded payload is at most 128 kB. Returns the
    URI unchanged; raises ValueError on a non-image or oversized upload
    (surfaced as HTTP 422 by the race/game API routes).
    """
    header, sep, payload = data_uri.partition(";base64,")
    if not sep or not header.startswith("data:"):
        raise ValueError(
            "Custom race icon must be a base64 image data URI")
    if header[len("data:"):] not in RACE_ICON_MIME_TYPES:
        raise ValueError(
            "Custom race icon must be a PNG, JPEG or SVG image")
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError(
            "Custom race icon is not valid base64 image data")
    if len(decoded) > RACE_ICON_MAX_BYTES:
        raise ValueError(
            "Custom race icon exceeds the 128 kB size limit")
    return data_uri


def calculate_password_hash(password: str) -> str:
    """
    Race password hash.

    Port of Common/PasswordUtility.cs CalculateHash (lines 30-36):
    MD5 over the ASCII bytes of the password, formatted as C#
    BitConverter.ToString does - uppercase hex pairs joined by dashes.
    Non-ASCII characters become '?', matching Encoding.ASCII.GetBytes.
    """
    digest = hashlib.md5(
        password.encode("ascii", errors="replace")).digest()
    return "-".join(f"{b:02X}" for b in digest)


def _race_from_wizard(data: dict) -> Race:
    """
    Build a Race from the race wizard's payload.

    Wizard fields map onto the Race dataclass (RaceDefinition/Race.cs),
    including per-field research cost multipliers and the "start at
    level 3" ExtraTech pseudo-trait.
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
        immune_gravity=bool(data.get("immuneGravity")),
        immune_temperature=bool(data.get("immuneTemperature")),
        immune_radiation=bool(data.get("immuneRadiation")),
        primary_trait=data.get("prt", "JOAT"),
        # The wizard uses "NRSE" for No Ram Scoop Engines; the C#
        # trait code is "NRS" (RaceAdvantagePointCalculator.cs:46)
        traits={"NRS" if t == "NRSE" else t
                for t in (data.get("lrts") or [])},
    )
    race.plural_name = data.get("pluralName") or race.name
    # Optional race password: the wizard sends plaintext, the race
    # stores only the hash (Race.cs:50; PasswordUtility.cs:30-36)
    password = data.get("password") or ""
    race.password = calculate_password_hash(password) if password else ""
    # Standard emblem index (0-15) plus optional uploaded custom icon
    # (validated data URI); rejection raises ValueError -> HTTP 422
    race.icon = int(data.get("icon") or 0)
    custom_icon = data.get("customIcon") or ""
    race.custom_icon = (
        _validate_custom_icon(custom_icon) if custom_icon else "")

    # Per-field research cost percents; wizard keys are lowercase
    # field names with 'cheap'/'normal'/'expensive' values
    wizard_costs = data.get("researchCosts") or {}
    race.research_costs = {
        key: _RESEARCH_COST_PERCENTS.get(
            wizard_costs.get(key.lower(), "normal"), 100)
        for key in RESEARCH_KEYS
    }

    # "All extra cost technologies start at level 3" checkbox maps to
    # the ExtraTech pseudo-trait (RaceDesigner.cs:1824-1827)
    if data.get("startAtLevel3"):
        race.traits.add("ExtraTech")

    # Leftover advantage-point spend (Race.cs:64 LeftoverPointTarget,
    # default "Surface minerals"). The budget itself is computed
    # server-side from the ported RaceAdvantagePointCalculator at game
    # creation (create_game below), as in C# Race.cs:215-221 - any
    # wizard-supplied point total is ignored.
    race.leftover_point_target = data.get(
        "leftoverPointTarget", "Surface minerals")

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
        self.db = Database(db_path)
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
            raise

    # =========================================================================
    # Game Lifecycle
    # =========================================================================

    def create_game(
        self,
        name: str,
        player_count: int = 2,
        universe_size: str = "medium",
        seed: Optional[int] = None,
        race: Optional[dict] = None,
        accelerated_start: bool = False,
        victory: Optional[dict] = None,
        mystery_trader: bool = True,
        human_players: int = 1
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
            accelerated_start: Accelerated BBS play (GameSettings.cs:63).
            victory: Optional victory-settings dict (partial allowed);
                None keeps the C# defaults (GameSettings.cs:49-58).
            mystery_trader: "Mystery Trader" toggle (default on;
                canonical feature, C# has only a TODO).
            human_players: Empires 1..human_players are human-controlled
                (correspondence play); the rest run the default AI.

        Returns:
            Game metadata dict.
        """
        # Validate the custom race against the advantage-point budget
        # BEFORE the game record is created, so an over-budget race
        # leaves no orphan row. This is the web equivalent of the C#
        # race designer's Finish_Click gate (RaceDesigner.cs:1712-1719,
        # "You are not allowed to generate a race file when you have
        # less than zero Advantage Points").
        player_race = _race_from_wizard(race) if race else None
        if player_race is not None:
            points = calculate_advantage_points(player_race)
            if points < 0:
                raise ValueError(
                    f"Race exceeds the advantage point budget by "
                    f"{-points} points")
            # Leftover budget spent on the homeworld, clamped to
            # [0, 50] (Race.cs GetLeftoverAdvantagePoints, lines 215-221)
            player_race.leftover_points = min(50, points)

        # Create game record
        game_record = self.repository.create_game(name, player_count, universe_size)
        game_id = game_record["id"]

        # Generate galaxy
        generator = GalaxyGenerator(seed)
        server_data = generator.generate(player_count, universe_size,
                                         player_race=player_race,
                                         accelerated_start=accelerated_start,
                                         human_players=human_players)

        # Victory condition settings, C# defaults unless overridden
        server_data.victory_settings = (
            VictorySettings.from_dict(victory) if victory
            else VictorySettings())

        # Mystery Trader toggle (default on)
        server_data.mystery_trader_enabled = mystery_trader

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

        # Turn-submission gate (NovaConsole.cs SetPlayerList, line 450:
        # empire null / wrong TurnYear / not TurnSubmitted -> "don't
        # allow the turn to be generated"). Enforced only when the game
        # has 2+ human empires: single-human games keep the one-button
        # flow, matching the C# console's force-generate affordance.
        human_players = [p for p in server_data.all_players
                         if p.ai_program == "Human"]
        if len(human_players) >= 2:
            waiting_on = []
            for player in human_players:
                empire = server_data.all_empires.get(player.player_number)
                if (empire is None
                        or empire.turn_year != server_data.turn_year
                        or not empire.turn_submitted):
                    waiting_on.append(player.race_name)
            if waiting_on:
                return {
                    "error": "Waiting for orders from: "
                             + ", ".join(waiting_on),
                    "waiting_on": waiting_on,
                }

        # Deterministic turn generation (web extension; the original C#
        # server used unseeded Random). When the game was created with a
        # seed, re-seed Python's global random module from
        # (game_seed, turn_year) so every randomness source this turn -
        # TurnGenerator.rand, the battle engines' Random instances (both
        # derive their seeds from the global module) and nova_point's
        # module-level calls - is reproducible: same seed + same
        # submitted commands produce identical state. A fixed integer
        # mix is used instead of hash() so results do not depend on
        # PYTHONHASHSEED.
        if server_data.game_seed is not None:
            random.seed((server_data.game_seed * 1000003
                         + server_data.turn_year) & 0xFFFFFFFF)

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

            # AI empires submit automatically (NovaConsole.cs RunAI,
            # lines 519-556, launches the AI for every non-submitted
            # computer empire; its orders file marks it submitted)
            empire.turn_submitted = True
            empire.last_turn_submitted = server_data.turn_year

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
                owner = server_data.all_empires.get(fleet.owner)
                fleets.append(self._fleet_to_dict(
                    fleet, race=getattr(owner, 'race', None)))

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
                owner = server_data.all_empires.get(fleet.owner)
                return self._fleet_to_dict(
                    fleet, race=getattr(owner, 'race', None))

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
                base.update(self._star_full_view(star, race, empire))
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
            self._fleet_to_dict(fleet, nebula_field, race)
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
                "composition": report.get("composition", []),
                "intel": "scanned",
            }
            for report in empire.fleet_reports.values()
            if (report.get("key", 0) >> 32) != empire_id
        ]

        # Learned enemy designs (hull-only from scanning, full from
        # battles) - the player's earned intel
        enemy_designs = [
            record
            for report in empire.empire_reports.values()
            for record in report.get("designs", {}).values()
        ]

        # Player relations: every opponent's id/race name is known
        # from turn 0 via EmpireReports (GameInitialiser.cs:132-143)
        relations = [
            {
                "id": eid,
                "race_name": rep.get("race_name", ""),
                "relation": rep.get("relation", "Enemy"),
            }
            for eid, rep in empire.empire_reports.items()
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
                key: research_cost(
                    ResearchField(i), empire.race, empire.research_levels,
                    empire.research_levels.levels.get(key, 0) + 1)
                for i, key in enumerate(RESEARCH_KEYS)
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

        # Galactic storms are visible to everyone (natural phenomena);
        # shape_radii carries the blob polygon so the client renders
        # the true boundary (user directive 2026-07-13)
        storms = [
            {
                "key": s.key, "x": s.x, "y": s.y,
                "radius": s.radius, "intensity": s.intensity,
                "shape_radii": list(s.shape_radii),
            }
            for s in getattr(server_data, 'all_storms', {}).values()
        ]

        # Mystery traders are visible to everyone from the moment they
        # spawn, regardless of scanners (universal visibility, user
        # directive). Velocity lets the client draw the projected
        # course; the gift balance is the VIEWER's only - other
        # empires' gifts are never exposed.
        traders = [
            {
                "key": t.key, "name": t.name,
                "x": t.x, "y": t.y, "warp": t.warp,
                "velocity_x": t.velocity_x, "velocity_y": t.velocity_y,
                "gift_total": t.gifts.get(empire_id, {}).get("total", 0),
                "gift_threshold": MT_GIFT_THRESHOLD,
            }
            for t in getattr(server_data, 'all_traders', {}).values()
        ]

        # Minefields the empire knows about
        minefields = [
            {
                "key": mf.key, "owner": mf.owner,
                "x": mf.position_x, "y": mf.position_y,
                "radius": mf.radius,
                "mine_type": mf.mine_type,
                "mine_descriptor": mf.mine_descriptor,
                # The detonation toggle is owner-only intel
                "detonate": mf.detonate if mf.owner == empire_id else False,
            }
            for mf in getattr(empire, 'visible_minefields', {}).values()
        ]

        # Score records are public to all players (Intel.cs:67
        # AllScores carries every empire's record), computed live per
        # IntelWriter.cs:79-89; the per-year history is the web
        # extension stored on each empire
        score_service = Scores(server_data)
        scores = [
            {
                **record.to_dict(),
                "race_name": getattr(
                    server_data.all_empires.get(record.empire_id),
                    'race_name', ''),
            }
            for record in score_service.get_scores()
        ]
        score_history = {
            str(eid): list(getattr(e, 'score_history', []))
            for eid, e in server_data.all_empires.items()
        }
        victory_status = (
            VictoryCheck(server_data, score_service).status(empire_id)
            if server_data.all_stars else None)

        return {
            "game_id": game_id,
            "turn_year": server_data.turn_year,
            "victor": getattr(server_data, 'victor', None),
            "scores": scores,
            "score_history": score_history,
            "victory_status": victory_status,
            "empire": {
                "id": empire_id,
                "race_name": empire.race_name,
                "race": race.to_dict() if race else None,
            },
            "stars": stars,
            "fleets": fleets,
            "foreign_fleets": foreign_fleets,
            "enemy_designs": enemy_designs,
            "relations": relations,
            "battle_plans": {
                name: (plan.to_dict() if hasattr(plan, 'to_dict') else plan)
                for name, plan in empire.battle_plans.items()
            },
            "messages": messages,
            "research": research,
            "designs": designs,
            "storms": storms,
            "traders": traders,
            # Mystery Trader component grants (hidden technology) -
            # the client hides ungranted MT items from the designer
            "mt_components": list(getattr(empire, 'mt_components', [])),
            "minefields": minefields,
            "wormholes": wormholes,
        }

    def _star_full_view(self, star: Star, race: Optional[Race],
                        empire=None) -> dict:
        """Full owner-visible view of a star."""
        # Mass driver rating on the star's starbase (0 = none) for the
        # star panel's fling controls
        mass_driver = 0
        if empire is not None and star.starbase_key:
            starbase = empire.owned_fleets.get(star.starbase_key)
            if starbase is not None:
                mass_driver = starbase.mass_driver
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
            "pen_scan_range": star.pen_scan_range,
            "scanner_type": star.scanner_type,
            "defense_type": star.defense_type,
            # SummaryCoverage percent shown by the original planet
            # detail (PlanetDetail.cs:174-178)
            "defense_coverage": compute_defense_coverage(star)["summary"],
            "starbase_key": star.starbase_key,
            "mass_driver": mass_driver,
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

        locked = self._empire_locked(empire)
        if locked:
            return locked

        ctype = (command_type or "").strip().lower()
        if ctype == "battle_plan":
            # Battle plan CRUD. No C# command exists (the Nova dialog's
            # newPlan/modifyPlan buttons are disabled,
            # BattlePlans.Designer.cs:94,104); plans live per empire
            # keyed by name (EmpireData.cs:91) and fleets reference
            # them by name (Fleet.cs:60). Handled inline like
            # "detonate_minefield" below.
            result = self._apply_battle_plan_command(empire, command_data)
            if "error" in result:
                return result
            self._record_order(empire, ctype, command_data)
            self._save_game_state(game_id, server_data)
            return {
                "turn_year": server_data.turn_year,
                "status": "applied"
            }
        if ctype == "detonate_minefield":
            # SD per-field detonation toggle (canonical Stars! rule;
            # the C# reference only carries the SD trait text,
            # PrimaryTraits.cs:58). Commands' apply_to_state only sees
            # the empire, so the server-wide minefield is toggled
            # inline here, like the "design" special case below.
            minefield = server_data.all_minefields.get(
                command_data.get("key"))
            if minefield is None:
                return {"error": "Minefield not found"}
            if minefield.owner != empire_id:
                return {"error": "Not your minefield"}
            race = empire.race
            if race is None or not race.has_trait("SD"):
                return {"error": "Only Space Demolition races can "
                                 "detonate minefields"}
            if minefield.mine_type != 0:
                return {"error": "Only standard minefields can be "
                                 "detonated"}
            minefield.detonate = bool(command_data.get("detonate", False))
            self._record_order(empire, ctype, command_data)
            self._save_game_state(game_id, server_data)
            return {
                "turn_year": server_data.turn_year,
                "status": "applied"
            }
        if ctype == "fling_packet":
            # Mass-driver packet fling (canonical Stars! rules - the
            # C# reference only defines the driver component property,
            # MassDriver.cs, and has no packet code). Needs the
            # server-wide star registry and fleet creation, which
            # Command.apply_to_state(empire) cannot reach, so it is
            # handled inline like "detonate_minefield" above.
            result = self._apply_fling_packet(
                game_id, server_data, empire, command_data)
            if "error" in result:
                return result
            self._record_order(empire, ctype, command_data)
            self._save_game_state(game_id, server_data)
            return {
                "turn_year": server_data.turn_year,
                "status": "applied",
                "fleet_key": result["fleet_key"]
            }
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

        self._record_order(empire, ctype, command_data)
        self._save_game_state(game_id, server_data)

        return {
            "turn_year": server_data.turn_year,
            "status": "applied"
        }

    def _empire_locked(self, empire) -> Optional[dict]:
        """
        Reject state-changing orders once the empire has submitted.

        Web analog of the C# turn-submitted lock: after WriteOrders
        sets TurnSubmitted (OrderWriter.cs:63-64) the client's turn is
        final until the year advances (TurnGenerator resets the flag).
        """
        if empire.turn_submitted:
            return {"error": f"Orders already submitted for year "
                             f"{empire.turn_year}"}
        return None

    def _record_order(self, empire, command_type: str,
                      command_data: dict) -> None:
        """
        Record an applied command in the empire's per-year orders log.

        Web analog of the client command stack the C# OrderWriter
        serializes into the .orders file (OrderWriter.cs:77-80).
        Recorded at submission - web orders apply immediately, so an
        orders file cannot be reconstructed later.
        """
        empire.orders_log.append({
            "command_type": command_type,
            "command_data": command_data,
        })

    def _record_fleet_op(self, empire, op: str, args: dict) -> None:
        """
        Record a direct fleet operation in the orders log.

        Split/merge/rename/battle-plan/cargo/gift are immediate server
        operations, not Command objects (see each method's C# note);
        they are logged as {"op", "args"} entries so an orders file
        replays the complete turn.
        """
        empire.orders_log.append({"op": op, "args": args})

    def _apply_battle_plan_command(self, empire, data: dict) -> dict:
        """
        Apply a battle_plan command to the empire.

        Payloads: {mode: "set", plan: {...}} adds or replaces a plan;
        {mode: "delete", name: str} removes one (never "Default",
        EmpireData.cs:160 always seeds it) and reassigns fleets that
        referenced it back to "Default" (canonical safety, C# absent).
        """
        from ..server.battle.battle_plan import (
            BattlePlan, Victims, TACTICS, ATTACK_OPTIONS, MAX_BATTLE_PLANS)

        mode = (data.get("mode") or "").strip().lower()
        if mode == "set":
            plan_data = dict(data.get("plan") or {})
            name = (plan_data.get("name") or "").strip()
            if not name:
                return {"error": "Battle plan name cannot be empty"}
            if plan_data.get("tactic", "Maximise Damage") not in TACTICS:
                return {"error": f"Unknown tactic "
                                 f"'{plan_data.get('tactic')}'"}
            if plan_data.get("attack", "Enemies") not in ATTACK_OPTIONS:
                return {"error": f"Unknown attack option "
                                 f"'{plan_data.get('attack')}'"}
            valid_targets = {int(v) for v in Victims}
            for tier in ("primary_target", "secondary_target",
                         "tertiary_target", "quaternary_target",
                         "quinary_target"):
                value = plan_data.get(tier, 0)
                if not isinstance(value, int) or value not in valid_targets:
                    return {"error": f"Invalid {tier} '{value}'"}
            if (name not in empire.battle_plans
                    and len(empire.battle_plans) >= MAX_BATTLE_PLANS):
                return {"error": f"At most {MAX_BATTLE_PLANS} battle "
                                 f"plans per player"}
            plan_data["name"] = name
            empire.battle_plans[name] = BattlePlan.from_dict(plan_data)
            return {"status": "applied"}

        if mode == "delete":
            name = (data.get("name") or "").strip()
            if name == "Default":
                return {"error": "The Default battle plan cannot be "
                                 "deleted"}
            if name not in empire.battle_plans:
                return {"error": f"Unknown battle plan '{name}'"}
            del empire.battle_plans[name]
            for fleet in empire.owned_fleets.values():
                if fleet.battle_plan == name:
                    fleet.battle_plan = "Default"
            return {"status": "applied"}

        return {"error": f"Unknown battle_plan mode '{data.get('mode')}'"}

    def _apply_fling_packet(self, game_id: str, server_data, empire,
                            data: dict) -> dict:
        """
        Fling a mineral packet from a starbase mass driver.

        Canonical Stars! mass-driver rules (C# absent - MassDriver.cs
        only defines the component property). Payload: {star, target,
        warp, ironium, boranium, germanium}. The packet is created as
        a cargo-only pseudo-fleet with one token from a per-empire
        "Mineral Packet" design (the token keeps cleanup_fleets from
        deleting it - the salvage pattern, ron_battle_engine.py); it
        starts flying at the next turn generation, consistent with
        the command model.
        """
        star = empire.owned_stars.get(data.get("star"))
        if star is None:
            return {"error": "Star not found or not owned"}
        starbase = empire.owned_fleets.get(star.starbase_key) \
            if star.starbase_key else None
        if starbase is None:
            return {"error": f"No starbase at {star.name}"}
        rating = starbase.mass_driver
        if rating <= 0:
            return {"error": "No mass driver on the starbase"}

        target = server_data.all_stars.get(data.get("target"))
        if target is None:
            return {"error": "Target star not found"}
        if target.name == star.name:
            return {"error": "Cannot fling a packet at its own star"}

        try:
            warp = int(data.get("warp", rating))
        except (TypeError, ValueError):
            return {"error": "Invalid fling warp"}
        max_warp = min(rating + PACKET_OVERFLING_MAX, PACKET_MAX_WARP)
        if warp < rating or warp > max_warp:
            return {"error": f"Fling warp must be between {rating} "
                             f"and {max_warp}"}

        try:
            amounts = {mineral: int(data.get(mineral, 0))
                       for mineral in ("ironium", "boranium", "germanium")}
        except (TypeError, ValueError):
            return {"error": "Invalid mineral amount"}
        if any(amount < 0 for amount in amounts.values()):
            return {"error": "Mineral amounts cannot be negative"}
        total_kt = sum(amounts.values())
        if total_kt <= 0:
            return {"error": "Packet must carry at least 1 kT of "
                             "minerals"}
        for mineral, amount in amounts.items():
            if amount > getattr(star.resources_on_hand, mineral):
                return {"error": f"Not enough {mineral} on {star.name}"}

        # Take the minerals off the surface
        star.remove_cargo(Cargo(ironium=amounts["ironium"],
                                boranium=amounts["boranium"],
                                germanium=amounts["germanium"]))

        # Per-empire packet pseudo-design (registered once)
        packet_design = find_design(empire, "Mineral Packet")
        if packet_design is None:
            packet_design = SimpleDesign(
                key=empire.get_next_design_key(), name="Mineral Packet",
                hull_name="Mineral Packet", optimal_speed=0)
            empire.designs[packet_design.key] = packet_design

        key = empire.get_next_fleet_key()
        packet = Fleet(name=f"Mineral Packet #{key & 0xFFFFFFFF}",
                       position=star.position.copy())
        packet.key = key
        token = make_token(packet_design, 1)
        packet.tokens[token.design_key] = token
        packet.cargo = Cargo(ironium=amounts["ironium"],
                             boranium=amounts["boranium"],
                             germanium=amounts["germanium"])
        packet.fuel_available = 0
        packet.packet_warp = warp
        packet.packet_safe_warp = rating
        packet.turn_year = server_data.turn_year
        packet.waypoints = [Waypoint(
            position_x=target.position.x, position_y=target.position.y,
            warp_factor=warp, destination=target.name, task=NoTaskObj())]
        empire.add_or_update_fleet(packet)

        # Confirmation lands in the current message pane immediately
        # (turn-time all_messages are wiped at the next generation)
        self._last_messages.setdefault(game_id, []).append(Message(
            audience=empire.id,
            text=f"Your starbase at {star.name} has flung a "
                 f"{total_kt} kT mineral packet at {target.name} "
                 f"(warp {warp}).",
            message_type="Star", star_name=star.name))

        return {"status": "applied", "fleet_key": key}

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
        locked = self._empire_locked(empire)
        if locked:
            return locked

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
        self._record_fleet_op(empire, "split_fleet", {
            "fleet_key": fleet_key,
            "keep_composition": {str(k): v
                                 for k, v in keep_composition.items()},
        })
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
        locked = self._empire_locked(empire)
        if locked:
            return locked
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

        self._record_fleet_op(empire, "merge_fleets", {
            "fleet_key": fleet_key,
            "other_fleet_key": other_fleet_key,
        })
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

        locked = self._empire_locked(empire)
        if locked:
            return locked

        name = (name or "").strip()
        if not name:
            return {"error": "Name cannot be empty"}

        fleet.name = name
        self._record_fleet_op(empire, "rename_fleet", {
            "fleet_key": fleet_key, "name": name,
        })
        self._save_game_state(game_id, server_data)
        return {"status": "ok", "name": name}

    def set_fleet_battle_plan(self, game_id: str, empire_id: int,
                              fleet_key: int, plan_name: str) -> dict:
        """
        Assign a named battle plan to an owned fleet.

        Fleets reference plans by name (Fleet.cs:60, default
        "Default"); the plan must exist in the empire's plan dict
        (EmpireData.cs:91).
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

        locked = self._empire_locked(empire)
        if locked:
            return locked

        plan_name = (plan_name or "").strip()
        if plan_name not in empire.battle_plans:
            return {"error": f"Unknown battle plan '{plan_name}'"}

        fleet.battle_plan = plan_name
        self._record_fleet_op(empire, "set_fleet_battle_plan", {
            "fleet_key": fleet_key, "plan_name": plan_name,
        })
        self._save_game_state(game_id, server_data)
        return {"status": "ok", "battle_plan": plan_name}

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

        locked = self._empire_locked(empire)
        if locked:
            return locked

        star = server_data.all_stars.get(fleet.in_orbit_name or "")
        if star is None:
            return {"error": "Fleet is not orbiting a star"}
        # Canonical Stars!: freighters load remote-mined minerals from
        # (and may drop minerals on) uninhabited worlds; only stars
        # OWNED by another empire refuse cargo transfer
        if star.owner != empire_id and star.owner != NOBODY:
            return {"error": "Cannot transfer cargo at a foreign star"}

        d_iron = int(cargo_delta.get("ironium", 0))
        d_bor = int(cargo_delta.get("boranium", 0))
        d_germ = int(cargo_delta.get("germanium", 0))
        d_col = int(cargo_delta.get("colonists", 0))
        d_col_kt = d_col // 100

        # Colonist transfer at an uninhabited world is colonization or
        # invasion, not cargo transfer
        if star.owner == NOBODY and d_col != 0:
            return {"error": "Cannot transfer colonists at an "
                             "uninhabited star"}

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

        self._record_fleet_op(empire, "transfer_cargo", {
            "fleet_key": fleet_key, "cargo_delta": cargo_delta,
        })
        self._save_game_state(game_id, server_data)

        return {
            "status": "ok",
            "fleet": self._fleet_to_dict(fleet),
            "star": self._star_to_dict(star),
        }

    def transfer_cargo_between_fleets(
        self,
        game_id: str,
        empire_id: int,
        fleet_key: int,
        other_fleet_key: int,
        delta: dict
    ) -> dict:
        """
        Transfer cargo and fuel between two co-located owned fleets.

        In the C# reference this exists only client-side
        (FleetDetail.cs ButtonCargoXfer_Click, lines 766-786, directly
        assigns both fleets' Cargo/FuelAvailable; no command object is
        sent to the server - a known C# incompleteness). The
        server-authoritative web port implements it as an immediate
        server operation, like transfer_cargo. Counterparty rules
        follow FleetDetail.cs fleetsAtLocation (lines 495-503): own
        fleets only, exact same location, no starbases, not self.
        The C# dialog's ReJigValues clamping (CargoTransferDialog.cs:
        58-90) is client-side UX; the server rejects invalid orders
        instead of silently clamping.

        Args:
            game_id: Game identifier.
            empire_id: Acting empire.
            fleet_key: Fleet on the receiving side of positive deltas.
            other_fleet_key: Counterparty fleet.
            delta: {ironium, boranium, germanium, colonists, fuel}.
                Positive moves other -> this fleet; negative reverses.
                colonists is in colonist headcount (100 per kT).

        Returns:
            Result with both updated fleets, or error.
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
        locked = self._empire_locked(empire)
        if locked:
            return locked
        other = empire.owned_fleets.get(other_fleet_key)
        if other is None:
            # Canonical packet interception (Stars! rules, C# absent):
            # any fleet may fly to a mineral packet in flight and load
            # (steal) minerals from it. Every other counterparty stays
            # own-fleet-only.
            for other_empire in server_data.all_empires.values():
                candidate = other_empire.owned_fleets.get(other_fleet_key)
                if candidate is not None and is_mineral_packet(candidate):
                    other = candidate
                    break
            if other is None:
                return {"error": "Fleet not found or not owned"}
        other_is_packet = is_mineral_packet(other)
        if fleet is other:
            return {"error": "Cannot transfer cargo with the same fleet"}
        if getattr(fleet, 'is_starbase', False) or \
                getattr(other, 'is_starbase', False):
            return {"error": "Starbases cannot transfer cargo"}

        # Fleets must be at the same location (merge tolerance)
        dx = fleet.position.x - other.position.x
        dy = fleet.position.y - other.position.y
        if (dx * dx + dy * dy) > 1.0:
            return {"error": "Fleets must be at the same location "
                             "to transfer cargo"}

        d_iron = int(delta.get("ironium", 0))
        d_bor = int(delta.get("boranium", 0))
        d_germ = int(delta.get("germanium", 0))
        d_col = int(delta.get("colonists", 0))
        d_col_kt = d_col // 100
        d_fuel = int(delta.get("fuel", 0))

        # Packets carry minerals only - no colonists, no fuel
        if other_is_packet and (d_col != 0 or d_fuel != 0):
            return {"error": "Mineral packets carry minerals only"}

        # Giver must have the goods (positive: other gives; negative:
        # this fleet gives)
        if d_iron > other.cargo.ironium or -d_iron > fleet.cargo.ironium:
            return {"error": "Not enough ironium"}
        if d_bor > other.cargo.boranium or -d_bor > fleet.cargo.boranium:
            return {"error": "Not enough boranium"}
        if d_germ > other.cargo.germanium or \
                -d_germ > fleet.cargo.germanium:
            return {"error": "Not enough germanium"}
        if d_col_kt > other.cargo.colonists_in_kilotons or \
                -d_col_kt > fleet.cargo.colonists_in_kilotons:
            return {"error": "Not enough colonists"}
        if d_fuel > other.fuel_available or -d_fuel > fleet.fuel_available:
            return {"error": "Not enough fuel"}

        # Receiver must have room. A packet has no hold - its cargo IS
        # the packet - so the counterparty clamp is skipped for one
        moved_mass = d_iron + d_bor + d_germ + d_col_kt
        if fleet.cargo.mass + moved_mass > fleet.total_cargo_capacity:
            return {"error": "Cargo capacity exceeded"}
        if not other_is_packet and \
                other.cargo.mass - moved_mass > other.total_cargo_capacity:
            return {"error": "Cargo capacity exceeded"}
        if fleet.fuel_available + d_fuel > fleet.total_fuel_capacity or \
                other.fuel_available - d_fuel > other.total_fuel_capacity:
            return {"error": "Fuel capacity exceeded"}

        fleet.cargo.ironium += d_iron
        other.cargo.ironium -= d_iron
        fleet.cargo.boranium += d_bor
        other.cargo.boranium -= d_bor
        fleet.cargo.germanium += d_germ
        other.cargo.germanium -= d_germ
        fleet.cargo.colonists_in_kilotons += d_col_kt
        other.cargo.colonists_in_kilotons -= d_col_kt
        fleet.fuel_available += d_fuel
        other.fuel_available -= d_fuel

        # An emptied packet vanishes
        if other_is_packet and other.cargo.mass == 0:
            for other_empire in server_data.all_empires.values():
                other_empire.owned_fleets.pop(other.key, None)
                other_empire.fleet_reports.pop(other.key, None)

        self._record_fleet_op(empire, "transfer_cargo_between_fleets", {
            "fleet_key": fleet_key, "other_fleet_key": other_fleet_key,
            "delta": delta,
        })
        self._save_game_state(game_id, server_data)

        return {
            "status": "ok",
            "fleet": self._fleet_to_dict(fleet),
            "other_fleet": self._fleet_to_dict(other),
        }

    def gift_to_trader(
        self,
        game_id: str,
        empire_id: int,
        fleet_key: int,
        trader_key: int,
        delta: dict
    ) -> dict:
        """
        Gift minerals or colonists to a co-located Mystery Trader.

        Canonical Stars! Mystery Trader intercept-and-gift (the C#
        reference has only a TODO, GameInitialiser.cs:180; user
        directive, acc-crit Mystery Trader section). Modeled on
        transfer_cargo_between_fleets, but strictly ONE-WAY: minerals
        (kT) and colonists (headcount, 100 per kT) flow to the trader,
        never back, and fuel is not accepted. The gift accumulates in
        the trader's per-empire ledger; rewards resolve on the seeded
        per-turn RNG in TurnGenerator._process_traders, never here
        (keeps the determinism criterion - API calls happen outside
        the seeded window). The trader always keeps the cargo.

        Args:
            game_id: Game identifier.
            empire_id: Gifting empire.
            fleet_key: Gifting fleet (must be at the trader's position).
            trader_key: Target trader.
            delta: {ironium, boranium, germanium, colonists} amounts.

        Returns:
            Result with the updated fleet, running gift total and the
            reward threshold, or error.
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
            return {"error": "Starbases cannot gift to the trader"}
        locked = self._empire_locked(empire)
        if locked:
            return locked

        trader = getattr(server_data, 'all_traders', {}).get(trader_key)
        if trader is None:
            return {"error": "Mystery Trader not found"}

        # Co-location gate (merge tolerance)
        dx = fleet.position.x - trader.x
        dy = fleet.position.y - trader.y
        if (dx * dx + dy * dy) > 1.0:
            return {"error": "Fleet must be at the trader's position"}

        d_iron = int(delta.get("ironium", 0))
        d_bor = int(delta.get("boranium", 0))
        d_germ = int(delta.get("germanium", 0))
        d_col = int(delta.get("colonists", 0))
        d_col_kt = d_col // 100

        # One-way gift: no negative amounts, no fuel
        if any(v < 0 for v in (d_iron, d_bor, d_germ, d_col)):
            return {"error": "Gift amounts cannot be negative"}
        if int(delta.get("fuel", 0)) != 0:
            return {"error": "The trader does not accept fuel"}

        total_kt = d_iron + d_bor + d_germ + d_col_kt
        if total_kt <= 0:
            return {"error": "Gift must carry at least 1 kT"}

        if d_iron > fleet.cargo.ironium:
            return {"error": "Not enough ironium"}
        if d_bor > fleet.cargo.boranium:
            return {"error": "Not enough boranium"}
        if d_germ > fleet.cargo.germanium:
            return {"error": "Not enough germanium"}
        if d_col_kt > fleet.cargo.colonists_in_kilotons:
            return {"error": "Not enough colonists"}

        fleet.cargo.ironium -= d_iron
        fleet.cargo.boranium -= d_bor
        fleet.cargo.germanium -= d_germ
        fleet.cargo.colonists_in_kilotons -= d_col_kt

        entry = trader.gifts.setdefault(
            empire_id, {"total": 0, "fleet_key": fleet_key})
        entry["total"] += total_kt
        entry["fleet_key"] = fleet_key

        self._record_fleet_op(empire, "gift_to_trader", {
            "fleet_key": fleet_key, "trader_key": trader_key,
            "delta": delta,
        })
        self._save_game_state(game_id, server_data)

        return {
            "status": "ok",
            "fleet": self._fleet_to_dict(fleet),
            "gift_total": entry["total"],
            "threshold": MT_GIFT_THRESHOLD,
        }

    # =========================================================================
    # Correspondence Play
    #
    # Web adaptation of the C# file-based turn-submission model: the
    # per-empire fog file (IntelWriter.cs WriteIntel), the per-empire
    # orders file (Orders.cs / OrderWriter.cs / OrderReader.cs) and the
    # race password (Race.cs:50, PasswordUtility.cs, CheckPassword.cs -
    # scaffolding without live call sites in the reference; the web
    # wires the canonical intent). Files are versioned JSON envelopes
    # instead of XML files in a shared game folder.
    # =========================================================================

    def verify_empire_password(self, game_id: str, empire_id: int,
                               supplied: Optional[str]) -> Optional[bool]:
        """
        Check a supplied plaintext password against the empire's race.

        Returns None if the game or empire does not exist, True when
        access is allowed (no password set, or hash match - the
        CheckPassword.cs:41-70 comparison), False on mismatch.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None
        empire = server_data.all_empires.get(empire_id)
        if empire is None:
            return None
        stored = getattr(empire.race, 'password', '') if empire.race else ''
        if not stored:
            return True
        return calculate_password_hash(supplied or "") == stored

    def get_turn_package(self, game_id: str,
                         empire_id: int) -> Optional[dict]:
        """
        Per-empire turn package: the empire's fog-of-war player state
        for the current year in a portable versioned envelope.

        Web analog of the per-player .intel file (IntelWriter.cs
        WriteIntel, lines 60-110). Fog integrity holds by construction:
        the body is exactly get_player_state - nothing global is added.
        """
        state = self.get_player_state(game_id, empire_id)
        if state is None:
            return None
        return {
            "format": TURN_PACKAGE_FORMAT,
            "version": CORRESPONDENCE_FILE_VERSION,
            "game_id": game_id,
            "empire_id": empire_id,
            "turn_year": state["turn_year"],
            "state": state,
        }

    def get_orders_file(self, game_id: str,
                        empire_id: int) -> Optional[dict]:
        """
        Export the empire's orders for the current year as a file.

        Mirrors Orders.cs ToXml (lines 137-175: the Turn year is
        written first "so it can be determined quickly") and
        OrderWriter.cs WriteOrders (lines 70-71: ROOT/Turn + ROOT/Id).
        "auth" carries the race password hash so the host can verify
        the file came from the password holder (export is
        password-gated at the route).
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None
        empire = server_data.all_empires.get(empire_id)
        if empire is None:
            return None
        return {
            "format": ORDERS_FILE_FORMAT,
            "version": CORRESPONDENCE_FILE_VERSION,
            "turn_year": server_data.turn_year,
            "game_id": game_id,
            "empire_id": empire_id,
            "auth": getattr(empire.race, 'password', '')
            if empire.race else '',
            "orders": list(empire.orders_log),
        }

    def import_orders(self, game_id: str, orders_file: dict) -> dict:
        """
        Import an orders file and apply it to the empire.

        Port of OrderReader.cs ReadPlayerTurn (lines 68-174): the year
        check (96-102 - where C# silently skips stale orders, the web
        rejects with a clear message, "code" 409), the empire id check
        (105-110), oldest-first application (111-114) and the final
        TurnSubmitted/LastTurnSubmitted flags (171-173). Validation
        happens BEFORE any state mutates; each entry then replays
        through the identical live-entry code path, so orders apply
        exactly as if entered live.
        """
        if orders_file.get("format") != ORDERS_FILE_FORMAT:
            return {"error": "Not a Stars UltraNova orders file",
                    "code": 422}
        if orders_file.get("version") != CORRESPONDENCE_FILE_VERSION:
            return {"error": "Unsupported orders file version "
                             f"'{orders_file.get('version')}'",
                    "code": 422}

        server_data = self._load_game_state(game_id)
        if not server_data:
            return {"error": "Game not found", "code": 404}

        empire_id = orders_file.get("empire_id")
        empire = server_data.all_empires.get(empire_id)
        if empire is None:
            return {"error": "Empire not found", "code": 404}

        # Stale-year gate (OrderReader.cs:96-102)
        file_year = orders_file.get("turn_year")
        if file_year != server_data.turn_year:
            return {"error": f"Orders file is for year {file_year} but "
                             f"the game is at year "
                             f"{server_data.turn_year} - orders "
                             f"rejected, nothing applied",
                    "code": 409}

        # Password gate: the file's auth must match the empire's
        # stored hash (the exporter proved knowledge at export time)
        stored = getattr(empire.race, 'password', '') if empire.race else ''
        if stored and orders_file.get("auth") != stored:
            return {"error": "Incorrect password - Access denied",
                    "code": 401}

        if empire.turn_submitted:
            return {"error": f"Orders already submitted for year "
                             f"{empire.turn_year}", "code": 409}

        # Replay in file order (oldest first, OrderReader.cs:111-114);
        # abort and report on the first failing entry
        applied = 0
        for entry in orders_file.get("orders") or []:
            result = self._replay_order(game_id, empire_id, entry)
            if result is not None and "error" in result:
                return {"error": f"Order {applied + 1} failed: "
                                 f"{result['error']}", "code": 422,
                        "applied": applied}
            applied += 1

        # OrderReader.cs:171-173
        empire.turn_submitted = True
        empire.last_turn_submitted = server_data.turn_year
        self._save_game_state(game_id, server_data)

        return {
            "status": "applied",
            "empire_id": empire_id,
            "turn_year": server_data.turn_year,
            "orders_applied": applied,
        }

    def _replay_order(self, game_id: str, empire_id: int,
                      entry: dict) -> Optional[dict]:
        """
        Replay one orders-log entry through the live code path.

        Command entries go through submit_command; fleet-op entries
        call the matching immediate server operation.
        """
        if "command_type" in entry:
            return self.submit_command(
                game_id, empire_id, entry["command_type"],
                entry.get("command_data") or {})
        op = entry.get("op")
        args = dict(entry.get("args") or {})
        try:
            if op == "split_fleet":
                return self.split_fleet(
                    game_id, empire_id, int(args["fleet_key"]),
                    {int(k): int(v) for k, v in
                     (args.get("keep_composition") or {}).items()})
            if op == "merge_fleets":
                return self.merge_fleets(
                    game_id, empire_id, int(args["fleet_key"]),
                    int(args["other_fleet_key"]))
            if op == "rename_fleet":
                return self.rename_fleet(
                    game_id, empire_id, int(args["fleet_key"]),
                    args.get("name", ""))
            if op == "set_fleet_battle_plan":
                return self.set_fleet_battle_plan(
                    game_id, empire_id, int(args["fleet_key"]),
                    args.get("plan_name", ""))
            if op == "transfer_cargo":
                return self.transfer_cargo(
                    game_id, empire_id, int(args["fleet_key"]),
                    args.get("cargo_delta") or {})
            if op == "transfer_cargo_between_fleets":
                return self.transfer_cargo_between_fleets(
                    game_id, empire_id, int(args["fleet_key"]),
                    int(args["other_fleet_key"]),
                    args.get("delta") or {})
            if op == "gift_to_trader":
                return self.gift_to_trader(
                    game_id, empire_id, int(args["fleet_key"]),
                    int(args["trader_key"]), args.get("delta") or {})
        except (KeyError, TypeError, ValueError):
            return {"error": f"Malformed '{op}' order entry"}
        return {"error": f"Unknown order entry type '{op}'"}

    def submit_orders(self, game_id: str, empire_id: int) -> dict:
        """
        Lock the empire's turn: orders are final until the year
        advances.

        Port of OrderWriter.cs WriteOrders lines 63-64: TurnSubmitted =
        true, LastTurnSubmitted = TurnYear.
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return {"error": "Game not found"}
        empire = server_data.all_empires.get(empire_id)
        if empire is None:
            return {"error": "Empire not found"}
        empire.turn_submitted = True
        empire.last_turn_submitted = server_data.turn_year
        self._save_game_state(game_id, server_data)
        return {
            "status": "submitted",
            "empire_id": empire_id,
            "turn_year": server_data.turn_year,
        }

    def get_submissions(self, game_id: str) -> Optional[List[dict]]:
        """
        Per-empire submission status for the current year.

        Web analog of the console player list (NovaConsole.cs
        SetPlayerList, lines 411-467): ai_program, turn flags and
        last_turn_submitted (0 = "No Orders" ever submitted).
        """
        server_data = self._load_game_state(game_id)
        if not server_data:
            return None
        rows = []
        for player in server_data.all_players:
            empire = server_data.all_empires.get(player.player_number)
            rows.append({
                "empire_id": player.player_number,
                "race_name": player.race_name,
                "ai_program": player.ai_program,
                "turn_year": getattr(empire, 'turn_year', 0),
                "turn_submitted": getattr(empire, 'turn_submitted',
                                          False),
                "last_turn_submitted": getattr(
                    empire, 'last_turn_submitted', 0),
            })
        return rows

    def export_game(self, game_id: str) -> Optional[dict]:
        """
        Export the entire game as a portable versioned file.

        The body is exactly what save_game_state persists (the full
        ServerData serialization plus last_messages), so import
        round-trips through the existing loaders. The note marks the
        file as host/carrier material - it contains every empire's
        state, unlike the fog-limited turn package.
        """
        game_record = self.repository.get_game(game_id)
        server_data = self._load_game_state(game_id)
        if not game_record or not server_data:
            return None
        state_dict = self._serialize_state(server_data)
        state_dict["last_messages"] = [
            m.to_dict() for m in self._last_messages.get(game_id, [])
        ]
        return {
            "format": GAME_FILE_FORMAT,
            "version": CORRESPONDENCE_FILE_VERSION,
            "game_id": game_id,
            "turn_year": server_data.turn_year,
            "note": "Full game state - host/carrier only. This file "
                    "contains every empire's unfogged state; players "
                    "should receive turn packages instead.",
            "game": {
                "name": game_record["name"],
                "player_count": game_record["player_count"],
                "universe_size": game_record["universe_size"],
            },
            "state": state_dict,
        }

    def import_game(self, game_file: dict) -> dict:
        """
        Import a full-game file as a new game.

        Creates a fresh game record and persists the embedded state
        through the normal save path; the imported game continues
        under a new id with its seed and determinism intact.
        """
        if game_file.get("format") != GAME_FILE_FORMAT:
            return {"error": "Not a Stars UltraNova game file",
                    "code": 422}
        if game_file.get("version") != CORRESPONDENCE_FILE_VERSION:
            return {"error": "Unsupported game file version "
                             f"'{game_file.get('version')}'",
                    "code": 422}
        state_dict = game_file.get("state")
        game_meta = game_file.get("game") or {}
        if not isinstance(state_dict, dict) or not state_dict:
            return {"error": "Game file carries no state", "code": 422}

        try:
            server_data = self._deserialize_state(state_dict)
        except Exception:
            logger.exception("Game file state failed to deserialize")
            return {"error": "Corrupt game file state", "code": 422}

        game_record = self.repository.create_game(
            game_meta.get("name", "Imported game"),
            game_meta.get("player_count", len(server_data.all_empires)),
            game_meta.get("universe_size", "medium"))
        new_id = game_record["id"]

        self._last_messages[new_id] = [
            Message.from_dict(m)
            for m in state_dict.get("last_messages", [])
        ]
        self._save_game_state(new_id, server_data)
        self.repository.update_game(new_id, status="active")

        return {
            **game_record,
            "status": "active",
            "turn": server_data.turn_year,
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
            # Learned enemy-design intel (plain dicts from ScanStep /
            # battle engines)
            empire_dict["empire_reports"] = {
                str(k): v for k, v in empire.empire_reports.items()
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

            # Migrate pre-canonical-fuel-table saves (run100 DEF-11):
            # tokens serialized before the DEF-7 fix carry
            # free_warp_speed 0 (ShipToken.from_dict default) and an
            # all-zero fuel_table, leaving the fleet stuck at warp 0
            # forever once out of fuel. Refresh both from the owning
            # empire's design (mirroring make_token); when the design
            # is gone, derive free warp from a stored non-zero fuel
            # table (all zeros = absent data or starbase - keep 0)
            for fleet in empire.owned_fleets.values():
                for token in fleet.tokens.values():
                    if token.free_warp_speed:
                        continue
                    design = empire.designs.get(token.design_key)
                    if design is not None:
                        engine = getattr(design, 'engine', None)
                        if engine is not None:
                            design_table = list(engine.fuel_consumption)
                        else:
                            design_table = list(
                                getattr(design, 'fuel_table', [0] * 10))
                        if not any(token.fuel_table) and any(design_table):
                            token.fuel_table = design_table
                        token.free_warp_speed = getattr(
                            design, 'free_warp_speed', 0)
                    if not token.free_warp_speed and any(token.fuel_table):
                        token.free_warp_speed = _free_warp_from_table(
                            token.fuel_table)

            empire.star_reports = dict(empire_dict.get("star_reports", {}))
            empire.fleet_reports = {
                int(k): v
                for k, v in empire_dict.get("fleet_reports", {}).items()
            }
            empire.empire_reports = {
                int(k): v
                for k, v in empire_dict.get("empire_reports", {}).items()
            }
            from ..server.battle.battle_plan import BattlePlan
            empire.battle_plans = {
                name: BattlePlan.from_dict(plan)
                for name, plan in empire_dict.get("battle_plans", {}).items()
            }
            if "Default" not in empire.battle_plans:
                # C# default Attack="Enemies" (BattlePlan.cs:44);
                # pre-relations saves lack relation keys, which default
                # to Enemy - identical net behavior
                empire.battle_plans["Default"] = BattlePlan(attack="Enemies")

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

    def _fleet_to_dict(self, fleet: Fleet, nebula_field=None,
                       race=None) -> dict:
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
            # Fleet-min storm protection (web extension, wave 4)
            "storm_protection": round(fleet.storm_protection(race), 2),
            "key": fleet.key,
            "name": fleet.name,
            "owner": fleet.owner,
            "battle_plan": fleet.battle_plan,
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
            "is_packet": bool(is_mineral_packet(fleet)),
            "packet_warp": fleet.packet_warp,
            "can_colonize": fleet.can_colonize,
            "mining_rate": fleet.total_mining_rate,
            "warp_factor": warp,
            "tokens": [
                {
                    "design_key": token.design_key,
                    "design_name": token.design_name,
                    "quantity": token.quantity,
                    "armor": token.armor,
                    "shields": token.shields,
                    "damage_percent": token.damage_percent,
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
                    # Full task dict so a warp-only Edit can round-trip
                    # the task with its parameters intact (C# preserves
                    # the Task object on speed edits, FleetDetail.cs:110)
                    "task": wp.to_dict()["task"],
                }
                for wp in fleet.waypoints
            ],
            "waypoint_count": len(fleet.waypoints),
            # Fuel consumption (mg/year) at each warp 0-10, for the
            # client leg time/fuel readout (FleetDetail.cs:391-439;
            # Fleet.FuelConsumption port at Fleet.cs:817-839)
            "fuel_consumption_by_warp": [
                round(fleet.fuel_consumption(w, race), 2)
                for w in range(11)
            ],
        }


# Global game manager instance
_game_manager: Optional[GameManager] = None


def get_game_manager() -> GameManager:
    """
    Get or create global game manager instance.

    Returns:
        GameManager instance.
    """
    global _game_manager
    if _game_manager is None:
        _game_manager = GameManager()
    return _game_manager
