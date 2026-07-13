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
- [Mystery Trader](#mystery-trader)
- [Client UI](#client-ui)
- [AI and Harness](#ai-and-harness)
- [Correspondence Play](#correspondence-play)
- [Extensions](#extensions)
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
- [x] **Electronics in battle** - computers (initiative+accuracy), jammers (torpedo accuracy), capacitors (+beam), deflectors (-beam) honored by the battle engine
  - log: 2026-07-13 criterion added, scheduled wave 4
  - log: 2026-07-14 design aggregation landed (probability stacking for jammers/computers/deflectors, geometric for capacitors with 250 cap per Capacitor.cs:41) plus consumption in both battle engines - torpedo accuracy = computers cut miss chance, jammers cut hit chance; beam damage x (1+cap/100) x (1-defl/100); tests/unit/test_ship_design.py::TestElectronicsAggregation, tests/unit/test_battle_engine.py::TestElectronicsInBattle, seeded e2e tests/e2e/test_electronics_battle.py (jammed target takes 0.64x torpedo damage; capacitor ship out-damages plain ship)

## Fleets and Movement

- [x] **Fuel fidelity** - live movement burns (mass+cargo) x engine table x warp^2 / 200, IFE x0.85
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Edge: out of fuel** - fleet drops to free/battle warp with a Fuel message, waypoint preserved
  - log: 2026-07-13 implemented pre-campaign; re-verify wave 6
- [x] **Split/merge** - SplitMergeTask.cs semantics: overflow cargo spill, proportional armor pools, merge deletes source
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [x] **Repair/refuel table** - situational repair rates 0/1/2/3/5/8/20% per RegenerateFleet; refuel at own/friendly starbases
  - log: 2026-07-13 in progress (wave 3)
  - log: 2026-07-13 implemented wave 3 (repair-refuel, suite 620; tests/e2e/test_repair_refuel.py); verify pending wave 3 verifier
  - log: 2026-07-13 met - wave 3 verifier: full suite 682 green; dock 20 pts/yr re-proven in tests/e2e/test_wave3_integration.py
- [x] **Waypoint cargo tasks** - load/unload/set amounts per commodity incl. colonists and fuel, executed in the turn pipeline
  - log: 2026-07-13 implemented wave 3 (cargo-ops, suite 594); verify pending wave 3 verifier
  - log: 2026-07-13 met - wave 3 verifier: tests/e2e/test_cargo_ops.py green; cloaked-freighter cargo route in tests/e2e/test_wave3_integration.py
- [x] **Fleet-to-fleet transfer** - immediate transfer between fleets at the same location via API + dialog
  - log: 2026-07-13 implemented wave 3 (cargo-ops); verify pending
  - log: 2026-07-13 met - wave 3 verifier: tests/e2e/test_cargo_ops.py::TestCargoOps::test_fleet_to_fleet_transfer incl. over-transfer rejection
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
  - log: 2026-07-13 re-verified wave 3 verifier: 10 tests in tests/unit/test_defenses.py::TestInvasion (bonuses, coverage, 100-colonist floor, tie wipe, starbase cancel, ownership transfer)
- [ ] **Edge: invade starbase-protected world** - invasion blocked/repelled per C# rule
  - log: 2026-07-13 criterion added; verify wave 6

## Minefields, Gates, Wormholes

- [x] **Minefield core** - laying, 1%/yr decay, radius = sqrt(mines), safe warps 4/6/5, canonical hit/damage, fleet stopped, 10-mine expenditure
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [x] **Mine sweeping** - beam-armed fleets sweep enemy fields they are inside (canonical rate, gatling special case); field deleted at 0, both owners messaged
  - log: 2026-07-13 implemented wave 3 (tests/unit/test_mine_sweeping.py, tests/e2e/test_mine_sweeping.py)
- [x] **SD detonation** - Space Demolition can set standard fields to detonate yearly, damaging non-SD fleets inside
  - log: 2026-07-13 implemented wave 3 (canonical: damages every fleet inside, owner's own included; detonate_minefield command, owner-only flag)
- [ ] **Edge: own field** - own/allied fleets never struck by own mines; sweep does not target own fields
  - log: 2026-07-13 pre-campaign for strikes; sweep case verify wave 6
- [x] **Stargates** - warp-10 jumps honor SafeHullMass/SafeRange, over-limit transit losses
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Gate hull limit** - only small and medium hulls may gate; large and capital hulls are refused outright (no over-limit gamble for them) - deliberate deviation from canonical, keeps heavy fleets flying conventionally while light forces teleport
  - log: 2026-07-13 user directive - "no stargates for large ships, only small up to medium ones"; scheduled wave 5
- [ ] **Star-fuelled gate range** - gates are powered by their host star: reach scales with the star's size (the larger the star, the farther the gate throws), always bounded - no unlimited-range gates
  - log: 2026-07-13 user directive - "not too far... fuelled by the presence of the nearby star (the larger the star, the larger the distance)"; scheduled wave 5
- [ ] **No minerals through gates** - gates move ships only; loose mineral logistics stay with mass drivers (packets) and freighters
  - log: 2026-07-13 user directive; scheduled wave 5 with the packets decision
- [x] **Wormholes** - pairs drift by stability, discovered by scan, transit via waypoint within 5 ly
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Edge: gate without destination gate** - jump rejected/no-op with message
  - log: 2026-07-13 pre-campaign; re-verify wave 6

## Combat

- [x] **Engine parity** - stacks, 16x16 grid, initiative + battle-speed movement, attractiveness targeting, weapon-class rules, shield/armor pools, report steps
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [x] **Battle plans** - per-fleet plan (attack-who, primary/secondary target types, tactic, max damage %) edited in dialog, honored by engine
  - log: 2026-07-13 criterion added, scheduled wave 4
  - log: 2026-07-13 implemented wave 4; per-empire named plans (canonical 14-plan cap) with battle_plan CRUD command + POST /fleets/{key}/battle-plan assignment, Battle Plans dialog in the Commands menu (two-pane, working New/Save/Delete - the C# dialog's edit buttons are disabled) and per-fleet plan selector in the fleet panel; Ron engine honors attack-who incl. dialog-only "Enemies and Neutrals" (canonical, BattleEngine.cs never checked it), five target tiers gate engagement and fire allocation (priority target eats the fire first), tactics Disengage (7 flee moves -> leaves the battle), Disengage if Challenged, stand-off variants (canonical-approx; standard engine stays C#-exact per BattleEngine.cs); "max damage %" -> Ron percent-to-fire overkill allocation; tests/unit/test_battle_engine.py TestBattlePlan/TestAreEnemies/TestRonTargetPriority/TestTactics + tests/e2e/test_battle_plans.py (CRUD round-trip, disengaging freighter escapes while escort fights, control freighter destroyed, deterministic digests)
- [x] **Player relations** - Enemy/Neutral/Friend per empire drive battle eligibility and invasion legality, relations dialog
  - log: 2026-07-13 criterion added, scheduled wave 4
  - log: 2026-07-13 implemented wave 4; per-opponent relation map initialized all-Enemy at game creation (GameInitialiser.cs:132-143), "relation" command + F7 dialog (correct Neutral display, C# bug not ported); honored by battle targeting (default plan attack="Enemies", BattlePlan.cs:44), invasion cancel (InvadeTask.cs:110-131, colonists kept aboard), bombing gate (Bombing.cs:59-64), minefield strike friend-skip, enemy-only sweeping and friendly-starbase refuel/repair (canonical); tests/unit/test_relations.py (29 tests), tests/e2e/test_relations.py
- [x] **Edge: neutral contact** - co-located neutral fleets do not battle
  - log: 2026-07-13 criterion added, scheduled wave 4
  - log: 2026-07-13 met wave 4; seeded e2e parks two armed warships on one deep-space point at mutual Neutral over several turns with zero battles, then both declare Enemy and the same encounter fights (tests/e2e/test_relations.py); engine-level Neutral-not-targeted case for both battle engines in tests/unit/test_battle_engine.py

## Bombing and Colonization

- [x] **Bombing formulas** - coverage 1-(1-base)^n, min kill, installation damage, smart bombs, starbase protection, depopulation -> unowned
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [x] **Colonization** - ship consumed, colonists landed
  - log: 2026-07-13 pre-campaign (v0.1.0)

## Intel and Cloaking

- [x] **Scanning** - best-scanner 4th-root stacking, pen-scan planets, normal-scan fleets, report aging
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [x] **Cloaking** - cloak percent (units per kT) reduces detection range; tachyon detectors counter on the scanning fleet
  - log: 2026-07-13 scheduled wave 3 (in flight)
  - log: 2026-07-13 met wave 3 - canonical units curve + fleet dilution (SS/ISB rules) in scan step; tests/unit/test_ship_design.py::TestCloaking, tests/unit/test_turn_generator.py::TestScanStepCloaking, tests/e2e/test_cloaking_intel.py
- [x] **Design learning** - detecting an enemy fleet records its hull/design in observer intel; battles reveal full designs
  - log: 2026-07-13 scheduled wave 3 (in flight)
  - log: 2026-07-13 met wave 3 - hull-only records on scan (ScanStep.cs:170-183 port), full designs on battle (BattleEngine.cs:347-368 port), persisted empire_reports, enemy_designs in player state; tests/unit/test_turn_generator.py::TestScanStepCloaking, tests/unit/test_battle_engine.py::TestBattleDesignLearning, tests/e2e/test_cloaking_intel.py
- [x] **Edge: cloaked in orbit** - cloak reduces range, never prevents detection at distance ~0
  - log: 2026-07-13 criterion added; verify wave 6
  - log: 2026-07-13 met wave 3 - 98% cloak cap guarantees detection at distance 0; tests/unit/test_turn_generator.py::TestScanStepCloaking::test_cloaked_fleet_always_detected_at_distance_zero

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
- [x] **Storm shape** - irregular blob perimeter (radial noise), dashed red boundary surrounding the storm, drift + bounce preserved
  - log: 2026-07-13 implemented wave 3; 32 sampled radii from 2-4 sine harmonics, polygon rendering; tests/unit/test_phenomena.py::TestStormShape
- [x] **Storm intensity field** - local intensity ramps boundary -> core -> boundary; ALL effects sample local intensity at fleet position
  - log: 2026-07-13 implemented wave 3; smoothstep ramp, get_intensity_at; tests/unit/test_phenomena.py::TestStormShape, TestStormHazards
- [x] **Storm hazards** - locally-scaled hull damage; warp risk above safe warp (mishap = extra damage + fleet stopped); scan dampening stronger than dust; colonist attrition per turn
  - log: 2026-07-13 implemented wave 3; mishap 10%/warp above 6 capped 75%, scan 0.7 penalty, attrition ceil(10% x local); tests/e2e/test_storms.py
- [x] **Storm spawning** - storms preferentially spawn inside nebulae
  - log: 2026-07-13 implemented wave 3; ~70% nebula-biased rejection sampling on a seed-derived RNG; tests/unit/test_phenomena.py::TestStormSpawning
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
- [x] **Encyclopedia** - Help menu opens Encyclopedia with numbered entries (dust/emission nebulae, storms, wormholes, minefields, stargates) stating actual gameplay numbers
  - log: 2026-07-13 implemented wave 3; frontend/js/views/encyclopedia.js, Help → Encyclopedia in menu-bar.js; entries mirror globals.py / MINE_STATS / gate catalog numbers; met with browser evidence wave 6
- [ ] **Emission nebula glare** - emission nebulae are not inert: their glow washes out sensors for a small scanner-range penalty at high glow density (constant in globals, far milder than dust), no effect on ship speed; encyclopedia entry updated to match
  - log: 2026-07-13 user directive - "must have some small effect, not entirely inert... maybe small sensor hit?"; scheduled wave 5
- [x] **Encyclopedia imagery** - every phenomenon entry carries beautiful, hand-painted-feel artwork (deterministic procedural painting, consistent style across entries, no external assets)
  - log: 2026-07-13 user directive - "beautiful, like-hand-painted imagery" for all phenomena
  - log: 2026-07-13 implemented - EncyclopediaArt in encyclopedia.js: seeded painterly canvas per entry (layered brush strokes, gradient billows, grain, vignette); all 6 entries browser-verified (walkthrough/final/wave3/07-12)
- [x] **Phenomena tooltips** - map hover explains the phenomenon and links to its encyclopedia entry
  - log: 2026-07-13 implemented wave 3; galaxy-map.js hit-testing (storm blob local intensity, wormhole endpoints, minefield circles, dust density from nebula regions) + dark tooltip with Encyclopedia link; met with browser evidence wave 6

## Mystery Trader

Canonical Stars! feature the C# reference never implemented (only a TODO in GameInitialiser.cs:180) - built directly from canonical rules per user directive, like mine sweeping was.

- [ ] **Spawning** - from mid-game on, a trader periodically enters at a galaxy edge and crosses the map in a straight line at high warp (canonical 7-13), exiting the far side; multiple traders possible late game
  - log: 2026-07-13 user directive: canonical feature, model directly; scheduled wave 5
- [ ] **Universal visibility** - every empire sees the trader and its course from the moment it spawns, regardless of scanners; spawn and departure broadcast to all empires; distinct map marker
  - log: 2026-07-13 user directive; scheduled wave 5
- [ ] **Untouchable** - cannot be attacked, invaded, or struck by mines; storms do not harm it; it never initiates hostilities
  - log: 2026-07-13 user directive; scheduled wave 5
- [ ] **Intercept and gift** - a fleet at the trader's position may transfer minerals or colonists to it as a gift; the trader always keeps the cargo
  - log: 2026-07-13 user directive; scheduled wave 5
- [ ] **Rewards** - a gift at or above the threshold earns a reward from the canonical table: a Mystery Trader component (hidden tech), research level boosts, minerals/fuel, or a gifted ship; reward scales with gift size; chosen thresholds and odds documented in code comments and the encyclopedia
  - log: 2026-07-13 user directive; scheduled wave 5
- [ ] **Hidden technology** - trader-exclusive components (canonical MT items such as Multi-Function Pod, Anti-Matter Torpedo, Genesis Device) cannot be researched; once granted, the empire can build them and they appear in its component catalog
  - log: 2026-07-13 user directive; matches the C# TODO's "hidden technology" note; scheduled wave 5
- [ ] **Moving waypoint target** - fleets can set the trader as a waypoint target; intercept course recomputed each turn
  - log: 2026-07-13 criterion added; scheduled wave 5
- [ ] **Game setting** - "Mystery Trader" toggle at game creation, default on
  - log: 2026-07-13 criterion added; scheduled wave 5
- [ ] **Encyclopedia + tooltip** - encyclopedia article stating actual thresholds and reward odds; map hover tooltip links to it
  - log: 2026-07-13 criterion added; scheduled wave 5
- [ ] **Determinism** - spawn timing, course, and rewards reproduce bit-for-bit in seeded games
  - log: 2026-07-13 criterion added; scheduled wave 5
- [ ] **Edge: below-threshold gift** - trader keeps the cargo, no reward, giver messaged
  - log: 2026-07-13 criterion added; scheduled wave 5
- [ ] **Edge: multiple empires intercept** - gifts tracked per empire; simultaneous intercepts resolve independently
  - log: 2026-07-13 criterion added; scheduled wave 5

## Client UI

- [ ] **Map layers** - scanner overlays, minefields, storms, wormholes, fleet paths render truthfully from player state
  - log: 2026-07-13 pre-campaign partial; storm blob rendering wave 3
- [x] **Zoom clamp** - zoom-out limited to best-fit / 1.2 (~20% over board) in all zoom paths; zoom-in unchanged
  - log: 2026-07-13 implemented wave 3; galaxy-map.js minAllowedZoom() enforced in wheel, +/- keys, menu zoom (via setZoom), setZoom and game load; zoomToFit unchanged at best fit; met with browser evidence wave 6
- [ ] **Dialog parity** - production (auto items, % complete), research, designer, battle plans, relations, cargo (fleet-to-fleet), split, rename, race wizard with live points
  - log: 2026-07-13 partial waves 1-2; plans/relations wave 4
  - log: 2026-07-13 relations dialog landed wave 4 (F7, empire list + Enemy/Neutral/Friend radio group, immediate apply per PlayerRelations.cs:104-120, C# Neutral-displays-as-Friend bug not ported); battle plans UI still pending
  - log: 2026-07-13 battle plans dialog landed wave 4 (Commands menu, two-pane list + details with name, five target tiers, tactic, attack; working New/Save/Delete unlike the disabled C# buttons; per-fleet plan selector in fleet panel); criterion stays open pending remaining dialog checks
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
- [x] **Credits dedication** - the game credits (Help menu About dialog) carry the dedication "For my beloved son Henry, alienated from his father for so long..." and the thanks "with thanks to my beloved wife Ewa" - each named once; present in every build, verified in the browser pass
  - log: 2026-07-13 user directive - the dedication is a permanent, non-negotiable credit
  - log: 2026-07-13 dedication wording finalized by the user
  - log: 2026-07-13 thanks to beloved wife Ewa added by the user
  - log: 2026-07-13 implemented in menu-bar.js showAbout, verified in browser (walkthrough/final/wave3/01-about-dedication.png)
  - log: 2026-07-13 user fix: Henry named once, Ewa once - thanks line reworded, re-verified

## AI and Harness

- [x] **AI campaigns** - AI empires produce, expand, fight and finish seeded games without errors
  - log: 2026-07-13 re-verified every wave regression (v0.1.0)
- [ ] **Full acceptance harness** - seeded e2e scenarios exercise every criterion above marked for e2e, JSONL recordings kept, full suite + autoplay regression green, browser gameplay pass recorded (screenshots per wave in walkthrough/final/)
  - log: 2026-07-13 harness live wave 1; full gate scheduled wave 6

## Correspondence Play

The C# reference's turn-submission model (per-player orders files, turn-submitted flags, race passwords - [C# ok] in the mechanics inventory) adapted to the web port: the game travels between people as files so each may play their turn.

- [ ] **Turn package export** - the host exports a per-empire turn package: that empire's fog-of-war player state for the current year, as a portable versioned JSON file
  - log: 2026-07-13 user requirement; awaits campaign slot (wave 5 candidate)
- [ ] **Orders file round-trip** - the recipient plays their turn against the package and exports an orders file (commands only); the host imports it and the orders apply exactly as if entered live
  - log: 2026-07-13 user requirement
- [ ] **Full-game handoff** - alternatively the entire game file travels: the recipient imports it, plays only their own empire, and sends it onward - hot-seat by correspondence
  - log: 2026-07-13 user requirement - "sending a turn / game state file to another person, so they may play their turn"
- [ ] **Race password** - each empire may set a password per the C# reference; opening an empire's view or submitting its orders requires it
  - log: 2026-07-13 criterion added (C# parity: password per race)
- [ ] **Turn locking** - an empire's orders lock once submitted (turn-submitted flag per C#); the year advances only when every human empire has submitted
  - log: 2026-07-13 criterion added (C# parity: turn-submitted flags)
- [ ] **Fog integrity** - a per-empire package contains only that empire's fog-of-war view; the full game file is meant for the host/carrier and says so on import
  - log: 2026-07-13 criterion added
- [ ] **Determinism** - a game played by correspondence replays to the same digest as the identical game played live
  - log: 2026-07-13 criterion added
- [ ] **UI** - Game menu: export turn package / export game file / import orders / import game; submission status per empire visible
  - log: 2026-07-13 criterion added
- [ ] **Edge: stale package** - orders produced against an outdated year are rejected with a clear message, nothing corrupted
  - log: 2026-07-13 criterion added

## Extensions

Web-only concepts beyond the C# reference, recorded for a future implementation slot. Each ships only when its full rule set lands together - a partial superweapon is worse than none.

### Exterminatus weapon (star killer)

- [ ] **Game setting gate** - "Allow Exterminatus" toggle at game creation, default off; research, build and fire paths all disabled when off
  - log: 2026-07-13 user directive (concept recorded); unscheduled - awaits campaign slot
- [ ] **Endgame prerequisite** - demands near-top tech across several fields and an astronomical resource + mineral cost on a dedicated single-purpose hull; only a mature endgame economy can field one
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Singular device** - at most one in existence per empire; consumed on firing (one shot)
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Visible from afar** - detected by every empire at any range, cannot be cloaked, rendered as a distinct map marker; all empires messaged when it is completed, each turn it moves, and when it fires
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Slow and alone** - hard warp cap (slower than fleet norm) and travels as a lone fleet - escorts must fly as separate fleets, so defenders can engage it directly
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Storm vulnerability** - storm effects amplified against it and no storm protection applies (storm shields, standard shields, armor all void); a storm mishap detonates the device in place
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **No wormhole or stargate transit** - attempting either detonates the device at the entry point
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Detonation blast** - destruction by any cause (battle, storm, wormhole attempt) detonates it: every fleet at the location takes massive damage and a permanent galactic storm forms at the blast site
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Star kill** - fired at a star via waypoint task: population and installations annihilated, habitability zeroed permanently, surface minerals vaporized, concentrations slagged; the corpse can never be colonized or terraformed again
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Dead star spawns storm** - the killed system births a permanent galactic storm centered on the dead star
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Wrath of Milena** - the permanent storm born of an Exterminatus star kill or device detonation is a named phenomenon: labeled "Wrath of Milena" on the map instead of the generic storm label, with its own encyclopedia entry telling what happened there
  - log: 2026-07-13 user directive - destructive effect named by the user
- [ ] **Diplomatic fallout** - firing sets every other empire's relation to the firer to Enemy, locked for a configurable number of years, plus a heavy score penalty
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Interceptable** - engageable in battle like any ship and deliberately fragile (no shields mountable), so the launch broadcast opens a real interception window before it reaches the target
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Encyclopedia entry** - dedicated encyclopedia article stating all rules and actual numbers; map marker tooltip links to it
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Edge: homeworld target** - homeworlds are valid targets; victory and score checks handle an empire whose last world is killed
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Edge: destroyed mid-flight** - target star survives; blast and permanent storm occur at the destruction point instead
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Balance calibration** - costs, warp cap, blast damage, fallout duration tuned by trial games before the feature is called done
  - log: 2026-07-13 concept extension (recorded with user concept)

### Deep space station (wormhole outpost)

- [ ] **Concept** - researchable "Deep Space Station" technology: a station hull constructible at a wormhole endpoint in open space
  - log: 2026-07-13 user directive (concept recorded); unscheduled - perk set below is a proposal awaiting user confirmation
- [ ] **Construction** - built by a fleet at the endpoint via a waypoint task, consuming minerals carried as cargo; one station per endpoint
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Wormhole stabiliser** - researchable technology mounted on the deep space station: while fitted and the station stands, the endpoint stops wandering
  - log: 2026-07-13 proposed perk (as inherent anchor)
  - log: 2026-07-13 user confirmed as mounted technology - "wormhole stabiliser, which stops the wormhole from wandering"
- [ ] **Transit intelligence** - the owner sees and is messaged about every transit through the wormhole, cloaked fleets included (proposed perk)
  - log: 2026-07-13 proposed perk
- [ ] **Far-side scouting** - the station scans a region around the far endpoint as if a scanner stood there (proposed perk)
  - log: 2026-07-13 proposed perk
- [ ] **Deep-space dock** - friendly fleets repair at starbase rates and refuel at the station, extending logistics beyond planets (proposed perk)
  - log: 2026-07-13 proposed perk
- [ ] **Fights like a starbase** - mounts weapons and shields, defends the endpoint, immune to storm hull damage like starbases; must be destroyed to clear the endpoint
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Edge: both endpoints stationed** - two empires may station opposite endpoints of the same wormhole; each sees the other's transits, anchor applies to both
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Packet relay** - a station mounting a mass driver catches mineral packets flung at its wormhole endpoint and re-flings them from the far mouth toward their final target, turning stationed wormholes into freight arteries
  - log: 2026-07-13 user approved the relay concept ("what a grand concept")
- [ ] **Edge: relay catch failure** - a packet arriving at an endpoint whose station lacks an adequate driver impacts the station like a packet strike; classic rules apply end to end (final target still needs its own catcher)
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Perk confirmation + balance** - final perk set and numbers confirmed with the user before implementation; tuned by trial games
  - log: 2026-07-13 user was unsure of perks - confirmation gate recorded

### LLM narrator (news and commentary)

- [ ] **Pluggable LLM backend** - settings accept any provider: local endpoint (OpenAI-compatible, e.g. Ollama), frontier API, or Claude; provider, endpoint, model and key configurable
  - log: 2026-07-13 user directive (concept recorded); unscheduled
- [ ] **Game news** - the narrator turns real game events (battles, colonizations, invasions, discoveries, storms, victories) into a turn-by-turn news feed written in the game's voice
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Battle commentary** - battle reports gain a generated narrative summary alongside the factual report
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Grounded only** - generated text is styled from actual events and numbers passed to the model; the factual report stays authoritative and visible
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Optional and inert** - off by default, zero gameplay effect, game fully playable without it; no external calls unless a provider is explicitly configured
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Determinism unaffected** - narrator output lives outside deterministic game state; seeded digests identical with the feature on or off
  - log: 2026-07-13 concept extension (recorded with user concept)

### Officers (captains and admirals)

- [ ] **Captains** - a captain serves aboard a single ship; the user can name them and move them from ship to ship
  - log: 2026-07-13 user directive (concept recorded); unscheduled
- [ ] **Admirals** - an admiral commands a fleet, assigned to its flagship; nameable and movable like captains
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Badges** - officers collect badges for deeds (battles survived, kills, minefields swept, storms crossed, distance traveled); each badge slightly improves the odds of relevant actions
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Small effect cap** - officer bonuses stay slight - total effect capped and calibrated by trial games so officers flavor battles rather than decide them
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Admiral idle rule** - an admiral has no effect unless the fleet contains more than one capital ship; otherwise he is idle and brings no bonus
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Capital ship definition** - which hulls count as capital ships is defined explicitly (hull-class list in constants) and shown in the encyclopedia
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Officer fate** - officer is lost when their ship dies (proposed: a small seeded survival chance returns them to the pool); survives ship transfers and fleet merges
  - log: 2026-07-13 proposed rule - confirm with user
- [ ] **Backstory** - every officer carries a backstory: user-written if provided, otherwise selected from a built-in catalogue or generated by the LLM narrator when one is configured
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Service record** - experience accumulates as a chronicled record: badges earned, battles fought, ships served, storms crossed - each deed a dated entry with commentary
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Storyline** - backstory plus service record weave into a continuing per-officer storyline; the LLM narrator (see LLM narrator extension) writes the episodes when configured, grounded in actual game events; catalogue templates otherwise
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Roster UI** - officer roster dialog: names, assignments, badges, and the storyline view; assignment controls in the fleet/ship view
  - log: 2026-07-13 concept extension (recorded with user concept)
  - log: 2026-07-13 storyline view added per user directive

### Trade agreements

- [ ] **Concept** - two empires may sign a trade agreement: scheduled mineral deliveries per year on agreed terms; requires at least Neutral relations
  - log: 2026-07-13 user directive (concept recorded); unscheduled - builds on mineral packets and the packet relay
- [ ] **Carriage** - trade deliveries ride the packet infrastructure: mass-driver flings between the parties' worlds, relayed through stationed wormholes where routes allow; freighter runs as the low-tech fallback
  - log: 2026-07-13 user directive - packet relay "can help with the trade agreements"
- [ ] **Terms** - quantities per mineral per year and duration proposed by one side, confirmed by the other; cancelable with notice
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Trade incidents** - a trade packet that impacts an unprepared receiver, or a breached agreement, damages relations and is messaged to both sides
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Piracy risk** - trade packets in transit remain interceptable by third-party fleets like any packet; looted deliveries count as undelivered
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Trade ledger** - deliveries tallied per agreement with a ledger view; each delivery messaged
  - log: 2026-07-13 concept extension (recorded with user concept)

### Boarding, capture and imprisonment

- [ ] **Boarding action** - in battle, a fleet may attempt to board an adjacent enemy ship whose shields are down; requires boarding capability (troops or a boarding component) on the attacker
  - log: 2026-07-13 user directive (concept recorded); unscheduled
- [ ] **Takeover odds** - success odds from crew strength, tech edge, and officer bonuses; a failed attempt costs the boarding party
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Captured ship** - a taken ship joins the captor's fleet; its full design is revealed to the captor (feeds design-learning intel)
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Imprisonment** - officers aboard a captured ship become prisoners of the captor; the roster shows prisoner status and the storyline chronicles the capture
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Release paths** - prisoners return via rescue (recapturing the ship), prisoner exchange between empires, or a small seeded escape chance per turn
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Interrogation** - a captor may extract intel from a prisoner (e.g. reveal a design or a star report of the prisoner's empire); provocative - damages relations when discovered
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Balance + confirmation** - boarding conditions, odds and interrogation yield confirmed with the user before implementation; tuned by trial games
  - log: 2026-07-13 confirmation gate recorded

### Henry's Hope (Mystery Trader quest)

A last-hope quest the Mystery Trader grants only to a race at the brink of extinction - rides on the canonical Mystery Trader (see its section).

- [ ] **Brink test** - an empire qualifies when it is losing and near death: last place in score AND (homeworld lost, or a single world remaining, or total population under a threshold); thresholds in constants
  - log: 2026-07-13 user directive (concept recorded); unscheduled - natural companion to the wave 5 trader
- [ ] **Only sometimes** - each qualifying turn carries a small seeded chance the quest is offered; at most once per empire per game; deterministic under the game seed
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **The hail** - the Mystery Trader appears (off-schedule if need be) and hails ONLY the qualifying empire with a cryptic private message naming a distant dangerous world; no other empire sees the hail, the marker, or the quest
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **The dangerous world** - the cache world is genuinely hazardous: extreme habitability, seeded deep inside a storm or dense nebula, possibly ringed by ancient minefields - the expedition itself can die trying
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **The stash** - a fleet that reaches the world and holds orbit one full turn unearths the cache: a burst of hidden technology (research levels, one or two Mystery Trader components, minerals) - a fighting chance, never a guaranteed win
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Hope fades** - the quest expires after a set number of years if unclaimed; it dies with the empire if extinction comes first
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Quest marker + story** - the holder sees a private map marker and quest messages; completing it earns the expedition's officers a unique badge and a storyline episode (LLM narrator when configured)
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Edge: several empires at the brink** - the offer evaluates independently per qualifying empire; each may receive its own Henry's Hope, unaware of the others
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Balance** - brink thresholds, offer chance, cache contents and expiry tuned by trial games so the hope is real but never a crutch
  - log: 2026-07-13 concept extension (recorded with user concept)

### Jump wear (drive strain)

Every jump may end in unexpected damage, and the propensity grows the longer a fleet runs without rest - only a stop for repairs clears it. Adds drama to long travels; The Hunt rides on it.

- [ ] **Strain accumulation** - every turn of travel adds drive strain scaled by warp (high warp accrues much faster); strain persists until repaired
  - log: 2026-07-13 user directive (concept recorded); unscheduled
- [ ] **Growing propensity** - each travel turn rolls a seeded malfunction chance proportional to accumulated strain: the longer the unbroken run, the likelier the breakdown
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Malfunctions** - a malfunction damages a random ship (engine blowout) and may drop the fleet out of warp on the spot with waypoint preserved and a message; severity scales with strain
  - log: 2026-07-13 user directive (concept recorded)
- [ ] **Only rest repairs** - strain clears only by spending a full turn stationary: fully at a starbase dock, partially in open space; separate from armor repair (RegenerateFleet)
  - log: 2026-07-13 user directive - "only stop for repairs may repair it"
- [ ] **Strain indicator** - fleet panel shows strain percent with a warning tint as it climbs
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Edge: merge** - merging fleets takes the worst strain of the two
  - log: 2026-07-13 concept extension (recorded with user concept)
- [ ] **Dramatic pacing + determinism** - constants tuned by trial games so short hops stay safe and marathon runs get tense; all rolls ride the game seed
  - log: 2026-07-13 user directive - "adds to gameplay dynamics and the dramatism of long travels"

### The Hunt (relentless pursuit)

Battlestar Galactica "33" homage: a relentless hunter re-acquires the fugitive on a fixed cadence; survival means running, and running wears the fleet down (see Jump wear).

- [ ] **Trigger** - a Hunt spawns from a grave provocation; canonical trigger: firing the Exterminatus births a vengeance hunter out of the Wrath of Milena storm
  - log: 2026-07-13 concept recorded from user-approved hypothesis; unscheduled
- [ ] **Rare confluence triggers** - beyond Exterminatus, a Hunt can ignite when chance, circumstances and unique conditions align (seeded, rare): absconding with a Mystery Trader gift another empire coveted, imprisoning an enemy admiral, carrying the Henry's Hope cache home through hostile space, an Enemy empire commissioning a hunter at high tech
  - log: 2026-07-13 user directive - "given chance, circumstances and presence of unique conditions... rare but interesting"
- [ ] **Declared chase** - every Hunt is publicly declared to all empires at ignition: hunter, prey and the stake named in a galaxy-wide broadcast, with messages at every major beat (lock broken, mishap, stand, resolution) - the galaxy watches
  - log: 2026-07-13 user directive - "I want for the chase to be declared"
- [ ] **The stake** - the prize pot grows every turn the chase runs (minerals, research, and a unique relic at its heart): the longer the drama, the greater the legend
  - log: 2026-07-13 concept per user directive - massive prize
- [ ] **The prize** - escaped prey claims the pot plus the Vengeance Drive, a unique flagship engine immune to jump wear and storm warp risk (the engine that never tires); a victorious empire-commissioned hunter claims the pot plus the Trophy of the Hunt (small permanent bonus to every officer of the empire, massive score award); when an unowned vengeance hunter kills its prey the pot scatters as salvage at the kill site for anyone to scramble over
  - log: 2026-07-13 concept per user directive - "think of a concept"; confirm relic details with user
- [ ] **Officer glory** - the winning side's captains and admirals earn unique Hunt badges with permanently elevated bonuses and a storyline chapter written of them
  - log: 2026-07-13 user directive - winners gain bonuses to captains and admirals
- [ ] **The hunter** - unownable AI fleet, combat-superior to its prey at spawn, immune to diplomacy; it only follows
  - log: 2026-07-13 concept recorded
- [ ] **The cadence** - every N turns (seeded) the hunter jumps to the fugitive fleet's position while it holds a lock; sharing the position at year end forces battle
  - log: 2026-07-13 concept recorded
- [ ] **The lock** - sustained by high-warp jump signatures; broken by quiet running (warp 4 or less) or storm/nebula concealment, each quiet turn giving a seeded shake chance scaled by local dust/storm intensity
  - log: 2026-07-13 concept recorded - reuses scan dampening as the hiding mechanic
- [ ] **Exhaustion** - the chase rides Jump wear: running hot accrues strain and malfunctions, resting invites the cadence - the "33" dilemma
  - log: 2026-07-13 concept recorded
- [ ] **Resolution** - the Hunt ends when the lock stays broken K consecutive turns, the hunter dies in battle, or the prey reaches sanctuary (defended starbase or deep space station); surviving officers earn a unique badge and storyline chapter
  - log: 2026-07-13 concept recorded
- [ ] **Determinism + balance** - cadence, lock rolls and hunter strength seeded and calibrated by trial games
  - log: 2026-07-13 concept recorded

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
  - log: 2026-07-13 user reversed for the mystery trader - now canonical scope, see the Mystery Trader section (scheduled wave 5); random events remain excluded
- [ ] **Mineral packets + mass drivers** - wave 5 decides: minimal canonical implementation or clean removal of the `_move_mineral_packets` remnant, documented either way
  - log: 2026-07-13 decision deferred to wave 5
  - log: 2026-07-13 user embraced packet relay + trade agreements extensions - weighs the wave 5 decision strongly toward implementing packets
- [ ] **Multiplayer turn submission** - per-player order files, passwords, turn locking; web port is single-human live API
  - log: 2026-07-13 excluded by scope decision
  - log: 2026-07-13 partial reversal: correspondence (file-based) play is now a user requirement - see the Correspondence Play section; live simultaneous multiplayer remains excluded
- [ ] **Extended diplomacy** - beyond the 3-state relations model
  - log: 2026-07-13 excluded by scope decision
  - log: 2026-07-13 partial reversal: trade agreements recorded as an extension concept (see Trade agreements section); broader diplomacy remains excluded
