"""
Stars Nova Web - Galaxy Generator

Generates initial game state with stars, empires, and starting positions.
Ported from Nova/WinForms/NewGame logic.
"""

import random
import math
from pathlib import Path
from typing import List, Dict, Optional

from . import star_field
from ..core.data_structures import NovaPoint, Resources, TechLevel
from ..core.data_structures.empire_data import EmpireData
from ..core.defenses import (
    best_defense_type, best_planetary_scanner, race_trait_codes
)
from ..core.game_objects.star import Star
from ..core.game_objects.fleet import Fleet, ShipToken
from ..core.race.race import Race
from ..core.globals import STARTING_YEAR, COLONISTS_PER_KILOTON
from ..server.server_data import (
    ServerData, PlayerSettings, NebulaField, NebulaRegion,
    GalacticStorm, Wormhole
)


# Universe size configurations (width x height in light years).
#
# THIS TABLE IS THE SINGLE SOURCE OF TRUTH for board dimensions. The API
# reports width and height alongside the size name (GET /api/games/...),
# and the client reads them from game state - nothing outside this file
# restates them.
#
# Enlarged 2026-07-28 on the "maps for the players must be larger"
# directive: tiny 200 -> 400, small 400 -> 700, medium 600 -> 1000,
# large 800 -> 1300, huge 1000 -> 1600. The C# reference has no size
# tiers at all - GameSettings.cs:51-52 is a free MapWidth/MapHeight pair
# defaulting to 400x400 - so the tiers are a web convention and the new
# values bracket the original Stars! board sizes.
UNIVERSE_SIZES = {
    "tiny": (400, 400),
    "small": (700, 700),
    "medium": (1000, 1000),
    "large": (1300, 1300),
    "huge": (1600, 1600),
}

# Star density: mean distance between stars in light years, so a map
# carries area / STAR_DENSITY^2 stars and density is constant across the
# tiers - a bigger board is a bigger galaxy, not an emptier one
# (64 / 196 / 400 / 676 / 1024 stars). Raised 25 -> 50 with the enlarged
# boards; the old value would put 1024 stars on a tiny map and 4096 on a
# huge one, far past the canonical name pool.
STAR_DENSITY = 50

# Keep-out band along the map edge, in light years
STAR_MARGIN = 20

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

# Canonical star name pool, ported from the C# reference
# NameGenerator.cs:157 (starNames, 1210 entries) into
# backend/data/star_names.txt with its 10 duplicates dropped. The pool
# is the hard cap on stars per map: 1200 names against the largest
# board's 1024 stars.
STAR_NAMES_FILE = Path(__file__).resolve().parents[1] / "data" / "star_names.txt"


def _load_star_names() -> List[str]:
    """Read the canonical star name pool from backend/data."""
    names = []
    with open(STAR_NAMES_FILE, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                names.append(line)
    return names


STAR_NAMES = _load_star_names()


# Default race templates (using string trait keys from traits.py).
# Icons index the client's 16 standard SVG emblems (race-icons.js).
DEFAULT_RACES = [
    {"name": "Humanoids", "prt": "JOAT", "icon": 0},
    {"name": "Rabbitoids", "prt": "HE", "icon": 1},
    {"name": "Insectoids", "prt": "WM", "icon": 2},
    {"name": "Siliconoids", "prt": "AR", "icon": 3},
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
        universe_size: str = "medium",
        player_race: Optional[Race] = None,
        accelerated_start: bool = False,
        human_players: int = 1
    ) -> ServerData:
        """
        Generate a new game.

        Args:
            player_count: Number of players.
            universe_size: Size of universe.
            player_race: Optional custom race for the human player.
            accelerated_start: Accelerated BBS play (GameSettings.cs:63);
                its only effect is the higher starting population
                (Race.cs GetStartingPopulation, lines 340-355).
            human_players: How many empires (1..N, from empire 1 up)
                are human-controlled (PlayerSettings.AiProgram "Human",
                Common/DataStructures/PlayerSettings.cs). Correspondence
                play needs 2+ human empires.

        Returns:
            Initialized ServerData.
        """
        server_data = ServerData()
        server_data.turn_year = STARTING_YEAR
        server_data.game_in_progress = True
        # Remember the creation seed so turn generation can be made
        # reproducible (see GameManager.generate_turn)
        server_data.game_seed = self.seed

        # Get universe dimensions
        width, height = UNIVERSE_SIZES.get(universe_size, UNIVERSE_SIZES["medium"])

        # Generate stars
        stars = self._generate_stars(width, height)
        for star in stars:
            server_data.all_stars[star.name] = star

        # Generate nebula density field
        server_data.nebula_field = self._generate_nebulae(stars, width, height)

        # Generate roaming galactic storms (web extension)
        for storm in self._generate_storms(width, height,
                                           server_data.nebula_field):
            server_data.all_storms[storm.key] = storm

        # Generate wormhole pairs
        for wormhole in self._generate_wormholes(width, height):
            server_data.all_wormholes[wormhole.key] = wormhole

        # Create player settings and races
        races = self._create_races(player_count)
        if player_race is not None:
            # Human player (empire 1) uses the wizard-designed race;
            # keep its name unique against the AI templates
            if any(r.name == player_race.name for r in races[1:]):
                player_race.name = f"{player_race.name} Prime"
            races[0] = player_race
        for i, race in enumerate(races):
            server_data.all_races[race.name] = race
            server_data.all_players.append(PlayerSettings(
                player_number=i + 1,
                race_name=race.name,
                ai_program="Human" if i < human_players else "Default AI"
            ))

        # Create empires with home worlds
        home_stars = self._select_home_worlds(
            list(server_data.all_stars.values()), player_count,
            width, height)

        for i, (race, home_star) in enumerate(zip(races, home_stars)):
            empire_id = i + 1
            empire = self._create_empire(empire_id, race, home_star)
            server_data.all_empires[empire_id] = empire

            # Set star ownership
            home_star.owner = empire_id
            # Starting population (StarMapInitialiser.cs:449 via
            # Race.cs GetStartingPopulation): 25000 normal, 100000
            # accelerated BBS, x0.7 with LSP
            home_star.colonists = race.get_starting_population(
                accelerated_start)
            home_star.factories = 10
            home_star.mines = 10
            home_star.this_race = race

            # Homeworld habitability equals the race's optimum values
            # (AllocateHomeStarResources, StarMapInitialiser.cs:441-443
            # uses race.OptimumRadiationLevel etc. = tolerance centre)
            home_star.gravity = (race.gravity_min + race.gravity_max) // 2
            home_star.temperature = (
                race.temperature_min + race.temperature_max) // 2
            home_star.radiation = (race.radiation_min + race.radiation_max) // 2
            # Pristine environment mirror - anchor for the terraform
            # limit and Retro Bomb reversal (Star.cs:64-66)
            home_star.original_gravity = home_star.gravity
            home_star.original_temperature = home_star.temperature
            home_star.original_radiation = home_star.radiation

            # Starting surface minerals: 300-500 kT of each mineral
            # (PrepareResources, StarMapInitialiser.cs:305-316; uses
            # the seeded generator rng for reproducibility)
            home_star.resources_on_hand = Resources(
                ironium=self.rng.randint(300, 500),
                boranium=self.rng.randint(300, 500),
                germanium=self.rng.randint(300, 500),
                energy=0
            )
            # Homeworld installations. C# fixes ScannerType "Scoper
            # 150" / ScanRange 50 / DefenseType "SDI" regardless of
            # race (StarMapInitialiser.cs:462-464, internally
            # inconsistent - Scoper 150 scans 150 ly). Web deviation:
            # Viewer 50 / SDI baseline, then upgraded to the best
            # planetary scanner / defense type the race's starting
            # tech unlocks (canonical rule; e.g. JOAT with Electronics
            # 3 starts on Scoper 150 at its true 150 ly range). Races
            # whose restrictions allow nothing better (AR) keep the
            # C# baseline.
            home_star.scan_range = 50
            home_star.scanner_type = "Viewer 50"
            home_star.pen_scan_range = 0
            home_star.defense_type = "SDI"
            best_scanner = best_planetary_scanner(
                race_trait_codes(race), empire.research_levels)
            if (best_scanner is not None
                    and best_scanner.scan_range_normal
                    > home_star.scan_range):
                home_star.scanner_type = best_scanner.name
                home_star.scan_range = best_scanner.scan_range_normal
                home_star.pen_scan_range = \
                    best_scanner.scan_range_penetrating
            best_defense = best_defense_type(
                empire.research_levels, race_trait_codes(race))
            if best_defense != "None":
                home_star.defense_type = best_defense

            # Spend leftover advantage points on the homeworld
            # (StarMapInitialiser.cs:466)
            self._adjust_homeworld_leftover_points(home_star, race)

            # Starting fleets: scout and loaded colony ship
            for fleet in self._create_starting_fleets(empire, home_star, race):
                empire.owned_fleets[fleet.key] = fleet

            # Homeworld starbase (dock, refuel, defense) as in the original
            starbase = self._create_starbase(empire, home_star)
            empire.owned_fleets[starbase.key] = starbase
            home_star.starbase_key = starbase.key

        # Pre-register every opponent with an Enemy relation
        # (GameInitialiser.cs:132-143). EmpireIntel copies id/race name
        # (EmpireIntel.cs:46-51); Relation defaults to enum member 0 =
        # Enemy (EmpireData.cs:34-39) and is set explicitly at init
        # (GameInitialiser.cs:140). Because all empires are registered
        # here, there is no "newly met" case - as in C#.
        for wolf in server_data.all_empires.values():
            for lamb in server_data.all_empires.values():
                if wolf.id == lamb.id:
                    continue
                wolf.empire_reports[lamb.id] = {
                    "id": lamb.id,
                    "race_name": lamb.race_name,
                    "relation": "Enemy",
                    "designs": {},
                }

        return server_data

    def _generate_stars(self, width: int, height: int) -> List[Star]:
        """
        Generate the galaxy's stars on a clustered density field.

        Placement is delegated to star_field: seeded value-noise fBm
        supplies the density field and variable-radius Poisson-disk
        sampling (Bridson) lays the stars down on it, so the galaxy
        clumps into loose clusters without dense knots or empty deserts.
        Replaces the earlier centre-weighted Gaussian mixture, whose
        radial bias made corner starts structurally poor.

        Args:
            width: Galaxy width in light years.
            height: Galaxy height in light years.

        Returns:
            List of Star objects.
        """
        # Star count from the constant density, capped by the name pool
        area = width * height
        num_stars = area // (STAR_DENSITY * STAR_DENSITY)
        num_stars = max(20, min(num_stars, len(STAR_NAMES)))

        available_names = list(STAR_NAMES)
        self.rng.shuffle(available_names)

        # The density field is keyed on the game seed; an unseeded game
        # draws its field seed from the rng so two such games do not
        # share one galaxy shape
        field_seed = (self.seed if self.seed is not None
                      else self.rng.randrange(2 ** 31))
        positions = star_field.generate_positions(
            width, height, num_stars, STAR_MARGIN, field_seed, self.rng)

        stars = []
        for x, y in positions:
            if not available_names:
                break
            star = Star()
            star.name = available_names.pop()
            star.position = NovaPoint(x, y)

            # Random habitability values (0-100)
            star.gravity = self.rng.randint(0, 100)
            star.temperature = self.rng.randint(0, 100)
            star.radiation = self.rng.randint(0, 100)
            # Pristine environment mirror (Star.cs:64-66)
            star.original_gravity = star.gravity
            star.original_temperature = star.temperature
            star.original_radiation = star.radiation

            # Random mineral concentrations (1-100)
            star.ironium_concentration = self.rng.randint(1, 100)
            star.boranium_concentration = self.rng.randint(1, 100)
            star.germanium_concentration = self.rng.randint(1, 100)

            # Assign spectral class based on astronomical distribution
            self._assign_spectral_class(star)

            stars.append(star)

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

    def _generate_storms(self, width: int, height: int,
                         nebula_field=None) -> List[GalacticStorm]:
        """
        Generate roaming galactic storms scaled to universe size.

        Web extension - not in original Stars!. Storms drift each turn
        and hazard ships caught inside them. Roughly 70% of storms
        spawn inside nebulae (capped rejection sampling against the
        nebula density field) and each storm gets an irregular blob
        perimeter sampled deterministically from the game seed (user
        directive 2026-07-13).
        """
        area = width * height
        count = max(1, area // 160000)  # tiny/small 1, medium 2, large 4, huge 6
        # Blob shapes and nebula-bias placement draw on a dedicated
        # seed-derived stream so self.rng consumption stays identical
        # to the pre-blob generator (star placement, homeworlds and
        # wormholes keep their seeded geometry)
        storm_rng = random.Random(self.seed)
        storms = []
        for i in range(count):
            angle = self.rng.random() * math.pi * 2
            speed = 4.0 + self.rng.random() * 6.0  # 4-10 ly per turn
            x = self.rng.random() * width
            y = self.rng.random() * height
            if nebula_field is not None and storm_rng.random() < 0.7:
                # Prefer a center inside a nebula; the last sample
                # stands if none qualifies within the cap
                for _ in range(30):
                    if nebula_field.get_density_at(x, y) > 0.0:
                        break
                    x = storm_rng.random() * width
                    y = storm_rng.random() * height
            storm = GalacticStorm(
                key=i + 1,
                x=x,
                y=y,
                radius=25.0 + self.rng.random() * 30.0,
                velocity_x=math.cos(angle) * speed,
                velocity_y=math.sin(angle) * speed,
                intensity=0.3 + self.rng.random() * 0.7,
            )
            storm.generate_shape(storm_rng)
            storms.append(storm)
        return storms

    WORMHOLE_NAMES = ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"]

    def _generate_wormholes(self, width: int, height: int) -> List[Wormhole]:
        """
        Generate wormhole pairs scaled to universe size.

        Endpoints are placed far apart (at least a third of the
        universe width) so transit is worth the risk of the unknown.
        """
        area = width * height
        count = min(len(self.WORMHOLE_NAMES), max(1, area // 250000))
        wormholes = []
        for i in range(count):
            for _ in range(20):  # retry until endpoints are far apart
                x1 = self.rng.random() * width
                y1 = self.rng.random() * height
                x2 = self.rng.random() * width
                y2 = self.rng.random() * height
                if math.hypot(x2 - x1, y2 - y1) >= width / 3:
                    break
            wormholes.append(Wormhole(
                key=i + 1,
                name=f"Wormhole {self.WORMHOLE_NAMES[i]}",
                x1=x1, y1=y1, x2=x2, y2=y2,
                stability=0.3 + self.rng.random() * 0.7,
            ))
        return wormholes

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
            race.icon = template.get("icon", 0)
            race.primary_trait = template.get("prt", "JOAT")

            # Default habitability ranges (centered, wide range)
            race.gravity_min = 15
            race.gravity_max = 85
            race.temperature_min = 15
            race.temperature_max = 85
            race.radiation_min = 15
            race.radiation_max = 85

            race.growth_rate = 15  # 15% base growth
            race.colonists_per_resource = 1000  # 1000 colonists = 1 resource
            race.factory_production = 10
            race.factory_cost = 10
            race.mine_cost = 5
            race.mine_production_rate = 10

            races.append(race)

        return races

    # Neighborhood radius for the homeworld fairness constraint - the
    # run100 forensic metric, kept at two mean star spacings so it
    # tracks the board density (2 * STAR_DENSITY; 50 ly before the
    # 2026-07-28 enlargement, 100 ly after it)
    HOMEWORLD_NEIGHBORHOOD_RADIUS = 2 * STAR_DENSITY

    def _select_home_worlds(self, stars: List[Star], player_count: int,
                            width: int, height: int) -> List[Star]:
        """
        Select home worlds for players with a fairness constraint.

        Documented web deviation from C#: StarMapGenerator.cs places
        homeworlds FIRST by rejection sampling over a UNIFORM density
        field with enforced minimum separation (Generate 93-106,
        SetHomeworldReducer 156-172, PlaceHomeworlds 215-238), so
        every homeworld gets a statistically equivalent neighborhood -
        fairness is structural. The web keeps its clustered star field
        for the galaxy aesthetic and delivers the same guarantee by
        SELECTION instead of construction (DEF-16): every homeworld
        must have a minimum number of neighbor stars within
        HOMEWORLD_NEIGHBORHOOD_RADIUS (comparable expansion prospects)
        and homeworlds must be mutually separated by the C#-derived
        minimum min(width, height) / (2 * (floor(sqrt(players)) + 1))
        (StarMapGenerator.cs:160-163; 175 ly for 2 players on a 700
        map). Constraints relax stepwise on dense-candidate shortage
        so selection always terminates (tiny maps). The clustered field
        is statistically homogeneous, so unlike the old centre-weighted
        mixture it does not work against this bound.

        Args:
            stars: All stars in galaxy.
            player_count: Number of players.
            width: Universe width in light years.
            height: Universe height in light years.

        Returns:
            List of home world stars.
        """
        if len(stars) < player_count:
            raise ValueError("Not enough stars for all players")

        # Neighborhood counts: stars within the fairness radius
        radius_sq = self.HOMEWORLD_NEIGHBORHOOD_RADIUS ** 2
        counts: Dict[str, int] = {}
        for star in stars:
            counts[star.name] = sum(
                1 for other in stars
                if other is not star
                and (star.position.x - other.position.x) ** 2
                + (star.position.y - other.position.y) ** 2 <= radius_sq
            )

        # Minimum viable neighborhood: half the median count, floored
        # at 3 - guarantees every start a comparable-by-floor
        # expansion neighborhood
        sorted_counts = sorted(counts.values())
        median_count = sorted_counts[len(sorted_counts) // 2]
        n_min = max(3, math.ceil(0.5 * median_count))

        # C#-derived mutual separation (StarMapGenerator.cs:160-163)
        player_factor = int(math.floor(math.sqrt(player_count))) + 1
        min_sep = min(width, height) / (2 * player_factor)

        def candidates_for(threshold: int) -> List[Star]:
            return [s for s in stars if counts[s.name] >= threshold]

        def min_dist_to(star: Star, chosen: List[Star]) -> float:
            return min(
                math.sqrt((star.position.x - s.position.x) ** 2
                          + (star.position.y - s.position.y) ** 2)
                for s in chosen
            )

        def pick_next(chosen: List[Star],
                      candidates: List[Star]) -> Optional[Star]:
            """Farthest-point pick among candidates, honoring the
            separation floor with a 0.9-stepwise relaxation ladder
            (floor at half the C# separation)."""
            sep = min_sep
            while sep >= 0.5 * min_sep:
                best_star = None
                best_dist = -1.0
                for star in candidates:
                    if star in chosen:
                        continue
                    dist = min_dist_to(star, chosen)
                    if dist < sep:
                        continue
                    # Deterministic tie-break by name
                    if (dist > best_dist
                            or (dist == best_dist and best_star is not None
                                and star.name < best_star.name)):
                        best_dist = dist
                        best_star = star
                if best_star is not None:
                    return best_star
                sep *= 0.9
            return None

        candidates = candidates_for(n_min)
        if not candidates:
            candidates = list(stars)

        # Player 1: seeded choice among dense candidates (one rng draw,
        # as the previous quadrant pick, so downstream homeworld
        # mineral draws stay aligned)
        selected = [self.rng.choice(candidates)]

        for _ in range(1, player_count):
            best_star = None
            # Relax the density floor stepwise before giving up on it
            for threshold in range(n_min, 0, -1):
                best_star = pick_next(selected, candidates_for(threshold))
                if best_star is not None:
                    break
            if best_star is None:
                # Tiny-map fallback: plain farthest-point over all
                # stars (the pre-DEF-16 rule, always terminates)
                best_star = max(
                    (s for s in stars if s not in selected),
                    key=lambda s: (min_dist_to(s, selected), s.name)
                )
            selected.append(best_star)

        # Make home worlds habitable (centered values)
        for star in selected:
            star.gravity = 50
            star.temperature = 50
            star.radiation = 50
            # Pristine environment mirror (Star.cs:64-66)
            star.original_gravity = 50
            star.original_temperature = 50
            star.original_radiation = 50
            # Good mineral concentrations, 50-100% each
            # (PrepareResources, StarMapInitialiser.cs:313-315)
            star.ironium_concentration = self.rng.randint(50, 100)
            star.boranium_concentration = self.rng.randint(50, 100)
            star.germanium_concentration = self.rng.randint(50, 100)

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
        from .ship_specs import make_starting_designs

        empire = EmpireData()
        empire.id = empire_id
        empire.race = race
        empire.race_name = race.name
        empire.turn_year = STARTING_YEAR

        # Starting tech levels by PRT
        # (GameInitialiser.cs ProcessPrimaryTraits, lines 187-254)
        empire.research_levels = TechLevel()
        prt = race.primary_trait
        if prt == "SS":
            empire.research_levels.levels["Electronics"] = 5
        elif prt == "WM":
            empire.research_levels.levels["Propulsion"] = 1
            empire.research_levels.levels["Energy"] = 1
        elif prt == "CA":
            empire.research_levels.levels["Weapons"] = 1
            empire.research_levels.levels["Propulsion"] = 1
            empire.research_levels.levels["Energy"] = 1
            empire.research_levels.levels["Biotechnology"] = 6
        elif prt == "SD":
            empire.research_levels.levels["Propulsion"] = 2
            empire.research_levels.levels["Biotechnology"] = 2
        elif prt == "PP":
            empire.research_levels.levels["Energy"] = 4
        elif prt == "IT":
            empire.research_levels.levels["Propulsion"] = 5
            empire.research_levels.levels["Construction"] = 5
        elif prt == "AR":
            empire.research_levels.levels["Energy"] = 1
        elif prt == "JOAT":
            empire.research_levels = TechLevel.from_level(3)
        # HE and IS start with no tech

        # LRT starting tech (GameInitialiser.cs ProcessSecondaryTraits)
        if race.has_trait("IFE"):
            # Propulsion tech starts one level higher
            # (GameInitialiser.cs:267-275)
            empire.research_levels.levels["Propulsion"] += 1
        if race.has_trait("ExtraTech"):
            # "Start at Tech 3" checkbox (pseudo-trait, not a normal
            # LRT). C# Nova boosts ALL six fields - +1 for JOAT, +3
            # otherwise (GameInitialiser.cs:355-376) - deviating from
            # canonical Stars! "expensive fields only start at 3"; we
            # port the C# code.
            boost = 1 if prt == "JOAT" else 3
            for key in empire.research_levels.levels:
                empire.research_levels.levels[key] += boost

        # Research allocation (even distribution)
        empire.research_budget = 15  # 15% of resources to research
        empire.research_topics = TechLevel.from_level(1)

        # Home star ownership
        empire.owned_stars[home_star.name] = home_star

        # Starting ship designs
        make_starting_designs(empire)

        # Default battle plan: Attack="Enemies" (BattlePlan.cs:44);
        # combined with the all-Enemy relation init
        # (GameInitialiser.cs:140) fresh games behave as before, and
        # player relation changes now govern battle eligibility
        from ..server.battle.battle_plan import (
            BattlePlan, DEFAULT_EMPIRE_PLAN, seed_admiralty_plans)
        empire.battle_plans["Default"] = BattlePlan(attack="Enemies")
        # The six admiralty standard plans ship in every empire's plan
        # list - they ARE the doctrine, there is no separate doctrine
        # object - and a fresh empire hands newly built fleets the
        # Balanced one
        seed_admiralty_plans(empire.battle_plans)
        empire.default_battle_plan = DEFAULT_EMPIRE_PLAN

        return empire

    def _adjust_homeworld_leftover_points(self, star: Star, race: Race) -> None:
        """
        Spend leftover race-design advantage points on the homeworld.

        Port of: HomeStarLeftoverpointsAdjuster.cs Adjust (lines 12-82).
        The budget is clamped to [0, 50] as in Race.cs
        GetLeftoverAdvantagePoints (lines 215-221).
        """
        points = max(0, min(50, race.leftover_points))
        if points == 0:
            return

        target = race.leftover_point_target
        if target == "Mineral concentration":
            # 1% for three points for the poorest mineral; poorest picked
            # by the nested compares (HomeStarLeftoverpointsAdjuster.cs:22-48)
            additional = points // 3
            conc = star.mineral_concentration
            if conc.boranium > conc.germanium:
                if conc.germanium > conc.ironium:
                    conc.ironium += additional
                else:
                    conc.germanium += additional
            else:
                if conc.boranium > conc.ironium:
                    conc.ironium += additional
                else:
                    conc.boranium += additional
        elif target == "Mines":
            # one mine for two points (lines 49-53)
            star.mines += points // 2
        elif target == "Factories":
            # one factory for five points (lines 54-58)
            star.factories += points // 5
        elif target == "Defenses":
            # one defense for ten points (lines 59-63)
            star.defenses += points // 10
        else:
            # "Surface minerals" and any unknown target (lines 64-81):
            # 10 kT per point, distribution weighted for the rarest
            # surface minerals
            total = points * 10
            germanium = max(1, star.resources_on_hand.germanium)
            boranium = max(1, star.resources_on_hand.boranium)
            ironium = max(1, star.resources_on_hand.ironium)
            dividend = float(boranium + germanium + ironium)
            factor_boranium = dividend / boranium
            factor_germanium = dividend / germanium
            factor_ironium = dividend / ironium
            distributed_total = (factor_boranium + factor_germanium
                                 + factor_ironium)
            star.resources_on_hand.boranium += int(
                round(factor_boranium / distributed_total * total))
            star.resources_on_hand.germanium += int(
                round(factor_germanium / distributed_total * total))
            star.resources_on_hand.ironium += int(
                round(factor_ironium / distributed_total * total))

    # Per-PRT starting fleet composition, as (design name, count) pairs.
    # C# implements only the HE 3x mini-colony-ship and the universal
    # single scout (StarMapInitialiser.cs AllocateHomeStarOrbitalInstallations,
    # lines 363-420); the remaining per-PRT extras are canonical Stars!
    # rules that the C# reference leaves as comments only
    # (GameInitialiser.cs:192-248).
    PRT_STARTING_FLEETS = {
        "HE": [("Armed Probe", 1), ("Spore Cloud", 3)],
        "SS": [("Long Range Scout", 1), ("Santa Maria", 1)],
        "WM": [("Armed Probe", 1), ("Santa Maria", 1)],
        # CA orbital-terraformer is comment-only in C#
        # (GameInitialiser.cs:206-212); scout + colony ship instead
        "CA": [("Long Range Scout", 1), ("Santa Maria", 1)],
        "IS": [("Long Range Scout", 1), ("Santa Maria", 1)],
        "SD": [("Long Range Scout", 1), ("Santa Maria", 1),
               ("Little Hen", 1), ("Speed Turtle", 1)],
        # PP second starting planet in a non-tiny universe is not
        # implemented in C# either (comment only)
        "PP": [("Shielded Scout", 2), ("Santa Maria", 1)],
        # IT second planet with 100/250 stargates is not implemented
        # in C# either (comment only)
        "IT": [("Long Range Scout", 1), ("Santa Maria", 1),
               ("Stalwart Defender", 1), ("Swashbuckler", 1)],
        # AR colonize-to-orbit semantics are a separate gap; the AR
        # colonizer difference in C# is the Orbital Construction Module
        # (StarMapInitialiser.cs:155-158)
        "AR": [("Long Range Scout", 1), ("Santa Maria", 1)],
        "JOAT": [("Long Range Scout", 2), ("Santa Maria", 1),
                 ("Teamster", 1), ("Cotton Picker", 1),
                 ("Stalwart Defender", 1)],
    }

    def _create_starting_fleets(
        self,
        empire: EmpireData,
        home_star: Star,
        race: Race
    ) -> List[Fleet]:
        """
        Create starting fleets for an empire, by primary racial trait.

        C# reference implements the universal scout + colony ship (3x
        mini-colony for HE); the per-PRT extras follow the canonical
        Stars! table left as comments in GameInitialiser.cs:192-248.

        Args:
            empire: Empire receiving the fleets.
            home_star: Home world.
            race: Race definition.

        Returns:
            List of starting fleets.
        """
        from .ship_specs import find_design, make_token
        from ..core.data_structures.cargo import Cargo

        composition = list(self.PRT_STARTING_FLEETS.get(
            race.primary_trait, self.PRT_STARTING_FLEETS["JOAT"]))
        if race.has_trait("ARM"):
            # ARM: "Start the game with two midget miners" - TODO comment
            # in C# (GameInitialiser.cs:282-286); Cotton Picker mini-miner
            # stands in for the midget miner
            composition.append(("Cotton Picker", 2))

        fleets: List[Fleet] = []
        for design_name, count in composition:
            design = find_design(empire, design_name)
            for i in range(count):
                fleet = Fleet()
                fleet.key = empire.get_next_fleet_key()
                fleet.name = f"{design_name} #{i + 1}"
                fleet.position = NovaPoint(
                    home_star.position.x, home_star.position.y)
                fleet.in_orbit_name = home_star.name
                token = make_token(design)
                fleet.tokens[token.design_key] = token
                fleet.fuel_available = fleet.total_fuel_capacity
                if design.can_colonize:
                    # Colony ships launch pre-loaded with colonists up
                    # to their cargo capacity (25 kT Santa Maria,
                    # 10 kT Spore Cloud)
                    fleet.cargo = Cargo(
                        colonists_in_kilotons=design.cargo_capacity)
                fleets.append(fleet)

        return fleets

    def _create_starbase(self, empire: EmpireData, home_star: Star) -> Fleet:
        """Create the homeworld starbase fleet."""
        from .ship_specs import find_design, make_token

        design = find_design(empire, "Starbase")
        base = Fleet()
        base.key = empire.get_next_fleet_key()
        base.name = "Starbase"
        base.position = NovaPoint(home_star.position.x, home_star.position.y)
        base.in_orbit_name = home_star.name
        token = make_token(design)
        base.tokens[token.design_key] = token
        base.fuel_available = 0
        return base


