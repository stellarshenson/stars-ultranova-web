# Station Rendering

A station reads as real hardware when its silhouette is a **spine with things hung off it at right angles** - one dominant linear body, a couple of modules stacked asymmetrically along it, and flat panels on a single perpendicular axis - and when that silhouette is separated from the planet behind it by a hard dark keyline rather than by softness. It reads as a logo the moment it becomes radially symmetric about its own centre, because radial symmetry is the visual grammar of emblems, wheels and mandalas, not of vehicles.

## 1. Real station morphology

Every flown station is a **spine plus perpendicular appendages**, and the spine is never centred in the silhouette. The load-bearing features at small scale are, in order: the long axis, the panels crossing it, and the lumpy asymmetric mass where the pressurised modules are. Everything else - handrails, trunnions, antennas, docked visiting vehicles - is sub-pixel below about 40 px and must be discarded.

- **ISS** - a straight truss backbone with eight solar wings strung along it and a perpendicular cluster of pressurised modules crossing it near the middle, forming a rough plus sign with unequal arms. NASA: the Integrated Truss Structure is "11 segments plus a separate component called Z1 that are attachment points for the solar arrays, thermal control radiators and external payloads", and "The ITS reaches 108.5 meters (356 feet) in length across the extended solar arrays". Survives at small scale: the long truss line, the four paired panel blades, the module cluster offset from centre. Dies: radiators, the Canadarm, docking ports
- **Mir** - a hub-and-spoke accretion, deliberately unbalanced because it was built over nine years. ESA describes a core module with "five docking ports", with Kvant on +X, Kvant-2 on +Y, Kristall on -Z and Spektr on -Y, each added years apart. Survives: a knot of cylinders at different angles with panels sprouting at inconsistent orientations. This is the reference for "accreted, not designed"
- **Skylab** - one fat cylinder with a single solar wing on one side and a four-panel windmill (the Apollo Telescope Mount) at the front. The asymmetry was an accident - NASA records that during launch "debris jammed one solar array panel and the second one tearing off entirely" - and it is exactly what makes the silhouette memorable. Survives: big body, one wing, one cross. This is the cheapest station silhouette to draw and the most legible
- **Tiangong** - a literal T. "The Tiangong space station shows a T-shaped configuration, with the Tianhe core module in the middle and two experiment modules, namely Wentian and Mengtian, being assembled on the 2 sides." Core module 16.6 m long, 4.2 m diameter; experiment modules ~17.9 m. Survives: three thick bars in a T, panels on the ends. The T is the smallest arrangement that still says "assembled from parts"
- **Lunar Gateway** - a small stack: the Power and Propulsion Element, "a 60-kilowatt solar electric propulsion spacecraft", carrying two roll-out arrays "approximately the size of a football field's endzone", docked nose to tail with HALO, a short pressurised can. Survives: a short body with two enormous flat rectangles - the panels dominate the silhouette, which is the correct read for a small modern station

The common rule: **panels are large, flat and few; bodies are small, lumpy and off-centre**. Any drawing that inverts that ratio - a big central body ringed by small equal arms - stops looking like a station.

## 2. Why asymmetry reads as real

Radial symmetry is what the eye has been trained to classify as *insignia*. Design writing on radial balance describes it as composition where "elements radiate outward from a central focal point, distributing visual weight evenly in all directions and creating circular harmony", and notes the perceptual reason it is used for marks: "the brain processes radial patterns quickly because symmetrical arrangements require less mental effort to decode". That efficiency is exactly the problem. A shape that decodes instantly as a centred, evenly weighted pattern is decoded as a symbol, and the decoding finishes before the viewer ever asks what the parts are for.

Vehicles use bilateral symmetry, not radial. Arne Niklas Jansson's spaceship design essay is blunt about the axis that matters: "The human mind is used to the top/bottom, back/front looking different on humans. Our minds are instinctively opposed to l/r asymmetry." So the rule is not "make it asymmetric" - it is **mirror across one axis only, and never across the second**. A spine with panels mirrored above and below, and a module cluster that is not mirrored front to back, hits this precisely. An N-fold rosette violates it by mirroring across every axis at once.

There is a documented, in-production failure of exactly this kind. Elite Dangerous Coriolis starports are cuboctahedra, and the community wiki records the consequence: "Due to the symmetrical nature of Coriolis stations it can be difficult to find the docking slot. To remedy this the target hologram displayed when targeting the station has arrows pointing towards the station's entrance." A design so symmetric that the game had to ship a UI arrow to tell you which way it was facing is the clearest possible evidence that symmetry destroys orientation cues, and orientation cues are what make a shape read as a machine.

Two further points that bear directly on the current attempt:

- **A rosette has no orientation, so it cannot be lit.** Directional light on a symmetric star produces a symmetric gradient that the eye reads as a glow, not as a lit object. A spine has a sunward side and a shadow side, and that one hard boundary does more work than any amount of detail
- **A rosette fills a disc; a spine fills a line.** This is the size problem restated as geometry. N arms of length `s` occupy a circle of area `pi*s^2`. A spine of length `2s` and thickness `t` occupies `2*s*t`. At `s = 20 px, t = 4 px` that is 1257 px versus 160 px of ink - the rosette is eight times heavier on the page at the same nominal scale

Jansson's other relevant finding is that detail must be subordinate to the primary form: the Borg cube works because "the silhouette is not disturbed" by its heavy greebling, whereas failed designs are "a mess of protrusions which makes them hard to recognize". Radial spars are protrusions with nothing to protrude from.

## 3. Sci-fi station design language

The productions that are respected for station design all pick **one dominant primitive** and let function hang off it. None of them uses an even rosette as the primary read.

- **Babylon 5** - an O'Neill cylinder, "five miles in length and one mile in diameter", based on O'Neill's 1973 proposal. The read is a single long tube; rotation is implied by the tube, not shown. Function signalled: a habitat, because habitats need spin gravity and spin gravity needs a cylinder
- **Deep Space Nine** - radial, and it works, but not because it is symmetric. It is "a broad outer docking ring, an inner habitat ring containing residential apartments, and a central core", with "three sets of docking pylons sweep up and down equidistantly around the docking ring, defining an almost spherical shape". The critical detail is *up and down*: the pylons leave the ring plane, so the projected silhouette is never a flat star. It also works because it is shot large in frame, with ships for scale. Neither condition holds for a 12 px sprite
- **The Expanse** - industrial realism through machinery that is clearly for something. Tycho is "an artificial ring station 700(+) meters in diameter built around a micro-gravity sphere", and the yard is signalled by "half a dozen massive construction waldoes that looked like they could rip a heavy freighter in half". The station's identity is the grabbing arms, not the ring
- **Elite Dangerous** - Coriolis is a cuboctahedron and pays for its symmetry, as above; Orbis fixes the problem by breaking the ring, being "a cylindrical main hub which contains the docking bay" with "a spire that hosts habitat rings, storage modules, solar panel arrays, and a reactor at the far end". That spire is a spine. The docking slot is a black rectangle in a lit face - a hole reads as a hole even when tiny
- **Kuat Drive Yards** - the canonical shipyard read: "A vast man-made ring of factories and spacedocks encircles the planet", described as "an immense scaffold in space, bridged and augmented with enormous habitats and machinery". Scaffold is the operative word

**What specifically says shipyard**, distilled from Kuat, Tycho and real yard practice (drydocks, slipways, cradles, Goliath gantry cranes):

- An **open frame** rather than a closed hull - you can see through it
- A **slip**: a rectangular gap in the frame, open at one end, that is obviously ship-shaped and obviously empty or occupied
- A **partially built hull inside the frame**, lighter and smoother than the frame around it - the single strongest cue, because it shows the frame doing its job
- **Gantries**: bars crossing the slip perpendicular to the ship's axis, ideally more than one, ideally unevenly spaced
- **Work lighting**: warm, clustered inside the slip, not distributed evenly around the perimeter
- Absence of guns. A yard with turrets is a fort

## 4. What the original actually drew

Two findings, and the second one matters more than the first.

**The 1995 game did not draw a station on the planet at all.** In the reference screenshot of the main screen (`.resources/orig_game_screenshots/original_1995/stars_4.png`), the planet thumbnail is a bare world; the starbase is reported as a text block - Dock Capacity, Armor, Shields, Damage, Mass Driver, Destination. The starbase art appears only in the Ship & Starbase Designer hull preview (`stars_2.png`, an Ultra Station). So compositing a station over the planet disc is an invention of this port, and there is no original to violate. What must be respected is the *design vocabulary* of the base art, not its placement.

**The Nova base art is a closed polygon of armoured nodes, not a hub with spokes.** The reference renders under `references/original-game/Graphics/High_Resolution/Base/` show a consistent family:

| Hull | Nodes | Arrangement |
|---|---|---|
| Orbital Fort | 2 | one spar, two nodes, two shield petals |
| Space Dock | 3 | open triangle, three petals |
| Space Station | 4 | closed quadrilateral ring, four petals |
| Ultra Station | 6 | closed hexagonal ring, six petals |
| Death Star | many | spherical geodesic cage of green and grey struts, glowing orange core, violet shield petals all round |

Each node is a chunky faceted block with grey gun barrels sticking out at odd angles; the nodes are joined **edge to edge by tubular spars around the perimeter**; the magenta shield petals are curved surfaces standing *perpendicular to the ring plane*, which is what stops the shape from being a flat rosette. Progression is by node count, and the Death Star breaks the family by being a filled sphere.

The low-resolution in-game sprites (`Graphics/Base/*0000.png`) are **64 x 64**, and at that size the Death Star already collapses to an indistinct blob. That is direct evidence that the 3D art does not scale down: at 12-20 px it must be re-authored as a small-scale drawing, not imitated.

**Functional grounding from `backend/data/components.xml`** (dock capacity), which should drive the visual differentiation:

- Orbital Fort - **0** dock capacity. It cannot service ships at all. It is a gun platform
- Space Dock - **200 kT**. A small, limited cradle
- Space Station / Ultra Station / Death Star - **10000** (unlimited). A full open dock

So the fort should have no slip and visible barrels; the dock should have a small cradle; the station classes should have an open dock aperture.

## 5. Drawing small, sharp hardware in Canvas 2D

At 10-30 px the medium is effectively pixel art with anti-aliasing, and the pixel-art rules apply verbatim: "Before adding any detail, block out your shape in a single color. If the silhouette isn't readable, no amount of shading will fix it", and "The best 16x16 sprites aren't the most detailed - they're the most readable. When in doubt, remove pixels."

**Geometry and snapping.** Canvas coordinates fall between pixels, so "a 1 pixel line has to span 2 pixels and will look faded or blurred"; the fix is the 0.5 offset. The distinction that matters here: "If you're drawing a stroked rectangle you want to add 0.5, so the stroke lines are centered in the middle of the edge pixels; but if you're drawing a filled rectangle then you want to use whole numbers for the corners."

- Build the station from **`fillRect` on integer coordinates**, not from strokes. Fills give hard edges for free
- Reserve strokes for the few genuine 1 px lines (a gantry bar, a hull seam) and offset those by 0.5
- **Round the station origin to integers** before drawing anything
- `ctx.rotate` reintroduces anti-aliasing on every edge. Either snap the rotation to a small set of angles, or accept it and enforce a **2 px minimum on every feature's minor dimension** so anti-aliasing can never consume a feature outright
- Never use `lineCap = 'round'`. Round caps turn a 2 px bar into a soft capsule, which is the single largest contributor to the current "soft" reading

**Separation from the planet.** The station is composited over a lit sphere whose local value is unpredictable - bright ochre desert on one visit, near-black night side on the next. Alpha-modulated fills (the current `rgba(hue, 0.35 + lit*0.6)`) let the planet show through and wash the station out.

- Use **opaque fills**. Put the lighting into RGB, never into alpha
- Draw a **1 px near-black keyline by dilation, not by stroking**: render the whole silhouette once in `rgb(4,6,10)` with every rectangle inflated by 1 px on all sides, then render the lit body on top. This works at any thickness, including a 2 px bar, where a stroked outline would leave no interior
- Keep at least **three luminance steps** in the sprite: keyline (near black), shadow side (dark blue-grey), lit side (near white). Value contrast is what survives downscaling; hue is not

**How much greebling survives.** A feature is visible only if its minor dimension is at least 2 px and it differs from its neighbour by roughly 25 percent luminance. That gives a hard budget.

- **The dozen-pixel rule**: at a longest dimension of 12-16 px, allow at most **four distinct silhouette features** (spine, module cluster, panel pair, one class marker), each at least 2 px thick, each separated from its neighbour by at least 1 px of a different value. A fifth feature does not add information, it adds mush
- Detail below 2 px must be replaced by a **value change on an existing surface**, not by a new shape

## 6. Lighting and context

The planet renderer already has a light direction (`P.lightAngle`, `Lx`, `Ly`) and a hard smoothstep terminator. The station must obey the same light or it will read as a decal.

- **One light, same direction.** Split the station body into a sunward half and a shadow half with a **hard boundary** - no gradient. At 12 px a gradient is two intermediate pixels and reads as blur
- **Specular glint on panels only.** Real stations are visible from the ground precisely because of this: NASA notes the ISS "is visible because it is reflecting sunlight", off arrays covering "about 27,000 square feet (2,500 square meters)". Give the panel a single bright 1 px edge when the panel normal is within about 30 degrees of the light, and a near-black face otherwise. That flip between "bright blade" and "dark blade" is a large part of what makes panels read as flat plates
- **Dark keyline where it crosses the bright limb.** This is the same job as the dilated keyline in section 5 and needs no special case, provided the keyline is opaque and near black. Against the night side, the keyline vanishes and the lit hull carries the contrast - which is why the night side is the better default placement
- **Placement**: put the station over the dark hemisphere, roughly 35-50 percent of the radius out from the centre. Maximum contrast, and it avoids the busiest part of the surface texture
- **Orbit path: remove it.** The current dashed ellipse at 1.34 R is a graphic roughly forty times the area of the station. It reads as UI chrome, it dominates the thing it is meant to annotate, and it forces the eye to interpret the station as a marker on a diagram. If an orbital cue is wanted, use a **short arc of 25-35 degrees** centred on the station, one pixel, 10-15 percent alpha, and clipped to the disc

## 7. Size

The honest answer is that the ISS is invisible. 109 m against an Earth radius of 6371 km is a ratio of 1.7e-5. At the renderer's 65 px planet radius that is **0.0011 px** - one thousandth of a pixel. To occupy a single pixel a structure would have to be about 98 km across.

So every game exaggerates, and the only question is by how much before the station stops being hardware and starts being a moon. The current table is well past that line:

| | current scale | px at R=65 | implied real size | ink on the disc |
|---|---|---|---|---|
| Orbital Fort | 0.13 | 8.5 arm length | 830 km | ~1.7 % |
| Death Star | 0.31 | 20 arm length | **1975 km** | **~9.5 %** |

A 1975 km object is between Ceres and a mid-size moon. The renderer is drawing a moon, and the rosette geometry means it covers nearly a tenth of the planet disc in ink.

**Recommendation** - constrain the **longest dimension** and let the linear form do the size reduction:

- **Longest dimension 0.10 R to 0.20 R**, i.e. **6.5 px to 13 px at R = 65**
- **Minor dimension 3 to 5 px.** The bounding box must be at least 2.5:1 elongated for every class except the Death Star
- **Ink budget: under 1 percent of the planet disc.** A 13 x 4 px spine with panels is roughly 90 px against a 13273 px disc, a fourteen-fold reduction from the current Death Star
- The elongation is what buys the size back: a station can be 13 px long and still feel small, because the eye judges size by area, not by extent

## Recommended design

### Shared silhouette grammar

One construction, six parameterisations. All coordinates in a local frame whose origin is `Math.round`ed to integer device pixels, with the spine lying along the local X axis and rotated to within about 20 degrees of the orbit tangent so the station looks like it is travelling, not floating.

1. **Spine** - a filled rectangle, length `L` (per class), thickness `T = 3 px`. This is the whole design. Everything else attaches to it
2. **Modules** - two or three short rectangles of width `T + 2`, straddling the spine at **asymmetric stations along it**: 0.18 L, 0.55 L, 0.82 L. Never at 0.5. Never mirrored front to back
3. **Panels** - a pair of rectangles `0.45 L` long and 2 px wide, perpendicular to the spine, both attached at **one** point at about 0.30 L, one reaching up and one reaching down, joined to the spine by a 1 px stub. This is the ISS arrangement and it is the feature that says "station" fastest. Mirror across the spine axis only, never across the perpendicular
4. **Keyline** - the entire silhouette rendered first in `rgb(4,6,10)`, every rectangle inflated 1 px on all sides. Then the body on top
5. **Two-tone body** - sunward half of every rectangle in the light value, shadow half in the dark value, hard boundary, both opaque
6. **One running light** - a single 1 px warm dot at the far end of the spine. One, not one per feature

### Per-class differentiation

Differentiate by **topology and feature count**, never by scale alone. Scaling one shape produces six of the same thing, which is what the current table does.

| Class | L at R=65 | Construction | The one-glance read |
|---|---|---|---|
| **Orbital Fort** | 7 px (0.11 R) | Spine, 1 module, **no panels**, two 2 px barrels at right angles near the ends. Dock capacity is 0 - it services nothing | A short armoured bar with guns |
| **Space Dock** | 9 px (0.14 R) | Spine, 2 modules, **one small panel pair**, a 3 px open **C-cradle** at one end. Dock capacity 200 kT - limited | A bar with a small clamp |
| **Shipyard** | 11 px (0.17 R) | See the Shipyard section | Open frame with a hull in it |
| **Space Station** | 11 px (0.17 R) | Spine, 3 modules, **full 4-panel array** (two pairs, at 0.28 L and 0.62 L), one thin 1 px radiator at a different angle, a 2 x 2 px **dark dock aperture** in the largest module | A proper truss station |
| **Ultra Station** | 13 px (0.20 R) | **Two parallel spines** 5 px apart joined by three cross-ties - an H-truss, not a longer bar - 4 modules, 4 panels, 2 radiators | Twice the structure, obviously |
| **Death Star** | 11 px diameter (0.17 R) | The **only compact class**. A filled disc with a hard terminator, one 1 px meridian trench offset from centre, one 2 px circular emplacement at about 0.35 R off-centre, a 1 px equatorial band, and a single warm core pixel echoing the Nova render's glowing core | The one that is not a truss |

The Death Star earns its distinctiveness by being the odd one out in *form*, not by being the biggest. That is also faithful to the reference art, where it is the only base that is a sphere rather than a spar frame.

Doubling the spine for Ultra Station rather than lengthening it is the key trick: **feature count reads as capability at small size; length reads as distance**.

### Draw order

1. Optional short orbit arc, 25-35 degrees, 1 px, alpha 0.12, clipped to the disc. Default off
2. Dilated near-black keyline for the complete silhouette
3. Panel fills - dark first, so they sit behind the structure
4. Spine and module fills, shadow value
5. Spine and module fills, light value, clipped to the sunward half
6. Class markers - barrels, cradle, aperture, trench, gantries
7. 1 px sunward highlight edge on the spine and on the sunward panel face
8. Specular glint on a panel if its normal is within about 30 degrees of the light
9. Running or work lights

Costs roughly 30 to 60 `fillRect` calls with no allocation. Against a per-world budget of 10-21 ms this is unmeasurable, and it does not need caching separately from the existing per-world cache.

## Shipyard

The shipyard must read as a **yard with a ship in it**, and the ship-in-the-frame is the whole trick. A fort is a closed, armed, symmetric mass; a yard is an open frame with a soft object cradled inside it.

- **Open frame** - a rectangle drawn as four 2 px bars with a visible **gap on the outward long side**. Never a filled rectangle. The gap is what makes it a slip rather than a box
- **The hull in the slip** - a 4 x 2 px light-grey lozenge inside the frame, **brighter and smoother than the frame**, and deliberately **not filling the slip** - leave 1 px of black at one end so it reads as unfinished. This is the single feature that converts "frame" to "yard"
- **Gantries** - two 1 px bars crossing the slip perpendicular to the hull, **unevenly spaced** (about 0.35 and 0.7 along the slip). Even spacing reads as decoration
- **Work lights** - two warm amber pixels **inside** the slip, clustered, not on the perimeter. Perimeter lights read as navigation lights, which is a fort cue
- **No barrels, no shield petals, no radial anything.** The absence of weapons is half the read
- Cool structure against a warm interior. The frame in the same blue-grey as the other classes, the work lights and the partial hull warm - so the yard is the only class with warm light inside a cool shell

Vocabulary check against the references: Kuat is "an immense scaffold in space"; Tycho's identity is its "massive construction waldoes"; real yards are gantry cranes, slipways and cradles. All four of those are frames holding something, and none of them is a fortification.

## Failure modes to avoid

- **The asterisk.** N radial spars from a common centre plus a ring is a compass rose, a snowflake or a sparkle - a mark, not a machine. This is the current `_drawStation` construction and it is the primary defect. No amount of lighting, colour or size adjustment rescues it, because the failure is topological. Replace the hub with a spine
- **Round line caps.** `lineCap = 'round'` on a 2 px spar produces a soft capsule. Butt caps or, better, filled rectangles
- **Stroked ellipse rings.** An ellipse of 10 px radius stroked at 2 px is a fuzzy O. If a ring is wanted it must be a closed polygon of filled segments with nodes at the vertices - which is what the Nova reference art actually is
- **Scaling one shape for six classes.** Six sizes of the same object is one object. Differentiate by feature count and topology
- **A running light per arm.** A ring of evenly spaced dots is a UI marker or a loading spinner. One light
- **The dashed orbit ellipse.** Forty times the station's area, reads as chrome, and reframes the station as an annotation on a diagram
- **Alpha-modulated fills over a bright planet.** `rgba(hue, 0.35 + lit*0.6)` lets a lit desert surface bleed through. Opaque fills, lighting in RGB
- **Soft gradients across a 12 px body.** Two intermediate pixels is not a terminator, it is blur
- **Imitating the 3D reference art directly.** The Nova renders collapse to blobs at their own 64 px sprite size. Re-author for the scale
- **Sub-2 px greebles.** They become grey haze and cost contrast elsewhere

## Sources

- [NASA - Integrated Truss Structure](https://www.nasa.gov/international-space-station/integrated-truss-structure/)
- [NASA - International Space Station Assembly Elements](https://www.nasa.gov/international-space-station/international-space-station-assembly-elements/)
- [NASA - Spot the Station FAQ](https://www.nasa.gov/missions/station/spot-the-station-frequently-asked-questions/)
- [NASA - Solar Arrays on the International Space Station](https://www.nasa.gov/image-article/solar-arrays-international-space-station-2/)
- [NASA - 50 Years Ago: Skylab 2 Astronauts Deploy Jammed Solar Array](https://www.nasa.gov/history/50-years-ago-skylab-2-astronauts-deploy-jammed-solar-array-during-spacewalk-2/)
- [NASA - Gateway Space Station](https://www.nasa.gov/reference/gateway-about/)
- [NASA - A Powerhouse in Deep Space: Gateway's Power and Propulsion Element](https://www.nasa.gov/missions/artemis/gateway/a-powerhouse-in-deep-space-gateways-power-and-propulsion-element/)
- [ESA Bulletin 88 - Working Aboard the Mir Space Station](https://www.esa.int/esapub/bulletin/bullet88/reite88.htm)
- [Design and Application Prospect of China's Tiangong Space Station - Space: Science & Technology](https://spj.science.org/doi/10.34133/space.0035)
- [Arne Niklas Jansson - Spaceship Design](https://androidarts.com/spaceships/spaceship_design.htm)
- [Greeble - Visual Technobabble](https://medium.com/@liam3D/greeble-visual-technobabble-8d1cd99274bd)
- [What Is Radial Balance? A Designer's Secret for Harmony](https://www.designyourway.net/blog/what-is-radial-balance/)
- [Elite Dangerous Wiki - Coriolis](https://elite-dangerous.fandom.com/wiki/Coriolis)
- [Elite Dangerous Wiki - Orbis](https://elite-dangerous.fandom.com/wiki/Orbis)
- [Wikipedia - Deep Space Nine (fictional space station)](https://en.wikipedia.org/wiki/Deep_Space_Nine_(fictional_space_station))
- [Memory Alpha - Terok Nor type](https://memory-alpha.fandom.com/wiki/Terok_Nor_type)
- [Wikipedia - O'Neill cylinder](https://en.wikipedia.org/wiki/O%27Neill_cylinder)
- [The Expanse Wiki - Tycho Station](https://expanse.fandom.com/wiki/Tycho_Station)
- [ArtStation Magazine - Behind the scenes: the concept art of The Expanse](https://magazine.artstation.com/2016/02/scenes-concept-art-expanse/)
- [Wookieepedia - Kuat Drive Yards](https://starwars.fandom.com/wiki/Kuat_Drive_Yards)
- [Wookieepedia - Kuat Drive Yards Orbital Array](https://starwars.fandom.com/wiki/Kuat_Drive_Yards_Orbital_Array)
- [Damen - Docking systems](https://www.damen.com/vessels/shipyards-and-docks/docking-systems)
- [Wikipedia - Arrol Gantry](https://en.wikipedia.org/wiki/Arrol_Gantry)
- [HTML5 Canvas - Crisp lines every time](https://mobtowers.wordpress.com/2013/04/15/html5-canvas-crisp-lines-every-time/)
- [RGraph - How to get crisp lines on your canvas tag without anti-aliasing](https://www.rgraph.net/canvas/howto-antialias.html)
- [whatwg/html issue 3181 - Drawing crisp lines in canvas](https://github.com/whatwg/html/issues/3181)
- [Sprite-AI - How to create 16x16 pixel art sprites](https://www.sprite-ai.art/guides/how-to-create-16x16-pixel-art)
- [Sprite-AI - Pixel art fundamentals](https://www.sprite-ai.art/guides/pixel-art-fundamentals)

Local references consulted:

- `/home/lab/workspace/private/games/stars-ultranova-web/references/original-game/Graphics/High_Resolution/Base/` - Orbital_Fort.jpg, Space_Dock.jpg, Space_Station.jpg, Ultra_Station.jpg, Deathstar_With_Shields.jpg
- `/home/lab/workspace/private/games/stars-ultranova-web/references/original-game/Graphics/Base/` - the five 64 x 64 in-game sprites
- `/home/lab/workspace/private/games/stars-ultranova-web/.resources/orig_game_screenshots/original_1995/stars_2.png`, `stars_4.png`
- `/home/lab/workspace/private/games/stars-ultranova-web/backend/data/components.xml` - starbase hull dock capacities
