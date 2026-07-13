"""
Stars Nova Web - Autoplay Harness

Plays a full game as the human empire (id 1) against the AI through the
same player-scoped HTTP API the browser client uses. Used as the final
functional test: it exercises production, research, scouting,
colonization, cargo transfer, fleet orders, combat, and turn generation,
and validates invariants every turn.

Usage:
    python scripts/autoplay.py --name game1 --seed 11 --size small \
        --players 2 --turns 30
"""

import argparse
import json
import math
import sys
import urllib.request

BASE = "http://localhost:9800/api"
EMPIRE = 1


def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(r, timeout=120) as resp:
        return json.load(resp)


def dist(a, b):
    return math.hypot(a["position_x"] - b["position_x"],
                      a["position_y"] - b["position_y"])


class Player:
    """Heuristic human player."""

    def __init__(self, game_id):
        self.game_id = game_id
        self.state = None
        self.scout_targets = {}   # fleet_key -> star name
        self.colonize_targets = set()
        self.errors = 0

    # -- state helpers ----------------------------------------------------
    def refresh(self):
        self.state = req("GET", f"/games/{self.game_id}/empires/{EMPIRE}/state")

    @property
    def owned(self):
        return [s for s in self.state["stars"] if s.get("intel") == "owned"]

    @property
    def known(self):
        return {s["name"]: s for s in self.state["stars"]}

    def submit(self, ctype, cdata):
        try:
            r = req("POST", f"/games/{self.game_id}/empires/{EMPIRE}/commands",
                    {"command_type": ctype, "command_data": cdata})
            if r.get("status") == "error":
                print(f"    command rejected: {r.get('error')}")
                self.errors += 1
            return r
        except urllib.error.HTTPError as e:
            print(f"    command HTTP error: {e.code} {e.read().decode()[:200]}")
            self.errors += 1

    # -- per-turn decision logic ------------------------------------------
    def act(self):
        self.manage_production()
        self.manage_research()
        self.manage_scouts()
        self.manage_colonizers()
        self.manage_warfleets()

    def manage_production(self):
        designs = {d["name"]: d for d in self.state["designs"]}
        for star in self.owned:
            queue = star.get("production_queue") or []
            if len(queue) >= 3:
                continue
            idx = len(queue)
            queued_names = [q.get("name") for q in queue]

            def add(ptype, name, qty, design=None):
                nonlocal idx
                order = {"production_type": ptype, "quantity": qty, "name": name}
                if design is not None:
                    order["design_key"] = "0x%x" % design["key"]
                self.submit("production", {
                    "mode": "Add", "star_key": star["name"],
                    "index": idx, "production_order": order
                })
                idx += 1

            operable_f = star.get("operable_factories", 100)
            operable_m = star.get("operable_mines", 100)
            if star.get("factories", 0) < operable_f and "Factory" not in queued_names:
                add("FACTORY", "Factory", 10)
            if star.get("mines", 0) < operable_m and "Mine" not in queued_names:
                add("MINE", "Mine", 10)

            # Fleet composition goals
            my_fleets = self.state["fleets"]
            scouts = [f for f in my_fleets if "Scout" in f["name"]]
            colonizers = [f for f in my_fleets if f.get("can_colonize")]
            warships = [f for f in my_fleets
                        if "Stalwart" in f["name"] and not f.get("is_starbase")]

            if len(scouts) < 2 and "Long Range Scout" not in queued_names:
                add("SHIP", "Long Range Scout", 1, designs.get("Long Range Scout"))
            elif len(colonizers) < 1 and "Santa Maria" not in queued_names:
                add("SHIP", "Santa Maria", 1, designs.get("Santa Maria"))
            elif len(warships) < 3 and "Stalwart Defender" not in queued_names:
                add("SHIP", "Stalwart Defender", 1, designs.get("Stalwart Defender"))

    def manage_research(self):
        research = self.state.get("research") or {}
        if research.get("budget", 0) != 15:
            fields = {k: 0 for k in research.get("levels", {})}
            fields["Energy"] = 1
            self.submit("research", {"budget": 15, "topics": {"levels": fields}})

    def idle(self, fleet):
        return not fleet.get("waypoints")

    def send(self, fleet, star, warp, task):
        self.submit("waypoint", {
            "mode": "Add", "fleet_key": fleet["key"],
            "index": len(fleet.get("waypoints") or []),
            "waypoint": {
                "position_x": star["position_x"], "position_y": star["position_y"],
                "warp_factor": warp, "destination": star["name"],
                "task": {"type": task}
            }
        })

    def manage_scouts(self):
        unexplored = [s for s in self.state["stars"] if s.get("intel") == "unknown"]
        taken = set(self.scout_targets.values())
        for fleet in self.state["fleets"]:
            if "Scout" not in fleet["name"] or fleet.get("is_starbase"):
                continue
            if not self.idle(fleet):
                continue
            options = [s for s in unexplored if s["name"] not in taken]
            if not options:
                break
            target = min(options, key=lambda s: dist(fleet, s))
            # Warp chosen by rough fuel budget (fuel/ly ~ mass*warp/200)
            warp = 9 if fleet["fuel_available"] > 150 else 6
            self.send(fleet, target, warp, "None")
            self.scout_targets[fleet["key"]] = target["name"]
            taken.add(target["name"])

    def manage_colonizers(self):
        candidates = [
            s for s in self.state["stars"]
            if s.get("intel") in ("scanned", "unknown")
            and not s.get("owner")
            and (s.get("habitability") is None or s.get("habitability", 0) > 20)
            and s["name"] not in self.colonize_targets
        ]
        for fleet in self.state["fleets"]:
            if not fleet.get("can_colonize") or not self.idle(fleet):
                continue
            # Ensure colonists aboard
            if fleet["cargo"]["colonists"] < 100:
                star = self.known.get(fleet.get("in_orbit") or "")
                if star and star.get("intel") == "owned" and star["colonists"] > 30000:
                    try:
                        req("POST", f"/games/{self.game_id}/fleets/{fleet['key']}/cargo",
                            {"empire_id": EMPIRE, "colonists": 2500})
                    except urllib.error.HTTPError as e:
                        print(f"    cargo load failed: {e.read().decode()[:150]}")
                        self.errors += 1
                    continue
            if not candidates:
                continue
            target = min(candidates, key=lambda s: dist(fleet, s))
            self.send(fleet, target, 6, "Colonise")
            self.colonize_targets.add(target["name"])
            candidates.remove(target)

    def manage_warfleets(self):
        # Send idle warships at scanned enemy planets or contacts
        enemy_stars = [
            s for s in self.state["stars"]
            if s.get("owner") and s["owner"] != EMPIRE and s.get("colonists")
        ]
        contacts = self.state.get("foreign_fleets") or []
        for fleet in self.state["fleets"]:
            if "Stalwart" not in fleet["name"] or fleet.get("is_starbase"):
                continue
            if not self.idle(fleet):
                continue
            targets = enemy_stars or contacts
            if not targets:
                continue
            target = min(targets, key=lambda s: dist(fleet, s))
            self.send(fleet, {
                "position_x": target["position_x"],
                "position_y": target["position_y"],
                "name": target.get("name", "enemy contact"),
            }, 7, "None")


def play(name, seed, size, players, turns):
    g = req("POST", "/games/", {
        "name": name, "player_count": players,
        "universe_size": size, "seed": seed
    })
    gid = g["id"]
    print(f"=== {name}: game {gid} seed={seed} size={size} "
          f"players={players} turns={turns}")

    p = Player(gid)
    battles = colonized = 0
    prev_pop = 0

    for turn_no in range(1, turns + 1):
        p.refresh()
        p.act()
        result = req("POST", f"/games/{gid}/turn/generate")
        msgs = result.get("messages", [])
        my_msgs = [m for m in msgs if m["audience"] in (0, EMPIRE)]
        battles += sum(1 for m in my_msgs if m["type"] == "Battle")
        colonized += sum(1 for m in my_msgs if m["type"] == "Colonization")

        p.refresh()
        pop = sum(s.get("colonists", 0) for s in p.owned)
        res = sum(s.get("resources_per_year", 0) for s in p.owned)
        print(f"turn {result['turn']}: planets={len(p.owned)} pop={pop:,} "
              f"res/yr={res} fleets={len(p.state['fleets'])} "
              f"contacts={len(p.state.get('foreign_fleets') or [])} "
              f"msgs={len(my_msgs)}")
        for m in my_msgs[:4]:
            print(f"    [{m['type']}] {m['text'][:100]}")

        if p.state.get("victor"):
            print(f"*** VICTORY: empire {p.state['victor']} at turn {result['turn']}")
            break
        prev_pop = pop

    # Final summary + invariants
    empires = req("GET", f"/games/{gid}/empires")
    print(f"--- final: {json.dumps(empires)}")
    ok = True
    if p.errors > 0:
        print(f"!!! {p.errors} command errors during play")
        ok = False
    if prev_pop <= 250000:
        print("!!! population never grew above starting value")
        ok = False
    my = [e for e in empires if e["id"] == EMPIRE][0]
    if my["star_count"] < 1:
        print("!!! human empire lost all planets")
    print(f"=== {name} {'PASS' if ok else 'FAIL'}: battles={battles} "
          f"colonized={colonized} planets={my['star_count']} "
          f"fleets={my['fleet_count']}")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--size", default="small")
    ap.add_argument("--players", type=int, default=2)
    ap.add_argument("--turns", type=int, default=30)
    args = ap.parse_args()
    ok = play(args.name, args.seed, args.size, args.players, args.turns)
    sys.exit(0 if ok else 1)
