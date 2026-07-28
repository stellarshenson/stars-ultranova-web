# Art Direction

Visual direction for rendered hardware - orbital stations and ships. Captured from the user's directives so they survive the wave queue; the acceptance criteria in `docs/acc-crit-stars-ultranova-web.md` remain the contract, and these entries move there once the file is free.

Everything here is drawn procedurally in Canvas 2D. No image assets, no WebGL.

## Two scales, two techniques

The same subject is drawn twice by different machinery, because a technique that works at 10 px fails at 256 px and the reverse.

- **Sprite scale** - the star panel's 8-11 px station, drawn as flat opaque rectangles with a dilated near-black keyline. Legibility comes from contrast, elongation and placement off the limb, never from bulk. Lives in `frontend/js/views/planet-art.js`
- **Detail scale** - 256 px and up, drawn by signed-distance-field raymarching with soft shadows, ambient occlusion, Fresnel rim and specular metal. This is where photorealism is possible. Lives in `frontend/js/views/station-detail.js`

The rule that forced the split: photorealism is size-bound. At 10 px there are not enough pixels to carry a lighting model, so the sprite is deliberately schematic and the detail view carries the realism.

## Where the detail view appears

The station detail render is the **refit screen** - opened when the player opens a starbase to refit it. That is the moment the player is looking at the station as an object rather than as a map token.

## Stations

- **Architecture** - Deep Space 9 and Wing Commander Privateer's Perry Station: a core with a habitat ring on pylons for the large classes, a pressurised drum on an axle for the small ones
- **Radial symmetry is permitted** - but only carried by solid volumes. The first rejected attempt failed because it was radial *wire*: thin spars with no mass, which the eye decodes as an emblem. Volume is what separates architecture from heraldry
- **No external guns** - user directive: "no guns outside, stations are large enough that they'd have their gun emplacements anyway". Weapons are internal emplacements on every class
- **Photorealistic at detail scale** - "almost photorealistic, realistic such as if they were photographed real"
- **Canon class ladder** - taken from the original game's own starbase art in `references/original-game/Graphics/High_Resolution/Base/`: Fort 2 armoured nodes, Dock 3, Station 4, Ultra 6, Death Star a sphere. The ladder and spirit are canon; the 1990s purple plastic look is not carried over
- **Shipyard reads as a yard** - an open scaffold with a partially built hull cradled inside, gantries, warm work lights inside the slip against a cool shell. No weapons at all; their absence is half the read

## Station catalogue

- **20-30 selectable types** - the player chooses a station's appearance when designing or refitting a starbase
- **Appearance is cosmetic** - the hull class continues to govern all game rules (dock capacity, armour, shields, slots). A design declares which hull classes it is valid for
- **Flavour axis** - designs span a range from familiar human industrial through to markedly alien; the player picks where on that axis their empire sits

## Ships

Not yet built. No ship art exists in the game today - `EncyclopediaArt.paint` covers phenomena only (nebulae, storms, wormholes, minefields, stargates, mystery trader, mineral packets), and ships are map symbols plus text in the design panel. Rendering hulls is a new renderer, not a restyle.

- **Capital ships** - The Expanse crossed with Warhammer 40,000. The Expanse supplies the functional logic: thrust-axis architecture, ribbed working hulls, drive cones, no wasted volume, everything visibly for something. W40k supplies mass and silhouette: slab armour, buttressed flanks, a heavy cathedral prow. Industrial bones, gothic outline
- **Flavour axis** - as with stations, further variants push less or more alien
- **200-300 distinct ships** - tankers, carriers, freighters, escorts and capitals, every one recognisably its own vessel

### How 200-300 hulls get built

Not by hand. The same architecture that already solved diverse worlds: a small set of role archetypes plus a seeded parameter space, so each design is generated deterministically from its own name and looks identical on every visit. `PlanetArt` reaches unlimited distinct worlds from nine classes and fifteen seeded parameters; ships work the same way.

- **Archetype per role** - the generator keys off the SAME role cascade the battle engine uses for target-class orders (capital, escort, support, logistics, boarding), so a ship that reads as a tanker IS a tanker to the targeting code. One source of truth for what a ship is
- **Seeded parameters** - hull proportions, module count and placement, drive-cone count, armour banding, prow treatment, greeble density, panel albedo, all drawn in fixed order from a hash of the design name
- **Correlated to the real design** - the parameters that can be driven by game state should be: mass and hull size set bulk, weapon slots set gun housings and prow mass, cargo capacity sets tank or bay volume, engine count sets drive cones. A freighter must look like a freighter because it IS one, not because a random draw said so
- **Flavour axis as a global modifier** - the human-to-alien dial biases silhouette rules (symmetry, curvature, whether structure is orthogonal or organic) across the whole catalogue rather than being a separate model set

## Open questions

- Whether ship art appears in the design panel, the encyclopedia, the battle replay, or all three
- Whether the alien flavour axis is a per-empire choice made once at race design, or a per-design choice
