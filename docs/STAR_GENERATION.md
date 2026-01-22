# Star Generation and Rendering

Stars Nova Web generates and renders stars using astronomical models for realistic galaxy visualization.

## Star Distribution

Stars are distributed using a Gaussian Mixture Model (GMM) that creates natural-looking galaxy structures.

### GMM Components

The galaxy generator (`backend/services/galaxy_generator.py`) uses weighted components:

| Component | Weight | Shape | Purpose |
|-----------|--------|-------|---------|
| Central Core | 15% | Circular | Dense galactic center |
| Main Band | 35% | Elongated ellipse (1.5-2.5x stretch) | Primary galactic structure |
| Star Clusters | 8% each (2-5 clusters) | Compact groups | Local stellar concentrations |
| Star Streams | 6% each (1-3 streams) | Very elongated | Band-like structures |
| Outer Halo | 10% | Diffuse | Background star field |

### Sampling Algorithm

```
1. Select component by cumulative weight
2. Sample (x, y) from 2D Gaussian with component parameters
3. Apply rotation transform for elongated components
4. Reject if inside void region (2-5 voids per galaxy)
5. Reject if too close to existing star (minimum distance check)
```

### Minimum Distance Constraint

Stars maintain separation based on density setting:
- `min_distance = STAR_DENSITY * 0.6`
- Prevents unrealistic clustering while allowing natural groupings

## Spectral Classification

Stars are assigned spectral types following the Initial Mass Function (IMF) distribution.

### Spectral Class Distribution

| Class | Temperature | Color | Weight | Description |
|-------|-------------|-------|--------|-------------|
| O | 30,000-50,000K | Blue | 1% | Hot massive stars |
| B | 10,000-30,000K | Blue-white | 4% | Hot stars |
| A | 7,500-10,000K | White | 6% | White stars |
| F | 6,000-7,500K | Yellow-white | 10% | Warm stars |
| G | 5,200-6,000K | Yellow | 15% | Sun-like stars |
| K | 3,700-5,200K | Orange | 20% | Cool stars |
| M | 2,400-3,700K | Red-orange | 40% | Red dwarfs (most common) |

### Luminosity Classes

Each spectral type includes luminosity variants:
- **V** (Main Sequence) - Standard hydrogen-burning stars
- **III** (Giants) - Evolved stars with expanded envelopes
- **I** (Supergiants) - Massive evolved stars

### Assignment Algorithm

```python
def _assign_spectral_class(star, seed):
    # Select from weighted distribution
    spectral_class = weighted_random(SPECTRAL_CLASSES, seed)

    # Assign temperature within class range
    star.star_temperature = random_in_range(class.temp_min, class.temp_max)

    # Calculate radius based on luminosity class
    star.star_radius = base_radius * luminosity_factor
```

## Star Rendering

Stars render on the galaxy map canvas (`frontend/js/views/galaxy-map.js`) with colors based on spectral classification.

### Color Palette

```javascript
STAR_COLORS = {
    'O': { r: 155, g: 176, b: 255 },  // Blue
    'B': { r: 170, g: 191, b: 255 },  // Blue-white
    'A': { r: 202, g: 215, b: 255 },  // White
    'F': { r: 248, g: 247, b: 255 },  // Yellow-white
    'G': { r: 255, g: 244, b: 232 },  // Yellow (Sun-like)
    'K': { r: 255, g: 210, b: 161 },  // Orange
    'M': { r: 255, g: 180, b: 100 }   // Red-orange
}
```

### Rendering Logic

```
For each star:
  1. Transform world coordinates to screen coordinates
  2. Determine base radius (3-6 pixels based on zoom)
  3. If uncolonized:
     - Use spectral color from STAR_COLORS
     - Add radial glow for hot/large stars (O, B, A classes)
  4. If colonized:
     - Use ownership color (green=player, red=enemy)
     - Draw ownership ring around star
  5. Optionally render star name label
```

### Visual Effects

- **Hot star glow**: O, B, A class stars get radial gradient glow
- **Size variation**: Larger radius multiplier for giant/supergiant luminosity classes
- **Ownership indicators**: Colored rings for colonized planets

## Data Flow

```
Galaxy Generation (Backend)
    │
    ├── GMM sampling for positions
    ├── Spectral class assignment
    ├── Store in Star objects
    │
    ▼
API Response
    │
    ├── StarSummary includes spectral_class, star_temperature
    │
    ▼
Frontend Rendering
    │
    ├── GalaxyMap.renderStar()
    ├── Color lookup from STAR_COLORS
    └── Canvas drawing with effects
```

## Files

- `backend/services/galaxy_generator.py` - Star generation with GMM and spectral assignment
- `backend/core/game_objects/star.py` - Star data model
- `backend/api/routes/stars.py` - API endpoints and Pydantic models
- `frontend/js/views/galaxy-map.js` - Canvas rendering with spectral colors
