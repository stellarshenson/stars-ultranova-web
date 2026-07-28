"""
Stars Nova Web - LLM-vs-LLM Playtest Harness

Plays a two-empire game through the real backend HTTP API with the
"claude" CLI (claude -p) commanding BOTH sides. Empire 1 is "Iron
Fist" (military pressure), empire 2 is "Silicon Loom" (economy and
tech). Each side inherits a persistent strategy memo it rewrites every
turn plus the last five turns' event digests. Every turn is mined for
forensics: full state dumps, anomaly detectors, rejected orders,
server tracebacks and the commanders' own bug observations.

The harness boots ITS OWN server subprocess on port 9830 with a
persistent dedicated database under results/playtest/<name>/db/, so a
resumed run reattaches to the same game. State is checkpointed to
results/playtest/<name>/state.json after every turn; --resume
continues an interrupted run. One bad turn never aborts the loop.

Usage:
    uv run python scripts/llm_playtest.py --name smoke --seed 777 --turns 3

Detached launch (the real 100-turn run):
    mkdir -p logs
    setsid nohup bash -c \
      'uv run python scripts/llm_playtest.py --name run100 --seed 4242 \
       --turns 100 2>&1 | tee -a logs/llm-playtest-run100.log' \
      >/dev/null 2>&1 &

    Resume after interruption:
    setsid nohup bash -c \
      'uv run python scripts/llm_playtest.py --name run100 --seed 4242 \
       --turns 100 --resume 2>&1 | tee -a logs/llm-playtest-run100.log' \
      >/dev/null 2>&1 &

Outputs under results/playtest/<name>/:
    db/               server working dir (stars_nova.db lives here)
    server.log        playtest server output (scraped for tracebacks)
    state.json        per-turn checkpoint (game id, next turn, history)
    memo-1.md/2.md    each commander's inherited strategy memo
    digests.jsonl     per-turn per-side event digests
    turnNNNN.json     full both-sides state dump per turn
    forensics.jsonl   anomaly events (see FORENSIC EVENT TYPES below)
    bug_reports.jsonl commanders' "observations" verbatim
    orders/           raw claude -p request+response per turn per side

FORENSIC EVENT TYPES: order_rejected, commander_error, invalid_json,
negative_value, absurd_value, stuck_fleet, turn_time, server_traceback,
turn_failed, server_restart, game_over.
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PORT = 9830
BASE = f"http://127.0.0.1:{PORT}/api"
SIDES = (1, 2)
RESEARCH_FIELDS = ("Energy", "Weapons", "Propulsion", "Construction",
                   "Electronics", "Biotechnology")
PRODUCTION_TYPES = ("FACTORY", "MINE", "DEFENSE", "SHIP", "STARBASE",
                    "TERRAFORM", "ALCHEMY")
MEMO_WORD_CAP = 600
CLAUDE_TIMEOUT = 600
TURN_TIME_ANOMALY = 60.0
STUCK_TURNS = 3

PERSONAS = {
    1: {
        "name": "Iron Fist",
        "text": (
            "You are IRON FIST, a ruthless military commander. Doctrine: "
            "expand early and aggressively, then pivot to war fleets and "
            "sustained military pressure on the enemy. Seize habitable "
            "worlds fast, keep weapons and propulsion tech ahead, build "
            "warships in numbers and hunt the enemy's colonies and "
            "shipping. Adapt to setbacks: if a push fails, rebuild, "
            "protect your core worlds, and strike where the enemy is "
            "weak. You still need a working economy to feed the war "
            "machine - do not starve your factories and mines."
        ),
    },
    2: {
        "name": "Silicon Loom",
        "text": (
            "You are SILICON LOOM, a patient technocrat. Doctrine: "
            "economy and technology first, defensive posture, late-game "
            "power spike. Maximize factories, mines and population "
            "growth, research aggressively, fortify with defenses and "
            "starbases, and avoid early wars you cannot win. Scout "
            "enough to see threats coming. When your tech and industry "
            "dominate, field a decisive modern fleet and win. Adapt: if "
            "attacked early, shift enough production to defense to "
            "survive without abandoning the long game."
        ),
    },
}

SHARED_BRIEF = (
    "You inherit your STRATEGY MEMO below - it is your long-term memory. "
    "Keep long-term plans there and rewrite it every turn (max 600 "
    "words). Adapt your strategy across game phases (opening / "
    "consolidation / endgame). You are also a PLAYTESTER: report any "
    "game behavior that looks buggy, impossible or unbalanced in "
    "\"observations\" (empty list if nothing odd)."
)

ORDERS_SCHEMA_TEXT = """Reply with STRICT JSON only - a single JSON object, no markdown fences, no commentary. Schema (all keys optional except strategy, memo, observations):
{
  "strategy": "<one line: current phase and plan>",
  "memo": "<your rewritten strategy memo, max 600 words>",
  "observations": ["<anything that looks like a bug or imbalance>"],
  "research": {"budget": <0-100 percent of resources>, "field": "<Energy|Weapons|Propulsion|Construction|Electronics|Biotechnology>"},
  "production": [{"star": "<owned star name>", "items": [{"type": "<FACTORY|MINE|DEFENSE|SHIP|STARBASE|TERRAFORM|ALCHEMY>", "name": "<design name, SHIP/STARBASE only>", "quantity": <1-500>}]}],
  "fleets": [{"fleet_key": <key>, "waypoints": [{"target": "<star name>" or [x, y], "warp": <1-10>, "task": "<none|colonize>"}]}],
  "cargo": [{"fleet_key": <key>, "ironium": <kT>, "boranium": <kT>, "germanium": <kT>, "colonists": <headcount>}],
  "designs": [{"name": "<new design name>", "hull": "<buildable hull name>", "role": "<warship|scout|colonizer|freighter|starbase>"}],
  "relations": [{"empire_id": <id>, "relation": "<Enemy|Neutral|Friend>"}],
  "packets": [{"star": "<owned star with mass driver>", "target": "<star name>", "warp": <n>, "ironium": <kT>, "boranium": <kT>, "germanium": <kT>}]
}
Rules:
- production REPLACES the star's whole queue (list items in build order, max 6 per star); stars you omit keep their current queue
- fleets entries REPLACE that fleet's waypoints (max 4 waypoints); fleets you omit keep their orders; use task "colonize" only on a colony ship aimed at an unowned star
- cargo transfers with the orbited star: positive loads star -> fleet, negative unloads; colonists are headcount (load colonists before sending a colonizer)
- designs: max 2 per turn; the harness fills slots with the best components your tech allows for the role; build the design afterwards via production type SHIP (or STARBASE) using its name
- research: one field gets all progress; budget is the percent of resources spent on research
- keep orders consistent with what you can see; invalid orders are rejected and wasted"""


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# Rich console: force_terminal keeps colour codes in the detached log so
# "tail -f" and "less -R" render them; markup stays OFF for plain log()
# because messages may contain literal brackets (latency lists, tracebacks).
from rich.console import Console

_console = Console(force_terminal=True, width=140, highlight=False)

# semantic palette (rich-output standard): side 1 light_coral, side 2
# steel_blue, success dark_sea_green, warning dark_goldenrod,
# error indian_red, headers medium_purple, values light_sea_green
SIDE_STYLE = {1: "light_coral", 2: "steel_blue"}


def _stamp():
    return f"[{datetime.now().strftime('%H:%M:%S')}]"


def log(msg):
    _console.print(f"{_stamp()} {msg}", markup=False)


def rlog(msg):
    """Rich-markup log line (caller escapes any literal brackets)."""
    _console.print(f"[dim]{_stamp()}[/dim] {msg}")


def append_jsonl(path, record):
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


# =====================================================================
# Server subprocess
# =====================================================================

class PlaytestServer:
    """Owns the dedicated uvicorn subprocess on PORT with its own db."""

    def __init__(self, run_dir: Path):
        self.run_dir = run_dir
        self.db_dir = run_dir / "db"
        self.server_log = run_dir / "server.log"
        self.proc = None

    def prepare_dirs(self):
        self.db_dir.mkdir(parents=True, exist_ok=True)
        for name in ("backend", "frontend"):
            link = self.db_dir / name
            if link.is_symlink() and not link.exists():
                link.unlink()  # dangling symlink - replace it
            if not link.exists():
                link.symlink_to(REPO_ROOT / name)

    def _port_in_use(self):
        try:
            with urllib.request.urlopen(BASE + "/games/", timeout=3):
                return True
        except (urllib.error.URLError, OSError):
            return False

    def start(self):
        self.prepare_dirs()
        if self._port_in_use():
            raise RuntimeError(
                f"port {PORT} already serving - another playtest server "
                "is running; kill it first (pkill -f 'uvicorn.*9830')")
        log_file = open(self.server_log, "a")
        log_file.write(f"\n=== playtest server start {now_iso()} ===\n")
        log_file.flush()
        python = REPO_ROOT / ".venv" / "bin" / "python"
        self.proc = subprocess.Popen(
            [str(python), "-m", "uvicorn", "backend.main:app",
             "--host", "127.0.0.1", "--port", str(PORT)],
            cwd=str(self.db_dir), stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self._wait_healthy()

    def _wait_healthy(self, timeout=60):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError(
                    f"playtest server exited rc={self.proc.returncode} "
                    f"(see {self.server_log})")
            try:
                with urllib.request.urlopen(
                        BASE + "/games/", timeout=5):
                    pass
                # guard against a stale server answering while our
                # spawn lost the port bind race
                time.sleep(0.5)
                if self.proc.poll() is not None:
                    raise RuntimeError(
                        f"server exited rc={self.proc.returncode} but "
                        f"port {PORT} answers - stale server holds it")
                return
            except (urllib.error.URLError, OSError):
                time.sleep(0.5)
        raise RuntimeError("playtest server never became healthy")

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self):
        if self.alive():
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()


# =====================================================================
# API client with retry/backoff and server restart
# =====================================================================

class Api:
    def __init__(self, server: PlaytestServer, forensics):
        self.server = server
        self.forensics = forensics

    def request(self, method, path, body=None, timeout=180):
        """Returns (status_code, parsed_json_or_text)."""
        data = json.dumps(body).encode() if body is not None else None
        last_error = None
        for attempt in range(5):
            try:
                req = urllib.request.Request(
                    BASE + path, data=data, method=method,
                    headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.status, json.load(resp)
            except urllib.error.HTTPError as e:
                text = e.read().decode(errors="replace")
                try:
                    payload = json.loads(text)
                except ValueError:
                    payload = {"detail": text[:500]}
                if e.code >= 500 and attempt < 4:
                    last_error = f"HTTP {e.code}"
                    time.sleep(2 ** attempt)
                    continue
                return e.code, payload
            except (urllib.error.URLError, OSError, TimeoutError) as e:
                last_error = repr(e)
                if not self.server.alive():
                    self.forensics.event("server_restart", {
                        "reason": "server process dead",
                        "during": f"{method} {path}"})
                    log("server died - restarting")
                    try:
                        self.server.start()
                    except Exception as boot:
                        last_error = f"restart failed: {boot!r}"
                time.sleep(2 ** attempt)
        raise RuntimeError(
            f"API unreachable after retries: {method} {path}: {last_error}")


# =====================================================================
# Forensics
# =====================================================================

class Forensics:
    def __init__(self, run_dir: Path):
        self.events_path = run_dir / "forensics.jsonl"
        self.bugs_path = run_dir / "bug_reports.jsonl"
        self.turn = 0
        self.year = 0
        self.turn_events = 0

    def event(self, etype, detail):
        self.turn_events += 1
        record = {"time": now_iso(), "turn": self.turn,
                  "year": self.year, "type": etype, "detail": detail}
        append_jsonl(self.events_path, record)

    def bug_report(self, side, observations):
        for obs in observations:
            append_jsonl(self.bugs_path, {
                "time": now_iso(), "turn": self.turn, "year": self.year,
                "side": side, "persona": PERSONAS[side]["name"],
                "observation": str(obs)[:2000]})


def find_nonfinite(obj, path=""):
    """Recursively find NaN/inf values in a JSON-ish structure."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            found += find_nonfinite(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:200]):
            found += find_nonfinite(v, f"{path}[{i}]")
    elif isinstance(obj, float) and not math.isfinite(obj):
        found.append(path)
    return found


# =====================================================================
# Component catalog (for curated ship designs)
# =====================================================================

class Catalog:
    """Hull modules + component tech data, fetched once per process."""

    def __init__(self, api: Api):
        _, hulls = api.request("GET", "/designs/hulls")
        _, comps = api.request("GET", "/designs/components")
        self.hulls = {h["name"]: h for h in hulls}
        self.components = {c["name"]: c for c in comps}

    def tech_ok(self, comp, levels):
        return all(levels.get(field, 0) >= need
                   for field, need in
                   (comp.get("tech_requirements") or {}).items())

    def _best(self, item_types, levels, keyfn):
        pool = [c for c in self.components.values()
                if c["item_type"] in item_types
                and self.tech_ok(c, levels)]
        return max(pool, key=keyfn) if pool else None

    def buildable_hulls(self, levels):
        """Tech-ok hulls as (name, is_starbase), cheap-tech first."""
        out = []
        for name, hull in self.hulls.items():
            comp = self.components.get(name)
            if comp is None or not self.tech_ok(comp, levels):
                continue
            out.append((name, hull.get("is_starbase", False),
                        sum((comp.get("tech_requirements") or {})
                            .values())))
        out.sort(key=lambda t: t[2])
        return [(n, sb) for n, sb, _ in out]

    def build_slots(self, hull_name, role, levels):
        """Curated slot fill for a role. Returns (slots, error)."""
        hull = self.hulls.get(hull_name)
        if hull is None:
            return None, f"unknown hull {hull_name}"
        techsum = lambda c: sum(
            (c.get("tech_requirements") or {}).values())
        # Hull Affinity engines (e.g. Settler's Delight) fit only one
        # hull and are often race-restricted; the components API does
        # not expose race restrictions, so avoid them in curated picks
        engine = self._best(
            {"ENGINE"}, levels, lambda c: (
                "Hull Affinity" not in (c.get("properties") or {}),
                (c.get("properties", {}).get("Engine", {})
                 .get("optimal_speed", 0)), -c["mass"]))
        weapon = self._best({"BEAM_WEAPONS", "TORPEDOES", "WEAPON"},
                            levels, techsum)
        shield = self._best({"SHIELD"}, levels, techsum)
        armor = self._best({"ARMOR"}, levels, techsum)
        scanner = self._best({"SCANNER"}, levels, techsum)

        slots = []
        colonizer_placed = False

        def put(module, comp, count=None):
            if comp is None:
                return
            slots.append({
                "cell_number": module["cell_number"],
                "component": comp["name"],
                "count": count or module.get("component_maximum", 1),
            })

        for module in hull.get("modules", []):
            slot_type = (module.get("component_type") or "").lower()
            if "engine" in slot_type:
                put(module, engine)
            elif (role == "colonizer" and not colonizer_placed
                    and ("mechanical" in slot_type or "mech" in slot_type
                         or "general purpose" in slot_type)):
                comp = self.components.get("Colonization Module")
                if comp is not None and self.tech_ok(comp, levels):
                    put(module, comp, 1)
                    colonizer_placed = True
            elif "general purpose" in slot_type:
                if role in ("warship", "starbase"):
                    put(module, weapon or armor)
                elif role == "freighter":
                    pod = self.components.get("Cargo Pod")
                    if pod is not None and self.tech_ok(pod, levels):
                        put(module, pod)
                elif role == "scout":
                    tank = self.components.get("Fuel Tank")
                    if tank is not None and self.tech_ok(tank, levels):
                        put(module, tank)
            elif "weapon" in slot_type and role in ("warship", "starbase"):
                put(module, weapon)
            elif "shield" in slot_type:
                if role in ("warship", "starbase"):
                    put(module, shield or armor)
            elif "armor" in slot_type:
                if role in ("warship", "starbase"):
                    put(module, armor)
            elif "scanner" in slot_type:
                put(module, scanner)
        if role == "colonizer" and not colonizer_placed:
            return None, f"no slot for Colonization Module on {hull_name}"
        return slots, None


# =====================================================================
# Compact state summary for the commander prompt
# =====================================================================

def fmt_queue(queue):
    return ",".join(f"{q.get('name') or q.get('production_type')}x"
                    f"{q.get('quantity', 1)}" for q in (queue or [])[:8])


def fmt_waypoints(wps):
    parts = []
    for wp in (wps or [])[:4]:
        dest = wp.get("destination") or (
            f"({wp.get('position_x', 0):.0f},{wp.get('position_y', 0):.0f})")
        task = wp.get("task_type", "NoTask").replace("TaskObj", "")
        suffix = "" if task in ("NoTask", "NoTaskObj") else f" {task}"
        parts.append(f"{dest}@w{wp.get('warp_factor', 0)}{suffix}")
    return " then ".join(parts) if parts else "idle"


def compact_state(state, catalog, max_chars=14000):
    """Compress the player-scoped state into a prompt-friendly digest."""
    lines = []
    year = state.get("turn_year")
    empire = state.get("empire") or {}
    lines.append(f"YEAR {year}. You are empire {empire.get('id')} "
                 f"({empire.get('race_name')}).")

    for rec in state.get("scores") or []:
        lines.append(
            f"SCORE e{rec.get('empire_id')} {rec.get('race_name', '')}: "
            f"score={rec.get('score')} planets={rec.get('planets')} "
            f"tech={rec.get('tech_level')} resources={rec.get('resources')} "
            f"capships={rec.get('capital_ships')} rank={rec.get('rank')}")

    research = state.get("research") or {}
    levels = research.get("levels") or {}
    topics = research.get("topics") or {}
    active = [k for k, v in topics.items() if v] or ["?"]
    lines.append(
        f"RESEARCH budget={research.get('budget')}% field={active[0]} "
        "levels=" + " ".join(f"{k[:4]}{v}" for k, v in levels.items()))

    stars = state.get("stars") or []
    mine = [s for s in stars if s.get("intel") == "owned"]
    lines.append(f"OWNED PLANETS ({len(mine)}):")
    for s in mine[:14]:
        lines.append(
            f"  {s['name']} ({s['position_x']:.0f},{s['position_y']:.0f}) "
            f"hab={s.get('habitability')}% pop={s.get('colonists', 0):,} "
            f"fact={s.get('factories', 0)}/{s.get('operable_factories', 0)} "
            f"mine={s.get('mines', 0)}/{s.get('operable_mines', 0)} "
            f"def={s.get('defenses', 0)} res/yr={s.get('resources_per_year', 0)} "
            f"surf(I/B/G)={s.get('ironium', 0)}/{s.get('boranium', 0)}"
            f"/{s.get('germanium', 0)} "
            f"conc={s.get('ironium_concentration', 0)}/"
            f"{s.get('boranium_concentration', 0)}/"
            f"{s.get('germanium_concentration', 0)} "
            f"queue=[{fmt_queue(s.get('production_queue'))}]"
            + (" STARBASE" if s.get("starbase_key") else "")
            + (f" driver={s.get('mass_driver')}"
               if s.get("mass_driver") else ""))

    fleets = [f for f in state.get("fleets") or []
              if not f.get("is_packet")]
    lines.append(f"FLEETS ({len(fleets)}):")
    for f in fleets[:28]:
        tokens = " ".join(f"{t['design_name']}x{t['quantity']}"
                          for t in f.get("tokens", [])[:4])
        cargo = f.get("cargo") or {}
        cargo_txt = (f" cargo(I/B/G/col)={cargo.get('ironium', 0)}/"
                     f"{cargo.get('boranium', 0)}/"
                     f"{cargo.get('germanium', 0)}/"
                     f"{cargo.get('colonists', 0)}"
                     if any(cargo.values()) else "")
        base = " STARBASE" if f.get("is_starbase") else ""
        lines.append(
            f"  key={f['key']} {f['name']}{base} "
            f"({f['position_x']:.0f},{f['position_y']:.0f})"
            + (f" orbit={f['in_orbit']}" if f.get("in_orbit") else "")
            + f" fuel={f.get('fuel_available', 0)}/"
              f"{f.get('fuel_capacity', 0)}{cargo_txt} [{tokens}] "
              f"orders: {fmt_waypoints(f.get('waypoints'))}")

    scanned = [s for s in stars if s.get("intel") == "scanned"]
    enemy = [s for s in scanned if s.get("owner")]
    free = [s for s in scanned if not s.get("owner")]
    unknown = [s for s in stars if s.get("intel") == "unknown"]
    if enemy:
        lines.append(f"ENEMY PLANETS SEEN ({len(enemy)}):")
        for s in enemy[:10]:
            lines.append(
                f"  {s['name']} ({s['position_x']:.0f},"
                f"{s['position_y']:.0f}) owner=e{s['owner']} "
                f"pop={s.get('colonists', 0):,} "
                f"hab={s.get('habitability')}% "
                f"(report y{s.get('report_year')})")
    lines.append(f"SCANNED UNOWNED PLANETS ({len(free)}), best hab first:")
    for s in sorted(free, key=lambda x: -(x.get("habitability") or -999))[:12]:
        lines.append(
            f"  {s['name']} ({s['position_x']:.0f},{s['position_y']:.0f}) "
            f"hab={s.get('habitability')}% "
            f"conc={s.get('ironium_concentration', 0)}/"
            f"{s.get('boranium_concentration', 0)}/"
            f"{s.get('germanium_concentration', 0)}")
    if unknown:
        sample = ", ".join(
            f"{s['name']}({s['position_x']:.0f},{s['position_y']:.0f})"
            for s in unknown[:10])
        lines.append(f"UNEXPLORED ({len(unknown)}): {sample}")

    foreign = state.get("foreign_fleets") or []
    if foreign:
        lines.append(f"ENEMY FLEET CONTACTS ({len(foreign)}):")
        for f in foreign[:8]:
            lines.append(
                f"  {f.get('name')} owner=e{f.get('owner')} "
                f"({f.get('position_x', 0):.0f},"
                f"{f.get('position_y', 0):.0f}) "
                f"ships={f.get('ship_count')} (y{f.get('report_year')})")

    rels = state.get("relations") or []
    if rels:
        lines.append("RELATIONS: " + " ".join(
            f"e{r['id']}({r.get('race_name', '')})={r.get('relation')}"
            for r in rels))

    lines.append("YOUR SHIP DESIGNS:")
    for d in state.get("designs") or []:
        cost = d.get("cost") or {}
        tags = "".join([
            " colonizer" if d.get("can_colonize") else "",
            " armed" if d.get("has_weapons") else "",
            " starbase" if d.get("is_starbase") else "",
        ])
        lines.append(
            f"  {d['name']} (hull {d.get('hull_name')}){tags} "
            f"mass={d.get('mass')} armor={d.get('armor')} "
            f"cargo={d.get('cargo_capacity')} fuel={d.get('fuel_capacity')} "
            f"cost={cost.get('energy', 0)}res")

    hulls = catalog.buildable_hulls(levels)
    ships = [n for n, sb in hulls if not sb]
    bases = [n for n, sb in hulls if sb]
    lines.append("BUILDABLE HULLS (for new designs): "
                 + ", ".join(ships[:12]))
    if bases:
        lines.append("BUILDABLE STARBASE HULLS: " + ", ".join(bases[:4]))

    msgs = state.get("messages") or []
    lines.append(f"MESSAGES THIS YEAR ({len(msgs)}):")
    for m in msgs[:18]:
        lines.append(f"  [{m.get('type')}] {str(m.get('text'))[:150]}")

    extras = []
    traders = state.get("traders") or []
    for t in traders:
        extras.append(
            f"mystery trader at ({t.get('x', 0):.0f},{t.get('y', 0):.0f}) "
            f"warp {t.get('warp')} (gift so far {t.get('gift_total')}kT, "
            f"threshold {t.get('gift_threshold')}kT)")
    storms = state.get("storms") or []
    if storms:
        extras.append(f"{len(storms)} galactic storm(s)")
    minefields = state.get("minefields") or []
    if minefields:
        extras.append(f"{len(minefields)} known minefield(s)")
    if extras:
        lines.append("PHENOMENA: " + "; ".join(extras))

    victory = state.get("victory_status")
    if victory:
        lines.append("VICTORY: " + json.dumps(victory)[:300])

    text = "\n".join(lines)
    if len(text) > max_chars:
        text = text[:max_chars] + "\n[...state truncated...]"
    return text


# =====================================================================
# Commander (claude -p)
# =====================================================================

class Commander:
    def __init__(self, side, run_dir: Path, model, forensics):
        self.side = side
        self.model = model
        self.forensics = forensics
        self.memo_path = run_dir / f"memo-{side}.md"
        self.orders_dir = run_dir / "orders"
        self.orders_dir.mkdir(exist_ok=True)
        self.last_latency = 0.0

    def read_memo(self):
        if self.memo_path.exists():
            return self.memo_path.read_text()
        return ("(no memo yet - this is your first turn; set out your "
                "opening plan)")

    def write_memo(self, memo):
        words = str(memo).split()
        if len(words) > MEMO_WORD_CAP:
            words = words[:MEMO_WORD_CAP]
        self.memo_path.write_text(" ".join(words) + "\n")

    def build_prompt(self, state_summary, digests):
        persona = PERSONAS[self.side]
        digest_text = "\n".join(
            f"  year {d['year']}: {d['digest']}" for d in digests
        ) or "  (none yet)"
        return "\n\n".join([
            f"You are \"{persona['name']}\", commander of empire "
            f"{self.side} in a game of Stars! (Nova web port). "
            f"This is a live playtest - play to win.",
            "PERSONA: " + persona["text"],
            SHARED_BRIEF,
            "YOUR STRATEGY MEMO (from last turn):\n" + self.read_memo(),
            "RECENT EVENTS (last 5 turns):\n" + digest_text,
            "CURRENT STATE:\n" + state_summary,
            ORDERS_SCHEMA_TEXT,
        ])

    def _call_claude(self, prompt):
        cmd = ["claude", "-p"]
        if self.model:
            cmd += ["--model", self.model]
        log(f"  side {self.side}: calling claude -p "
            f"({len(prompt)} chars)...")
        start = time.time()
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True,
            timeout=CLAUDE_TIMEOUT)
        self.last_latency = time.time() - start
        if proc.returncode != 0:
            raise RuntimeError(
                f"claude -p rc={proc.returncode}: {proc.stderr[:400]}")
        return proc.stdout

    def get_orders(self, turn, state_summary, digests):
        """Call claude -p; parse strict JSON with one retry.

        Returns (orders_dict_or_None, transcript). Never raises.
        """
        prompt = self.build_prompt(state_summary, digests)
        transcript = {"turn": turn, "side": self.side,
                      "persona": PERSONAS[self.side]["name"],
                      "model": self.model or "default",
                      "prompt_chars": len(prompt), "prompt": prompt,
                      "calls": []}
        orders = None
        try:
            response = self._call_claude(prompt)
            transcript["calls"].append({
                "latency_s": round(self.last_latency, 1),
                "response_chars": len(response), "response": response})
            orders, error = parse_orders(response)
            if orders is None:
                self.forensics.event("invalid_json", {
                    "side": self.side, "error": error,
                    "response_head": response[:400]})
                retry_prompt = (
                    prompt + "\n\nYour previous reply could not be "
                    f"parsed as JSON ({error}). Previous reply:\n"
                    + response[:2000]
                    + "\n\nReply again with ONLY the corrected JSON "
                      "object, nothing else.")
                response = self._call_claude(retry_prompt)
                transcript["calls"].append({
                    "retry": True,
                    "latency_s": round(self.last_latency, 1),
                    "response_chars": len(response),
                    "response": response})
                orders, error = parse_orders(response)
                if orders is None:
                    self.forensics.event("invalid_json", {
                        "side": self.side, "retry": True, "error": error,
                        "response_head": response[:400]})
        except Exception as e:
            self.forensics.event("commander_error", {
                "side": self.side, "error": repr(e)[:500]})
            transcript["calls"].append({"error": repr(e)[:500]})
        transcript["parsed"] = orders is not None
        path = self.orders_dir / f"{turn:04d}-{self.side}.json"
        path.write_text(json.dumps(transcript, indent=1))
        return orders, transcript


def parse_orders(text):
    """Parse the commander's reply into an orders dict.

    Strips markdown fences defensively, then brace-scans for the first
    complete JSON object. Returns (dict, None) or (None, error).
    """
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj, None
    except ValueError:
        pass
    start = s.find("{")
    if start < 0:
        return None, "no JSON object found"
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(s[start:i + 1])
                    if isinstance(obj, dict):
                        return obj, None
                    return None, "top-level JSON is not an object"
                except ValueError as e:
                    return None, f"JSON error: {e}"
    return None, "unbalanced braces"


# =====================================================================
# Order application
# =====================================================================

class OrderApplier:
    """Maps parsed commander orders onto real API calls."""

    def __init__(self, api: Api, game_id, forensics: Forensics,
                 catalog: Catalog):
        self.api = api
        self.game_id = game_id
        self.forensics = forensics
        self.catalog = catalog
        self.accepted = 0
        self.rejected = 0

    def _command(self, side, ctype, cdata):
        status, resp = self.api.request(
            "POST", f"/games/{self.game_id}/empires/{side}/commands",
            {"command_type": ctype, "command_data": cdata})
        ok = status == 200 and resp.get("status") in ("applied", "unchanged")
        if ok:
            self.accepted += 1
        else:
            self.rejected += 1
            self.forensics.event("order_rejected", {
                "side": side, "command_type": ctype, "payload": cdata,
                "http_status": status, "response": resp})
        return ok

    def apply(self, side, orders, state):
        """Apply one side's orders. Never raises."""
        self.accepted = self.rejected = 0
        try:
            self._apply_inner(side, orders, state)
        except Exception as e:
            self.forensics.event("commander_error", {
                "side": side, "phase": "apply_orders",
                "error": repr(e)[:600]})
        return self.accepted, self.rejected

    def _apply_inner(self, side, orders, state):
        levels = (state.get("research") or {}).get("levels") or {}

        # -- designs first so production can reference them ----------
        for spec in (orders.get("designs") or [])[:2]:
            if not isinstance(spec, dict):
                continue
            name = str(spec.get("name") or "").strip()[:40]
            hull = str(spec.get("hull") or "").strip()
            role = str(spec.get("role") or "warship").strip().lower()
            if not name or not hull:
                continue
            slots, err = self.catalog.build_slots(hull, role, levels)
            if err:
                self.rejected += 1
                self.forensics.event("order_rejected", {
                    "side": side, "command_type": "design",
                    "payload": spec, "response": {"error": err}})
                continue
            self._command(side, "design", {
                "mode": "Add",
                "design": {"name": name, "hull": hull, "slots": slots}})

        # design keys may have changed; refresh for production lookup
        _, state = self.api.request(
            "GET", f"/games/{self.game_id}/empires/{side}/state")
        designs = {d["name"]: d for d in state.get("designs") or []}
        owned = {s["name"]: s for s in state.get("stars") or []
                 if s.get("intel") == "owned"}
        fleets = {f["key"]: f for f in state.get("fleets") or []}
        stars_by_name = {s["name"]: s for s in state.get("stars") or []}

        # -- research ------------------------------------------------
        research = orders.get("research")
        if isinstance(research, dict):
            field = str(research.get("field") or "")
            budget = research.get("budget")
            try:
                budget = max(0, min(100, int(budget)))
            except (TypeError, ValueError):
                budget = None
            if field in RESEARCH_FIELDS and budget is not None:
                topics = {k: 0 for k in RESEARCH_FIELDS}
                topics[field] = 1
                self._command(side, "research", {
                    "budget": budget, "topics": {"levels": topics}})

        # -- production (replace queue per star) ---------------------
        for entry in (orders.get("production") or [])[:8]:
            if not isinstance(entry, dict):
                continue
            star = owned.get(str(entry.get("star") or ""))
            if star is None:
                self.rejected += 1
                self.forensics.event("order_rejected", {
                    "side": side, "command_type": "production",
                    "payload": entry,
                    "response": {"error": "star not owned/found"}})
                continue
            queue_len = len(star.get("production_queue") or [])
            for _ in range(queue_len):
                self._command(side, "production", {
                    "mode": "Delete", "star_key": star["name"],
                    "index": 0})
            index = 0
            for item in (entry.get("items") or [])[:6]:
                if not isinstance(item, dict):
                    continue
                ptype = str(item.get("type") or "").upper()
                if ptype not in PRODUCTION_TYPES:
                    continue
                try:
                    qty = max(1, min(500, int(item.get("quantity", 1))))
                except (TypeError, ValueError):
                    qty = 1
                order = {"production_type": ptype, "quantity": qty,
                         "name": str(item.get("name") or ptype.title())}
                if ptype in ("SHIP", "STARBASE"):
                    design = designs.get(str(item.get("name") or ""))
                    if design is None:
                        self.rejected += 1
                        self.forensics.event("order_rejected", {
                            "side": side, "command_type": "production",
                            "payload": item,
                            "response": {"error": "unknown design"}})
                        continue
                    order["design_key"] = "0x%x" % design["key"]
                    order["name"] = design["name"]
                if self._command(side, "production", {
                        "mode": "Add", "star_key": star["name"],
                        "index": index, "production_order": order}):
                    index += 1

        # -- fleet waypoints (replace) -------------------------------
        for entry in (orders.get("fleets") or [])[:30]:
            if not isinstance(entry, dict):
                continue
            try:
                key = int(entry.get("fleet_key"))
            except (TypeError, ValueError):
                continue
            fleet = fleets.get(key)
            if fleet is None:
                self.rejected += 1
                self.forensics.event("order_rejected", {
                    "side": side, "command_type": "waypoint",
                    "payload": entry,
                    "response": {"error": "fleet not owned/found"}})
                continue
            for _ in range(len(fleet.get("waypoints") or [])):
                self._command(side, "waypoint", {
                    "mode": "Delete", "fleet_key": key, "index": 0})
            index = 0
            for wp in (entry.get("waypoints") or [])[:4]:
                if not isinstance(wp, dict):
                    continue
                target = wp.get("target")
                destination = ""
                if isinstance(target, str) and target in stars_by_name:
                    star = stars_by_name[target]
                    x, y = star["position_x"], star["position_y"]
                    destination = target
                elif (isinstance(target, (list, tuple))
                        and len(target) == 2):
                    try:
                        x, y = float(target[0]), float(target[1])
                    except (TypeError, ValueError):
                        continue
                else:
                    self.rejected += 1
                    self.forensics.event("order_rejected", {
                        "side": side, "command_type": "waypoint",
                        "payload": wp,
                        "response": {"error": "unknown target"}})
                    continue
                try:
                    warp = max(1, min(10, int(wp.get("warp", 6))))
                except (TypeError, ValueError):
                    warp = 6
                task = str(wp.get("task") or "none").lower()
                task_obj = ({"type": "ColoniseTask"}
                            if task in ("colonize", "colonise")
                            else {"type": "NoTask"})
                if self._command(side, "waypoint", {
                        "mode": "Add", "fleet_key": key, "index": index,
                        "waypoint": {
                            "position_x": x, "position_y": y,
                            "warp_factor": warp,
                            "destination": destination,
                            "task": task_obj}}):
                    index += 1

        # -- cargo transfers (fleet <-> orbited star) ----------------
        for entry in (orders.get("cargo") or [])[:12]:
            if not isinstance(entry, dict):
                continue
            try:
                key = int(entry.get("fleet_key"))
            except (TypeError, ValueError):
                continue
            body = {"empire_id": side}
            for mineral in ("ironium", "boranium", "germanium",
                            "colonists"):
                try:
                    body[mineral] = int(entry.get(mineral, 0))
                except (TypeError, ValueError):
                    body[mineral] = 0
            status, resp = self.api.request(
                "POST", f"/games/{self.game_id}/fleets/{key}/cargo",
                body)
            if status == 200:
                self.accepted += 1
            else:
                self.rejected += 1
                self.forensics.event("order_rejected", {
                    "side": side, "command_type": "cargo",
                    "payload": entry, "http_status": status,
                    "response": resp})

        # -- relations ----------------------------------------------
        for entry in (orders.get("relations") or [])[:4]:
            if not isinstance(entry, dict):
                continue
            try:
                target = int(entry.get("empire_id"))
            except (TypeError, ValueError):
                continue
            relation = str(entry.get("relation") or "")
            if relation not in ("Enemy", "Neutral", "Friend"):
                continue
            self._command(side, "relation", {
                "target_empire_id": target, "relation": relation})

        # -- mineral packets ----------------------------------------
        for entry in (orders.get("packets") or [])[:4]:
            if not isinstance(entry, dict):
                continue
            cdata = {"star": entry.get("star"),
                     "target": entry.get("target")}
            for k in ("warp", "ironium", "boranium", "germanium"):
                if entry.get(k) is not None:
                    cdata[k] = entry.get(k)
            self._command(side, "fling_packet", cdata)


# =====================================================================
# Playtest orchestration
# =====================================================================

class Playtest:
    def __init__(self, args):
        self.args = args
        self.run_dir = REPO_ROOT / "results" / "playtest" / args.name
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.run_dir / "state.json"
        self.digests_path = self.run_dir / "digests.jsonl"
        self.forensics = Forensics(self.run_dir)
        self.server = PlaytestServer(self.run_dir)
        self.api = Api(self.server, self.forensics)
        self.commanders = {
            side: Commander(side, self.run_dir, args.model,
                            self.forensics)
            for side in SIDES}
        self.checkpoint = None
        self.catalog = None

    # -- checkpointing -----------------------------------------------

    def save_checkpoint(self):
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.checkpoint, indent=1))
        tmp.replace(self.state_path)

    def setup(self):
        if self.state_path.exists() and not self.args.resume:
            raise RuntimeError(
                f"checkpoint {self.state_path} already exists - pass "
                "--resume to continue that run, or remove the run "
                "directory to start fresh")
        self.server.start()
        self.catalog = Catalog(self.api)
        if self.args.resume and self.state_path.exists():
            self.checkpoint = json.loads(self.state_path.read_text())
            status, game = self.api.request(
                "GET", f"/games/{self.checkpoint['game_id']}")
            if status != 200:
                raise RuntimeError(
                    f"resume failed: game {self.checkpoint['game_id']} "
                    f"not found in playtest db ({game})")
            log(f"resumed game {self.checkpoint['game_id']} at year "
                f"{game['turn']}, next playtest turn "
                f"{self.checkpoint['next_turn']}")
        else:
            status, game = self.api.request("POST", "/games/", {
                "name": self.args.name,
                "player_count": 2,
                "universe_size": self.args.size,
                "seed": self.args.seed,
                "mystery_trader": True,
                "human_players": 2,
            })
            if status != 200:
                raise RuntimeError(f"game creation failed: {game}")
            self.checkpoint = {
                "game_id": game["id"], "name": self.args.name,
                "seed": self.args.seed, "size": self.args.size,
                "model": self.args.model, "turns_target": self.args.turns,
                "next_turn": 1, "year": game["turn"],
                "server_log_offset": 0, "fleet_history": {},
                "memo_paths": {str(s): str(self.commanders[s].memo_path)
                               for s in SIDES},
                "done": False, "victor": None,
                "created": now_iso(),
            }
            self.save_checkpoint()
            log(f"created game {game['id']} seed={self.args.seed} "
                f"size={self.args.size} year={game['turn']}")

    # -- per-side helpers --------------------------------------------

    def recent_digests(self, side):
        if not self.digests_path.exists():
            return []
        records = []
        with open(self.digests_path) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if rec.get("side") == side:
                    records.append(rec)
        return records[-5:]

    def get_state(self, side):
        status, state = self.api.request(
            "GET",
            f"/games/{self.checkpoint['game_id']}/empires/{side}/state")
        if status != 200:
            raise RuntimeError(f"state fetch failed for side {side}: "
                               f"{state}")
        return state

    def command_side(self, turn, side):
        """One side's whole decision+application phase. Never raises."""
        stats = {"accepted": 0, "rejected": 0, "latency": [],
                 "strategy": None, "parsed": False}
        try:
            state = self.get_state(side)
            summary = compact_state(state, self.catalog)
            commander = self.commanders[side]
            orders, transcript = commander.get_orders(
                turn, summary, self.recent_digests(side))
            stats["latency"] = [c.get("latency_s") for c in
                                transcript.get("calls", [])
                                if c.get("latency_s") is not None]
            if orders is not None:
                stats["parsed"] = True
                stats["strategy"] = str(orders.get("strategy") or "")[:300]
                if orders.get("memo"):
                    commander.write_memo(orders["memo"])
                observations = orders.get("observations") or []
                if isinstance(observations, list) and observations:
                    self.forensics.bug_report(side, observations)
                applier = OrderApplier(
                    self.api, self.checkpoint["game_id"],
                    self.forensics, self.catalog)
                stats["accepted"], stats["rejected"] = applier.apply(
                    side, orders, state)
        except Exception as e:
            self.forensics.event("commander_error", {
                "side": side, "phase": "command_side",
                "error": repr(e)[:600]})
        # Always submit so the year can advance (empty orders if the
        # commander failed) - loop resilience over completeness
        try:
            self.api.request(
                "POST",
                f"/games/{self.checkpoint['game_id']}/empires/{side}"
                "/submit-orders")
        except Exception as e:
            self.forensics.event("commander_error", {
                "side": side, "phase": "submit_orders",
                "error": repr(e)[:400]})
        return stats

    # -- turn generation ---------------------------------------------

    def generate(self):
        """Advance the year. Returns (new_year, wall_time) or None."""
        gid = self.checkpoint["game_id"]
        start = time.time()
        for attempt in range(3):
            status, resp = self.api.request(
                "POST", f"/games/{gid}/turn/generate", timeout=600)
            if status == 200:
                return resp["turn"], time.time() - start
            if status == 409:
                # someone has not submitted - submit and retry
                _, subs = self.api.request("GET", f"/games/{gid}/submissions")
                for row in subs if isinstance(subs, list) else []:
                    if not row.get("turn_submitted"):
                        self.api.request(
                            "POST",
                            f"/games/{gid}/empires/"
                            f"{row['empire_id']}/submit-orders")
                continue
            self.forensics.event("turn_failed", {
                "http_status": status, "response": resp,
                "attempt": attempt})
            time.sleep(2)
        return None

    # -- forensic detectors ------------------------------------------

    def detect_anomalies(self, side, state, turn):
        gid = state.get("game_id")
        for star in state.get("stars") or []:
            if star.get("intel") != "owned":
                continue
            for field in ("colonists", "factories", "mines", "defenses",
                          "ironium", "boranium", "germanium",
                          "resources_per_year"):
                value = star.get(field)
                if isinstance(value, (int, float)) and value < 0:
                    self.forensics.event("negative_value", {
                        "side": side, "object": f"star {star['name']}",
                        "field": field, "value": value})
            colonists = star.get("colonists") or 0
            if colonists > 10_000_000_000:
                self.forensics.event("absurd_value", {
                    "side": side, "object": f"star {star['name']}",
                    "field": "colonists", "value": colonists})
        history = self.checkpoint.setdefault("fleet_history", {})
        side_hist = history.setdefault(str(side), {})
        seen = set()
        for fleet in state.get("fleets") or []:
            if fleet.get("fuel_available", 0) < 0:
                self.forensics.event("negative_value", {
                    "side": side, "object": f"fleet {fleet['name']}",
                    "field": "fuel_available",
                    "value": fleet["fuel_available"]})
            for mineral, value in (fleet.get("cargo") or {}).items():
                if isinstance(value, (int, float)) and value < 0:
                    self.forensics.event("negative_value", {
                        "side": side, "object": f"fleet {fleet['name']}",
                        "field": f"cargo.{mineral}", "value": value})
            # stuck fleet detector: waypoints set but position frozen
            key = str(fleet.get("key"))
            seen.add(key)
            pos = (round(fleet.get("position_x", 0), 1),
                   round(fleet.get("position_y", 0), 1))
            has_orders = bool(fleet.get("waypoints")) \
                and not fleet.get("is_starbase")
            prev = side_hist.get(key)
            if (has_orders and prev and tuple(prev["pos"]) == pos
                    and prev.get("with_orders")):
                streak = prev.get("streak", 0) + 1
            else:
                streak = 0
            side_hist[key] = {"pos": list(pos), "streak": streak,
                              "with_orders": has_orders}
            if streak >= STUCK_TURNS:
                wp0 = (fleet.get("waypoints") or [{}])[0]
                self.forensics.event("stuck_fleet", {
                    "side": side, "fleet": fleet["name"],
                    "key": fleet.get("key"), "position": list(pos),
                    "turns_stuck": streak,
                    "destination": wp0.get("destination"),
                    "warp": wp0.get("warp_factor")})
        for key in list(side_hist):
            if key not in seen:
                del side_hist[key]
        nonfinite = find_nonfinite(state)
        if nonfinite:
            self.forensics.event("absurd_value", {
                "side": side, "field": "NaN/inf",
                "paths": nonfinite[:20]})

    def scrape_server_log(self):
        offset = self.checkpoint.get("server_log_offset", 0)
        path = self.server.server_log
        if not path.exists():
            return
        size = path.stat().st_size
        if size < offset:
            offset = 0  # rotated/truncated
        with open(path, errors="replace") as f:
            f.seek(offset)
            chunk = f.read()
        self.checkpoint["server_log_offset"] = size
        for match in re.finditer(
                r"Traceback \(most recent call last\):\n"
                r"(?:.+\n)+?\S.*", chunk):
            self.forensics.event("server_traceback", {
                "traceback": match.group(0)[-3000:]})

    def digest_side(self, side, state, turn, stats):
        owned = [s for s in state.get("stars") or []
                 if s.get("intel") == "owned"]
        pop = sum(s.get("colonists", 0) for s in owned)
        my_score = next(
            (r for r in state.get("scores") or []
             if r.get("empire_id") == side), {})
        msgs = state.get("messages") or []
        highlights = "; ".join(
            f"[{m.get('type')}] {str(m.get('text'))[:90]}"
            for m in msgs[:3])
        digest = (
            f"planets={len(owned)} pop={pop:,} "
            f"fleets={len(state.get('fleets') or [])} "
            f"score={my_score.get('score')} "
            f"orders {stats['accepted']} ok/{stats['rejected']} "
            f"rejected; strategy: {stats.get('strategy') or '(none)'}"
            + (f"; events: {highlights}" if highlights else ""))
        append_jsonl(self.digests_path, {
            "turn": turn, "year": state.get("turn_year"),
            "side": side, "digest": digest})
        return digest

    # -- main loop ----------------------------------------------------

    def play_turn(self, turn):
        """One full turn for both sides. Returns True if year advanced."""
        self.forensics.turn = turn
        self.forensics.year = self.checkpoint["year"]
        self.forensics.turn_events = 0
        turn_t0 = time.time()
        _console.rule(
            f"[bold medium_purple]Turn {turn}/"
            f"{self.checkpoint['turns_target']}"
            f" - Year {self.checkpoint['year']}[/bold medium_purple]",
            style="medium_purple")
        stats = {}
        for side in SIDES:
            stats[side] = self.command_side(turn, side)
            latency = ",".join(f"{s:.0f}s" for s in stats[side]["latency"])
            colour = SIDE_STYLE[side]
            ok = stats[side]["accepted"]
            rej = stats[side]["rejected"]
            rej_style = "indian_red" if rej else "dark_sea_green"
            strategy = (stats[side].get("strategy") or "(none)")[:110]
            strategy = strategy.replace("[", "(").replace("]", ")")
            rlog(f"[bold {colour}]{PERSONAS[side]['name']}[/bold {colour}] "
                 f"orders [dark_sea_green]{ok} ok[/dark_sea_green]/"
                 f"[{rej_style}]{rej} rejected[/{rej_style}] "
                 f"[dim]latency {latency}[/dim]\n"
                 f"    [slate_blue1]strategy:[/slate_blue1] "
                 f"[grey70]{strategy}[/grey70]")

        generated = self.generate()
        if generated is None:
            self.forensics.event("turn_failed", {
                "turn": turn, "reason": "year did not advance"})
            log(f"turn {turn}: YEAR DID NOT ADVANCE (forensic logged)")
            return False
        year, wall = generated
        self.checkpoint["year"] = year
        self.forensics.year = year
        self.forensics.event("turn_time", {
            "seconds": round(wall, 2),
            "anomaly": wall > TURN_TIME_ANOMALY})

        # post-turn forensics and state dump
        dump = {"turn": turn, "year": year, "sides": {}}
        victor = None
        for side in SIDES:
            try:
                state = self.get_state(side)
            except Exception as e:
                self.forensics.event("turn_failed", {
                    "turn": turn, "side": side,
                    "reason": f"post-turn state fetch: {e!r}"})
                continue
            dump["sides"][str(side)] = state
            self.detect_anomalies(side, state, turn)
            self.digest_side(side, state, turn, stats[side])
            victor = victor or state.get("victor")
        (self.run_dir / f"turn{turn:04d}.json").write_text(
            json.dumps(dump))
        self.scrape_server_log()

        if victor:
            self.checkpoint["victor"] = victor
            self.checkpoint["done"] = True
            self.forensics.event("game_over", {"victor": victor})
            rlog(f"[bold dark_goldenrod]GAME OVER at year {year}: "
                 f"victor empire {victor}[/bold dark_goldenrod]")

        # single multiline rich summary: scores, forensics, pace, ETA
        walls = getattr(self, "_turn_walls", [])
        walls.append(time.time() - turn_t0)
        self._turn_walls = walls[-10:]
        remaining = self.checkpoint["turns_target"] - turn
        pace = sum(self._turn_walls) / len(self._turn_walls)
        eta_h = pace * remaining / 3600
        score_bits = []
        for side in SIDES:
            st = dump["sides"].get(str(side)) or {}
            rec = next((r for r in st.get("scores") or []
                        if r.get("empire_id") == side), {})
            owned = sum(1 for s in st.get("stars") or []
                        if s.get("intel") == "owned")
            score_bits.append(
                f"[{SIDE_STYLE[side]}]{PERSONAS[side]['name']}[/"
                f"{SIDE_STYLE[side]}] score "
                f"[light_sea_green]{rec.get('score', '?')}"
                f"[/light_sea_green] planets "
                f"[dark_sea_green]{owned}[/dark_sea_green] fleets "
                f"[dark_sea_green]{len(st.get('fleets') or [])}"
                f"[/dark_sea_green]")
        ev = self.forensics.turn_events
        ev_style = "dark_goldenrod" if ev else "dark_sea_green"
        rlog(f"[bold dark_sea_green]turn {turn} done[/bold dark_sea_green] "
             f"year [light_sea_green]{year}[/light_sea_green]  "
             + "  ".join(score_bits) + "\n"
             f"    generation [light_sea_green]{wall:.1f}s[/light_sea_green]"
             f"  forensic events [{ev_style}]{ev}[/{ev_style}]"
             f"  pace [light_sea_green]{pace/60:.1f}m/turn"
             f"[/light_sea_green]  ETA "
             f"[light_sea_green]~{eta_h:.1f}h[/light_sea_green]")
        return True

    def run(self):
        failures = 0
        try:
            self.setup()
            while (self.checkpoint["next_turn"]
                    <= self.checkpoint["turns_target"]
                    and not self.checkpoint["done"]):
                turn = self.checkpoint["next_turn"]
                try:
                    advanced = self.play_turn(turn)
                except Exception as e:
                    # belt and braces: play_turn should not raise
                    self.forensics.event("turn_failed", {
                        "turn": turn, "reason": repr(e)[:800]})
                    log(f"turn {turn} raised (logged): {e!r}")
                    advanced = False
                if advanced:
                    failures = 0
                    self.checkpoint["next_turn"] = turn + 1
                else:
                    failures += 1
                    if failures >= 5:
                        log("5 consecutive failed turns - stopping "
                            "(run is resumable with --resume)")
                        break
                    time.sleep(3)
                self.save_checkpoint()
            self.save_checkpoint()
            log(f"playtest finished: played through turn "
                f"{self.checkpoint['next_turn'] - 1} of "
                f"{self.checkpoint['turns_target']}, year "
                f"{self.checkpoint['year']}, victor "
                f"{self.checkpoint['victor']}")
        finally:
            self.server.stop()


def main():
    ap = argparse.ArgumentParser(
        description="LLM-vs-LLM playtest harness (claude -p both sides)")
    ap.add_argument("--name", required=True,
                    help="run name (results/playtest/<name>/)")
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--turns", type=int, default=100)
    ap.add_argument("--size", default="small",
                    choices=["tiny", "small", "medium"])
    ap.add_argument("--resume", action="store_true",
                    help="continue an interrupted run")
    ap.add_argument("--model", default=None,
                    help="passthrough to claude -p --model")
    args = ap.parse_args()

    playtest = Playtest(args)
    playtest.run()


if __name__ == "__main__":
    main()
