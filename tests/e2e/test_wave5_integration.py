"""
Wave-5 cross-feature integration: one seeded game combining the four
wave-5 gap families end to end.

A two-player small game (JOAT, mystery trader enabled) plays four
phases in sequence on the same seeded state:

- waypoint leg editing (client parity): the starting Teamster's route
  is shaped through the per-index Add/Edit/Insert/Delete waypoint
  command stream the fleet panel submits (WaypointCommand.cs:148-160),
  a warp-only Edit round-trips the CargoTask intact
  (FleetDetail.cs:110), and the final [LOAD at home, checkpoint,
  UNLOAD at target] list executes exactly over the following turns;
- stargate rework (user directive 2026-07-13): the homeworld starbase
  and a second colony both carry gates on class-B stars (range factor
  1.6), a starting Long Range Scout jumps the full leg in one turn
  with no fuel spent, while a Battleship-hull fleet ordered through
  the same gate is refused outright with the too-large message;
- mystery trader (canonical Stars! rules - the C# reference has only
  a TODO, GameInitialiser.cs:180): an injected trader with a known
  course is intercepted by a freighter, gifted 4000 kT per pass until
  the hidden-tech band lands on the seeded per-turn RNG, and the
  granted MT component then mounts on a real Destroyer design;
- mineral packets (canonical Stars! rules - MassDriver.cs defines only
  the component property): two driver stars exchange packets safely
  at the rated warp (exact surface deltas, no impact message) while
  the undefended enemy homeworld takes a canonical packet impact that
  wipes the colony.

Fleets, gates, drivers and the trader are placed by state surgery
(the established harness pattern, see test_stargate_rework.py,
test_mystery_trader.py and test_packets.py); tech is granted by
surgery so the MT design validates. Every roll rides the per-turn
seeded RNG, so the recorded outcome is reproducible for the fixed
seed.
"""

import math

SEED = 20260714
LOAD_KT = 20
REWARD_ATTEMPTS = 12  # component odds 55% per 4000 kT gift

RACE = {
    "name": "Wavefront",
    "pluralName": "Wavefronts",
    "prt": "JOAT",
}

# Destroyer hull slot per MT item type (cell 2 Weapon, 6 Mechanical,
# 12 General Purpose, 16 Electrical)
MT_ITEM_SLOT = {
    "Anti-Matter Torpedo": 2,
    "Genesis Device": 6,
    "Mega Poly Shell": 12,
    "Multi-Function Pod": 16,
}


def _manager():
    from backend.services.game_manager import get_game_manager
    return get_game_manager()


def _load(harness):
    return _manager()._load_game_state(harness.game_id)


def _save(harness, server_data):
    _manager()._save_game_state(harness.game_id, server_data)


def _clear_phenomena(harness):
    """Exact travel and scanning: no dust drag, no storms."""
    from backend.server.server_data import NebulaField
    server_data = _load(harness)
    server_data.all_storms = {}
    server_data.nebula_field = NebulaField(regions=[])
    _save(harness, server_data)


def _dist(a, b):
    return math.hypot(a.position.x - b.position.x,
                      a.position.y - b.position.y)


def _fleet_named(harness, prefix, empire_id=1):
    for fleet in harness.my_fleets(empire_id):
        if fleet["name"].startswith(prefix):
            return fleet
    return None


def _fleet_by_key(harness, key, empire_id=1):
    for fleet in harness.my_fleets(empire_id):
        if fleet["key"] == key:
            return fleet
    return None


def _add_waypoint(harness, fleet_key, index, x, y, warp, dest, task,
                  mode="Add"):
    harness.submit(1, "waypoint", {
        "mode": mode,
        "fleet_key": fleet_key,
        "index": index,
        "waypoint": {
            "position_x": x,
            "position_y": y,
            "warp_factor": warp,
            "destination": dest,
            "task": task,
        },
    })


def _home_star(server_data, empire_id):
    return next(s for s in server_data.all_empires[empire_id]
                .owned_stars.values())


# -- stargate surgery (pattern: test_stargate_rework.py) --------------

def _add_gate(fleet, gate_mass=300, gate_range=600):
    for token in fleet.tokens.values():
        token.has_gate = True
        token.gate_mass = gate_mass
        token.gate_range = gate_range


def _gate_pair(harness):
    """Gate the homeworld starbase and a second star 85-300 ly away,
    both on class-B stars. Returns (origin_name, dest_name)."""
    from backend.core.data_structures import NovaPoint
    from backend.core.game_objects.fleet import Fleet, ShipToken

    server_data = _load(harness)
    empire = server_data.all_empires[1]
    home = _home_star(server_data, 1)
    home.spectral_class = "B"

    base = next(f for f in empire.owned_fleets.values() if f.is_starbase)
    _add_gate(base)

    dest = min(
        (s for s in server_data.all_stars.values()
         if s.owner == 0 and 85 < _dist(s, home) < 300),
        key=lambda s: _dist(s, home))
    dest.owner = 1
    dest.colonists = 10000
    dest.spectral_class = "B"
    empire.owned_stars[dest.name] = dest

    far_base = Fleet(name=f"{dest.name} Base", position=NovaPoint(
        dest.position.x, dest.position.y))
    far_base.key = (1 << 32) | 900
    far_base.owner = 1
    far_base.in_orbit_name = dest.name
    far_base.in_orbit = dest
    token = ShipToken(design_key=990, design_name="Gate Base",
                      quantity=1, mass=0, armor=500, is_starbase=True)
    far_base.tokens[990] = token
    _add_gate(far_base)
    empire.owned_fleets[far_base.key] = far_base

    _save(harness, server_data)
    return home.name, dest.name


def _park_fleet(harness, fleet_key, star_name):
    from backend.core.data_structures import NovaPoint

    server_data = _load(harness)
    fleet = server_data.all_empires[1].owned_fleets[fleet_key]
    star = server_data.all_stars[star_name]
    fleet.position = NovaPoint(star.position.x, star.position.y)
    fleet.waypoints = []
    fleet.in_orbit_name = star_name
    fleet.in_orbit = star
    fleet.fuel_available = 5000
    _save(harness, server_data)


def _make_battleship(harness, star_name):
    """Battleship-hull fleet parked at a star, by state surgery."""
    from backend.core.data_structures import NovaPoint
    from backend.core.game_objects.fleet import Fleet, ShipToken

    server_data = _load(harness)
    empire = server_data.all_empires[1]
    star = server_data.all_stars[star_name]
    fleet = Fleet(name="Heavy Squadron #901", position=NovaPoint(
        star.position.x, star.position.y))
    fleet.key = (1 << 32) | 901
    fleet.owner = 1
    fleet.in_orbit_name = star_name
    fleet.in_orbit = star
    fleet.fuel_available = 5000
    fleet.tokens[991] = ShipToken(
        design_key=991, design_name="Heavy", hull_name="Battleship",
        quantity=1, mass=222, armor=2000, fuel_capacity=2800)
    empire.owned_fleets[fleet.key] = fleet
    _save(harness, server_data)
    return fleet.key


def _order_jump(harness, fleet_key, star_name, x, y):
    harness.submit(1, "waypoint", {
        "mode": "Add",
        "fleet_key": fleet_key,
        "index": 0,
        "waypoint": {
            "position_x": x,
            "position_y": y,
            "warp_factor": 10,
            "destination": star_name,
            "task": {"type": "NoTask"},
        },
    })


# -- mystery trader surgery (pattern: test_mystery_trader.py) ---------

def _advance_year(harness, year):
    server_data = _load(harness)
    server_data.turn_year = year
    for empire in server_data.all_empires.values():
        empire.turn_year = year
    _save(harness, server_data)


def _inject_trader(harness, x, y, vx, vy, warp=7):
    from backend.server.server_data import MysteryTrader
    server_data = _load(harness)
    server_data.trader_counter += 1
    key = server_data.trader_counter
    server_data.all_traders[key] = MysteryTrader(
        key=key, x=x, y=y, velocity_x=vx, velocity_y=vy, warp=warp)
    _save(harness, server_data)
    return key


def _freighter_key(server_data, empire_id=1):
    """Deterministic pick: the lowest-keyed non-starbase fleet."""
    fleets = server_data.all_empires[empire_id].owned_fleets
    return min(k for k, f in fleets.items() if not f.is_starbase)


def _park_with_cargo(harness, fleet_key, x, y, ironium):
    from backend.core.data_structures import NovaPoint
    server_data = _load(harness)
    fleet = server_data.all_empires[1].owned_fleets[fleet_key]
    fleet.position = NovaPoint(x, y)
    fleet.waypoints = []
    fleet.in_orbit = None
    fleet.in_orbit_name = None
    for token in fleet.tokens.values():
        token.cargo_capacity = 10000
    fleet.cargo.ironium = ironium
    fleet.cargo.boranium = 0
    fleet.cargo.germanium = 0
    fleet.fuel_available = 100000
    _save(harness, server_data)


def _gift(harness, fleet_key, trader_key, ironium):
    return harness._request(
        "POST",
        f"/api/games/{harness.game_id}/fleets/{fleet_key}/gift",
        {"empire_id": 1, "trader_key": trader_key, "ironium": ironium})


def _mt_messages(state, needle=None):
    msgs = [m for m in state["messages"]
            if m.get("type") == "Mystery Trader"]
    if needle is not None:
        msgs = [m for m in msgs if needle in m.get("text", "")]
    return msgs


# -- mineral packet surgery (pattern: test_packets.py) ----------------

def _fit_driver(harness, empire_id, rating):
    """Stamp a driver rating on the empire's home starbase token."""
    server_data = _load(harness)
    empire = server_data.all_empires[empire_id]
    home = _home_star(server_data, empire_id)
    starbase = empire.owned_fleets[home.starbase_key]
    for token in starbase.tokens.values():
        token.mass_driver = rating
    _save(harness, server_data)
    return home.name


def _freeze_minerals(harness, star_name, ironium=1000, boranium=1000,
                     germanium=1000):
    """Known surface stock that only packets can change."""
    server_data = _load(harness)
    star = server_data.all_stars[star_name]
    star.mines = 0
    star.manufacturing_queue.orders.clear()
    star.resources_on_hand.ironium = ironium
    star.resources_on_hand.boranium = boranium
    star.resources_on_hand.germanium = germanium
    _save(harness, server_data)


def _add_driver_colony(harness, empire_id, rating):
    """Grant the empire a second colonized star with a driver
    starbase (state surgery), returning its name."""
    from backend.core.game_objects.fleet import Fleet
    from backend.services.ship_specs import find_design, make_token

    server_data = _load(harness)
    empire = server_data.all_empires[empire_id]
    home = _home_star(server_data, empire_id)
    star = min((s for s in server_data.all_stars.values()
                if s.owner == 0 and s.name != home.name),
               key=lambda s: _dist(s, home))
    star.owner = empire_id
    star.colonists = 50000
    design = find_design(empire, "Starbase")
    token = make_token(design, 1)
    token.mass_driver = rating
    base = Fleet(name=f"{star.name} Base", position=star.position.copy())
    base.key = empire.get_next_fleet_key()
    base.tokens[design.key] = token
    empire.add_or_update_fleet(base)
    star.starbase_key = base.key
    empire.owned_stars[star.name] = star
    _save(harness, server_data)
    return star.name


def _fling(harness, empire_id, star_name, target_name, warp, **minerals):
    result = harness.submit(empire_id, "fling_packet", {
        "star": star_name, "target": target_name, "warp": warp,
        **minerals,
    })
    assert result["status"] == "applied"
    return result["fleet_key"]


def _fly_until_resolved(harness, packet_keys, max_years):
    """Generate turns until every packet is gone."""
    for year in range(1, max_years + 1):
        harness.generate_turn()
        server_data = _load(harness)
        remaining = [
            key for key in packet_keys
            if any(key in e.owned_fleets
                   for e in server_data.all_empires.values())
        ]
        if not remaining:
            return year
    raise AssertionError(
        f"packets {remaining} still in flight after {max_years} years")


class TestWave5Integration:

    def test_cross_feature_seeded_game(self, harness):
        from backend.core.data_structures import TechLevel
        from backend.core.globals import STARTING_YEAR, MT_MIN_YEARS

        harness.create_game(seed=SEED, size="small", players=2,
                            race=RACE, mystery_trader=True)
        _clear_phenomena(harness)

        # ==============================================================
        # Phase 1 - waypoint leg editing executes exactly
        # ==============================================================
        home = harness.my_stars(1)[0]
        teamster = _fleet_named(harness, "Teamster")
        assert teamster is not None
        key = teamster["key"]

        stars = [s for s in harness.state(1)["stars"]
                 if s.get("intel") != "owned"]
        stars.sort(key=lambda s: (
            (s["position_x"] - home["position_x"]) ** 2
            + (s["position_y"] - home["position_y"]) ** 2))
        target = stars[0]      # final destination
        detour = stars[1]      # leg removed again below

        # Assemble: [0] LOAD at home (warp 0), [1] detour NoTask warp 6,
        # [2] target Cargo UNLOAD warp 4
        _add_waypoint(harness, key, 0, home["position_x"],
                      home["position_y"], 0, home["name"],
                      {"type": "Cargo", "mode": "LOAD",
                       "amount": {"ironium": LOAD_KT},
                       "target_name": home["name"]})
        _add_waypoint(harness, key, 1, detour["position_x"],
                      detour["position_y"], 6, detour["name"],
                      {"type": "NoTask"})
        _add_waypoint(harness, key, 2, target["position_x"],
                      target["position_y"], 4, target["name"],
                      {"type": "Cargo", "mode": "UNLOAD",
                       "amount": {"ironium": LOAD_KT},
                       "target_name": target["name"]})

        # Warp-only Edit resending the task read back from state - the
        # CargoTask must survive intact (FleetDetail.cs:110)
        wps = _fleet_by_key(harness, key)["waypoints"]
        _add_waypoint(harness, key, 2, wps[2]["position_x"],
                      wps[2]["position_y"], 5, wps[2]["destination"],
                      wps[2]["task"], mode="Edit")

        # Insert a checkpoint before the detour, then delete the detour
        mid_x = (home["position_x"] + target["position_x"]) / 2
        mid_y = (home["position_y"] + target["position_y"]) / 2
        _add_waypoint(harness, key, 1, mid_x, mid_y, 6, "checkpoint",
                      {"type": "NoTask"}, mode="Insert")
        harness.submit(1, "waypoint", {
            "mode": "Delete", "fleet_key": key, "index": 2})

        wps = _fleet_by_key(harness, key)["waypoints"]
        assert [w["destination"] for w in wps] == [
            home["name"], "checkpoint", target["name"]]
        assert [w["warp_factor"] for w in wps] == [0, 6, 5]
        assert wps[2]["task"]["type"] == "CargoTask"
        assert wps[2]["task"]["mode"] == "UNLOAD"
        assert wps[2]["task"]["amount"]["ironium"] == LOAD_KT

        # Execute: the load lands first, then the edited route runs to
        # the target where the cargo task unloads on arrival
        harness.generate_turn()
        assert _fleet_by_key(harness, key)["cargo"]["ironium"] == LOAD_KT

        unloaded = False
        for _ in range(20):
            result = harness.generate_turn()
            if any(m["audience"] == 1
                   and f"has unloaded its cargo at {target['name']}"
                   in m["text"] for m in result["messages"]):
                unloaded = True
                break
        assert unloaded, "teamster never unloaded at the target"
        teamster = _fleet_by_key(harness, key)
        assert teamster["in_orbit"] == target["name"]
        assert teamster["cargo"]["ironium"] == 0

        # ==============================================================
        # Phase 2 - stargates: small hull jumps, battleship refused
        # ==============================================================
        origin_name, dest_name = _gate_pair(harness)
        server_data = _load(harness)
        dest = server_data.all_stars[dest_name]
        dx, dy = dest.position.x, dest.position.y
        origin = server_data.all_stars[origin_name]
        distance = _dist(origin, dest)
        # Class-B stars: 600 ly gates throw 600 * 1.6 = 960 ly - safe
        assert distance < 960

        gate_scout = _fleet_named(harness, "Long Range Scout")["key"]
        _park_fleet(harness, gate_scout, origin_name)
        server_data = _load(harness)
        fuel_before = server_data.all_empires[1] \
            .owned_fleets[gate_scout].fuel_available
        _order_jump(harness, gate_scout, dest_name, dx, dy)

        battleship = _make_battleship(harness, origin_name)
        _order_jump(harness, battleship, dest_name, dx, dy)

        harness.generate_turn()

        server_data = _load(harness)
        scout = server_data.all_empires[1].owned_fleets[gate_scout]
        assert scout.position.x == dx and scout.position.y == dy, \
            "small hull did not gate the full distance in one turn"
        assert scout.fuel_available == fuel_before, \
            "gate jump burned fuel"

        heavy = server_data.all_empires[1].owned_fleets[battleship]
        gone = math.hypot(heavy.position.x - dx, heavy.position.y - dy)
        assert gone > 1, "battleship should not have arrived"
        state = harness.state(1)
        assert any(m.get("type") == "Invalid Command"
                   and "too large" in m.get("text", "")
                   for m in state["messages"]), \
            "no hull-size refusal message"
        assert any(m.message_type == "Stargate"
                   for m in server_data.all_messages), \
            "no stargate jump message"

        # Stand the refused battleship down for the later phases
        heavy.waypoints = []
        _save(harness, server_data)

        # ==============================================================
        # Phase 3 - mystery trader: gift above threshold, component
        # granted, mounted on a real design
        # ==============================================================
        _advance_year(harness, STARTING_YEAR + MT_MIN_YEARS)
        fleet_key = _freighter_key(_load(harness))

        granted = None
        for attempt in range(REWARD_ATTEMPTS):
            server_data = _load(harness)
            traders = server_data.all_traders
            key = min(traders) if traders else None
            if key is None or traders[key].x + 49 > 380:
                key = _inject_trader(harness, x=49, y=200, vx=49, vy=0)
                server_data = _load(harness)
            trader = server_data.all_traders[key]
            next_x, next_y = trader.x + 49, trader.y

            _park_with_cargo(harness, fleet_key, next_x, next_y,
                             ironium=4000)
            harness.generate_turn()

            # Co-location at the turn boundary
            server_data = _load(harness)
            trader = server_data.all_traders[key]
            fleet = server_data.all_empires[1].owned_fleets[fleet_key]
            assert (fleet.position.x, fleet.position.y) == \
                (trader.x, trader.y), "freighter missed the trader"

            result = _gift(harness, fleet_key, key, 4000)
            assert result["gift_total"] == 4000
            harness.generate_turn()

            server_data = _load(harness)
            empire = server_data.all_empires[1]
            state = harness.state(1)
            rewards = _mt_messages(state, "rewards your gift")
            assert len(rewards) == 1, "no reward for a 4000 kT gift"
            if "secret plans" in rewards[0]["text"]:
                granted = empire.mt_components[-1]
                break
        assert granted is not None, \
            f"no component within {REWARD_ATTEMPTS} gifts"
        assert granted in MT_ITEM_SLOT

        # Hidden tech usable: the granted item mounts on a real design
        server_data = _load(harness)
        server_data.all_empires[1].research_levels = \
            TechLevel.from_level(10)
        _save(harness, server_data)

        result = harness.submit(1, "design", {
            "mode": "Add",
            "design": {
                "name": "Trader Tech Boat",
                "hull": "Destroyer",
                "slots": [
                    {"cell_number": 10, "component": "Quick Jump 5",
                     "count": 1},
                    {"cell_number": MT_ITEM_SLOT[granted],
                     "component": granted, "count": 1},
                ],
            },
        })
        assert result["status"] == "applied"
        assert any(d["name"] == "Trader Tech Boat"
                   for d in harness.state(1)["designs"])

        # ==============================================================
        # Phase 4 - packets: safe driver-to-driver exchange, impact on
        # the undefended enemy homeworld
        # ==============================================================
        home_name = _fit_driver(harness, 1, rating=5)
        second_name = _add_driver_colony(harness, 1, rating=5)
        _freeze_minerals(harness, home_name)
        _freeze_minerals(harness, second_name)

        server_data = _load(harness)
        home_star = server_data.all_stars[home_name]
        second = server_data.all_stars[second_name]

        key_out = _fling(harness, 1, home_name, second_name, 5,
                         ironium=200, boranium=50)
        key_back = _fling(harness, 1, second_name, home_name, 5,
                          germanium=120)

        # Fling deducts the surface exactly
        assert home_star.resources_on_hand.ironium == 800
        assert home_star.resources_on_hand.boranium == 950
        assert second.resources_on_hand.germanium == 880

        leg = _dist(home_star, second)
        years = math.ceil(leg / 25) + 2
        _fly_until_resolved(harness, [key_out, key_back], years)

        # Caught safely: every kT lands, no impact message
        assert second.resources_on_hand.ironium == 1200
        assert second.resources_on_hand.boranium == 1050
        assert home_star.resources_on_hand.germanium == 1120
        messages = " ".join(m.get("text", "")
                            for m in harness.state(1)["messages"])
        assert "has caught" in messages
        assert "has struck" not in messages

        # Impact: the driverless, undefended enemy homeworld
        server_data = _load(harness)
        enemy_home = _home_star(server_data, 2)
        enemy_base = server_data.all_empires[2].owned_fleets[
            enemy_home.starbase_key]
        assert enemy_base.mass_driver == 0  # driverless colony
        enemy_home.colonists = 100000
        enemy_home.defenses = 0
        home_star.resources_on_hand.ironium = 100000
        _save(harness, server_data)

        # 30000 kT at warp 5: raw damage 25 * 30000 / 160 = 4687.5 -
        # enough to wipe the undefended colony outright
        key_hit = _fling(harness, 1, home_name, enemy_home.name, 5,
                         ironium=30000)
        years = math.ceil(_dist(home_star, enemy_home) / 25) + 2
        _fly_until_resolved(harness, [key_hit], years)

        assert enemy_home.colonists == 0
        messages = " ".join(m.get("text", "")
                            for m in harness.state(1)["messages"])
        assert "mineral packet has struck" in messages
