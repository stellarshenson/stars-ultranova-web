# Stars Nova Web - Implementation Scratchpad

Working notes, C# references, and implementation details for current phase.

---

## Current Phase: 2 - Components and Designs

### Key C# Files to Port

1. **ShipDesign.cs** (954 lines) - `Common/Components/ShipDesign.cs`
   - Central ship design class
   - Aggregates components into slots
   - Calculates combined stats (mass, armor, shields, weapons)

2. **Hull.cs** - `Common/Components/Hull.cs`
   - Hull component with module slots
   - Slot types and capacities

3. **Engine.cs** - `Common/Components/Engine.cs`
   - Fuel consumption table (11 entries for warp 0-10)
   - Free warp speed
   - Battle speed

4. **Weapon.cs** - Already partially ported
   - Power, range, initiative, accuracy
   - Weapon types (beam, torpedo, missile)

### ShipDesign Structure (from C#)

```csharp
// Key fields from ShipDesign.cs
public Component Hull;
public List<HullModule> Modules;  // Slots with components
public int Armor;      // Aggregated
public int Shield;     // Aggregated
public int CargoCapacity;
public int FuelCapacity;
public int Mass;
public int Cost;       // Resources
public int Initiative;
```

### Hull Module System

Each hull has slots (modules) that can hold components:
- Slot types: General, Engine, Weapon, Scanner, Electrical, Mechanical, Armor, Shield
- Each slot has a capacity (how many components fit)
- Components are stacked in slots

### Engine Fuel Table

From Engine.cs - fuel consumption per 100mg at each warp:
```
Warp:  0    1    2    3    4    5    6    7    8    9   10
Fuel:  0  100  200  300  400  500  600  700  800  900 1000
```
(Actual values vary by engine type)

### Implementation Order

1. Port Hull.cs -> hull.py
2. Port Engine.cs -> engine.py (with fuel table)
3. Port ShipDesign.cs -> ship_design.py
4. Add design API endpoints
5. Write tests

---

## Notes

### Phase 1 Completion Notes
- 90 tests passing
- ComponentLoader successfully parses all ~300 components
- Star growth formula matches C# exactly
- Fleet movement and fuel consumption working

### Architectural Decisions
- Using dataclasses for Python models
- Properties stored as Dict[str, Any] in ComponentProperty for flexibility
- Event emission pattern for state changes (observer pattern)

---

## Quick Reference

### File Locations
- C# Source: `stars-nova-orig-c#/`
- Python Backend: `backend/`
- Tests: `tests/unit/`
- Components XML: `backend/data/components.xml`

### Commands
```bash
make install    # Set up venv
make run        # Start dev server
make test       # Run all tests
make test-unit  # Run unit tests only
```

### Git
- Main branch: `main`
- Last commit: `54078ec` - Phase 1 complete
