# Feature Checklist

Verification checklist derived from [ORIGINAL_GAME_MECHANICS.md](ORIGINAL_GAME_MECHANICS.md): every feature/mechanic item mapped to its verifying test and status. Status values: `covered` (implemented and verified by the listed test), `partial` (implemented or tested in part - remainder listed in the mechanics doc), `pending` (implementation and/or test still to come in a later wave). Unit tests count as coverage; e2e scenarios (tests/e2e/) are preferred for gameplay-level mechanics and will replace the "pending" markers wave by wave.

| Feature | Mechanics doc section | Test | Status |
|---|---|---|---|
| Galaxy generation (density, named stars, homeworlds) | 1. Universe and game setup | tests/unit/test_api.py::TestGalaxyGenerator | covered |
| Seeded reproducible games (galaxy + turn generation) | 1. Universe and game setup | tests/e2e/test_harness.py::TestReproducibility | covered |
| Game settings: 8 tunable victory targets, minimum game time | 1. Universe and game setup | - | pending |
| Starting conditions: PRT starting tech, starting fleets per PRT, leftover-point spend, accelerated-BBS start | 1. Universe and game setup | tests/unit/test_research.py::TestStartingTech; tests/unit/test_starting_conditions.py; tests/e2e/test_starting_conditions.py | covered |
| Population growth (rate, hab scaling, crowding, PRT max pop) | 2. Planets and economy | tests/regression/test_parity.py::TestPopulationGrowthParity | covered |
| Resource generation (colonists + factories, operable limits) | 2. Planets and economy | tests/regression/test_parity.py::TestResourceGenerationParity | covered |
| Mining rate and concentration depletion | 2. Planets and economy | tests/regression/test_parity.py::TestMiningRateParity; tests/regression/test_integration.py::test_mining_reduces_concentration | covered |
| Planetary defenses: bombing coverage formula | 2. Planets and economy | tests/unit/test_turn_generator.py::TestBombingStep::test_defense_coverage_formula | covered |
| Planetary defenses: type upgrade path, invasion coverage use | 2. Planets and economy | tests/unit/test_defenses.py::TestDefenseCoverage, TestBestDefenseType, TestTechLevelUpUpgrades; tests/e2e/test_defense_scanner_upgrades.py | covered |
| Planetary scanner types (pen-scan) | 2. Planets and economy | tests/unit/test_defenses.py::TestBestPlanetaryScanner, TestTechLevelUpUpgrades; tests/e2e/test_defense_scanner_upgrades.py | covered |
| Terraforming (production item, hab mod, CA instaforming, Retro Bomb) | 2. Planets and economy | tests/unit/test_terraforming.py; tests/e2e/test_terraforming.py::TestTerraforming::test_colonize_and_terraform | covered |
| Mineral alchemy | 2. Planets and economy | tests/unit/test_alchemy.py; tests/e2e/test_alchemy.py::TestAlchemy | covered |
| Remote mining | 2. Planets and economy | tests/unit/test_remote_mining.py; tests/e2e/test_remote_mining.py::TestRemoteMining; tests/e2e/test_wave2_integration.py | covered |
| Production queue: factory/mine/defense/ship/starbase orders, partial-build carry | 3. Production queue | tests/unit/test_commands.py::TestProductionCommand; tests/regression/test_integration.py::test_resource_accumulation | covered |
| Production queue: alchemy/terraform/auto-build items, reorder | 3. Production queue | terraform: tests/unit/test_terraforming.py::TestTerraformProduction; alchemy: tests/unit/test_alchemy.py, tests/e2e/test_alchemy.py; auto-build/skip caps: tests/unit/test_production_queue.py; reorder: tests/unit/test_commands.py::TestProductionCommand::test_command_move_mode; e2e: tests/e2e/test_production_autobuild.py, tests/e2e/test_wave2_integration.py (alchemy + terraform + auto factory in one queue) | covered |
| OnlyLeftover star research flag | 3. Production queue | tests/unit/test_star.py::test_update_research_only_leftover | covered |
| Research: 6 fields, budget, leftover contribution, next-cost formula | 4. Research | tests/unit/test_commands.py::TestResearchCommand; tests/regression/test_integration.py::test_research_accumulation | covered |
| Research: race cost multipliers, spillover, start-at-level-3 LRT | 4. Research | tests/unit/test_research.py::TestResearchCost, TestSpillover; tests/e2e/test_research.py::TestResearchFidelity | covered |
| Race wizard server-side (full params) | 5. Race design | tests/unit/test_research.py::TestRaceFromWizard; tests/unit/test_starting_conditions.py::TestRaceFromWizardNewFields | partial |
| Advantage-point budget calculator | 5. Race design | tests/unit/test_race_points.py; tests/unit/test_api.py::TestRaceValidation | covered |
| PRT/LRT effects (IFE fuel, CE engine-fail, starting tech) | 5. Race design | tests/unit/test_commands.py (has_trait only); tests/unit/test_research.py::TestStartingTech | partial |
| Component catalog: 228 components load with stats/restrictions | 6. Ship design and components | tests/unit/test_component_loader.py | covered |
| Ship design rules (engine mandatory, slot enforcement, obsolete, delete strips fleets) | 6. Ship design and components | tests/unit/test_ship_design.py; tests/unit/test_commands.py::TestDesignCommand | covered |
| Battle speed, initiative, power rating formulas | 6. Ship design and components | tests/regression/test_parity.py::TestBattleSpeedParity, TestGlobalConstantsParity | covered |
| Component battle effects: jammer/capacitor/deflector/computer | 6. Ship design and components | - | pending |
| Fleet movement: fuel tables, multi-leg, free-warp, ram-scoop (live pipeline) | 7. Fleets and movement | tests/regression/test_integration.py::TestFleetMovementIntegration | partial |
| Fleet ops: split/merge, rename, scrap recovery %, repair/refuel | 7. Fleets and movement | tests/unit/test_turn_generator.py::TestScrapFleetStep, TestSplitFleetStep, TestRegenerateFleet; tests/e2e/test_repair_refuel.py | done |
| Cargo transfer: immediate fleet-star dialog | 7. Fleets and movement | tests/unit/test_cargo.py; tests/unit/test_remote_mining.py::TestCargoAtUninhabitedStar | covered |
| Cargo transfer: waypoint cargo task, fleet-fleet transfer | 7. Fleets and movement | tests/unit/test_turn_generator.py::TestCargoTaskExecution; tests/unit/test_api.py::TestFleetToFleetTransfer; tests/e2e/test_cargo_ops.py | covered |
| Salvage decay 30%/yr | 7. Fleets and movement | - | pending |
| Waypoint tasks: NoTask/Cargo/Colonise/Invade/LayMines/Scrap/SplitMerge | 8. Waypoint tasks | tests/unit/test_turn_generator.py::TestWaypointTaskHelpers, TestPostBombingStep, TestCargoTaskExecution | covered |
| Invasion math verified against InvadeTask.cs | 8. Waypoint tasks | tests/unit/test_defenses.py::TestInvasion | covered |
| Minefields: laying, decay, radius, safe speed, strike formula, damage | 9. Minefields | tests/unit/test_phenomena.py::TestMinefieldStrikes; tests/unit/test_turn_generator.py::TestFirstStep | covered |
| Mine sweeping by beam weapons, detonating fields (SD) | 9. Minefields | - | pending |
| Stargates: safe mass/range, over-limit losses | 10. Stargates and wormholes | tests/unit/test_wormholes_gates.py::TestStargates | covered |
| Wormholes: pairs, drift, scan discovery, transit | 10. Stargates and wormholes | tests/unit/test_wormholes_gates.py::TestWormholes | covered |
| Battle engine: stacks, grid, initiative movement, targeting, damage pools, reports | 11. Combat | tests/unit/test_battle_engine.py | covered |
| Battle plans: editing, target types, tactics honored | 11. Combat | tests/unit/test_battle_engine.py::TestBattlePlan (default plan only) | partial |
| Player relations (Enemy/Neutral/Friend) | 11. Combat | - | pending |
| Bombing (pop kill, min kill, installations, smart bombs, starbase protection) | 12. Bombing and colonization | tests/unit/test_turn_generator.py::TestBombingStep | covered |
| Colonization (ship consumed, colonists landed) | 12. Bombing and colonization | tests/unit/test_turn_generator.py::TestPostBombingStep | covered |
| Scanning: best-scanner stacking, pen-scan, fleet detection, report aging | 13. Intel, scanning, cloaking | tests/unit/test_turn_generator.py::TestScanStep; tests/unit/test_phenomena.py | covered |
| Enemy design hull learning on detection | 13. Intel, scanning, cloaking | - | pending |
| Cloaking effect on detection, tachyon counter | 13. Intel, scanning, cloaking | - | pending |
| Empire intel records (star/fleet reports) | 13. Intel, scanning, cloaking | tests/unit/test_turn_generator.py::TestScanStep | covered |
| Messages: types, audience filter, goto-linkage | 14. Messages, score, victory | tests/unit/test_commands.py::TestMessage | partial |
| Score: formula, history, score report | 14. Messages, score, victory | - | pending |
| Victory: last-standing + 8 configurable targets | 14. Messages, score, victory | - | pending |
| Client parity: dialogs, reports, battle viewer, race designer | 15. Client features | - (browser verification, later wave) | pending |
| Multi-fleet picker, waypoint leg editing | 15. Client features | - | pending |
| AI: planet production, fleet scout/colonize/attack, planner | 16. AI and turn model | tests/unit/test_ai.py | covered |
| Turn submission model (locking per empire, multiplayer story) | 16. AI and turn model | - | pending |
| Mineral packets and mass drivers | 17. Absent in C# (canonical) | - | pending |
| Mystery trader | 17. Absent in C# (canonical) | - | pending |
| Random events (comet strikes etc.) | 17. Absent in C# (canonical) | - | pending |
| Pop transfers between own worlds via waypoints | 17. Absent in C# (canonical) | - | pending |
| Dust nebulae slow ships and dampen scanners | 18. Web-only extensions | tests/unit/test_phenomena.py::TestNebulaDust | covered |
| Galactic storms (drift, damage, ship loss, persistence) | 18. Web-only extensions | tests/unit/test_phenomena.py::TestGalacticStorms | covered |
| Turn processing: year increment, step order, multi-empire isolation | 16. AI and turn model | tests/unit/test_turn_generator.py::TestTurnGenerator; tests/regression/test_integration.py | covered |
| State persistence round-trip (empire/star/fleet serialization) | 16. AI and turn model | tests/regression/test_integration.py::TestStateSerializationIntegration | covered |
| HTTP API surface (games, stars, fleets, empires, commands, health) | 16. AI and turn model | tests/unit/test_api.py | covered |
