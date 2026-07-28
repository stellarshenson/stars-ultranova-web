#!/usr/bin/env python3
"""
Re-evaluate the sweep finalists and the shipped tables on ONE tree.

The full grid ran while other workflows were editing the battle engine,
so the stance grid and the posture grid were measured on two different
working trees and both are now behind HEAD. This script takes the top
finalists off each axis plus the shipped table and re-scores all of
them against whatever tree is on disk right now, so the comparison the
recommendation rests on is internally consistent.

Read-only with respect to the repo: candidates are applied in memory by
balance_sweep.applied(), exactly as in the sweep.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import balance_sweep as bs  # noqa: E402

TOP = int(sys.argv[1]) if len(sys.argv) > 1 else 25


def load(axis):
    path = REPO_ROOT / "results" / "balance" / f"{axis}.jsonl"
    seen = {}
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            seen[rec["id"]] = rec
    return list(seen.values())


def worse(rec):
    return min(rec["train"]["score"], rec["holdout"]["score"])


def shipped_candidate(axis):
    """The live table as a plain candidate dict, minus the pinned row."""
    _, _, table = bs.AXES[axis]
    lattice = bs.STANCE_LATTICE if axis == "stance" else bs.POSTURE_LATTICE
    out = {}
    for name in lattice:
        row = table[name]
        out[name] = {field: getattr(row, field) for field in lattice[name]}
    return out


def run(axis):
    fp = bs.engine_fingerprint()
    print(f"\n===== {axis.upper()} rechecked on head {fp['head'][:12]} "
          f"tree {fp['worktree_sha256'][:12]} =====")

    records = load(axis)
    accepted = [r for r in records if r["accepted"]]
    accepted.sort(key=lambda r: (-worse(r), r["id"]))
    finalists = accepted[:TOP]

    rows = []
    ship = shipped_candidate(axis)
    for label, cand, old in [("SHIPPED", ship, None)] + \
            [(r["id"], r["candidate"], r) for r in finalists]:
        t = bs.evaluate(axis, cand, bs.TRAINING_SEEDS).to_dict()
        h = bs.evaluate(axis, cand, bs.HELDOUT_SEEDS).to_dict()
        rows.append((label, cand, t, h, old))

    rows.sort(key=lambda r: -min(r[2]["score"], r[3]["score"]))
    print(f"{'label':18s} {'worse':>8s} {'train':>8s} {'hold':>8s} "
          f"{'live t/h':>10s} {'spread t/h':>14s}  (was t/h)")
    for label, cand, t, h, old in rows:
        was = ""
        if old:
            was = (f"  (was {old['train']['score']:.1f}/"
                   f"{old['holdout']['score']:.1f}, "
                   f"{old['train']['live_pairings']}/"
                   f"{old['holdout']['live_pairings']})")
        flag = "" if (t["hard_ok"] and t["spread_ok"]
                      and h["hard_ok"] and h["spread_ok"]) else "  FAILS-GATE"
        print(f"{label:18s} {min(t['score'], h['score']):8.2f} "
              f"{t['score']:8.2f} {h['score']:8.2f} "
              f"{str(t['live_pairings']) + '/' + str(h['live_pairings']):>10s} "
              f"{t['spread']:6.3f}/{h['spread']:6.3f}{was}{flag}")

    best = rows[0]
    print(f"\nbest after recheck: {best[0]}")
    print(f"  {json.dumps(best[1], sort_keys=True)}")
    print(f"  train live_by_pairing   {best[2]['live_by_pairing']}")
    print(f"  holdout live_by_pairing {best[3]['live_by_pairing']}")
    print(f"  train totals {best[2]['totals']}")
    print(f"  hold  totals {best[3]['totals']}")
    with bs.applied(axis, best[1]), bs.seeds_of(bs.TRAINING_SEEDS):
        adm = bs.analyse(bs._admiralty_round_robin(), spread_cap=None).to_dict()
    print(f"  admiralty gate: hard_ok={adm['hard_ok']} "
          f"spread={adm['spread']:.3f} "
          f"live={adm['live_pairings']}/{adm['total_pairings']}")
    return fp


if __name__ == "__main__":
    start = bs.engine_fingerprint()
    for axis in ("stance", "posture"):
        run(axis)
    end = bs.engine_fingerprint()
    if start["worktree_sha256"] != end["worktree_sha256"]:
        print(f"\nWARNING tree changed during recheck: "
              f"{start['worktree_sha256'][:12]} -> "
              f"{end['worktree_sha256'][:12]}")
    else:
        print(f"\ntree stable through recheck: "
              f"{end['worktree_sha256'][:12]}")
