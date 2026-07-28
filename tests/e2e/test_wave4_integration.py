"""
Wave-4 cross-feature integration: one seeded game combining the five
wave-4 gap families end to end.

A two-player tiny game created with a configured victory condition
(planets_owned 1%, minimum game time 4 - the GameSettings.cs payload
shape from test_score_victory.py) plays five phases:

- relations: both empires stand at Neutral while an empire-1 raider
  pair shares a deep-space point with an empire-2 convoy - the
  encounter passes without battle (BattleEngine.cs:468-494 attack-who
  under the Ron engine);
- relations flip mid-game: both sides declare Enemy and the same
  encounter now fights;
- battle plans in that battle: the convoy freighter rides a
  "Disengage" plan and flees the board alive while the armed escort
  (Escort tier, priority above the freighter's Any Ship tier) soaks
  every raider volley - plan target tiers and tactic both observable
  in the battle report;
- electronics in that battle: the raiders carry 2x Energy Capacitor
  (21% stacked) and the escort a Beam Deflector (10%), so the first
  recorded beam hit is exactly power x quantity x 1.21 x 0.9
  (canonical Stars! rules; the C# consumption is a stub,
  BattleEngine.cs:880-929);
- storm protection: a Storm Bulwark fleet (storm-shield component
  line, total immunity) crosses a stationary intensity-1.0 blob storm
  unharmed at warp 5 while an identical unshielded fleet takes the
  full locally-scaled hull damage (user directive, wave 4);
- score + victory: the game ends by the configured victory condition
  at the first turn past the minimum game time, with a public Victory
  announcement and a per-turn score history consistent with the live
  public score records.

Fleets and the storm are placed by state surgery (the established
harness pattern, see test_battle_plans.py and test_storms.py); tech is
granted by state surgery so the designs validate (pattern from
test_wave3_integration.py). Every roll rides the per-turn seeded RNG,
so the recorded outcome is reproducible for the fixed seed.
"""

import math
import random

import pytest

SEED = 20260714
UNIVERSE = 200            # "tiny" universe (galaxy_generator SIZES)
MIN_GAME_TIME = 4         # victory gate: declared on generated turn 5

RESEARCH_FIELDS = ("Biotechnology", "Electronics", "Energy",
                   "Propulsion", "Weapons", "Construction")

# Destroyer cells: 2/22 Weapon, 6 Mechanical, 10 Engine, 11 Armor(2),
# 12 General Purpose, 16 Electrical
DESIGNS = {
    1: [
        ("Raider", [  # 2x Energy Capacitor -> 21% stacked beam boost
            {"cell_number": 2, "component": "Laser", "count": 1},
            {"cell_number": 22, "component": "Laser", "count": 1},
            {"cell_number": 10, "component": "Alpha Drive 8", "count": 1},
            {"cell_number": 16, "component": "Energy Capacitor",
             "count": 1},
            {"cell_number": 12, "component": "Energy Capacitor",
             "count": 1},
        ]),
        ("Storm Runner", [  # Storm Bulwark: storm protection 1.0
            {"cell_number": 10, "component": "Alpha Drive 8", "count": 1},
            {"cell_number": 12, "component": "Storm Bulwark", "count": 1},
        ]),
        ("Storm Mule", [  # bare hull: storm protection 0.0
            {"cell_number": 10, "component": "Alpha Drive 8", "count": 1},
        ]),
    ],
    2: [
        ("Picket", [  # armed + Beam Deflector -> incoming beams x 0.9
            {"cell_number": 2, "component": "Laser", "count": 1},
            {"cell_number": 10, "component": "Quick Jump 5", "count": 1},
            {"cell_number": 11, "component": "Crobmnium", "count": 2},
            {"cell_number": 6, "component": "Beam Deflector", "count": 1},
        ]),
    ],
}


def _manager():
    from backend.services.game_manager import get_game_manager
    return get_game_manager()


def _load(harness):
    return _manager()._load_game_state(harness.game_id)


def _save(harness, server_data):
    _manager()._save_game_state(harness.game_id, server_data)


def _grant_tech(harness, level=18):
    """Set every research field of both empires by state surgery so
    the designs validate (Storm Bulwark needs Energy/Propulsion 18)."""
    server_data = _load(harness)
    for empire in server_data.all_empires.values():
        for tech_field in RESEARCH_FIELDS:
            empire.research_levels.levels[tech_field] = level
    _save(harness, server_data)


def _spawn_fleet(harness, empire_id, design_name, name, x, y,
                 quantity=1, battle_plan="Default", parked=False):
    """Create a fleet at (x, y) by state surgery (pattern from
    test_battle_plans.py); returns its key."""
    from backend.core.data_structures import NovaPoint
    from backend.core.game_objects import Fleet
    from backend.core.waypoints.waypoint import (
        Waypoint, LayMinesTaskObj, NoTaskObj)
    from backend.services.ship_specs import find_design, make_token

    server_data = _load(harness)
    empire = server_data.all_empires[empire_id]
    design = find_design(empire, design_name)
    assert design is not None, f"no design '{design_name}'"

    fleet = Fleet()
    fleet.key = empire.get_next_fleet_key()
    fleet.name = name
    fleet.turn_year = empire.turn_year
    fleet.position = NovaPoint(x, y)
    fleet.battle_plan = battle_plan
    token = make_token(design, quantity)
    fleet.tokens[token.design_key] = token
    fleet.fuel_available = fleet.total_fuel_capacity
    if parked:
        # AI-held fleets: >1 waypoints keeps DefaultAI hands off (the
        # parking stack pattern from test_relations.py)
        fleet.waypoints = [
            Waypoint(position_x=x, position_y=y, warp_factor=4,
                     destination="park", task=LayMinesTaskObj()),
            Waypoint(position_x=x, position_y=y, warp_factor=4,
                     destination="park", task=NoTaskObj()),
        ]
    empire.owned_fleets[fleet.key] = fleet
    _save(harness, server_data)
    return fleet.key


def _fleet_named(harness, name, empire_id):
    for fleet in harness.my_fleets(empire_id):
        if fleet["name"] == name:
            return fleet
    return None


def _relation_toward(harness, empire_id, other_id):
    for entry in harness.state(empire_id)["relations"]:
        if entry["id"] == other_id:
            return entry
    return None


def _deep_space_point(harness):
    """Fractional-coordinate point midway between the homeworlds."""
    home1 = harness.my_stars(1)[0]
    home2 = harness.my_stars(2)[0]
    return ((home1["position_x"] + home2["position_x"]) / 2 + 0.5,
            (home1["position_y"] + home2["position_y"]) / 2 + 0.5)


def _clear_space(harness, avoid=(), avoid_by=45):
    """Grid-search the point with the most clearance from every star
    (and every `avoid` point), in-bounds with room for a -x approach
    run (tiny-universe variant of test_wave3_integration.py)."""
    server_data = _load(harness)
    stars = list(server_data.all_stars.values())
    best = None
    for gx in range(40, UNIVERSE - 10, 10):
        for gy in range(10, UNIVERSE - 10, 10):
            if any(math.hypot(gx - ax, gy - ay) < avoid_by
                   for ax, ay in avoid):
                continue
            clearance = min(math.hypot(gx - s.position.x,
                                       gy - s.position.y) for s in stars)
            if best is None or clearance > best[0]:
                best = (clearance, gx, gy)
    assert best is not None, "no clear space for this seed"
    return best[1], best[2]


def _send_to(harness, fleet_key, x, y, warp):
    harness.submit(1, "waypoint", {
        "mode": "Add",
        "fleet_key": fleet_key,
        "index": 0,
        "waypoint": {
            "position_x": x,
            "position_y": y,
            "warp_factor": warp,
            "destination": "storm run",
            "task": {"type": "NoTask"},
        },
    })


def _storm_messages(state, name):
    return [m for m in state["messages"]
            if m.get("type") == "Storm" and name in m.get("text", "")]


class TestWave4Integration:

    def test_cross_feature_seeded_game(self, harness):
        harness.create_game(seed=SEED, size="tiny", players=2, victory={
            "planets_owned": {"enabled": True, "value": 1},
            "targets_to_meet": 1,
            "minimum_game_time": MIN_GAME_TIME,
        })

        # The configured victory condition is echoed in the status
        status = harness.state(1)["victory_status"]
        assert status["minimum_game_time"] == MIN_GAME_TIME
        assert status["targets"]["planets_owned"]["value"] == 1

        # No wandering storms: they would pollute the battle phases
        # (storm placement is phase 4's surgery)
        server_data = _load(harness)
        server_data.all_storms = {}
        _save(harness, server_data)

        _grant_tech(harness)
        for empire_id, designs in DESIGNS.items():
            for design_name, slots in designs:
                result = harness.submit(empire_id, "design", {
                    "mode": "Add",
                    "design": {"name": design_name, "hull": "Destroyer",
                               "slots": slots},
                })
                assert result["status"] == "applied", result

        # The convoy freighter rides a Disengage plan (wave-4 battle
        # plans: tactic honored by the Ron engine)
        result = harness.submit(2, "battle_plan", {"mode": "set", "plan": {
            "name": "Runner", "tactic": "Disengage", "attack": "Enemies"}})
        assert result["status"] == "applied"

        # -- Phase 1: Neutral relations - contact without battle -------
        # Turn-0 default is mutual Enemy (GameInitialiser.cs:132-143);
        # both sides stand down before the fleets meet
        assert _relation_toward(harness, 1, 2)["relation"] == "Enemy"
        for empire_id, other_id in ((1, 2), (2, 1)):
            result = harness.submit(empire_id, "relation", {
                "target_empire_id": other_id, "relation": "Neutral"})
            assert result["status"] == "applied"

        px, py = _deep_space_point(harness)
        _spawn_fleet(harness, 1, "Raider", "Raider", px, py, quantity=2)
        _spawn_fleet(harness, 2, "Picket", "Picket", px, py, parked=True)
        _spawn_fleet(harness, 2, "Swashbuckler", "Convoy", px, py,
                     battle_plan="Runner", parked=True)

        result = harness.generate_turn()
        assert not any(m["type"] == "Battle" for m in result["messages"]), \
            "neutral contact must not battle"
        for name, empire_id in (("Raider", 1), ("Picket", 2),
                                ("Convoy", 2)):
            assert _fleet_named(harness, name, empire_id) is not None, \
                f"{name} lost without a battle"
        assert harness.state(1)["victor"] is None

        # -- Phase 2: relations flip to Enemy - the encounter fights ---
        for empire_id, other_id in ((1, 2), (2, 1)):
            result = harness.submit(empire_id, "relation", {
                "target_empire_id": other_id, "relation": "Enemy"})
            assert result["status"] == "applied"

        result = harness.generate_turn()
        battles = [m for m in result["messages"] if m["type"] == "Battle"]
        assert any(m["audience"] == 1 for m in battles)
        assert any(m["audience"] == 2 for m in battles)
        assert any("deep space" in m["text"] for m in battles)

        reports = harness._request(
            "GET", f"/api/games/{harness.game_id}/empires/2/battles")
        assert reports, "no battle report for empire 2"
        location = f"deep space ({int(px)}, {int(py)})"
        report = next(r for r in reports if r["location"] == location)
        steps = report["steps"]

        # Electronics: the first raider beam hit lands exactly
        # power(10) x quantity(2) x 1.21 (2x Energy Capacitor stacked)
        # x 0.9 (Beam Deflector) on the escort x 0.99216 (beam range
        # dissipation - the first exchange happens 0.28 of the way out
        # to the weapon's maximum range, where a beam keeps
        # 100 - 10 * 0.28^2 percent of its power)
        # - beams have no accuracy roll, so the value is deterministic
        # once the approach is. That approach used to end at maximum
        # range for this seed; it ends closer in now that movement
        # resolves heaviest-first with a 15 percent juggle instead of
        # in the order empires occupy in the stack list
        # (RonBattleEngine._move_order, BattleEngine.cs:524). The
        # electronics arithmetic this row is asserting - capacitor
        # x deflector - is unchanged; only the range they met at moved
        raider_fire = [s for s in steps
                       if s["type"] == "Weapons"
                       and (s["weapon_target"]["stack_key"] >> 32) == 1
                       and (s["weapon_target"]["target_key"] >> 32) == 2]
        assert raider_fire, "raiders never fired"
        assert raider_fire[0]["damage"] == pytest.approx(
            10 * 2 * 1.21 * 0.9 * 0.99216)

        # Battle plans: the Escort tier outranks the freighter's Any
        # Ship tier in the Default plan, so every raider volley up to
        # the kill lands on one stack - the Picket
        destroy_index = next(i for i, s in enumerate(steps)
                             if s["type"] == "Destroy")
        picket_key = {s["weapon_target"]["target_key"]
                      for s in raider_fire[:1]}.pop()
        for step in steps[:destroy_index]:
            if step["type"] == "Weapons" \
                    and (step["weapon_target"]["stack_key"] >> 32) == 1:
                assert step["weapon_target"]["target_key"] == picket_key

        # The escort fought back (armed, Default plan) and died for it;
        # the disengaging freighter fled the board and survived
        assert any(s["type"] == "Weapons"
                   and (s["weapon_target"]["stack_key"] >> 32) == 2
                   for s in steps), "escort never fired"
        assert _fleet_named(harness, "Picket", 2) is None, \
            "escort survived the raider volleys"
        assert _fleet_named(harness, "Convoy", 2) is not None, \
            "disengaging freighter was destroyed"
        assert _fleet_named(harness, "Raider", 1) is not None

        # -- Phase 3: storm-shielded fleet crosses a storm unharmed ----
        # A stationary intensity-1.0 blob storm in clear space; both
        # fleets fly the identical leg to the core at warp 5 (below
        # STORM_SAFE_WARP - no mishap randomness)
        from backend.server.server_data import GalacticStorm

        cx, cy = _clear_space(harness, avoid=((px, py),))
        server_data = _load(harness)
        storm = GalacticStorm(key=1, x=cx, y=cy, radius=24,
                              velocity_x=0, velocity_y=0, intensity=1.0)
        storm.generate_shape(random.Random(4242))
        server_data.all_storms = {1: storm}
        _save(harness, server_data)

        runner = _spawn_fleet(harness, 1, "Storm Runner", "Shielded Run",
                              cx - 30, cy)
        mule = _spawn_fleet(harness, 1, "Storm Mule", "Naked Run",
                            cx - 30, cy)
        _send_to(harness, runner, cx, cy, warp=5)
        _send_to(harness, mule, cx, cy, warp=5)

        # The fleet API exposes the component-line protection (wave 4)
        by_key = {f["key"]: f for f in harness.my_fleets(1)}
        assert by_key[runner]["storm_protection"] == pytest.approx(1.0)
        assert by_key[mule]["storm_protection"] == pytest.approx(0.0)

        harness.generate_turn()

        # Both fleets end at the same deep-space spot inside the blob
        server_data = _load(harness)
        fleets = server_data.all_empires[1].owned_fleets
        positions = {(fleets[k].position.x, fleets[k].position.y)
                     for k in (runner, mule)}
        assert len(positions) == 1, "storm fleets diverged"
        end_pos = positions.pop()
        assert server_data.get_star_at_position(*end_pos) is None, \
            "storm leg ended in orbit - safe harbor would mask the test"
        local = server_data.all_storms[1].get_intensity_at(*end_pos)
        assert local > 0.0, "storm fleets did not end inside the storm"

        def damage(key):
            fleet = fleets[key]
            return fleet.tokens[next(iter(fleet.tokens))].damage_percent

        # The Storm Bulwark fleet is untouched; the identical bare
        # fleet takes the full locally-scaled hit
        assert damage(runner) == 0.0
        assert damage(mule) == pytest.approx(20 * local)
        state = harness.state(1)
        assert _storm_messages(state, "Naked Run")
        assert not _storm_messages(state, "Shielded Run")

        # -- Phase 4: configured victory past the minimum game time ----
        # The check runs before the year increment: at generated turn N
        # the game_time seen is N-1, so turn 4 stays gated and turn 5
        # (game_time 4 >= 4) declares the first empire meeting the 1%
        # planets target - empire 1, first in iteration order
        result = harness.generate_turn()
        assert harness.state(1)["victor"] is None

        result = harness.generate_turn()
        state = harness.state(1)
        assert state["victor"] == 1
        assert any(m["type"] == "Victory" and "have won the game"
                   in m["text"] for m in result["messages"])
        # The loser sees the same public announcement
        assert any("have won the game" in m["text"]
                   for m in harness.state(2)["messages"])

        # Score history: one entry per empire per generated turn,
        # stamped with the post-increment year, the latest entry
        # matching the live public record
        final_year = result["turn"]
        assert sorted(r["rank"] for r in state["scores"]) == [1, 2]
        for record in state["scores"]:
            entries = state["score_history"][str(record["empire_id"])]
            assert len(entries) == 5
            assert [e["year"] for e in entries] == list(
                range(final_year - 4, final_year + 1))
            assert entries[-1]["score"] == record["score"]
        # Scores are public: both empires see identical records
        assert harness.state(2)["scores"] == state["scores"]
