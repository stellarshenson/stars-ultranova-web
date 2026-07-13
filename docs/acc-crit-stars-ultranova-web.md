# Acceptance Criteria - Stars Ultranova Web

Feature-parity contract for the web port against the original Stars! Nova (C# reference in `references/original-game/`) plus user-directed web extensions. Verified by unit tests, seeded e2e scenarios (tests/e2e, recorded to logs/e2e) and recorded gameplay passes; test mapping in [FEATURE_CHECKLIST.md](FEATURE_CHECKLIST.md).

## Contents

- [Universe and Setup](#universe-and-setup)
- [Economy and Planets](#economy-and-planets)
- [Production Queue](#production-queue)
- [Research](#research)
- [Race Design](#race-design)
- [Ships and Components](#ships-and-components)
- [Fleets and Movement](#fleets-and-movement)
- [Waypoints and Invasion](#waypoints-and-invasion)
- [Minefields, Gates, Wormholes](#minefields-gates-wormholes)
- [Combat](#combat)
- [Bombing and Colonization](#bombing-and-colonization)
- [Intel and Cloaking](#intel-and-cloaking)
- [Messages, Score, Victory](#messages-score-victory)
- [Spatial Phenomena](#spatial-phenomena)
- [Client UI](#client-ui)
- [AI and Harness](#ai-and-harness)
- [API](#api)
- [Out of Scope](#out-of-scope)

## Universe and Setup

- [x] **Seeded reproducibility** - same seed + same commands -> identical galaxy and identical state digest after N turns
  - log: 2026-07-13 implemented wave 1 (v0.1.0)
- [ ] **Edge: different seed** - different seed -> different galaxy, no digest collision
  - log: 2026-07-13 covered by tests/e2e/test_harness.py; re-verify wave 6
- [ ] **Victory settings** - game creation accepts 8 tunable targets, TargetsToMeet, MinimumGameTime per GameSettings.cs, with New Game settings UI
  - log: 2026-07-13 criterion added, scheduled wave 4
- [x] **PRT starting tech** - each PRT gets C#-exact grants (ProcessPrimaryTraits), AI empires included; IFE +1 Propulsion; ExtraTech +3 all fields (+1 JOAT)
  - log: 2026-07-13 implemented wave 1 (v0.1.0)
- [x] **Leftover points spend** - leftover advantage points convert to homeworld bonuses per HomeStarLeftoverpointsAdjuster, all 5 targets
  - log: 2026-07-13 implemented wave 1 (v0.1.0)
- [x] **Accelerated BBS** - flag on game creation applies C# starting population (100000 vs 25000, LSP x0.7)
  - log: 2026-07-13 implemented wave 1 (v0.1.0)

## Economy and Planets

- [x] **Growth/resources/mining parity** - growth rate, hab scaling, crowding 16/9, PRT max-pop factors, resource rates, concentration depletion match C# parity tests
  - log: 2026-07-13 pre-campaign, regression-tested (v0.1.0)
- [x] **Terraforming** - production item shifts worst env variable 1 click per unit toward race optimum, tech-gated per variable, capped at original +-max, hab recomputes
  - log: 2026-07-13 implemented wave 2 (v0.1.0)
- [x] **CA instaforming** - CA races get 1 free click per variable per year on owned stars
  - log: 2026-07-13 implemented wave 2 (v0.1.0)
- [x] **Retro Bomb** - bombing with Retro Bombs reverses terraform toward original values
  - log: 2026-07-13 implemented wave 2 (v0.1.0)
- [ ] **Edge: terraform without tech** - Terraform order with no terraform component tech is skipped, not blocking
  - log: 2026-07-13 criterion added; verify wave 6
- [ ] **Edge: terraform at cap** - fully terraformed world skips further Terraform units without spending
  - log: 2026-07-13 criterion added; verify wave 6
- [x] **Alchemy** - queue item converts 100 resources -> 1 kT of each surface mineral, 25 with MA LRT, partial progress carries
  - log: 2026-07-13 implemented wave 2 (v0.1.0)
- [x] **Remote mining** - fleets with mining robots at uninhabited stars deposit concentration-scaled minerals on the surface, standard depletion, ARM/OBRM hull gating
  - log: 2026-07-13 implemented wave 2 (v0.1.0)
- [ ] **Edge: remote mine inhabited** - RemoteMine order at an owned/inhabited star is rejected with a message
  - log: 2026-07-13 implemented wave 2; re-verify wave 6
- [x] **Defense type ladder** - defense type upgrades with research (SDI -> Neutron Shield, base coverage 0.0099 -> 0.0379); bombing and invasion use current type
  - log: 2026-07-13 implemented wave 2 (v0.1.0)
- [x] **Planetary scanner upgrades** - scanners auto-upgrade on tech level-up per C# TechLevelUp with messages; type drives scan/pen range
  - log: 2026-07-13 implemented wave 2 (v0.1.0)

## Production Queue

- [x] **Core orders** - factory/mine/defense/ship/starbase orders with partial-build cost carry
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [x] **Auto-build semantics** - auto items skip without blocking when unaffordable and persist across turns; concrete items block per Manufacture.cs
  - log: 2026-07-13 implemented wave 2 (v0.1.0)
- [x] **Queue reorder** - move up/down via command/API and production dialog; auto items visually distinct; percent-complete shown
  - log: 2026-07-13 implemented wave 2 (v0.1.0)
- [ ] **Edge: operable caps** - auto factory/mine stops at operable limits (pop-driven), resumes when pop grows
  - log: 2026-07-13 implemented wave 2; re-verify wave 6
- [ ] **Edge: deleted design in queue** - ship order whose design was deleted is dropped or skipped without crashing the turn
  - log: 2026-07-13 criterion added; verify wave 6

## Research

- [x] **Cost formula** - (Fibonacci(level+5) x 10 + 10 x total attained levels) x race field factor (50/100/175) / 100, integer division per Research.cs
  - log: 2026-07-13 implemented wave 1 (v0.1.0)
- [x] **Cumulative banks + spillover** - per-field research banks cumulative, multiple level-ups per turn, leftover energy contributed from every star
  - log: 2026-07-13 implemented wave 1 (v0.1.0)
- [ ] **Edge: multi-level jump** - a huge bank crosses several level thresholds in one turn, one message each
  - log: 2026-07-13 covered wave 1 unit tests; re-verify wave 6

## Race Design

- [x] **Advantage-point calculator** - faithful RaceAdvantagePointCalculator.cs port: PRT/LRT costs, hab integration with TT correction, growth curve, factory/mine penalties, science table, /3 truncation
  - log: 2026-07-13 implemented wave 1 (v0.1.0); documented deviation: Nova source yields 29 baseline vs its test's ~25
- [x] **Server validation** - over-budget races rejected at game creation with 422; wizard shows live server-computed points
  - log: 2026-07-13 implemented wave 1 (v0.1.0)
- [x] **Wizard fidelity** - wizard races carry hab ranges/immunities, growth, economy, research costs, PRT/LRTs, leftover-point target into gameplay
  - log: 2026-07-13 implemented waves 1-2 (v0.1.0); CF germanium discount landed wave 2
- [ ] **Edge: 3-immune race** - triple immunity scores -3900 exactly (locks trunc-toward-zero /3)
  - log: 2026-07-13 unit-tested wave 1; keep as regression anchor

## Ships and Components

- [x] **Catalog + designer** - 228 components, slot type/capacity and tech gating server-side, engine mandatory, design delete strips fleets
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Electronics in battle** - computers (initiative+accuracy), jammers (torpedo accuracy), capacitors (+beam), deflectors (-beam) honored by the battle engine
  - log: 2026-07-13 criterion added, scheduled wave 4

## Fleets and Movement

- [x] **Fuel fidelity** - live movement burns (mass+cargo) x engine table x warp^2 / 200, IFE x0.85
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Edge: out of fuel** - fleet drops to free/battle warp with a Fuel message, waypoint preserved
  - log: 2026-07-13 implemented pre-campaign; re-verify wave 6
- [x] **Split/merge** - SplitMergeTask.cs semantics: overflow cargo spill, proportional armor pools, merge deletes source
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Repair/refuel table** - situational repair rates 0/1/2/3/5/8/20% per RegenerateFleet; refuel at own/friendly starbases
  - log: 2026-07-13 in progress (wave 3)
- [ ] **Waypoint cargo tasks** - load/unload/set amounts per commodity incl. colonists and fuel, executed in the turn pipeline
  - log: 2026-07-13 implemented wave 3 (cargo-ops, suite 594); verify pending wave 3 verifier
- [ ] **Fleet-to-fleet transfer** - immediate transfer between fleets at the same location via API + dialog
  - log: 2026-07-13 implemented wave 3 (cargo-ops); verify pending
- [ ] **Edge: capacity clamp** - loading beyond cargo capacity clamps; unloading more than held moves only what exists
  - log: 2026-07-13 criterion added; verify wave 6
- [ ] **Edge: transfer at different locations** - fleet-to-fleet transfer rejected unless co-located
  - log: 2026-07-13 criterion added; verify wave 6
- [ ] **Scrap + salvage** - scrap recovery percentages, salvage decays 30%/yr
  - log: 2026-07-13 partial pre-campaign; verify wave 3/6

## Waypoints and Invasion

- [ ] **Task coverage** - Cargo, Colonise, Invade, LayMines, Scrap, SplitMerge, RemoteMine all execute in the pipeline
  - log: 2026-07-13 RemoteMine wave 2, Cargo wave 3; full sweep verify wave 6
- [x] **Invasion math** - full InvadeTask.cs port: 1.1 attacker bonus, 0.75 x pop-coverage defense, troop math
  - log: 2026-07-13 implemented wave 2 (v0.1.0)
- [ ] **Edge: invade starbase-protected world** - invasion blocked/repelled per C# rule
  - log: 2026-07-13 criterion added; verify wave 6

## Minefields, Gates, Wormholes

- [x] **Minefield core** - laying, 1%/yr decay, radius = sqrt(mines), safe warps 4/6/5, canonical hit/damage, fleet stopped, 10-mine expenditure
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Mine sweeping** - beam-armed fleets sweep enemy fields they are inside (canonical rate, gatling special case); field deleted at 0, both owners messaged
  - log: 2026-07-13 scheduled wave 3 (in flight)
- [ ] **SD detonation** - Space Demolition can set standard fields to detonate yearly, damaging non-SD fleets inside
  - log: 2026-07-13 scheduled wave 3 (in flight)
- [ ] **Edge: own field** - own/allied fleets never struck by own mines; sweep does not target own fields
  - log: 2026-07-13 pre-campaign for strikes; sweep case verify wave 6
- [x] **Stargates** - warp-10 jumps honor SafeHullMass/SafeRange, over-limit transit losses
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [x] **Wormholes** - pairs drift by stability, discovered by scan, transit via waypoint within 5 ly
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Edge: gate without destination gate** - jump rejected/no-op with message
  - log: 2026-07-13 pre-campaign; re-verify wave 6

## Combat

- [x] **Engine parity** - stacks, 16x16 grid, initiative + battle-speed movement, attractiveness targeting, weapon-class rules, shield/armor pools, report steps
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Battle plans** - per-fleet plan (attack-who, primary/secondary target types, tactic, max damage %) edited in dialog, honored by engine
  - log: 2026-07-13 criterion added, scheduled wave 4
- [ ] **Player relations** - Enemy/Neutral/Friend per empire drive battle eligibility and invasion legality, relations dialog
  - log: 2026-07-13 criterion added, scheduled wave 4
- [ ] **Edge: neutral contact** - co-located neutral fleets do not battle
  - log: 2026-07-13 criterion added, scheduled wave 4

## Bombing and Colonization

- [x] **Bombing formulas** - coverage 1-(1-base)^n, min kill, installation damage, smart bombs, starbase protection, depopulation -> unowned
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [x] **Colonization** - ship consumed, colonists landed
  - log: 2026-07-13 pre-campaign (v0.1.0)

## Intel and Cloaking

- [x] **Scanning** - best-scanner 4th-root stacking, pen-scan planets, normal-scan fleets, report aging
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Cloaking** - cloak percent (units per kT) reduces detection range; tachyon detectors counter on the scanning fleet
  - log: 2026-07-13 scheduled wave 3 (in flight)
- [ ] **Design learning** - detecting an enemy fleet records its hull/design in observer intel; battles reveal full designs
  - log: 2026-07-13 scheduled wave 3 (in flight)
- [ ] **Edge: cloaked in orbit** - cloak reduces range, never prevents detection at distance ~0
  - log: 2026-07-13 criterion added; verify wave 6

## Messages, Score, Victory

- [ ] **Message goto** - typed messages link to the referenced object (fleet/star/battle)
  - log: 2026-07-13 partial pre-campaign; completion scheduled wave 5
- [ ] **Score** - C# formula (planets, starbases +3, colonists/100k, resources/30, ship classes, tech), ScoreRecord history, score report UI
  - log: 2026-07-13 criterion added, scheduled wave 4
- [ ] **Victory** - last-standing plus 8 configurable targets evaluated after MinimumGameTime, TargetsToMeet honored
  - log: 2026-07-13 criterion added, scheduled wave 4
- [ ] **Edge: before minimum time** - no victory declared before MinimumGameTime even if targets met
  - log: 2026-07-13 criterion added, scheduled wave 4

## Spatial Phenomena

- [x] **Dust nebulae** - slow ships up to 40% and dampen scanners up to 50% by local dust density
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Storm shape** - irregular blob perimeter (radial noise), dashed red boundary surrounding the storm, drift + bounce preserved
  - log: 2026-07-13 user directive; scheduled wave 3 (in flight)
- [ ] **Storm intensity field** - local intensity ramps boundary -> core -> boundary; ALL effects sample local intensity at fleet position
  - log: 2026-07-13 user directive; scheduled wave 3 (in flight)
- [ ] **Storm hazards** - locally-scaled hull damage; warp risk above safe warp (mishap = extra damage + fleet stopped); scan dampening stronger than dust; colonist attrition per turn
  - log: 2026-07-13 user directive; scheduled wave 3 (in flight)
- [ ] **Storm spawning** - storms preferentially spawn inside nebulae
  - log: 2026-07-13 user directive; scheduled wave 3 (in flight)
- [ ] **Edge: outside boundary** - zero storm effect outside the blob; starbases immune inside
  - log: 2026-07-13 criterion added; verify wave 6
- [ ] **Orbit safe harbor** - storms never affect planets, nor fleets and stations in orbit of a planet; only fleets in open space inside the storm suffer effects
  - log: 2026-07-13 user directive; scheduled wave 4
- [ ] **Storm shields** - researchable storm shield components join the catalog (tech-gated discovery); equipped ships negate/strongly reduce all storm effects (damage, mishap, colonist attrition)
  - log: 2026-07-13 user directive; scheduled wave 4
- [ ] **Standard shields vs storms** - conventional shields grant partial storm protection scaled by shield rating
  - log: 2026-07-13 user directive; scheduled wave 4
- [ ] **Armor vs storms** - armor grants a smaller but non-zero storm damage reduction
  - log: 2026-07-13 user directive; scheduled wave 4
- [ ] **Edge: protection stacking** - storm shield + standard shield + armor compose without exceeding full immunity; unshielded hull takes full local effect
  - log: 2026-07-13 criterion added; scheduled wave 4
- [ ] **Total immunity attainable** - full storm immunity is realistically reachable (top-tier storm shields alone, or high-tier combinations) by mid-to-late game tech
  - log: 2026-07-13 user directive; scheduled wave 4
- [ ] **Radiation-hardened races** - races accustomed to radiation (high radiation tolerance or radiation immunity) get inherent storm resilience on all their ships
  - log: 2026-07-13 user directive; scheduled wave 4
- [ ] **Storm balance calibration** - hazard and protection numbers calibrated via seeded trial games (survival rates with/without protection recorded and reviewed); constants adjusted until the curve feels right
  - log: 2026-07-13 user directive; calibration pass scheduled wave 6
- [ ] **Encyclopedia** - Help menu opens Encyclopedia with numbered entries (dust/emission nebulae, storms, wormholes, minefields, stargates) stating actual gameplay numbers
  - log: 2026-07-13 user directive; scheduled wave 3 (in flight)
- [ ] **Phenomena tooltips** - map hover explains the phenomenon and links to its encyclopedia entry
  - log: 2026-07-13 user directive; scheduled wave 3 (in flight)

## Client UI

- [ ] **Map layers** - scanner overlays, minefields, storms, wormholes, fleet paths render truthfully from player state
  - log: 2026-07-13 pre-campaign partial; storm blob rendering wave 3
- [ ] **Zoom clamp** - zoom-out limited to best-fit / 1.2 (~20% over board) in all zoom paths; zoom-in unchanged
  - log: 2026-07-13 user directive; scheduled wave 3 (in flight)
- [ ] **Dialog parity** - production (auto items, % complete), research, designer, battle plans, relations, cargo (fleet-to-fleet), split, rename, race wizard with live points
  - log: 2026-07-13 partial waves 1-2; plans/relations wave 4
- [ ] **Waypoint editing** - insert/modify legs, per-leg warp incl. warp-10 gate; multi-fleet same-location picker
  - log: 2026-07-13 criterion added, scheduled wave 5
- [ ] **Reports** - planets, fleets, battles (viewer replay), score
  - log: 2026-07-13 partial pre-campaign; score report wave 4
- [ ] **Panel polish** - no text touching panel borders in the left column; consistent margins/padding on sections, labels, values, bars; clean at 1080p and 1440p
  - log: 2026-07-13 user directive; scheduled wave 5
- [ ] **Race icons** - 16 designed SVG emblem icons replace numbered boxes; custom icon upload per player, stored with the race, shown in wizard/race select/empire summary/reports
  - log: 2026-07-13 user directive; scheduled wave 5
- [ ] **Edge: invalid icon upload** - non-image or oversized upload rejected with a clear message, selection unchanged
  - log: 2026-07-13 criterion added, scheduled wave 5

## AI and Harness

- [x] **AI campaigns** - AI empires produce, expand, fight and finish seeded games without errors
  - log: 2026-07-13 re-verified every wave regression (v0.1.0)
- [ ] **Full acceptance harness** - seeded e2e scenarios exercise every criterion above marked for e2e, JSONL recordings kept, full suite + autoplay regression green, browser gameplay pass recorded (screenshots per wave in walkthrough/final/)
  - log: 2026-07-13 harness live wave 1; full gate scheduled wave 6

## API

- `POST /api/races/validate` body = wizard race payload -> `{points, legal, breakdown}`; used live by the wizard footer
- `POST /api/games` body incl. `race`, `seed`, `accelerated_start` -> game; 422 `race over budget`
- `GET /api/games/{id}/empires/{eid}/state` -> player-scoped fog-of-war state (stars, fleets, storms, minefields, wormholes, messages)
- `GET /api/games/{id}/empires/{eid}/battles` -> battle reports for the viewer
- `POST /api/games/{id}/fleets/{key}/split` / `/merge` -> fleet ops
- Production queue, waypoint, research, design commands via `POST /api/games/{id}/empires/{eid}/commands`

## Out of Scope

Declared exclusions for this campaign - future candidates, not acceptance blockers:

- [ ] **Mystery trader + random events** - absent in the C# reference, canonical-only
  - log: 2026-07-13 excluded by scope decision
- [ ] **Mineral packets + mass drivers** - wave 5 decides: minimal canonical implementation or clean removal of the `_move_mineral_packets` remnant, documented either way
  - log: 2026-07-13 decision deferred to wave 5
- [ ] **Multiplayer turn submission** - per-player order files, passwords, turn locking; web port is single-human live API
  - log: 2026-07-13 excluded by scope decision
- [ ] **Extended diplomacy** - beyond the 3-state relations model
  - log: 2026-07-13 excluded by scope decision
