# Stars! UI Feature Analysis

Reference screenshots collected from original Stars! (1995) and Stars! Nova C# clone for UI layout and feature documentation. Purpose is to understand information organization patterns - not to replicate the rustic Windows 3.1 aesthetic.

---

## Screenshot Inventory

### Original Stars! (1995) - `original_1995/`

| File | Contents |
|------|----------|
| `stars_1.png` | Main game screen - wormhole selected, production queue empty |
| `stars_2.png` | Ship & Starbase Designer - Ultra Station starbase |
| `stars_3.png` | Ship Designer - Galleon freighter hull |
| `stars_4.png` | Main game screen - production queue with items |
| `stars_5.png` | Main game screen - scanner range overlay, fleet waypoints |
| `classicreload_cover.png` | Cover art |

### Nova C# Clone - `nova_csharp/`

| File | Contents |
|------|----------|
| `GUI_Main_Screen.png` | Main game screen layout |
| `Race_Designer.png` | Race creation wizard - 5 tabs |
| `Component_Editor.png` | Component editing tool |
| `New_Game_Game_Options.png` | New game setup with map parameters |
| `Nova_Launcher.png` | Game launcher |
| `Nova_Console.png` | Console/debug output |
| `debugAI.png` | AI debug visualization |
| `hm_*.png` | Habitability and mineral concentration charts (6 files) |

---

## Main Game Screen Layout

The original Stars! main screen divides into four quadrants with dense information display.

### Left Column (Selection Details)

**Star/Planet Info Panel** (upper-left):
- Planet image with Prev/Next navigation buttons
- "Minerals On Hand" section with colored bars:
  - Ironium (blue) - quantity in kT
  - Boranium (green) - quantity in kT
  - Germanium (yellow) - quantity in kT
- Mines count: "X of Y" format (operating/total)
- Factories count: "X of Y" format

**Status Section**:
- Population with comma formatting
- Resources/Year output
- Scanner Type and Range
- Defenses count and type
- Defense Coverage percentage

**Starbase Section** (when present):
- Dock Capacity
- Armor and Shields (in dp)
- Damage indicator
- Mass Driver and Destination

### Center Column (Fleets and Production)

**Fleets in Orbit Dropdown**:
- Fleet selector dropdown
- Fuel bar with "X of Ymg" display
- Cargo bar with "X of YkT" display
- Goto and Cargo buttons

**Production Queue**:
- Header: "--- Queue is Empty ---" or item list
- Items show name and quantity
- Completion time: "X - Y years"
- Route controls: Change, Clear, Route buttons

### Right Side (Galaxy Map)

**Scanner Pane**:
- Star field with names
- Colored indicators for ownership
- Yellow highlight for selected objects
- Scanner range circles (red) when enabled
- Fleet waypoint paths as lines
- Wormholes as special purple objects

**Coordinates Display**:
- "X: XXXX Y: YYYY" position
- Distance indicator: "XX.XX light years from [Planet]"

### Bottom (Messages)

**Message Panel**:
- Year indicator with asterisk for pending actions
- Message counter: "Messages: X of Y"
- Message text area (multi-line)
- Navigation: Prev, Goto, Next buttons

---

## Ship & Starbase Designer

Two-panel layout for ship construction.

### Left Panel (Components)

- Category dropdown filter ("All" default)
- Scrollable component list with:
  - Component image thumbnail
  - Component name
- Selected component cost display:
  - Ironium, Boranium, Germanium in kT
  - Resources cost
  - Mass in kT

### Right Panel (Hull/Design)

**Hull Preview**:
- Hull image with navigation arrows
- Hull name header

**Slot Grid**:
- Visual grid of component slots
- Each slot shows:
  - Component image when filled
  - "X of Y" count (current/maximum)
  - Slot type indicator for empty slots
- Special slots labeled (Cargo, General Purpose, Unlimited Space Dock)

**Design Statistics**:
- Full design cost: Ironium, Boranium, Germanium, Resources
- Mass total
- Combat stats: Armor (dp), Shields (dp), Rating
- Special abilities: Cloak/Jam percentages
- Movement: Initiative/Moves
- Scanner Range (normal/penetrating)
- Max Fuel (mg)

---

## Race Designer (Nova)

Tabbed interface with 5 pages:

1. **Race Tab**: Name, plural name, password, race icon, Primary Racial Trait selection (10 radio options)
2. **Traits Tab**: Secondary trait checkboxes
3. **Production Tab**: Factory/mine efficiency settings
4. **Environment Tab**: Habitability ranges (gravity, temperature, radiation)
5. **Research Tab**: Technology cost modifiers

**Key Elements**:
- Advantage Points counter at top (starts at 25)
- Trait Description panel showing selected trait explanation
- Generate button to create race file
- Race icon display with +/- navigation

---

## Component Editor (Nova)

Development tool for editing components.xml.

**Layout**:
- Component Type dropdown filter
- Component List (scrollable)
- Required Tech Levels (6 fields): Energy, Weapons, Propulsion, Construction, Electronics, Biotechnology
- Basic Properties: Mass (kT), Ironium/Boranium/Germanium costs, Resources
- Component Properties: Type-specific values (Armor Value for armor, etc.)
- Description text area
- Component Image selector

---

## New Game Options (Nova)

Three tabs: Game Options, Players, Victory Conditions.

**Game Options Tab**:
- Game Name text field
- Map dimensions: Height, Width (in ly)
- Min separation between stars
- Density percentage
- Uniformity percentage
- Number of stars (disabled in this version)

---

## UI Patterns for Our Implementation

### Information Density

Original Stars! displays extensive data in compact panels. Key patterns:
- Colored resource bars (blue/green/yellow) with numeric labels
- "X of Y" format for capacity indicators (mines, factories, fuel, cargo)
- Comma-formatted large numbers
- dp (damage points) and kT (kilotons) and mg (milligrams) units

### Scanner Visualization Modes

The original supports 12 scanner modes via toolbar. Based on screenshots:
1. Normal view - star names, ownership colors
2. Scanner range - red circles showing detection radius
3. Fleet paths - waypoint route lines
4. Population indicators
5. Mineral concentrations
6. Habitability colors

### Color Coding

| Element | Color |
|---------|-------|
| Ironium | Blue (#4169E1) |
| Boranium | Green (#32CD32) |
| Germanium | Yellow (#FFD700) |
| Player/Friendly | Green indicators |
| Enemy | Red indicators |
| Neutral/Unknown | Gray/white |
| Scanner range | Red circle |
| Waypoints | White/yellow lines |

### Keyboard Shortcuts (from manual)

- Shift+click: Add 10 units
- Ctrl+click: Add 100 units
- Shift+Ctrl+click: Add 1000 units
- Shift+right-drag: Measure distance

---

## Feature Comparison Checklist

### Main Screen Features

| Feature | Original | Nova C# | Our Web |
|---------|----------|---------|---------|
| Galaxy map with stars | Yes | Yes | Yes |
| Star names toggle | Yes | Yes | Yes |
| Scanner range overlay | Yes | ? | No |
| Fleet waypoint lines | Yes | Yes | Yes |
| Planet info panel | Yes | Yes | Yes |
| Mineral bars | Yes | Yes | Yes |
| Production queue | Yes | Yes | Partial |
| Fleet dropdown | Yes | Yes | No |
| Message panel | Yes | Yes | No |
| Year/turn indicator | Yes | Yes | Yes |
| Distance measuring | Yes | ? | No |

### Ship Designer Features

| Feature | Original | Nova C# | Our Web |
|---------|----------|---------|---------|
| Hull selection | Yes | Yes | Yes |
| Slot-based grid | Yes | Yes | Yes |
| Component list | Yes | Yes | Yes |
| Cost breakdown | Yes | Yes | Partial |
| Design stats | Yes | Yes | Partial |
| Save design | Yes | Yes | Yes |

### Race Designer Features

| Feature | Original | Nova C# | Our Web |
|---------|----------|---------|---------|
| Primary traits (10) | Yes | Yes | No |
| Secondary traits | Yes | Yes | No |
| Habitability ranges | Yes | Yes | No |
| Production settings | Yes | Yes | No |
| Research costs | Yes | Yes | No |
| Race icon | Yes | Yes | No |
| Advantage points | Yes | Yes | No |

---

## Priority Features to Add

Based on analysis, high-value missing features for our implementation:

1. **Scanner Range Overlay** - Red circle visualization for detection radius
2. **Message Panel** - Turn messages, research notifications, events
3. **Fleet Selector Dropdown** - Quick fleet switching at location
4. **Distance Measuring** - Shift+drag to measure ly between points
5. **Race Designer** - Full wizard for custom race creation
6. **Production Queue Polish** - Completion times, color coding (blue/black/red)
7. **Quantity Shortcuts** - Shift/Ctrl modifiers for production amounts

---

## Visual Style Notes

Our dark theme is preferred over the Windows 3.1 gray aesthetic. However, preserve:
- Resource color coding (blue/green/yellow for minerals)
- dp/kT/mg unit conventions
- "X of Y" capacity format
- Comma formatting for large numbers
- Panel-based information organization
