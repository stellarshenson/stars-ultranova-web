"""
Seeded e2e: mineral packets and mass drivers (canonical Stars! rules,
C# absent - MassDriver.cs only defines the component property).

Setup uses the established state-surgery pattern (see
tests/e2e/test_storms.py): starting starbases get a mass driver
rating stamped on their token, dust nebulae and storms are cleared so
flight math and scanning are exact, and the mineral books of the
stars under test are frozen (no mines, empty production queue).

Scenarios:
- two driver stars exchange packets safely (exact surface deltas,
  warp^2 flight, no decay at the rated warp) while the driverless
  enemy homeworld takes canonical packet damage;
- an enemy scanner picks a passing packet up as a foreign-fleet
  contact and the stale report is purged after the packet resolves;
- a fleet parked on a packet's position loads (steals) minerals from
  it, colonist/fuel deltas are rejected, and the emptied packet
  vanishes;
- determinism: the same seed and script produce identical per-turn
  digests across two runs.
"""

import math

import pytest

SEED = 20260727

RACE = {
    "name": "Packeteers",
    "pluralName": "Packeteers",
    "prt": "JOAT",
}


def _manager():
    from backend.services.game_manager import get_game_manager
    return get_game_manager()


def _load(harness):
    return _manager()._load_game_state(harness.game_id)


def _save(harness, server_data):
    _manager()._save_game_state(harness.game_id, server_data)


def _dist(a, b):
    return math.hypot(a.position.x - b.position.x,
                      a.position.y - b.position.y)


def _home_star(server_data, empire_id):
    return next(s for s in server_data.all_empires[empire_id]
                .owned_stars.values())


def _clear_phenomena(harness):
    """Exact flight math and scanning: no dust drag, no storm static."""
    server_data = _load(harness)
    server_data.nebula_field.regions = []
    server_data.all_storms = {}
    _save(harness, server_data)


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
    """Generate turns until every packet is gone; returns the number
    of turns generated."""
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


class TestPacketExchangeAndImpact:

    def test_driver_stars_exchange_driverless_colony_takes_damage(
            self, harness):
        harness.create_game(seed=SEED, size="small", players=2,
                            race=RACE)
        _clear_phenomena(harness)
        home_name = _fit_driver(harness, 1, rating=5)
        second_name = _add_driver_colony(harness, 1, rating=5)
        _freeze_minerals(harness, home_name)
        _freeze_minerals(harness, second_name)

        server_data = _load(harness)
        empire1 = server_data.all_empires[1]
        home = server_data.all_stars[home_name]
        second = server_data.all_stars[second_name]

        # -- Exchange: both driver stars fling at the rated warp -----
        key_out = _fling(harness, 1, home_name, second_name, 5,
                         ironium=200, boranium=50)
        key_back = _fling(harness, 1, second_name, home_name, 5,
                          germanium=120)

        # Fling deducts the surface exactly
        assert home.resources_on_hand.ironium == 800
        assert home.resources_on_hand.boranium == 950
        assert second.resources_on_hand.germanium == 880

        # Packets are visible own fleets with the packet flag
        state = harness.state(1)
        flying = {f["key"]: f for f in state["fleets"]
                  if f["key"] in (key_out, key_back)}
        assert set(flying) == {key_out, key_back}
        for fleet in flying.values():
            assert fleet["is_packet"] is True
            assert fleet["packet_warp"] == 5

        # Flight math: warp 5 covers 25 ly in the first year
        packet = empire1.owned_fleets[key_out]
        start = packet.position.copy()
        leg = _dist(home, second)
        harness.generate_turn()
        if key_out in empire1.owned_fleets:
            moved = math.hypot(packet.position.x - start.x,
                               packet.position.y - start.y)
            assert moved == pytest.approx(25, abs=1.6)

        years = math.ceil(leg / 25) + 2
        _fly_until_resolved(harness, [key_out, key_back], years)

        # Caught safely: every kT lands, no impact message anywhere
        # (colonist counts only drift with habitability growth here)
        assert second.resources_on_hand.ironium == 1200
        assert second.resources_on_hand.boranium == 1050
        assert second.resources_on_hand.germanium == 880
        assert home.resources_on_hand.ironium == 800
        assert home.resources_on_hand.germanium == 1120
        messages = " ".join(m.get("text", "")
                            for m in harness.state(1)["messages"])
        assert "has caught" in messages
        assert "has struck" not in messages

        # -- Impact: the driverless enemy homeworld ------------------
        enemy_home = _home_star(server_data, 2)
        enemy_base = server_data.all_empires[2].owned_fleets[
            enemy_home.starbase_key]
        assert enemy_base.mass_driver == 0  # driverless colony
        assert enemy_home.colonists > 0

        server_data = _load(harness)
        home.resources_on_hand.ironium = 100000
        _save(harness, server_data)

        # 30000 kT at warp 5: raw damage 25 * 30000 / 160 = 4687.5 -
        # enough to wipe the colony through any early defense coverage
        key_hit = _fling(harness, 1, home_name, enemy_home.name, 5,
                         ironium=30000)
        years = math.ceil(_dist(home, enemy_home) / 25) + 2
        _fly_until_resolved(harness, [key_hit], years)

        assert enemy_home.colonists == 0
        assert enemy_home.defenses == 0
        # Uncaught impact still recovers minerals on the surface
        state = harness.state(1)
        messages = " ".join(m.get("text", "") for m in state["messages"])
        assert "mineral packet has struck" in messages


class TestPacketScannedByEnemy:

    def test_contact_appears_then_purges(self, harness):
        harness.create_game(seed=SEED, size="small", players=2,
                            race=RACE)
        _clear_phenomena(harness)
        home_name = _fit_driver(harness, 1, rating=5)
        _freeze_minerals(harness, home_name, ironium=5000)

        server_data = _load(harness)
        empire1 = server_data.all_empires[1]
        home = server_data.all_stars[home_name]
        enemy_home = _home_star(server_data, 2)
        # The enemy homeworld's planetary scanner sees the packet on
        # its final approach (25 ly per year at warp 5)
        assert enemy_home.scan_range >= 25

        key = _fling(harness, 1, home_name, enemy_home.name, 5,
                     ironium=300)
        years = math.ceil(_dist(home, enemy_home) / 25) + 2

        seen = False
        for _ in range(years):
            harness.generate_turn()
            contacts = [f for f in harness.state(2)["foreign_fleets"]
                        if f["key"] == key]
            if contacts:
                seen = True
                contact = contacts[0]
                assert "Mineral Packet" in contact["name"]
                assert any(
                    c.get("design_name") == "Mineral Packet"
                    for c in contact.get("composition", []))
            if key not in empire1.owned_fleets:
                break
        assert seen, "enemy scanners never detected the packet"
        assert key not in empire1.owned_fleets, "packet never arrived"

        # Stale report purged by the next scan
        harness.generate_turn()
        assert key not in [f["key"]
                           for f in harness.state(2)["foreign_fleets"]]


class TestPacketInterception:

    def test_fleet_loads_minerals_from_packet(self, harness):
        harness.create_game(seed=SEED, size="small", players=2,
                            race=RACE)
        _clear_phenomena(harness)
        home_name = _fit_driver(harness, 1, rating=5)
        _freeze_minerals(harness, home_name)

        server_data = _load(harness)
        empire1 = server_data.all_empires[1]
        empire2 = server_data.all_empires[2]
        home = server_data.all_stars[home_name]

        # Long flight so the packet is deep in space when boarded
        target = max((s for s in server_data.all_stars.values()
                      if s.name != home_name),
                     key=lambda s: _dist(s, home))
        key = _fling(harness, 1, home_name, target.name, 5, ironium=60)
        harness.generate_turn()
        packet = empire1.owned_fleets[key]
        assert packet.in_orbit_name is None

        # Park an enemy fleet exactly on the packet (surgery -
        # interception flight is ordinary waypoint travel; the hold is
        # widened so the whole packet fits)
        freighter = next(f for f in empire2.owned_fleets.values()
                         if not f.is_starbase)
        for token in freighter.tokens.values():
            token.cargo_capacity = 100
        freighter.cargo = type(freighter.cargo)()
        freighter.position = packet.position.copy()
        freighter.waypoints = []
        freighter.in_orbit = None
        freighter.in_orbit_name = None
        _save(harness, server_data)

        path = (f"/api/games/{harness.game_id}/fleets/"
                f"{freighter.key}/transfer")

        # Steal 20 kT
        result = harness._request("POST", path, {
            "empire_id": 2, "target_fleet_key": key, "ironium": 20})
        assert result["status"] == "ok"
        assert freighter.cargo.ironium == 20
        assert packet.cargo.ironium == 40

        # Packets carry minerals only: colonist and fuel deltas 400
        for bad in ({"colonists": 100}, {"fuel": 5}):
            response = harness.client.request("POST", path, json={
                "empire_id": 2, "target_fleet_key": key, **bad})
            assert response.status_code == 400

        # Empty it - the packet vanishes everywhere
        result = harness._request("POST", path, {
            "empire_id": 2, "target_fleet_key": key, "ironium": 40})
        assert result["status"] == "ok"
        assert freighter.cargo.ironium == 60
        assert key not in empire1.owned_fleets
        assert all(key not in e.fleet_reports
                   for e in server_data.all_empires.values())


class TestPacketDeterminism:

    def test_same_seed_same_digests(self, harness):
        def run():
            harness.create_game(seed=SEED, size="small", players=2,
                                race=RACE)
            _clear_phenomena(harness)
            home_name = _fit_driver(harness, 1, rating=5)
            _freeze_minerals(harness, home_name)
            server_data = _load(harness)
            home = server_data.all_stars[home_name]
            target = min((s for s in server_data.all_stars.values()
                          if s.name != home_name),
                         key=lambda s: _dist(s, home))
            _fling(harness, 1, home_name, target.name, 6,
                   ironium=200, boranium=100)
            return [harness.generate_turn()["digests"]
                    for _ in range(3)]

        assert run() == run()
