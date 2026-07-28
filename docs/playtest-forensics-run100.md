# Playtest Forensics - run100

The first full-length LLM-vs-LLM playtest (game d3f51d91, seed 4242, Opus commanders on both sides) ran 56 turns of its 100-turn target before ending in a legitimate victory, and its forensic record - 56 full both-sides state dumps, 190 harness events, 620 commander observations and 112 raw order transcripts - was adjudicated into nine new registered defects (DEF-8 through DEF-16), a set of confirmed not-a-bug verdicts, and a list of mechanics the run never exercised. The headline result is a game that works end to end but is strategically distorted by three compounding forces: an unfair map, a score formula that rewards ship spam over empire building, and the old linear fuel physics (DEF-7, already fixed) that stranded most of one side's early fleets.

Key facts:

- Game ended turn 56, year 2156 - empire 1 "Iron Fist" (Humanoids) won the owns-60%-of-planets victory target with 54 of 89 planets (60.7%) after minimum game time
- Loser out-scored the winner 10x: empire 2 "Silicon Loom" (Rabbitoids) ended with 4 planets but score 2657 vs the victor's 264 - 2536 of that score from 1268 cheap armed probes at +2 per ship
- Map start asymmetry: e1 homeworld had 9 stars within 50 ly, e2 had 1 (second-nearest 80 ly) - the expansion race was decided by galaxy generation before turn 1
- 117 rejected orders (58 cargo, 24 waypoint, 23 design, 12 production), peak 32 rejections on turn 49 driven by commander key-guessing against nonexistent fleets
- 16 stuck_fleet forensic events, all traceable to the old linear fuel burn plus free_warp 0 starting designs (DEF-7 scope)
- Server clean throughout: zero tracebacks, zero 500s, max turn generation time 0.04 s
- Nine defects registered: DEF-8..DEF-16, five HIGH (score economics, production starvation, colonize auto-invasion, zero-fuel deadlock, phantom battles, homeworld fairness), plus a DEF-7 evidence note

## The War Story

Seed 4242 dealt empire 1 a central start (Gliese 1 at 188,192, deep in the GMM core of the star field) and empire 2 a corner exile (Zubeneschamali at 380,20, farthest-point pick by construction). The expansion curves never crossed: e1 grew 1 -> 6 -> 14 -> 25 -> 36 -> 54 planets across turns 1/15/20/30/40/55 while e2 plateaued at 4 planets from turn 20 onward - its nearest targets sat beyond colony-ship fuel range under the old linear burn model, and its colonizer waves stranded or died in transit.

Silicon Loom adapted rationally to a broken incentive landscape. Locked out of expansion, it discovered that escort-class ships score +2 each with no cost or mass scaling, that tech contributes a flat +4 at best, and that planets add roughly nothing to score directly. From turn 30 it pivoted to mass-producing cheap armed probes at 0% research: escort count 2 -> 62 -> 320 -> 622 -> 938 -> 1268 over turns 30/35/40/45/50/56, roughly +90 score per turn at the end. Score-vs-planets diverged into absurdity - 2657 with 4 planets against 264 with 54 - but only the planets_owned victory target was enabled, so the score leader had no path to victory or denial and Iron Fist ground out the 60% threshold by turn 55. Adjudication then fired one turn late (target met at 55, victor declared 56), a lesser display/check-order issue.

The mechanism is named and verified (DEF-8): per-ship escort counting in `backend/server/scores.py` is a deliberate documented deviation siding with legacy Common/Scores.cs and canonical Stars!, but with the capital-ship harmonic reachable and tech bracketed, the economics make probe spam strictly dominant. Since score gates three victory targets in victory_check.py, any score-victory configuration is trivially exploitable until the design call is made.

## Verified Defects

All nine registered in docs/defects.md with dated notes; ids and one-line essences:

- DEF-8 (HIGH, needs-design) - score formula: +2 per escort ship, flat +4 tech, ~0 for planets makes ship spam strictly dominant and 0% research score-optimal
- DEF-9 (MEDIUM) - negative-hab deaths use Python floor division where C# truncates toward zero: 1-99 computed deaths become a flat 100 killed per year, over-killing every negative-hab world
- DEF-10 (HIGH) - a mineral-blocked production order neither reserves minerals nor stalls the queue; trailing orders eat the minerals it awaits forever (C# banks per-resource RemainingCost and blocks)
- DEF-11 (MEDIUM) - the in-transit placeholder waypoint takes warp default 6, so every in-transit fleet serializes phantom warp 6 and warp edits made in transit are silently discarded
- DEF-12 (HIGH) - colonize on an occupied planet auto-invades (C# aborts "already occupied"); run100's only invasion, at Kapteyn's Star, happened by this accident on stale intel
- DEF-13 (HIGH) - zero-fuel fleets move the full ordered distance before fuel deduction, then strand in_transit at warp 0 with no message; Santa Maria #64 deadlocked 0.04 ly short of its colonize target
- DEF-14 (HIGH) - the active Ron battle engine counts unarmed flee-targets as battle triggers: two unarmed ships co-located at Sabik fought a phantom 60-round no-shot battle every turn for 12 years
- DEF-15 (MEDIUM) - battle messages drop the C# loss summary ("N of your ships were destroyed"); losses are visible only by fleet disappearance
- DEF-16 (HIGH) - homeworld placement has no fairness constraint: center-weighted star field plus greedy farthest-point selection systematically gives player 2+ sparse corner starts (C# places homeworlds first on a uniform field with minimum separation)

The run-time fleet stranding itself maps to closed DEF-7 (linear fuel burn plus free_warp 0 starting designs, both fixed in the uncommitted change set); a dated evidence note was added there.

## Not-A-Bug Verdicts

- Colony economy (sub-1000-pop worlds yield 0 resources, 0 facility caps) - exact port of Star.cs formulas with identical constants; both playtest races carried default 10-per-10k settings, arithmetically pop/1000; a dying colony unable to self-fund terraforming is canon. Side observation worth a future look: DEFAULT_RACES presets set only name/prt/icon, so the Rabbitoids preset did not inherit canonical Rabbitoid.race stats (OperableFactories=17, GrowthRate=20)
- No refueling anywhere - refuted: 9 refuel-to-full events at both homeworld Space Stations in the dumps; Orbital Fort not refueling (DockCapacity 0) is canon, as is bare colonies never refueling; fleet-to-fleet fuel transfer exists at POST /fleets/{key}/transfer but the harness never exposed it
- Batch build into one fleet, whole-fleet colonize consumption, and "missing" split/merge - all canonical or better than canon (the port consumes only colonizer tokens where C# clears the entire fleet); split/merge exists at API, engine and UI layers but not in the harness order schema, so commanders could not use it
- Starting tech 18-vs-0 is canonical JOAT; tech does advance with research (e1 18 -> 33, e2 0 -> 27); score.resources is leftover ResourcesOnHand per C#; armed non-bombers doing nothing over undefended colonies is canon (no blockade mechanic in Stars!)

## Dead Mechanics

Never exercised over 56 turns; hypothesized cause in parentheses - these need targeted coverage before any filing, since unreachable and broken are indistinguishable from this run:

- Minefields, battle plans, stargates, cloaking, wormhole travel (no order-API exposure in the harness schema)
- Mineral packets (mass-driver prerequisite invisible to commanders; 0 uses)
- Mystery Trader (first spawn on the final turn; no intercept or gift verb)
- Deliberate invasion (no invade verb - the only invasion was DEF-12's colonize accident)
- Remote mining (Mini Miner parked over high-concentration planets produced nothing; hull may have no wired function)
- Bombing (harness role vocabulary has no "bomber" role, so Mini Bomber designs were rejected 3x - structurally unreachable)

## Map-Balance Assessment

The galaxy generator stacks three biases against later players: stars are drawn from a center-heavy GMM (15% core plus 35% central band, corners are distribution tails), player 1 gets a density-weighted pick near the sub-centroid, and each later player gets the greedy farthest-point star - the sparsest periphery by definition - with no density, nearest-habitable or parity check. Run100's 9-vs-1 stars-within-50-ly asymmetry follows directly and would recur on most seeds. The C# reference avoids the whole class of problem structurally (homeworlds first, uniform field, enforced 100 ly separation for 2 players on a 400 map). Registered as DEF-16; until fixed, two-player playtests measure map luck as much as strategy.

## Commander Behavior Notes

- Orders volume: 112 order transcripts over 56 turns (both sides each turn), 117 rejections total - a 2%-per-order-class rejection profile except for the turn-49 spike (32 rejections) when e1's commander began guessing fleet keys (4294967296+n pattern) and ordered ~67 phantom fleets, which the API silently accepted or rejected without reasons
- Rejection patterns: 58 cargo (consumed or mid-flight fleets), 24 waypoint (mostly phantom keys), 23 design (slot cap ~21, race-locked hulls - Mini-Colony rejected 17x for JOAT, no "bomber" role), 12 production
- Memo evolution: both commanders maintained coherent multi-turn plans within the 600-word memo cap; e1's memo tracked an expansion checklist that degraded gracefully as state truncation hid 139 of its 167 fleets and 29 of 43 planets late-game; e2's memo shows the explicit strategic pivot from expansion to score-farming around turn 30 once it concluded expansion was physically impossible
- Both commanders independently converged on permanent 0% research - the score formula told them research was worthless, and they listened
- 25 separate filings complained the victory display shows percentage progress beside an absolute-looking target of 60 - the check itself was correct (54/89 = 60.7%)

## Recommended Fix Priority

1. DEF-16 homeworld fairness - every future playtest is confounded until starts are equitable
2. DEF-8 score economics (design call: per-token vs per-ship, cap or cost-scale ship terms) - removes the dominant degenerate strategy and restores research/expansion incentives
3. DEF-10 production mineral banking - core economy correctness, canonical partial builds
4. DEF-13 zero-fuel movement deadlock plus DEF-11 placeholder waypoint - one movement-code cluster, fixes silent stranding and phantom warp reporting together
5. DEF-12 colonize auto-invasion - restores the canonical occupied-planet guard
6. DEF-14 phantom battles - eliminates recurring no-shot battles and their message spam
7. DEF-9 negative-hab rounding and DEF-15 battle loss summaries - small, well-localized
8. Harness follow-ups (not game code): expose split/merge, fuel transfer, invade and bomber-role verbs; surface storm/wormhole coordinates already present in state; paginate or de-truncate large fleet/planet lists; reject orders against unknown fleet keys with reasons

A retest run on the same seed after fixes 1-4 should show a competitive two-sided game; the remaining lesser findings (stale intel reconciliation, alchemy yield, facility-cap teardown, storm targeting, mineral depletion scaling) stay parked as report-only until a fixed-physics run reproduces them.
