#!/usr/bin/env python3
"""
Summarise a checkpointed balance sweep for the write-up.

Reads results/balance/<axis>.jsonl and answers the five questions the
report has to carry: are the hard constraints satisfiable at all, what
is the best candidate on the TRAINING seeds, what does that candidate
score on HELD-OUT, how many candidates the held-out set caught, and how
the winner's doctrine liveness compares with the shipped table.

Read-only. Applies nothing, edits nothing.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def load(axis):
    path = REPO_ROOT / "results" / "balance" / f"{axis}.jsonl"
    out = []
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    # de-duplicate on id, last record wins (resume can re-append)
    seen = {}
    for rec in out:
        seen[rec["id"]] = rec
    return list(seen.values())


def summarise(axis):
    records = load(axis)
    n = len(records)
    train_feasible = [r for r in records
                      if r["train"]["hard_ok"] and r["train"]["spread_ok"]]
    train_hard_only = [r for r in records if r["train"]["hard_ok"]]
    accepted = [r for r in records if r["accepted"]]
    rejected = [r for r in records if r["rejected_by_holdout"]]

    print(f"\n===== {axis.upper()} =====")
    print(f"evaluated                      {n}")
    print(f"hard constraints met on train  {len(train_hard_only)}"
          f"  ({100.0 * len(train_hard_only) / n:.1f}%)")
    print(f"  + spread cap met (gated)     {len(train_feasible)}")
    print(f"accepted (also clears held-out){len(accepted)}")
    print(f"rejected BY held-out gates     {len(rejected)}")

    if not train_hard_only:
        print("  !!! HARD CONSTRAINTS UNSATISFIABLE ANYWHERE IN THE SPACE !!!")
        return

    # overfitting measured two ways
    scored_both = [r for r in records if r["holdout"]]
    worse_on_holdout = [r for r in scored_both
                        if r["holdout"]["score"] < r["train"]["score"]]
    print(f"scored on both seed sets       {len(scored_both)}")
    print(f"  scored WORSE on held-out     {len(worse_on_holdout)}"
          f"  ({100.0 * len(worse_on_holdout) / max(1, len(scored_both)):.1f}%)")

    def show(label, rec):
        t, h = rec["train"], rec["holdout"]
        print(f"\n-- {label}")
        print(f"   id        {rec['id']}")
        print(f"   candidate {json.dumps(rec['candidate'], sort_keys=True)}")
        print(f"   train     score={t['score']:.3f} hard_ok={t['hard_ok']} "
              f"spread={t['spread']:.3f} "
              f"live={t['live_pairings']}/{t['total_pairings']} "
              f"cells={t['live_comparisons']}/{t['total_comparisons']}")
        if h:
            print(f"   held-out  score={h['score']:.3f} hard_ok={h['hard_ok']} "
                  f"spread={h['spread']:.3f} "
                  f"live={h['live_pairings']}/{h['total_pairings']} "
                  f"cells={h['live_comparisons']}/{h['total_comparisons']}")
        else:
            print("   held-out  not evaluated (failed training gates)")

    best_train = max(records, key=lambda r: (r["train"]["score"], r["id"]))
    show("BEST ON TRAINING (unconditioned - what a train-only fit would pick)",
         best_train)

    if accepted:
        best_worse = max(accepted, key=lambda r: (
            min(r["train"]["score"], r["holdout"]["score"]), r["id"]))
        show("SHIPPABLE PICK (best on the WORSE of the two seed sets)",
             best_worse)
        best_hold = max(accepted, key=lambda r: (r["holdout"]["score"], r["id"]))
        show("BEST ON HELD-OUT", best_hold)

    ceiling_t = max(r["train"]["live_pairings"] for r in train_feasible) \
        if train_feasible else 0
    ceiling_h = max((r["holdout"]["live_pairings"] for r in accepted),
                    default=0)
    print(f"\nliveness ceiling  train {ceiling_t}/9   held-out {ceiling_h}/9")

    if accepted:
        top = sorted(accepted, key=lambda r: (
            -min(r["train"]["score"], r["holdout"]["score"]), r["id"]))[:10]
        print("\n-- top 10 by worse-of-two")
        for rec in top:
            t, h = rec["train"], rec["holdout"]
            print(f"   {rec['id']}  worse={min(t['score'], h['score']):.2f}"
                  f"  train={t['score']:.2f}({t['live_pairings']}/9)"
                  f"  hold={h['score']:.2f}({h['live_pairings']}/9)"
                  f"  spread={t['spread']:.3f}/{h['spread']:.3f}")


if __name__ == "__main__":
    for axis in (sys.argv[1:] or ["stance", "posture"]):
        summarise(axis)
