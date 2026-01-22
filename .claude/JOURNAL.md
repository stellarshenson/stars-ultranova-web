# Claude Code Journal

This journal tracks substantive work on documents, diagrams, and documentation content.

---

1. **Task - Project initialization**: Full project setup with Claude Code configuration and documentation<br>
   **Result**: Initialized Stars Nova Web project as a Python/FastAPI/uvicorn port of the Stars! 4X strategy game from C# reference in `stars-nova-orig-c#/`. Created `.claude/CLAUDE.md` with workspace import directive, mandatory bans section, technology stack (Python 3.11+, FastAPI, uvicorn, HTML/CSS/JS frontend), and code porting rules requiring exact logic preservation from C# source. Updated `.gitignore` with Python patterns (pycache, venv, eggs, pytest, coverage) plus reference implementation exclusion. Updated `README.md` with setup instructions including venv creation and uvicorn dev server command. Git repository pre-existed.

2. **Task - Phase 1 implementation**: Complete Phase 1 of the Stars Nova Web implementation plan - Core Data Structures and Game Objects<br>
   **Result**: Implemented the complete backend core infrastructure with exact logic preservation from C# source files. This phase establishes the foundational data structures and game objects required for all subsequent phases.

   **Data Structures** (`backend/core/data_structures/`):
   - `resources.py`: Ported from `Common/DataStructures/Resources.cs`. Implements Ironium, Boranium, Germanium, Energy resource container with full operator overloading (+, -, *, /, >=, ==). Mass property excludes energy (energy has no mass). Float multiplication uses ceiling rounding to match C# behavior. ResourceType enum for indexing.
   - `cargo.py`: Ported from `Common/DataStructures/Cargo.cs`. Extends Resources with Colonists field. Includes `scale()` method clamped to [0,1] range and `to_resource()` conversion excluding colonists.
   - `nova_point.py`: Ported from `Common/DataStructures/NovaPoint.cs`. 2D coordinate class with distance calculations. Note: Original C# uses odd Manhattan distance formula `abs(x1-x2) + abs(y1-y2) - min(abs components)` which is preserved exactly. Includes `battle_speed_vector()` for combat movement calculations.
   - `tech_level.py`: Ported from `Common/DataStructures/TechLevel.cs`. Technology level requirements with 6 research fields (Biotechnology, Electronics, Energy, Propulsion, Weapons, Construction). Implements comparison operators with special semantics - a race can have higher tech in some fields but lower in others, so both `A < B` and `B < A` can be true simultaneously.

   **Game Objects** (`backend/core/game_objects/`):
   - `item.py`: Ported from `Common/GameObjects/Item.cs` and `ItemType.cs`. Base class for game items with 64-bit key structure: bits 25-32 contain owner/empire ID, bits 33-64 contain item ID. Includes key manipulation functions matching `KeyExtensions.cs`. ItemType enum with 26 types (Defense, Hull, Engine, Scanner, Bomb, Fleet, Star, etc.).
   - `mappable.py`: Ported from `Common/GameObjects/Mappable.cs`. Positioned object with x,y coordinates, extends Item.
   - `star.py`: Ported from `Common/GameObjects/Star.cs` (805 lines). Complete planet/star implementation including:
     - Population growth with crowding factor (BASE_CROWDING_FACTOR = 16/9)
     - Five growth cases: negative habitability, low population, crowding threshold, full planet, over capacity
     - Mining rate with concentration reduction over time
     - Resource generation from colonists and factories
     - Factory/mine operation limits based on population
     - Observer pattern for state change notifications
   - `fleet.py`: Ported from `Common/GameObjects/Fleet.cs` (1106 lines). Fleet container with:
     - ShipToken dataclass for ship groups (design, quantity, damage, armor)
     - TravelStatus enum (ARRIVED, IN_TRANSIT)
     - Movement with fuel consumption calculations
     - Waypoint handling and interception point calculation for moving targets
     - Cargo and fuel management

   **Race System** (`backend/core/race/`):
   - `race.py`: Ported from `Common/RaceDefinition/Race.cs`. Race definition with habitability ranges (gravity, temperature, radiation), growth rate, and `hab_value()` calculation for planet suitability.
   - `traits.py`: Ported from `Common/RaceDefinition/AllTraits.cs` and `RaceRestriction.cs`. Defines 10 Primary Racial Traits (HE, SS, WM, CA, IS, SD, PP, IT, AR, JOAT) and 14 Lesser Racial Traits (IFE, TT, ARM, ISB, GR, UR, MA, NRSE, OBRM, CE, NAS, LSP, BET, RS). RaceRestriction class determines component availability based on traits with NOT_AVAILABLE, NOT_REQUIRED, REQUIRED states.

   **Waypoints** (`backend/core/waypoints/`):
   - `waypoint.py`: Ported from `Common/Waypoints/Waypoint.cs` and task classes. Waypoint with position, destination, warp factor. WaypointTask enum and task classes (CargoTask, ColoniseTask, LayMinesTask, etc.) for fleet orders.

   **Production** (`backend/core/production/`):
   - `production_queue.py`: Ported from `Common/DataStructures/ProductionQueue.cs`. ProductionQueue and ProductionOrder classes for planetary production management.

   **Components** (`backend/core/components/`):
   - `component.py`: Ported from `Common/Components/Component.cs`. Component class with mass, cost (Resources), tech requirements (TechLevel), description, image file, race restrictions, and property dictionary. ComponentProperty base class stores typed values (weapons, scanners, engines, etc.).
   - `component_loader.py`: XML parser for `components.xml` (237KB, ~300 components). Parses all component types including property-specific data (weapon power/range/initiative, scanner ranges, bomb damage, engine fuel tables). Provides lookup by name, by type, and availability filtering by race traits and tech level.

   **Global Constants** (`backend/core/globals.py`):
   Ported from `Common/GlobalDefinitions.cs`. Contains all game constants including COLONISTS_PER_KILOTON (100), BASE_CROWDING_FACTOR (16/9), BEAM_RATING_MULTIPLIER table for combat, and other fixed values.

   **API Layer** (`backend/api/`):
   - `routes/games.py`: Game CRUD endpoints (create, list, get, delete, generate turn)
   - `routes/stars.py`: Star query endpoints (list, get by name)
   - `routes/fleets.py`: Fleet operation endpoints (list, get, waypoints)
   - `main.py`: FastAPI application entry point with CORS, static files, and route mounting

   **Frontend Scaffold** (`frontend/`):
   - `index.html`: Main HTML structure with header, game container, info panel, menu overlay, footer
   - `css/main.css`: Dark theme styling for game interface
   - `css/stars-theme.css`: Original Stars! color palette (--stars-bg-dark: #000020, resource colors, habitability indicators, fleet/ship colors)
   - `js/api/client.js`: API client wrapper for all backend endpoints
   - `js/state/game-state.js`: Client-side state management with event emission (gameCreated, gameLoaded, starSelected, fleetSelected, turnGenerated)
   - `js/app.js`: Application initialization and UI event binding

   **Configuration Files**:
   - `requirements.txt`: FastAPI, uvicorn, pydantic, websockets, aiofiles, pytest, pytest-asyncio, httpx
   - `pyproject.toml`: Project metadata and pytest configuration
   - `Makefile`: install, run, test, test-unit, test-integration, clean targets

   **Test Suite** (`tests/unit/`):
   - `test_resources.py`: 14 tests for Resources class
   - `test_cargo.py`: 15 tests for Cargo class
   - `test_nova_point.py`: 16 tests for NovaPoint class
   - `test_star.py`: 18 tests for Star class (growth, mining, resources)
   - `test_component_loader.py`: 21 tests for ComponentLoader, TechLevel, RaceRestriction

   **Verification**: All 90 unit tests pass. Server starts successfully with uvicorn. ComponentLoader correctly parses all components from the C# source's components.xml file.

3. **Task - Phase 2 implementation**: Complete Phase 2 of Stars Nova Web - Components and Ship Designs<br>
   **Result**: Implemented the complete ship design system with component aggregation, following the C# source exactly. This phase enables ship construction and the ship designer interface.

   **Ship Design System** (`backend/core/components/`):
   - `hull_module.py`: Ported from `Common/Components/HullModule.cs` (242 lines). Individual slot definitions for hull module system. Each slot has cell_number, component_type (Engine, Weapon, Scanner, etc.), component_maximum (stacking limit), and allocated_component reference.
   - `hull.py`: Ported from `Common/Components/Hull.cs` (307 lines). Hull component with module slots list. Properties include fuel_capacity (0 for starbases), dock_capacity, base_cargo, armor_strength, battle_initiative, heals_others_percent. Properties `is_starbase` (fuel=0) and `can_refuel` (starbase with dock).
   - `engine.py`: Ported from `Common/Components/Engine.cs` (296 lines). Engine with 10-element fuel consumption table (warp 1-10), ram_scoop flag, fastest_safe_speed, optimal_speed. Calculates `free_warp_speed` (max speed at 0 consumption), `optimum_speed` (balancing efficiency vs time with 10% threshold), and `most_fuel_efficient_speed`.
   - `ship_design.py`: Ported from `Common/Components/ShipDesign.cs` (954 lines). Core ship design class extending Item. Contains blueprint (hull component), aggregated stats (_summary_mass, _summary_cost, _summary_properties). Weapons stored as list (can't simply sum - fire at different initiatives). Separate Bomb tracking (conventional vs smart) and MineLayer tracking (standard/heavy/speed trap with different hit chances). Key properties: mass, cost, shield, armor, fuel_capacity, cargo_capacity, battle_speed. Battle speed formula from manual: `(Ideal_Speed - 4) / 4 - (weight / 70 / 4 / Number_of_Engines) + bonuses`, clamped to [0.5, 2.5] in 0.25 increments. `update()` method recalculates all aggregated stats. `_sum_property()` handles aggregation rules: armor/cargo/shield sum, scanners take max, engines don't stack.

   **ComponentLoader Enhancements**:
   Updated `component_loader.py` to parse specialized property types from XML:
   - `_parse_hull_property()`: Parses Hull properties with FuelCapacity, DockCapacity, ArmorStrength, BattleInitiative, and Module sub-elements (CellNumber, ComponentType, ComponentMaximum).
   - `_parse_engine_property()`: Parses Engine properties with RamScoop, FastestSafeSpeed, OptimalSpeed, and FuelConsumption table (Warp0-Warp9).
   - Added imports for Hull, HullModule, Engine to component package `__init__.py`.

   **API Endpoints** (`backend/api/routes/designs.py`):
   - `GET /api/designs/hulls`: List all hull components with modules
   - `GET /api/designs/hulls/{name}`: Get specific hull by name
   - `GET /api/designs/engines`: List all engine components
   - `GET /api/designs/engines/{name}`: Get specific engine by name
   - `GET /api/designs/components`: List all components, optional type filter
   - `GET /api/designs/components/{name}`: Get specific component
   - `GET /api/designs/stats`: Component count by type

   **Test Suite** (`tests/unit/test_ship_design.py`):
   - TestHullModule: 6 tests (constructor, empty, clone, serialization)
   - TestHull: 10 tests (starbase detection, refuel, modules, clone)
   - TestEngine: 8 tests (fuel consumption, free warp, optimum speed)
   - TestShipDesign: 9 tests (mass, cost, armor, fuel, battle speed)
   - TestComponentLoaderHullEngine: 5 tests (XML parsing verification)

   **Verification**: All 128 unit tests pass. API endpoints functional - tested with TestClient. 228 components loaded from XML (38 hulls, 15 engines). Destroyer hull: 280 fuel, 200 armor, 7 modules. Settler's Delight engine: ram_scoop=True, optimal_speed=6, negative fuel consumption (generates fuel).

4. **Task - Phase 3 implementation**: Complete Phase 3 of Stars Nova Web - Commands and Waypoints<br>
   **Result**: Implemented the command pattern for player actions, enabling turn order submission. Commands encapsulate player orders that modify game state during turn processing.

   **Command System** (`backend/core/commands/`):
   - `base.py`: Ported from `Common/Commands/ICommand.cs`. Abstract Command base class with `is_valid()` and `apply_to_state()` methods. CommandMode enum (ADD, EDIT, DELETE, INSERT). Message class for validation/execution feedback.
   - `waypoint.py`: Ported from `Common/Commands/WaypointCommand.cs` (380 lines). Modifies fleet waypoint lists. Supports all four command modes. Validates fleet ownership. Includes `_is_waypoint_zero_command()` logic for immediate execution of splits and cargo transfers at current location.
   - `design.py`: Ported from `Common/Commands/DesignCommand.cs` (242 lines). Manages ship designs. ADD creates new design, DELETE removes design and updates fleet compositions (removes ships of deleted design), EDIT toggles obsolete flag.
   - `production.py`: Ported from `Common/Commands/ProductionCommand.cs` (254 lines). Modifies planet manufacturing queues. Validates star ownership and queue indices. Cost validation simplified (full validation during processing).
   - `research.py`: Ported from `Common/Commands/ResearchCommand.cs` (124 lines). Sets research budget (0-100%) and topic priorities (TechLevel weighting). Invalidates if nothing changed.

   **Empire Data** (`backend/core/data_structures/empire_data.py`):
   Ported from `Common/DataStructures/EmpireData.cs` (811 lines). Central data structure for player state including:
   - Empire identification and turn tracking
   - Research settings (budget, levels, topics)
   - Owned objects (stars, fleets) and designs dictionaries
   - Intel reports for stars, fleets, empires
   - Key generation with empire ID in high bits (get_next_fleet_key, get_next_design_key)
   - Terraforming capabilities

   **Test Suite** (`tests/unit/test_commands.py`):
   - TestCommandMode: 1 test
   - TestMessage: 2 tests
   - TestWaypointCommand: 6 tests (validation, apply modes, serialization)
   - TestDesignCommand: 7 tests (add, delete, edit obsolete toggle)
   - TestResearchCommand: 5 tests (budget validation, no-change detection)
   - TestEmpireData: 5 tests (key generation, serialization)

   **Verification**: All 155 unit tests pass (27 new for Phase 3). Command pattern enables clean separation between order submission and execution. Commands serialize to/from dict for API transport and persistence.

5. **Task - Phase 4 implementation**: Complete Phase 4 of Stars Nova Web - Turn Processing<br>
   **Result**: Implemented the complete server-side turn processing system with modular turn steps following the C# TurnGenerator.cs structure.

   **Server Infrastructure** (`backend/server/`):
   - `server_data.py`: Ported from `ServerState/Persistence/ServerData.cs` (623 lines). Central game state container with `all_empires`, `all_stars`, `all_minefields`, `all_messages`. Includes `Minefield` dataclass with radius calculation and mine type descriptors. `PlayerSettings` for player configuration. Key methods: `iterate_all_fleets()`, `cleanup_fleets()` (removes empty fleets and handles salvage decay), `set_fleet_orbit()`, `get_star_at_position()`.
   - `turn_generator.py`: Ported from `ServerState/TurnGenerator.cs` (750 lines). Main turn processing orchestrator executing 14-step sequence: parse commands, split/merge fleets, lay mines (FirstStep), scrap fleets, move fleets with fuel consumption, check minefields, cleanup fleets, battle engine (placeholder), victory check, increment year, run turn steps (StarUpdateStep, BombingStep, PostBombingStep, ScanStep), move mineral packets, update minefield visibility.

   **Turn Step Classes** (`backend/server/turn_steps/`):
   - `base.py`: ITurnStep abstract base class with `process(server_state) -> List[Message]` interface.
   - `first_step.py`: Ported from `FirstStep.cs` (108 lines). Mine laying from fleets with LAY_MINES task. Minefield decay (1% per year). Removes fields with <=10 mines. Key structure encodes position grid, owner, mine type.
   - `scrap_fleet_step.py`: Ported from `ScrapFleetStep.cs` (65 lines). Fleet scrapping with resource recovery: 75% at starbase, 33% at planet without starbase, 0% in deep space.
   - `split_fleet_step.py`: Ported from `SplitFleetStep.cs` (118 lines). Removes already-processed SPLIT_MERGE waypoints at position zero. Handles spent cargo tasks. Restores NoTask waypoint if all removed.
   - `bombing_step.py`: Ported from `BombingStep.cs` (33 lines). Orbital bombardment of enemy planets. Calculates kill rate from bomber designs, applies defense coverage reduction.
   - `post_bombing_step.py`: Ported from `PostBombingStep.cs` (118 lines). Colonization and invasion after bombing. Handles colonist transfer, cargo unloading, ownership changes. Invasion mechanics with 1.1:1 attacker advantage.
   - `scan_step.py`: Ported from `ScanStep.cs` (230 lines). Intel generation from scanners. Updates star reports (owned/deep_scan/none levels). Fleet detection within scan range. Penetrating vs non-penetrating scan ranges.
   - `star_update_step.py`: Ported from `StarUpdateStep.cs` (246 lines). Mining (concentration-based mineral extraction with decay). Resource generation (colonists + factories). Research contribution and tech level advancement. Manufacturing queue processing. Population growth with habitability and crowding factors.

   **Waypoint System Enhancement** (`backend/core/waypoints/waypoint.py`):
   Added dual representation system for task types:
   - `WaypointTask` IntEnum for quick comparison (NO_TASK, TRANSFER_CARGO, COLONIZE, LAY_MINES, INVADE, SCRAP, SPLIT_MERGE)
   - Task object classes (*Obj suffix) with `task_type` property returning corresponding enum
   - `get_task_type()` helper function handling both enum values and task objects
   - Backwards compatibility aliases (NoTask = NoTaskObj, etc.)

   **TechLevel Enhancement** (`backend/core/data_structures/tech_level.py`):
   Added `get_level(field: ResearchField)` and `set_level(field: ResearchField, value: int)` methods for cleaner access from turn steps.

   **Test Suite** (`tests/unit/test_turn_generator.py`):
   - TestServerData: 3 tests (initialization, fleet iteration, cleanup)
   - TestFirstStep: 3 tests (decay, removal, mine laying)
   - TestScrapFleetStep: 2 tests (starbase 75%, planet 33%)
   - TestSplitFleetStep: 2 tests (waypoint removal, restoration)
   - TestScanStep: 2 tests (owned stars, fleet detection)
   - TestBombingStep: 1 test (colonist casualties)
   - TestPostBombingStep: 1 test (colonization transfer)
   - TestTurnGenerator: 3 tests (year increment, step execution, multiple empires)
   - TestWaypointTaskHelpers: 5 tests (get_task_type with enums, objects, None)

   **Verification**: All 177 unit tests pass (22 new for Phase 4). Turn generator executes complete sequence. Turn steps process game state modifications correctly. Waypoint task dual system enables both quick enum comparison and rich task objects.

6. **Task - Phase 5 implementation**: Complete Phase 5 of Stars Nova Web - Battle Engines<br>
   **Result**: Implemented the complete combat resolution system with both standard and alternative battle engines ported from C# source.

   **Battle Data Structures** (`backend/server/battle/`):
   - `battle_step.py`: Ported from `ServerState/NewGame/BattleStep.cs`. Event recording classes for battle replay: BattleStep (base), BattleStepMovement (position changes), BattleStepTarget (targeting), BattleStepWeapons (damage dealt), BattleStepDestroy (ship destruction). TokenDefence enum (SHIELDS, ARMOR) for damage targeting. WeaponTarget dataclass linking attacker/defender stacks with weapon details.
   - `battle_report.py`: Ported from `Common/DataStructures/BattleReport.cs`. Container for combat results including all stacks involved, list of battle steps, start/end state snapshots.
   - `battle_plan.py`: Ported from `Common/DataStructures/BattlePlan.cs`. Player-defined targeting priorities. Victims enum with 8 target categories: STARBASE, BOMBER, CAPITAL_SHIP (>700 armor), ESCORT, ARMED_SHIP, ANY_SHIP, SUPPORT_SHIP, NONE. BattlePlan stores dump_cargo flag and ordered list of Victims priorities.
   - `stack.py`: Ported from `Common/GameObjects/Stack.cs` (259 lines). Battle-specific fleet containing single ShipToken. StackToken class bridges ShipToken (cached design values) with mutable battle state (shields, armor remaining). Stack has position, velocity_vector, target, target_list. Key computed as `(owner << 32) | stack_id`. Properties: defenses, is_destroyed, is_armed, mass, battle_speed (from token design).
   - `weapon_details.py`: Ported from `ServerState/BattleEngine/WeaponDetails.cs`. Weapon configuration for combat including power, range, accuracy. TargetPercent dataclass for hit probability tracking per-target.
   - `space_allocator.py`: Ported from `ServerState/BattleEngine/SpaceAllocator.cs`. Battle arena positioning with Rectangle class. Allocates non-overlapping spaces for fleets entering combat.

   **Standard Battle Engine** (`backend/server/battle/battle_engine.py`):
   Ported from `ServerState/BattleEngine/BattleEngine.cs` (1001 lines). Traditional Stars! combat model:
   - 16 maximum battle rounds, 3 movement phases per round
   - Movement table: exact 9x8 array from C# mapping battle speeds (0.5 to 2.5+) to moves per round (1-8)
   - Target attractiveness formula: `cost / defenses` - prioritizes expensive/weak targets
   - Initiative order based on ship design battle_initiative
   - Weapon damage application with shield penetration before armor damage
   - Shield regeneration between rounds
   - Token defense tracking (shields vs armor)
   - `resolve_battle()` main entry point, `_run_round()` for single round execution

   **Ron Battle Engine** (`backend/server/battle/ron_battle_engine.py`):
   Ported from `ServerState/BattleEngine/RonBattleEngine.cs` (1134 lines). Alternative engine with improved movement fidelity:
   - 60 maximum battle rounds for longer engagements
   - 1000-unit grid with 100 scale factor for finer positioning
   - Velocity vectors for smooth movement (not discrete steps)
   - `_battle_speed_vector()` calculates movement direction and magnitude
   - More gradual damage application over extended combat
   - Same target selection and damage formulas as standard engine

   **Module Export** (`backend/server/battle/__init__.py`):
   Exports all battle classes: BattleStep variants, BattleReport, BattlePlan, Victims, Stack, StackToken, WeaponDetails, TargetPercent, SpaceAllocator, BattleEngine, RonBattleEngine.

   **Test Suite** (`tests/unit/test_battle_engine.py`):
   38 tests covering: BattlePlan/Victims (4 tests), Stack/StackToken (8 tests), SpaceAllocator/Rectangle (6 tests), WeaponDetails/TargetPercent (4 tests), BattleStep variants (5 tests), BattleEngine movement table (5 tests), RonBattleEngine (4 tests), Integration (2 tests).

   **Bug Fixes During Implementation**:
   - Fixed `Cargo.colonists` -> `Cargo.colonists_in_kilotons` in Stack creation
   - Fixed `Fleet.in_orbit` -> removed (Fleet has `in_orbit_name` string, Stack has `in_orbit` Star object - resolved by leaving None in Stack.from_fleet)
   - Fixed test using `fleet.key` directly when it should use `fleet.id` (Item.key encodes owner in upper bits)

   **Verification**: All 215 unit tests pass (38 new for Phase 5). Both battle engines functional. Movement table verified against C# source values. Stack creation from Fleet preserves all token properties.
