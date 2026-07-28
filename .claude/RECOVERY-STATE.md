# Recovery State

## CURRENT 2026-07-28 ~13:20 CEST - Forensics DONE (DEF-8..16), fix wave + architect audit RUNNING

- Forensics tribunal DONE: 78 candidates -> 10 verdicts -> DEF-8..16 registered (score escort-spam, neg-hab rounding, production starvation, phantom warp, colonize auto-invade, fuel deadlock, phantom battles, lost loss summary, homeworld fairness); report docs/playtest-forensics-run100.md; acc-crit Hundred-turn box checked (victory turn 56)
- Bug-hunter panel: 13/13 findings CONFIRMED and FIXED (wf_4a4a48dc; start/stop.sh PID+health, conftest race, CWD paths, resume guard, WORKERS guard, campaign mkdir/preflight, symlink, Makefile chrome, base-href regex, dead DATABASE_URL) - suite steady 989; round-2 re-confirm PENDING (pinned re-run after defect wave)
- **DEF-8..16 fix wave DONE** (task #30 closed, journal 43): all nine closed with tests, suite 989 -> **1082 passed, 8 skipped**; functional harness 8/8 twice against regenerated golden (score 38 -> 34 from the DEF-8 cap); tests/e2e alone 85 passed. Key fixes: escort/unarmed ship points capped at one per owned planet (documented web mod restoring canonical Stars! semantics both Nova C# variants omitted), homeworld fairness constraint (seed 4242 now 10-vs-4 stars within 50 ly, was 9-vs-1), unarmed flee-targets no longer trigger battles, colonize aborts on occupied per ColoniseTask.cs, fuel-capped movement + stranded message, per-resource production banking
- **ARCHITECT FIX WAVE RUNNING**: `wf_c24f26b7-335` (task wecdo61n5; delete 4 authorized dead subsystems, then 5 traps + residue). If killed, RESUME:
  `Workflow({scriptPath: "/home/lab/.claude/projects/-home-lab-workspace-private-games-stars-ultranova-web/518b5b18-c8ff-44e1-9680-3dac877c6d5a/workflows/scripts/architect-fixes.js", resumeFromRunId: "wf_c24f26b7-335"})`
- Planet-rendering RESEARCH DONE -> docs/research-planet-rendering.md (benchmarked: one-level domain-warped fBm at 5-6 octaves = 4.6-5.0 ms at 300x230, affordable; sample 3D noise at the sphere normal to kill the seam; gas giants need a SEPARATE evaluator; 9-class table; 15 per-world params; rotationPhase is free diversity)
- **VISUAL WAVE SCRIPT READY** (task #34): `/home/lab/.claude/projects/-home-lab-workspace-private-games-stars-ultranova-web/518b5b18-c8ff-44e1-9680-3dac877c6d5a/workflows/scripts/visual-generation-wave.js` - PlanetArt renderer + preview harness, star size scaling, larger universes, Perlin+Poisson clustering with statistical tests, engine-table single source. LAUNCH ONLY AFTER the architect wave finishes: `Workflow({scriptPath: ".../workflows/scripts/visual-generation-wave.js"})`
- USER APPROVAL GATE: imagery/sizing/clustering criteria may NOT be checked without the user approving screenshots; preview pages are built for that purpose, orchestrator screenshots them to walkthrough/review/
- **Architect audit DONE**: DO-NOT-SHIP, 18 findings. CRITICAL triaged + FIXED BY ME already: empire-password gate missing on all 7 fleets.py mutations + games.py get_battles -> X-Empire-Password header added, DEF-17 logged and closed, unit+e2e 946 green. Report kept at scratchpad/advrev/architect-result.txt
- **USER AUTHORIZED** (2026-07-28) the remaining architect work: delete all four dead subsystems (websocket.py, panel-manager.js, stars-theme.css, CORS) AND fix all five live traps (duplicate conflicting Victims/Strategy enums, get_database ignoring db_path, get_game_manager param, decorative turn-step priorities, hardcoded route status codes, plus residue). Script READY at `/home/lab/.claude/projects/-home-lab-workspace-private-games-stars-ultranova-web/518b5b18-c8ff-44e1-9680-3dac877c6d5a/workflows/scripts/architect-fixes.js` - LAUNCH IT ONLY AFTER the defect wave finishes (never two agents in one tree): `Workflow({scriptPath: ".../workflows/scripts/architect-fixes.js"})`
- After both waves: pinned round-2 re-confirms for BOTH adversaries (task #33), journal, close #30
- **NEW GOAL 2026-07-28 14:05** (task #34, acc-crit criteria added + TOC green): star size scaling (small default, modest zoom-in growth, floor on zoom-out), diverse realistic world imagery driven by real planet stats and seeded per star, LARGER player maps, star CLUSTERING (visible but restrained, DEF-16 fairness preserved), smart engine-table representation. All unit AND functional tested; functional golden must be regenerated (map changes shift seeded layouts). Runs after the fix waves; then #26 wave-6 gate closes the campaign ("ready for next game")
- After fix wave: journal, close #30, bug-hunter+architect round-2 re-confirms, then #26 wave-6 gate. Commit pending fresh approval (everything since 6d5865d)

## PREVIOUS 2026-07-28 ~12:50 CEST - Playtest ENDED (victor Iron Fist turn 56), forensics tribunal RUNNING

- run100 FINISHED 09:39: victor empire 1 (Iron Fist) at year 2156, turn 56/100, by 60%-planets target (54 planets); Silicon Loom 4 planets but score 2657 vs 264 (suspected score-formula exploit, 0% research + mass ship building). 620 bug observations, 190 forensic events. Task #29 done
- **Forensics workflow RUNNING**: `wf_1d6c213b-2d8` (task w81ck0mkf; 3 analysts -> dedup -> up to 10 code-level verifies -> registrar writes docs/playtest-forensics-run100.md + new DEF entries + acc-crit). If killed, RESUME:
  `Workflow({scriptPath: "/home/lab/.claude/projects/-home-lab-workspace-private-games-stars-ultranova-web/518b5b18-c8ff-44e1-9680-3dac877c6d5a/workflows/scripts/playtest-forensics-wf_1d6c213b-2d8.js", resumeFromRunId: "wf_1d6c213b-2d8"})`
- On completion: review verdicts, journal entry, close #30 after FIX WAVE for confirmed defects (fixes need own workflow), then #26 wave-6 gate
- Suite 989 baseline (fuel fix landed); uncommitted: fuel fix + playtest harness + results (next commit needs fresh approval)

## PREVIOUS 2026-07-28 ~02:35 CEST - 100-turn LLM playtest RUNNING DETACHED (opus commanders)

- Playtest harness DONE (#28, journal 41, smoke + resumeproof evidence in results/playtest/); DEF-5/6 logged; journal archived (1-21 -> JOURNAL_ARCHIVE.md, 20 remain)
- Commit `6d5865d` pushed (user-authorized); playtest harness files (scripts/llm_playtest*, results/) NOT yet committed - next commit needs fresh approval
- **100-TURN PLAYTEST RUNNING DETACHED** (user chose OPUS commanders): game 263cf41a seed 4242, launched 02:35 via `bash scripts/run_llm_playtest.sh run100 4242 100 --model opus`; log `logs/llm-playtest-run100.log`; state results/playtest/run100/; est 8-14h. DETACHED - survives session death. If interrupted: `bash scripts/run_llm_playtest.sh run100 4242 100 --model opus --resume`
- Monitor via the LOG FILE only (never own the process). On completion: #30 forensics analysis (turn dumps, forensics.jsonl, bug_reports.jsonl -> docs/defects.md -> fix wave), then #26 wave-6 gate
- **DEF-7 fuel-tables fix DONE** (task #32 closed, journal 42): root cause engineless STARTING_DESIGN_SPECS hitting the _consume_fuel linear fallback + hardcoded client estimator; canonical Engine.cs tables ported, hand-checked, suite 960 -> 989, DEF-7 closed. Rich logging landed in scripts/llm_playtest.py + rich==15.0.0 added via uv. Fix is UNCOMMITTED (next commit needs fresh approval)
- NOTE: playtest server 9830 holds OLD fuel physics in memory; if its harness restarts it mid-run the physics change - forensics analysis must note that boundary
- Tasks: #29 in progress (the run), #30 forensics/fixes, #26 gate (last). Suite baseline 960; dev server 9800 detached; functional harness RUN_FUNCTIONAL=1

## PREVIOUS 2026-07-28 ~00:15 CEST - Correspondence + functional harness CLOSED (960 green), LLM playtest harness IN FLIGHT

- Correspondence play DONE (#25): suite 939 -> 960, all 9 criteria checked, determinism digest proven, journal 39. Functional harness DONE (#31): tests/functional/ 8 Playwright tests green twice, golden gamethrough seed 4242, RUN_FUNCTIONAL=1 gate, journal 40; docs/defects.md created with DEF-1..4 (functional-harness observations)
- **LLM playtest harness builder RUNNING**: `wf_8f609647-f5c` (task w8tu81543; builds scripts/llm_playtest.py - claude -p both sides, port 9830 isolated server, per-turn checkpoints + forensics, 3-turn live smoke). If killed, RESUME:
  `Workflow({scriptPath: "/home/lab/.claude/projects/-home-lab-workspace-private-games-stars-ultranova-web/518b5b18-c8ff-44e1-9680-3dac877c6d5a/workflows/scripts/llm-playtest-harness-wf_8f609647-f5c.js", resumeFromRunId: "wf_8f609647-f5c"})`
- On harness completion: review smoke, launch #29 100-turn run DETACHED (setsid nohup scripts/run_llm_playtest.sh, tee logs/), then #30 forensics -> defects.md -> fixes, then #26 wave-6 gate (final verification incl. RUN_FUNCTIONAL=1 harness + browser evidence)
- Commit `6d5865d` pushed 2026-07-28 ~00:30 (user-authorized): correspondence + functional harness + wave-5 close-out; EXCLUDED in-flight playtest builder files (scripts/llm_playtest*, results/) - commit them after #28 completes WITH FRESH USER APPROVAL (#27 done, next commit needs new authorization)

## PREVIOUS 2026-07-27 ~23:30 CEST - Wave 5 CLOSED (939 green), Correspondence Play IN FLIGHT

- Wave 5 verified and closed: suite 808 -> 939 passed, integration e2e tests/e2e/test_wave5_integration.py, live regression PASS (logs/wave5-regression.log), evidence walkthrough/final/wave5/ (7 frames: MT toggle, race wizard emblems, in-game race icon + Goto, star panel polish, waypoint leg editor, encyclopedia trader + packets art), journal entry 38, stale wave-5 log dates corrected to 2026-07-27, task #24 done
- New acc-crit section "LLM Playtest Forensics" (6 criteria) - 100-turn claude -p vs claude -p game with forensics-to-fixes, runs AFTER all implementation, BEFORE wave-6 gate (tasks #28-30); wave-6 gate (#26) is now LAST
- **Correspondence Play RUNNING**: `wf_b1556989-d7a` (task wt7dgp3bj; scout -> full-stack implementer -> verifier; all 9 acc-crit criteria). If killed, RESUME:
  `Workflow({scriptPath: "/home/lab/.claude/projects/-home-lab-workspace-private-games-stars-ultranova-web/518b5b18-c8ff-44e1-9680-3dac877c6d5a/workflows/scripts/correspondence-play-wf_b1556989-d7a.js", resumeFromRunId: "wf_b1556989-d7a"})`
- **Functional harness RUNNING in parallel**: `wf_cb1bb133-fc0` (task wafa87u12; single builder - tests/functional/ Playwright harness, own server port 9820 + isolated DB, RUN_FUNCTIONAL=1 gate, 8 UI test modules incl. 30-turn fixed-seed gamethrough vs golden snapshot; touches ONLY new files, no backend/frontend edits). Task #31, blocks wave-6 gate. If killed, RESUME:
  `Workflow({scriptPath: "/home/lab/.claude/projects/-home-lab-workspace-private-games-stars-ultranova-web/518b5b18-c8ff-44e1-9680-3dac877c6d5a/workflows/scripts/functional-harness-wf_cb1bb133-fc0.js", resumeFromRunId: "wf_cb1bb133-fc0"})`
- New acc-crit section "Functional Browser Harness" (4 criteria) recorded 2026-07-27, TOC green
- On correspondence completion: review verify, journal entry, close #25, then #28 playtest harness build -> #29 100-turn detached run -> #30 forensics/fixes -> #26 wave-6 gate (also gated on #31)
- Commit #27 still awaits explicit user approval (working tree carries wave 5 + everything since 6dd2aa7)
- Dev server 9800 detached (health /health); suite baseline 939

## BRACE 2026-07-27 ~20:20 CEST - user-ordered brace mid-wave-5 (RESOLVED - resumed ~20:40 as task w62r8m5ax, 8 cached agents replayed)

**HORIZON: SESSION-ONLY (assumed - user gave none; matches prior usage-limit braces).** Cold-restart commands below cover a full server restart too.

### State at brace (all persisted)

- Wave 5 workflow `wf_c3d773f2-2d3` **explicitly PAUSED via TaskStop (task w328ga0nb) at 2026-07-27 ~20:20 CEST** - **8/10 agent results cached** in `journal.jsonl` (3 spec scouts + 5 of 6 implementers; the in-flight implementer was killed mid-run, its partial file edits may sit in the working tree - agents re-read files before editing, re-run is safe). Remaining live work on resume: last implementer(s) + verify:wave5
- **RESUME COMMAND** (first action of next session):
  `Workflow({scriptPath: "/home/lab/.claude/projects/-home-lab-workspace-private-games-stars-ultranova-web/518b5b18-c8ff-44e1-9680-3dac877c6d5a/workflows/scripts/wave5-trader-parity-ui.js", resumeFromRunId: "wf_c3d773f2-2d3"})`
- Per-agent results: `.../subagents/workflows/wf_c3d773f2-2d3/journal.jsonl`
- Dev server: gunicorn :9800 DETACHED via `./start.sh` (health 200 at `/health`, NOT /api/health) - survives SESSION-ONLY; after server restart relaunch with `./start.sh`
- Suite baseline 808 green at wave-4 close; wave-5 partials in working tree not yet verified
- Task list: #24 wave 5 in progress (this workflow), #25 correspondence play, #26 wave 6 gate, #27 commit remainder (NEEDS EXPLICIT USER APPROVAL - post-brace-checkpoint commits still gated)
- KNOWN FIX QUEUED: wave-5 agents stamp log date 2026-07-14 (script kept byte-identical for cache) - after wave completes, correct wave-5 `log:` dates to the actual completion date in acc-crit/mechanics/checklist docs
- Stop-hook goal SUSPENDED by brace: all features implemented, game plays end-to-end, all checklist features gameplay-checked, seeded reproducible e2e testing every feature, all passing

### FIRST ACTION next session (/brace-resume)

1. Read this section + TaskList; verify dev server (`curl -s http://localhost:9800/health`), `./start.sh` if down
2. **RESUME the paused wave-5 workflow** via the command above (already TaskStopped - safe to resume immediately; 8 cached agents replay, remainder runs live)
3. On completion: review verify, screenshot pass to `walkthrough/final/wave5/`, fix stale log dates, journal entry via /journal:update, close #24, proceed to #25 correspondence play then #26 wave-6 gate

## PREVIOUS 2026-07-27 ~18:40 CEST - Wave 5 RESUMED after credits outage

- 2026-07-14 outage: 7 of 9 wave-5 agents died on usage credits; 2 spec scouts (client-parity, mystery-trader) cached in journal.jsonl
- 2026-07-27: dev server relaunched via ./start.sh (health 200), workflow RESUMED via resumeFromRunId wf_c3d773f2-2d3 (task w328ga0nb) - cached scouts replay, 7 agents run live
- Task list recreated: #24 wave 5 (in progress), #25 correspondence play, #26 wave 6 gate, #27 commit (needs user approval)
- NOTE: wave-5 agents log with CTX date 2026-07-14 (script kept byte-identical to preserve cache) - correct log dates to 2026-07-27 in tracking docs after wave completes

## PREVIOUS 2026-07-14 ~01:30 CEST - Wave 4 CLOSED (808 green), Wave 5 IN FLIGHT

- Wave 4 verified: 808 passed, integration e2e + wave4-regression PASS, evidence walkthrough/final/wave4/ (4 frames), task #19 done, journal entries 36 (agent-written score/victory) + 37 (wave-4 close)
- Checkpoint 6ec3157 pushed; post-checkpoint wave-4 remainder uncommitted (score-victory + storm-protection + evidence) - commit needs user approval
- **Wave 5 RUNNING**: `wf_c3d773f2-2d3` (10 agents: 3 scouts, 6 implementers - client-parity trio, mineral packets FLESH decision, stargate rework + emission glare, mystery trader, panel polish, race icons - verifier). If killed, RESUME:
  `Workflow({scriptPath: "/home/lab/.claude/projects/-home-lab-workspace-private-games-stars-ultranova-web/518b5b18-c8ff-44e1-9680-3dac877c6d5a/workflows/scripts/wave5-trader-parity-ui.js", resumeFromRunId: "wf_c3d773f2-2d3"})`
- On wave-5 completion: review verify, screenshots to walkthrough/final/wave5/, close #20, then decide correspondence-play slot (#23, own mini-wave) before the wave-6 gate (#21)
- Dev server 9800 detached (health at /health); suite baseline 808

## BRACE 2026-07-13 ~23:37 CEST - usage limit hit mid-wave-4 (RESOLVED - wave 4 recovered and completed)

**HORIZON: SESSION-ONLY.** Wave 4 workflow `wf_761e6d66-939` COMPLETED PARTIALLY - its last 5 agents died on the session limit (resets 23:00 Europe/Warsaw). Not paused - the workflow task finished; recovery = RESUME by run id.

### State on disk (all verified green before the limit)

- Suite: **713 passed** (baseline 682 + relations' 31). Waves 1-3 fully verified; wave 3 evidence in `walkthrough/final/wave3/` (12 frames incl. About-dialog dedication, storm blob, tooltip, encyclopedia + 6 painterly artworks)
- Wave 4 landed so far: **impl:relations done** (Enemy/Neutral/Friend map, C# all-Enemy init, honored by battle targeting/minefields/sweeping/invasion/bombing/friendly refuel-repair, relation command API + relations dialog F7)
- Wave 4 FAILED on limit (to re-run): impl:battle-plans, impl:electronics-battle, impl:score-victory, impl:storm-protection, verify:wave4
- **RESUME COMMAND** (first action): `Workflow({scriptPath: "/home/lab/.claude/projects/-home-lab-workspace-private-games-stars-ultranova-web/518b5b18-c8ff-44e1-9680-3dac877c6d5a/workflows/scripts/wave4-combat-score-victory.js", resumeFromRunId: "wf_761e6d66-939"})` - 4 specs + relations replay from cache, the 5 failed agents run live
- Dev server: gunicorn port 9800 detached via `./start.sh`, health at `/health` (NOT /api/health). If down: `./start.sh`
- Journal entries 33 (wave 3) + 34 (encyclopedia artwork) validated, 0 errors
- Acceptance doc `docs/acc-crit-stars-ultranova-web.md` carries ALL user directives through 23:00: Mystery Trader canonical (wave 5), Correspondence Play (task #23), stargate rework (small/medium only, star-fuelled range, no minerals - wave 5), emission nebula glare (wave 5), wormhole stabiliser as station tech, Extensions: Exterminatus/Wrath of Milena, deep space station + packet relay, trade agreements, LLM narrator, officers + storylines, boarding/imprisonment, Henry's Hope, Jump wear, The Hunt (declared chase, growing stake, Vengeance Drive / Trophy of the Hunt prizes, rare confluence triggers)
- Credits dedication (menu-bar.js showAbout): "For my beloved son Henry, alienated from his father for so long..." + "with thanks to my beloved wife Ewa" - PERMANENT, browser-verified, task #22 done
- Tasks: #18 done, #19 in progress (wave 4), #20 wave 5 (updated scope), #21 wave 6 gate, #23 correspondence play
- Commits: NONE pending authorization - working tree carries waves 3-4 uncommitted per policy

### FIRST ACTION next session

1. Read this section + TaskList
2. Resume wave 4 via the command above; on completion: review verify, screenshot pass to walkthrough/final/wave4/, close #19, launch wave 5 (author script from wave-4 pattern + task #20 scope)

## BRACE 2026-07-13 ~16:50 UTC - usage limits (RESOLVED - wave 3 recovered and completed)

**HORIZON: SESSION-ONLY** - session dying on usage limits. Detached jobs survive; session-owned jobs (the running workflow) die and must be RESUMED, not relaunched from scratch.

### Running - survives on its own

- Dev server: gunicorn on port 9800, PID 284746, detached via `./start.sh`, logs `server.log`, health 200. No action needed. If ever down: `./start.sh`

### PAUSED by brace - /brace-resume MUST RESUME THIS

- Wave 3 workflow `wf_49e7938a-7e5` - **explicitly PAUSED via TaskStop (task whng2iiw4) at 2026-07-13 ~17:00 UTC** per user brace order. 6 results cached at pause (4 specs + cargo-ops + repair-refuel). Completed agents replay instantly on resume:
  - Done: 4 spec scouts + impl:cargo-ops (suite 594 passed) + impl:repair-refuel (suite 620 passed)
  - In flight at brace: impl:cloaking-intel (its partial file edits may sit in the working tree; agents re-read files before editing, so a re-run is safe)
  - Still to run: impl:mine-sweeping, impl:storm-overhaul, impl:encyclopedia-ui, verify:wave3
  - **RESUME COMMAND** (first action of the next session):
    `Workflow({scriptPath: "/home/lab/.claude/projects/-home-lab-workspace-private-games-stars-ultranova-web/518b5b18-c8ff-44e1-9680-3dac877c6d5a/workflows/scripts/wave3-fleetops-intel-storms-wf_49e7938a-7e5.js", resumeFromRunId: "wf_49e7938a-7e5"})`
  - Per-agent results: `.../subagents/workflows/wf_49e7938a-7e5/journal.jsonl`

### Valid on disk

- Suite at 620 passed as of repair-refuel completion (`uv run pytest tests/ -q` to confirm)
- Waves 1-2 fully landed and verified (574 baseline): seeded e2e harness (tests/e2e, deterministic turns), research/PRT/advantage-points, terraforming/alchemy/auto-build/remote-mining/defense-scanner-upgrades + InvadeTask port
- Wave 3 landed so far: cargo ops (waypoint CargoTask + fleet-to-fleet transfer), repair/refuel RegenerateFleet fidelity
- Acceptance criteria: `docs/acc-crit-stars-ultranova-web.md` (canonical, skill format; old ACCEPTANCE_CRITERIA.md deleted per user); test map `docs/FEATURE_CHECKLIST.md`; inventory `docs/ORIGINAL_GAME_MECHANICS.md`
- Journal entry 32 covers waves 1-2 (`journal-tools check`: 32 entries, 0 errors)
- Screenshots: `walkthrough/final/wave1-2/` (4 evidence frames); future waves get their own subfolder per user directive
- Regression logs: `logs/wave1-regression.log`, `logs/wave2-regression.log`; e2e recordings `logs/e2e/`

### Quarantined / caution

- Working tree may contain PARTIAL impl:cloaking-intel edits (agent was mid-flight). The workflow resume re-runs that agent; it re-reads files first. Checkpoint commit below includes these partials deliberately - do not treat committed state as wave-3-verified

### Campaign plan (tasks #16-#21)

- #16 Wave 1 done, #17 Wave 2 done, #18 Wave 3 in progress (resume workflow), #19 Wave 4 pending (relations/battle plans/electronics/score/victory + STORM PROTECTION addendum: orbit safe harbor, storm shields, shield/armor partial protection, rad-hardened races, total immunity attainable), #20 Wave 5 pending (waypoint edit, fleet picker, message goto, packets decision, PANEL POLISH, RACE ICONS + custom upload), #21 Wave 6 pending (full verification vs acc-crit doc, per-feature seeded e2e, browser gameplay pass with recordings, STORM BALANCE CALIBRATION via trial games)
- Method: one Workflow per wave - parallel spec scouts (C# refs), SEQUENTIAL implementers (shared repo, no worktrees), verifier (full suite + integration e2e + live autoplay regression + screenshot pass to walkthrough/final/waveN/). Executor model: user chose "Inherit Fable 5" for the whole campaign. Wave prompts embed CTX discipline block - copy it from the wave-3 script above
- Active Stop-hook goal (suspended by brace, resume after): all features implemented, game plays end to end, gameplay checks all checklist features, all tests execute, functional tests recorded, seeded reproducible e2e harness testing every feature, all passing

### Pending decisions / notes

- Git commit policy: brace checkpoint commit authorized; FURTHER commits need explicit user approval each time
- Out-of-scope declarations (user veto window open): mystery trader, random events, multiplayer turn model, extended diplomacy; mineral packets = wave 5 flesh-or-cut decision
- User UX directives all recorded in acc-crit doc + task descriptions (storm blob shape/dashed red boundary/local intensity, encyclopedia+tooltips, zoom clamp fit/1.2, panel padding, race icons)

### FIRST ACTION for next session (/brace-resume)

1. Read this file, then `docs/acc-crit-stars-ultranova-web.md` + TaskList
2. **RESUME the paused Wave 3 workflow** - the exact Workflow resume command above (prior run already stopped via TaskStop, safe to resume immediately; 6 cached agents replay, then cloaking-intel re-runs live followed by mine-sweeping, storm-overhaul, encyclopedia-ui, verify:wave3)
3. On wave-3 completion: review verify result, screenshot pass to `walkthrough/final/wave3/`, close task #18, launch Wave 4 per task #19
