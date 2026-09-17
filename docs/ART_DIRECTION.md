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
- **No aircraft anatomy in vacuum** - user directive: 80s-style bomber wings and tails are "just wrong; the only reason for a bomber to have wings is to carry weapons". No aerofoils, no empennage, no aircraft silhouettes anywhere. A bomber is an ordnance frame: a spine or truss whose spars exist to hang bomb racks and hardpoints, plus drive and RCS. If a spar carries no weapon, radiator or sensor, it does not exist. Attitude control is RCS, never a tail
- **The 3D model is the primitive** - user directive after rejecting the SDF sprite sheet: hulls are compiled, textured 3D models (`assets/ships/<hull>.glb`, PBR materials, baked maps) and every sprite or render is derived from the model at whatever resolution and angle is wanted - "improve resolution much more; we can always scale down". Intricate detail is mandatory: dense greebles, layered plating, material separation, no toy-grey boxes
- **Class identity round** - user rulings on the rebuilt fleet gallery: "more clear differences" between classes; bombers must "look like bombers" - the hung ordnance is the identity, rows of visible bombs and torpedoes on the racks, payload reading at sheet scale; the battleship prow: "no ram, just that characteristic front of the w40k ships" - NO projecting ram beam or rostrum spar; the front IS the identity: the classic W40k armoured prow blade, one massive angled wedge face spanning the full bow height, layered armour facets; profile per user spec "wide at the bottom, and retracted + narrower to the top" - the bottom juts furthest forward and carries the greatest width, the face rakes backward and narrows rising (the underbite blade), broad keel to narrow crest, dominating the bow on capitals; second ruling: the blade belongs to EVERY warship scaled to its class, Frigate to Dreadnought - one prow language for the family, and stronger everywhere: the prow is the single most massive element of every warship silhouette; "colony ships must be bulkier" - fat pressurised volume, habitat domes and life-support mass, the fattest hulls in the fleet; "miners must look like they are purpose built" - visible working tools: drill booms, bucket wheels, intake maws, ore hoppers, conveyor spines, floodlights; "and probes?" - the Armed Probe design gets its own model instead of the generic scout hull: UNMANNED identity - no windows, no habitat mass, instrument booms, dish, sensor cluster, a drive disproportionate for its size ('probe' record; the design-to-model mapping is frontend-only via DESIGN_MODEL_OVERRIDES in records.js, backend hull tables untouched)
- **Silhouette distance gate** - class identity is measured, not asserted: all 33 hulls render as 256 px black-on-white silhouettes (`tools/ships3d_sil.html`) and every pair's mask IoU is checked (`tools/ships3d_silhouette_check.py`); no cross-family or cross-class pair may reach IoU 0.85, while same-role size-ladder neighbours may share their family language. The round that installed the gate split three near-twins: the Privateer became a fat stubby rust trader against the Rogue's dark lean smuggler hull (stealth palette, twin oversized outboard nacelles); the Cruiser raised a tall stern-castle bridge and crenellated spine against the Destroyer's low-slung trench hull; the Galleon traded its container stack for a wide flat single cargo deck under a dorsal line of four oversized turrets - the armed merchantman, not another freighter
- **Reference-driven, ready models as inspiration** - user directive after the first generated fleet: "Redo; pick some ready 3d models... and use as inspiration". The build studies real ship models - W40k Battlefleet Gothic capital ships, FreeSpace fleets, quality sci-fi model kits - and drives our proportions and anatomy from them. Inspiration is IP-safe; geometry is not: only clean-licensed (CC0 / CC-BY) models may be used as kitbash donor geometry, every donor recorded with license and author in assets/ships/LICENSES.md. GW and Volition assets never ship
- **Stern is an engine block** - user directive: "back of the ship is weird" - a bare box with flat fins is rejected. Clustered thruster bells recessed in an armoured housing, glowing exhausts that read at sheet scale, radiators integrated as edge fins, the block looking like it pushes a million tonnes
- **Prow is solid volume** - user directive: "this is some very weird prow" - open framework, spars or gantries at the bow are forbidden; the ram is closed plated mass that could survive ramming a station
- **Broadside batteries on the battle line** - user directive: "Battleships need broadside capability". Battleship, Dreadnought and Battle Cruiser carry their main armament as flank gun decks - rows of turreted batteries and gun ports arrayed down BOTH sides, ship-of-the-line fashion, with tiered decks on the Dreadnought. Spinal and prow weapons remain, but the broadside is the visual centre of mass: the flank reads as a wall of guns
- **Ever more intricate** - user directive: "more intricate designs please" - standing pressure, not a one-time bar. Capitals should run well past the proof's 68k triangles; gun decks carry individual barrels, sensor gardens, tiered superstructure, dense emissive window fields that read as a crewed city
- **Galley-ram prow on warships** - user directive on the Destroyer proof: "stronger, more wedged prow, more w40k style, like greek galera style". The warship prow is a massive armoured RAM in the trireme lineage: a deep V-wedge in both profile and plan, leading edge a reinforced ram beam layered like a plough, extending well forward of the hull mass, gothic beak allowed on capitals. The prow leads the ship; the silhouette reads as a weapon before the guns do
- **Alien flavour knob renders incarnations** - user directive: the gallery ships at multiple positions of the human-to-alien dial - the same hull re-rendered as the knob turns. The flavour parameter lives in the design record and biases the compiler (symmetry, curvature, orthogonal vs organic structure, palette), so every hull has human, mid and alien incarnations from one record
- **Futuristic, FreeSpace-inflected** - user directive: "must be more futuristic, borrow some design concepts from FreeSpace". From Volition's language: faceted angular hulls, forward mandible prongs and split prows on combat hulls, turret blisters distributed over the surface, beam-cannon apertures cut into the prow, glowing hangar maws on capitals and carriers, clustered engine exhausts with strong saturated glow, superstructure towers and greebled trenches on the big slabs, strong one-glance silhouette identity per class. Blend, do not replace: FreeSpace futurism over Expanse engineering with W40k mass

### How 200-300 hulls get built

Not by hand. The same architecture that already solved diverse worlds: a small set of role archetypes plus a seeded parameter space, so each design is generated deterministically from its own name and looks identical on every visit. `PlanetArt` reaches unlimited distinct worlds from nine classes and fifteen seeded parameters; ships work the same way.

- **Archetype per role** - the generator keys off the SAME role cascade the battle engine uses for target-class orders (capital, escort, support, logistics, boarding), so a ship that reads as a tanker IS a tanker to the targeting code. One source of truth for what a ship is
- **Seeded parameters** - hull proportions, module count and placement, drive-cone count, armour banding, prow treatment, greeble density, panel albedo, all drawn in fixed order from a hash of the design name
- **Correlated to the real design** - the parameters that can be driven by game state should be: mass and hull size set bulk, weapon slots set gun housings and prow mass, cargo capacity sets tank or bay volume, engine count sets drive cones. A freighter must look like a freighter because it IS one, not because a random draw said so
- **Flavour axis as a global modifier** - the human-to-alien dial biases silhouette rules (symmetry, curvature, whether structure is orthogonal or organic) across the whole catalogue rather than being a separate model set

## Open questions

- Whether ship art appears in the design panel, the encyclopedia, the battle replay, or all three
- Whether the alien flavour axis is a per-empire choice made once at race design, or a per-design choice
