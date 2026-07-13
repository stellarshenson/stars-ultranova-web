# Original Game Mechanics Inventory

Complete feature and mechanics inventory of the original Stars! Nova game, compiled from the C# reference (`references/original-game/`). This document is the substrate for the game's acceptance criteria: every item is a candidate criterion for feature parity.

Status legend: **[C# ok]** implemented in reference / **[C# stub]** present but non-functional in reference / **[C# absent]** not in Nova (canonical Stars! only) / **→web: done | partial | missing** = state in the Python port at the time of the scout.

## 1. Universe and game setup

- Galaxy generation: star density/separation/uniformity params, named stars, homeworld selection `StarMapGenerator/StarMapInitialiser` [C# ok] →web: done (own generator, richer)
- Game settings: map size, victory conditions (8 tunable `EnabledValue` targets: planets-owned 60%, tech 22 in N fields, total score, 2nd-place margin, production capacity, capital ships, highest-score-for-N-years; `TargetsToMeet`, `MinimumGameTime` 50) `GameSettings.cs:51-71` [C# ok] →web: **partial** (only 60% stars + last-standing; no settings UI, no multi-target victory)
- Starting conditions: PRT-based starting tech (`GameInitialiser.ProcessPrimaryTraits`), starting fleets per PRT, accelerated-BBS start, leftover advantage points → surface minerals/pop/factories (`HomeStarLeftoverpointsAdjuster`) [C# ok] →web: **partial** (fixed scout+colony+starbase; no PRT tech grants, no leftover-points spend)

## 2. Planets and economy

- Population growth: growth rate, hab-value scaling, crowding factor 16/9, max pop by PRT (HE 0.5×, JOAT 1.2×, OBRM 1.1×) [C# ok] →web: done
- Resources: colonists/factories rate, `GetResourceRate/GetFutureResourceRate`, factories-in-use vs operable [C# ok] →web: done
- Mining: `GetMiningRate(concentration)`, concentration depletion [C# ok] →web: done
- Defenses: type-graded (SDI/Missile/Laser/Planet/Neutron, base coverage 0.0099→0.0379), pop/building/invasion/smart-bomb coverage `Defenses.cs` [C# ok] →web: done (bombing); **missing**: defense *type* research upgrade path, invasion coverage use
- Planetary scanner types (`ScannerType` string, pen-scan TODO in C#) [C# stub-ish] →web: partial (fixed Viewer 50)
- Terraforming: `TerraformProductionUnit` **[C# stub - all NotImplementedException]**; Gravity/Temp/Rad ±N components exist in components.xml; `OriginalGravity/Temperature/Radiation` fields for retro-bomb reversal →web: **missing** (production item + hab mod + CA instaforming + Retro Bomb)
- Mineral alchemy: `AlchemyProductionUnit` [C# ok-ish] →web: **missing**
- Remote mining: Robot Miner hulls/components (7+ components, `Mining Robot` type; miner hulls Midget→Ultra) - no server step found [C# stub] →web: **missing**

## 3. Production queue

- Order types: Factory, Mine, Defense, Ship, Starbase, Alchemy, Terraform, NoOp units; partial-build cost carry (`RemainingCost`); **auto-build flag** with skip logic (`IsAutoBuild`, `IsSkipped`) `ProductionOrder.cs` [C# ok exc. terraform] →web: partial (factory/mine/defense/ship/starbase with partial progress; **missing**: alchemy, terraform, auto-build items, queue reorder UI)
- `OnlyLeftover` star research flag [C# ok] →web: done (flag exists)

## 4. Research

- 6 fields × 26 levels, budget %, allocated + leftover research contribution, tech-level-up messages, next-cost formula, race research-cost multipliers (50/100/175%) [C# ok] →web: partial (**missing**: race cost multipliers, spillover rules, "start at level 3" LRT)

## 5. Race design

- Full wizard params: 3 hab tolerances (min/max/immune), growth 3-20, pop/resource, factory cost/output/operable (+CF germanium discount), mine cost/rate/operable, research costs, PRT (10) + LRTs (14), leftover-point target [C# ok] →web: **missing server-side** (frontend wizard exists, localStorage only)
- Advantage-point budget: start 1650, /3 at end; PRT costs (HE 40… JOAT -66), LRT costs (IFE -235… NAS 325), hab integration with TT correction, growth-rate curve, factory/mine piecewise penalties, science cost table `RaceAdvantagePointCalculator.cs:204-394` [C# ok] →web: **missing**
- PRT effects: only starting-tech implemented in C#; LRT effects: only IFE fuel ×0.85, CE 10% engine-fail, ExtraTech [C# mostly stub] →web: same subset (IFE formula ported, CE ported)

## 6. Ship design and components

- 228-component catalog: hulls (38), engines (15, fuel tables Warp1-10, ram scoops, free-warp), weapons (beams/gatlings/sappers/torpedoes/missiles: power, range, initiative, accuracy), shields, armor, scanners (4th-root stacking), electrical (computers: initiative+accuracy; jammers; capacitors: +beam dmg; deflectors: −beam dmg), mechanical (cargo pods, fuel tanks, maneuvering jets/overthrusters: battle speed, colonization module, orbital-construction), bombs (14), mine layers (10), mining robots, stargates (7), cloaks (7, value stored) [C# ok data; some effects unused] →web: catalog loaded + designer done; **effect gaps**: jammer/capacitor/deflector in battle (deflector partially in C# `BattleEngine.cs:888`), cloak (see §13)
- Design rules: engine mandatory (non-starbase), slot type/capacity enforcement, obsolete flag, design delete strips fleets [C# ok] →web: done
- Battle speed formula, initiative, power rating (beam multiplier table) [C# ok] →web: done

## 7. Fleets and movement

- warp² ly/yr, multi-leg with `availableTime`, fuel = (mass+cargo)×table×warp²/200, IFE ×0.85, warp-1 fuel generation, out-of-fuel drop to free-warp, ram-scoop coasting [C# ok] →web: **partial - live pipeline uses simplified fuel (mass×warp/200/ly) and ignores engine fuel tables; the faithful `Fleet.move()` port exists but is bypassed** - acceptance-critical
- Fleet ops: split/merge (overflow cargo spill), rename command, scrap (waypoint + at-starbase mineral recovery %), refuel at starbase, repair rates (0/1/2/3/5/8/20% by situation `RegenerateFleet`) [C# ok] →web: split/merge/rename/scrap done; repair/refuel partial (flat rules)
- Cargo transfer task (load/unload/set amounts, waypoint-based) + immediate dialog [C# ok] →web: immediate transfer only; **missing**: waypoint cargo task execution
- Salvage from scrapping/battles decaying 30%/yr →web: done (cleanup_fleets)

## 8. Waypoint tasks

- NoTask, CargoTask, ColoniseTask, InvadeTask (1.1 attacker bonus, defense coverage 0.75×pop-coverage), LayMinesTask, ScrapTask, SplitMergeTask [C# ok exc. laying stub] →web: all present; invade ported; **verify invasion defense coverage + troop math against InvadeTask.cs:162**

## 9. Minefields

- Laying rate from components, 1%/yr decay, ≤10 removal, radius=√mines, safe speeds 4/6/5, hit 0.3/1/3.5%/ly/over-warp, per-engine damage + min-fleet damage, fleet stopped; **[C# stub: laying commented out, hit formula 10× buggy, damage hardcoded]** →web: done (canonical constants); mines-visible-to-all in C# vs our scan-gated - decide policy; **missing**: mine sweeping by beam weapons (canonical), detonating fields (SD)

## 10. Stargates and wormholes

- Gates: SafeHullMass/SafeRange per component, non-additive, Orbital slots only [C# data only, travel absent]; wormholes **[C# absent]** →web: both done (canonical-approx over-limit losses; wormhole pairs, drift, scan discovery)

## 11. Combat

- Battle engine: stack building (per-design tokens), 16×16 grid, initiative+battle-speed movement, target selection by attractiveness (power/defense ratio), beam dispersal, gatling multi-hit, sapper shield-only, torpedo accuracy vs computers/jammers, missile double-dmg vs shieldless, capacitors/deflectors, shield+armor pools, distribute damage, destroy steps, battle report steps (Movement/Target/Weapons/Destroy), losses per empire [C# ok] →web: done (Ron engine); **verify**: jammer/capacitor/deflector/computer effects present in port
- Battle plans: per-fleet plan (attack who: Everyone/Enemies/…, primary/secondary target types, tactic, max damage %) + BattlePlans dialog [C# ok] →web: single default plan; **missing**: plan editing UI + target-type/tactic honoring
- Player relations: Enemy/Neutral/Friend per empire, drives battle eligibility + invasion legality `PlayerRelations` dialog [C# ok] →web: **missing** (everyone hostile)

## 12. Bombing and colonization

- Bombing formulas (pop kill %, min kill, installations, smart bombs, starbase protection, depopulate→unowned) [C# ok] →web: done; colonization (ship consumed, cargo down) [C# ok] →web: done

## 13. Intel, scanning, cloaking

- Scan: fleet best-scanner (design-level 4th-root stacking), pen-scan reveals planet, normal detects fleets, report aging, enemy-design hull learning on detection [C# ok] →web: done except design-learning detail
- Cloaking: values stored, **never applied [C# stub]**; canonical: cloak% reduces detection range; tachyon detector counters →web: **missing**
- Empire intel (`EmpireIntel`), star/fleet intel records [C# ok] →web: done (reports)

## 14. Messages, score, victory

- Message types + goto-linkage (fleet_key), turn summary [C# ok] →web: done, goto partial
- Score: planets, starbases (+3), colonists/100k, resources/30, ship classes (unarmed 0.5/escort 2/capital), tech levels, rank; `ScoreRecord` history + Score report [C# ok] →web: **missing** (no scoring at all)
- Victory: last-standing + 8 configurable targets after minimum game time [C# ok] →web: partial (2 conditions)

## 15. Client features (parity targets)

- Star map (scanner overlays, minefield circles, paths), planet/fleet detail+summary panels, production dialog (auto-build items, % edits), research dialog, ship design dialog + Design Manager, battle plans dialog, player relations dialog, cargo transfer dialog (fleet↔fleet too - web is fleet↔planet only), split fleets dialog, rename dialog, reports: planets/fleets/battles/score, battle viewer replay, race designer, launcher/new-game wizard [C# ok] →web: most done; **missing**: fleet↔fleet cargo, battle plans UI, relations UI, score report
- Multi-fleet same-location picker, waypoint edit (insert/modify legs, per-leg warp incl. gate/warp-10) →web: partial (append/delete only)

## 16. AI and turn model

- Planet AI (production), fleet AI (scout/colonize/attack), planner with proclivities (bombers/escorts/interceptors/starbases), AiRunner for headless turns [C# ok] →web: done subset; AI never lays mines/uses gates in either codebase
- Orders/turn-submission model: per-player orders files, turn-submitted flags, password per race [C# ok] →web: N/A (live API model) - decide multiplayer story (turn locking per empire)

## 17. Absent in the C# reference (canonical Stars! - implement from rules if wanted)

- Wormholes (done in web), mineral packets and mass drivers (web has a `_move_mineral_packets` remnant - flesh out or cut), mystery trader (only a TODO comment), random events (comet strikes etc.), tachyon detection, mine sweeping, pop transfers between own worlds via waypoints, diplomacy beyond 3-state relations

## 18. Web-only extensions (regression-test targets)

- Dust nebulae slow ships (≤40%) and dampen scanners (≤50%), emission/filament nebulae visual-only, galactic storms (drift, hull damage, ship loss), proxy-free self-locating client

## Priority gaps

Biggest fidelity deltas surfaced by the scout:

1. Fuel-table movement not wired into live pipeline (§7) - acceptance-critical
2. Player relations + battle plans
3. Score + full victory conditions
4. Race wizard / advantage points server-side
5. Cloaking effect on detection
6. Terraforming + alchemy + auto-build production items
7. Fleet↔fleet cargo transfer
