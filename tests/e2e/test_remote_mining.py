"""
Seeded e2e: remote mining full cycle.

An ARM race designs a Midget Miner ("Rock Chewer", 2x Robo-Midget
Miner = 10 kT/mineral/year at 100% concentration), builds it on the
homeworld, parks it at a nearby uninhabited world with a Remote Mine
waypoint task, and mines for several years. A Teamster freighter
follows and loads the ore off the uninhabited surface - proof the
minerals accumulated there. Remote mining is a stub in the C#
reference; the step follows canonical Stars! rules.
"""

SEED = 20260713
MINING_TURNS = 4

# JOAT + ARM wizard race; colonistsPerResource 1500 keeps the race
# inside the advantage-point budget (default 1000 is 23 points over)
MINER_RACE = {
    "name": "Miners",
    "pluralName": "Miners",
    "prt": "JOAT",
    "lrts": ["ARM"],
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

MINERALS = ("ironium", "boranium", "germanium")


def _fleet_named(harness, prefix, empire_id=1):
    for fleet in harness.my_fleets(empire_id):
        if fleet["name"].startswith(prefix):
            return fleet
    return None


def _target_star(harness, home):
    """Nearest foreign star to the homeworld. Canonical planetary
    scanners (Viewer/Scoper, pen 0) deep-scan nothing at a distance,
    so the target is picked by position alone and its concentrations
    are revealed by the miner scanning from orbit on arrival."""
    candidates = [
        s for s in harness.state(1)["stars"]
        if s.get("intel") != "owned"
    ]
    assert candidates, "no foreign star near home"
    return min(candidates, key=lambda s: (
        (s["position_x"] - home["position_x"]) ** 2
        + (s["position_y"] - home["position_y"]) ** 2))


def _add_waypoint(harness, fleet, star, warp, task):
    harness.submit(1, "waypoint", {
        "mode": "Add",
        "fleet_key": fleet["key"],
        "index": len(fleet.get("waypoints", [])),
        "waypoint": {
            "position_x": star["position_x"],
            "position_y": star["position_y"],
            "warp_factor": warp,
            "destination": star["name"],
            "task": {"type": task},
        },
    })


def _run_scenario(harness):
    """Drive the full mining cycle; returns (harness state artifacts)."""
    harness.create_game(seed=SEED, size="small", players=2,
                        race=MINER_RACE, accelerated_start=True)

    # Design the miner: Midget Miner hull (ARM-only, tech 0) with a
    # Quick Jump 5 and two Robo-Midget Miners (rate 2 x 5 = 10)
    harness.submit(1, "design", {"mode": "Add", "design": {
        "name": "Rock Chewer",
        "hull": "Midget Miner",
        "slots": [
            {"cell_number": 11, "component": "Quick Jump 5", "count": 1},
            {"cell_number": 12, "component": "Robo-Midget Miner",
             "count": 2},
        ],
    }})
    design = next(d for d in harness.state(1)["designs"]
                  if d["name"] == "Rock Chewer")

    home = harness.my_stars(1)[0]
    harness.submit(1, "production", {
        "mode": "Add", "star_key": home["name"], "index": 0,
        "production_order": {"production_type": "SHIP", "quantity": 1,
                             "name": "Rock Chewer",
                             "design_key": design["key"]},
    })

    # Build the miner
    miner = None
    for _ in range(6):
        harness.generate_turn()
        miner = _fleet_named(harness, "Rock Chewer")
        if miner:
            break
    assert miner is not None, "Rock Chewer was never built"
    assert miner["mining_rate"] == 10

    # Choose the mining target and dispatch miner + freighter, plus
    # the scout - the Rock Chewer carries no scanner, and only a
    # scanning fleet in orbit reveals a star (ScanStep.cs:118-127)
    target = _target_star(harness, home)
    _add_waypoint(harness, miner, target, warp=5, task="RemoteMine")
    teamster = _fleet_named(harness, "Teamster")
    assert teamster is not None
    _add_waypoint(harness, teamster, target, warp=5, task="NoTask")
    scout = _fleet_named(harness, "Long Range Scout")
    assert scout is not None
    _add_waypoint(harness, scout, target, warp=5, task="NoTask")

    # Fly out, then mine for several years once in orbit. The target's
    # concentrations become visible when the scout scans from orbit;
    # the first sighting is the baseline (at most one mining year in)
    mining_messages = []
    mined_turns = 0
    conc_before = None
    for _ in range(12):
        result = harness.generate_turn()
        if conc_before is None:
            sighting = harness.star_by_name(target["name"], 1)
            if sighting.get("intel") == "scanned":
                conc_before = {m: sighting[f"{m}_concentration"]
                               for m in MINERALS}
        turn_mining = [
            m for m in result["messages"]
            if m["type"] == "Remote Mining" and m["audience"] == 1
        ]
        mining_messages.extend(turn_mining)
        if turn_mining:
            mined_turns += 1
        if mined_turns >= MINING_TURNS:
            break
    assert mined_turns >= MINING_TURNS, "miner never mined"
    assert conc_before is not None, "target never scanned from orbit"

    # (c) Mining messages report the yield off the target star
    assert all("has mined" in m["text"] and target["name"] in m["text"]
               for m in mining_messages)

    # (a) Reported concentrations never increase under mining
    target_after = harness.star_by_name(target["name"], 1)
    conc_after = {m: target_after[f"{m}_concentration"] for m in MINERALS}
    for mineral in MINERALS:
        assert conc_after[mineral] <= conc_before[mineral]

    # (b) Haul proof: the Teamster loads one year's yield of the
    # richest mineral off the uninhabited surface
    teamster = _fleet_named(harness, "Teamster")
    assert teamster["in_orbit"] == target["name"], "Teamster not in orbit"
    best = max(MINERALS, key=lambda m: conc_before[m])
    per_turn = int(10 * conc_before[best] / 100.0)
    assert per_turn >= 1, f"seed produced a barren target: {conc_before}"
    loaded = harness._request(
        "POST",
        f"/api/games/{harness.game_id}/fleets/{teamster['key']}/cargo",
        {"empire_id": 1, best: per_turn},
    )
    assert loaded["status"] == "ok"
    assert loaded["fleet"]["cargo"][best] == per_turn

    return conc_before, conc_after


class TestRemoteMining:

    def test_remote_mining_full_cycle(self, harness):
        _run_scenario(harness)

    def test_remote_mining_is_deterministic(self, harness):
        """Same seed + same commands -> identical state digest."""
        digests = []
        for _ in range(2):
            _run_scenario(harness)
            digests.append(harness.state_digest(1))
        assert digests[0] == digests[1]
