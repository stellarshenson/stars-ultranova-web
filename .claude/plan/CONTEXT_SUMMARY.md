# Stars Nova Web - Context Summary

Use this file to restore context after compaction.

---

## Project Overview

**Stars Nova Web** is a direct port of the Stars! Nova 4X strategy game from C# to Python/FastAPI/uvicorn with a web frontend.

**Repository**: `/home/lab/workspace/private/games/stars-nova-web/`

**Reference**: C# source in `stars-nova-orig-c#/` (gitignored)

---

## Implementation Status

### Phase 1: COMPLETE ✅

All core data structures and game objects ported:

**Files Created (48 files, 14,529 lines)**:
- `backend/core/data_structures/` - Resources, Cargo, NovaPoint, TechLevel
- `backend/core/game_objects/` - Item, Mappable, Star (805 lines C#), Fleet (1106 lines C#)
- `backend/core/race/` - Race, traits (10 PRTs + 14 LRTs)
- `backend/core/components/` - Component, ComponentProperty, ComponentLoader
- `backend/core/waypoints/` - Waypoint, task classes
- `backend/core/production/` - ProductionQueue, ProductionOrder
- `backend/core/globals.py` - All game constants
- `backend/api/routes/` - games, stars, fleets endpoints
- `backend/main.py` - FastAPI entry point
- `frontend/` - HTML, CSS (Stars! theme), JS scaffold
- `tests/unit/` - 90 tests, all passing

**Key Formulas Preserved**:
- Population growth with BASE_CROWDING_FACTOR = 16/9
- Mining rate with concentration reduction
- Fleet fuel consumption
- Habitability calculation

**Commit**: `54078ec` - "feat: implement Phase 1 core data structures and game objects"

### Phase 2: IN PROGRESS 🔄

Ship design system - need to port:
- `ShipDesign.cs` (954 lines)
- `Hull.cs` - Hull with module slots
- `Engine.cs` - Fuel consumption tables

---

## Current State

**Runnable but not playable**:
- Server starts: `make run`
- API responds at `http://localhost:8000`
- Frontend loads but no game visualization

**Missing for playability**:
- Universe generation (create stars)
- Galaxy map rendering (canvas)
- Turn processing
- Ship designer
- Database persistence

---

## Key Technical Details

**Item Key Structure** (64-bit):
- Bits 25-32: Owner/Empire ID
- Bits 33-64: Item ID

**Star Growth Cases**:
1. Negative habitability -> death
2. Low population -> 15% growth
3. Crowding threshold -> reduced growth
4. Full planet -> no growth
5. Over capacity -> population death

**Research Fields**: Biotechnology, Electronics, Energy, Propulsion, Weapons, Construction

**Race Traits**:
- PRTs: HE, SS, WM, CA, IS, SD, PP, IT, AR, JOAT
- LRTs: IFE, TT, ARM, ISB, GR, UR, MA, NRSE, OBRM, CE, NAS, LSP, BET, RS

---

## Directory Structure

```
stars-nova-web/
├── .claude/
│   ├── CLAUDE.md          # Project config
│   ├── JOURNAL.md         # Work journal
│   └── plan/
│       ├── CHECKLIST.md   # Phase checklist
│       ├── SCRATCHPAD.md  # Working notes
│       └── CONTEXT_SUMMARY.md  # This file
├── backend/
│   ├── core/              # Game logic
│   ├── api/               # FastAPI routes
│   ├── data/              # components.xml
│   └── main.py            # Entry point
├── frontend/
│   ├── css/               # Styles
│   ├── js/                # Client code
│   └── index.html
├── tests/unit/            # 90 tests
├── stars-nova-orig-c#/    # Reference (gitignored)
├── Makefile
├── requirements.txt
└── pyproject.toml
```

---

## Commands

```bash
make install     # Create venv, install deps
make run         # uvicorn on port 8000
make test        # Run all tests
make test-unit   # Unit tests only
```

---

## Next Steps

1. Read `ShipDesign.cs` from C# source
2. Port Hull.cs with module slot system
3. Port Engine.cs with fuel tables
4. Create ship_design.py aggregating components
5. Add API endpoints for designs
6. Write tests
