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
from ..server.server_data import ServerData, PlayerSettings, NebulaField, NebulaRegion


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

# Star spectral classes with astronomical distribution (approximated from IMF)
# Format: (class, luminosity, temp_range, radius_range, weight)
# Weights adjusted for visual variety while keeping general pattern
SPECTRAL_CLASSES = [
    # Main sequence stars (class V)
    ("M", "V", (2400, 3700), (0.1, 0.6), 40),    # Red dwarfs - most common
    ("K", "V", (3700, 5200), (0.7, 0.96), 20),   # Orange dwarfs
    ("G", "V", (5200, 6000), (0.96, 1.15), 15),  # Yellow dwarfs (Sun-like)
    ("F", "V", (6000, 7500), (1.15, 1.4), 10),   # Yellow-white
    ("A", "V", (7500, 10000), (1.4, 1.8), 6),    # White
    ("B", "V", (10000, 30000), (1.8, 6.6), 3),   # Blue-white
    ("O", "V", (30000, 50000), (6.6, 15), 1),    # Blue - very rare

    # Giants and supergiants (for visual interest)
    ("K", "III", (3500, 5000), (10, 25), 2),     # Orange giant
    ("M", "III", (2500, 3500), (40, 100), 1),    # Red giant
    ("G", "III", (5000, 5500), (8, 15), 1),      # Yellow giant
    ("B", "I", (10000, 30000), (30, 70), 0.5),   # Blue supergiant - rare
    ("M", "I", (2500, 3500), (200, 1000), 0.3),  # Red supergiant - very rare
]

# Star colors by spectral class (RGB values)
STAR_COLORS = {
    "O": (155, 176, 255),    # Blue
    "B": (170, 191, 255),    # Blue-white
    "A": (202, 215, 255),    # White
    "F": (248, 247, 255),    # Yellow-white
    "G": (255, 244, 234),    # Yellow
    "K": (255, 210, 161),    # Orange
    "M": (255, 204, 111),    # Red-orange
}

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

        # Generate nebula density field
        server_data.nebula_field = self._generate_nebulae(stars, width, height)

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
        Generate stars for the galaxy using Gaussian Mixture Model distribution.

        Creates natural-looking clusters, streams, and voids.

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

        # Galaxy center
        cx, cy = width / 2, height / 2
        max_radius = min(width, height) * 0.45

        # Create Gaussian mixture components
        components = []

        # 1. Central core - high weight, circular
        components.append({
            'weight': 0.15,
            'mean_x': cx,
            'mean_y': cy,
            'std_x': max_radius * 0.20,
            'std_y': max_radius * 0.20,
            'rotation': 0
        })

        # 2. Main galactic band - elongated ellipse
        band_angle = self.rng.random() * math.pi
        band_stretch = 1.5 + self.rng.random() * 1.0  # 1.5 to 2.5
        components.append({
            'weight': 0.35,
            'mean_x': cx,
            'mean_y': cy,
            'std_x': max_radius * 0.6 * band_stretch,
            'std_y': max_radius * 0.25,
            'rotation': band_angle
        })

        # 3-5. Star clusters - compact groups
        num_clusters = 2 + self.rng.randint(0, 3)
        for i in range(num_clusters):
            angle = self.rng.random() * math.pi * 2
            dist = max_radius * (0.3 + self.rng.random() * 0.5)
            cluster_size = 25 + self.rng.random() * 40
            components.append({
                'weight': 0.08,
                'mean_x': cx + math.cos(angle) * dist,
                'mean_y': cy + math.sin(angle) * dist,
                'std_x': cluster_size,
                'std_y': cluster_size * (0.5 + self.rng.random() * 0.5),
                'rotation': self.rng.random() * math.pi
            })

        # 6-7. Star streams - very elongated
        num_streams = 1 + self.rng.randint(0, 2)
        for i in range(num_streams):
            stream_angle = self.rng.random() * math.pi
            offset_angle = self.rng.random() * math.pi * 2
            offset_dist = max_radius * (0.2 + self.rng.random() * 0.4)
            components.append({
                'weight': 0.06,
                'mean_x': cx + math.cos(offset_angle) * offset_dist,
                'mean_y': cy + math.sin(offset_angle) * offset_dist,
                'std_x': max_radius * (0.3 + self.rng.random() * 0.4),
                'std_y': 15 + self.rng.random() * 20,
                'rotation': stream_angle
            })

        # 8. Outer halo - diffuse background
        components.append({
            'weight': 0.10,
            'mean_x': cx,
            'mean_y': cy,
            'std_x': max_radius * 0.8,
            'std_y': max_radius * 0.8,
            'rotation': 0
        })

        # Normalize weights
        total_weight = sum(c['weight'] for c in components)
        for c in components:
            c['weight'] /= total_weight

        # Generate void regions (rejection sampling)
        voids = []
        num_voids = 2 + self.rng.randint(0, 3)
        for i in range(num_voids):
            angle = self.rng.random() * math.pi * 2
            dist = max_radius * (0.3 + self.rng.random() * 0.5)
            voids.append({
                'x': cx + math.cos(angle) * dist,
                'y': cy + math.sin(angle) * dist,
                'radius': 25 + self.rng.random() * 45
            })

        attempts = 0
        while len(stars) < num_stars and attempts < num_stars * 20:
            attempts += 1

            # Sample from Gaussian mixture
            x, y = self._sample_gmm(components)

            x = int(x)
            y = int(y)

            # Clamp to bounds with margin
            margin = 20
            x = max(margin, min(width - margin, x))
            y = max(margin, min(height - margin, y))

            # Check if in void region
            in_void = False
            for void in voids:
                dist_to_void = math.sqrt((x - void['x'])**2 + (y - void['y'])**2)
                if dist_to_void < void['radius']:
                    in_void = True
                    break
            if in_void:
                continue

            # Check minimum distance from other stars
            too_close = False
            for px, py in used_positions:
                dist = math.sqrt((x - px) ** 2 + (y - py) ** 2)
                if dist < STAR_DENSITY * 0.5:
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

            # Assign spectral class based on astronomical distribution
            self._assign_spectral_class(star)

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

    def _assign_spectral_class(self, star: Star) -> None:
        """
        Assign spectral class to a star based on astronomical distribution.

        Uses weighted random selection from SPECTRAL_CLASSES following
        the Initial Mass Function (IMF) approximation.

        Args:
            star: Star object to modify.
        """
        # Calculate total weight
        total_weight = sum(sc[4] for sc in SPECTRAL_CLASSES)

        # Weighted random selection
        r = self.rng.random() * total_weight
        cumulative = 0

        for spectral, luminosity, temp_range, radius_range, weight in SPECTRAL_CLASSES:
            cumulative += weight
            if r <= cumulative:
                star.spectral_class = spectral
                star.luminosity_class = luminosity

                # Random temperature within range
                star.star_temperature = self.rng.randint(temp_range[0], temp_range[1])

                # Random radius within range
                star.star_radius = radius_range[0] + self.rng.random() * (radius_range[1] - radius_range[0])
                break

    def _sample_gmm(self, components: List[dict]) -> Tuple[float, float]:
        """
        Sample a point from a Gaussian Mixture Model.

        Args:
            components: List of GMM components with weight, mean, std, and rotation.

        Returns:
            (x, y) coordinate tuple.
        """
        # Select component based on weights
        r = self.rng.random()
        cumulative = 0
        selected = components[0]
        for c in components:
            cumulative += c['weight']
            if r <= cumulative:
                selected = c
                break

        # Sample from 2D Gaussian
        # Generate in local coordinates (aligned with ellipse axes)
        local_x = self.rng.gauss(0, selected['std_x'])
        local_y = self.rng.gauss(0, selected['std_y'])

        # Rotate to world coordinates
        rotation = selected.get('rotation', 0)
        cos_r = math.cos(rotation)
        sin_r = math.sin(rotation)
        world_x = local_x * cos_r - local_y * sin_r
        world_y = local_x * sin_r + local_y * cos_r

        # Translate to mean position
        x = selected['mean_x'] + world_x
        y = selected['mean_y'] + world_y

        return x, y

    def _generate_nebulae(self, stars: List[Star], width: int, height: int) -> NebulaField:
        """
        Generate nebula density field based on star distribution.

        Creates nebula regions near star clusters and in void areas.
        The density field will later affect warp speed calculations.

        Args:
            stars: List of stars in the galaxy.
            width: Universe width.
            height: Universe height.

        Returns:
            NebulaField with density regions.
        """
        nebula_field = NebulaField(universe_width=width, universe_height=height)

        # Analyze star distribution to find clusters
        cell_size = 80
        cols = width // cell_size + 1
        rows = height // cell_size + 1
        density_grid = [[0 for _ in range(cols)] for _ in range(rows)]

        for star in stars:
            gx = int(star.position.x / cell_size)
            gy = int(star.position.y / cell_size)
            if 0 <= gx < cols and 0 <= gy < rows:
                density_grid[gy][gx] += 1

        # Find high-density regions (star clusters) - add emission nebulae
        clusters = []
        for gy in range(1, rows - 1):
            for gx in range(1, cols - 1):
                # Sum 3x3 neighborhood
                neighborhood = sum(
                    density_grid[gy + dy][gx + dx]
                    for dy in range(-1, 2) for dx in range(-1, 2)
                )
                if neighborhood >= 5:
                    clusters.append({
                        'x': (gx + 0.5) * cell_size,
                        'y': (gy + 0.5) * cell_size,
                        'density': neighborhood
                    })

        # Add emission nebulae near clusters
        for i, cluster in enumerate(clusters[:6]):
            angle = self.rng.random() * math.pi * 2
            offset = 30 + self.rng.random() * 50
            nebula_field.regions.append(NebulaRegion(
                x=cluster['x'] + math.cos(angle) * offset,
                y=cluster['y'] + math.sin(angle) * offset,
                radius_x=50 + self.rng.random() * 80,
                radius_y=40 + self.rng.random() * 60,
                rotation=self.rng.random() * math.pi,
                density=0.3 + self.rng.random() * 0.4,
                nebula_type='emission'
            ))

        # Find void regions - add dark nebulae
        voids = []
        for gy in range(1, rows - 1):
            for gx in range(1, cols - 1):
                neighborhood = sum(
                    density_grid[gy + dy][gx + dx]
                    for dy in range(-1, 2) for dx in range(-1, 2)
                )
                if neighborhood == 0:
                    voids.append({
                        'x': (gx + 0.5) * cell_size,
                        'y': (gy + 0.5) * cell_size
                    })

        # Add dark nebulae in voids
        for i, void in enumerate(voids[:4]):
            nebula_field.regions.append(NebulaRegion(
                x=void['x'],
                y=void['y'],
                radius_x=40 + self.rng.random() * 60,
                radius_y=40 + self.rng.random() * 60,
                rotation=self.rng.random() * math.pi,
                density=0.4 + self.rng.random() * 0.3,
                nebula_type='dark'
            ))

        # Add filament nebulae connecting regions
        num_filaments = 2 + self.rng.randint(0, 3)
        cx, cy = width / 2, height / 2
        for i in range(num_filaments):
            angle = self.rng.random() * math.pi
            offset_angle = self.rng.random() * math.pi * 2
            offset_dist = (width / 4) * (0.3 + self.rng.random() * 0.5)
            nebula_field.regions.append(NebulaRegion(
                x=cx + math.cos(offset_angle) * offset_dist,
                y=cy + math.sin(offset_angle) * offset_dist,
                radius_x=80 + self.rng.random() * 120,
                radius_y=15 + self.rng.random() * 25,
                rotation=angle,
                density=0.2 + self.rng.random() * 0.3,
                nebula_type='filament'
            ))

        return nebula_field

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
