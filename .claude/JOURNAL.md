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
