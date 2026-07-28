# Engagement Range Doctrine - Orders Layer Design

What a commander orders about distance, and what the engine is told to do about it. This document covers the ORDERS layer only. The engine mechanics that make holding a range physically possible, and the damage model that decides whether chip damage at range is worth anything, are owned by `docs/research-standoff-canon.md`, which landed while this was being written and whose measurements are cited below. Every mechanics question here is named and handed over rather than answered.

## The finding, first

This is a **restoration, not an invention**. Canonical Stars! tactics are pure movement AI and two of the six already say "hold at maximum range" in so many words. The C# reference dropped the whole thing - `grep -n "Tactic" references/original-game/ServerState/BattleEngine.cs` returns no matches at all, and `MoveStacks` (BattleEngine.cs:501-600) unconditionally walks every stack toward its target via `PointUtilities.BattleMoveTo(from, to)` at line 594, with a standing admission at line 603 that strategy is not consulted. The port restored roughly half of it. The half still missing is the half that matters.

One thing here is genuinely new: the sequenced "salvo at range, then close for the finish" the user asked for. Canon has both poles but never the transition between them. It is a small invention expressed entirely in canon's own vocabulary.

## 1. What canon actually instructs about range

The authority is BATTLE.TXT and Guts of the Battle Engine as captured in `docs/research-battle-doctrine.md`. The load-bearing quotation is at `docs/research-battle-doctrine.md:39`, describing Maximise Net Damage: "If out of range with ANY weapon then move towards target. If in range with all weapons them move as to maximise damage_done/damage_taken. The effect of this is if your weapons are longer range then try to stay at maximum range... If your weapons are shorter range and also beam weapons then attempt to close in to zero range."

That single rule is the entire engagement-range axis, already written in 1995. The rest of the list positions itself around it:

- **Maximise Net Damage** - close until every weapon bears, then hold; stand off at maximum range when out-ranging the enemy, close to zero when out-ranged with beams
- **Maximise Damage Ratio** - identical, but "only considers the longest range weapon" (research-battle-doctrine.md:39), so a mixed design stands off at its torpedo's reach and never brings its beams to bear
- **Maximise Damage** - closes to range 0 whenever beams are mounted, because beams lose damage with separation (research-battle-doctrine.md:39)
- **Minimise Damage to Self** - "cause as much damage as possible while taking as little damage as possible" (BATTLE.TXT, research-battle-doctrine.md:34); the stand-off pole
- **Disengage** - open the range every square, 7 board moves to leave (research-battle-doctrine.md:43)
- **Disengage if Challenged** - Maximise Damage Ratio until damaged, then Disengage

So canon encodes hold-at-range explicitly and close-to-contact explicitly. What canon does not encode is a stack that changes its mind mid-battle from one to the other, and that is the only new mechanic proposed here.

Two canonical details the port collapsed and should not: the Maximise Net Damage band is set by the shortest weapon that must bear ("in range with ALL weapons"), while the Maximise Damage Ratio band is set by the longest. The port uses the longest for all three stand-off tactics (`ron_battle_engine.py:966-969`, `max(w.range for w in ...)`), so Maximise Net Damage currently behaves as Maximise Damage Ratio and a mixed beam-plus-torpedo design never closes to bring its beams up. That is a one-line divergence with real consequences for mixed designs.

## 2. What the port ships today

The order surface is `BattlePlan` in `backend/server/battle/battle_plan.py:258-329`: a name, five target tiers, a tactic, attack-who, a target id, and four doctrine axes - `stance`, `posture`, `withdraw`, `board`. It reaches the client through the `battle_plan` command (modes set / default / delete) and `POST /fleets/{key}/battle-plan` (`backend/api/routes/fleets.py:117-124`), plus the per-battle override `fleet.engagement_plan`.

The UI already enforces the cognitive-load principle. In `frontend/js/views/dialogs.js:1020-1060`, Stance is the only axis above the fold; the five tiers, posture, withdrawal, boarding, tactic and attack-who all sit inside a collapsed `<details>Detailed parameters</details>`. The fleet panel offers only a named-plan dropdown (`frontend/js/views/fleet-panel.js:497-505`). A commander who never opens the composer picks one of six admiralty plans and is done.

Movement lives in `RonBattleEngine._move_stacks` (`ron_battle_engine.py:852-1004`). It already implements the closing half of canon at lines 962-975: the three stand-off tactics close until the target is inside the stack's own longest weapon range, then set the heading to zero. What it never does is **back off**. A torpedo boat that has halted at 500 units watches a beam ship walk the last 300 units into contact and does nothing about it. Canon's rule is maintain-distance; the port implements approach-and-halt.

That gap is measured, not assumed. `docs/defects.md:114` (DEF-32) records that a mid-tier Juggernaut Missile fleet beat an equal-cost Mark IV Blaster fleet in **0 of 8 seeds** even with the stand-off tactic set on both sides, and gives the arithmetic: "the range advantage (500 units against 200) buys only about 1.5 rounds of free fire before contact because both sides close at once." Torpedoes and missiles lose every pairing at every tier in `tests/unit/test_battle_balance.py::test_no_weapon_class_dominates_at_equal_cost`, and the reach they pay for in cost, mass and accuracy is never converted into free shots.

`docs/research-standoff-canon.md` then measured the order's effect directly: patching in range maintenance alone, with every other defect left in place, moves late-tier torpedo from **0 of 16 to 10 of 16** against beams. That is the strongest evidence this design has, and it also sets the honest ceiling - the same audit puts a missile-only `hit_power / 10` divisor (`ron_battle_engine.py:1344`, present in neither canon nor the C#) ahead of movement as the largest single cause, worth roughly 13x in damage per shot. The orders layer converts reach into free fire; it does not make the shots land harder. Both fixes are needed and only the first is designed here.

## 3. The axis

One new field on `BattlePlan`, four values, doctrinal names following the genre convention already used for stances and postures.

- **Tactic Decides** - the tactic's own canonical range rule, both halves including the back-off. This is the default and it is exactly today's behaviour once the maintain-distance half is restored. Every legacy save loads with this value and fights unchanged
- **Close to Contact** - drive to zero range and stay there. Full beam power, the same square boarding needs, and a fleeing enemy cannot open the gap. Pays for it by eating every longer-ranged weapon on the way in
- **Hold at Range** - stand off at the outer edge of the stack's own effective reach and give ground when a threat closes inside that band. Never fires a short-ranged mount, cannot board, cannot stop an enemy disengaging
- **Salvo then Close** - Hold at Range until the target has been broken, then Close to Contact. The user's requested doctrine

The trigger for Salvo then Close is one number and one condition, both automatic: the target's armour falls to or below `CLOSE_FOR_KILL_ARMOUR_PERCENT` (proposed 50.0, a module constant, deliberately not a per-plan dial), or the target begins to disengage. The switch is per target and one-way - a stack that has committed to the run-in does not re-open the range when its target dies and a fresh one is assigned, because a fleet that oscillates between bands spends the battle in transit and fires from neither.

Three properties of the band, stated as order intent rather than mechanics:

- The band is measured against the **closest hostile armed stack that can reach**, not only against the assigned target. "Hold at range from my target while a different enemy shoots me at point blank" is an incoherent order
- **A stand-off order does not grant speed.** If the pursuer is faster it closes anyway and the order degrades to a fight at contact. No dice roll, no percentage - escape capability is bought at the shipyard with engines, manoeuvring jets and overthrusters, exactly as canon prices retreat (research-battle-doctrine.md:172)
- Giving ground is **not** disengaging. A stack keeping its band must not accumulate flee moves

## 4. Precedence - the single ordered list

Three systems currently claim authority over a stack's heading, and the axis makes a fourth. This ladder is the deliverable's spine; anything not on it is not an authority.

1. Destroyed, or already disengaged - no movement decision
2. Withdrawal threshold met, or the tactic resolves to Disengage (`ron_battle_engine.py:1029-1061`) - break off and count flee moves. **The engagement-range axis is ignored.** A withdrawing fleet runs
3. Unarmed hull - the canonical avoid-combat behaviour (BATTLE.TXT gives new unarmed fleets Default-Defense, "try to avoid combat entirely"). The axis is ignored, for the same reason DEF-31 un-pinned Brace's freighters: the axis fixes a firing position and an unarmed hull has none
4. Early manoeuvring rounds - unchanged
5. The engagement-range axis decides the heading. On **Tactic Decides**, the tactic's canonical rule runs, both halves

Aggressive stance forfeiting disengagement (`battle_plan.py:126`, `may_disengage=False`) governs step 2 only. It must not block a Hold at Range stack from giving ground in step 5 - these are two different meanings of "move away" and conflating them silently converts Standoff into Close for every Aggressive plan.

## 5. Brace

Brace's `holds_position` (`battle_plan.py:184-186`, consumed at `ron_battle_engine.py:914-916`) is the crude ancestor of this axis and the two collide immediately: a plan carrying Brace and Close to Contact is self-contradictory, and today's precedence would silently discard the Close and never report it.

**Recommendation: Brace survives, but loses `holds_position`.** Redefine it as the emplacement stat package it already is - shields x1.30, +1 square of weapon range, damage dealt x0.80 - and let the engagement-range axis own every movement decision. Brace then means "fight from a fixed firing solution" and its natural pairing, Brace plus Hold at Range, is Defensive Hold exactly as it reads today. A commander who wants literal zero movement gets it from Hold at Range with a band at the stack's own maximum reach, which is what Brace was doing.

The honest cost: this moves the anti-degeneracy matrix. `docs/defects.md:113` records that Brace's `damage_dealt` 0.80 was added specifically because un-pinning the unarmed hulls left holding position costing almost nothing, and Brace then won every matchup at 71 against 44 and 43. Removing `holds_position` removes the rest of what that 0.80 was paying for, so `tests/unit/test_battle_degeneracy.py::test_no_posture_wins_every_matchup` must be re-run and Brace's gunnery price re-derived. The DEF-31 log notes the value sits on a broad passing plateau (0.75-0.80 x shields 1.20-1.40 x range +0/+1), so a re-tune is likely cheap - but it is a re-tune, not a free rename.

The alternative - keep `holds_position` and declare that Brace forces the axis to Hold at Range - costs nothing to tune and leaves two overlapping concepts in the plan forever. Not recommended.

## 6. Defaults - every stance gets a doctrine

The user asked for a range doctrine in every strategy. In this codebase the admiralty standard plans **are** the doctrine (`docs/acc-crit-stars-ultranova-web.md:206` - "there is no separate doctrine object"), so the doctrine lands there rather than as a hidden per-stance rule. This keeps the field's default at Tactic Decides, so no legacy save and no hand-written plan changes behaviour, while every plan a commander actually picks carries an explicit range order.

| Plan | Stance | Tactic | Engagement range | Why |
|---|---|---|---|---|
| Aggressive Assault | Aggressive | Maximise Damage | Close to Contact | Kill the fleet this turn; beams at full power, prizes takeable, no escapes |
| Balanced | Balanced | Maximise Damage | Salvo then Close | Never wrong, rarely optimal - trades a slower kill for free opening shots |
| Defensive Hold | Defensive | Minimise Damage to Self | Hold at Range | Survive to the clock; the emplacement pairing |
| Commerce Raid | Balanced | Maximise Damage Ratio | Salvo then Close | Break the escort at range, then run down unarmed hulls that cannot shoot back |
| Escort Screen | Defensive | Maximise Net Damage | Hold at Range | A screen interposes, it does not chase |
| Fighting Retreat | Defensive | Maximise Damage Ratio | Hold at Range | Keeps the gap the withdrawal needs |

The composer gains one dropdown inside the existing collapsed `<details>` block. Nothing is added above the fold, so the one-dial path is untouched: the commander picks a named plan, and the plan carries the range order. The pre-battle engagement override (`fleet.engagement_plan`) carries it for free.

Open question for the wave owner, raised rather than acted on: the research doc's recommended list contained a **Standoff Barrage** preset that has no equivalent among the six. It is now expressible as Balanced plus Maximise Damage Ratio plus Hold at Range. Adding a seventh plan is a scope decision, not a design gap.

## 7. Why this is a trade and not a button

Take DEF-32's own arithmetic and re-run it under the order. A Juggernaut Missile fleet buys 15 hulls at power 150 and 20 percent accuracy - 450 effective throw weight per round. The Mark IV Blaster fleet buys 23 hulls at power 66 and 100 percent accuracy - 1518. The missile fleet therefore needs about **3.4 rounds of free fire** to break even on throughput. Today it gets 1.5, because both sides close at once and the 300-unit gap shuts at twice one side's speed.

Under Hold at Range with equal battle speeds, the net closing rate is zero and the free fire is bounded only by the board and the clock. At one speed step of advantage to the beam fleet (0.25 squares per round, 25 units), the 300-unit gap takes 12 rounds to cross - about 5400 damage delivered free, comfortably past break-even. At double speed the kite buys almost nothing, which is correct: the beam fleet bought engines instead of guns.

That is the trade in one sentence. Reach is only worth what your engines can hold, and engines cost mass and slots that would otherwise be weapons. It is the same currency canon charges for retreat, and it is enforced by the enemy's build, which the commander cannot fully see. The arithmetic is corroborated end to end: `docs/research-standoff-canon.md` measured range maintenance alone taking late-tier torpedo from 0 of 16 to 10 of 16 against beams.

Three honest limits:

- **Closing buys less damage than it looks.** Beam dissipation in this port is `100 - 10 * (d^2 / maxrange^2)` (`backend/server/battle/weapon_details.py:58-71`), so a beam at half its reach keeps 97.5 percent of its power and only loses the full 10 percent at maximum range. "Close for the finish" therefore earns its keep on kills, prizes and denied escapes - not on a damage multiplier. If the close pole needs to be worth more, the lever is the dissipation curve, and it belongs to the mechanics design, not here
- **Kiting needs a bounded board.** There is no boundary clamp anywhere in the engine (`docs/research-standoff-canon.md`), and DEF-30 measured stacks drifting to (2261, 2373) on a nominal 1000-unit board. Unbounded, a fast stand-off fleet retreats forever and wins on the clock without ever being caught, which would make Hold at Range the only order worth giving. Canon's 10 x 10 grid is the natural cap; the mechanics design owns which fix lands, and this axis must not ship before one does
- **Sixty rounds is not sixteen.** `MAX_BATTLE_ROUNDS = 60` (`ron_battle_engine.py:71`) against canon's 16 (research-battle-doctrine.md:71). Every free-fire count above scales with the clock, so a bounded-board kite gets nearly four times the free rounds canon intended and Hold at Range could become dominant. Either restore 16 or re-derive; the two cannot both be left alone

## 8. Options disqualified by cognitive load

The governing principle - "some commanders focus on grand strategy not petty battles" - rules out three shapes that otherwise look attractive.

- **A per-round range schedule** ("rounds 1-4 at range, close from round 5"). Battles resolve inside turn generation with no player input, so a schedule is a blind guess about a fight the commander cannot see. Salvo then Close's armour trigger reads the actual battle instead
- **Per-weapon or per-mount range orders**, the Aurora fire-control model. Requires the commander to reason about each design's mount list before every engagement. Disqualified
- **A mid-battle close order.** There is no mid-battle. The engagement override in the pre-generation window is the last moment orders exist, and the axis rides on it already

## 9. Proposed acceptance criteria

For the main session to register in `docs/acc-crit-stars-ultranova-web.md`. Not written there by this design.

- [ ] **Canonical stand-off movement restored** - the three stand-off tactics maintain their band instead of merely halting at it: a stack whose target closes inside the band gives ground while its speed allows, and giving ground never accumulates disengagement moves. Maximise Net Damage sets its band by the shortest weapon that must bear and Maximise Damage Ratio by the longest, per Guts of the Battle Engine
- [ ] **Engagement range axis** - a fifth doctrine axis on the battle plan (Tactic Decides / Close to Contact / Hold at Range / Salvo then Close), defaulting to Tactic Decides so every plan written before it existed fights unchanged; Salvo then Close holds the band until the target drops to CLOSE_FOR_KILL_ARMOUR_PERCENT armour or begins to disengage, then closes, one-way per target
- [ ] **Every standard plan carries a range order** - all six admiralty plans name an explicit engagement range; the axis is offered in the composer inside the existing detailed-parameters fold and nowhere above it, so the one-dial path adds no dial
- [ ] **Precedence is single and stated** - withdrawal and Disengage outrank the axis, unarmed hulls ignore it, and an Aggressive stance's forfeited disengagement does not prevent a Hold at Range stack from giving ground
- [ ] **Brace is stats, not movement** - Brace keeps its emplacement package (shields, weapon range, gunnery price) and surrenders holds_position to the range axis; the posture anti-degeneracy matrix is re-run and Brace's damage price re-derived on the new behaviour
- [ ] **Reach converts to free fire** - a torpedo or missile fleet on Hold at Range against an equal-cost, equal-speed beam fleet wins the pairing it currently loses 0 of 8, and the advantage decays as the beam fleet buys speed; proven by a seeded test over the equal-budget matrix
- [ ] **No range order wins every matchup** - the existing anti-degeneracy round-robin gains the axis as a fourth variable and each value is beaten somewhere and wins somewhere

## Sources

- `docs/research-battle-doctrine.md` - lines 34, 39, 43, 71, 172 (BATTLE.TXT and Guts of the Battle Engine quotations)
- `docs/research-standoff-canon.md` - the mechanics audit: the 0 of 16 to 10 of 16 range-maintenance measurement, the missile-only damage divisor, and the absent board boundary
- `references/original-game/ServerState/BattleEngine.cs:501-603` - MoveStacks; no reference to Tactic anywhere in the file
- `references/original-game/Common/DataStructures/BattlePlan.cs:42` - the Tactic field the engine never reads
- `backend/server/battle/battle_plan.py:106-195, 258-414` - stances, postures, plan fields, admiralty plans
- `backend/server/battle/ron_battle_engine.py:71-79, 502, 852-1004, 1029-1082` - clock and grid, boarding contact gate, movement, tactic resolution and flee counting
- `backend/server/battle/weapon_details.py:58-71` - beam dissipation curve
- `backend/api/routes/fleets.py:117-124`, `frontend/js/views/dialogs.js:1020-1060`, `frontend/js/views/fleet-panel.js:497-505` - the orders surface
- `docs/defects.md:108-115` - DEF-30, DEF-31, DEF-32
- `tests/unit/test_battle_balance.py:82-105` - the weapon table the arithmetic above uses
