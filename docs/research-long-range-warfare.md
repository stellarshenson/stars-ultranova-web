# Long-Range Warfare - Design Options

Torpedoes and missiles lose every pairing at every tech tier in `tests/unit/test_battle_balance.py`. This document lays out what can be done about it, what each choice costs, and which of them break the project's contract. It is a menu, not a survey. Pick from section 7.

Two prior documents are the evidence base and are not repeated here. `docs/research-standoff-canon.md` carries the code audit and every measurement quoted below. `docs/design-engagement-range.md` carries the orders-layer design for range maintenance. A third input, a comparative study of Starsector's flux economy, supplies section 5 and is summarised inline because it has no in-repo home.

## 1. The governing tension, stated plainly

This project's contract is a faithful port. `.claude/CLAUDE.md` says it in three places: "All game logic, rules, and calculations must match the C# source in `references/original-game/`", "preserve original logic exactly - do not improve or modernize algorithms", and "Feature parity is mandatory - no omissions or simplifications".

Every option in section 5 and section 6 violates that contract deliberately. They are not refinements of canon; they are new mechanics that Stars! does not have and never had. Adopting one means the port stops being a port in that respect, and every future question of the form "what does the original do here?" gains an answer of "we diverged, on purpose, in 2026". That is a real and permanent cost, and it is the user's call to pay it. The job of this document is to make sure the cost is visible before the choice is made, not to argue for it.

One clarification that matters for the honesty of the whole exercise: **removing the missile-only `/10` divisor is not a divergence.** It is present in neither canon nor the C# reference (`docs/research-standoff-canon.md`, table row "Missile damage divisor"). It is a defect in this port's own engine, applied to one damage path and not the other. Fixing it is what the contract already demands. It is listed under Option A for that reason and nowhere else.

The second governing constraint is the user's own: "It is all about cognitive load - some commanders focus on grand strategy not petty battles." A commander who never opens the battle screen must still fight coherently. Any mechanic that only pays off when the player hand-tunes designs against a specific enemy, reads battle logs to calibrate, or issues per-mount orders is disqualified on those grounds regardless of how well it balances. This rules out more of section 5 than section 4.

## 2. What is actually broken, in order of size

The standing hypothesis was that range buys nothing because every stack closes. That is real but secondary. Measured causes, largest first:

- **The missile-only damage divisor.** `_fire_missile` does `hit_power = hit_power / 10` (`ron_battle_engine.py:1344`); `_fire_beam` does not. Instrumented late-tier fight at equal 3000 budget: torpedo dealt 295 damage over 4 shots, beam 7155 over 9. That is 74 per shot against 795, a factor of 10.7, which is the divisor times the 0.75 accuracy roll
- **No range maintenance.** Stand-off tactics halt when the target enters their own reach (`ron_battle_engine.py:966-978`) and never give ground as the enemy keeps walking in. A range-5 torpedo against a range-3 beam at equal speed converts its whole reach advantage into exactly one free round
- **Weapon classes below beam/missile do not exist.** `WeaponType` (`component.py:31-36`) is referenced nowhere else in `backend/`. Gatlings, shield sappers and capital-ship missiles all resolve through the two generic paths
- **Mid and early tier are cost-dominated, not mechanic-dominated.** Mark IV Blaster buys 23 hulls at power 66 for 1518 nominal throw weight; Gatling Gun buys 682 and Epsilon Torpedo 912 before its 65 percent accuracy. No engine change moves that

There is also a live exploit not previously logged. Because `shieldSapper` takes the ordinary beam path, Syncro Sapper (power 541, range 3, cost 29, mass 1) cuts armour and beats Mega Disruptor, Big Mutha Cannon and Upsilon Torpedo 16 of 16 each. It is currently the strongest weapon in the game, and the balance harness misses it because it samples one weapon per group and never picks a sapper.

## 3. Option A - implement the missing canon

Everything in this section is already owed under the port's contract. Zero divergence, no design decision required beyond sequencing.

**A0. Remove the missile `/10` divisor, and fix the spill arithmetic that depends on it.** One line at `ron_battle_engine.py:1344`. The same defect is visible from the other side at `ron_battle_engine.py:1198-1204`, where `_generate_attacks` computes `damage_per = weapon.power * quantity / 10.0` for both classes: for missiles that matches delivery, for beams it understates output tenfold, so `percent_to_fire` saturates at 100 and the overkill-spill mechanism never engages at realistic force sizes. Fixing the divisor without fixing the spill denominator turns spill on for the first time, which is a behaviour change in its own right and needs its own measurement pass.

**A1. Capital-ship missiles double their damage to armour once shields are down.** The xfail at `tests/e2e/test_battle_scenarios_engine.py:719`. One branch on the weapon group inside `_fire_missile`. This is the entire justification for missile accuracy figures of 20 to 30 percent, and without it a missile is a strictly worse torpedo.

**A2. Gatlings sweep every stack in range.** The xfail at `test_battle_scenarios_engine.py:733`. Needs the enemy stack list at fire time, which `_execute_attack` already has via the source stack's target list.

**A3. Shield sappers damage shields only, never armour.** Not currently tracked as an xfail. One branch, and it closes the 16 of 16 exploit above.

**A4. Starbases reach one square further than the same weapon on a ship.** The xfail at `test_battle_scenarios_engine.py:791`. `range_bonus` in `_generate_attacks` comes solely from the Brace posture; `Stack.is_starbase` grants nothing.

**A5. Canonical range maintenance.** Guts of the Battle Engine on Maximise Net Damage: "if your weapons are longer range then try to stay at maximum range". The C# reference never consumes the tactic at all (`BattleEngine.cs:594`, with the gap admitted at `:603`), so this is canon-legal by the documentation but has no reference implementation to copy. Design already written up in `docs/design-engagement-range.md`. It has a hard prerequisite, below.

**A5-prereq. A board boundary, and a decision on the clock.** There is no boundary clamp anywhere in the engine, and DEF-30 measured stacks drifting to (2261, 2373) on a nominal 1000-unit board. Add range maintenance to an unbounded board and an equal-speed kiter holds range for all 60 rounds and wins on the clock, which makes Hold at Range the only order worth giving. Separately, `MAX_BATTLE_ROUNDS = 60` against canon's 16 inflates every free-fire count by roughly 4x. Both must be settled before A5 lands, and settling them is itself canon-restoration work.

### Is Option A sufficient? Measured answer

**The two xfailed mechanics alone: no, emphatically.** From the balance matrix, wins out of 16 at late tier:

| Change | Late-tier result |
|---|---|
| Shipped | torpedo 0/16 and missile 0/16 against every class; gatling dominates |
| A1 alone (missile armour bonus) | unchanged at late tier; mid tier missile 6/16 against torpedo, still 0 against beams |
| A2 alone (gatling sweep) | strictly worse - gatling now also beats missile 16/16 at mid tier |
| A0 alone (divisor removed) | torpedo 7/16 against beam, 5/16 against gatling; missile still 0-1 everywhere |
| **A0 + A1** | **no class dominates** - beam beaten by missile and gatling, torpedo beaten by beam and gatling, missile beaten by torpedo, gatling beaten by missile 9-7 |
| A0 + A1 + A2 | gatling returns to dominance at mid and late tier |
| A5 alone, divisor left in | torpedo 10/16 against beam at equal speed (medium confidence, see below) |

**Option A taken as a whole: yes at late tier, no at mid and early tier.** A0 plus A1 produces the target state - a matrix with no dominant class - and does so without a single line of non-canon mechanic. That is the strongest result in this document and it costs nothing against the contract.

It does not fix mid or early tier, because those tiers are lost on price rather than on mechanics. That is catalogue work, and section 5 has the only useful thing to say about it.

Two confidence caveats. The A5 measurement used a crude back-off patch and produced a non-monotonic result (a speed-2.5 kiter did worse, 5 of 16, than an equal-speed one at 10 of 16), which points at an artefact in the probe rather than a property of the mechanic; trust the direction, not the size. The A3 sapper result is unambiguous in the harness but the harness hull has no shields research behind it, so a sapper's real-game value is a strong candidate rather than a proven dominance.

**Cognitive load: zero for all of A.** Nothing here adds a decision. A5 adds one dropdown inside an already-collapsed detail block, defaulting to today's behaviour, with every named admiralty plan carrying its own range order so the one-dial path stays one dial.

## 4. Option B - canon-compatible extensions

These are not in Stars!. They fit its turn structure and would not look alien in it. Each is a deliberate divergence and is listed with what it changes and what it breaks.

**B1. Suppression: ranged fire that fails to kill still leaves something behind.** The transplantable core of Starsector's flux economy, stripped of real-time venting. A torpedo hit that fails to penetrate currently produces nothing at all; N rounds of reach produce N rounds of nothing, and the only thing that ever scores is total damage per resource at contact, which the beam wins by construction. The fix in shape: one integer per stack, incremented by ranged hits, decaying slower than one round, reducing effective shields or raising damage taken. Applied at end of round so simultaneous resolution stays order-independent.

- Changes: adds persistent per-stack combat state, which the engine has never had
- Risks: every existing balance and degeneracy test is invalidated at once, because the currency of a fight changes. The decay rate becomes a new global tuning knob with no canonical anchor. Battle reports must surface it or the commander cannot understand why a fight went the way it did
- Cognitive load: borderline. It demands no micromanagement, but it makes battle outcomes less legible, and illegibility is the same problem as micromanagement for a commander who never opens the battle screen

**B2. Long-range weapons as force multipliers rather than killers.** Starsector's Graviton Beam does trivial damage; its actual job is raising all shield damage the target takes from every source by 5 to 10 percent. Translated: a torpedo hit applies a stack-level debuff consumed by the whole fleet's fire that round. Cheaper than B1 because it need not persist.

- Changes: a per-round multiplier bucket on the target stack
- Risks: makes torpedoes only worth buying alongside beams, which is a real strategic statement but converts a standalone class into a support class. Mono-torpedo fleets get worse, not better
- Cognitive load: low. It rewards mixed fleets, which the commander already builds by default

**B3. Missiles as limited ammo with a hold-fire condition.** Per-battle shot limits plus the rule "hold fire until the target's shields are down". Converts missiles from bad sustained damage into a burst that only ever fires into the window where A1's armour double applies.

- Changes: a per-stack ammo counter and a firing gate, both evaluable at round start
- Risks: with a 60-round clock and no ammo, a missile stack becomes dead weight for the back half of a long fight. Interacts violently with the clock decision in A5-prereq
- Cognitive load: low, both halves are automatic

**B4. Per-shot-strength gating on armour.** Starsector's `damage / (damage + armour)` with a 15 percent floor. Punishes high-rate low-per-shot fire and rewards alpha strikes, which is the mathematical reason a big slow missile beats a fast small gun through armour.

- Changes: the armour damage formula for every weapon in the game
- Risks: the largest blast radius of anything in this section. It re-prices the entire catalogue implicitly and invalidates every damage figure in every test and document
- Cognitive load: low to use, high to explain

**B5. Re-price the catalogue against a calibrated range tax.** Not an engine change at all - `backend/data/components.xml` only. Starsector's most extreme range premium (Gauss Cannon) is 2x fitting cost for 1.67x range at 0.7x output, and is considered niche but usable. This port's Upsilon Torpedo is roughly 1.24x the cost and 12.5x the mass of Mega Disruptor for 1.67x range at 0.75x accuracy, and Doomsday Missile is 1.79x the cost for 25 percent accuracy. That is above the reference ceiling while delivering strictly less.

- Changes: cost and mass numbers in the data file. Zero engine cost
- Risks: it is a divergence from the original catalogue, which is exactly the kind of "improvement" the contract forbids, and the original numbers are the only real anchor the project has. It is also the **only** lever identified anywhere in this document that addresses the mid and early tier failures
- Cognitive load: zero

## 5. Option C - the radical choices

**C1. Restore the canonical board: 10 by 10 squares, 16 rounds, three movement phases per round, discrete one-square steps.** Canon runs 16 rounds (`BattleEngine.cs:42`) with 3 movement phases (`:41`), a moves-per-round table indexed by battle speed over an 8-round cycle (`:44-73`), and one-square steps where an axis moves only while strictly farther away (`PointUtilities.cs:224-247`). This port runs 60 rounds on a 1000-unit continuous grid with the two sides starting about 14 squares apart, off the notional board entirely, with no boundary anywhere.

This is the option that makes every other range question well-posed. A bounded 10-square board is only two weapon-ranges wide, so there is nowhere to kite forever; the free-shot window becomes pure arithmetic (range gap divided by closing rate, 1 to 4 rounds at speeds 0.5 to 2.5); and the boundary and clock prerequisites of A5 dissolve rather than needing separate patches. It is also fully canon-legal - it is the port's current board that is the divergence.

The cost is honest and large. `RonBattleEngine` is roughly the whole battle system, and its docstring claims it was "Ported from RonBattleEngine.cs" - **no such file exists under `references/original-game/`**. The engine that decides every battle in this game has no reference implementation in the repository, which is precisely why the `/10` divisor survived. Rewriting movement to a discrete board touches velocity vectors, `_break_off_heading`, disengagement counting, the battle viewer's rendering coordinates, `battle.grid_size`, and every scenario test's expectations about round numbers. Estimate: the largest single change on this list, and one that another workflow is currently editing around.

**C2. Adopt a flux economy wholesale.** Rejected, and stated here only so the rejection is on record. The mechanic's core is a mid-fight decision made under threat - vent now and be defenceless, or back off and contribute nothing. Stars! has no per-round decision layer and no player input during a battle. Automate the decision and it degenerates into a flat regeneration rate that carries none of the tension. Overload as a timed disable is worse: in a 16-round battle even a 4-round stun is a guaranteed kill. This is a new mechanic with a balance problem, not a translation.

**C3. Port `BattleEngine.cs` faithfully and retire the Ron engine.** The strictest reading of the contract. It would deliver the canonical board for free and remove the reference gap permanently. It would also throw away every mechanic this port implements and the C# does not: missile accuracy from computers and jammers, capacitors and deflectors on beam power, correct initiative ordering, mass-ordered movement, tactic consumption. The C# reference is measurably the worse engine of the two. Not recommended, listed for completeness.

## 6. What cognitive load disqualifies

Three shapes look attractive and are ruled out by "some commanders focus on grand strategy not petty battles":

- **Any mechanic requiring per-mount or per-weapon orders.** The Aurora fire-control model. It asks the commander to reason about each design's mount list before every engagement
- **Any mechanic requiring the commander to read a battle log to calibrate.** If understanding why a fight was lost requires opening the battle viewer and tracing a hidden counter, the commander who never opens it is playing blind. This is the specific charge against B1
- **A per-round range schedule or a mid-battle close order.** There is no mid-battle. Battles resolve inside turn generation with no player input, so a schedule is a blind guess about a fight that has not happened. The armour-threshold trigger in `design-engagement-range.md` reads the actual battle instead, which is the correct shape

## 7. Recommendation

**Take Option A in full, in sequence, and take B5 only if mid and early tier still fail after it. Take nothing else.**

The reasoning is the measurement. A0 plus A1 alone produces a late-tier matrix where no weapon class dominates, and both are things the port already owes: one is a defect in code that exists in neither canon nor the reference, the other is a canonical mechanic already sitting as a documented xfail. There is no case for paying the contract cost of a new mechanic when the canon-legal fix is measured to work.

Sequence, because the order matters and two of these make things worse if landed early:

1. **A0** - remove the divisor, and re-derive the spill denominator with it. Measure before continuing; this is the change that moves the matrix
2. **A3** - shield sappers to shields only. Closes a live 16 of 16 dominant purchase, and until it lands the balance matrix is measuring a game nobody is playing. Extend the balance harness to sample sappers, or the fix is unverifiable
3. **A1** - missile armour double. With A0 this reaches the no-dominant-class state, and it turns a missile into something other than a strictly worse torpedo
4. **A4** - starbase reach. Cheap, isolated, unrelated to the rest
5. **A5-prereq** - decide the board boundary and the clock. This is a design decision, not an implementation, and it gates everything after it
6. **A5** - range maintenance. This is the change that makes stand-off a *strategic* option rather than a damage-model outcome, which is what was actually asked for. It must not ship before step 5
7. **A2** - gatling sweep, last. Measured to entrench the class that is already on top; land it only after re-measuring post-A0, and expect it to require a gatling re-price to stay balanced
8. **B5**, conditionally - re-price torpedo and missile mass and cost at mid and early tier, if and only if those tiers still fail after step 7. It is a divergence and should be treated as a last resort, but it is the only identified lever that touches them

Defer B1, B2, B3 and B4 entirely. They are competent designs and one of them may eventually be wanted for its own sake, but none is needed to fix the measured failure, and each buys a permanent contract cost plus a full re-tune of the balance and degeneracy suites. B1 additionally trades away legibility, which for this project's stated principle is close to trading away the point.

One thing to fix regardless of which option is chosen: the `RonBattleEngine` docstring claims a reference file that does not exist. Either the real provenance goes in the docstring or the claim goes. An engine with no checkable reference is how a non-canon divisor survives long enough to decide every battle in the game.

## 8. Change table

| Change | Canon-legal | Engine cost | Fixes the measured failure |
|---|---|---|---|
| A0 - remove missile `/10` divisor, fix spill denominator | Yes (defect fix) | 1 line plus 2 in `_generate_attacks`, then a full re-measure | Yes - the single largest cause. Torpedo 0/16 to 7/16 |
| A1 - missile double damage to armour | Yes (xfail) | One branch in `_fire_missile` | Only with A0. Alone, no change at late tier. With A0, reaches no-dominant-class |
| A2 - gatling sweep | Yes (xfail) | Moderate - needs stack list at fire time | No - measured strictly worse. Land last |
| A3 - shield sapper cuts shields only | Yes | One branch in `_execute_attack` | Indirectly - removes a 16/16 dominant purchase the harness does not sample |
| A4 - starbase +1 square of range | Yes (xfail) | Small, in `_generate_attacks` range bonus | No - unrelated, but owed |
| A5 - canonical range maintenance | Yes (per Guts; C# never implements it) | Large - `_move_stacks` rework plus orders plumbing | Partly - 0/16 to 10/16 at medium confidence. Converts reach into free fire, not into harder hits |
| A5-prereq - board boundary and 16 vs 60 rounds | Yes (port's board is the divergence) | Small for a clamp, large if the clock changes | Prerequisite. Without it A5 makes Hold at Range dominant |
| B1 - suppression state from ranged fire | **No** | Large - new per-stack state, full re-tune | Yes in principle, unmeasured. Costs legibility |
| B2 - long-range weapons as force multipliers | **No** | Moderate - per-round debuff bucket | Partly - makes torpedoes support, not standalone |
| B3 - missile ammo plus hold-fire gate | **No** | Moderate - ammo counter, firing gate | Unmeasured. Interacts hard with the clock decision |
| B4 - per-shot-strength armour gating | **No** | Moderate to write, enormous to re-balance | Unmeasured. Re-prices the whole catalogue implicitly |
| B5 - re-price torpedo/missile cost and mass | **No** (data divergence) | Zero engine cost, `components.xml` only | The only lever that touches mid and early tier |
| C1 - restore 10x10 board, 16 rounds, 3 phases | Yes (canon) | Largest on this list - movement, viewer, every scenario test | Indirectly - makes every range question well-posed and dissolves A5-prereq |
| C2 - flux economy wholesale | **No** | Very large | Rejected - needs a mid-fight decision layer that does not exist |
| C3 - port `BattleEngine.cs`, retire Ron engine | Yes (strictest reading) | Very large, and regressive | No - the C# is the worse engine; drops five mechanics this port has |

## Sources

- `docs/research-standoff-canon.md` - the code audit and every balance measurement quoted above
- `docs/research-battle-doctrine.md` - BATTLE.TXT, Guts of the Battle Engine, Iztok's battle-speed article
- `docs/design-engagement-range.md` - the orders-layer design for A5, precedence ladder, Brace interaction, admiralty plan defaults
- `docs/defects.md:108-115` - DEF-30 unbounded drift, DEF-31 Brace tuning, DEF-32 the 0 of 8 missile result
- `references/original-game/ServerState/BattleEngine.cs:41-73, 501-606, 761-810, 869-930` - rounds, movement table, MoveStacks, fire paths, the double-damage FIXME at :802
- `references/original-game/Common/PointUtilities.cs:224-247` - BattleMoveTo
- `references/original-game/BUGS.txt:120` - the missile double-damage bug, acknowledged upstream
- `backend/server/battle/ron_battle_engine.py:71-74, 966-978, 1186-1230, 1290-1362` - clock and grid, tactic movement, attack generation, fire paths
- `backend/core/components/component.py:31-36, 68-81` - `WeaponType`, referenced nowhere else; the two-way beam/missile collapse
- `tests/unit/test_battle_balance.py:60-105` - the equal-budget harness and its weapon table
- `tests/e2e/test_battle_scenarios_engine.py:719, 733, 791` - the three xfailed canon mechanics
- Starsector comparative study - flux, damage-type asymmetry, point defence as an interception class, the Gauss Cannon range-tax calibration. Sourced from the official Starsector wiki; no in-repo home, summarised inline in sections 4 and 5
