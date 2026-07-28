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
- [Functional Browser Harness](#functional-browser-harness)
- [LLM Playtest Forensics](#llm-playtest-forensics)
- [Correspondence Play](#correspondence-play)
- [Extensions](#extensions)
- [API](#api)
- [Out of Scope](#out-of-scope)

## Universe and Setup

- [x] **Seeded reproducibility** - same seed + same commands -> identical galaxy and identical state digest after N turns
  - log: 2026-07-13 implemented wave 1 (v0.1.0)
- [ ] **Edge: different seed** - different seed -> different galaxy, no digest collision
  - log: 2026-07-13 covered by tests/e2e/test_harness.py; re-verify wave 6
- [x] **Victory settings** - game creation accepts 8 tunable targets, TargetsToMeet, MinimumGameTime per GameSettings.cs, with New Game settings UI
  - log: 2026-07-13 criterion added, scheduled wave 4
  - log: 2026-07-13 met wave 4 - VictorySettings/EnabledValue model (server_data.py) with GameSettings.cs:49-58 defaults, victory payload on POST /api/games/ -> GameManager.create_game, persisted + restart-safe, New Game dialog Victory Conditions fieldset with C# wizard captions; tests/unit/test_scores.py::TestSerialization, tests/e2e/test_score_victory.py::TestVictoryDeclaration::test_victory_settings_default
- [x] **PRT starting tech** - each PRT gets C#-exact grants (ProcessPrimaryTraits), AI empires included; IFE +1 Propulsion; ExtraTech +3 all fields (+1 JOAT)
  - log: 2026-07-13 implemented wave 1 (v0.1.0)
- [x] **Leftover points spend** - leftover advantage points convert to homeworld bonuses per HomeStarLeftoverpointsAdjuster, all 5 targets
  - log: 2026-07-13 implemented wave 1 (v0.1.0)
- [x] **Accelerated BBS** - flag on game creation applies C# starting population (100000 vs 25000, LSP x0.7)
  - log: 2026-07-13 implemented wave 1 (v0.1.0)
- [ ] **Larger player maps** - universe dimensions per player count are enlarged so empires have room to expand; sizes stated in one place and honored by generator, UI labels and zoom fitting
  - log: 2026-07-28 user directive - "maps for the players must be larger"
- [ ] **Star clustering** - star placement clumps into loose clusters rather than an even scatter; the effect is visible but restrained (no dense knots, no empty deserts), tunable by one documented parameter set, and every empire still meets the DEF-16 fairness bound
  - log: 2026-07-28 user directive - "designed stars clusters where the stars clump more (but not too dense) although effect must not be exaggereated"
  - log: 2026-07-28 approach agreed with the user - seeded Perlin/simplex noise supplies the DENSITY FIELD (organic clumps and voids, no radial lumps, statistically homogeneous so no privileged centre and no structurally poor corner, which also protects the DEF-16 fairness fix); placement uses variable-radius Poisson-disk sampling with the radius driven by that field, so the radius floor makes dense knots impossible and the radius ceiling makes empty deserts impossible; four documented dials - cluster scale (noise frequency), roughness (octaves, persistence), clumping strength (density contrast), separation floor and ceiling; self-contained seeded noise, no new dependency, documented web mod (the C# reference does nothing comparable); testable by three assertions - quadrat-count index of dispersion proves clustering present, nearest-neighbour minimum proves no knots, largest-empty-circle proves no deserts
  - log: 2026-07-28 DEF-16 homeworld fairness landed ahead of this criterion - _select_home_worlds now guarantees every homeworld >= N_min = max(3, ceil(0.5 * median neighborhood count)) neighbor stars within 50 ly AND C#-derived mutual separation min(width,height)/(2*(floor(sqrt(players))+1)) (StarMapGenerator.cs:160-163) with a stepwise relaxation ladder, selecting from the untouched GMM field (documented web deviation from C# homeworlds-first uniform placement; star layouts per seed unchanged); seed 4242 now 10-vs-4 stars within 50 ly (was 9-vs-1 with second-nearest 80 ly); tests/unit/test_galaxy_fairness.py (10 seeds x 2/4 players: floor, separation, determinism, tiny-map termination); any clustering rework must keep this bound
- [ ] **Engine tables solution** - the per-engine fuel tables carry a smart maintainable representation: canonical values sourced once, deliberate web mods marked, no duplicated literals across components.xml and code, with a test proving table lookup equals the canonical source
  - log: 2026-07-28 user directive - "smart solution for engine tables developed"; builds on DEF-7 fix

## Economy and Planets

- [x] **Growth/resources/mining parity** - growth rate, hab scaling, crowding 16/9, PRT max-pop factors, resource rates, concentration depletion match C# parity tests
  - log: 2026-07-13 pre-campaign, regression-tested (v0.1.0)
  - log: 2026-07-28 DEF-9 fixed - negative growth rounding now truncates toward zero per Star.cs:380-383 (Python // floored, producing a flat 100 deaths/year on lightly hostile worlds); tests/unit/test_star.py negative-hab tests, seeded e2e tests/e2e/test_hostile_world_growth.py, test_parity.py expectation updated to the truncation canon
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
  - log: 2026-07-28 DEF-10 fixed - per-resource RemainingCost banking ported (FactoryProductionUnit.cs:108-142, ShipProductionUnit.cs:137-180): proportional partial builds spend the scarce mineral to exactly 0, trailing non-auto orders block per Manufacture.cs:56-61 instead of starving the head, remaining_cost serialized with legacy energy-scalar save migration, ADD anti-tamper extended; tests/unit/test_production_banking.py, seeded e2e tests/e2e/test_production_banking_e2e.py
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
  - log: 2026-07-14 wave-4 verifier - full suite 808 green; cross-feature seeded game tests/e2e/test_wave4_integration.py re-proves the first raider beam hit at exactly power 10 x quantity 2 x 1.21 (2x Energy Capacitor) x 0.9 (Beam Deflector)

## Fleets and Movement

- [x] **Fuel fidelity** - live movement burns (mass+cargo) x engine table x warp^2 / 200, IFE x0.85
  - log: 2026-07-13 pre-campaign (v0.1.0)
  - log: 2026-07-28 CONTRADICTED by run100 playtest empirical measurement (burn linear in warp, approx mass x ly x 0.005 x warp) - see DEF-7 in docs/defects.md and the Per-engine burn tables criterion below
- [x] **Per-engine burn tables (canonical)** - every engine carries the original Stars! per-warp fuel table (Engine.cs port); measured burn at any warp matches the engine's table entry exactly, quadratic-by-warp character restored; deliberate web deviations (if any) documented in code and encyclopedia
  - log: 2026-07-28 user directive from playtest finding - "we need stars! Original burn tables with some our mods"
  - log: 2026-07-28 met - all 15 engines in backend/data/components.xml already carried canonical tables but starting SimpleDesigns had no engine, so live burn fell back to the linear model (DEF-7 root cause); fix: ShipToken caches the engine table, starting designs mount Quick Jump 5 / Settler's Delight (StarMapInitialiser.cs:140-151, Spore Cloud free warp corrected 5 -> 6 from the table), Fleet.fuel_consumption ports ShipDesign.cs:721-744 and TurnGenerator._consume_fuel delegates to it; web mods preserved and documented in code plus a new "Engines and Fuel" encyclopedia entry - negative ramscoop table entries burn 0 (free-warp detection now <= 0), Fuel "Generation" subtraction, warp-1 fuel generation, stargates/packets burn nothing; proven by tests/unit/test_fuel_tables.py and seeded e2e tests/e2e/test_fuel_burn.py (scout burns 3/8/64 mg at w5/w6/w8 per table entries 100/180/800, refuting linear 15/27; out-of-fuel drop to table free warp 1); suite 989 green
- [x] **Edge: out of fuel** - fleet drops to free/battle warp with a Fuel message, waypoint preserved
  - log: 2026-07-13 implemented pre-campaign; re-verify wave 6
  - log: 2026-07-28 CONTRADICTED by run100 forensics (DEF-13, DEF-11): fleets moved the full ordered leg BEFORE fuel deduction (Santa Maria #64 covered 4.0 ly on an empty tank then deadlocked silently at warp 0), the in-transit placeholder waypoint serialized phantom warp 6 and ate warp edits, and the web-only "dropped to warp N" message duplicated the canonical per-turn one
  - log: 2026-07-28 met - _move_fleet now ports the Fleet.cs Move three-way travel-time min (target/available/fuel time, lines 520-546 incl. the >= comparison) so an empty tank moves 0 ly and partial fuel moves exactly what the tank buys; the free-warp drop is silent per Fleet.cs:570-576 with the single canonical per-turn "has run out of fuel." message (TurnGenerator.cs:270-279), plus a web-addition per-turn "stranded in deep space" message at effective warp 0; the placeholder copies waypointZero's warp (TurnGenerator.cs:430-436) and in-transit warp edits write through to the destination waypoint; pre-DEF-7 saves migrate token free_warp/fuel_table from designs on load; proven by tests/unit/test_turn_generator.py (TestMoveFleetFuelCap, TestInTransitWarp, TestFreeWarpSaveMigration), seeded e2e tests/e2e/test_transit_waypoints.py and test_fuel_burn.py::test_fuel_time_caps_travel_distance; suite 1033 green
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
- [x] **Gate hull limit** - only small and medium hulls may gate; large and capital hulls are refused outright (no over-limit gamble for them) - deliberate deviation from canonical, keeps heavy fleets flying conventionally while light forces teleport
  - log: 2026-07-13 user directive - "no stargates for large ships, only small up to medium ones"; scheduled wave 5
  - log: 2026-07-27 landed wave 5 - GATE_HULL_SIZE hull-name table + GATE_ALLOWED_HULL_SIZES in globals.py, hull_name cached on ShipToken via make_token; _gate_travel refuses any large/capital (or unclassified) hull with an Invalid Command message and clamps to warp 9; tests/unit/test_wormholes_gates.py::TestStargateHullLimit, tests/e2e/test_stargate_rework.py (battleship refused where a scout gates)
  - log: 2026-07-27 wave-5 verifier - cross-feature seeded game tests/e2e/test_wave5_integration.py re-proves the pair on class-B gates: a Long Range Scout jumps the full leg in one turn with no fuel spent while a Battleship-hull fleet ordered through the same gate is refused with the too-large message
- [x] **Star-fuelled gate range** - gates are powered by their host star: reach scales with the star's size (the larger the star, the farther the gate throws), always bounded - no unlimited-range gates
  - log: 2026-07-13 user directive - "not too far... fuelled by the presence of the nearby star (the larger the star, the larger the distance)"; scheduled wave 5
  - log: 2026-07-27 landed wave 5 - GATE_SPECTRAL_RANGE_FACTOR (O 2.0, B 1.6, A 1.3, F 1.1, G 1.0, K 0.8, M 0.6) and GATE_MAX_BASE_RANGE 800 ly in globals.py; _star_gate multiplies the model's safe range ("any" -> clamped to 800) by the host star's factor, tighter of the two gates applies; over-range small/medium hulls keep the canonical 25% loss / 50% damage gamble; tests/unit/test_wormholes_gates.py::TestStargateStarFuelledRange, tests/e2e/test_stargate_rework.py (class-B pair throws 960 ly)
- [x] **No minerals through gates** - gates move ships only; loose mineral logistics stay with mass drivers (packets) and freighters
  - log: 2026-07-13 user directive; scheduled wave 5 with the packets decision
  - log: 2026-07-27 landed wave 5 - mineral cargo (ironium/boranium/germanium/silicoxium) refuses the jump for everyone incl. IT; colonists gate only for Interstellar Traveler races (canonical cargo rule) and fuel always travels free, both documented in _gate_travel and the encyclopedia Stargates entry; tests/unit/test_wormholes_gates.py::TestStargateCargoRules, tests/e2e/test_stargate_rework.py (ironium-laden scout refused with message)
- [x] **Wormholes** - pairs drift by stability, discovered by scan, transit via waypoint within 5 ly
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Edge: gate without destination gate** - jump rejected/no-op with message
  - log: 2026-07-13 pre-campaign; re-verify wave 6

## Combat

- [x] **Engine parity** - stacks, 16x16 grid, initiative + battle-speed movement, attractiveness targeting, weapon-class rules, shield/armor pools, report steps
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [ ] **Admiralty standard plans** - six complete plans ship in every empire's plan list (Aggressive Assault, Balanced, Defensive Hold, Commerce Raid, Escort Screen, Fighting Retreat); a fleet is assigned one from the list and a commander may design and name new ones alongside them; there is no separate doctrine object - the standard plans are the doctrine
  - log: 2026-07-28 user directive - "Fleet will be assigned a battle plan from the list of plans designed by admiralty, the standard plans will be there but commander can design new ones"; governing principle recorded by the user - "It is all about cognitive load - some commanders focus on grand strategy not petty battles"
- [ ] **Empire default plan** - an empire-wide default plan is inherited by every newly built fleet, so a commander who never opens the battle screen still fights coherently; today every fleet silently gets the plan named Default from a dataclass default and production never sets it
  - log: 2026-07-28 criterion added (the one-dial requirement)
- [ ] **Beam range dissipation (canon prerequisite)** - beams lose damage with range per canonical Stars!, which is the entire reason a fleet closes; without it standing off is strictly better and every positional tactic is dead
  - log: 2026-07-28 DEF-24 - found by the battle-doctrine research; the dispersal helpers already exist in weapon_details.py with zero callers. This MUST land before the stance layer or the stance is degenerate on day one
- [ ] **Stance** - aggressive, balanced and defensive trade accuracy and initiative against effective shields and armour, so aggressive wins short fights and loses attrition wars; the encyclopedia states the real modifiers
  - log: 2026-07-28 user directive - "fleet can be aggressivve, mix or defensive; it will impact its abilities to tske and give damage"; model chosen by the user over flat damage multipliers, which collapse to one dominant ratio
  - log: 2026-07-28 research refinement (docs/research-battle-doctrine.md) - canonical Stars! tactics carry NO stat modifiers at all; they are pure movement AI, and aggression is expressed as distance closed with beam dissipation paying the cost. Recommended shape therefore keeps the canonical tactic list as the POSITIONAL layer and adds exactly ONE new axis on top, whose sharpest cost is that Aggressive forfeits disengagement entirely. Symmetric damage-dealt versus damage-taken multipliers were rejected with a reason: in a fight to annihilation they only change the round count, and the stronger fleet always wants the shorter fight - what actually creates the trade-off is the hard round limit (surviving the clock is a win for the weaker side) and a positional commitment a differently-armed enemy punishes
- [ ] **Postures** - a fleet may brace (hold position, maximum survivability, no closing) or scatter (spread to blunt area effects and improve escape odds)
  - log: 2026-07-28 user directive - "fleet can brace for battle (essentially hunker down and take defensive strategy or scatter etc)"
- [ ] **Withdrawal** - a fleet may attempt to flee with a stated threshold (damage level or outnumbered) rather than only on first damage, and a withdrawal has a post-battle consequence instead of the current battle-local flag that lets the same fleet fight again next turn
  - log: 2026-07-28 user directive - "fleet can also attempt to flee"
- [ ] **Target classes** - orders may name real classes to hunt: capital ships, escorts, support ships, logistics; roles are inferred from the player's own design (capability booleans, weapon groups and the existing power-rating threshold) rather than a fixed hull list, because players design their own ships
  - log: 2026-07-28 user directive - "attack capital ships, attack small attack ships (frigates?), attack support ships (repair ships, supplies), attack logistic lines (fuel tankers)"; today SUPPORT_SHIP means nothing more than unarmed, so freighters, colonisers, scouts and tankers are indistinguishable
- [ ] **Boarding in battle** - a boarding order lets a fleet attempt to capture an enemy ship at great risk; success transfers the ship and reveals its design, failure destroys the boarding party and heavily damages the boarder
  - log: 2026-07-28 user directive - "add boarding ships and boarding battle plans - to take over ships - but st great risk to self"; failure severity chosen by the user; extends the recorded Boarding, capture and imprisonment extension criteria
- [ ] **Universal boarding capability** - EVERY ship carries a base boarding strength derived from what it already is (hull size and crew, so a Dreadnought's crew outmuscles a Scout's), so any warship may attempt a capture without a special fitting
  - log: 2026-07-28 user directive - "Bosrding capability - every ship can have it, but we must have some components that make it better"
- [ ] **Boarding components** - fittable components multiply boarding strength (assault pods, marine barracks, breaching gear); mounting them costs slots and mass, so a boarder trades combat capability for capture capability
  - log: 2026-07-28 user directive - "we must have some components that make it better"
- [ ] **Boarding ship class** - a dedicated hull class specialised for boarding (high crew capacity, boarding-only slots, poor direct firepower) exists alongside the general capability, and the role cascade recognises it as its own battle role so target-class orders can hunt or screen against boarders
  - log: 2026-07-28 user directive - "and we can have special class of boarding ships too"
- [ ] **Engagement override** - when a battle is imminent (hostile forces at or arriving at a fleet's position, shown to the player before the turn is generated), a fleet may be switched from its standing plan to a plan chosen for that engagement only; the override applies to that battle and the fleet reverts to its standing plan afterwards
  - log: 2026-07-28 user directive - "battle plans and change of doctrin will be possible when battle begins (switch from currently assigned to this battle specific)". Constraint stated honestly: combat resolves inside turn generation with no player input during the fight, so "when battle begins" is implemented as the last moment the player still has - the pre-generation window in which an imminent engagement is visible. Orders cannot be injected mid-battle without abandoning simultaneous resolution
- [ ] **Imminent battle warning** - the client surfaces which of the player's fleets are about to fight, so an engagement override is an informed choice rather than a guess
  - log: 2026-07-28 criterion added - prerequisite for the engagement override above
- [ ] **Battle legibility** - the replay explains itself: each target step carries the priority tier and matched role, withdrawal appears as its own step, and each stack's plan name is shown, so a doctrine can be seen working
  - log: 2026-07-28 criterion added - the engine computes a priority tier for every choice and discards it today
- [ ] **Anti-degeneracy** - no stance, posture or standard plan wins every matchup; proven by a seeded test across paired forces
  - log: 2026-07-28 criterion added - this game has already been beaten once by a dominant strategy (DEF-8 escort spam), and that lesson is the reason this test exists
  - log: 2026-07-28 CONTRADICTED by run100 forensics (DEF-14): the active Ron engine counted unarmed flee-targets as battle triggers, so two co-located unarmed hostiles (Sabik) fought a 60-round movement-only no-shot battle every turn for 12 years, where C# SelectTargets skips unarmed wolves entirely
  - log: 2026-07-28 met - only ARMED wolves count in ron_battle_engine._select_targets (BattleEngine.cs:412-415); unarmed stacks keep their flee target lists for movement, but unarmed-vs-unarmed co-location yields no battle, no report, no message (the C# double gate: run() aborts pre-report, _do_battle ends once only unarmed survivors remain); tests/unit/test_battle_engine.py TestUnarmedBattleTrigger + seeded e2e tests/e2e/test_phantom_battles.py (run100 Sabik reproduction: 3 turns zero battles; armed-vs-unarmed still fights)
- [x] **Battle plans** - per-fleet plan (attack-who, primary/secondary target types, tactic, max damage %) edited in dialog, honored by engine
  - log: 2026-07-13 criterion added, scheduled wave 4
  - log: 2026-07-13 implemented wave 4; per-empire named plans (canonical 14-plan cap) with battle_plan CRUD command + POST /fleets/{key}/battle-plan assignment, Battle Plans dialog in the Commands menu (two-pane, working New/Save/Delete - the C# dialog's edit buttons are disabled) and per-fleet plan selector in the fleet panel; Ron engine honors attack-who incl. dialog-only "Enemies and Neutrals" (canonical, BattleEngine.cs never checked it), five target tiers gate engagement and fire allocation (priority target eats the fire first), tactics Disengage (7 flee moves -> leaves the battle), Disengage if Challenged, stand-off variants (canonical-approx; standard engine stays C#-exact per BattleEngine.cs); "max damage %" -> Ron percent-to-fire overkill allocation; tests/unit/test_battle_engine.py TestBattlePlan/TestAreEnemies/TestRonTargetPriority/TestTactics + tests/e2e/test_battle_plans.py (CRUD round-trip, disengaging freighter escapes while escort fights, control freighter destroyed, deterministic digests)
  - log: 2026-07-14 wave-4 verifier - cross-feature seeded game tests/e2e/test_wave4_integration.py re-proves target tiers (Escort tier soaks every raider volley up to the kill) and the Disengage tactic (freighter flees the board alive) inside one relations-triggered battle
- [x] **Player relations** - Enemy/Neutral/Friend per empire drive battle eligibility and invasion legality, relations dialog
  - log: 2026-07-13 criterion added, scheduled wave 4
  - log: 2026-07-13 implemented wave 4; per-opponent relation map initialized all-Enemy at game creation (GameInitialiser.cs:132-143), "relation" command + F7 dialog (correct Neutral display, C# bug not ported); honored by battle targeting (default plan attack="Enemies", BattlePlan.cs:44), invasion cancel (InvadeTask.cs:110-131, colonists kept aboard), bombing gate (Bombing.cs:59-64), minefield strike friend-skip, enemy-only sweeping and friendly-starbase refuel/repair (canonical); tests/unit/test_relations.py (29 tests), tests/e2e/test_relations.py
  - log: 2026-07-14 wave-4 verifier - cross-feature seeded game tests/e2e/test_wave4_integration.py: Neutral contact passes without battle, mid-game flip to Enemy fights the same deep-space encounter
- [x] **Edge: neutral contact** - co-located neutral fleets do not battle
  - log: 2026-07-13 criterion added, scheduled wave 4
  - log: 2026-07-13 met wave 4; seeded e2e parks two armed warships on one deep-space point at mutual Neutral over several turns with zero battles, then both declare Enemy and the same encounter fights (tests/e2e/test_relations.py); engine-level Neutral-not-targeted case for both battle engines in tests/unit/test_battle_engine.py

## Bombing and Colonization

- [x] **Bombing formulas** - coverage 1-(1-base)^n, min kill, installation damage, smart bombs, starbase protection, depopulation -> unowned
  - log: 2026-07-13 pre-campaign (v0.1.0)
- [x] **Colonization** - ship consumed, colonists landed
  - log: 2026-07-13 pre-campaign (v0.1.0)
  - log: 2026-07-28 CONTRADICTED by run100 forensics (DEF-12): a COLONIZE task on a foreign-owned planet silently converted into a full invasion (Kapteyn's Star, 455 defenders killed on stale intel) and colonize on a populated own planet overwrote its population - C# ColoniseTask.cs IsValid aborts on any occupant
  - log: 2026-07-28 met - _perform_colonization now runs the ColoniseTask.cs IsValid guards in C# order (occupied 88-92 for ANY occupant, colonists aboard 94-98, module 100-104) with the canonical "attempted to colonise ... but it is already occupied." texts; aborts keep colonists aboard and the fleet intact, invasion requires an explicit INVADE order; colonizer-token-only consumption kept as the adjudicated better-than-canon deviation (comment cites ColoniseTask.cs:119-127) - full-fleet-consumption remains an open design call; proven by tests/unit/test_turn_generator.py TestPostBombingStep occupied-guard tests and seeded e2e tests/e2e/test_colonize_guard.py; suite 1033 green

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

- [x] **Message goto** - typed messages link to the referenced object (fleet/star/battle)
  - log: 2026-07-13 partial pre-campaign; completion scheduled wave 5
  - log: 2026-07-27 met wave 5 - Message gains star_name (web port of C# Message.Event, Message.cs:38; from_dict default keeps old saves loading), all 13 Star-message sites and the battle announcement populate it (battle carries the report location per BattleEngine.cs:936-943); message panel Goto button enabled per message, selects and centers the referenced star or fleet, battle messages open the battle viewer on the matching report (Messages.cs:229-238 superset per canonical Stars! rule), old number-jump relabeled Jump...; tests/unit/test_commands.py::TestMessage star_name roundtrip, tests/e2e/test_client_parity.py::TestMessageGotoLinkage (star/fleet/battle linkage resolve)
  - log: 2026-07-28 DEF-15 fixed - battle messages now carry the C# per-empire loss summary (ReportBattle, BattleEngine.cs:945-953): "None of your ships were destroyed." / "N of your ships were destroyed." appended from battle.losses; star_name goto linkage unchanged (the zero-schema-change option), the standard engine's dead _report_battle text-building removed and its per-empire duplicate battle append collapsed to one entry per battle; tests/unit/test_turn_generator.py TestBattleLossSummary + e2e tests/e2e/test_phantom_battles.py loss-summary assertions
- [x] **Score** - C# formula (planets, starbases +3, colonists/100k, resources/30, ship classes, tech), ScoreRecord history, score report UI
  - log: 2026-07-13 criterion added, scheduled wave 4
  - log: 2026-07-13 met wave 4 - backend/server/scores.py exact Scores.cs port (int divisions, tech buckets, capital bonus, rank sort; per-ship counting per legacy Common/Scores.cs + canonical Stars!; real power_rating for the C# stub), per-year score_history on empires appended each generated turn, public scores + history in player state, Reports Score tab with the 10 C# columns + history graph; tests/unit/test_scores.py::TestScoreFormula, tests/e2e/test_score_victory.py::TestScoresInPlayerState
  - log: 2026-07-14 wave-4 verifier - cross-feature seeded game tests/e2e/test_wave4_integration.py: one history entry per empire per generated turn through the victory turn, latest entry matching the live public records for both viewers
  - log: 2026-07-28 DEF-8 fixed - unarmed/escort ship POINTS capped at one scoring ship per owned planet (documented web mod in scores.py restoring canonical original-Stars! 'The Score' semantics that both Nova C# Scores.cs variants omitted; capital harmonic already saturates at 8*planets); raw report counts stay uncapped; escort spam no longer outscores expansion - tests/unit/test_scores.py cap/boundary tests, seeded e2e tests/e2e/test_score_victory.py::TestEscortSpamNotDominant (300-probe 4-planet empire strictly below a 40-planet empire)
- [x] **Victory** - last-standing plus 8 configurable targets evaluated after MinimumGameTime, TargetsToMeet honored
  - log: 2026-07-13 criterion added, scheduled wave 4
  - log: 2026-07-13 met wave 4 - backend/server/victory_check.py full VictoryCheck.cs port at the C# call site (before year increment); last-man-standing any year, 7 target checks, C# defects fixed with comments (HighestScore break, ExceedsSecondPlace gate + canonical exceed-by-N% formula); winner messaged to everyone once, victor persisted, game stays playable; victory-conditions status dialog shows per-target progress; tests/unit/test_scores.py::TestVictoryCheck, tests/e2e/test_score_victory.py::TestVictoryDeclaration
  - log: 2026-07-14 wave-4 verifier - cross-feature seeded game tests/e2e/test_wave4_integration.py ends by a configured condition (planets_owned 1%, minimum_game_time 4): gated at turn 4, empire 1 declared at turn 5 with the public announcement; full suite 808 green, live 30-turn autoplay regression PASS (logs/wave4-regression.log)
- [x] **Edge: before minimum time** - no victory declared before MinimumGameTime even if targets met
  - log: 2026-07-13 criterion added, scheduled wave 4
  - log: 2026-07-13 met wave 4 - minimum-time gate ported from VictoryCheck.cs:76-81 (last-man-standing exempt per C#); tests/unit/test_scores.py::TestVictoryCheck::test_minimum_game_time_gates_target_victories, tests/e2e/test_score_victory.py::TestVictoryDeclaration::test_no_victory_before_minimum_time

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
- [x] **Orbit safe harbor** - storms never affect planets, nor fleets and stations in orbit of a planet; only fleets in open space inside the storm suffer effects
  - log: 2026-07-13 user directive; scheduled wave 4
  - log: 2026-07-14 met wave 4 - _process_storms skips any fleet whose position coincides with a star (get_star_at_position), covering hull damage, warp mishap and colonist attrition; starbases stay immune; scan dampening deliberately stays environmental - a scanner inside a storm still scans worse (decision documented in scan_step.py); tests/unit/test_phenomena.py::TestStormProtection::test_orbit_safe_harbor_skips_all_effects, tests/e2e/test_storms.py::TestStormProtectionE2E
- [x] **Storm shields** - researchable storm shield components join the catalog (tech-gated discovery); equipped ships negate/strongly reduce all storm effects (damage, mishap, colonist attrition)
  - log: 2026-07-13 user directive; scheduled wave 4
  - log: 2026-07-14 met wave 4 - web-only 3-tier line in components.xml (catalog 228 -> 231): Storm Deflector 0.40 (Prop 6 + Energy 6), Storm Barrier 0.70 (Prop 12 + Energy 12), Storm Bulwark 1.00 (Prop 18 + Energy 18); mountable in shield slots, best tier aboard wins, aggregated on the design and cached on tokens; tests/unit/test_phenomena.py::TestStormShieldComponents
  - log: 2026-07-14 wave-4 verifier - cross-feature seeded game tests/e2e/test_wave4_integration.py: a real Storm Bulwark design registered through the design command crosses an intensity-1.0 storm at warp 5 with zero damage and no Storm message while an identical bare hull takes the full 20 x local hit; fleet API storm_protection reads 1.0 vs 0.0
- [x] **Standard shields vs storms** - conventional shields grant partial storm protection scaled by shield rating
  - log: 2026-07-13 user directive; scheduled wave 4
  - log: 2026-07-14 met wave 4 - STORM_SHIELD_PROTECTION (0.35) in globals.py for tokens with shields aboard, full factor while undepleted (tokens carry no persistent shield depletion - shields regenerate between battles); tests/unit/test_phenomena.py::TestStormProtection::test_each_source_alone
- [x] **Armor vs storms** - armor grants a smaller but non-zero storm damage reduction
  - log: 2026-07-13 user directive; scheduled wave 4
  - log: 2026-07-14 met wave 4 - STORM_ARMOR_PROTECTION (0.15) in globals.py for tokens with armor components mounted; hull base armor grants nothing (ShipDesign.has_armor_components); tests/unit/test_phenomena.py::TestStormProtection, TestStormShieldComponents::test_armor_components_flagged
- [x] **Edge: protection stacking** - storm shield + standard shield + armor compose without exceeding full immunity; unshielded hull takes full local effect
  - log: 2026-07-13 criterion added; scheduled wave 4
  - log: 2026-07-14 met wave 4 - sources additive (0.35 + 0.15 + 0.25 + storm-shield tier) then clamped at 1.0, per token then fleet-min (a convoy is as protected as its weakest ship); storm shields never sum (best tier wins) and carry no conventional Shield rating, so no component is double-counted; hull damage, mishap chance AND mishap damage, and attrition all scale by (1 - protection) - never negative; unprotected hull takes the full local effect; tests/unit/test_phenomena.py::TestStormProtection::test_stacking_clamps_at_full_immunity, test_fleet_min_weakest_ship, tests/e2e/test_storms.py::TestStormProtectionE2E
- [x] **Total immunity attainable** - full storm immunity is realistically reachable (top-tier storm shields alone, or high-tier combinations) by mid-to-late game tech
  - log: 2026-07-13 user directive; scheduled wave 4
  - log: 2026-07-14 met wave 4 - Storm Bulwark (1.00, Prop 18 + Energy 18) alone grants total immunity: zero damage, zero mishap chance, zero attrition, not even a Storm message; mid-tier combos also reach 1.0 (Barrier 0.70 + shields 0.35; Deflector 0.40 + shields + armor + rad race); tests/unit/test_phenomena.py::TestStormProtection::test_damage_scaling_at_protection_levels, test_mishap_never_fires_at_full_protection, tests/e2e/test_storms.py::TestStormProtectionE2E
- [x] **Radiation-hardened races** - races accustomed to radiation (high radiation tolerance or radiation immunity) get inherent storm resilience on all their ships
  - log: 2026-07-13 user directive; scheduled wave 4
  - log: 2026-07-14 met wave 4 - STORM_RAD_RACE_PROTECTION (0.25) fleet-wide for races with radiation immunity or radiation optimum in the extreme band (>= STORM_RAD_EXTREME_OPTIMUM, 85); derived from existing habitability data via Race.is_radiation_hardened - no new race-wizard fields; tests/unit/test_phenomena.py::TestStormProtection::test_rad_race_qualification, test_rad_race_protection_applies_in_turn
- [ ] **Storm balance calibration** - hazard and protection numbers calibrated via seeded trial games (survival rates with/without protection recorded and reviewed); constants adjusted until the curve feels right
  - log: 2026-07-13 user directive; calibration pass scheduled wave 6
- [x] **Encyclopedia** - Help menu opens Encyclopedia with numbered entries (dust/emission nebulae, storms, wormholes, minefields, stargates) stating actual gameplay numbers
  - log: 2026-07-13 implemented wave 3; frontend/js/views/encyclopedia.js, Help → Encyclopedia in menu-bar.js; entries mirror globals.py / MINE_STATS / gate catalog numbers; met with browser evidence wave 6
  - log: 2026-07-14 storms entry extended wave 4 - Safe harbor bullet (orbit shelter) and a Protection paragraph mirroring the storm-protection constants (storm shield tiers 40/70/100% with tech costs, shields 35%, armor 15%, rad races 25%, additive with 100% cap, fleet-min, scan static never cleared); fleet panel shows "Storm protection: NN%" when > 0 (storm_protection in fleet API payload)
- [x] **Emission nebula glare** - emission nebulae are not inert: their glow washes out sensors for a small scanner-range penalty at high glow density (constant in globals, far milder than dust), no effect on ship speed; encyclopedia entry updated to match
  - log: 2026-07-13 user directive - "must have some small effect, not entirely inert... maybe small sensor hit?"; scheduled wave 5
  - log: 2026-07-27 landed wave 5 - NEBULA_GLARE_SCAN_PENALTY 0.15 in globals.py, scaled by local emission density (new NebulaField emission grid) and composed with dust and storm dampening in scan_step.py; speed untouched; Emission Nebulae encyclopedia entry replaces "No gameplay effect" with the Sensor glare / No drag bullets; tests/unit/test_phenomena.py::TestNebulaGlare, tests/e2e/test_stargate_rework.py (scout provably scans shorter inside the glow)
- [x] **Encyclopedia imagery** - every phenomenon entry carries beautiful, hand-painted-feel artwork (deterministic procedural painting, consistent style across entries, no external assets)
  - log: 2026-07-13 user directive - "beautiful, like-hand-painted imagery" for all phenomena
  - log: 2026-07-13 implemented - EncyclopediaArt in encyclopedia.js: seeded painterly canvas per entry (layered brush strokes, gradient billows, grain, vignette); all 6 entries browser-verified (walkthrough/final/wave3/07-12)
- [x] **Phenomena tooltips** - map hover explains the phenomenon and links to its encyclopedia entry
  - log: 2026-07-13 implemented wave 3; galaxy-map.js hit-testing (storm blob local intensity, wormhole endpoints, minefield circles, dust density from nebula regions) + dark tooltip with Encyclopedia link; met with browser evidence wave 6

## Mystery Trader

Canonical Stars! feature the C# reference never implemented (only a TODO in GameInitialiser.cs:180) - built directly from canonical rules per user directive, like mine sweeping was.

- [x] **Spawning** - from mid-game on, a trader periodically enters at a galaxy edge and crosses the map in a straight line at high warp (canonical 7-13), exiting the far side; multiple traders possible late game
  - log: 2026-07-13 user directive: canonical feature, model directly; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - TurnGenerator._process_traders/_spawn_trader (before the fleet move loop): eligible from year 2140 (STARTING_YEAR + MT_MIN_YEARS 40), 1-in-16 yearly roll (MT_SPAWN_CHANCE) on the seeded per-turn RNG, cap 1 active early -> 3 from year 2200 (MT_LATE_YEARS 100), spawn ON a random edge crossing to the opposite edge, warp randint(7, 13), velocity = unit heading x warp^2, first out-of-bounds step exits; MysteryTrader dataclass + all_traders/trader_counter in server_data.py (keys never reused); tests/unit/test_traders.py (spawn gate, edge/warp/velocity, caps, exit), tests/e2e/test_mystery_trader.py phase 1
- [x] **Universal visibility** - every empire sees the trader and its course from the moment it spawns, regardless of scanners; spawn and departure broadcast to all empires; distinct map marker
  - log: 2026-07-13 user directive; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - get_player_state "traders" list (no fog; key/name/x/y/warp/velocity + viewer-only gift balance), spawn and departure Messages audience=EVERYONE (message_type "Mystery Trader"); map marker: renderTraders in galaxy-map.js - gold diamond, pulsing halo, dashed gold projected-course line, TRADER label at zoom >= 0.4; tests/unit test_universal_visibility, e2e phases 1 and 5
- [x] **Untouchable** - cannot be attacked, invaded, or struck by mines; storms do not harm it; it never initiates hostilities
  - log: 2026-07-13 user directive; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - structural, zero defensive code: the trader is not a Fleet and belongs to no empire, so battle engines, minefield checks, storm damage and scans never iterate it; asserted in tests/unit test_untouchable_by_construction (armed fleet co-located + storm blob + hostile minefield over the trader, full generate(), trader and ledger untouched, no Battle/Storm/Minefield message names it)
- [x] **Intercept and gift** - a fleet at the trader's position may transfer minerals or colonists to it as a gift; the trader always keeps the cargo
  - log: 2026-07-13 user directive; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - GameManager.gift_to_trader (one-way sibling of transfer_cargo_between_fleets: co-location gate 1 ly, minerals kT + colonists //100, no negatives, no fuel, no refund path) + POST /api/games/{id}/fleets/{key}/gift (TraderGift model); per-empire ledger trader.gifts[empire] = {total, fleet_key}; fleet panel Gift button (enabled only with a trader at the fleet position) + gift dialog showing running total vs threshold; tests/unit test_gift_validation_and_ledger, e2e phase 2
- [x] **Rewards** - a gift at or above the threshold earns a reward from the canonical table: a Mystery Trader component (hidden tech), research level boosts, minerals/fuel, or a gifted ship; reward scales with gift size; chosen thresholds and odds documented in code comments and the encyclopedia
  - log: 2026-07-13 user directive; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - thresholds/odds in globals.py (MT_GIFT_THRESHOLD 1000 kT, tiers 2000/4000) and the authoritative table comment at TurnGenerator._grant_trader_reward: tier1 40% component / 30% research +1 in 2 fields / 30% minerals 2x gift + full fuel; tier2 50/25/15 (3x) /10 ship; tier3 55/20 (+2 in 3) /25 ship (Trader Marauder: armor 2000, shields 800, 4x Anti-Matter Torpedo battery, fueled, at the gifting fleet); component band falls through to research when all items owned, dead gifting fleet converts bounty to research; rewards resolve in _process_traders on the seeded per-turn RNG (never at API time); mirrored verbatim in the encyclopedia entry; tests/unit TestTraderRewards (every band + clamp + fallbacks), e2e phase 3
- [x] **Hidden technology** - trader-exclusive components (canonical MT items such as Multi-Function Pod, Anti-Matter Torpedo, Genesis Device) cannot be researched; once granted, the empire can build them and they appear in its component catalog
  - log: 2026-07-13 user directive; matches the C# TODO's "hidden technology" note; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - four catalog items in components.xml (Multi-Function Pod, Anti-Matter Torpedo, Mega Poly Shell, Genesis Device), each with the "Mystery Trader Item" marker property, Tech all zero and empty race restrictions; per-empire grant list EmpireData.mt_components (serialized, exposed in player state); design_builder._mt_granted gates hull and slot components server-side ("requires a Mystery Trader grant"); design-panel.js hides ungranted items client-side; Genesis Device is a buildable trophy only - its planet-reforming effect is DEFERRED (out of this criterion's scope: grant -> buildable -> in catalog); tests/unit TestHiddenTechGating (zero-tech empire passes _tech_ok, grant unlocks build), e2e phase 4 (granted item mounts for the giver, second empire refused)
  - log: 2026-07-27 wave-5 verifier - cross-feature seeded game tests/e2e/test_wave5_integration.py re-proves the grant chain: an injected trader is intercepted, gifted 4000 kT per pass on the seeded per-turn RNG until the component band lands, and the granted MT item mounts on a real Destroyer design through the design command
- [x] **Moving waypoint target** - fleets can set the trader as a waypoint target; intercept course recomputed each turn
  - log: 2026-07-13 criterion added; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - waypoints carry the trader NAME as destination (C# Waypoint.cs is position-only, so this is a web extension); _process_traders retargets every matching waypoint to the trader's post-move position each turn BEFORE the fleet move loop (co-location at the turn boundary); departed traders freeze the waypoint into a "Space at x,y" positional leg; fleet-panel Add Waypoint lists live traders as destinations; tests/unit test_moving_waypoint_retarget, e2e phase 2 co-location
- [x] **Game setting** - "Mystery Trader" toggle at game creation, default on
  - log: 2026-07-13 criterion added; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - GameCreate.mystery_trader (default true) -> create_game -> ServerData.mystery_trader_enabled (persisted; _process_traders no-ops when off); New Game dialog checkbox, default checked, passed through GameState.createGame -> ApiClient.createGame; tests/unit test_disabled_toggle, e2e test_toggle_off_no_trader
- [x] **Encyclopedia + tooltip** - encyclopedia article stating actual thresholds and reward odds; map hover tooltip links to it
  - log: 2026-07-13 criterion added; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - encyclopedia.js entry 'mystery-trader' ("The Mystery Trader") stating the actual numbers: year 2140 gate, 1-in-16 chance, 3 late-game from 2200, warp 7-13, 1000/2000/4000 kT tiers, the full odds table and all four MT items with stats; EncyclopediaArt._mysteryTrader painter (enigmatic lone dark hull, warm running lights, curved golden wake, seeded painterly composition per the established helpers); galaxy-map findPhenomenonAt hit-tests traders FIRST and links entryId 'mystery-trader'; browser walkthrough evidence due at the wave 6 verification gate
- [x] **Determinism** - spawn timing, course, and rewards reproduce bit-for-bit in seeded games
  - log: 2026-07-13 criterion added; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - all trader randomness rides TurnGenerator.rand (seeded per turn from game_seed), dict iteration over sorted keys, rewards resolve only inside the seeded window; e2e test_determinism_bit_for_bit runs the identical scenario (same seed, same surgery, same API calls) in two games and asserts equal per-empire state digests every turn
- [x] **Edge: below-threshold gift** - trader keeps the cargo, no reward, giver messaged
  - log: 2026-07-13 criterion added; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - sub-threshold balances persist on the ledger (an empire may top up across turns), resolution pass sends the giver a polite "courteous nod" message naming the 1000 kT bar, nothing else changes and there is no refund path; tests/unit test_gift_below_threshold_no_reward, tests/unit test_multi_empire_independent_gifts (empire 2 side)
- [x] **Edge: multiple empires intercept** - gifts tracked per empire; simultaneous intercepts resolve independently
  - log: 2026-07-13 criterion added; scheduled wave 5
  - log: 2026-07-27 implemented wave 5 - trader.gifts keyed by empire id, resolution iterates sorted empire ids independently, player state exposes only the viewer's balance; tests/unit test_multi_empire_independent_gifts (two empires gift the same trader the same turn: one rewarded and zeroed, one below threshold persists; neither sees the other's message)

## Client UI

- [ ] **Map layers** - scanner overlays, minefields, storms, wormholes, fleet paths render truthfully from player state
  - log: 2026-07-13 pre-campaign partial; storm blob rendering wave 3
- [x] **Zoom clamp** - zoom-out limited to best-fit / 1.2 (~20% over board) in all zoom paths; zoom-in unchanged
  - log: 2026-07-13 implemented wave 3; galaxy-map.js minAllowedZoom() enforced in wheel, +/- keys, menu zoom (via setZoom), setZoom and game load; zoomToFit unchanged at best fit; met with browser evidence wave 6
- [ ] **Star size scaling** - stars render small by default and grow only modestly as the user zooms in; zooming out shrinks them to a floor size and no further, so a wide view stays readable rather than dissolving; relative size differences between star classes are preserved at every zoom
  - log: 2026-07-28 user directive - "made the stars smaller on the map and only become little bigger when user zooms in; when zooms out - stars get smaller to a threshold size and stay"
- [ ] **Diverse world imagery** - planet graphics vary convincingly across the galaxy: surface palette, banding, cloud cover, ice caps and terminator shading follow the world's real temperature, radiation, gravity and habitability rather than one template, and each world looks the same on every visit (seeded by star)
  - log: 2026-07-28 user directive - "variated the images of worlds so that they look now more diverse and realistic"
  - log: 2026-07-28 baseline REJECTED by the user after review of walkthrough/review/worlds-before.png - "Worlds look too much the same"; "They practically differ now only by rotation and hue". The failure mode to defeat is exactly that: one sphere gradient plus vertical banding on every world, three temperature-interpolated palettes, a magenta ring for radiation, and gas giants rendered as tinted rocky worlds. Acceptance now requires DISTINCT SURFACE STRUCTURE per class, not recolouring - continents against oceans, craters, lava fissures, ice caps, cloud systems, and gas giants as a genuinely different renderer with zonal bands and storms
  - log: 2026-07-28 approach - research first (docs/research-planet-rendering.md: fBm and domain-warped noise, elevation plus latitude colour ramps, sphere projection in Canvas 2D, per-class signatures, terminator and limb scattering, per-world randomized parameters), then implementation reviewed by the user against the baseline sheet; user approval is required before this criterion may be checked
- [ ] **Dialog parity** - production (auto items, % complete), research, designer, battle plans, relations, cargo (fleet-to-fleet), split, rename, race wizard with live points
  - log: 2026-07-13 partial waves 1-2; plans/relations wave 4
  - log: 2026-07-13 relations dialog landed wave 4 (F7, empire list + Enemy/Neutral/Friend radio group, immediate apply per PlayerRelations.cs:104-120, C# Neutral-displays-as-Friend bug not ported); battle plans UI still pending
  - log: 2026-07-13 battle plans dialog landed wave 4 (Commands menu, two-pane list + details with name, five target tiers, tactic, attack; working New/Save/Delete unlike the disabled C# buttons; per-fleet plan selector in fleet panel); criterion stays open pending remaining dialog checks
- [x] **Waypoint editing** - insert/modify legs, per-leg warp incl. warp-10 gate; multi-fleet same-location picker
  - log: 2026-07-13 criterion added, scheduled wave 5
  - log: 2026-07-27 met wave 5 - fleet panel leg editor: clickable leg list (last selected by default per FleetDetail.cs:482-486), per-leg warp slider 0-10 incl. gate warp-10 (Edit command on release), task selector mapping UI names to real task types (C# LoadTask Replace() defect Waypoint.cs:132 not ported), Insert Before via backend INSERT, delete any leg (web waypoint-zero divergence documented), leg distance/time/fuel + route fuel readout red over fuel aboard (FleetDetail.cs:376-439); player state ships full waypoint task dicts + fuel_consumption_by_warp (Fleet.cs:817-839); map left-click cycles stacked objects within 10 px repeat clicks, right-click near-object menu stars-then-fleets (StarMap.cs:859-953); tests/unit/test_api.py::TestClientParityState, tests/e2e/test_client_parity.py::TestWaypointLegEditing (mixed warps/tasks list shaped via Add/Edit/Insert/Delete executes exactly over several turns), TestMultiFleetSharedPosition
  - log: 2026-07-27 wave-5 verifier - cross-feature seeded game tests/e2e/test_wave5_integration.py re-proves the command stream: a Teamster route shaped via Add/Edit/Insert/Delete (warp-only Edit keeps the CargoTask intact) executes exactly - load at home, checkpoint leg, unload on arrival at the target
- [ ] **Reports** - planets, fleets, battles (viewer replay), score
  - log: 2026-07-13 partial pre-campaign; score report wave 4
  - log: 2026-07-13 score report landed wave 4 - Reports Score tab (Race/Rank/Score/Planets/Starbases/Unarmed/Escort/Capital/Tech Levels/Resources per ScoreReport.Designer.cs) + score history graph, Report -> Score History menu wired; battles viewer replay still pending
- [x] **Panel polish** - no text touching panel borders in the left column; consistent margins/padding on sections, labels, values, bars; clean at 1080p and 1440p
  - log: 2026-07-13 user directive; scheduled wave 5
  - log: 2026-07-27 met wave 5 - PANEL POLISH block in main.css scoped to #left-column on a 4/8/12/16px scale: panel inner padding 12/16px restored (classic layout stripped .panel to 0 so text sat flush), sections separated 16px with last-child collapse, fleet panel header separated like the star panel header, bars and mineral rows on the 8px rhythm, ship/waypoint/queue rows 8px inner padding, waypoint leg details 8/12px, habitability badge 4/8px, empire summary 8px gaps; base rules outside the left column untouched (dialogs/reports keep original values); panel JS inline styles are data-driven bar widths only - no stylesheet conflicts, star-panel.js and fleet-panel.js pass node --check; main.css cache-buster -> v=9; tests/e2e/test_panel_polish.py (served stylesheet rules + seeded state, scope guard on base rules); browser evidence wave 6
- [x] **Race icons** - 16 designed SVG emblem icons replace numbered boxes; custom icon upload per player, stored with the race, shown in wizard/race select/empire summary/reports
  - log: 2026-07-13 user directive; scheduled wave 5
  - log: 2026-07-27 met wave 5 - race-icons.js: 16 designed SVG emblems keyed 0-15 (48x48 viewBox, shared dark emblem disc, silver linework with one accent colour per sigil, named, readable 24-64px) replace the numbered boxes in the wizard grid; custom upload per player (file input, PNG/JPG/SVG up to 128 kB) stored as a base64 data URI in the race payload; Race model gained icon/custom_icon fields serialized through game creation and player state (AI template races carry emblem indexes 0-3); icon shown in wizard grid + upload preview, New Game race selector preview, empire summary bar, Reports score table own-empire row; tests/unit/test_race_icons.py (field persistence, wizard mapping), tests/e2e/test_race_icons.py (seeded round-trip through turns); touched JS passes node --check; browser evidence wave 6
- [x] **Edge: invalid icon upload** - non-image or oversized upload rejected with a clear message, selection unchanged
  - log: 2026-07-13 criterion added, scheduled wave 5
  - log: 2026-07-27 met wave 5 - client rejects wrong type or oversized file with a clear alert before storing (file input cleared, icon selection unchanged); server _validate_custom_icon enforces data URI shape, PNG/JPEG/SVG mime, base64 validity and decoded size up to 128 kB, ValueError -> HTTP 422 from POST /api/games/ and POST /api/races/validate with no game created; tests/unit/test_race_icons.py::TestCustomIconValidation + TestIconUploadApi, tests/e2e/test_race_icons.py::test_invalid_uploads_rejected_without_game; browser evidence wave 6
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

## Functional Browser Harness

A separate functional test harness drives the real UI in a real browser, verifying the load-bearing functions of the game and its workflow end to end - distinct from the unit/e2e suite, which uses in-process clients.

- [x] **Playwright harness** - tests/functional/ drives the served frontend in headless Chrome (Playwright) against a dedicated server instance on its own port with an isolated database; opt-in (RUN_FUNCTIONAL=1) so the default suite stays fast
  - log: 2026-07-27 user directive - "start making functional tests - in a separate funcitonal harness with playwright, so that load bearing functions of the game and workflow (complete gamethrough in the fixed seed - are set)"
  - log: 2026-07-27 met - tests/functional/conftest.py boots uvicorn on port 9820 from a temp workdir (backend/frontend symlinked, SQLite db isolated there), system headless Chrome with --no-sandbox at 2560x1440; RUN_FUNCTIONAL gate verified (default suite: 960 passed, 8 skipped); runner scripts/run_functional.sh
- [x] **Load-bearing functions** - functional tests cover through the real UI: new-game creation via the dialogs, race designer save, star selection and production queue edit, fleet waypoint editing, turn generation, message goto, encyclopedia entries rendering their artwork, score report
  - log: 2026-07-27 criterion added
  - log: 2026-07-27 met - tests/functional/ test_new_game, test_race_designer, test_star_panel, test_fleet_waypoints, test_turn_and_messages, test_encyclopedia, test_reports; all via real clicks on the served frontend, two consecutive green runs
- [x] **Fixed-seed gamethrough** - a complete browser gamethrough on a fixed seed advances the game turn by turn through the UI and reproduces recorded golden outcomes deterministically
  - log: 2026-07-27 criterion added
  - log: 2026-07-27 met - tests/functional/test_gamethrough.py: seed 4242, 2 players, small, 30 turns via the Turn menu; golden tests/functional/golden/gamethrough_seed4242.json (year 2130, planets 1, fleets 7, score 38) written on first run and reproduced exactly on the second
  - log: 2026-07-28 golden honestly regenerated 38 -> 34 after the DEF-8 score cap (planets=1 caps the scout fleet's unarmed points; year/planets/fleets unchanged), two consecutive green runs via the RUN_FUNCTIONAL=1 harness launcher on port 9820 (was free)
  - log: 2026-07-28 golden deleted and re-recorded after DEF-16 (homeworld picks move on seed 4242): two consecutive RUN_FUNCTIONAL=1 runs green, digest unchanged (year 2130, planets 1, fleets 7, score 34) - the 30-turn browser gamethrough counts prove insensitive to the homeworld shift
- [x] **Console forensics** - browser console errors during any functional test fail that test and are recorded to logs/functional/
  - log: 2026-07-27 criterion added
  - log: 2026-07-27 met - page fixture collects console messages and pageerror events; console.error/pageerror entries fail the test, every message written to logs/functional/<test-name>-console.log

## LLM Playtest Forensics

A full-length game played by two LLM commanders against the real backend, mined for defects. Runs after all implementation (wave 5 and correspondence play) and before the final verification gate, so the gate verifies the post-fix game.

- [x] **Hundred-turn LLM game** - an end-to-end 100-turn two-empire game plays through the real backend API with claude -p commanding both sides; the run is detached, checkpoints every turn and resumes after interruption
  - log: 2026-07-27 user directive - "play end to end 100 turns game, variate both sides strategy, make the other side inherit context of what happened (claude -p for both sides) and analyse and collect forensics from the game to fix"; scheduled after all implementation per follow-up "after all is implemented that is"
  - log: 2026-07-28 harness landed - scripts/llm_playtest.py + scripts/run_llm_playtest.sh (setsid nohup detached launch, port-9830 dedicated server, persistent db under results/playtest/<name>/db/, per-turn state.json checkpoint, --resume); 3-turn live smoke green; the 100-turn run itself still pending
  - log: 2026-07-28 met - run100 (game d3f51d91, seed 4242, opus commanders both sides) played end to end and ended by legitimate victory at turn 56 of the 100-turn target: empire 1 Iron Fist won the owns-60%-of-planets target with 54 of 89 planets (60.7%) after minimum game time, year 2156; end-to-end complete by victory, full artifact set under results/playtest/run100/ (56 both-sides turn dumps, forensics.jsonl 190 events, bug_reports.jsonl 620 observations, orders/, digests.jsonl, memos)
- [x] **Strategy variation** - the two sides play distinct strategy personas and adapt them across game phases; each turn's chosen strategy is recorded
  - log: 2026-07-27 criterion added
  - log: 2026-07-28 met - empire 1 "Iron Fist" (military pressure) vs empire 2 "Silicon Loom" (economy/tech, defensive); personas prompted with phase adaptation (opening/consolidation/endgame); each turn's "strategy" line recorded in digests.jsonl and the raw orders transcript; smoke run shows distinct openings (war-fleet expansion vs economy-first settlement)
- [x] **Context inheritance** - each side inherits the history of what happened: a persistent strategy memo the commander rewrites every turn plus the recent event record feeds the next turn's decisions
  - log: 2026-07-27 criterion added
  - log: 2026-07-28 met - per-side memo-<n>.md rewritten by the commander every turn (600-word cap) plus the last 5 turns' event digests fed into every prompt; smoke memos show plans carried and refined across turns 1-3
- [x] **Forensics collection** - per-turn full state dumps, server traceback scan, anomaly detectors (negative stockpiles, rejected orders, stuck fleets, turn generation time) and commander-reported oddities are recorded to disk under results/playtest/
  - log: 2026-07-27 criterion added
  - log: 2026-07-28 met - results/playtest/<name>/: turnNNNN.json both-sides dumps, forensics.jsonl (negative_value, absurd_value/NaN, stuck_fleet 3+ turns, order_rejected with payload+response, turn_time, server_traceback scrape, server_restart), bug_reports.jsonl commander observations verbatim, orders/ raw claude -p request+response with latencies; smoke captured 2 rejected orders and 1 commander observation
- [x] **Loop resilience** - a failed order, an unparseable commander reply or a server outage never aborts the game; the event is logged as forensic evidence and the turn proceeds
  - log: 2026-07-27 criterion added
  - log: 2026-07-28 met - rejected orders logged and skipped (smoke: race-restricted component designs rejected, run continued), invalid JSON gets one retry with the error quoted then falls back to no orders, API calls retry with backoff and restart a dead server, a failed side still submits so the year advances, 5 consecutive failed turns stop the run resumably; proven live by the kill-after-turn-2 resume drill (same game id, turn 3 completed after hard kill of harness and server)
- [ ] **Defect docket clear** - docs/defects.md carries ZERO open entries before a next game is played; every defect is either fixed with a test proving it, or closed as not-a-bug with its reason recorded
  - log: 2026-07-28 user directive - "All defects must be closed before next game"
- [x] **Forensics to fixes** - the collected forensics are analysed into a defect list (docs/defects.md) and confirmed defects are fixed with tests before the wave-6 gate
  - log: 2026-07-27 criterion added
  - log: 2026-07-28 analysis half done - run100 forensics adjudicated: DEF-8..DEF-16 registered in docs/defects.md (score escort-spam economics, negative-hab rounding, mineral-starved production, in-transit phantom warp, colonize auto-invasion, zero-fuel movement deadlock, phantom no-shot battles, missing battle loss summaries, homeworld placement fairness) plus a DEF-7 evidence note; full report docs/playtest-forensics-run100.md; fixes with tests still pending
  - log: 2026-07-28 DEF-8, DEF-9, DEF-10 fixed with unit + seeded e2e tests and closed in docs/defects.md; full suite 1013 passed, 8 skipped
  - log: 2026-07-28 DEF-14 (phantom unarmed battles), DEF-15 (battle loss summaries) and DEF-16 (homeworld placement fairness) fixed with unit + seeded e2e tests and closed in docs/defects.md - all nine run100 defects DEF-8..DEF-16 now closed; seeded fallout honestly updated (test_terraforming seed 20260713 -> 20260716, test_packets driver colony >= 26 ly) and the functional golden re-recorded and reproduced; full suite 1082 passed, 8 skipped
  - log: 2026-07-28 met - independent verification pass: all nine run100 defects closed in docs/defects.md with dated fix notes - DEF-8 (escort-spam score cap), DEF-9 (negative-hab truncation), DEF-10 (per-resource production banking), DEF-11 (in-transit placeholder warp), DEF-12 (colonize occupied-planet abort), DEF-13 (fuel-time distance cap + stranded message), DEF-14 (unarmed battle triggers), DEF-15 (battle loss summaries), DEF-16 (homeworld fairness); full suite 1082 passed 8 skipped, new defect e2es 18/18, functional gamethrough 8/8 against the regenerated golden, tests/e2e 85/85, both doc checkers clean

## Correspondence Play

The C# reference's turn-submission model (per-player orders files, turn-submitted flags, race passwords - [C# ok] in the mechanics inventory) adapted to the web port: the game travels between people as files so each may play their turn.

- [x] **Turn package export** - the host exports a per-empire turn package: that empire's fog-of-war player state for the current year, as a portable versioned JSON file
  - log: 2026-07-13 user requirement; awaits campaign slot (wave 5 candidate)
  - log: 2026-07-27 GET /api/games/{id}/empires/{eid}/turn-package returns the versioned envelope (format/version/game_id/empire_id/turn_year) around get_player_state - the IntelWriter.cs analog; tests/e2e/test_correspondence.py::TestTurnPackage
  - log: 2026-07-27 correspondence verifier - re-proved via tests/e2e/test_correspondence.py (9 passed) and full suite 960 passed 8 skipped
- [x] **Orders file round-trip** - the recipient plays their turn against the package and exports an orders file (commands only); the host imports it and the orders apply exactly as if entered live
  - log: 2026-07-13 user requirement
  - log: 2026-07-27 per-empire orders_log records every applied command and fleet op at submission (EmpireData, cleared on year advance); GET .../orders-file exports it (Orders.cs ToXml year-first analog), POST /api/games/{id}/import/orders validates then replays each entry through the identical live code path and locks the turn (OrderReader.cs ReadPlayerTurn); tests/e2e/test_correspondence.py::TestOrdersRoundTrip
  - log: 2026-07-27 correspondence verifier - re-proved via e2e re-run; round-trip digest equality confirmed against the live game
- [x] **Full-game handoff** - alternatively the entire game file travels: the recipient imports it, plays only their own empire, and sends it onward - hot-seat by correspondence
  - log: 2026-07-13 user requirement - "sending a turn / game state file to another person, so they may play their turn"
  - log: 2026-07-27 GET /api/games/{id}/export wraps the full save-state serialization in a versioned envelope; POST /api/games/import creates a new game from it with seed and determinism intact; tests/e2e/test_correspondence.py::TestFullGameHandoff
  - log: 2026-07-27 correspondence verifier - re-proved via e2e re-run; post-handoff digests equal across both copies after a further turn
- [x] **Race password** - each empire may set a password per the C# reference; opening an empire's view or submitting its orders requires it
  - log: 2026-07-13 criterion added (C# parity: password per race)
  - log: 2026-07-27 Race.password stores the MD5 hash (Race.cs:50; PasswordUtility.cs CalculateHash ported exactly, C# BitConverter format); wizard payload "password" hashed server-side; X-Empire-Password header gates state/commands/turn-package/orders-file/submit-orders (401 mirrors CheckPassword.cs); orders import verifies the file's auth hash; the C# gate itself is scaffolding without call sites - the web wires the canonical intent; tests/unit/test_correspondence_files.py, tests/e2e/test_correspondence.py::TestRacePassword
  - log: 2026-07-27 correspondence verifier - re-proved via e2e re-run (401 wrong/missing, 200 correct, no-password empire open)
- [x] **Turn locking** - an empire's orders lock once submitted (turn-submitted flag per C#); the year advances only when every human empire has submitted
  - log: 2026-07-13 criterion added (C# parity: turn-submitted flags)
  - log: 2026-07-27 submit-orders sets turn_submitted/last_turn_submitted (OrderWriter.cs:63-64); all command and fleet-op paths reject once locked; generate_turn enforces the NovaConsole.cs:450 gate (409 with waiting_on) when the game has 2+ human empires (human_players game option); single-human games keep one-button generation; AI empires auto-submit in _run_ai_empires (RunAI parity); tests/e2e/test_correspondence.py::TestTurnLocking
  - log: 2026-07-27 correspondence verifier - re-proved via e2e re-run (two-human 409 gate, locked-command rejection, flag reset, single-human ungated)
- [x] **Fog integrity** - a per-empire package contains only that empire's fog-of-war view; the full game file is meant for the host/carrier and says so on import
  - log: 2026-07-13 criterion added
  - log: 2026-07-27 turn package body is exactly get_player_state (nothing global added - fog by construction); the game file envelope carries a "host/carrier only" note and the import UI displays it; tests/e2e/test_correspondence.py::TestTurnPackage, TestFullGameHandoff
  - log: 2026-07-27 correspondence verifier - re-proved via e2e re-run (package state equals fogged player state, all fleets owner-scoped)
- [x] **Determinism** - a game played by correspondence replays to the same digest as the identical game played live
  - log: 2026-07-13 criterion added
  - log: 2026-07-27 proven end to end: same-seed game exported/imported as the host copy, orders file replayed into it, turn generated - per-empire sha256 state digests equal the live game's; tests/e2e/test_correspondence.py::TestOrdersRoundTrip::test_correspondence_matches_live_digest
  - log: 2026-07-27 correspondence verifier - assertion proven non-vacuous: same seed with vs without orders produces different digests, so the equality is order-sensitive
- [x] **UI** - Game menu: export turn package / export game file / import orders / import game; submission status per empire visible
  - log: 2026-07-13 criterion added
  - log: 2026-07-27 File menu gains Export Turn Package / Export Orders File / Export Game File / Import Orders File / Import Game File (JSON download/upload); Turn menu Submit Orders and Wait for All wired to submit-orders and the per-empire submission status dialog ("No Orders" until first submission); 401 prompts for the race password once per session; cache busters bumped (client.js v8, game-state.js v7, menu-bar.js v8)
  - log: 2026-07-27 correspondence verifier - node --check clean on all 7 changed frontend/js files; live server regression scripts/autoplay.py seed 118 20 turns PASS
- [x] **Edge: stale package** - orders produced against an outdated year are rejected with a clear message, nothing corrupted
  - log: 2026-07-13 criterion added
  - log: 2026-07-27 orders import validates the year before touching state and returns 409 "Orders file is for year X but the game is at year Y - orders rejected, nothing applied" (the web surfaces what OrderReader.cs:96-102 silently skips); digest-before equals digest-after; tests/e2e/test_correspondence.py::TestStaleOrders
  - log: 2026-07-27 correspondence verifier - re-proved via e2e re-run (409 with year in message, digests unchanged)

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
- [x] **Mineral packets + mass drivers** - wave 5 decides: minimal canonical implementation or clean removal of the `_move_mineral_packets` remnant, documented either way
  - log: 2026-07-13 decision deferred to wave 5
  - log: 2026-07-13 user embraced packet relay + trade agreements extensions - weighs the wave 5 decision strongly toward implementing packets
  - log: 2026-07-27 implemented canonical packets - fling command from starbase drivers (MassDriver.cs aggregation semantics), warp^2 flight with overfling decay (10/25/50 pct, min 10 kT), catch/impact formulas (/160 divisor, 1/3 recovery, defense coverage), map rendering, scannable contacts, fleet loading from packets, encyclopedia entry with art; remnant replaced; tests tests/unit/test_packets.py + tests/e2e/test_packets.py
  - log: 2026-07-27 wave-5 verifier - cross-feature seeded game tests/e2e/test_wave5_integration.py re-proves exchange and impact in one game: driver-to-driver packets land every kT at the rated warp while a 30000 kT packet wipes the undefended enemy homeworld; full suite 939 green, all 62 e2e green, live 30-turn autoplay regression PASS (logs/wave5-regression.log)
- [ ] **Multiplayer turn submission** - per-player order files, passwords, turn locking; web port is single-human live API
  - log: 2026-07-13 excluded by scope decision
  - log: 2026-07-13 partial reversal: correspondence (file-based) play is now a user requirement - see the Correspondence Play section; live simultaneous multiplayer remains excluded
- [ ] **Extended diplomacy** - beyond the 3-state relations model
  - log: 2026-07-13 excluded by scope decision
  - log: 2026-07-13 partial reversal: trade agreements recorded as an extension concept (see Trade agreements section); broader diplomacy remains excluded
