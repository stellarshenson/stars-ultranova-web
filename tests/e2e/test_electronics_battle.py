"""
Seeded e2e: electronics in battle - jammers, computers, capacitors,
beam deflectors (canonical Stars! rules; the C# consumption is a stub,
BattleEngine.cs:880-929).

Two comparison pairs, each two otherwise-identical seeded games that
differ ONLY in which registered design the spawned fleet references:
- Torpedo pairing: a computer-fitted torpedo destroyer pounds an
  unarmed armored target for one full battle; with 2x Jammer 20
  fitted (36% stacked) the target takes exactly 0.64x the torpedo
  damage - the seeded RNG rolls align between the games because every
  design is registered in both and the fleets fly the same geometry.
- Beam pairing: a laser destroyer with 2x Energy Capacitor (21%
  stacked) out-damages the identical ship without them against the
  same deflector-fitted target (10%); beams have no accuracy roll so
  the first damage step equals power * quantity * (1 + cap/100) *
  (1 - defl/100) exactly.

Fleets are placed by state surgery at a deep-space point with empire
2's target parked (established harness pattern, test_battle_plans.py);
unknown empires default to Enemy so contact = battle. Tech is granted
by state surgery so the designs validate (pattern from
test_wave3_integration.py).
"""

import pytest

SEED = 20260714

RESEARCH_FIELDS = ("Biotechnology", "Electronics", "Energy",
                   "Propulsion", "Weapons", "Construction")

# Destroyer cells: 2/22 Weapon, 6 Mechanical, 10 Engine, 11 Armor(2),
# 12 General Purpose, 16 Electrical
DESIGNS = {
    1: [
        ("Torp Comp", [  # 2x Battle Computer -> 36% stacked accuracy
            {"cell_number": 2, "component": "Beta Torpedo", "count": 1},
            {"cell_number": 22, "component": "Beta Torpedo", "count": 1},
            {"cell_number": 10, "component": "Alpha Drive 8", "count": 1},
            {"cell_number": 16, "component": "Battle Computer", "count": 1},
            {"cell_number": 12, "component": "Battle Computer", "count": 1},
        ]),
        ("Beam Plain", [
            {"cell_number": 2, "component": "Laser", "count": 1},
            {"cell_number": 22, "component": "Laser", "count": 1},
            {"cell_number": 10, "component": "Alpha Drive 8", "count": 1},
        ]),
        ("Beam Cap", [  # 2x Energy Capacitor -> 21% stacked
            {"cell_number": 2, "component": "Laser", "count": 1},
            {"cell_number": 22, "component": "Laser", "count": 1},
            {"cell_number": 10, "component": "Alpha Drive 8", "count": 1},
            {"cell_number": 16, "component": "Energy Capacitor",
             "count": 1},
            {"cell_number": 12, "component": "Energy Capacitor",
             "count": 1},
        ]),
    ],
    2: [
        ("Target Plain", [  # unarmed, 200 hull + 150 armor
            {"cell_number": 10, "component": "Quick Jump 5", "count": 1},
            {"cell_number": 11, "component": "Crobmnium", "count": 2},
        ]),
        ("Target Jam", [  # 2x Jammer 20 -> 36% stacked jamming
            {"cell_number": 10, "component": "Quick Jump 5", "count": 1},
            {"cell_number": 11, "component": "Crobmnium", "count": 2},
            {"cell_number": 16, "component": "Jammer 20", "count": 1},
            {"cell_number": 12, "component": "Jammer 20", "count": 1},
        ]),
        ("Target Defl", [  # Beam Deflector -> beam damage x 0.9
            {"cell_number": 10, "component": "Quick Jump 5", "count": 1},
            {"cell_number": 11, "component": "Crobmnium", "count": 2},
            {"cell_number": 6, "component": "Beam Deflector", "count": 1},
        ]),
    ],
}


def _grant_tech(harness, level=12):
    """Set every research field of both empires by state surgery so
    the electronics designs validate (Jammer 20 needs Electronics 10)."""
    from backend.services.game_manager import get_game_manager

    manager = get_game_manager()
    server_data = manager._load_game_state(harness.game_id)
    for empire in server_data.all_empires.values():
        for tech_field in RESEARCH_FIELDS:
            empire.research_levels.levels[tech_field] = level
    manager._save_game_state(harness.game_id, server_data)


def _spawn_fleet(harness, empire_id, design_name, name, x, y,
                 parked=False):
    """Create a one-ship fleet at (x, y) by state surgery (pattern
    from test_battle_plans.py); returns its key."""
    from backend.core.data_structures import NovaPoint
    from backend.core.game_objects import Fleet
    from backend.core.waypoints.waypoint import (
        Waypoint, LayMinesTaskObj, NoTaskObj)
    from backend.services.game_manager import get_game_manager
    from backend.services.ship_specs import find_design, make_token

    manager = get_game_manager()
    server_data = manager._load_game_state(harness.game_id)
    empire = server_data.all_empires[empire_id]
    design = find_design(empire, design_name)
    assert design is not None, f"no design '{design_name}'"

    fleet = Fleet()
    fleet.key = empire.get_next_fleet_key()
    fleet.name = name
    fleet.turn_year = empire.turn_year
    fleet.position = NovaPoint(x, y)
    fleet.battle_plan = "Default"
    token = make_token(design, 1)
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
    manager._save_game_state(harness.game_id, server_data)
    return fleet.key


def _deep_space_point(harness):
    """Fractional-coordinate point midway between the homeworlds."""
    home1 = harness.my_stars(1)[0]
    home2 = harness.my_stars(2)[0]
    return ((home1["position_x"] + home2["position_x"]) / 2 + 0.5,
            (home1["position_y"] + home2["position_y"]) / 2 + 0.5)


def _run_battle(harness, attacker_design, target_design):
    """One seeded game, one deep-space battle: returns the Weapons
    steps of the battle at the rendezvous. ALL designs are registered
    in every game so AI behavior and RNG consumption stay identical
    between paired runs - only the spawned fleets' design references
    differ."""
    harness.create_game(seed=SEED, size="tiny", players=2)
    _grant_tech(harness)

    for empire_id, designs in DESIGNS.items():
        for design_name, slots in designs:
            result = harness.submit(empire_id, "design", {
                "mode": "Add",
                "design": {"name": design_name, "hull": "Destroyer",
                           "slots": slots},
            })
            assert result["status"] == "applied", result

    px, py = _deep_space_point(harness)
    _spawn_fleet(harness, 1, attacker_design, "Attacker", px, py)
    _spawn_fleet(harness, 2, target_design, "Target", px, py,
                 parked=True)

    harness.generate_turn()

    reports = harness._request(
        "GET", f"/api/games/{harness.game_id}/empires/2/battles")
    assert reports, "no battle report for empire 2"
    location = f"deep space ({int(px)}, {int(py)})"
    report = next(r for r in reports if r["location"] == location)

    # Weapons fire from the empire-1 attacker into the empire-2 target
    steps = [s for s in report["steps"]
             if s["type"] == "Weapons"
             and (s["weapon_target"]["stack_key"] >> 32) == 1
             and (s["weapon_target"]["target_key"] >> 32) == 2]
    assert steps, "attacker never fired"
    destroyed = any(s["type"] == "Destroy" for s in report["steps"])
    return steps, destroyed


class TestElectronicsBattle:

    def test_jammed_target_takes_fewer_torpedo_hits(self, harness):
        """Same seed, same rolls: the 36%-jammed target takes exactly
        0.64x the torpedo damage of the plain target (each Ron-engine
        shot lands hit_power * percent_hit on armor, and percent_hit
        scales linearly with the jam factor - no clamping because the
        computer-boosted base of 64.8% caps at 81% on the widest
        roll)."""
        plain_steps, plain_destroyed = _run_battle(
            harness, "Torp Comp", "Target Plain")
        jam_steps, jam_destroyed = _run_battle(
            harness, "Torp Comp", "Target Jam")

        # Beta Torpedoes cannot chew 350 armor within one battle:
        # the totals compare complete, equal-length engagements
        assert not plain_destroyed and not jam_destroyed

        plain_total = sum(s["damage"] for s in plain_steps)
        jam_total = sum(s["damage"] for s in jam_steps)
        assert jam_total < plain_total, "jammers did not reduce hits"
        # 2x Jammer 20 stack to 36% -> hit chance x 0.64 per shot
        assert jam_total == pytest.approx(0.64 * plain_total, rel=0.01)

    def test_capacitor_ship_out_damages_plain_ship(self, harness):
        """Beams are deterministic: every hit on the deflector-fitted
        target lands power * quantity * (1 + cap/100) * 0.9 * range
        dissipation, so the capacitor ship's first shot is exactly
        1.21x the plain ship's and it destroys the target in fewer
        shots."""
        plain_steps, plain_destroyed = _run_battle(
            harness, "Beam Plain", "Target Defl")
        cap_steps, cap_destroyed = _run_battle(
            harness, "Beam Cap", "Target Defl")

        # Beam range dissipation: the closing move leaves the stacks
        # 0.8 of the Laser's range apart on the first exchange, so
        # every hit keeps 100 - 10 * 0.8^2 = 93.6 percent of its power
        dissipation = 0.936
        # Laser power 10, quantity 1, deflector 10% -> 9.0 per hit;
        # with 2x Energy Capacitor (21% stacked) -> 10.89
        assert plain_steps[0]["damage"] == pytest.approx(
            10 * 0.9 * dissipation)
        assert cap_steps[0]["damage"] == pytest.approx(
            10 * 1.21 * 0.9 * dissipation)

        # The boosted beams kill the same target with fewer shots
        assert plain_destroyed and cap_destroyed
        assert len(cap_steps) < len(plain_steps)
