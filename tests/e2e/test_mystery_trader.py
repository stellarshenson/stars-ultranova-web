"""
Seeded e2e: the Mystery Trader (canonical Stars! rules - the C#
reference has only a TODO, GameInitialiser.cs:180; user directive,
acc-crit Mystery Trader section).

Full cycle on one seeded game: an organic spawn past the mid-game year
gate is broadcast to both empires and universally visible; a
surgically injected trader with a known course is intercepted by a
freighter parked at its next-turn position; a 4000 kT gift resolves on
the seeded per-turn RNG until the hidden-tech component band lands;
the granted MT component then mounts on a real design for the giver
while the other empire is refused; finally the trader exits and the
departure is broadcast. A separate scenario proves bit-for-bit
determinism (same seed, same surgery, same API calls -> identical
per-empire state digests every turn), and a third proves the New Game
toggle keeps the galaxy trader-free.
"""

import pytest

from backend.services.galaxy_generator import UNIVERSE_SIZES

SEED = 20260727
SPAWN_ATTEMPTS = 80   # spawn chance 1/16 per year past the gate
REWARD_ATTEMPTS = 12  # component odds 55% per 4000 kT gift

RACE = {
    "name": "Traders",
    "pluralName": "Traders",
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


def _advance_year(harness, year):
    server_data = _load(harness)
    server_data.turn_year = year
    for empire in server_data.all_empires.values():
        empire.turn_year = year
    _save(harness, server_data)


def _inject_trader(harness, x, y, vx, vy, warp=7):
    """Surgically add a trader with a known course; returns its key."""
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
    """Park the fleet at (x, y) with the gift load aboard."""
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


class TestMysteryTraderE2E:

    def test_full_trader_cycle(self, harness):
        from backend.core.data_structures import TechLevel
        from backend.core.globals import STARTING_YEAR, MT_MIN_YEARS

        harness.create_game(seed=SEED, size="small", players=2,
                            race=RACE, mystery_trader=True)

        # -- Phase 1: organic spawn past the year gate, broadcast and
        # universally visible to both empires (no scanners involved) --
        _advance_year(harness, STARTING_YEAR + MT_MIN_YEARS)
        spawned = False
        for _ in range(SPAWN_ATTEMPTS):
            harness.generate_turn()
            state1 = harness.state(1)
            if _mt_messages(state1, "entered the galaxy"):
                spawned = True
                break
        assert spawned, f"no spawn within {SPAWN_ATTEMPTS} years"
        state2 = harness.state(2)
        assert _mt_messages(state2, "entered the galaxy"), \
            "spawn broadcast missing for empire 2"
        assert state1["traders"], "trader missing from empire 1 state"
        assert state2["traders"], "trader missing from empire 2 state"
        assert (state1["traders"][0]["name"]
                == state2["traders"][0]["name"])
        warp = state1["traders"][0]["warp"]
        assert 7 <= warp <= 13

        # -- Phase 2 + 3: intercept-and-gift until the hidden-tech
        # component band lands on the seeded per-turn RNG. Each pass
        # parks the freighter at the trader's next-turn position
        # (course is known: velocity is straight-line), generates to
        # co-locate, gifts 4000 kT (tier 3: 55% component) and
        # generates again to resolve the reward. The controlled
        # trader is re-injected whenever the previous one exits. --
        server_data = _load(harness)
        server_data.all_traders.clear()  # replace the organic trader
        _save(harness, server_data)
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
            assert result["threshold"] == 1000
            server_data = _load(harness)
            fleet = server_data.all_empires[1].owned_fleets[fleet_key]
            assert fleet.cargo.ironium == 0, "gift did not drain cargo"
            levels_before = dict(server_data.all_empires[1]
                                 .research_levels.levels)

            harness.generate_turn()

            # The reward landed per the seeded roll; the trader kept
            # the cargo (the ledger zeroed, nothing refunded)
            server_data = _load(harness)
            empire = server_data.all_empires[1]
            trader = server_data.all_traders.get(key)
            if trader is not None:
                assert trader.gifts[1]["total"] == 0
            state1 = harness.state(1)
            rewards = _mt_messages(state1, "rewards your gift")
            assert len(rewards) == 1, "no reward for a 4000 kT gift"
            text = rewards[0]["text"]
            fleet = empire.owned_fleets[fleet_key]
            if "secret plans" in text:
                granted = empire.mt_components[-1]
                break
            elif "trove of research" in text:
                assert sum(empire.research_levels.levels.values()) > \
                    sum(levels_before.values())
                assert fleet.cargo.ironium == 0  # nothing refunded
            elif "refined minerals" in text:
                # Bounty, not refund: 3x the 4000 kT gift (tier-3
                # gifts have no mineral band; tier-2 3x applies only
                # to 2000-3999 - a 4000 kT roll cannot land here)
                raise AssertionError(
                    "mineral bounty rolled in tier 3")
            elif "warship" in text:
                assert any(f.name.startswith("Trader Gift")
                           for f in empire.owned_fleets.values())
        assert granted is not None, \
            f"no component within {REWARD_ATTEMPTS} gifts"
        assert granted in MT_ITEM_SLOT

        # -- Phase 4: hidden tech usable - the granted item mounts on
        # a real design for empire 1; empire 2 is refused the same
        # design (server-side gate) --
        server_data = _load(harness)
        for empire_id in (1, 2):
            server_data.all_empires[empire_id].research_levels = \
                TechLevel.from_level(10)
        _save(harness, server_data)

        design_payload = {
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
        }
        result = harness.submit(1, "design", design_payload)
        assert result["status"] == "applied"
        assert any(d["name"] == "Trader Tech Boat"
                   for d in harness.state(1)["designs"])

        result = harness.submit(2, "design", design_payload)
        assert result["status"] == "error"
        assert "Mystery Trader grant" in result["error"]

        # -- Phase 5: departure - the trader exits the far side and
        # the departure is broadcast to every empire --
        server_data = _load(harness)
        if not server_data.all_traders:
            _inject_trader(harness, x=49, y=200, vx=49, vy=0)
            server_data = _load(harness)
        key = min(server_data.all_traders)
        trader = server_data.all_traders[key]
        # One 49 ly step short of the board edge, so the next step
        # leaves the galaxy (board width from the canonical size table)
        trader.x = float(UNIVERSE_SIZES["small"][0]) - 8.0
        _save(harness, server_data)

        harness.generate_turn()
        server_data = _load(harness)
        assert key not in server_data.all_traders
        for empire_id in (1, 2):
            state = harness.state(empire_id)
            assert _mt_messages(state, "left the galaxy"), \
                f"departure broadcast missing for empire {empire_id}"
            assert not any(t["key"] == key for t in state["traders"])

    def _deterministic_run(self, harness):
        """Compact seeded scenario: inject a known trader, intercept,
        gift above threshold, resolve; returns per-turn digests."""
        harness.create_game(seed=SEED, size="small", players=2,
                            race=RACE, mystery_trader=True)
        from backend.core.globals import STARTING_YEAR, MT_MIN_YEARS
        _advance_year(harness, STARTING_YEAR + MT_MIN_YEARS)
        _inject_trader(harness, x=49, y=200, vx=49, vy=0)
        fleet_key = _freighter_key(_load(harness))
        _park_with_cargo(harness, fleet_key, 98, 200, ironium=4000)

        digests = [harness.generate_turn()["digests"]]
        _gift(harness, fleet_key, 1, 4000)
        digests.append(harness.generate_turn()["digests"])
        digests.append(harness.generate_turn()["digests"])
        return digests

    def test_determinism_bit_for_bit(self, harness):
        """The identical seeded scenario in two games reproduces
        identical per-empire state digests every turn: spawn timing,
        course and rewards are bit-for-bit deterministic."""
        first = self._deterministic_run(harness)
        second = self._deterministic_run(harness)
        assert first == second

    def test_toggle_off_no_trader(self, harness):
        """mystery_trader=False: years past the gate, no trader, no
        broadcast, ever."""
        from backend.core.globals import STARTING_YEAR, MT_MIN_YEARS
        harness.create_game(seed=SEED, size="small", players=2,
                            race=RACE, mystery_trader=False)
        _advance_year(harness, STARTING_YEAR + MT_MIN_YEARS)
        for _ in range(30):
            harness.generate_turn()
            state = harness.state(1)
            assert state["traders"] == []
            assert not _mt_messages(state)
