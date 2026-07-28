#!/usr/bin/env python3
"""
Balance sweep over the doctrine modifier tables (stance and posture).

WHAT IS TUNED, AND WHAT IS NOT
------------------------------
Only STANCE_MODIFIERS and POSTURE_MODIFIERS in
backend/server/battle/battle_plan.py are swept. Those two tables are
this port's own invention - canonical Stars! tactics carry no stat
modifiers - so they are the only numbers that may be fitted.
backend/data/components.xml is canon ported from the original game and
is never touched, proposed or read by this script. Three canonical
mechanics are still unimplemented (missile double damage to armour,
gatling area sweep, hold-at-range movement doctrine), so any
weapon-class imbalance this sweep exposes is a report, not a target.

Candidates are applied IN MEMORY by swapping rows into the live
module-level dicts. Nothing on disk is edited: every consumer reaches
the tables through BattlePlan.stance_modifiers / .posture_modifiers,
which resolve against battle_plan.STANCE_MODIFIERS and
battle_plan.POSTURE_MODIFIERS at call time, so mutating those dicts is
enough and one process can evaluate the whole grid.

SEARCH STRATEGY - full deterministic grid on a coarse lattice
-------------------------------------------------------------
The two tables are searched independently, which is not an
approximation but a property of the harness: the stance round-robin
builds its variants from the Balanced admiralty plan with
posture="Standard", whose modifier row is the identity, and the
posture round-robin holds stance="Balanced", likewise the identity. So
a stance candidate's score cannot depend on POSTURE_MODIFIERS and vice
versa, and the product space never has to be enumerated.

That factorisation leaves two spaces small enough for exhaustive
search: 40,960 stance candidates and 18,432 posture candidates on the
lattice below, at roughly one second per evaluation, parallel over the
box's cores. A full grid was chosen over anything adaptive for three
reasons - it is exactly reproducible, it cannot get stuck in the local
optimum a coordinate descent would find in a space with booleans in
it, and at this size it is not meaningfully slower. Candidate order is
itertools.product over fixed, sorted lattices, so the enumeration is
identical on every run; --sample subsets it through a seeded
random.Random, which is likewise deterministic.

Each row is swept only over the levers that row is documented to move.
Giving Brace a splash multiplier or Scatter a range bonus would invent
a new posture rather than tune the one that ships, so those cells stay
pinned at the identity. Balanced and Standard are pinned entirely:
they are the no-modifier reference every other option is measured
against, and a save written before doctrine existed must keep loading
as them.

THE OBJECTIVE
-------------
Three terms, evaluated per force pairing exactly as
tests/unit/test_battle_degeneracy.py does, on the same round-robin
(imported, not reimplemented):

  HARD  no option unbeaten - every option must have a force pairing
        where some other option was the better order
  HARD  no option inert - every option must be the better order in
        some force pairing
  SOFT  totals spread - best option's total wins over worst, capped at
        MAX_SPREAD (1.25, the value the shipped test asserts)

plus one term the shipped test cannot see:

  LIVENESS  the fraction of the nine force pairings in which changing
        the option changes the outcome. A pairing where every
        head-to-head cell ties is a pairing the weapon matchup decided
        on its own; the degeneracy test passes on it, because a tie is
        neither a win nor a loss, while the doctrine layer sat there
        doing nothing. This is the weakness the sweep exists to fix.

See score() for the exact scalar being maximised.

Training seeds are the three the shipped test uses; held-out seeds are
three the optimiser never sees. A candidate that clears the gates on
training and fails them on held-out is rejected and counted, because a
modifier table fitted to three seeds is noise wearing a balance label.

PROVISIONAL BY CONSTRUCTION
---------------------------
Another workflow is fixing a proven move-order bias in
RonBattleEngine._move_stacks. Every record carries the engine
fingerprint (git HEAD plus a digest of the working-tree battle files)
so a later run can tell whether a number is stale. Numbers produced
before that fix lands are provisional.

USAGE
-----
    python scripts/balance_sweep.py --mode validate
    python scripts/balance_sweep.py --mode sweep --axis stance
    python scripts/balance_sweep.py --mode report --axis stance --top 10
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import multiprocessing as mp
import os
import random
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rich.console import Console
from rich.progress import (BarColumn, MofNCompleteColumn, Progress,
                           SpinnerColumn, TaskProgressColumn, TextColumn,
                           TimeElapsedColumn, TimeRemainingColumn)
from rich.table import Table

from backend.server.battle import battle_plan
from backend.server.battle.battle_plan import (PostureModifiers,
                                               StanceModifiers)
from tests.unit import test_battle_degeneracy as degen

console = Console()

RESULTS_DIR = REPO_ROOT / "results" / "balance"

# The spread cap the shipped test asserts on the general-purpose axes
MAX_SPREAD = 1.25

# The three seeds tests/unit/test_battle_degeneracy.py runs on. Using
# them as the training set is deliberate: a candidate's training score
# is then literally the number the shipped test will see.
TRAINING_SEEDS: Tuple[int, ...] = tuple(degen.SEEDS)

# Never seen by the optimiser. Fixed constants, not drawn at runtime,
# so a held-out score is reproducible across runs and machines.
HELDOUT_SEEDS: Tuple[int, ...] = (10203040, 60606, 987654321)

# Working-tree files whose contents change what a battle does. Hashed
# into every record so a stale number is recognisable as stale.
ENGINE_FILES = (
    "backend/server/battle/ron_battle_engine.py",
    "backend/server/battle/battle_plan.py",
    "backend/server/battle/stack.py",
    "backend/server/battle/battle_engine.py",
    "backend/server/battle/weapon_details.py",
    "backend/server/battle/battle_step.py",
    "backend/server/battle/battle_report.py",
    "backend/core/components/ship_role.py",
    "tests/unit/test_battle_degeneracy.py",
)


# ---------------------------------------------------------------- lattice

# Aggressive buys firing order and missile guidance with shields and,
# at its sharpest, with the right to break off at all. Defensive is
# its mirror. Balanced is pinned at the identity and is not swept.
STANCE_LATTICE: Dict[str, Dict[str, Sequence]] = {
    "Aggressive": {
        "initiative": (0, 1, 2, 3),
        "missile_accuracy": (1.00, 1.05, 1.10, 1.20),
        "shields": (0.70, 0.80, 0.90, 1.00),
        "may_disengage": (False, True),
        "disengage_moves": (7,),
    },
    "Defensive": {
        "initiative": (0, -1, -2, -3),
        "missile_accuracy": (1.00, 0.95, 0.90, 0.80),
        "shields": (1.00, 1.10, 1.25, 1.40),
        "may_disengage": (True,),
        "disengage_moves": (3, 4, 5, 6, 7),
    },
}

# Brace fights as an emplacement - shields and reach, paid for by
# never closing and by deliberate gunnery. Scatter is spread out -
# evasion against guided weapons and a shorter break-off, paid for
# with concentration of fire. Standard is pinned at the identity.
POSTURE_LATTICE: Dict[str, Dict[str, Sequence]] = {
    "Brace": {
        "holds_position": (True, False),
        "shields": (1.00, 1.15, 1.30, 1.45),
        "splash_taken": (1.0,),
        "incoming_missile_accuracy": (1.0,),
        "damage_dealt": (0.70, 0.80, 0.90, 1.00),
        "weapon_range_bonus": (0, 1, 2),
        "disengage_moves_delta": (0,),
    },
    "Scatter": {
        "holds_position": (False,),
        "shields": (1.0,),
        "splash_taken": (0.25, 0.50, 0.75, 1.00),
        "incoming_missile_accuracy": (0.70, 0.85, 1.00),
        "damage_dealt": (0.75, 0.85, 0.95, 1.00),
        "weapon_range_bonus": (0,),
        "disengage_moves_delta": (0, -1, -2, -3),
    },
}

AXES = {
    "stance": (STANCE_LATTICE, StanceModifiers, battle_plan.STANCE_MODIFIERS),
    "posture": (POSTURE_LATTICE, PostureModifiers,
                battle_plan.POSTURE_MODIFIERS),
}


def enumerate_candidates(axis: str) -> Iterable[Dict[str, dict]]:
    """
    Every point of the coarse lattice, in a fixed order.

    itertools.product over sorted rows and sorted field names, so the
    n-th candidate is the same candidate on every run and on every
    machine.
    """
    lattice = AXES[axis][0]
    rows = sorted(lattice)
    per_row = []
    for row in rows:
        fields = sorted(lattice[row])
        per_row.append([
            dict(zip(fields, values))
            for values in itertools.product(*(lattice[row][f]
                                              for f in fields))
        ])
    for combo in itertools.product(*per_row):
        yield {row: values for row, values in zip(rows, combo)}


def candidate_id(axis: str, candidate: Dict[str, dict]) -> str:
    """Stable hash of a candidate - the resume key in the JSONL."""
    blob = json.dumps({"axis": axis, "candidate": candidate},
                      sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def shipped_candidate(axis: str) -> Dict[str, dict]:
    """The values currently in battle_plan.py, as a candidate."""
    lattice, _cls, table = AXES[axis]
    return {row: {field: getattr(table[row], field)
                  for field in sorted(lattice[row])}
            for row in sorted(lattice)}


# ------------------------------------------------------------ application

@contextmanager
def applied(axis: str, candidate: Dict[str, dict]):
    """
    Swap a candidate into the live modifier dict, then put it back.

    In memory only. The dict object is mutated in place rather than
    rebound, because every consumer resolves through the same object.
    """
    _lattice, cls, table = AXES[axis]
    saved = dict(table)
    try:
        for row, fields in candidate.items():
            table[row] = cls(**fields)
        yield
    finally:
        table.clear()
        table.update(saved)


@contextmanager
def seeds_of(values: Sequence[int]):
    """Point the imported harness at a seed set, then put it back."""
    saved = degen.SEEDS
    degen.SEEDS = tuple(values)
    try:
        yield
    finally:
        degen.SEEDS = saved


def _round_robin_for(axis: str):
    """The shipped harness, one axis at a time. Imported, not copied."""
    if axis == "stance":
        options = {name: degen._variants(name, stance=name)
                   for name in degen.STANCES}
    elif axis == "posture":
        options = {name: degen._variants(name, posture=name)
                   for name in degen.POSTURES}
    else:
        raise ValueError(axis)
    return degen._round_robin(options)


def _admiralty_round_robin():
    """
    The standard-plan matrix, which mixes both axes.

    Not part of per-candidate scoring - it is nine times the work and
    the two axes cannot be searched independently through it - but a
    table that breaks test_no_standard_plan_wins_every_matchup cannot
    ship, so the finalists are gated on it.
    """
    plans = {}
    for name, plan in battle_plan.ADMIRALTY_PLANS.items():
        copy = battle_plan.BattlePlan.from_dict(plan.to_dict())
        copy.attack = "Everyone"
        plans[name] = (copy,)
    return degen._round_robin(plans)


# -------------------------------------------------------------- objective

@dataclass
class Metrics:
    """One round-robin, reduced to the quantities the objective reads."""
    names: List[str]
    totals: Dict[str, int]
    unbeaten: List[str]       # options no other option ever out-scored
    inert: List[str]          # options that were never the better order
    spread: float             # best total / worst total
    live_pairings: int        # pairings where the option choice mattered
    total_pairings: int
    live_comparisons: int     # head-to-head cells that did not tie
    total_comparisons: int
    # Per-pairing liveness, in PAIRINGS order. A pairing that is dead
    # for every candidate is a force matchup the weapon classes decide
    # on their own, which is a finding about the weapon catalogue and
    # not something a modifier table can be asked to fix.
    live_by_pairing: Tuple[int, ...] = ()
    # The shipped test caps the spread on the general-purpose axes and
    # deliberately does not cap it on the standard plans, where the
    # specialists are meant to lose a stand-up fight. None means no cap.
    spread_cap: Optional[float] = MAX_SPREAD

    @property
    def hard_ok(self) -> bool:
        return not self.unbeaten and not self.inert

    @property
    def spread_ok(self) -> bool:
        return self.spread_cap is None or self.spread <= self.spread_cap

    @property
    def live_pairing_frac(self) -> float:
        return self.live_pairings / self.total_pairings

    @property
    def live_comparison_frac(self) -> float:
        return self.live_comparisons / self.total_comparisons

    def to_dict(self) -> dict:
        return {
            "names": self.names,
            "totals": self.totals,
            "unbeaten": self.unbeaten,
            "inert": self.inert,
            "spread": round(self.spread, 4),
            "live_pairings": self.live_pairings,
            "total_pairings": self.total_pairings,
            "live_comparisons": self.live_comparisons,
            "total_comparisons": self.total_comparisons,
            "live_by_pairing": list(self.live_by_pairing),
            "spread_cap": self.spread_cap,
            "hard_ok": self.hard_ok,
            "spread_ok": self.spread_ok,
            "score": round(score(self), 4),
        }


def analyse(result, spread_cap: Optional[float] = MAX_SPREAD) -> Metrics:
    """
    Reduce a round-robin to Metrics, using the shipped test's own rules.

    "Better order" is the shipped comparison: within one force
    pairing, A was the better order than B when A beat B more often
    than B beat A. Equal counts are a tie, which is what makes a
    pairing dead - the doctrine changed nothing there and the weapon
    matchup decided the fight on its own.
    """
    wins, names, _runs = result
    pairings = range(len(degen.PAIRINGS))

    beaten = {a: any(wins[(i, b, a)] > wins[(i, a, b)]
                     for i in pairings for b in names if b != a)
              for a in names}
    victor = {a: any(wins[(i, a, b)] > wins[(i, b, a)]
                     for i in pairings for b in names if b != a)
              for a in names}

    totals = {a: sum(wins[(i, a, b)] for i in pairings
                     for b in names if b != a) for a in names}
    spread = max(totals.values()) / max(1, min(totals.values()))

    pairs = [(a, b) for k, a in enumerate(names) for b in names[k + 1:]]
    live_comparisons = 0
    live_by_pairing = []
    for i in pairings:
        decided = [(a, b) for a, b in pairs
                   if wins[(i, a, b)] != wins[(i, b, a)]]
        live_comparisons += len(decided)
        live_by_pairing.append(1 if decided else 0)
    live_pairings = sum(live_by_pairing)

    return Metrics(
        names=list(names),
        totals=totals,
        unbeaten=[a for a in names if not beaten[a]],
        inert=[a for a in names if not victor[a]],
        spread=spread,
        live_pairings=live_pairings,
        total_pairings=len(degen.PAIRINGS),
        live_comparisons=live_comparisons,
        total_comparisons=len(degen.PAIRINGS) * len(pairs),
        live_by_pairing=tuple(live_by_pairing),
        spread_cap=spread_cap,
    )


def score(m: Metrics) -> float:
    """
    The scalar being maximised. Lexicographic, flattened into a number.

    Band 1, hard constraints unmet (score in [-100, -90]):
        -100 + 10 * (satisfied hard sub-constraints / all of them),
        where the sub-constraints are "this option is beaten
        somewhere" and "this option wins somewhere", one of each per
        option. An infeasible candidate is therefore still ordered by
        how close it came, which is only used for diagnostics.

    Band 2, hard met but the spread cap breached (score in (-20, -10]):
        -10 - (spread - MAX_SPREAD), so a near miss ranks above a
        runaway. Never competitive with a feasible candidate.

    Band 3, feasible (score in [0, 110]):
        100 * live_pairing_frac      the term the shipped test cannot
                                     see, and the reason this sweep
                                     exists - dominates everything
        + 10 * live_comparison_frac  finer-grained tie-break: how many
                                     head-to-head cells moved, not
                                     just how many pairings had one
        - (spread - 1.0)             at most -0.25 inside the cap, so
                                     an even matrix wins a tie but
                                     never outranks a livelier one

    The bands cannot overlap: band 3 is non-negative, band 2 is at
    most -10, band 1 is at most -90.
    """
    if not m.hard_ok:
        satisfied = sum(1 for a in m.names if a not in m.unbeaten)
        satisfied += sum(1 for a in m.names if a not in m.inert)
        return -100.0 + 10.0 * (satisfied / (2 * len(m.names)))
    if not m.spread_ok:
        return -10.0 - (m.spread - m.spread_cap)
    return (100.0 * m.live_pairing_frac
            + 10.0 * m.live_comparison_frac
            - (m.spread - 1.0))


def evaluate(axis: str, candidate: Dict[str, dict],
             seeds: Sequence[int]) -> Metrics:
    """Score one candidate on one seed set. Applies in memory only."""
    with applied(axis, candidate), seeds_of(seeds):
        return analyse(_round_robin_for(axis))


# ----------------------------------------------------------- provenance

def engine_fingerprint() -> dict:
    """git HEAD plus a digest of the working-tree battle files."""
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        head = "unknown"
    digest = hashlib.sha256()
    present = []
    for rel in ENGINE_FILES:
        path = REPO_ROOT / rel
        if not path.exists():
            continue
        present.append(rel)
        digest.update(rel.encode())
        digest.update(path.read_bytes())
    return {"head": head, "files": present,
            "worktree_sha256": digest.hexdigest()[:32]}


# ------------------------------------------------------------- execution

_WORKER_AXIS: Optional[str] = None
_WORKER_HELDOUT = True


def _worker_init(axis: str, heldout: bool) -> None:
    global _WORKER_AXIS, _WORKER_HELDOUT
    _WORKER_AXIS = axis
    _WORKER_HELDOUT = heldout


def _worker(candidate: Dict[str, dict]) -> dict:
    """
    One candidate: train always, held-out only if training passed.

    Held-out is skipped for candidates that already failed the gates
    on training, because they are rejected either way and the check
    would double the cost of the sweep for no information.
    """
    axis = _WORKER_AXIS
    train = evaluate(axis, candidate, TRAINING_SEEDS)
    record = {
        "id": candidate_id(axis, candidate),
        "axis": axis,
        "candidate": candidate,
        "train": train.to_dict(),
        "holdout": None,
        "accepted": False,
        "rejected_by_holdout": False,
    }
    gated = train.hard_ok and train.spread_ok
    if gated and _WORKER_HELDOUT:
        held = evaluate(axis, candidate, HELDOUT_SEEDS)
        record["holdout"] = held.to_dict()
        record["accepted"] = held.hard_ok and held.spread_ok
        record["rejected_by_holdout"] = not record["accepted"]
    elif gated:
        record["accepted"] = True
    return record


def sweep(axis: str, workers: int, sample: Optional[int], sample_seed: int,
          out_path: Path, heldout: bool) -> None:
    """Full grid over the axis, checkpointed to JSONL line by line."""
    candidates = list(enumerate_candidates(axis))
    if sample is not None and sample < len(candidates):
        picker = random.Random(sample_seed)
        indices = sorted(picker.sample(range(len(candidates)), sample))
        candidates = [candidates[i] for i in indices]

    fingerprint = engine_fingerprint()
    done = _completed_ids(out_path)
    pending = [c for c in candidates
               if candidate_id(axis, c) not in done]

    console.print(
        f"[bold cyan]axis[/] {axis}  "
        f"[bold cyan]grid[/] {len(candidates)}  "
        f"[bold cyan]done[/] {len(done)}  "
        f"[bold cyan]pending[/] {len(pending)}  "
        f"[bold cyan]workers[/] {workers}")
    console.print(f"[dim]engine {fingerprint['head'][:12]} "
                  f"tree {fingerprint['worktree_sha256'][:12]}[/]")
    console.print(f"[dim]train seeds {TRAINING_SEEDS} "
                  f"holdout seeds {HELDOUT_SEEDS}[/]")

    if not pending:
        console.print("[yellow]nothing to do[/]")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    counters = {"gated": 0, "accepted": 0, "rejected": 0}
    best = None

    columns = (
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
    )

    # A detached run is tee'd to a log file, where a live spinner is
    # thousands of redraw frames of noise; fall back to a periodic
    # one-line status there instead
    live = console.is_terminal
    context = mp.get_context("fork")
    seen = 0
    with open(out_path, "a", buffering=1) as sink, \
            Progress(*columns, console=console, disable=not live) \
            as progress, \
            context.Pool(workers, initializer=_worker_init,
                         initargs=(axis, heldout)) as pool:
        task = progress.add_task(axis, total=len(pending))
        for record in pool.imap_unordered(_worker, pending, chunksize=4):
            record["engine"] = fingerprint
            sink.write(json.dumps(record, sort_keys=True) + "\n")
            if record["train"]["hard_ok"] and record["train"]["spread_ok"]:
                counters["gated"] += 1
            if record["accepted"]:
                counters["accepted"] += 1
                key = _ranking_score(record)
                if best is None or key > best[0]:
                    best = (key, record["id"])
            if record["rejected_by_holdout"]:
                counters["rejected"] += 1
            seen += 1
            status = (f"{axis}  gated {counters['gated']}  "
                      f"accepted {counters['accepted']}  "
                      f"holdout-rejected {counters['rejected']}")
            progress.update(task, advance=1, description=status)
            if not live and (seen % 500 == 0 or seen == len(pending)):
                rate = seen / max(1e-9, time.time() - started)
                console.print(f"{seen}/{len(pending)}  {status}  "
                              f"{rate:.1f}/s")

    # Workers fork after the parent has imported the engine, so a
    # mid-run edit by another workflow cannot change what was
    # measured - but it does mean the checkpoint's fingerprint no
    # longer describes the tree, and the run should be repeated
    after = engine_fingerprint()
    if after["worktree_sha256"] != fingerprint["worktree_sha256"]:
        console.print("[bold red]WARNING[/] battle files changed during "
                      f"the run: {fingerprint['worktree_sha256'][:12]} -> "
                      f"{after['worktree_sha256'][:12]}. These results "
                      "describe the tree as it was at launch; re-run.")

    elapsed = time.time() - started
    console.print(f"[green]done[/] {len(pending)} candidates in "
                  f"{elapsed / 60:.1f} min -> {out_path}")
    console.print(f"  passed training gates : {counters['gated']}")
    console.print(f"  rejected by held-out  : {counters['rejected']}")
    console.print(f"  accepted              : {counters['accepted']}")
    if best:
        console.print(f"  best score (worse set): {best[0]:.3f} "
                      f"(id {best[1]})")


def _completed_ids(path: Path) -> set:
    """Resume support: ids already checkpointed, truncated line ignored."""
    done = set()
    if not path.exists():
        return done
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                done.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                continue
    return done


# ---------------------------------------------------------------- report

def _print_pairing_liveness(m: dict) -> None:
    """
    Which force pairings the doctrine actually decided.

    A pairing that stays dead across the whole sweep is not a modifier
    problem: it is a weapon matchup one archetype loses outright, and
    no stance or posture will change that. Printed so the report can
    say which ones, and stop there.
    """
    dead = [f"{a.name} vs {b.name}"
            for (a, b), live in zip(degen.PAIRINGS,
                                    m.get("live_by_pairing", []))
            if not live]
    if dead:
        console.print(f"  [yellow]doctrine-inert pairings[/]: "
                      f"{', '.join(dead)}")


def _ranking_score(record: dict) -> float:
    """The worse of the training and held-out scores - see report()."""
    scores = [record["train"]["score"]]
    if record["holdout"]:
        scores.append(record["holdout"]["score"])
    return min(scores)


def _metrics_row(table: Table, label: str, m: dict) -> None:
    table.add_row(
        label,
        "yes" if m["hard_ok"] else f"NO {m['unbeaten']}{m['inert']}",
        f"{m['spread']:.3f}" + ("" if m["spread_ok"] else " OVER"),
        f"{m['live_pairings']}/{m['total_pairings']}",
        f"{m['live_comparisons']}/{m['total_comparisons']}",
        f"{m['score']:.3f}",
    )


def _metrics_table(title: str) -> Table:
    table = Table(title=title, title_style="bold cyan")
    table.add_column("set")
    table.add_column("hard ok")
    table.add_column("spread")
    table.add_column("live pairings")
    table.add_column("live cells")
    table.add_column("score", justify="right")
    return table


def validate() -> None:
    """
    Score the shipped tables, so the objective is calibrated before
    anything is swept.

    The expectation stated by the task: the shipped values must read
    as feasible - no option unbeaten, no option inert, spread inside
    the cap - because tests/unit/test_battle_degeneracy.py passes on
    them, while the liveness term reads low, because the main session
    measured most force pairings as doctrine-inert. If the feasibility
    verdict disagrees with the shipped test, the objective is wrong
    and nothing may be swept until it is fixed.
    """
    fingerprint = engine_fingerprint()
    console.print(f"[dim]engine {fingerprint['head'][:12]} "
                  f"tree {fingerprint['worktree_sha256'][:12]}[/]")
    console.print(f"[dim]train seeds {TRAINING_SEEDS} "
                  f"holdout seeds {HELDOUT_SEEDS}[/]\n")

    for axis in ("stance", "posture"):
        candidate = shipped_candidate(axis)
        train = evaluate(axis, candidate, TRAINING_SEEDS).to_dict()
        held = evaluate(axis, candidate, HELDOUT_SEEDS).to_dict()
        table = _metrics_table(f"shipped {axis} modifiers")
        _metrics_row(table, "training", train)
        _metrics_row(table, "held-out", held)
        console.print(table)
        _print_pairing_liveness(train)

    with seeds_of(TRAINING_SEEDS):
        adm = analyse(_admiralty_round_robin(), spread_cap=None).to_dict()
    table = _metrics_table("shipped admiralty standard plans "
                           "(no spread cap in the shipped test)")
    _metrics_row(table, "training", adm)
    console.print(table)


def report(axis: str, out_path: Path, top: int) -> None:
    """Rank the checkpointed candidates and gate the finalists."""
    if not out_path.exists():
        console.print(f"[red]no results at {out_path}[/]")
        return
    records = []
    with open(out_path) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    accepted = [r for r in records if r["accepted"]]
    rejected = [r for r in records if r["rejected_by_holdout"]]
    console.print(f"[bold]{len(records)}[/] evaluated, "
                  f"[bold]{len(accepted)}[/] accepted, "
                  f"[bold]{len(rejected)}[/] rejected by held-out")

    # Ranked on the WORSE of the two seed sets, which is the honest
    # figure: a candidate is only as good as it is on the seeds it was
    # not fitted to, and one that scores well on held-out purely by
    # luck of a low training score has not earned a place either. Ties
    # broken by id so the ordering is stable whatever order the pool
    # finished its work in.
    accepted.sort(key=lambda r: (-_ranking_score(r), r["id"]))

    for record in accepted[:top]:
        console.print(f"\n[bold cyan]{record['id']}[/]  "
                      f"{json.dumps(record['candidate'], sort_keys=True)}")
        table = _metrics_table("")
        _metrics_row(table, "training", record["train"])
        if record["holdout"]:
            _metrics_row(table, "held-out", record["holdout"])
        console.print(table)
        _print_pairing_liveness(record["train"])
        with applied(axis, record["candidate"]), seeds_of(TRAINING_SEEDS):
            adm = analyse(_admiralty_round_robin(), spread_cap=None).to_dict()
        console.print(f"  admiralty gate: hard_ok={adm['hard_ok']} "
                      f"spread={adm['spread']:.3f} "
                      f"live={adm['live_pairings']}/{adm['total_pairings']}")


# ------------------------------------------------------------------ main

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--mode", choices=("validate", "sweep", "report"),
                        default="validate")
    parser.add_argument("--axis", choices=("stance", "posture"),
                        default="stance")
    parser.add_argument("--workers", type=int,
                        default=max(1, (os.cpu_count() or 4) - 4))
    parser.add_argument("--sample", type=int, default=None,
                        help="evaluate a deterministic subset of the grid")
    parser.add_argument("--sample-seed", type=int, default=20260728)
    parser.add_argument("--no-holdout", action="store_true",
                        help="skip held-out validation (diagnostics only)")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    out_path = args.out or (RESULTS_DIR / f"{args.axis}.jsonl")

    if args.mode == "validate":
        validate()
    elif args.mode == "sweep":
        sweep(args.axis, args.workers, args.sample, args.sample_seed,
              out_path, not args.no_holdout)
    else:
        report(args.axis, out_path, args.top)


if __name__ == "__main__":
    main()
