# Nebula Generation and Rendering

Stars Nova Web renders nebulae using a dual-layer system separating gas nebulae from dust clouds, based on astronomical observations.

## Astronomical Background

Real nebulae fall into distinct categories with different visual properties:

### Gas Nebulae

Ionized hydrogen clouds illuminated by nearby hot stars:
- **Emission Nebulae (H-II Regions)**: Hydrogen gas ionized by O/B stars emits characteristic pink/red (H-alpha 656nm) and teal (O-III 500nm) light
- **Reflection Nebulae**: Dust scatters blue light from nearby stars via Rayleigh scattering

### Dust Clouds

Dense molecular clouds that absorb and block light:
- **Dark Nebulae**: Cold clouds silhouetted against brighter backgrounds
- **Absorption Regions**: Block starlight, creating voids in star fields
- **Warm Edges**: Heated dust at boundaries emits infrared (rendered as amber glow)

## Backend Generation

Nebulae are generated in `backend/services/galaxy_generator.py` and stored in `NebulaField`.

### Region Placement

```
1. Find star clusters using spatial binning
2. Place emission nebulae centered on clusters (stars embedded in gas)
3. Find void regions (areas with no stars)
4. Place dark nebulae in voids (blocking light)
5. Add connecting filaments between regions
```

### Data Structure

```python
@dataclass
class NebulaRegion:
    x: float                    # Center X coordinate
    y: float                    # Center Y coordinate
    radius_x: float             # Semi-major axis
    radius_y: float             # Semi-minor axis
    rotation: float             # Rotation angle (radians)
    density: float              # 0.0-1.0 opacity factor
    nebula_type: str            # 'emission', 'reflection', 'dark', 'diffuse'

@dataclass
class NebulaField:
    regions: List[NebulaRegion]
    density_grid: Dict[str, float]  # Spatial lookup for warp effects
```

### Density Lookup

The `NebulaField` provides density queries for gameplay effects:
- `get_density_at(x, y)` - Point density using gaussian falloff
- `get_average_density_along_path(x1, y1, x2, y2)` - Path integral for warp speed calculations

## Frontend Rendering

Nebulae render as SVG paths in `frontend/js/views/nebula-svg.js` with separate layers for dust and gas.

### Layer Structure

```
SVG Container (#nebula-layer)
    │
    ├── <defs> - Blur filters
    │
    ├── <g id="dust-clouds"> - Renders first (behind)
    │   └── Dark nebulae with sharp edges
    │
    └── <g id="gas-nebulae"> - Renders on top
        └── Emission/reflection with soft edges
```

### Color Palettes

```javascript
palettes: {
    emission: {
        primary:   { r: 200, g: 70, b: 130 },   // H-alpha pink
        secondary: { r: 80, g: 150, b: 170 },   // O-III teal
        tertiary:  { r: 160, g: 90, b: 150 },   // Mixed
        glow:      { r: 255, g: 180, b: 200 }   // Bright core
    },
    reflection: {
        primary:   { r: 70, g: 110, b: 190 },   // Scattered blue
        secondary: { r: 90, g: 130, b: 210 },
        tertiary:  { r: 60, g: 95, b: 170 }
    },
    dark: {
        primary:   { r: 8, g: 5, b: 15 },       // Cold core
        secondary: { r: 15, g: 10, b: 25 },     // Mid density
        tertiary:  { r: 25, g: 18, b: 35 },     // Outer
        edge:      { r: 60, g: 35, b: 25 }      // Warm IR glow
    }
}
```

### Blur Filters

Different blur levels create depth and soft boundaries:

| Filter | Blur (px) | Usage |
|--------|-----------|-------|
| gas-blur-heavy | 30 | Outer halo of gas nebulae |
| gas-blur-medium | 18 | Mid-layer gas |
| gas-blur-soft | 10 | Inner gas structure |
| gas-blur-light | 5 | Core detail |
| dust-blur-edge | 6 | Dust cloud edges |
| dust-blur-soft | 3 | Dust transitions |
| dust-blur-sharp | 1 | Dense dust cores |

## Gas Nebula Rendering

Gas nebulae use filamentary structures with soft boundaries.

### Filament Generation

```
generateGasFilaments(region, embeddedStars):
    1. Create 2-4 primary filaments using generateSubstantialSpine()
       - Correlated random walk with 0.85 momentum
       - Base width 12-32 pixels
       - 8-13 control points per spine

    2. Add branch filaments from primary spines
       - Perpendicular branching (Rayleigh-Taylor model)
       - Width 8-20 pixels

    3. Create pillar structures toward embedded stars
       - generatePillarToStar() interpolates toward star position
       - Width 15-25 pixels
```

### Spine Algorithm

```python
def generateSubstantialSpine(region, seed):
    points = []
    momentum = 0.85  # High momentum = persistent direction

    # Start from random position within region
    x, y = random_start_position(region)
    angle = direction_toward_center + random_variation

    for i in range(num_points):
        # Large consistent steps
        step = base_radius * (0.12 + random * 0.08)

        # Gentle curvature with momentum damping
        curvature = gaussian_random(0, 0.15)
        angle += curvature * (1 - momentum)

        x += cos(angle) * step
        y += sin(angle) * step
        points.append((x, y))

    return points
```

### Multi-Layer Rendering

Each filament renders with multiple opacity layers:

```javascript
layers = [
    { blur: 'gas-blur-heavy',  opacity: density * 0.025 },
    { blur: 'gas-blur-medium', opacity: density * 0.04 },
    { blur: 'gas-blur-soft',   opacity: density * 0.05 }
]
```

### Star-Forming Regions

Bright glowing regions around embedded stars:

```
renderStarFormingRegions(embeddedStars, region):
    For each star inside nebula:
        1. Calculate intensity based on distance from center
        2. Draw inner bright core with star-glow filter
        3. Draw outer diffuse glow with gas-blur-soft
```

## Dust Cloud Rendering

Dust clouds use sharper boundaries with defined edges.

### Shape Generation

```python
def createDustShape(region, seed, scale=1.0):
    points = []
    num_points = 10-16  # More angular than gas

    for i in range(num_points):
        angle = (i / num_points) * 2 * PI + rotation

        # Less smooth variation for sharper edges
        radius_var = 0.75 + random * 0.5

        # Occasional deep rifts (15% chance)
        if random > 0.85:
            radius_var *= 0.6

        points.append(polar_to_cartesian(angle, radius * radius_var))

    return bezier_path(points, smoothing=0.25)  # Less smoothing
```

### Three-Layer Structure

```
Layer 1: Main body (dust-blur-sharp, 70% opacity)
    └── Dense opaque core

Layer 2: Transition (dust-blur-soft, 40% opacity)
    └── Mid-density outer region

Layer 3: Warm edge (dust-blur-edge, 8% opacity)
    └── IR glow at heated boundaries
```

### Dense Knots

Internal structure within dust clouds:

```
renderDustKnots(region):
    For 2-4 knots:
        1. Position randomly within cloud
        2. Draw compact blob (8-23px radius)
        3. Apply dust-blur-sharp for defined edges
        4. High opacity (85% of region density)
```

## ViewBox Synchronization

The SVG viewBox syncs with canvas pan/zoom:

```javascript
updateViewBox(viewX, viewY, zoom, canvasWidth, canvasHeight) {
    const worldWidth = canvasWidth / zoom;
    const worldHeight = canvasHeight / zoom;
    svg.setAttribute('viewBox',
        `${viewX - worldWidth/2} ${viewY - worldHeight/2} ${worldWidth} ${worldHeight}`
    );
}
```

## Astronomical References

The rendering is based on observations of:

- **Orion Nebula (M42)**: H-II emission region with embedded star cluster
- **Horsehead Nebula**: Sharp dust cloud boundary against emission background
- **Carina Nebula**: Massive star-forming complex with pillars
- **Coal Sack**: Dark absorption nebula silhouette
- **Veil Nebula**: Filamentary supernova remnant structure
- **Crab Nebula**: Filaments from pulsar wind

## Files

- `backend/services/galaxy_generator.py` - Nebula region generation
- `backend/server/server_data.py` - NebulaRegion and NebulaField dataclasses
- `backend/api/routes/games.py` - `/api/games/{id}/nebulae` endpoint
- `frontend/js/views/nebula-svg.js` - SVG rendering with dual dust/gas model
- `frontend/index.html` - SVG container element
- `frontend/css/main.css` - Nebula layer positioning
