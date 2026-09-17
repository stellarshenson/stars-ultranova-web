# Ship Asset Licenses

Every donor asset that may ship as geometry is recorded here: file, source URL, author, license. Anything not listed under Accepted was either never downloaded or was rejected (see Rejected). Reference imagery in `walkthrough/reference/ships/` is inspiration only and never ships - it is deliberately NOT part of this ledger.

License policy: only CC0 and CC-BY (with attribution recorded here) geometry enters `assets/`. ShareAlike (CC-BY-SA), GPL-only, and unverifiable licenses are rejected. Games Workshop, Volition/FreeSpace, and fan-ripped IP never ship as geometry.

## Accepted donors

### Kenney Space Kit - CC0 1.0

- Source: https://kenney.nl/assets/space-kit
- Author: Kenney (kenney.nl)
- License: CC0 1.0 Universal (public domain, per kenney.nl asset page)
- Files: `donors/kenney-space-kit/*.glb` - 35 files selected from the pack's native GLB set, unmodified. Kitbash parts, not whole ships: turrets (`turret_single`, `turret_double`), sensor dishes (`satelliteDish`, `satelliteDish_detailed`, `satelliteDish_large`), rocket stages usable as engine bells and tank stacks (`rocket_baseA/B`, `rocket_fuelA/B`, `rocket_sidesA/B`, `rocket_topA/B`), machinery housings (`machine_barrel`, `machine_barrelLarge`, `machine_generator`, `machine_generatorLarge`, `machine_wireless`, `machine_wirelessCable`), cargo pods and small craft (`craft_cargoA/B`, `craft_miner`), tank clusters (`barrel`, `barrels`, `barrels_rail`), pipework (`pipe_straight`, `pipe_ring`, `pipe_ringHigh`, `pipe_cross`, `pipe_corner`), truss and platform structure (`structure`, `structure_closed`, `structure_detailed`, `supports_high`, `supports_low`)
- Instanced into shipping hull glbs (via `frontend/js/ships3d/donors.js`, geometry retextured to our material families at compile time): `turret_single`, `turret_double`, `satelliteDish_detailed` (warship ladder - Frigate, Destroyer, Cruiser, Battle Cruiser, Battleship, Dreadnought); `craft_cargoA/B`, `barrels`, `pipe_straight` (freighter ladder and Galleon); `rocket_fuelA/B`, `barrels` (fuel transports); `machine_generator`, `machine_barrel`, `pipe_cross`, `supports_low` (miner ladder); `barrels_rail` (mine layers); `rocket_sidesA/B` (rack-spine bombers); `machine_generatorLarge`, `structure_detailed` (colony ships); `craft_cargoA/B` (Assault Transport). The remaining Kenney files stay in the donor store unused this round

### Quaternius Ultimate Spaceships - CC0 1.0

- Source: https://opengameart.org/content/lowpoly-spaceships-pack (CC0 mirror of the pack, uploaded by the author; canonical home https://quaternius.com)
- Author: Quaternius
- License: CC0 1.0 Universal (confirmed on the OpenGameArt entry and on quaternius.com, which links CC0 for all packs)
- Files: `donors/quaternius-ultimate-spaceships/*.glb` - 11 whole ships (`bob`, `challenger`, `dispatcher`, `executioner`, `imperial`, `insurgent`, `omen`, `pancake`, `spitfire`, `striker`, `zenith`). Converted here from the pack's OBJ+texture sources with obj2gltf 3.2.0; the pack's MTL files carried no texture reference, so a `map_Kd` line pointing at each ship's own atlas texture was added before conversion and the atlas is embedded in each GLB. Silhouette and blockout references only - no Quaternius geometry is instanced into shipping hulls

### Majadroid LowPoly Spaceships - CC0 1.0

- Source: https://opengameart.org/content/3d-lowpoly-spaceships-and-components
- Author: Majadroid (Maik Hoffmann)
- License: CC0 1.0 Universal (stated on the OpenGameArt entry and in the pack's own INFO.txt)
- Files: `donors/majadroid-lowpoly-spaceships/majadroid-components.glb`, `majadroid-accessories.glb`, `majadroid-readytofly.glb` - modular hull segments, engine and weapon components, and assembled ships. Converted here from the pack's FBX sources with FBX2glTF 0.9.7 (official Facebook Incubator release binary); the pack's four 512px atlas textures (`tex01-512.png` .. `tex04-512.png`) are kept alongside for retexturing. Held in the donor store; not instanced into shipping hulls this round

## Rejected

- **5 Space Ships** (https://opengameart.org/content/5-space-ships) - CC-BY-SA 3.0; ShareAlike is outside policy
- **Sci-Fi spaceship Ver. 1.0** (https://opengameart.org/content/sci-fi-spaceship-ver-10) - CC-BY-SA 3.0 / GPL only; outside policy
- **Space Transport** (https://opengameart.org/content/space-transport) - CC-BY 3.0 and thus in-policy, but the sole file is a `.blend` and no Blender toolchain exists in this environment to convert it; also two user accounts appear on the entry, leaving the attribution target ambiguous. Not used
- **Shipyard v0.4 customizable spaceships** (https://opengameart.org/content/shipyard-v04-customizable-spaceships) - CC0, but `.blend` only; no converter available. Not used
- **2 Small Terran Space Ships** (https://opengameart.org/content/2-small-terran-space-ships) - CC0, but `.blend` only; no converter available. Not used
- **Quaternius Ultimate Space Kit (Google Drive folder)** - the drive folder download rate-limited partway through and delivered only character mechs and environment blends, none of it ship geometry; superseded by the CC0 OpenGameArt mirror above
- **Sketchfab CC-filtered models** - downloading requires an authenticated account; per-model license could not be verified and fetched headlessly this round, so none were taken
- **NASA 3D resources** - not pursued this round; formats (.3ds/.blend heavy meshes) and film-scale density unsuited to kitbash parts without a conversion toolchain
