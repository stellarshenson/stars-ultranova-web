# Procedural Planet Rendering - Research

Research notes for replacing the current `star-panel.js` planet graphic, which draws every world as the same radial-gradient marble with vertical banding and a temperature-picked palette. Target surface is HTML5 Canvas 2D at roughly 300x230 px, no WebGL, no image assets, deterministic per star, budget of a few milliseconds.

## Overview

Procedural planets read as diverse when two things vary independently: the *structure* of the surface field (how noise is combined - smooth fBm for continents, ridged noise for mountain chains, cellular noise for craters, stretched-and-warped noise for gas bands) and the *mapping from that field to colour* (a two-axis elevation-by-moisture ramp modulated by latitude, not a single temperature ramp). Everything else - lighting, atmosphere, clouds - is polish that sells realism but does not by itself create variety; variety comes from giving each world a different noise recipe and a different colour ramp, then randomizing a dozen cheap per-world parameters on top.

## 1. Surface diversity - noise fields and how they become colour

### The base noise function

Value noise and gradient (Perlin) noise both work here. Simplex noise, presented by Ken Perlin in 2001, replaced classic Perlin noise to remove directional axis-aligned artifacts and reduce the per-sample cost from O(2^n) to O(n^2) in dimension n; Stefan Gustavson's "Simplex Noise Demystified" is the readable reference implementation. For a 300 px canvas in 2D and 3D the artifact difference is barely visible, and value noise with a smoothstep fade is roughly half the code and comparably fast. The practical recommendation is 3D value noise with a seeded 256-entry permutation table.

- **Permutation table** - shuffle `0..255` with the world's own seeded RNG, duplicate to 512 entries to avoid a modulo in the inner loop
- **Fade curve** - `u = t*t*(3-2*t)` is adequate; Perlin's Improved Noise uses `6t^5-15t^4+10t^3` because its second derivative is zero at t=0 and t=1, which removes artifacts on integer lattice values
- **3D over 2D** - sampling 3D noise directly at the sphere normal removes the equirectangular seam and the pole pinch entirely (see section 2)

### fBm and the Hurst exponent

Fractional Brownian motion sums octaves of noise at increasing frequency and decreasing amplitude. Inigo Quilez's fBm article gives the parameter that actually matters: gain `G = 2^-H` where `H` is the Hurst exponent in `[0,1]`, so `G` ranges over `[1.0, 0.5]`.

```
fbm(p, octaves, H):
    G = 2^-H;  f = 1.0;  a = 1.0;  t = 0.0
    for i in 0..octaves-1:
        t += a * noise(f * p)
        f *= 2.0        // lacunarity
        a *= G
    return t
```

- **H = 1.0 → G = 0.5** - smooth, isotropic, the classic "natural mountains" look
- **H = 0.5 → G ≈ 0.707** - rougher, brown-noise character
- **H = 0.0 → G = 1.0** - noisiest and wildest, pink noise

Varying `H` per world between about 0.6 and 1.0 is one of the cheapest and most effective diversity knobs available: the same octave count produces a smooth watery world or a jagged shattered one.

### Domain warping

This is the single highest-value technique in the list. Quilez's warping article defines it as replacing `f(p)` with `f(g(p))` where `g(p) = p + h(p)`, and gives the canonical two-level recipe with fixed decorrelating offsets:

```
q = vec2( fbm(p),                fbm(p + vec2(5.2, 1.3)) )
r = vec2( fbm(p + 4*q + vec2(1.7, 9.2)),
          fbm(p + 4*q + vec2(8.3, 2.8)) )
return fbm(p + 4*r)
```

One level of warping turns bland cloudy fBm into something with coastlines, estuaries and flow structure. Two levels give the swirled, marbled, organic look. The amplitude constant (4.0 in the article) is a per-world parameter: 0.5 gives gently perturbed continents, 4.0 gives heavy swirl suitable for gas giants and toxic worlds. Cost is linear in the number of fBm calls - one level costs 3x a plain fBm, two levels cost 7x.

### Ridged multifractal

Ridged noise creates sharp crests where the underlying noise crosses zero, which is what makes mountain ranges and lava fissures read correctly rather than as lumps. Musgrave introduced the basis as one minus the absolute value of the noise; The Book of Shaders states the three-step transform explicitly:

```
n = abs(n);        // fold - creases appear at the zero crossings
n = offset - n;    // invert so the creases point up (offset ~ 1.0)
n = n * n;         // sharpen the creases
```

The multifractal variant weights each octave by the previous octave's value (`weight = clamp(prev * weightMultiplier, 0, 1)`), which suppresses detail in the lowlands and concentrates it on the ridges. This is the standard formulation in Sebastian Lague-derived planet generators. Note: the exact `RidgidNoiseFilter.cs` source in the `SebLague/Procedural-Planets` repository could not be fetched (the path 404s and the repo's `Procedural Planet Noise` folder lists only `Noise.cs`), so the weight-multiplier detail here is from the general Musgrave literature rather than a verified file in that repository.

Practical use: compute smooth fBm for the base continent shape, compute ridged fBm separately, and add the ridged term masked to elevations above sea level - `h = base + ridged * smoothstep(seaLevel, seaLevel+0.25, base) * mountainStrength`. This keeps oceans flat and mountains sharp.

### Worley / cellular noise

Worley noise scatters feature points through space and returns the distance to the nearest (F1) or second-nearest (F2). It is the natural basis for craters, ice fractures and rock texture.

- **Craters** - `F1` alone produces concentric distance rings; the classic crater profile is a floor, a raised rim and a smooth blend outward, e.g. `crater(d) = max(floorDepth, min(rimHeight * (1 - |d - rimR| / rimW), 0))` blended with the base height
- **Cracks and lineae** - cell borders. `F2 - F1` is the naive test but produces uneven line widths because it is not a true distance; Quilez's Voronoi-edges article gives the correct two-pass method - find the closest seed, then in a second pass measure the perpendicular distance to the bisector between that seed and each neighbour, which yields uniform-width lines
- **Ice plates and flagstone** - `F1` quantized per cell, giving flat plates with visible boundaries

### From heightfield to colour

This is where the current renderer fails hardest. A single temperature-indexed palette guarantees that all cold worlds look identical. Red Blob Games' terrain-from-noise article gives the fix in three parts.

**Redistribution.** Raw fBm is roughly bell-distributed around 0.5, which gives too much mid-elevation. Raise it to a power: `e = pow(e * 1.2, exponent)` with exponent in 1..5. Higher exponents push mid elevations down into valleys while preserving peaks, which creates broad plains with isolated highlands rather than uniform lumpiness.

**A second independent field.** Generate moisture from a second fBm with a different seed offset. Two independent axes turn a 1D colour ramp into a 2D biome table, and that alone multiplies apparent variety.

**A biome lookup.** Red Blob's table, thresholded on elevation and moisture:

| Elevation | Moisture < 0.33 | 0.33 - 0.66 | > 0.66 |
|---|---|---|---|
| < 0.1 | Ocean | Ocean | Ocean |
| 0.1 - 0.3 | Temperate desert | Grassland | Forest |
| 0.3 - 0.6 | Temperate desert | Shrubland | Taiga |
| > 0.8 | Scorched | Tundra | Snow |

For a planet rather than a flat map, add latitude as a third input. The minimal useful version is a per-class palette of 5 to 7 stops indexed by elevation, with the stop colours shifted toward the class's cold colour by `smoothstep(iceLat, iceLat+0.12, |sin(lat)|)` and desaturated toward the dry colour by moisture. That is three cheap lerps per pixel and it is the difference between "green marble" and "a world".

## 2. Sphere projection on a 2D canvas

### The accurate method - per-pixel normal, ImageData

For an orthographic view of a sphere of radius `R` centred at `(cx, cy)`, every canvas pixel inside the disc maps directly to a surface normal:

```
dx = (px - cx) / R
dy = (py - cy) / R
d2 = dx*dx + dy*dy
if (d2 > 1) skip                 // outside the disc
nz = sqrt(1 - d2)                // N = (dx, dy, nz), already unit length
```

From the normal there are two ways to get a texture coordinate.

**Equirectangular sampling** rotates the normal by the world's axial tilt and rotation phase, then converts to spherical coordinates:

```
lat = asin(N.y)                  // -pi/2 .. pi/2
lon = atan2(N.x, N.z) + phase    // visible hemisphere spans pi
u = lon / PI,  v = lat / (PI/2)
h = fbm(u * bandScale, v * bandScale)
```

This costs two transcendental calls per pixel and reintroduces the two classic map problems: a seam at `lon = ±pi` and severe pinching at the poles. It is nonetheless the right choice for gas giants, because gas giants *want* a latitude coordinate - the bands are defined in `lat`.

**Direct 3D sampling** skips the projection entirely and evaluates 3D noise at the rotated normal:

```
N' = rotateY(rotateX(N, tilt), phase)
h  = fbm3(N'.x * scale, N'.y * scale, N'.z * scale)
```

No seam, no pole distortion, no `asin`/`atan2`. Latitude is still available for free as `N'.y`. This is the recommended path for all rocky classes. The extra cost is 3D noise (8 lattice corners instead of 4) versus the saved trigonometry - roughly a wash in practice.

**Rotation for free.** Because the visible hemisphere is only half the sphere, changing `phase` per world shows a completely different face of the same noise field at zero cost. This is the cheapest diversity knob in the entire document.

### Cheap alternatives

- **Pre-warped ellipse bands** - draw horizontal bands as ellipses whose half-width follows `R*sqrt(1-(y/R)^2)`, so the band edges hug the disc. Fast, works for gas giants, but the bands do not foreshorten toward the poles and the result looks like a striped disc rather than a sphere
- **Stereographic-style UV squash** - Deep-Fold's PixelPlanets `spherify` computes `z = sqrt(1 - dot(centered, centered))` then `sphere = centered / (z + 1)`, mapping a flat UV texture onto a convincing sphere in one expression. Useful if the texture is generated as a flat image first and then bent
- **Radial displacement of drawn shapes** - keep the existing composite-draw approach but push every drawn feature outward by `1/nz`, so blobs stretch toward the limb. Very cheap, but it cannot produce correct foreshortening of a continuous field
- **Concentric clipped arcs** - draw the whole texture as many thin arc slices, each `ctx.clip()`ed. Draw-call bound and slower than ImageData once the slice count is meaningful

### Cost and quality at 300 px

The full per-pixel method is affordable. I benchmarked it directly (Node 26.5.0, same V8 engine the browser uses) at 300x230 with `R = 100`, looping all 69,000 pixels with an early-out on the disc test so roughly 31,400 pixels are actually shaded, using 3D-free 2D value noise, equirectangular lookup and a Lambert term:

| Configuration | Time per frame |
|---|---|
| fBm 4 octaves, no warp | 1.82 ms |
| fBm 6 octaves, no warp | 2.25 ms |
| fBm 5 octaves, domain-warped (3 fBm calls) | 4.59 ms |
| fBm 6 octaves, domain-warped (3 fBm calls) | 5.04 ms |

Two-level warping (7 fBm calls) would land near 10 ms, which is the ceiling. One level of warping with 5 or 6 octaves is comfortably inside budget and is where the quality-per-millisecond curve peaks. Add roughly 0.3 ms for `putImageData` and the composite post-pass.

## 3. Planet class taxonomy and real references

Classes must differ in *generator*, not only in palette. What follows pairs each class with what the real object actually looks like, cited, so the results read as astronomy rather than as cartoon.

**Terrestrial / ocean.** Warped fBm continents against a flat sea level, ridged mountains masked to land, polar caps, a separate cloud octave. Earth is the reference; the key visual cues are that coastlines are fractal at every scale, that shallow shelf water is a distinctly lighter cyan than deep ocean, and that clouds are white and *decorrelated* from the coastlines.

**Desert.** No sea level. High-frequency, low-amplitude fBm, strong ridged component for canyon systems, dust-veil haze reducing contrast toward the limb. Mars is the reference: it is red because "iron minerals in the Martian dirt oxidize, or rust", but at ground level the palette is "browns, golds, and tans" rather than uniform red. Two features are worth caricaturing - Valles Marineris, a canyon system about 3,870 km long, up to 600 km wide and 9.3 km deep, and Olympus Mons, over 25 miles tall. Global dust storms periodically wash the whole disc to a flat ochre, which is a legitimate per-world variant.

**Ice / glacial.** High-albedo base, low colour variance, Worley cell borders as fracture lineae, broad caps merging near the equator, a strong specular response. Europa is the reference: a "light blue and brown surface marked by brown lines", geologically young and nearly crater-free, with ammonia-bearing compounds detected at the surface that may explain the reddish-brown staining along the cracks. The critical signature is the *linear* dark cracks over a bright, almost featureless field - noise alone will not produce this, Worley edges will.

**Tundra.** Terrestrial generator with sea level pushed low, ice caps pushed to roughly 35 degrees latitude, moisture ramp biased to taiga and shrubland greens and greys.

**Volcanic / lava.** Dark basaltic base with an emissive network in the cracks: invert the ridged field so the *valleys* glow, and composite the glow with `lighter` so it blooms. Io is the reference: "rust, tan, orange, and dark grayish-brown" from sulfur and sulfur dioxide frost, with "hundreds of volcanoes, some erupting lava fountains dozens of miles high", and - importantly - effectively no large impact craters, because volcanic resurfacing outpaces impacts. So a lava world should have *no* craters. The glow must be visible on the night side, which is what makes the class unmistakable.

**Barren / cratered.** Worley-based craters at two or three scales with a raised rim, mare-like dark patches from low-frequency fBm, no atmosphere and therefore a hard terminator with almost no penumbra and no rim glow. The absence of atmosphere is as much a signature as the craters.

**Toxic / greenhouse.** No surface at all - the visible layer is cloud. Venus is the reference: "dense clouds composed of sulfuric acid" that completely obscure the surface in visible light, a sky "likely some shade of sulfur yellow", 467 C, 93 bar. The dynamics are the giveaway: the clouds super-rotate at up to 360 kph while the planet itself turns once per 243 Earth days. Render it as a nearly featureless cream-yellow disc with faint Y-shaped ultraviolet-style shear streaks and heavy limb *brightening*.

**Hazy / Titan-like.** Worth a mention as a variant of the above rather than a separate class: a thick atmosphere producing a "hazy, yellowish" disc where the surface is hidden and the limb is brighter than the centre.

### Gas giants as a genuinely different renderer

Gas giants must not share the rocky code path. The construction is latitude-driven, not elevation-driven.

The proven approach, as documented by John Whigham, is to use "the planet space 'y' co-ordinate of the pixel being shaded (essentially the latitude) as a lookup into a colour ramp texture". He built that ramp by extracting a 1x2048 slice from real Cassini-Huygens Jupiter imagery and filtering it down. Scaling the latitude before the lookup controls band count directly - a smaller scale gives fewer, wider bands. Raw latitude alone is "way too regular and ordered", so the latitude coordinate is perturbed by turbulence before the lookup; Whigham combines "two weighted channels of two octaves" of volume noise. Parallel Cascades describes the equivalent trick as taking domain-warped noise and stretching it in y while squishing it in x and z. Deep-Fold's `GasPlanet.gdshader` implements the same idea compactly, warping band position with `uv.y += smoothstep(0.0, cloud_curve, abs(uv.x - 0.4))`.

Storms are added on top. Whigham encodes 100 to 200 cyclone cones per planet into a 128x128 cube map storing the cone axis in red and green, rotational strength in blue and radius in alpha, so the shader samples them all in one lookup rather than iterating. For a Canvas 2D port, iterating 3 to 8 analytic storms per world is cheaper than any texture and perfectly adequate.

Jupiter is the reference for what to aim at: "colorful cloud bands of tan, brown, white, and orange", a 9.9-hour day (the fastest in the solar system, which is why the bands are so sharply zonal), and the Great Red Spot - an anticyclone about 16,000 km across, currently around 1.3 Earth diameters, down from about 1.8 Earth diameters at the Voyager flybys in 1979, shrinking and rounding at roughly 580 miles per year.

Concrete gas giant recipe:

```
lat      = N'.y                                    // -1 .. 1
turb     = fbm(N' * 3.0) * 2 - 1                   // domain-warped once
latW     = lat + turb * 0.06 * (1 - lat*lat)       // warp, weakest at poles
band     = rampLookup( fract(latW * bandCount) )   // 6..14 bands
shear    = fbm(N' * 8.0 + vec3(0, latW*20, 0))     // fine streaks along flow
colour   = band * (0.9 + 0.2 * shear)
for each storm: colour = mix(colour, stormColour, ovalMask(N', storm))
```

The oval mask is an ellipse in (lon, lat) with an axis ratio of about 2:1 to 3:1, its interior swirled by rotating the sample coordinate about the storm centre by an angle falling off with radius - this is what makes a storm read as a vortex rather than a painted blob.

## 4. Lighting and atmosphere

Lighting is where a flat noise texture becomes a body in space. Five effects, in order of how much they buy.

**Terminator with a soft penumbra.** Lambert `d = dot(N, L)` then `lit = smoothstep(-w, +w, d)`. The width `w` is the single strongest atmospheric cue: `w ≈ 0.03` for an airless barren world gives a knife-edge terminator, `w ≈ 0.25` for a thick-atmosphere world gives a broad soft falloff. A wrap term `(d + w) / (1 + w)` additionally bleeds light around onto the night side, which is what atmospheres physically do.

**Limb darkening.** For stars the standard parameterization is a polynomial in `cos ψ`; for the Sun at 550 nm the coefficients are `a0 = 0.3, a1 = 0.93, a2 = -0.23`, giving an edge intensity of only 30% of the disc centre. Planets use Minnaert's law instead: bidirectional reflectance `r = μ0^k · μ^(k-1)` where `μ0 = cos(incidence)` and `μ = cos(emission) = N.z` in this orthographic setup. The exponent `k` is the useful knob - `k > 0.5` gives limb darkening, `k < 0.5` gives limb *brightening*. So `k ≈ 0.7` for a rocky world and `k ≈ 0.35` for Venus or Titan, and the class difference falls out of a single number.

**Atmospheric rim scattering.** The thin bright crescent at the limb is what most convincingly says "this planet has air". Approximate it as a Fresnel-style rim rather than computing Rayleigh scattering, which is too expensive for real time: `rim = pow(1 - N.z, p)` with `p` in 3..6, tinted by the atmosphere colour, multiplied by the lit mask so it forms a crescent on the day side rather than a uniform ring, and composited with `globalCompositeOperation = 'lighter'`. The existing `EncyclopediaArt._cloud` radial-gradient helper does this in two draw calls without touching ImageData.

**Specular highlight.** Only meaningful where there is water or ice, so gate it on the surface mask: `spec = pow(max(0, dot(N, normalize(L + V))), s) * waterMask` with `s` around 60 for rough seas and 200 for glassy ice. Applying it to the whole disc, as the current code does, is what makes every world look like a billiard ball.

**Night side and city lights.** On the dark side, `1 - lit` reveals whatever is emissive: lava glow for volcanic worlds, and for colonized worlds a scatter of warm points. NASA's Black Marble composite is the reference for what this looks like - lights cluster on coastlines and along corridors, never uniformly. Cheap implementation: seed a Poisson-ish scatter weighted by `landMask * (1 - iceMask)`, count proportional to `log(population)`, drawn as 1 px warm dots with a small `lighter` halo, masked to `(1 - lit)`.

**Clouds as a separate layer.** A second fBm octave with its own seed offset, its own rotation phase (so it does not track the surface), and a coverage threshold: `c = smoothstep(cover, cover + 0.15, fbm(N'' * cloudScale))`. Compositing white at alpha `c` over the shaded surface, with the *same* lighting term applied, gives clouds that darken correctly into the terminator. Offsetting the cloud layer's rotation by a few degrees from the surface produces a subtle parallax that reads as altitude.

## 5. Cheap per-world diversity

The goal is that two worlds with identical temperature, radiation and gravity still look different. Every parameter below is drawn from the world's seeded RNG and costs nothing at render time.

| Parameter | Range | Effect |
|---|---|---|
| `rotationPhase` | 0 .. 2π | Shows a different hemisphere of the same field - biggest visual delta per byte |
| `axialTilt` | -35° .. +35° | Tips the ice caps and band axis off horizontal, breaking the "all bands are level" tell |
| `lightAngle` | 200° .. 340° | Moves the terminator and the rim crescent |
| `hurstH` | 0.6 .. 1.0 | Smooth rolling terrain vs jagged shattered terrain |
| `warpAmount` | 0.4 .. 3.0 | Gentle coastlines vs heavily swirled marbling |
| `noiseScale` | 1.6 .. 4.0 | Few large continents vs many small islands |
| `seaLevel` | 0.32 .. 0.62 | Ocean world vs archipelago vs single supercontinent |
| `redistExponent` | 1.0 .. 3.5 | Broad plains vs uniform lumpiness |
| `cloudCover` | 0.0 .. 0.75 | Clear world vs mostly overcast |
| `iceLatitude` | 0.45 .. 0.95 | Thin polar frost vs snowball world |
| `mountainStrength` | 0.0 .. 0.5 | Flat vs heavily ranged |
| `hueJitter` | ±12° | Shifts the whole class palette so two deserts are not the same ochre |
| `bandCount` (gas) | 6 .. 16 | Broad Saturnine bands vs fine Jovian striping |
| `stormCount` (gas) | 0 .. 6 | Placement, size and swirl direction all seeded |
| `craterDensity` (barren) | 0.3 .. 1.0 | Lightly pocked vs saturated |

Three of these should be *correlated* with environment rather than free: `iceLatitude` from temperature, `cloudCover` from habitability, and `hueJitter` biased by the host star's spectral class so worlds around an M dwarf are consistently warmer-toned than worlds around an A star. That connects the visuals to the game state without collapsing back into a single ramp.

## 6. Performance, caching and determinism

**The budget is real but generous.** Section 2's benchmark shows one-level domain-warped fBm at 6 octaves over a 300x230 canvas costs about 5 ms in V8. That is a one-off cost per star, not per frame.

**Cache aggressively.** The panel re-renders on every selection change, and users click back and forth between the same few stars. Render into an `OffscreenCanvas` (or a detached `<canvas>`) keyed by star id and `drawImage` the cached bitmap thereafter. MDN's canvas optimization guidance recommends exactly this pre-render pattern, along with integer draw coordinates, avoiding `shadowBlur`, and batching draw calls. Cap the cache at 50 to 100 entries with simple LRU eviction; 100 bitmaps at 300x230 RGBA is about 27 MB, so cap lower if that matters.

**Structure the loop for the JIT.** Allocate the `Uint8ClampedArray` once and reuse it. Hoist the permutation table out of the pixel loop. Test `d2 > 1` before doing any noise work - that alone skips 55% of the canvas at `R = 100`. Avoid closures inside the inner loop.

**Determinism.** The project already has the right primitives in `encyclopedia.js`: FNV-1a `_hash` and mulberry32 `_rng`. Seed from the star's stable id rather than its name if names can be renamed. Derive every per-world parameter from that one generator in a *fixed order*, and shuffle the noise permutation table from it too. `Math.random` must not appear anywhere in the renderer. A useful invariant to assert in tests: rendering the same star twice produces byte-identical ImageData.

## Recommended approach for this project

Build `PlanetArt` as a sibling of `EncyclopediaArt` - same file conventions, same seeded RNG, same grain and vignette finishers - and delete `getPlanetColors` / `drawPlanetTexture` entirely rather than extending them.

**Layer order.**

1. **Cache probe** - `PlanetArt.cache.get(star.id)`; on hit, `drawImage` and return
2. **Seed and classify** - `rng = mulberry32(hash(star.id))`, then pick the planet class from the environment table below, then draw all fifteen per-world parameters from `rng` in fixed order
3. **Surface pass - one `ImageData` loop.** For each pixel inside the disc: compute the normal, rotate by `axialTilt` and `rotationPhase`, then branch once on class into either the rocky evaluator or the gas evaluator
   - *Rocky*: base = one-level domain-warped 3D fBm at 5 octaves with the world's `hurstH`; redistribute by `redistExponent`; add ridged fBm masked above sea level; for barren worlds add the Worley crater term; derive moisture from a second fBm at a different offset; look up the class palette by `(elevation, moisture)` and blend toward the class's cold colour by latitude past `iceLatitude`
   - *Gas*: latitude warped by domain-warped fBm, band ramp lookup at `bandCount`, fine shear streaks, then the analytic storm ovals
4. **Lighting - same loop, no second pass.** Minnaert `μ0^k · μ^(k-1)` with the class's `k`, `smoothstep` terminator at the class's penumbra width, wrap term for atmospheric classes, water/ice-gated specular, and on the night side the emissive terms (lava glow, city lights)
5. **Composite post-pass - draw calls only, no per-pixel work.** Cloud layer if `cloudCover > 0` (a second small ImageData pass or, cheaper, 20 to 40 `_cloud` billows clipped to the disc); atmospheric rim as a radial gradient ring in `'lighter'`; radiation glow ring retained from the current code but scoped to `radiation > 60`; `_grain` and `_vignette` reused verbatim from `EncyclopediaArt`
6. **Cache store**

**Why this shape.** One ImageData loop is where all the expensive work lives and it stays under 6 ms; everything after it is two or three gradient fills. Reusing `_hash`, `_rng`, `_cloud`, `_grain` and `_vignette` keeps the new renderer visually consistent with the encyclopedia art the project already ships. The class branch happening *inside* the pixel loop rather than as separate functions avoids duplicating the projection and lighting code eight times.

**What to build first.** The ordering that yields the most visible improvement per hour: (1) per-pixel normal and 3D noise replacing the radial gradient, (2) the elevation-by-moisture colour ramp replacing the temperature ramp, (3) the separate gas giant path, (4) domain warping, (5) Minnaert plus soft terminator plus rim, (6) craters, clouds and city lights.

## Planet class table

Thresholds are on the game's existing 0-100 environment scales and are starting points to tune, not derived constants.

| Class | Selected by | Visual signature |
|---|---|---|
| Gas giant | gravity ≥ 88 | 6-16 warped latitude bands, tan/brown/white/orange, 0-6 storm ovals with swirled interiors, no terminator sharpness, broad soft penumbra, strong rim |
| Ocean / terran | temp 40-62, rad < 40, hab > 40 | Fractal coastlines, deep blue with a lighter shelf band, green and tan continents, white decorrelated clouds, small polar caps, water-gated specular |
| Tundra | temp 22-42, rad < 55 | Low sea level, caps down to ~35° latitude, taiga greens and greys, thin cloud, high-contrast ice edge |
| Desert | temp 55-78, rad < 60, hab < 40 | No sea level, strong ridged canyon network, ochre through rust through tan, dust haze flattening limb contrast, no clouds |
| Ice / glacial | temp < 22 | Near-white high-albedo field, Worley cell-border cracks stained reddish-brown, caps merging toward equator, strong narrow specular |
| Volcanic / lava | temp > 82 | Dark basaltic base, inverted-ridged emissive fissure network glowing on the night side, sulfur yellows and oranges, no craters |
| Barren cratered | gravity < 30, rad any, hab very low | Multi-scale Worley craters with raised rims, dark mare patches, knife-edge terminator, no rim glow, no clouds |
| Toxic / greenhouse | rad > 70, or temp > 70 with hab < 5 | Featureless cream-yellow cloud deck, faint Y-shaped shear streaks, no surface detail, limb brightening (`k ≈ 0.35`), sickly green tint if radiation is extreme |
| Radiated barren | rad > 80, temp < 40 | Barren generator with a magenta-shifted palette and the existing radiation glow ring retained |

Colonized worlds of any class additionally get night-side city lights and a faint scatter of geometric surface marks near coastlines.

## Honest limitations without WebGL

- **No true per-pixel normal mapping from the heightfield** - computing surface normals by finite differences means three extra fBm evaluations per pixel, roughly tripling the cost. Bump shading of mountain ranges is therefore off the table at full quality; a cheap single-axis derivative approximation is the fallback
- **No animation** - the numbers above are per-render, not per-frame. Rotating gas bands or drifting clouds at 60 fps would need 300 ms per second of CPU, which is not viable. The planet must be a still image
- **No real atmospheric scattering** - the rim is a Fresnel-style approximation. Multiple scattering, the blue-to-orange gradient through the terminator, and correct optical-depth falloff all require a per-pixel integral that Canvas 2D cannot afford
- **No self-shadowing or ray-marched terrain** - mountains cannot cast shadows across valleys, and the terminator cannot break up over rough topography the way it does on the real Moon
- **No high-frequency detail** - 6 octaves at 300 px is near the Nyquist limit anyway, but there is no mip-mapping or analytic filtering, so pushing the noise scale up produces aliasing rather than detail
- **Resolution-bound quality** - at 300x230 with a 100 px radius the planet is about 200 px across. Fine features below roughly 2 px will not survive, which caps how much of the above actually reads. Rendering at 2x and downsampling costs 4x the time (about 20 ms) and is the only lever
- **The gas giant colour ramp is hand-authored** - Whigham's ramp came from real Cassini imagery. Without an image asset the ramp must be hand-tuned RGB stops, which will be less convincing than a sampled one

## Sources

Primary and high-trust, all verified by fetching except where noted.

**Noise and procedural technique**
- Inigo Quilez, *Domain warping* - https://iquilezles.org/articles/warp/
- Inigo Quilez, *fBM* - https://iquilezles.org/articles/fbm/
- Inigo Quilez, *Voronoi edges* - https://iquilezles.org/articles/voronoilines/
- The Book of Shaders, ch. 13 *Fractal Brownian Motion* - https://thebookofshaders.com/13/
- Red Blob Games, *Making maps with noise functions* - https://www.redblobgames.com/maps/terrain-from-noise/
- Stefan Gustavson, *Simplex Noise Demystified* (PDF) - https://cgvr.cs.uni-bremen.de/teaching/cg_literatur/simplexnoise.pdf - **note: the URL resolves and serves the PDF, but the binary could not be parsed by the fetch tool, so the simplex claims here are secondhand from search summaries rather than read directly from the paper**
- Blender Manual, *Musgrave texture* (ridged basis as one minus absolute value) - https://docs.blender.org/manual/en/latest/render/materials/legacy_textures/types/musgrave.html
- Worley noise overview - https://en.wikipedia.org/wiki/Worley_noise
- Endre Simo, *Worley noise cellular texturing* - https://www.esimov.com/2012/05/worley-noise-cellular-texturing

**Planet generators**
- Sebastian Lague, *Procedural Planets* source - https://github.com/SebLague/Procedural-Planets - **note: only `Noise.cs` is present in the `Procedural Planet Noise` folder; the ridged filter file could not be fetched**
- Sebastian Lague, *Coding Adventure: Procedural Moons and Planets* - https://www.youtube.com/watch?v=lctXaT9pxA0
- Sebastian Lague, *Procedural Planets E03: layered noise* - https://www.youtube.com/watch?v=uY9PAcNMu8s
- Sebastian Lague, *Procedural Planets E04: multiple noise filters* - https://www.youtube.com/watch?v=H4g-TC__cvg
- Deep-Fold, *PixelPlanets* (Godot shaders; classes Asteroids, DryTerran, GasPlanet, GasPlanetLayers, IceWorld, LandMasses, LavaWorld, NoAtmosphere, Rivers, Star) - https://github.com/Deep-Fold/PixelPlanets
- John Whigham, *Gas Giants* - http://johnwhigham.blogspot.com/2011/11/gas-giants.html
- Parallel Cascades, *Gas Giant Curl Simulation in Unity* - https://parallelcascades.com/gas-giant-curl-simulation/

**Lighting and photometry**
- *Limb darkening* (polynomial parameterization; solar coefficients at 550 nm) - https://en.wikipedia.org/wiki/Limb_darkening
- NASA JPL VICAR, *PHO_MINNAERT* (Minnaert law, the `k` exponent, limb darkening vs brightening) - https://www-mipl.jpl.nasa.gov/vicar/dev/html/vichelp/pho_minnaert.html

**Astronomical references**
- NASA, *Mars facts* - https://science.nasa.gov/mars/facts/
- NASA, *Jupiter* - https://science.nasa.gov/jupiter/
- NASA, *Io* - https://science.nasa.gov/jupiter/jupiter-moons/io/
- NASA, *Europa* - https://science.nasa.gov/jupiter/moons/europa/
- NASA, *Venus facts* - https://science.nasa.gov/venus/venus-facts/
- NASA, *Titan* - https://science.nasa.gov/saturn/moons/titan/
- NASA Hubble, *Jupiter's Great Red Spot is smaller than ever measured* - https://science.nasa.gov/missions/hubble/nasas-hubble-shows-jupiters-great-red-spot-is-smaller-than-ever-measured/
- NASA Earth Observatory, *Night Lights 2012 - The Black Marble* - https://science.nasa.gov/earth/earth-observatory/night-lights-2012-the-black-marble-79803/

**Platform**
- MDN, *Optimizing canvas* - https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial/Optimizing_canvas

**Measurements**
- The timing table in section 2 is my own benchmark, run on Node 26.5.0 (V8), 300x230 canvas, `R = 100`, 10 iterations after a warm-up, seeded value noise with equirectangular lookup and a Lambert term. It is not a citation from an external source.
