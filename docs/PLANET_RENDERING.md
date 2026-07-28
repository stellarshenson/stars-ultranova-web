# Planet Rendering

`PlanetArt` (`frontend/js/views/planet-art.js`) draws every world in the star panel from its environment values alone - no image assets, no WebGL, Canvas 2D only. It replaced a renderer whose worlds differed by hue and rotation and nothing else; the design brief and its sources are in `docs/research-planet-rendering.md`.

## Pipeline

Six stages, run once per world and cached. All the expensive work lives in a single per-pixel loop; everything after it is a handful of draw calls.

- **Cache probe** - `cache` is an LRU keyed by star id, environment and canvas size; a hit is a `drawImage` and nothing else
- **Classify and seed** - nine classes selected from the environment, then a `mulberry32` RNG seeded off the star id draws every per-world parameter in fixed order, so a world looks identical on every visit
- **Surface pass** - one `ImageData` loop over the disc; per pixel the sphere normal is computed, rotated by axial tilt and rotation phase, then the class branches once into the rocky or the gas evaluator
- **Lighting** - in the same loop, no second pass: Minnaert limb darkening, a smoothstep terminator, water and ice specular, and emissive terms on the night side
- **Composite** - draw calls only: cloud billows, the atmospheric limb ring, radiation halo, grain and vignette
- **Cache store**

## Surface generation

Sampling is **3D noise at the sphere normal**, not 2D noise through a latitude/longitude conversion. That eliminates the equirectangular seam and the pole pinch outright, and costs nothing extra because it drops the `asin` and `atan2` calls.

- **Base terrain** - one-level domain-warped fBm, 5-6 octaves, per-world Hurst exponent
- **Redistribution** - the height field is raised to a per-world exponent, which is what separates flat basins from jagged worlds
- **Ridges** - ridged multifractal masked above sea level; the class picks its ridge mode - `mountain`, `canyon`, `fissure` or `none`
- **Craters** - Worley cellular noise, used by barren and radiated classes
- **Moisture** - a second decorrelated fBm at a different offset
- **Colour** - a **two-axis** lookup on (elevation, moisture) in the class palette, then blended toward the class cold colour past the world's ice latitude. The old renderer's single temperature ramp is what made every world look the same
- **Gas giants** - a separate evaluator: latitude warped by domain-warped turbulence, band-ramp lookup, fine shear streaks, analytic storm ovals with swirled interiors. Band count falls out of the latitude scale factor

## Classes

Nine classes, selected in this order - first match wins. Thresholds are on the game's 0-100 environment scales.

| Class | Selected by | Visual signature |
|---|---|---|
| `gas` | gravity ≥ 88 | warped latitude bands, storm ovals, broad soft penumbra, strong limb ring |
| `toxic` | radiation > 80 and temp ≥ 78, or radiation > 70 | featureless cream-yellow cloud deck, limb brightening, sickly tint at extreme radiation |
| `volcanic` | temp ≥ 72 | dark basaltic base, emissive fissure network glowing on the night side |
| `radiated` | radiation > 80 and temp < 40 | crater field with a magenta-shifted palette, radiation halo retained |
| `ice` | temp < 22 | near-white high-albedo field, Worley cell-border cracks, caps merging toward the equator |
| `barren` | gravity < 30 | multi-scale craters with raised rims, dark mare patches, knife-edge terminator |
| `desert` | temp ≥ 58 | no sea level, ridged canyon network, ochre through rust, dust haze flattening limb contrast |
| `tundra` | temp < 42 | low sea level, caps to ~35 degrees latitude, taiga greens and greys |
| `terran` | habitability ≥ 40 | fractal coastlines, deep blue with a lighter shelf, green and tan continents, decorrelated clouds |

Habitability is taken from the star when present; otherwise it is derived from the distance of gravity, temperature and radiation from the ideal.

## Per-world variation

Eleven parameters are drawn from the seeded RNG, which is why two worlds with identical temperature, radiation and gravity still look different: `axialTilt`, `rotationPhase`, `lightAngle`, `cloudCover`, `seaLevel`, `iceLatitude`, `mountainStrength`, `redistExponent`, `craterDensity`, `bandCount`, `storms`.

- **`rotationPhase` is the cheapest diversity in the renderer** - only half the sphere is visible, so a phase change shows a completely different face of the same noise field at zero cost
- **Colonised worlds** additionally get night-side city lights, scaled by population

## Sphere silhouette

Three geometry rules keep the disc reading as a sphere. Each was learned by breaking it; all three failure modes were caught in review.

- **Ambient rises toward the limb** - `ambient = 0.05 + 0.06(1 − nz)²`. A flat 6% floor left the night limb of a dark world at ~4/255, indistinguishable from the background, so the silhouette vanished on the unlit side and the planet read as two mismatched circles. Grazing angles scatter more starlight, so this is physical as well as necessary
- **The limb ring is concentric** - an offset gradient centre makes the bright band an off-centre circle whose curvature disagrees with the planet's edge; the eye reads that as a potato. The day/night crescent is applied by masking the ring offscreen with `destination-in`, which changes its brightness without touching its geometry
- **No hard inner boundary** - clipping the ring to an annulus, or fading it to zero before the limb, draws a second visible circle inside the first. The profile peaks at the limb and decays inward; the disc's own one-pixel alpha feather finishes the outer edge

Verification is by measurement, not eye: walking rays outward from the centre and recording the last radius where alpha ≥ 200 must give the same radius on every ray.

## Performance

Measured in-browser via `performance.now`, reported per world in the preview harness.

- **10-21 ms per world** at 300x230, the one-off cost before caching
- **Budget headroom** - the researched benchmark put one-level domain warping at 5-6 octaves at 4.6-5.0 ms; the remainder is the composite pass and the class-specific terms
- **Cached thereafter** - LRU keyed by star id, environment and size, so re-selecting a star costs one `drawImage`
- **Scratch canvas reused** - the offscreen used for ring masking is allocated once and grown on demand, never per world

## Preview harness

`frontend/preview-planets.html` renders the twelve reference environments plus four same-environment-different-star pairs, with no game state and no API calls. It is the sheet used for visual review and is not part of the application's script list.
