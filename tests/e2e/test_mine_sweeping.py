"""
Seeded e2e: mine sweeping and SD minefield detonation.

An SD race flies its Little Hen mine layer next to the enemy homeworld
and lays a standard minefield; the enemy's beam-armed Armed Probe parks
inside the field and sweeps it away over several turns (canonical rate
power x range^2 per beam). In the detonation scenario the SD player
flags the field to detonate, destroying every fleet inside - the enemy
victim and the SD player's own mine layer alike.

Both mechanics are absent from the C# reference; the port follows
canonical Stars! rules (SD trait text: PrimaryTraits.cs:58).

Empire 2 is AI-driven. Its fleets are kept under test control with a
parking waypoint stack: waypoint 0 carries a LayMines task (a no-op
for fleets without mine layers) that never gets popped, so the fleet
stays parked, plus a dummy trailing waypoint so DefaultAI's
"len(waypoints) > 1" idle check always skips the fleet.
"""

import math

SEED = 20260713

# SD wizard race; colonistsPerResource 1500 keeps the race inside the
# advantage-point budget (same headroom trick as the other e2e races)
SD_RACE = {
    "name": "Demolition",
    "pluralName": "Demolitions",
    "prt": "SD",
    "lrts": [],
    "factoryCost": 10,
    "factoryEfficiency": 10,
    "factoryNumberPer10k": 10,
    "mineCost": 5,
    "mineEfficiency": 10,
    "mineNumberPer10k": 10,
    "colonistsPerResource": 1500,
    "gravityMin": 15, "gravityMax": 85,
    "temperatureMin": 15, "temperatureMax": 85,
    "radiationMin": 15, "radiationMax": 85,
    "growthRate": 15,
    "startAtLevel3": False,
}


def _fleet_named(harness, prefix, empire_id):
    for fleet in harness.my_fleets(empire_id):
        if fleet["name"].startswith(prefix):
            return fleet
    return None


def _wp(x, y, warp, task, dest="wp"):
    return {"position_x": x, "position_y": y, "warp_factor": warp,
            "destination": dest, "task": {"type": task}}


def _add_waypoints(harness, empire_id, fleet_key, waypoints):
    for i, waypoint in enumerate(waypoints):
        result = harness.submit(empire_id, "waypoint", {
            "mode": "Add", "fleet_key": fleet_key, "index": i,
            "waypoint": waypoint})
        assert result["status"] == "applied", result


def _field_at(minefields, x, y, mine_type=0):
    """The minefield of the given type laid at (x, y), or None."""
    for field in minefields:
        if field["mine_type"] == mine_type and \
                math.hypot(field["x"] - x, field["y"] - y) < 5:
            return field
    return None


def _setup_game(harness):
    """SD player 1 vs AI player 2; returns homes and the mine site P
    (30 ly from the enemy homeworld, toward home 1)."""
    harness.create_game(seed=SEED, size="tiny", players=2, race=SD_RACE)
    home1 = harness.my_stars(1)[0]
    home2 = harness.my_stars(2)[0]
    dist = math.hypot(home1["position_x"] - home2["position_x"],
                      home1["position_y"] - home2["position_y"])
    ux = (home1["position_x"] - home2["position_x"]) / dist
    uy = (home1["position_y"] - home2["position_y"]) / dist
    px = home2["position_x"] + 30 * ux
    py = home2["position_y"] + 30 * uy
    return home1, home2, (px, py), (ux, uy)


def _dispatch_mine_layer(harness, px, py):
    """Send the Little Hen to P; laying starts once parked there (the
    NoTask leg first, so nothing is laid at home on departure)."""
    hen = _fleet_named(harness, "Little Hen", 1)
    assert hen is not None
    _add_waypoints(harness, 1, hen["key"], [
        _wp(px, py, 5, "NoTask", "Mine Site"),
        _wp(px, py, 5, "LayMines", "Mine Site"),
    ])


class TestMineSweeping:

    def test_beam_fleet_sweeps_hostile_field(self, harness):
        home1, home2, (px, py), (ux, uy) = _setup_game(harness)
        _dispatch_mine_layer(harness, px, py)

        # Enemy Armed Probe (1 beam, power 16, range 1 -> sweeps
        # 16/yr) parks 3 ly from the field center, inside the field
        ox, oy = px - 3 * ux, py - 3 * uy
        probe = _fleet_named(harness, "Armed Probe", 2)
        assert probe is not None
        _add_waypoints(harness, 2, probe["key"], [
            _wp(ox, oy, 4, "NoTask", "Picket"),
            _wp(ox, oy, 4, "LayMines", "Picket"),
            _wp(home2["position_x"], home2["position_y"], 4, "NoTask",
                "dummy"),
        ])

        # Fly out and lay for three years; the parked probe sweeps
        # 16/yr off the growing field from the first lay year on
        lay_years = 0
        saw_sweep_messages = False
        for _ in range(20):
            result = harness.generate_turn()
            sweeps = [m for m in result["messages"]
                      if m["type"] == "Minefield Swept"]
            if any(m["audience"] == 1 for m in sweeps) and \
                    any(m["audience"] == 2 for m in sweeps):
                saw_sweep_messages = True
            field = _field_at(harness.state(1)["minefields"], px, py)
            hen = _fleet_named(harness, "Little Hen", 1)
            if field and math.hypot(hen["position_x"] - px,
                                    hen["position_y"] - py) < 1:
                lay_years += 1
            if lay_years >= 3:
                break
        assert lay_years >= 3, "minefield never reached 3 lay years"
        assert saw_sweep_messages, "no sweep messages for both owners"

        # Stop laying: the hen heads back toward home
        hen = _fleet_named(harness, "Little Hen", 1)
        result = harness.submit(1, "waypoint", {
            "mode": "Edit", "fleet_key": hen["key"], "index": 0,
            "waypoint": _wp(px + 60 * ux, py + 60 * uy, 5, "NoTask",
                            "back")})
        assert result["status"] == "applied"

        # The probe now sweeps the decaying field away over several
        # turns: radius shrinks every year until the field is deleted
        radii = []
        for _ in range(12):
            result = harness.generate_turn()
            sweeps = [m for m in result["messages"]
                      if m["type"] == "Minefield Swept"]
            field1 = _field_at(harness.state(1)["minefields"], px, py)
            field2 = _field_at(harness.state(2)["minefields"], px, py)
            if field1 is not None:
                assert sweeps, "field present but no sweep message"
                assert field2 is not None
                assert field2["radius"] == field1["radius"]
                radii.append(field1["radius"])
            else:
                # Swept away: gone from both players' views
                assert field2 is None
                break
        else:
            raise AssertionError("field was never swept away")

        assert len(radii) >= 2, "expected several sweeping turns"
        assert all(radii[i] > radii[i + 1] for i in range(len(radii) - 1)), \
            f"radius did not shrink turn over turn: {radii}"


class TestDetonation:

    def _run_detonation(self, harness):
        """Lay a field near the enemy home, park an enemy victim
        inside, detonate. Returns the post-detonation turn result."""
        home1, home2, (px, py), (ux, uy) = _setup_game(harness)
        _dispatch_mine_layer(harness, px, py)

        # Enemy Spore Cloud (unarmed - sweeps nothing) parks 3 ly
        # from the field center; free at warp 5
        vx, vy = px - 3 * ux, py - 3 * uy
        spore = _fleet_named(harness, "Spore Cloud #1", 2)
        assert spore is not None
        _add_waypoints(harness, 2, spore["key"], [
            _wp(vx, vy, 5, "NoTask", "Park"),
            _wp(vx, vy, 5, "LayMines", "Park"),
            _wp(home2["position_x"], home2["position_y"], 5, "NoTask",
                "dummy"),
        ])

        # The Speed Turtle lays a speed-bump field at home 1: the
        # non-standard-field rejection target
        turtle = _fleet_named(harness, "Speed Turtle", 1)
        _add_waypoints(harness, 1, turtle["key"], [
            _wp(turtle["position_x"], turtle["position_y"], 0,
                "LayMines", "Home field"),
        ])

        # Wait until the standard field covers the parked victim
        field = None
        for _ in range(20):
            harness.generate_turn()
            field = _field_at(harness.state(1)["minefields"], px, py)
            spore = _fleet_named(harness, "Spore Cloud #1", 2)
            if field and field["radius"] > 4 and \
                    math.hypot(spore["position_x"] - vx,
                               spore["position_y"] - vy) < 0.5:
                break
        assert field is not None, "standard minefield never laid"

        bump = _field_at(harness.state(1)["minefields"],
                         home1["position_x"], home1["position_y"],
                         mine_type=2)
        assert bump is not None, "speed-bump field never laid"

        # Command validation: wrong owner, unknown key, wrong type
        result = harness.submit(2, "detonate_minefield",
                                {"key": field["key"], "detonate": True})
        assert result["error"] == "Not your minefield"
        result = harness.submit(1, "detonate_minefield",
                                {"key": 12345, "detonate": True})
        assert result["error"] == "Minefield not found"
        result = harness.submit(1, "detonate_minefield",
                                {"key": bump["key"], "detonate": True})
        assert "standard minefields" in result["error"]

        # Valid toggle: SD race, own standard field
        result = harness.submit(1, "detonate_minefield",
                                {"key": field["key"], "detonate": True})
        assert result["status"] == "applied"

        # The flag is owner-only intel
        field1 = _field_at(harness.state(1)["minefields"], px, py)
        field2 = _field_at(harness.state(2)["minefields"], px, py)
        assert field1["detonate"] is True
        assert field2["detonate"] is False

        return harness.generate_turn(), (px, py)

    def test_sd_detonation_damages_fleets_inside(self, harness):
        result, (px, py) = self._run_detonation(harness)

        detonations = [m for m in result["messages"]
                       if m["type"] == "Minefield Detonation"]
        # Victim's owner is told, and the SD player pays for its own
        # mine layer sitting in the field (friend and foe alike)
        assert any(m["audience"] == 2 and "Spore Cloud" in m["text"]
                   and "destroyed" in m["text"] for m in detonations)
        assert any(m["audience"] == 1 and "Little Hen" in m["text"]
                   and "destroyed" in m["text"] for m in detonations)
        assert any(m["audience"] == 1 and "Enemy fleets" in m["text"]
                   for m in detonations)

        # Both fleets inside the field were destroyed
        assert _fleet_named(harness, "Spore Cloud #1", 2) is None
        assert _fleet_named(harness, "Little Hen", 1) is None

        # The field survives the blast and keeps detonating yearly
        field1 = _field_at(harness.state(1)["minefields"], px, py)
        assert field1 is not None
        assert field1["detonate"] is True

    def test_detonation_is_deterministic(self, harness):
        """Same seed + same commands -> identical state digests."""
        digests = []
        for _ in range(2):
            result, _ = self._run_detonation(harness)
            digests.append(result["digests"])
        assert digests[0] == digests[1]
