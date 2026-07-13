"""
Wave-2 cross-feature integration: one seeded game combining all five
implemented gaps. A JOAT+ARM race colonizes its nearest star, boosts
the colony with two Medium Freighter loads of colonists plus
germanium, and runs a production queue of Alchemy + Terraform + auto Factory
for 15 turns - all three make progress per the rules (a concrete
order at the front banks partial progress and blocks the queue behind
it, ProductionOrder.cs:96-99; the auto order persists). In the same
game a Rock Chewer remote-mines a second uninhabited world every year
and a freighter finally loads the accumulated ore off its surface.
"""

QUEUE_TURNS = 15
SETUP_TURNS = 14   # build ships, colonize, deliver colonists
HAUL_TURNS = 8     # freighter relocation to the mining world

SEED = 20260713

# Same JOAT + ARM wizard race as tests/e2e/test_remote_mining.py;
# colonistsPerResource 1500 keeps it inside the advantage-point budget
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


def dist2(a, b):
    return ((a["position_x"] - b["position_x"]) ** 2
            + (a["position_y"] - b["position_y"]) ** 2)


def env(star):
    return (star["gravity"], star["temperature"], star["radiation"])


def _zero_research(harness, empire_id=1):
    """All production resources to manufacturing, none to labs."""
    levels = {key: 0 for key in
              harness.state(empire_id)["research"]["levels"]}
    levels["Energy"] = 1
    harness.submit(empire_id, "research",
                   {"budget": 0, "topics": {"levels": levels}})


def _fleets_named(harness, prefix, empire_id=1):
    return [f for f in harness.my_fleets(empire_id)
            if f["name"].startswith(prefix)]


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


def _transfer(harness, fleet_key, **deltas):
    """Immediate cargo transfer with the orbited star (positive loads)."""
    body = {"empire_id": 1}
    body.update(deltas)
    result = harness._request(
        "POST",
        f"/api/games/{harness.game_id}/fleets/{fleet_key}/cargo",
        body,
    )
    assert result["status"] == "ok"
    return result["fleet"]


class TestWave2Integration:

    def test_combined_queue_and_remote_miner_fifteen_turns(self, harness):
        harness.create_game(seed=SEED, size="small", players=2,
                            race=MINER_RACE, accelerated_start=True)
        _zero_research(harness)
        home = harness.my_stars(1)[0]

        # Two nearest foreign stars: colony target and mining target
        foreign = sorted(
            (s for s in harness.state(1)["stars"]
             if s.get("intel") != "owned"),
            key=lambda s: dist2(s, home))
        colony_star, mining_star = foreign[0], foreign[1]

        # Ship designs: the ARM Midget Miner (as in test_remote_mining)
        # plus a 210 kT Medium Freighter hauler (Construction 3 hull -
        # JOAT starting tech) for the colonist boost
        harness.submit(1, "design", {"mode": "Add", "design": {
            "name": "Rock Chewer",
            "hull": "Midget Miner",
            "slots": [
                {"cell_number": 11, "component": "Quick Jump 5",
                 "count": 1},
                {"cell_number": 12, "component": "Robo-Midget Miner",
                 "count": 2},
            ],
        }})
        harness.submit(1, "design", {"mode": "Add", "design": {
            "name": "Big Mule",
            "hull": "Medium Freighter",
            "slots": [
                {"cell_number": 10, "component": "Quick Jump 5",
                 "count": 1},
            ],
        }})
        designs = harness.state(1)["designs"]
        for order_index, (name, quantity) in enumerate(
                (("Rock Chewer", 1), ("Big Mule", 2))):
            design = next(d for d in designs if d["name"] == name)
            harness.submit(1, "production", {
                "mode": "Add", "star_key": home["name"],
                "index": order_index,
                "production_order": {"production_type": "SHIP",
                                     "quantity": quantity,
                                     "name": name,
                                     "design_key": design["key"]},
            })

        # Dispatch the starting fleets: colony ship colonizes the
        # nearest star, the scout orbits the mining star to scan it
        # (the Rock Chewer carries no scanner, ScanStep.cs:118-127)
        colony_ship = next(f for f in harness.my_fleets(1)
                           if f["can_colonize"] and not f["is_starbase"])
        assert colony_ship["cargo"]["colonists"] > 0
        _add_waypoint(harness, colony_ship, colony_star, warp=6,
                      task="Colonise")
        scout = _fleets_named(harness, "Long Range Scout")[0]
        _add_waypoint(harness, scout, mining_star, warp=6, task="NoTask")

        # Build the ships, then send the miner out and the two loaded
        # freighters (colonists + germanium for factories) after the
        # colony ship
        miner_sent = False
        freighters_sent = False
        for _ in range(SETUP_TURNS):
            harness.generate_turn()

            if not miner_sent:
                miners = _fleets_named(harness, "Rock Chewer")
                if miners:
                    assert miners[0]["mining_rate"] == 10
                    _add_waypoint(harness, miners[0], mining_star,
                                  warp=5, task="RemoteMine")
                    miner_sent = True

            if not freighters_sent:
                mules = [f for f in _fleets_named(harness, "Big Mule")
                         if f["in_orbit"] == home["name"]]
                built = sum(t["quantity"] for f in mules
                            for t in f["tokens"])
                if built == 2:
                    germanium = 60
                    for mule in mules:
                        space = (mule["cargo_capacity"]
                                 - mule["cargo_mass"] - germanium)
                        _transfer(harness, mule["key"],
                                  germanium=germanium,
                                  colonists=space * 100)
                        _add_waypoint(harness, mule, colony_star,
                                      warp=6, task="NoTask")
                        germanium = 0
                    freighters_sent = True

            colony = harness.star_by_name(colony_star["name"], 1)
            mules = _fleets_named(harness, "Big Mule")
            if (freighters_sent and colony.get("intel") == "owned"
                    and mules
                    and all(f["in_orbit"] == colony_star["name"]
                            for f in mules)):
                break
        assert miner_sent and freighters_sent
        colony = harness.star_by_name(colony_star["name"], 1)
        assert colony.get("intel") == "owned", \
            f"{colony_star['name']} not colonized in {SETUP_TURNS} turns"

        # Deliver the boost: unload everything onto the young colony
        for mule in _fleets_named(harness, "Big Mule"):
            assert mule["in_orbit"] == colony_star["name"]
            cargo = mule["cargo"]
            _transfer(harness, mule["key"],
                      germanium=-cargo["germanium"],
                      colonists=-cargo["colonists"])

        # Baseline before the combined queue starts
        colony = harness.star_by_name(colony_star["name"], 1)
        env0 = env(colony)
        base = {m: colony[m] for m in MINERALS}
        base_factories = colony["factories"]
        # Precondition: random colony environment is off the race
        # optimum (50/50/50 for the 15-85 hab ranges), so terraforming
        # has real work to do
        assert any(abs(value - 50) >= 1 for value in env0), env0

        # The combined queue: concrete Alchemy, concrete Terraform,
        # auto Factory behind them. The front order banks partial
        # progress each year and blocks the rest until it completes
        # (ProductionOrder.IsBlocking, ProductionOrder.cs:96-99); the
        # auto order then soaks the leftovers and persists.
        orders = (
            {"production_type": "ALCHEMY", "quantity": 1,
             "name": "Alchemy"},
            {"production_type": "TERRAFORM", "quantity": 1,
             "name": "Terraform"},
            {"production_type": "FACTORY", "quantity": 30,
             "name": "Factory", "is_auto_build": True},
        )
        for index, order in enumerate(orders):
            harness.submit(1, "production", {
                "mode": "Add", "star_key": colony_star["name"],
                "index": index, "production_order": order,
            })

        # 15 turns: all three queue items make progress and the remote
        # miner works the mining star every year it is in orbit
        messages = []
        mined_turns = 0
        for _ in range(QUEUE_TURNS):
            result = harness.generate_turn()
            messages.extend(m["text"] for m in harness.state(1)["messages"])
            turn_mining = [
                m for m in result["messages"]
                if m["type"] == "Remote Mining" and m["audience"] == 1
            ]
            assert all("has mined" in m["text"]
                       and mining_star["name"] in m["text"]
                       for m in turn_mining)
            if turn_mining:
                mined_turns += 1
        assert not any("unknown item" in text for text in messages)

        after = harness.star_by_name(colony_star["name"], 1)
        queue_types = [o["production_type"]
                       for o in after["production_queue"]]

        # (a) Alchemy completed: +1 kT of every mineral transmuted
        # (GameInitialiser.cs:315-318), order left the queue
        assert any("has transmuted" in text for text in messages)
        assert "ALCHEMY" not in queue_types
        assert after["ironium"] == base["ironium"] + 1
        assert after["boranium"] == base["boranium"] + 1

        # (b) Terraform completed: environment moved toward the race
        # optimum centre, order left the queue
        assert any("has been terraformed" in text for text in messages)
        assert "TERRAFORM" not in queue_types
        assert env(after) != env0
        for key, before in zip(("gravity", "temperature", "radiation"),
                               env0):
            now = after[key]
            if now != before:
                assert abs(now - 50) < abs(before - 50), (key, before, now)

        # (c) Auto factories built with the leftover years and the auto
        # order persists in the queue (never dropped while unfinished)
        assert after["factories"] > base_factories
        assert after["factories"] <= after["operable_factories"]
        auto = next(o for o in after["production_queue"]
                    if o["production_type"] == "FACTORY")
        assert auto["is_auto_build"] is True

        # (d) The miner mined throughout the queue window
        assert mined_turns >= 10, f"only {mined_turns} mining years"

        # (e) Haul proof: an emptied freighter relocates to the mining
        # star and loads one year's yield of the richest mineral off
        # the uninhabited surface
        sighting = harness.star_by_name(mining_star["name"], 1)
        assert sighting.get("intel") == "scanned", \
            "mining star never scanned from orbit"
        conc = {m: sighting[f"{m}_concentration"] for m in MINERALS}
        best = max(MINERALS, key=lambda m: conc[m])
        per_turn = int(10 * conc[best] / 100.0)
        assert per_turn >= 1, f"seed produced a barren target: {conc}"

        hauler = _fleets_named(harness, "Big Mule")[0]
        _add_waypoint(harness, hauler, mining_star, warp=6, task="NoTask")
        for _ in range(HAUL_TURNS):
            harness.generate_turn()
            hauler = _fleets_named(harness, "Big Mule")[0]
            if hauler["in_orbit"] == mining_star["name"]:
                break
        assert hauler["in_orbit"] == mining_star["name"], \
            "freighter never reached the mining star"
        loaded = _transfer(harness, hauler["key"], **{best: per_turn})
        assert loaded["cargo"][best] == per_turn
