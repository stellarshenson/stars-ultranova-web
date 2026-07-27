"""
Seeded e2e: client parity trio - waypoint leg editing, the multi-fleet
shared-position picker contract, and message goto linkage.

The leg-editing scenario drives the same per-index waypoint command
stream the fleet panel submits (Add/Edit/Insert/Delete,
WaypointCommand.cs:148-160): a freighter's list is assembled with mixed
warps and tasks, a warp-only Edit round-trips the CargoTask intact
(C# preserves the Task object on speed edits, FleetDetail.cs:110), and
the final route executes exactly over several turns. Message goto
linkage mirrors the C# Message.Event (Message.cs:38; battle messages
carry the report location, BattleEngine.cs:936-943) via the web
star_name/fleet_key fields.
"""

SEED = 20260727
LOAD_KT = 20

RESEARCH_FIELDS = ("Biotechnology", "Electronics", "Energy",
                   "Propulsion", "Weapons", "Construction")


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


def _foreign_stars_by_distance(harness, home):
    stars = [s for s in harness.state(1)["stars"]
             if s.get("intel") != "owned"]
    stars.sort(key=lambda s: (
        (s["position_x"] - home["position_x"]) ** 2
        + (s["position_y"] - home["position_y"]) ** 2))
    return stars


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


class TestWaypointLegEditing:

    def test_waypoint_leg_editing(self, harness):
        """A mixed warp/task waypoint list is shaped through per-index
        Add/Edit/Insert/Delete commands and then executes exactly:
        load at home, fly via a checkpoint, unload at the target."""
        harness.create_game(seed=SEED, size="small", players=2)

        home = harness.my_stars(1)[0]
        teamster = _fleet_named(harness, "Teamster")
        assert teamster is not None
        key = teamster["key"]

        stars = _foreign_stars_by_distance(harness, home)
        target = stars[0]      # final destination (B)
        detour = stars[1]      # leg later removed again (A)

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

        # The player state exposes the full task dict per leg (the
        # client edit payloads resend it verbatim)
        teamster = _fleet_by_key(harness, key)
        wps = teamster["waypoints"]
        assert [w["destination"] for w in wps] == [
            home["name"], detour["name"], target["name"]]
        cargo_task = wps[2]["task"]
        assert cargo_task["mode"] == "UNLOAD"
        assert cargo_task["amount"]["ironium"] == LOAD_KT

        # Warp-only Edit on the cargo leg, resending the task read
        # back from state - the task must survive intact
        _add_waypoint(harness, key, 2, wps[2]["position_x"],
                      wps[2]["position_y"], 5, wps[2]["destination"],
                      cargo_task, mode="Edit")
        teamster = _fleet_by_key(harness, key)
        wps = teamster["waypoints"]
        assert wps[2]["warp_factor"] == 5
        assert wps[2]["task"]["type"] == "CargoTask"
        assert wps[2]["task"]["mode"] == "UNLOAD"
        assert wps[2]["task"]["amount"]["ironium"] == LOAD_KT
        assert wps[2]["task"]["target_name"] == target["name"]

        # Insert a checkpoint before the detour, then delete the
        # detour: [LOAD@home, checkpoint, target]
        mid_x = (home["position_x"] + target["position_x"]) / 2
        mid_y = (home["position_y"] + target["position_y"]) / 2
        _add_waypoint(harness, key, 1, mid_x, mid_y, 6, "checkpoint",
                      {"type": "NoTask"}, mode="Insert")
        teamster = _fleet_by_key(harness, key)
        assert [w["destination"] for w in teamster["waypoints"]] == [
            home["name"], "checkpoint", detour["name"], target["name"]]

        harness.submit(1, "waypoint", {
            "mode": "Delete", "fleet_key": key, "index": 2})
        teamster = _fleet_by_key(harness, key)
        wps = teamster["waypoints"]
        assert [w["destination"] for w in wps] == [
            home["name"], "checkpoint", target["name"]]
        assert [w["warp_factor"] for w in wps] == [0, 6, 5]

        # Execute: the load lands first, then the route runs to the
        # target where the cargo task unloads on arrival
        harness.generate_turn()
        teamster = _fleet_by_key(harness, key)
        assert teamster["cargo"]["ironium"] == LOAD_KT

        unloaded = False
        for _ in range(20):
            result = harness.generate_turn()
            if any(m["audience"] == 1
                   and f"has unloaded its cargo at {target['name']}"
                   in m["text"] for m in result["messages"]):
                unloaded = True
                break
        assert unloaded, "freighter never unloaded at the target"

        teamster = _fleet_by_key(harness, key)
        assert teamster["in_orbit"] == target["name"]
        assert teamster["cargo"]["ironium"] == 0


class TestMultiFleetSharedPosition:

    def test_multi_fleet_shared_position(self, harness):
        """Fleets split at one point report the identical position and
        are non-starbase - the data contract the map picker cycles
        over (canvas cycling itself is browser-verified in wave 6)."""
        harness.create_game(seed=SEED, size="small", players=2)

        scout1 = _fleet_named(harness, "Long Range Scout #1")
        scout2 = _fleet_named(harness, "Long Range Scout #2")
        assert scout1 is not None and scout2 is not None

        # Merge the pair, then split one scout back out
        merged = harness._request(
            "POST",
            f"/api/games/{harness.game_id}/fleets/{scout1['key']}/merge",
            {"empire_id": 1, "other_fleet_key": scout2["key"]},
        )
        assert merged["status"] == "applied"
        merged_fleet = _fleet_by_key(harness, scout1["key"])
        design_key = merged_fleet["tokens"][0]["design_key"]
        assert merged_fleet["tokens"][0]["quantity"] == 2

        split = harness._request(
            "POST",
            f"/api/games/{harness.game_id}/fleets/{scout1['key']}/split",
            {"empire_id": 1, "keep": {str(design_key): 1}},
        )
        assert split["status"] == "applied"

        # Both products share the exact position (the picker threshold
        # groups them) and neither is a starbase (StarMap.cs:977
        # excludes starbases from the near-object list)
        kept = _fleet_by_key(harness, scout1["key"])
        new_key = split["new_fleet_key"]
        spun_off = _fleet_by_key(harness, new_key)
        assert spun_off is not None
        assert kept["position_x"] == spun_off["position_x"]
        assert kept["position_y"] == spun_off["position_y"]
        assert not kept["is_starbase"] and not spun_off["is_starbase"]

        # The homeworld starbase shares the location but is flagged
        # for exclusion
        starbase = _fleet_named(harness, "Starbase")
        assert starbase is not None and starbase["is_starbase"]
        assert starbase["position_x"] == kept["position_x"]


class TestMessageGotoLinkage:

    def test_star_message_links_star(self, harness):
        """Star-type messages carry star_name resolving to a star in
        the same state payload (the client goto selects and centers)."""
        harness.create_game(seed=SEED, size="small", players=2)
        home = harness.my_stars(1)[0]

        harness.submit(1, "production", {
            "mode": "Add", "star_key": home["name"], "index": 0,
            "production_order": {"production_type": "FACTORY",
                                 "quantity": 3, "name": "Factory"},
        })

        linked = None
        for _ in range(6):
            result = harness.generate_turn()
            for m in result["messages"]:
                if (m["audience"] == 1 and m["type"] == "Star"
                        and "factor" in m["text"]):
                    linked = m
                    break
            if linked:
                break
        assert linked is not None, "no factory-built Star message"
        assert linked["star_name"] == home["name"]
        assert harness.star_by_name(linked["star_name"]) is not None

    def test_fleet_message_links_fleet(self, harness):
        """Fleet-linked messages carry a fleet_key present in the
        state fleet list."""
        harness.create_game(seed=SEED, size="small", players=2)
        home = harness.my_stars(1)[0]
        teamster = _fleet_named(harness, "Teamster")

        _add_waypoint(harness, teamster["key"], 0, home["position_x"],
                      home["position_y"], 0, home["name"],
                      {"type": "Cargo", "mode": "LOAD",
                       "amount": {"ironium": 10},
                       "target_name": home["name"]})
        result = harness.generate_turn()

        cargo_msgs = [m for m in result["messages"]
                      if m["audience"] == 1
                      and "has loaded cargo from" in m["text"]]
        assert cargo_msgs, "no cargo load message"
        assert cargo_msgs[0]["fleet_key"] == teamster["key"]
        assert _fleet_by_key(harness, cargo_msgs[0]["fleet_key"]) is not None

    def test_battle_message_links_report(self, harness):
        """Battle messages carry star_name equal to the location of a
        report served by GET /empires/{eid}/battles (the client goto
        opens the battle viewer on it, Messages.cs:229-238)."""
        harness.create_game(seed=SEED, size="small", players=2)

        # Tech by state surgery so the armed designs validate
        # (pattern from test_wave4_integration.py)
        from backend.services.game_manager import get_game_manager
        manager = get_game_manager()
        server_data = manager._load_game_state(harness.game_id)
        for empire in server_data.all_empires.values():
            for tech_field in RESEARCH_FIELDS:
                empire.research_levels.levels[tech_field] = 10
        manager._save_game_state(harness.game_id, server_data)

        for empire_id, name, engine in (
                (1, "Raider", "Alpha Drive 8"),
                (2, "Picket", "Quick Jump 5")):
            result = harness.submit(empire_id, "design", {
                "mode": "Add",
                "design": {"name": name, "hull": "Destroyer", "slots": [
                    {"cell_number": 2, "component": "Laser", "count": 1},
                    {"cell_number": 10, "component": engine, "count": 1},
                ]},
            })
            assert result["status"] == "applied", result

        # Both fleets on one deep-space point; relations default to
        # mutual Enemy (GameInitialiser.cs:132-143), so they fight
        from backend.core.data_structures import NovaPoint
        from backend.core.game_objects import Fleet
        from backend.core.waypoints.waypoint import (
            Waypoint, LayMinesTaskObj, NoTaskObj)
        from backend.services.ship_specs import find_design, make_token

        home1 = harness.my_stars(1)[0]
        home2 = harness.my_stars(2)[0]
        px = (home1["position_x"] + home2["position_x"]) / 2 + 0.5
        py = (home1["position_y"] + home2["position_y"]) / 2 + 0.5

        server_data = manager._load_game_state(harness.game_id)
        for empire_id, design_name in ((1, "Raider"), (2, "Picket")):
            empire = server_data.all_empires[empire_id]
            design = find_design(empire, design_name)
            assert design is not None
            fleet = Fleet()
            fleet.key = empire.get_next_fleet_key()
            fleet.name = f"{design_name} X"
            fleet.turn_year = empire.turn_year
            fleet.position = NovaPoint(px, py)
            token = make_token(design)
            fleet.tokens[token.design_key] = token
            fleet.fuel_available = fleet.total_fuel_capacity
            if empire_id == 2:
                # Parking stack keeps the AI's hands off the fleet
                # (pattern from test_wave4_integration.py)
                fleet.waypoints = [
                    Waypoint(position_x=px, position_y=py, warp_factor=4,
                             destination="park", task=LayMinesTaskObj()),
                    Waypoint(position_x=px, position_y=py, warp_factor=4,
                             destination="park", task=NoTaskObj()),
                ]
            empire.owned_fleets[fleet.key] = fleet
        manager._save_game_state(harness.game_id, server_data)

        result = harness.generate_turn()
        battle_msgs = [m for m in result["messages"]
                       if m["type"] == "Battle" and m["audience"] == 1]
        assert battle_msgs, "no battle announcement"
        assert battle_msgs[0]["star_name"], "battle message lacks star_name"

        reports = harness._request(
            "GET",
            f"/api/games/{harness.game_id}/empires/1/battles")
        assert reports, "no battle report for empire 1"
        assert any(r["location"] == battle_msgs[0]["star_name"]
                   for r in reports)
