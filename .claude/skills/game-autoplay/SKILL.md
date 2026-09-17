---
name: game-autoplay
description: Play Stars Ultranova with the built-in harnesses - launch an LLM-vs-LLM playtest (claude -p commanding both empires), resume an interrupted run, act as a commander writing turn orders, or mine a finished run's forensics. Use when the user says "play the game", "run a playtest", "100-turn game", "autoplay", "LLM vs LLM", "resume the run", or asks to analyze a playtest.
---

# Game Autoplay

Two harnesses play the game through the real backend HTTP API. Pick by purpose.

- **`scripts/llm_playtest.py`** - the real thing: `claude -p` commands BOTH empires (Iron Fist military vs Silicon Loom economy), every turn mined for forensics. Boots its own server on port 9830 with a dedicated db under `results/playtest/<name>/db/`, checkpoints after every turn, `--resume` reattaches. One bad turn never aborts the loop
- **`scripts/autoplay.py`** - scripted heuristic player (empire 1) against the AI on an already-running server (port 9800). Fast functional smoke, no LLM cost

## Launching a playtest

Smoke first, always - 3 turns proves the loop before burning a long run:

```bash
uv run python scripts/llm_playtest.py --name smoke --seed 777 --turns 3
```

The real run is DETACHED (session death must not kill it - detached compute rule):

```bash
mkdir -p logs
setsid nohup bash -c \
  'uv run python scripts/llm_playtest.py --name run100 --seed 4242 \
   --turns 100 2>&1 | tee -a logs/llm-playtest-run100.log' \
  >/dev/null 2>&1 &
```

Resume after any interruption - same command plus `--resume` (same `--name`
reattaches to the same game and db; state.json holds the next turn):

```bash
setsid nohup bash -c \
  'uv run python scripts/llm_playtest.py --name run100 --seed 4242 \
   --turns 100 --resume 2>&1 | tee -a logs/llm-playtest-run100.log' \
  >/dev/null 2>&1 &
```

- Watch the LOG FILE (`tail -f logs/llm-playtest-<name>.log`, colour renders under `less -R`), never the process tree
- Do not edit the harness or the backend while a run is live - the server subprocess imports once at boot, so edits land silently on the next restart and split the run across two engine states
- ~1-2 min per turn (two `claude -p` calls); 100 turns is an overnight run

## Playing a turn (the commander contract)

Each side receives its persona, its inherited strategy memo (rewritten every turn, 600-word cap), the last five turns' event digests, and the current state dump. It must reply STRICT JSON, no fences - keys optional except `strategy`, `memo`, `observations`:

- `research` - one field gets all progress; `budget` is percent of resources
- `production` - REPLACES the named star's whole queue, build order, max 6 items; omitted stars keep their queue; types FACTORY|MINE|DEFENSE|SHIP|STARBASE|TERRAFORM|ALCHEMY
- `fleets` - REPLACES that fleet's waypoints, max 4; `task: "colonize"` only on a colony ship aimed at an unowned star
- `cargo` - transfers with the orbited star; positive loads star -> fleet; colonists are headcount, load them BEFORE sending a colonizer
- `designs` - max 2 per turn; harness fills slots with the best tech for the `role`; build afterwards via production using the design name
- `relations`, `packets` - as schema
- `message` - ONE short free-text message per turn to the enemy commander, no classification or typing; delivered at the start of their NEXT turn so side order confers no advantage; it is diplomacy, not truth - either side may lie
- Invalid orders are rejected and wasted, never fixed up - keep orders consistent with visible state
- `observations` is the bug channel: anything that looks broken or imbalanced goes there verbatim, it lands in `bug_reports.jsonl` for forensics

Full schema text: `ORDERS_SCHEMA_TEXT` in `scripts/llm_playtest.py:116`.

## Outputs and forensics

Everything lands under `results/playtest/<name>/`:

- `state.json` - per-turn checkpoint (game id, next turn, history)
- `turnNNNN.json` - full both-sides state dump per turn
- `digests.jsonl` / `memo-1.md` / `memo-2.md` - what each commander saw and carried
- `forensics.jsonl` - anomaly events: order_rejected, commander_error, invalid_json, negative_value, absurd_value, stuck_fleet, turn_time, server_traceback, turn_failed, server_restart, game_over
- `bug_reports.jsonl` - commanders' observations verbatim
- `messages.jsonl` - the diplomatic channel, every message logged verbatim with turn, sender and recipient; read it alongside the memos to follow the psychological game
- `orders/` - raw claude -p request+response per turn per side
- `server.log` - scraped for tracebacks automatically

Mining a finished run: count `forensics.jsonl` events by type first (`jq -r .type | sort | uniq -c`), read every `server_traceback` and `order_rejected`, then read `bug_reports.jsonl` - commanders notice imbalances detectors cannot. Cross-check any suspected defect against `turnNNNN.json` state dumps before logging it in `docs/defects.md` (defects-tracking skill).

## Scripted smoke (no LLM)

Server must be running (`make run`, port 9800):

```bash
uv run python scripts/autoplay.py --name game1 --seed 11 --size small --players 2 --turns 30
```

Exercises production, research, scouting, colonization, cargo, fleet orders, combat and turn generation, validating invariants every turn.
