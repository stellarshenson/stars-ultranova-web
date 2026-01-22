"""
Stars Nova Web - Galaxy Generator

Generates initial game state with stars, empires, and starting positions.
Ported from Nova/WinForms/NewGame logic.
"""

import random
import math
from typing import List, Dict, Tuple, Optional

from ..core.data_structures import NovaPoint, Resources, TechLevel
from ..core.data_structures.empire_data import EmpireData
from ..core.game_objects.star import Star
from ..core.game_objects.fleet import Fleet, ShipToken
from ..core.race.race import Race
from ..core.globals import STARTING_YEAR, COLONISTS_PER_KILOTON
from ..server.server_data import ServerData, PlayerSettings


# Universe size configurations (width x height in light years)
UNIVERSE_SIZES = {
    "tiny": (200, 200),
    "small": (400, 400),
    "medium": (600, 600),
    "large": (800, 800),
    "huge": (1000, 1000),
}

# Star density (average distance between stars)
STAR_DENSITY = 25

# Star name pool (subset of original Stars! names)
STAR_NAMES = [
    "Sol", "Alpha Centauri", "Barnard's Star", "Wolf 359", "Lalande 21185",
    "Sirius", "Luyten 726-8", "Ross 154", "Ross 248", "Epsilon Eridani",
    "Lacaille 9352", "Ross 128", "EZ Aquarii", "Procyon", "61 Cygni",
    "Struve 2398", "Groombridge 34", "Epsilon Indi", "Tau Ceti", "Gliese 1061",
    "Kapteyn's Star", "Kruger 60", "Ross 614", "Wolf 1061", "Van Maanen's Star",
    "Gliese 1", "Wolf 424", "TZ Arietis", "Gliese 687", "LHS 292",
    "Proxima", "Vega", "Altair", "Arcturus", "Rigel",
    "Betelgeuse", "Aldebaran", "Antares", "Spica", "Pollux",
    "Fomalhaut", "Deneb", "Regulus", "Capella", "Canopus",
    "Achernar", "Hadar", "Acrux", "Mimosa", "Shaula",
    "Bellatrix", "Elnath", "Alnilam", "Alnitak", "Mintaka",
    "Saiph", "Polaris", "Mira", "Algol", "Rasalhague",
    "Kochab", "Thuban", "Dubhe", "Merak", "Phecda",
    "Megrez", "Alioth", "Mizar", "Alkaid", "Alcor",
    "Castor", "Gemma", "Zubenelgenubi", "Zubeneschamali", "Unukalhai",
    "Kornephoros", "Ras Algethi", "Sabik", "Rasalhague", "Cebalrai",
    "Sheliak", "Sulafat", "Albireo", "Sadr", "Gienah",
    "Azha", "Acamar", "Zaurak", "Rana", "Cursa",
]

# Default race templates (using string trait keys from traits.py)
DEFAULT_RACES = [
    {"name": "Humanoids", "prt": "JOAT", "icon": "humanoid"},
    {"name": "Rabbitoids", "prt": "HE", "icon": "rabbitoid"},
    {"name": "Insectoids", "prt": "WM", "icon": "insectoid"},
    {"name": "Siliconoids", "prt": "AR", "icon": "siliconoid"},
]


class GalaxyGenerator:
    """
    Generates initial game state.

    Creates stars, assigns home worlds, creates starting fleets.
    """

    def __init__(self, seed: Optional[int] = None):
        """
        Initialize generator.

        Args:
            seed: Random seed for reproducibility.
        """
        self.seed = seed
        self.rng = random.Random(seed)

    def generate(
        self,
        player_count: int = 2,
        universe_size: str = "medium"
    ) -> ServerData:
        """
        Generate a new game.

        Args:
            player_count: Number of players.
            universe_size: Size of universe.

        Returns:
            Initialized ServerData.
        """
        server_data = ServerData()
        server_data.turn_year = STARTING_YEAR
        server_data.game_in_progress = True

        # Get universe dimensions
        width, height = UNIVERSE_SIZES.get(universe_size, UNIVERSE_SIZES["medium"])

        # Generate stars
        stars = self._generate_stars(width, height)
        for star in stars:
            server_data.all_stars[star.name] = star

        # Create player settings and races
        races = self._create_races(player_count)
        for i, race in enumerate(races):
            server_data.all_races[race.name] = race
            server_data.all_players.append(PlayerSettings(
                player_number=i + 1,
                race_name=race.name,
                ai_program="Human" if i == 0 else "Default AI"
            ))

        # Create empires with home worlds
        home_stars = self._select_home_worlds(list(server_data.all_stars.values()), player_count)

        for i, (race, home_star) in enumerate(zip(races, home_stars)):
            empire_id = i + 1
            empire = self._create_empire(empire_id, race, home_star)
            server_data.all_empires[empire_id] = empire

            # Set star ownership
            home_star.owner = empire_id
            home_star.colonists = 250000  # Starting population
            home_star.factories = 10
            home_star.mines = 10

            # Create starting fleet with scout
            scout_fleet = self._create_starting_fleet(empire_id, home_star, race)
            empire.owned_fleets[scout_fleet.key] = scout_fleet

        return server_data

    def _generate_stars(self, width: int, height: int) -> List[Star]:
        """
        Generate stars for the galaxy.

        Args:
            width: Galaxy width in light years.
            height: Galaxy height in light years.

        Returns:
            List of Star objects.
        """
        stars = []
        used_names = set()
        used_positions = set()

        # Calculate number of stars based on size
        area = width * height
        num_stars = area // (STAR_DENSITY * STAR_DENSITY)
        num_stars = max(20, min(num_stars, len(STAR_NAMES)))

        # Shuffle names
        available_names = list(STAR_NAMES)
        self.rng.shuffle(available_names)

        attempts = 0
        while len(stars) < num_stars and attempts < num_stars * 10:
            attempts += 1

            # Random position with margin
            margin = 20
            x = self.rng.randint(margin, width - margin)
            y = self.rng.randint(margin, height - margin)

            # Check minimum distance from other stars
            too_close = False
            for px, py in used_positions:
                dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
                if dist < STAR_DENSITY * 0.6:
                    too_close = True
                    break

            if too_close:
                continue

            # Get name
            if not available_names:
                break
            name = available_names.pop()

            # Create star with random environment
            star = Star()
            star.name = name
            star.position = NovaPoint(x, y)

            # Random habitability values (0-100)
            star.gravity = self.rng.randint(0, 100)
            star.temperature = self.rng.randint(0, 100)
            star.radiation = self.rng.randint(0, 100)

            # Random mineral concentrations (1-100)
            star.ironium_concentration = self.rng.randint(1, 100)
            star.boranium_concentration = self.rng.randint(1, 100)
            star.germanium_concentration = self.rng.randint(1, 100)

            # Starting surface minerals
            star.resource_rate = self.rng.randint(5, 15)
            star.mineral_concentration = (
                star.ironium_concentration +
                star.boranium_concentration +
                star.germanium_concentration
            ) // 3

            stars.append(star)
            used_names.add(name)
            used_positions.add((x, y))

        return stars

    def _create_races(self, player_count: int) -> List[Race]:
        """
        Create race definitions for players.

        Args:
            player_count: Number of players.

        Returns:
            List of Race objects.
        """
        races = []

        for i in range(player_count):
            template = DEFAULT_RACES[i % len(DEFAULT_RACES)]

            race = Race()
            race.name = template["name"]
            if i >= len(DEFAULT_RACES):
                race.name = f"{template['name']} {i + 1}"

            race.plural_name = race.name
            race.icon = template.get("icon", "humanoid")

            # Default habitability ranges (centered, wide range)
            race.gravity_minimum = 15
            race.gravity_maximum = 85
            race.temperature_minimum = 15
            race.temperature_maximum = 85
            race.radiation_minimum = 15
            race.radiation_maximum = 85

            race.growth_rate = 15  # 15% base growth
            race.colonist_resource_production = 10  # 1000 colonists = 10 resources
            race.factory_production = 10
            race.factory_cost = 10
            race.mine_cost = 5
            race.mine_production = 10

            races.append(race)

        return races

    def _select_home_worlds(self, stars: List[Star], player_count: int) -> List[Star]:
        """
        Select home worlds for players.

        Ensures home worlds are spread apart.

        Args:
            stars: All stars in galaxy.
            player_count: Number of players.

        Returns:
            List of home world stars.
        """
        if len(stars) < player_count:
            raise ValueError("Not enough stars for all players")

        # Sort stars by distance from center for even distribution
        if stars:
            avg_x = sum(s.position.x for s in stars) / len(stars)
            avg_y = sum(s.position.y for s in stars) / len(stars)
        else:
            avg_x, avg_y = 0, 0

        # Divide into sectors and pick one from each
        selected = []
        remaining = list(stars)

        for i in range(player_count):
            if not remaining:
                break

            # Pick star furthest from already selected
            if selected:
                best_star = None
                best_min_dist = -1

                for star in remaining:
                    min_dist = min(
                        math.sqrt(
                            (star.position.x - s.position.x) ** 2 +
                            (star.position.y - s.position.y) ** 2
                        )
                        for s in selected
                    )
                    if min_dist > best_min_dist:
                        best_min_dist = min_dist
                        best_star = star

                selected.append(best_star)
                remaining.remove(best_star)
            else:
                # First player gets random corner area star
                corner_stars = [
                    s for s in remaining
                    if s.position.x < avg_x and s.position.y < avg_y
                ]
                if corner_stars:
                    star = self.rng.choice(corner_stars)
                else:
                    star = self.rng.choice(remaining)
                selected.append(star)
                remaining.remove(star)

        # Make home worlds habitable (centered values)
        for star in selected:
            star.gravity = 50
            star.temperature = 50
            star.radiation = 50
            # Good mineral concentrations
            star.ironium_concentration = self.rng.randint(50, 80)
            star.boranium_concentration = self.rng.randint(50, 80)
            star.germanium_concentration = self.rng.randint(50, 80)

        return selected

    def _create_empire(self, empire_id: int, race: Race, home_star: Star) -> EmpireData:
        """
        Create empire data for a player.

        Args:
            empire_id: Empire identifier.
            race: Race definition.
            home_star: Home world star.

        Returns:
            Initialized EmpireData.
        """
        empire = EmpireData()
        empire.id = empire_id
        empire.race_name = race.name
        empire.turn_year = STARTING_YEAR

        # Starting tech levels
        empire.research_levels = TechLevel.from_level(3)

        # Research allocation (even distribution)
        empire.research_budget = 15  # 15% of resources to research
        empire.research_topics = TechLevel.from_level(1)

        # Home star ownership
        empire.owned_stars[home_star.name] = home_star

        return empire

    def _create_starting_fleet(
        self,
        empire_id: int,
        home_star: Star,
        race: Race
    ) -> Fleet:
        """
        Create starting fleet for empire.

        Args:
            empire_id: Empire identifier.
            home_star: Home world.
            race: Race definition.

        Returns:
            Scout fleet.
        """
        fleet = Fleet()
        fleet.owner = empire_id
        fleet.id = 1  # First fleet
        fleet.name = "Scout #1"
        fleet.position = NovaPoint(home_star.position.x, home_star.position.y)
        fleet.in_orbit_name = home_star.name
        fleet.fuel_available = 200  # Full tank

        # Add scout ship token
        token = ShipToken()
        token.design_key = 1
        token.design_name = "Long Range Scout"
        token.quantity = 1
        token.armor = 20
        token.shields = 0
        token.mass = 25
        token.has_weapons = False
        token.can_colonize = False
        token.can_scan = True
        token.optimal_speed = 9
        token.free_warp_speed = 0
        token.fuel_capacity = 200
        token.scan_range_normal = 150
        token.scan_range_penetrating = 0

        fleet.tokens[token.design_key] = token

        return fleet
