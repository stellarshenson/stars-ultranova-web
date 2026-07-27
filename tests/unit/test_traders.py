"""
Tests for the Mystery Trader (canonical Stars! rules - the C# reference
has only a TODO, GameInitialiser.cs:180 "Mystery Trader Items ...
hidden technology"): seeded spawning, straight-line course and exit,
untouchability by construction, universal visibility, gift thresholds,
every reward band, hidden-tech gating, the game-creation toggle and
serialization.
"""

import math
import random

import pytest

from backend.server.server_data import (
    ServerData, GalacticStorm, Minefield, MysteryTrader
)
from backend.server.turn_generator import TurnGenerator, MT_ITEMS
from backend.core.data_structures import EmpireData, NovaPoint, TechLevel
from backend.core.data_structures.tech_level import RESEARCH_KEYS
from backend.core.game_objects.fleet import Fleet, ShipToken
from backend.core.race.race import Race
from backend.core.waypoints.waypoint import Waypoint
from backend.core.globals import (
    STARTING_YEAR, EVERYONE,
    MT_MIN_YEARS, MT_LATE_YEARS, MT_SPAWN_CHANCE, MT_MAX_ACTIVE_EARLY,
    MT_MAX_ACTIVE_LATE, MT_WARP_MIN, MT_WARP_MAX, MT_GIFT_THRESHOLD,
    MT_TIER2_GIFT, MT_TIER3_GIFT, MT_MINERAL_BOUNTY_FACTOR,
)


def make_fleet(key: int, owner: int, x: float, y: float,
               quantity: int = 1, armor: int = 100,
               cargo_capacity: int = 0) -> Fleet:
    """Build a minimal real fleet with one token."""
    fleet = Fleet(name=f"Fleet #{key}", position=NovaPoint(x, y))
    fleet._key = (owner << 32) | key
    fleet.owner_int = owner
    fleet.owner = owner
    fleet.tokens[1] = ShipToken(
        design_key=1, design_name="Testship", quantity=quantity,
        mass=10, armor=armor, fuel_capacity=500,
        cargo_capacity=cargo_capacity,
    )
    fleet.fuel_available = 500
    return fleet


def make_state(*fleets: Fleet) -> ServerData:
    state = ServerData()
    for fleet in fleets:
        empire_id = fleet.owner
        if empire_id not in state.all_empires:
            empire = EmpireData()
            empire.id = empire_id
            state.all_empires[empire_id] = empire
        state.all_empires[empire_id].owned_fleets[fleet.key] = fleet
    return state


def make_trader(key: int = 1, x: float = 300.0, y: float = 300.0,
                vx: float = 0.0, vy: float = 0.0,
                warp: int = 7) -> MysteryTrader:
    return MysteryTrader(key=key, x=x, y=y,
                         velocity_x=vx, velocity_y=vy, warp=warp)


def seed_where(predicate):
    """First RNG seed whose FIRST random() draw satisfies predicate
    (the reward/spawn roll is the first draw _process_traders makes)."""
    for seed in range(10000):
        if predicate(random.Random(seed).random()):
            return seed
    raise AssertionError("no seed found")


def trader_messages(state, needle=None):
    msgs = [m for m in state.all_messages
            if m.message_type == "Mystery Trader"]
    if needle is not None:
        msgs = [m for m in msgs if needle in m.text]
    return msgs


class TestTraderSpawning:
    """Seeded spawning: year gate, edge placement, warp band, caps."""

    def test_no_spawn_before_min_years(self):
        state = ServerData()
        state.turn_year = STARTING_YEAR + MT_MIN_YEARS - 1
        gen = TurnGenerator(state)
        gen.rand.seed(seed_where(lambda r: r < MT_SPAWN_CHANCE))
        for _ in range(200):
            gen._process_traders()
        assert state.all_traders == {}

    def test_spawn_after_min_years_seeded(self):
        state = ServerData()
        state.turn_year = STARTING_YEAR + MT_MIN_YEARS
        gen = TurnGenerator(state)
        gen.rand.seed(seed_where(lambda r: r < MT_SPAWN_CHANCE))
        gen._process_traders()

        assert len(state.all_traders) == 1
        trader = next(iter(state.all_traders.values()))
        assert trader.key == 1
        assert state.trader_counter == 1
        # Spawn point sits exactly ON an edge of the default 600x600
        # board, heading inward toward the opposite edge
        assert (trader.x in (0.0, 600.0)) or (trader.y in (0.0, 600.0))
        if trader.x == 0.0:
            assert trader.velocity_x > 0
        elif trader.x == 600.0:
            assert trader.velocity_x < 0
        elif trader.y == 0.0:
            assert trader.velocity_y > 0
        else:
            assert trader.velocity_y < 0
        # Canonical warp band; speed is exactly warp^2 ly per year
        assert MT_WARP_MIN <= trader.warp <= MT_WARP_MAX
        speed = math.hypot(trader.velocity_x, trader.velocity_y)
        assert speed == pytest.approx(trader.warp ** 2)
        # Spawn broadcast reaches every empire
        spawns = trader_messages(state, "entered the galaxy")
        assert len(spawns) == 1
        assert spawns[0].audience == EVERYONE

    def test_active_cap_early(self):
        state = ServerData()
        state.turn_year = STARTING_YEAR + MT_MIN_YEARS
        state.all_traders[1] = make_trader(key=1)  # stationary
        state.trader_counter = 1
        gen = TurnGenerator(state)
        gen.rand.seed(seed_where(lambda r: r < MT_SPAWN_CHANCE))
        for _ in range(200):
            gen._process_traders()
        assert len(state.all_traders) == MT_MAX_ACTIVE_EARLY
        assert list(state.all_traders) == [1]

    def test_active_cap_late(self):
        state = ServerData()
        state.turn_year = STARTING_YEAR + MT_LATE_YEARS
        state.all_traders[1] = make_trader(key=1)
        state.all_traders[2] = make_trader(key=2)
        state.trader_counter = 2
        gen = TurnGenerator(state)
        gen.rand.seed(7)
        reached = 0
        for _ in range(300):
            gen._process_traders()
            reached = max(reached, len(state.all_traders))
            assert len(state.all_traders) <= MT_MAX_ACTIVE_LATE
        assert reached == MT_MAX_ACTIVE_LATE

    def test_disabled_toggle(self):
        state = ServerData()
        state.turn_year = STARTING_YEAR + MT_MIN_YEARS
        state.mystery_trader_enabled = False
        gen = TurnGenerator(state)
        gen.rand.seed(seed_where(lambda r: r < MT_SPAWN_CHANCE))
        for _ in range(300):
            gen._process_traders()
        assert state.all_traders == {}
        assert not trader_messages(state)


class TestTraderCourse:
    """Straight-line movement, exit and moving-waypoint retargeting."""

    def test_straight_line_and_exit(self):
        state = ServerData()  # default year - spawn gate inactive
        trader = make_trader(key=1, x=300, y=300, vx=49.0, vy=0.0)
        state.all_traders[1] = trader
        gen = TurnGenerator(state)

        gen._process_traders()
        assert (trader.x, trader.y) == (349.0, 300.0)
        gen._process_traders()
        assert (trader.x, trader.y) == (398.0, 300.0)

        # Near the far edge: the first out-of-bounds step is the exit
        trader.x = 580.0
        gen._process_traders()
        assert 1 not in state.all_traders
        departures = trader_messages(state, "left the galaxy")
        assert len(departures) == 1
        assert departures[0].audience == EVERYONE

    def test_moving_waypoint_retarget(self):
        trader = make_trader(key=1, x=300, y=300, vx=49.0, vy=0.0)
        fleet = make_fleet(1, 1, 100, 100)
        fleet.waypoints.append(Waypoint(
            position_x=300, position_y=300, warp_factor=9,
            destination=trader.name))
        state = make_state(fleet)
        state.all_traders[1] = trader
        gen = TurnGenerator(state)

        gen._process_traders()
        wp = fleet.waypoints[0]
        assert (wp.position_x, wp.position_y) == (349.0, 300.0)
        assert wp.destination == trader.name

        # Departed trader: destination frozen into a positional label
        trader.x = 580.0
        gen._process_traders()
        wp = fleet.waypoints[0]
        assert wp.destination == "Space at 349,300"
        assert (wp.position_x, wp.position_y) == (349.0, 300.0)


class TestTraderUntouchable:
    """The trader is untouchable BY CONSTRUCTION: it is not a Fleet
    and belongs to no empire, so battles, minefields and storms never
    see it (asserted, no defensive code in the engine)."""

    def test_untouchable_by_construction(self):
        fleet = make_fleet(1, 1, 300, 300, quantity=2, armor=1000)
        fleet.tokens[1].has_weapons = True
        state = make_state(fleet)
        trader = make_trader(key=1, x=300, y=300)
        trader.gifts[1] = {"total": 0, "fleet_key": fleet.key}
        state.all_traders[1] = trader
        state.all_storms[1] = GalacticStorm(
            key=1, x=300, y=300, radius=50,
            velocity_x=0, velocity_y=0, intensity=1.0)
        state.all_minefields[1] = Minefield(
            key=1, owner=2, position_x=300, position_y=300,
            number_of_mines=2500, mine_type=0)

        gen = TurnGenerator(state)
        gen.generate()

        # Trader unharmed and unmoved (zero velocity), ledger intact
        assert state.all_traders[1] is trader
        assert (trader.x, trader.y) == (300.0, 300.0)
        assert trader.gifts == {1: {"total": 0, "fleet_key": fleet.key}}
        # No battle happened; no storm or minefield message names it
        assert not any(m.message_type == "Battle"
                       for m in state.all_messages)
        assert not any(
            trader.name in m.text for m in state.all_messages
            if m.message_type in ("Storm", "Minefield Hit",
                                  "Minefield Detonation"))


class TestTraderRewards:
    """Reward table bands on the seeded RNG (turn_generator comment
    block is the authoritative odds table)."""

    def _gift_state(self, total, cargo_capacity=0):
        fleet = make_fleet(1, 1, 300, 300,
                           cargo_capacity=cargo_capacity)
        state = make_state(fleet)
        trader = make_trader(key=1, x=300, y=300)
        trader.gifts[1] = {"total": total, "fleet_key": fleet.key}
        state.all_traders[1] = trader
        return state, trader, fleet

    def test_gift_below_threshold_no_reward(self):
        state, trader, fleet = self._gift_state(MT_GIFT_THRESHOLD - 1)
        gen = TurnGenerator(state)
        gen._process_traders()
        # Balance persists, polite message only, no reward of any kind
        assert trader.gifts[1]["total"] == MT_GIFT_THRESHOLD - 1
        polite = trader_messages(state, "courteous nod")
        assert len(polite) == 1
        assert polite[0].audience == 1
        assert not trader_messages(state, "rewards your gift")
        assert state.all_empires[1].mt_components == []

    def test_gift_reward_component(self):
        state, trader, fleet = self._gift_state(MT_GIFT_THRESHOLD)
        gen = TurnGenerator(state)
        gen.rand.seed(seed_where(lambda r: r < 0.40))  # tier-1 component
        gen._process_traders()
        empire = state.all_empires[1]
        assert trader.gifts[1]["total"] == 0
        assert len(empire.mt_components) == 1
        assert empire.mt_components[0] in MT_ITEMS
        rewards = trader_messages(state, "secret plans")
        assert len(rewards) == 1
        assert rewards[0].audience == 1

    def test_reward_research(self):
        state, trader, fleet = self._gift_state(MT_GIFT_THRESHOLD)
        gen = TurnGenerator(state)
        gen.rand.seed(seed_where(lambda r: 0.40 <= r < 0.70))
        gen._process_traders()
        empire = state.all_empires[1]
        levels = empire.research_levels.levels
        # Tier 1: +1 level in exactly 2 distinct fields
        assert sum(levels.get(k, 0) for k in RESEARCH_KEYS) == 2
        assert sorted(levels.values(), reverse=True)[:2] == [1, 1]
        assert trader_messages(state, "trove of research")

    def test_reward_mineral_bounty(self):
        state, trader, fleet = self._gift_state(
            MT_GIFT_THRESHOLD, cargo_capacity=5000)
        fleet.fuel_available = 100
        gen = TurnGenerator(state)
        gen.rand.seed(seed_where(lambda r: r >= 0.70))  # tier-1 minerals
        gen._process_traders()
        # 2x gift, split evenly, and fuel topped to full
        bounty = MT_MINERAL_BOUNTY_FACTOR * MT_GIFT_THRESHOLD
        assert fleet.cargo.mass == bounty
        assert fleet.cargo.ironium == bounty // 3
        assert fleet.cargo.boranium == bounty // 3
        assert fleet.fuel_available == fleet.total_fuel_capacity
        assert trader_messages(state, "refined minerals")

    def test_reward_mineral_bounty_clamped_to_free_space(self):
        state, trader, fleet = self._gift_state(
            MT_GIFT_THRESHOLD, cargo_capacity=900)
        gen = TurnGenerator(state)
        gen.rand.seed(seed_where(lambda r: r >= 0.70))
        gen._process_traders()
        assert fleet.cargo.mass == 900
        assert fleet.cargo.ironium == 300

    def test_reward_gifted_ship(self):
        state, trader, fleet = self._gift_state(MT_TIER3_GIFT)
        gen = TurnGenerator(state)
        gen.rand.seed(seed_where(lambda r: r >= 0.75))  # tier-3 ship
        gen._process_traders()
        empire = state.all_empires[1]
        marauders = [d for d in empire.designs.values()
                     if d.name == "Trader Marauder"]
        assert len(marauders) == 1
        assert marauders[0].armor == 2000
        gifts = [f for f in empire.owned_fleets.values()
                 if f.name.startswith("Trader Gift")]
        assert len(gifts) == 1
        gifted = gifts[0]
        assert (gifted.position.x, gifted.position.y) == (300.0, 300.0)
        assert gifted.owner == 1
        token = next(iter(gifted.tokens.values()))
        assert token.design_name == "Trader Marauder"
        assert gifted.fuel_available == gifted.total_fuel_capacity
        assert trader_messages(state, "warship")

    def test_all_components_owned_falls_back_to_research(self):
        state, trader, fleet = self._gift_state(MT_GIFT_THRESHOLD)
        empire = state.all_empires[1]
        empire.mt_components = list(MT_ITEMS)
        gen = TurnGenerator(state)
        gen.rand.seed(seed_where(lambda r: r < 0.40))  # component band
        gen._process_traders()
        assert empire.mt_components == list(MT_ITEMS)  # nothing added
        levels = empire.research_levels.levels
        assert sum(levels.get(k, 0) for k in RESEARCH_KEYS) == 2
        assert trader_messages(state, "trove of research")

    def test_dead_gifting_fleet_converts_bounty_to_research(self):
        state, trader, fleet = self._gift_state(MT_GIFT_THRESHOLD)
        trader.gifts[1]["fleet_key"] = 999  # no such fleet
        gen = TurnGenerator(state)
        gen.rand.seed(seed_where(lambda r: r >= 0.70))  # mineral band
        gen._process_traders()
        levels = state.all_empires[1].research_levels.levels
        assert sum(levels.get(k, 0) for k in RESEARCH_KEYS) == 2
        assert trader_messages(state, "trove of research")


class TestHiddenTechGating:
    """MT items are buildable only after a trader grant; research can
    never unlock them (Tech all zero, catalog property gate)."""

    def _empire(self, tech=10):
        empire = EmpireData(id=1)
        empire.race = Race(name="Testers", primary_trait="JOAT")
        empire.research_levels = TechLevel.from_level(tech)
        return empire

    def test_component_grant_unlocks_design(self):
        from backend.services.design_builder import (
            build_ship_design, ensure_components_loaded)
        ensure_components_loaded()
        empire = self._empire()
        slots = [
            {"cell_number": 10, "component": "Quick Jump 5", "count": 1},
            {"cell_number": 2, "component": "Anti-Matter Torpedo",
             "count": 1},
        ]
        design, error = build_ship_design(
            empire, "MT Boat", "Destroyer", slots)
        assert design is None
        assert "requires a Mystery Trader grant" in error

        empire.mt_components.append("Anti-Matter Torpedo")
        design, error = build_ship_design(
            empire, "MT Boat", "Destroyer", slots)
        assert error is None
        assert any(w.power == 60 and w.range == 6
                   for w in design.weapons)

    def test_zero_tech_passes_tech_gate_for_mt_items(self):
        from backend.services.design_builder import (
            _tech_ok, ensure_components_loaded)
        loader = ensure_components_loaded()
        empire = self._empire(tech=0)
        for name in MT_ITEMS:
            comp = loader.get_component(name)
            assert comp is not None
            # Research never gates MT items - Tech is all zero
            assert _tech_ok(empire, comp)
            assert all(v == 0 for v in comp.required_tech.levels.values())


class TestTraderGameManager:
    """gift_to_trader API path, universal visibility and multi-empire
    independence on a real (tiny, seeded) game."""

    @pytest.fixture
    def game(self, tmp_path):
        from backend.services.game_manager import GameManager
        manager = GameManager(str(tmp_path / "trader.db"))
        created = manager.create_game("t", 2, "tiny", seed=4242)
        game_id = created["id"]
        server_data = manager._load_game_state(game_id)
        # Surgically inject a stationary trader clear of every star
        trader = make_trader(key=1, x=150, y=5)
        server_data.trader_counter = 1
        server_data.all_traders[1] = trader
        return manager, game_id, server_data, trader

    def _park_freighter(self, server_data, empire_id, trader,
                        ironium=0):
        empire = server_data.all_empires[empire_id]
        fleet = next(f for f in empire.owned_fleets.values()
                     if not f.is_starbase)
        fleet.position = NovaPoint(trader.x, trader.y)
        fleet.waypoints = []
        fleet.in_orbit = None
        fleet.in_orbit_name = None
        for token in fleet.tokens.values():
            token.cargo_capacity = 10000
        fleet.cargo.ironium = ironium
        return fleet

    def test_universal_visibility(self, game):
        manager, game_id, server_data, trader = game
        # No scanner is anywhere near (150, 5); both empires still see
        # the same trader entry
        views = []
        for empire_id in (1, 2):
            state = manager.get_player_state(game_id, empire_id)
            assert len(state["traders"]) == 1
            entry = state["traders"][0]
            assert entry["name"] == "Mystery Trader 1"
            assert (entry["x"], entry["y"]) == (150, 5)
            assert entry["gift_total"] == 0
            views.append(entry)
        assert views[0] == views[1]
        # mt_components ride the player state
        assert state["mt_components"] == []

    def test_gift_validation_and_ledger(self, game):
        manager, game_id, server_data, trader = game
        fleet = self._park_freighter(server_data, 1, trader, ironium=800)

        # Not co-located fleets are rejected
        far = next(f for f in server_data.all_empires[1]
                   .owned_fleets.values()
                   if f.key != fleet.key and not f.is_starbase)
        result = manager.gift_to_trader(
            game_id, 1, far.key, 1, {"ironium": 10})
        assert "position" in result["error"]

        # Negative amounts and fuel are rejected (one-way gift)
        assert "error" in manager.gift_to_trader(
            game_id, 1, fleet.key, 1, {"ironium": -5})
        assert "error" in manager.gift_to_trader(
            game_id, 1, fleet.key, 1, {"ironium": 5, "fuel": 10})
        # Giver must have the goods
        assert "error" in manager.gift_to_trader(
            game_id, 1, fleet.key, 1, {"boranium": 5})

        result = manager.gift_to_trader(
            game_id, 1, fleet.key, 1, {"ironium": 500})
        assert result["status"] == "ok"
        assert result["gift_total"] == 500
        assert result["threshold"] == MT_GIFT_THRESHOLD
        assert fleet.cargo.ironium == 300

        # Top-up accumulates on the same ledger entry
        result = manager.gift_to_trader(
            game_id, 1, fleet.key, 1, {"ironium": 300})
        assert result["gift_total"] == 800
        assert trader.gifts[1] == {"total": 800, "fleet_key": fleet.key}

    def test_multi_empire_independent_gifts(self, game):
        manager, game_id, server_data, trader = game
        fleet1 = self._park_freighter(server_data, 1, trader,
                                      ironium=MT_GIFT_THRESHOLD)
        fleet2 = self._park_freighter(server_data, 2, trader,
                                      ironium=300)

        r1 = manager.gift_to_trader(
            game_id, 1, fleet1.key, 1,
            {"ironium": MT_GIFT_THRESHOLD})
        r2 = manager.gift_to_trader(
            game_id, 2, fleet2.key, 1, {"ironium": 300})
        assert r1["gift_total"] == MT_GIFT_THRESHOLD
        assert r2["gift_total"] == 300

        manager.generate_turn(game_id)

        server_data = manager._load_game_state(game_id)
        trader = server_data.all_traders[1]
        # Empire 1 resolved (balance zeroed, reward message); empire 2
        # below threshold (balance persists, polite message)
        assert trader.gifts[1]["total"] == 0
        assert trader.gifts[2]["total"] == 300
        state1 = manager.get_player_state(game_id, 1)
        state2 = manager.get_player_state(game_id, 2)
        rewards1 = [m for m in state1["messages"]
                    if m["type"] == "Mystery Trader"
                    and "rewards your gift" in m["text"]]
        assert len(rewards1) == 1
        polite2 = [m for m in state2["messages"]
                   if m["type"] == "Mystery Trader"
                   and "courteous nod" in m["text"]]
        assert len(polite2) == 1
        # Neither empire sees the other's reward/apology
        assert not any("courteous nod" in m["text"]
                       for m in state1["messages"]
                       if m["type"] == "Mystery Trader")
        assert not any("rewards your gift" in m["text"]
                       for m in state2["messages"]
                       if m["type"] == "Mystery Trader")


class TestTraderSerialization:
    """Traders, counters, toggle and grants survive persistence."""

    def test_server_data_roundtrip(self):
        state = ServerData()
        trader = make_trader(key=3, x=10, y=20, vx=49, vy=-7, warp=7)
        trader.gifts[1] = {"total": 500, "fleet_key": 42}
        trader.gifts[2] = {"total": 1200, "fleet_key": 99}
        state.all_traders[3] = trader
        state.trader_counter = 3
        state.mystery_trader_enabled = False

        restored = ServerData.from_dict(state.to_dict())
        r = restored.all_traders[3]
        assert (r.x, r.y) == (10, 20)
        assert (r.velocity_x, r.velocity_y) == (49, -7)
        assert r.warp == 7
        assert r.name == "Mystery Trader 3"
        assert r.gifts == {1: {"total": 500, "fleet_key": 42},
                           2: {"total": 1200, "fleet_key": 99}}
        assert restored.trader_counter == 3
        assert restored.mystery_trader_enabled is False

    def test_pre_trader_save_loads_cleanly(self):
        state = ServerData()
        data = state.to_dict()
        for key in ("all_traders", "trader_counter",
                    "mystery_trader_enabled"):
            del data[key]
        restored = ServerData.from_dict(data)
        assert restored.all_traders == {}
        assert restored.trader_counter == 0
        assert restored.mystery_trader_enabled is True

    def test_empire_mt_components_roundtrip(self):
        empire = EmpireData(id=1)
        empire.mt_components = ["Anti-Matter Torpedo", "Genesis Device"]
        restored = EmpireData.from_dict(empire.to_dict())
        assert restored.mt_components == ["Anti-Matter Torpedo",
                                          "Genesis Device"]

    def test_game_manager_state_roundtrip(self, tmp_path):
        from backend.services.game_manager import GameManager
        manager = GameManager(str(tmp_path / "roundtrip.db"))
        created = manager.create_game("t", 2, "tiny", seed=17)
        game_id = created["id"]
        server_data = manager._load_game_state(game_id)
        trader = make_trader(key=1, x=5, y=5, vx=49, vy=0)
        trader.gifts[1] = {"total": 700, "fleet_key": 4294967297}
        server_data.all_traders[1] = trader
        server_data.trader_counter = 1
        server_data.all_empires[1].mt_components = ["Mega Poly Shell"]
        manager._save_game_state(game_id, server_data)

        # Force a reload from the persisted dict
        manager._game_cache.clear()
        reloaded = manager._load_game_state(game_id)
        r = reloaded.all_traders[1]
        assert r.gifts == {1: {"total": 700, "fleet_key": 4294967297}}
        assert reloaded.trader_counter == 1
        assert reloaded.all_empires[1].mt_components == \
            ["Mega Poly Shell"]
