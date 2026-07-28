# Engagement Range Doctrine - The Orders Layer

What a commander orders about distance, and what the engine is told to do about it. This document designs the ORDERS layer only. The engine mechanics that make holding a range physically possible, and the damage model that decides whether chip damage at range is worth anything, belong to `docs/research-standoff-canon.md`, which landed while this was being written and whose measurements are cited throughout. Every mechanics question raised here is named and handed over rather than answered.

## The finding, first

This is a restoration, not an invention. Canonical Stars! tactics carry no stat modifiers at all - they are pure movement AI - and two of the six already say "hold at maximum range" in so many words. The C# reference dropped the whole thing: `grep -n "Tactic" references/original-game/ServerState/BattleEngine.cs` returns no matches, and `MoveStacks` walks every stack toward its target unconditionally through `PointUtilities.BattleMoveTo(from, to)` at line 594, with a standing admission at line 603 that strategy is never consulted. The port restored about half of it. The half still missing is the half the user is asking for.

That matters for the argument. The stance layer shipped today moves initiative, missile accuracy, shields and disengagement - four stat modifiers (`battle_plan.py:113-131`). Canon attaches none of those to a tactic. So the shipped doctrine layer is the divergence from canon, and an engagement-range doctrine, being pure movement AI, moves toward canon rather than away from it. The claim was checked against `docs/research-battle-doctrine.md` sections 1 and 3 and it holds. BATTLE.TXT itself is not present in this repository; the research doc is the citable proxy and carries the retrieval URLs.

One thing here is genuinely new. Canon has both poles - stand off at maximum range, close to zero with beams - but never a stack that changes from one to the other mid-battle. The user's "long distance salvo, then close-up finish" is that transition, and it is the only invented mechanic in this design.

## 1. What canon instructs, and what the port does

The load-bearing quotation is at `docs/research-battle-doctrine.md:39`, describing Maximise Net Damage: "If out of range with ANY weapon then move towards target. If in range with all weapons them move as to maximise damage_done/damage_taken. The effect of this is if your weapons are longer range then try to stay at maximum range... If your weapons are shorter range and also beam weapons then attempt to close in to zero range."

That one rule is the engagement-range axis, written in 1995. Maximise Damage Ratio is "as Maximise Net Damage but only considers the longest range weapon", so its band is set by the longest weapon while Maximise Net Damage's is set by the shortest weapon that must bear. Maximise Damage closes to range 0 whenever beams are mounted. Minimise Damage to Self is the stand-off pole. Disengage opens the range every square and needs 7 board moves to leave.

The port implements the closing half and not the maintaining half. `RonBattleEngine._move_stacks` at `ron_battle_engine.py:962-978` closes until the target is inside the stack's own longest weapon range and then sets the heading to zero. It never backs off. A torpedo boat that halted at 500 units watches a beam ship walk the last 300 units into contact and does nothing. It is approach-and-halt, a one-way ratchet, not maintain-distance. The same block uses `max(w.range ...)` for all three stand-off tactics, so Maximise Net Damage currently behaves as Maximise Damage Ratio and a mixed beam-plus-torpedo design never closes far enough to bring its beams up. That is a one-line divergence with real consequences.

The cost is measured, not assumed. `docs/defects.md:114` (DEF-32) records a mid-tier Juggernaut Missile fleet losing to an equal-cost Mark IV Blaster fleet in 0 of 8 seeds even with the stand-off tactic set on both sides, and gives the arithmetic: the range advantage of 500 units against 200 "buys only about 1.5 rounds of free fire before contact because both sides close at once". `docs/research-standoff-canon.md` then measured the fix: patching in range maintenance alone, every other defect left in place, moves late-tier torpedo from 0 of 16 to 10 of 16 against beams.

## 2. The axis

One new field on `BattlePlan`, named `engagement_range`, alongside the existing `stance`, `posture`, `withdraw` and `board`. Four values. Doctrinal names, following the naming convention the rest of the plan already uses.

**Tactic Decides** is the default and a no-op. The tactic's own canonical range rule runs, both halves, including the restored back-off and the shortest-versus-longest weapon split. Every plan written before the axis existed loads with this value through `from_dict` and fights exactly as it does today, once the restoration lands. This is also the answer to "close to optimal range and fight there" from the brief: canon already computes the optimal band per tactic, and adding a separate axis value for it would duplicate the tactic list. That reduction is deliberate - it is one fewer option to explain and one fewer row in the anti-degeneracy round-robin.

**Close to Contact** drives to zero range and stays there. Movement is the plain closing heading every round, capped at the target by `_cap_at_target`, with no halt band and no back-off. It is the existing Maximise Damage branch, promoted from a tactic side effect to an order. It buys full beam power, the same square that boarding requires (`ron_battle_engine.py:502`), and denial of escape. It pays by eating every longer-ranged weapon on the way in.

**Hold at Range** stands off at the outer edge of the stack's own reach and gives ground when a threat closes inside that band. Concretely, per round, with `R` the stack's longest weapon range in units including the posture range bonus:

- if the distance to the assigned target exceeds `R`, close on the normal heading
- if the distance to the nearest hostile armed stack falls below `0.9 * R`, move a full step directly away from that stack
- otherwise hold, heading zero

The band is `[0.9R, R]` rather than a single value because a single value oscillates: a stack one unit inside its band steps out, overshoots, steps back in, and spends the battle in transit firing from neither position. The 10 percent deadband is the same device Stellaris uses, holding a target between 70 and 90 percent of formation distance (`research-battle-doctrine.md:96`). The back-off is measured against the nearest hostile armed stack rather than the assigned target, because "hold at range from my target while a different enemy shoots me at point blank" is an incoherent order.

**Salvo then Close** is Hold at Range until the fight is decided, then Close to Contact for the rest of the battle. This is the doctrine the user asked for and it is covered in its own section below.

Three properties hold across all four values and are order intent rather than mechanics:

- A stand-off order does not grant speed. If the pursuer is faster it closes anyway and the order degrades to a fight at contact. No dice roll and no percentage: escape capability is bought at the shipyard with engines, manoeuvring jets and overthrusters, exactly as canon prices retreat (`research-battle-doctrine.md:172`)
- Giving ground is not disengaging. A stack keeping its band must not touch `_count_flee_move` (`ron_battle_engine.py:1063-1082`). If it shares that path it accumulates flee rounds, hits `DISENGAGE_MOVES` at 7, and silently leaves the board. Standoff would become Withdraw and the commander would never be told
- Starbases never move and are unaffected. `_move_stacks` skips them at the same gate the C# uses

## 3. The close-for-the-kill trigger

A trigger the commander cannot predict is worse than no trigger, so this is specified as one condition with one number, both fixed.

**A stack commits to the run-in when its current target's armour falls to or below 50 percent of that target's armour at the start of the battle, or when its current target begins to disengage.** The commitment is a single boolean on the stack, one-way, and it lasts the rest of the battle.

The armour fraction is the right reading for three reasons. It is already computed: `Stack.token.armor` and `Stack.token.initial_armor` are stored per stack at `stack.py:32-36` and populated at `stack.py:60-63`, so the trigger costs one division. It is monotonic, because armour never heals during a battle, which means the trigger fires once and never un-fires. And it is the number the commander can already see in the battle report and on the ship list, so the order reads as plain English: hold until you have broken them, then finish them.

One argument for the threshold does not survive contact with the shipped damage model and is dropped rather than quietly kept. The intended pricing was that a stack's armour pool is `armor * quantity`, so at half armour roughly half the ships are dead and the run-in is taken into half the return fire. `docs/research-damage-model.md` measured that this is false in this engine: damage is pooled per token, `quantity` is never decremented by gunfire, and a token shot to its last armour point still fires at full rate - instrumented at 462.0 hit power with 22 of 1750 armour left, and 0 of 29 armour hits reducing a ship count. So under the engine as it stands the run-in is not cheaper for having salvoed first, and Salvo then Close is worth strictly less than it looks. It becomes worth what it should once per-ship kills land, which the C# reference itself records as the canonical algorithm it failed to implement (`BattleEngine.cs:857`, "damage is being spread over all ships in the stack. Should destroy whole ships first"). The trigger is designed against canon, and its value is deferred until canon arrives.

Fifty percent rather than 25 or 75 is a first estimate and must be swept by `tests/unit/test_battle_balance.py`, ideally after per-ship kills land, since the sweep before and after will not agree. At 75 percent the trigger fires after roughly one good salvo and the doctrine collapses into Close to Contact. At 25 percent there is usually nothing left to finish and it collapses into Hold at Range. The number lives as a module constant, `CLOSE_FOR_KILL_ARMOUR_PERCENT = 50.0`, deliberately not as a per-plan dial: a threshold the commander must tune is a dial on the primary path, and the governing principle rules it out.

The second condition, the target beginning to disengage, exists because Hold at Range cannot stop an enemy leaving. Without it, the one situation where closing is unambiguously correct - a broken enemy walking off the board with your kills aboard - is the one situation the doctrine refuses to act on.

The commitment is per stack and one-way rather than per target. Per target, a stack that finishes a crippled enemy and is handed a fresh one re-opens the range and spends the next rounds walking backwards through a fleet it is already inside. One-way means the order reads as a single sentence a commander can predict: once their line breaks, my fleet charges and does not come back.

Three triggers were considered and rejected. Enemy shields down is unpredictable in the wrong direction: a great many designs carry no shields at all, so the condition is already true at round one and the doctrine silently becomes Close to Contact against exactly the unshielded light hulls it should be shooting from range. Rounds elapsed is a blind guess about a fight the commander cannot watch, and the clock it would be tuned against is not canonical - `MAX_BATTLE_ROUNDS = 60` (`ron_battle_engine.py:71`) against canon's 16. Own ammunition does not exist: there is no ammunition model anywhere in `backend/server/battle/` or `backend/core/components/`, so that trigger would require a new subsystem before it could be read.

## 4. Precedence

Four systems now claim authority over a stack's heading. This ladder is the spine of the design; anything not on it is not an authority.

1. Destroyed, or already disengaged - no movement decision
2. Withdrawal threshold met, or the tactic resolves to Disengage (`_effective_tactic`, `ron_battle_engine.py:1029-1061`) - break off and count flee moves. The engagement-range axis is ignored. A withdrawing fleet runs
3. Unarmed hull - the canonical avoid-combat behaviour, since BATTLE.TXT gives new unarmed fleets Default-Defense, whose initial behaviour is "to try to avoid combat entirely". The axis is ignored, for the same reason DEF-31 un-pinned Brace's freighters: the axis fixes a firing position and an unarmed hull has none
4. Early manoeuvring rounds, `battle_round < 5` - unchanged
5. The engagement-range axis decides the heading. On Tactic Decides, the tactic's canonical rule runs

One trap deserves naming. An Aggressive stance forfeits disengagement entirely (`battle_plan.py:126`, enforced at `ron_battle_engine.py:1058-1059`). That must govern step 2 only. If it also blocks a Hold at Range stack from giving ground in step 5, then every Aggressive plan silently becomes Close to Contact and the axis stops existing for a third of the doctrine. "Cannot leave the battle" and "cannot step backwards" are two different orders and conflating them is the most likely implementation bug in this design.

## 5. Brace

Brace's `holds_position` (`battle_plan.py:184-186`, consumed at `ron_battle_engine.py:914-916`) is the crude ancestor of this axis, and the two collide on contact. A plan carrying Brace and Close to Contact is self-contradictory, and today's precedence would silently discard the Close and never report it.

**Recommendation: Brace survives and loses `holds_position`.** Redefine it as the emplacement stat package it already is - shields x1.30, plus one square of weapon range, damage dealt x0.80 - and let the engagement-range axis own every movement decision. Brace then means "fight from a fixed firing solution", and its natural pairing, Brace plus Hold at Range, is Defensive Hold exactly as that plan reads today. A commander who wants literal zero movement gets it from Hold at Range with the band at the stack's own maximum reach, which is what Brace was doing.

The honest cost is a re-tune, not a rename. `docs/defects.md:113` records that Brace's `damage_dealt` 0.80 was added specifically because un-pinning the unarmed hulls left holding position costing almost nothing, after which Brace won every matchup at 71 against 44 and 43. Removing `holds_position` removes the rest of what that 0.80 was paying for, so `tests/unit/test_battle_degeneracy.py::test_no_posture_wins_every_matchup` must be re-run and Brace's gunnery price re-derived. The DEF-31 log notes the passing region is a broad plateau - damage 0.75 to 0.80 by shields 1.20 to 1.40 by range +0 or +1 - so the re-tune is likely cheap, but it is work and it is currently an open task (#44).

Brace plus Close to Contact becomes legal under this change and reads slightly oddly: an emplacement package on a charging stack. It is accepted rather than forbidden, because the combination is priced (a third more shields and a square of reach for a fifth of the gunnery) and because forbidding it means a validation rule and an error message on a path the design is trying to keep free of dials.

The alternative - keep `holds_position` and declare that Brace forces the axis to Hold at Range - costs no tuning and leaves two overlapping concepts in the battle plan forever, one of which silently overrules the other. Not recommended.

## 6. Defaults

The user asked for a range doctrine in every strategy. Two layers carry it, and the distinction between them is what keeps old saves intact.

**Stance defaults are authoring defaults, not runtime fallbacks.** When a commander picks a stance in the composer, the range dropdown moves to the stance's default. The stored field still defaults to Tactic Decides, so a plan written before the axis existed is never reinterpreted at runtime.

| Stance | Engagement range | Why this and not another |
|---|---|---|
| Aggressive | Close to Contact | The stance already forfeits disengagement; committing to contact is the same commitment expressed positionally |
| Balanced | Salvo then Close | Free opening shots, then the kill. Never wrong, rarely optimal - the same character the stance has on every other axis |
| Defensive | Hold at Range | Survive to the clock, keep the hulls, force the enemy to spend the approach |

Three visibly different answers, which is the test the axis has to pass to be worth its cost.

**The six admiralty plans carry an explicit value**, because in this codebase the standard plans are the doctrine - `docs/acc-crit-stars-ultranova-web.md:206` states there is no separate doctrine object. This is the one-dial path: the commander picks a named plan in the fleet panel and the plan brings its range order with it.

| Plan | Stance | Tactic | Engagement range | Why |
|---|---|---|---|---|
| Aggressive Assault | Aggressive | Maximise Damage | Close to Contact | Kill the fleet this turn - beams at full power, prizes takeable, no escapes |
| Balanced | Balanced | Maximise Damage | Salvo then Close | Trades a slower kill for free opening shots |
| Defensive Hold | Defensive | Minimise Damage to Self | Hold at Range | The emplacement pairing, now with one authority over movement instead of two |
| Commerce Raid | Balanced | Maximise Damage Ratio | Salvo then Close | Break the escort at range, then run down hulls that cannot shoot back. Against unarmed prey the armour trigger fires almost at once, so the plan self-converts to a charge, which is the right behaviour |
| Escort Screen | Defensive | Maximise Net Damage | Hold at Range | A screen interposes, it does not chase |
| Fighting Retreat | Defensive | Maximise Damage Ratio | Hold at Range | Keeps open the gap the withdrawal needs |

The composer gains one dropdown, placed inside the existing collapsed `<details>Detailed parameters</details>` block in `frontend/js/views/dialogs.js:1020-1060`. Nothing is added above the fold, where Stance currently sits alone. The per-battle override (`fleet.engagement_plan`, `backend/core/game_objects/fleet.py:265-270`) carries the axis for free, because it selects a whole plan.

**A fourth stance is not warranted. Recommend against.** Three reasons, in order of weight. The obvious fourth stance is a standoff or artillery stance, and that is precisely what this axis now expresses - adding it as a stance would repeat the exact mistake `holds_position` made, two concepts owning one decision. Second, `tests/unit/test_battle_degeneracy.py` runs a round-robin per axis in which every value must beat something and be beaten by something, and task #44 records that this matrix does not currently pass; adding a fourth value to an unsatisfied constraint system is not free. Third, the user's requirement is that every strategy carries a fight doctrine, and the table above delivers three visibly different ones.

If a fourth visible choice is wanted, it should be a seventh admiralty plan rather than a fourth stance, because plans are cheap and stances are not. The natural candidate is the **Standoff Barrage** preset the research doc recommended (`research-battle-doctrine.md:307`), which has no equivalent among the six and is now exactly expressible: Defensive stance, Maximise Damage Ratio, Scatter posture, Hold at Range. That is a scope decision for the wave owner, not a design gap.

## 7. How this reads in the battle report

A commander who never opens the battle screen must still see why their fleet fought the way it did. Three changes, in descending order of importance.

**The turn message is the only text that commander reads.** Today `turn_generator.py:1816` produces "A battle took place at X. N of your ships were destroyed." Add one clause naming the plan and its range order: "Your fleets fought under Balanced - salvo, then close." No numbers, no second sentence. This is the single load-bearing change for the governing principle, and it is one f-string.

**Movement steps gain a motive.** `BattleStepMovement` carries only a stack key and a position (`battle_step.py:41-56`), and the viewer renders it as "X moves to (400, 300)" (`battle-viewer.js:589-592`), which tells a commander nothing. Add one short string - closing, holding at range, giving ground, committed, withdrawing - and the log reads "Torpedo Line holds at range" and then "Torpedo Line commits - target below half armour". The precedent is in the same file: `BattleStepTarget` already carries `priority` and `target_role` purely so the log can say why a target was picked, and the comment at `battle_step.py:80-84` says so. Same pattern, same justification, and no new step type is needed - the commitment announces itself on the first movement step that closes.

**No new report surface beyond that.** The battle viewer already draws positions and plays back steps; a separate range indicator would be a fourth thing to read for a commander who chose not to read the first three.

## 8. Does this fix torpedoes

No, not alone, and the honest answer has three parts.

At late tier it does most of the work. `docs/research-standoff-canon.md` measured range maintenance alone, with every other defect left in place, taking torpedo from 0 of 16 to 10 of 16 against beams. Run the DEF-32 arithmetic and the mechanism is visible: a Juggernaut Missile fleet buys 15 hulls at power 150 and 20 percent accuracy for 450 effective throw weight per round, against a Mark IV Blaster fleet's 23 hulls at power 66 and full accuracy for 1518, so the missile fleet needs about 3.4 rounds of free fire to break even. Today it gets 1.5, because both sides close at once. Under Hold at Range at equal speed the net closing rate is zero and free fire is bounded only by the board and the clock; at one speed step of advantage to the beam fleet, 25 units per round, a 300-unit gap takes 12 rounds to cross. At double speed the kite buys nearly nothing, which is correct - the beam fleet bought engines instead of guns.

For missiles specifically it changes almost nothing until a sibling fix lands. `ron_battle_engine.py:1344` divides missile hit power by 10 and `_fire_beam` does not, which the same audit measured as worth roughly 13x in damage per shot and ranked ahead of movement as the largest single cause. Missile classes sit at 0 or 1 of 16 everywhere with the divisor in place. The orders layer converts reach into free fire; it does not make the shots land harder.

There is also a tax on reach that this axis cannot pay off on its own, and it is the sharpest reason the axis is insufficient alone. `docs/research-damage-model.md` establishes that a token's firepower is proportional to `quantity`, that `quantity` never falls to gunfire, and therefore that a token reduced to its last armour point still fires at one hundred percent. Chip damage accumulates arithmetically - the "sustained fire at range adds up to nothing" hypothesis is false as stated - but it never converts into dead enemy guns unless a single exchange exceeds a whole token's pool. That is precisely what free rounds of stand-off fire are for. A beam fleet loses nothing to the rule because it fights to annihilation at contact anyway, so the rule is not neutral between weapon classes: it is a tax paid only by the class that fights at range. Measured stranded armour, with the divisor lifted so torpedoes land at all: 1919 points of a 6750 beam-side pool at early tier, 1268 of 5750 at mid, killing nothing and reducing incoming fire by nothing. The sequencing that follows is divisor first, then per-ship kills, then this axis - and a workflow that lands them in another order will measure each one as smaller than it is.

At mid and early tier it changes nothing, because those tiers are cost-dominated rather than mechanic-dominated. Mark IV Blaster buys 23 hulls at 66 power for 1518 nominal against Epsilon Torpedo's 912 before a 65 percent accuracy roll; early tier is Laser at 270 against Beta Torpedo at 264 before 45 percent. No movement rule moves a catalogue price.

Estimated effect on the measured matrix, stated as an estimate: late-tier torpedo against beams moves from 0 of 16 to somewhere near 8 to 11 of 16, torpedo against gatling improves similarly since gatlings reach 2 squares against a torpedo's 5, missile classes stay near 0 until the divisor is removed, and mid and early tiers move by a couple of cells at most. Confidence is high that the axis is necessary and insufficient, medium on the late-tier magnitude, and low on mid tier. The magnitude caveat is the sibling's own: its kiting probe was a rough back-off applied after the normal move, not a canonical implementation, and it produced a non-monotonic result in which a speed-2.5 kiter did worse at 5 of 16 than an equal-speed one at 10 of 16. The direction is trustworthy, the size is not.

**Two engine prerequisites this axis must not ship without.** Both belong to the mechanics design.

- There is no board boundary anywhere in the engine, and DEF-30 measured stacks drifting to (2261, 2373) on a nominal 1000-unit board. Unbounded, a fast stand-off fleet retreats forever and wins on the clock without ever being caught, which makes Hold at Range the only order worth giving. Canon's 10 by 10 grid is the natural cap
- `MAX_BATTLE_ROUNDS = 60` against canon's 16. Every free-fire count above scales with the clock, so a bounded-board kite gets nearly four times the free rounds canon intended. Either restore 16 or re-derive the numbers; the two cannot both be left alone

## 9. Rejected by cognitive load

The governing principle - some commanders focus on grand strategy, not petty battles - disqualifies three shapes that otherwise look attractive. Each is disqualified because it only works under micromanagement.

A per-round range schedule, "rounds 1 to 4 at range, close from round 5", is a blind guess: battles resolve inside turn generation with no player input, so the commander is scheduling a fight they cannot see. The armour trigger reads the actual battle instead.

Per-weapon or per-mount range orders, the Aurora fire-control model (`research-battle-doctrine.md:116`), require reasoning about each design's mount list before every engagement. Disqualified outright.

A mid-battle close order has nowhere to live. There is no mid-battle. The pre-generation engagement override is the last moment orders exist, and the axis rides on it already.

## 10. The options, priced

| Option | Canon-legal | Engine cost | Effect on the torpedo and missile failure |
|---|---|---|---|
| Tactic Decides (default) | Yes - it is canon, restored. Maximise Net Damage and Maximise Damage Ratio both say "stay at maximum range" (`research-battle-doctrine.md:39`) | Moderate. About 15 lines in the existing stand-off branch of `_move_stacks`: add the back-off, split the band by shortest weapon for Maximise Net Damage and longest for Maximise Damage Ratio, and keep flee counting out of it | The largest single share. This is the behaviour the sibling measured at 0 of 16 to 10 of 16 for late-tier torpedo. Does nothing for missiles while the `/10` divisor stands |
| Close to Contact | Yes. Maximise Damage closes to range 0 with beams | Near zero. It is the existing default branch, reached by skipping the stand-off halt | None directly, and that is correct. It is the pole that punishes a stand-off order when the enemy is faster, which is what stops Hold at Range being a button |
| Hold at Range | Yes as behaviour, new as an explicit order. Canon reaches it through the tactic rather than a separate field | Highest of the four. About 20 lines plus a helper: nearest-hostile-armed scan, the 0.9R to R deadband, back-off away from that stack, and an explicit guarantee that giving ground never touches `_count_flee_move` | Direct. It is the order that converts reach into free shots against an enemy whose tactic would otherwise let it walk in. Needs the board boundary or it becomes dominant |
| Salvo then Close | Partly. Both poles are canon, the transition is invented | About 8 lines, one boolean on `Stack`, one module constant | Positive but second-order, and currently suppressed. It gives up free-fire rounds for kills, prizes and denied escapes, so it should measure slightly below Hold at Range against beams and above it against fleeing or unarmed prey - but until per-ship kills land, a broken target still shoots back at full rate and the run-in is not the discount the doctrine assumes |

## Sources

- `docs/research-battle-doctrine.md` - lines 34, 39, 43, 96, 116, 172, 307 (BATTLE.TXT and Guts of the Battle Engine quotations, Stellaris maintain-distance precedent, Aurora fire control, Standoff Barrage preset)
- `docs/research-standoff-canon.md` - the mechanics audit: the range-maintenance measurement, the missile-only damage divisor, the absent board boundary, and the confidence caveats
- `docs/research-damage-model.md` - whole-token damage resolution, the stranded-armour measurements, and the finding that lumpiness taxes only the class that fights at range
- `docs/research-long-range-warfare.md` - the mechanics menu this axis is one item of (option A5), and its board-boundary prerequisite
- `docs/design-engagement-range.md` - the first pass at this design, which this document supersedes
- `references/original-game/ServerState/BattleEngine.cs:501-603` - MoveStacks, and no reference to Tactic anywhere in the file
- `references/original-game/Common/DataStructures/BattlePlan.cs:42` - the Tactic field the engine never reads
- `backend/server/battle/battle_plan.py:40-47, 106-195, 258-329, 338-414` - tactics, stances, postures, plan fields, admiralty plans
- `backend/server/battle/ron_battle_engine.py:71-79, 502, 852-1004, 1029-1082, 1344` - clock and grid, boarding contact gate, movement, tactic resolution, flee counting, the missile divisor
- `backend/server/battle/stack.py:32-36, 60-63` - the armour fields the trigger reads
- `backend/server/battle/battle_step.py:41-107` - movement and target steps, and the precedent for carrying a reason
- `backend/server/turn_generator.py:1816` - the battle message a commander who never opens the battle screen reads
- `frontend/js/views/dialogs.js:1020-1060`, `frontend/js/views/battle-viewer.js:583-615`, `frontend/js/views/fleet-panel.js:497-505` - the orders surface and the battle log
- `docs/defects.md:108-115` - DEF-30, DEF-31, DEF-32
- `docs/acc-crit-stars-ultranova-web.md:206` - the standard plans are the doctrine
- `tests/unit/test_battle_balance.py:82-105` - the weapon table the arithmetic uses; `tests/unit/test_battle_degeneracy.py:383-405` - the per-axis round-robins

---

## Review - cognitive load (adversarial)

Independent hostile review against the governing principle: "It is all about cognitive load - some commanders focus on grand strategy not petty battles." Verdict first: **the four-value axis does not survive; the requirement behind it does, at roughly a fifth of the cost.** Eight objections, all reproduced against the shipped code, then the smallest version.

### What holds

Section 1's canon argument is verified and load-bearing. `grep -n "tactic" backend/server/battle/ron_battle_engine.py` returns thirteen hits and every one sits inside `_move_stacks` (927-978) or `_effective_tactic` (1029-1061). Tactic touches movement and disengagement and nothing else - not targeting, not accuracy, not shields. So the claim that canonical tactics are pure movement AI is true of this port as well as of BATTLE.TXT.

Section 9 is right, the fourth-stance rejection is right, putting the control inside the existing fold is right, and `CLOSE_FOR_KILL_ARMOUR_PERCENT` as a module constant rather than a per-plan dial is right. The section 4 warning that `may_disengage` must not block giving ground is the sharpest thing in the document and must survive whatever else changes.

### O1 - the design repeats the error it diagnoses, one section later

Section 5 rejects `holds_position` on the ground that two concepts must not own one decision. Section 2 then creates a second movement authority with four values, and section 4 step 5 confirms it overrules the first. Three of the four values are aliases of tactic values already on the plan: Close to Contact is Maximise Damage, Hold at Range is Minimise Damage to Self or Maximise Damage Ratio once the restoration lands, and Tactic Decides is "defer to the other dropdown". Exactly one value, Salvo then Close, is not expressible as a tactic.

Worked example. A commander opens Detailed parameters in `dialogs.js:1027-1066` and sees, seven rows apart in the same fold, "Engagement range: Hold at Range" and "Tactic: Maximise Damage". Both are declarative movement orders. They contradict. The dialog gives no indication that the first mutes the second, no validation fires, and the plan saves. That is `holds_position` again with four values instead of one boolean.

### O2 - interaction edges go from five to nine

The honest measure is not the product of the option lists (76.5 million plan states today, 306 million after) but the number of cross-control rules a commander must hold. Today there are five: stance `may_disengage` overrides withdraw and the Disengage tactic; posture `holds_position` overrides tactic movement; `disengage_moves` and `disengage_moves_delta` stack and floor at `MIN_DISENGAGE_MOVES`; boarding needs contact, which movement decides; "Disengage if Challenged" rewrites the tactic mid-battle.

The design adds four and rewires one. Range overrides tactic movement. Aggressive's forfeited disengagement must not block giving ground. Brace stops overriding tactic movement and range starts. The Salvo latch changes which rule applies partway through a battle the commander cannot watch. And boarding now interacts with range, which is O3. One new control, an eighty percent increase in the interaction surface, and the new control is the most entangled thing on the plan.

### O3 - board plus Hold at Range is a null order, and the design never mentions it

`_find_boarding_target` (`ron_battle_engine.py:494-503`) requires `dist_sq <= self.GRID_SCALE_SQUARED`, the same square, and requires the prize's shields to be down. Hold at Range forbids the stack from ever entering that square. So `board="When Able"` with `engagement_range="Hold at Range"` is an order that can never execute, and nothing tells the commander.

This is not a corner case, it is the natural path. Boarding is the riskiest thing on the plan (`BOARDING_FAILURE_ARMOR_PERCENT = 50.0`, able to kill the boarder outright), so the obvious commander response is a Defensive stance. The proposed authoring default then writes Hold at Range into the fold and the boarding order is dead on arrival. Section 4's precedence ladder has no boarding step and section 6's tables have no boarding column.

### O4 - the zero-decision path is broken for every in-progress game

`seed_admiralty_plans` (`battle_plan.py:428-430`) adds a plan only `if name not in battle_plans`, and `game_manager.py:2589` calls it on every load. Every save written since the doctrine wave already contains "Balanced", so it is skipped and loads with `engagement_range` at Tactic Decides rather than the Salvo then Close the section 6 table promises.

It is worse than a stale table. `game_manager.py:2591` sets `default_battle_plan = empire_dict.get("default_battle_plan", "Default")`, and the plan literally named "Default" is `BattlePlan(attack="Enemies")`: tactic Maximise Damage, stance Balanced, range Tactic Decides. Maximise Damage keeps the closing heading (`ron_battle_engine.py:976`). So in a loaded game the grand-strategy commander gets none of the axis, their torpedo fleets still charge, and the section 7 turn message names a plan with no range order to report. Two commanders using a plan with the same name fight differently according to save vintage, and the one who never opens the battle screen has no way to discover it. Section 6 presents this as the safety property; on the primary path it is the failure.

### O5 - "no stored plan is ever reinterpreted" is false, and section 5 is why

Section 6 states the stored field defaults to Tactic Decides "so a plan written before the axis existed is never reinterpreted at runtime". Section 5 removes `holds_position` from Brace, which reinterprets every stored plan carrying Brace.

Worked example. A player's custom plan "Fortress" is Brace, Maximise Damage, Balanced stance. Today `_move_stacks:914-916` hits `continue` and its armed stacks never move for the whole battle. After the change Brace has no `holds_position`, `engagement_range` loads as Tactic Decides, Maximise Damage keeps the closing heading, and the fortress charges across the board. The two sections contradict and section 6 is the one that is wrong. If Brace is redefined, the compatibility claim must be narrowed to "plans that do not carry Brace".

### O6 - the degraded value is on the default path, and the turn message announces it

`DEFAULT_EMPIRE_PLAN = "Balanced"` (`battle_plan.py:417`), and Balanced is both the empire default and the Balanced stance's authoring default, so Salvo then Close is what a commander who decides nothing gets in a new game.

Section 3 then records, honestly, that this is the one value the shipped engine degrades: `quantity` never decrements to gunfire and a token on its last armour point fires at full rate, instrumented at 462.0 hit power with 22 of 1750 armour remaining. At the fifty percent trigger the enemy has lost exactly zero guns. The doctrine's own plain-English reading, "hold until you have broken them, then finish them", is false in this engine, because nothing has been broken. The stack abandons the only advantage it has for a discount that does not exist.

The document reaches that finding and then leaves the value on the default path anyway, and section 7 proposes to state it in the turn message: "Your fleets fought under Balanced - salvo, then close." The one commander who will never verify the claim is the one being told it. If Salvo then Close ships before per-ship kills, it should be a value a commander opts into, and the default should be the value that was measured at 0 of 16 to 10 of 16.

### O7 - the stance coupling punishes exactly the commander it is meant to help

`showBattlePlans` rebuilds the whole dialog string on every list change, so the `<details>` fold reverts to closed. Today no control in that dialog writes to another; stance is a plain `<select>` at `dialogs.js:1022-1026`. The authoring default introduces the first cross-field write, and it targets a control the commander cannot see.

Worked example. A commander opens the fold once, deliberately sets Engagement range to Hold at Range for a torpedo wing, saves, comes back later and changes Stance to Aggressive because they want the two points of initiative. Their explicit range order is silently rewritten to Close to Contact behind a collapsed fold. They save and their torpedo wing charges. The cost lands on the commander who engaged with the system once and then went back to grand strategy, which is the worst possible group to punish under the governing principle. If the coupling is kept, it must apply only while the field is still at its stored default and must never overwrite an explicit value.

### O8 - the encyclopedia article is already the longest doctrine text in the game

Measured on `encyclopedia.js`, the `battle-doctrine` entry is 634 words. The four values, the 0.9R deadband, the nearest-hostile rule, the two-condition trigger, the five-step precedence ladder and the Brace redefinition are realistically another two hundred, a third again. The precedence ladder has nowhere else to live, so it cannot be cut, and a commander who wants to know why their boarding order never fired has to read all of it.

### The smallest version that still solves the torpedo problem

Three parts, one new field, and that field is a checkbox.

**Part 1, the restoration, with no new field at all.** Fix the stand-off branch of `_move_stacks` (962-978): add the back-off with the 0.9R to R deadband measured against the nearest hostile armed stack, split the band by shortest weapon for Maximise Net Damage and longest for Maximise Damage Ratio, and keep `_count_flee_move` out of it. This is the entire measured gain. Section 10 of this document credits Tactic Decides, which is exactly this fix, with the whole 0 of 16 to 10 of 16, and credits the other three values with nothing measured. It adds zero controls, zero plan fields, zero save migration, zero round-robin rows and no Brace re-tune.

**Part 2, the doctrine requirement, on the existing tactic field.** The tactic dropdown is already canon's engagement-range axis with six values and it already sits in the fold. Stance authoring defaults move it: Aggressive to Maximise Damage which closes to contact, Balanced to Maximise Net Damage which holds the band at the shortest weapon that must bear, Defensive to Minimise Damage to Self which is the stand-off pole. Three visibly different fight doctrines, satisfying the user's requirement, with no new data-model field.

**Part 3, the one genuinely new thing, as a boolean.** `close_for_kill: bool = False`, UI label "Close for the kill", in the fold. When true, a stack switches to the Maximise Damage rule for the rest of the battle once its current target drops to `CLOSE_FOR_KILL_ARMOUR_PERCENT` or begins to disengage. Same latch, same constant, same one-way per-stack semantics as section 3. This is the user's verbatim "closeup finishoff" and it is the only part of the brief the tactic list cannot already express.

Admiralty spread under this version, achieved by editing one existing field on two plans:

| Plan | Tactic | Close for the kill |
|---|---|---|
| Aggressive Assault | Maximise Damage | not applicable, already at contact |
| Balanced | Maximise Net Damage (was Maximise Damage) | yes |
| Defensive Hold | Minimise Damage to Self | no |
| Commerce Raid | Maximise Damage Ratio | yes |
| Escort Screen | Maximise Net Damage | no |
| Fighting Retreat | Maximise Damage Ratio | no |

Identical spread to the section 6 table. What it costs instead: one checkbox rather than a four-value dropdown, zero new movement authorities rather than one, Brace keeps `holds_position` so task #44 needs no re-derivation, the degeneracy suite gains a two-value round-robin rather than a four-value one, and the encyclopedia gains roughly forty words rather than two hundred. Every one of O1, O2, O3, O5, O7 and O8 disappears, and O6 becomes a straight choice of which tactic the Balanced stance authors.

Honest costs of the smaller version, stated rather than hidden. "Maximise Net Damage" is 1995 jargon and the doctrine is invisible under that label, so the tactic options need plain-language suffixes in the composer, for example "Maximise Net Damage - hold at range". That is a label change, not an axis. The version cannot express "stand off while running the Maximise Damage tactic", which is verified irrelevant because tactic has no non-movement effect anywhere in the engine, and because that combination is a contradiction in terms. And O4 still applies to it: `seed_admiralty_plans` must be given a field-level migration, or the two edited plans must be versioned, or no existing game gets any of this.

**Degenerate option.** If only one thing ships, ship Part 1 alone. It carries the whole measured torpedo gain, adds no control, changes no stored plan and needs no encyclopedia text. The user's doctrine requirement is then met by Part 2, which is a UI change with no data-model change at all.

## Review - degeneracy (adversarial)

The charge: this game has already been beaten once by a dominant strategy, and `tests/unit/test_battle_degeneracy.py` exists because of it. Does the axis replace one degenerate choice with another?

Every number below was measured, not argued. Method follows the sibling audit's: throwaway processes that import the fixture helpers from `tests/unit/test_battle_balance.py` and `tests/unit/test_battle_degeneracy.py` and monkeypatch `RonBattleEngine._move_stacks` in memory with the four options exactly as section 2 specifies them - `R` from the stack's own longest weapon plus posture bonus, the `[0.9R, R]` deadband, back-off against the nearest hostile armed stack, no `_count_flee_move`, the 50 percent armour latch for Salvo then Close. No file under `backend/`, `frontend/` or `tests/` was modified. Balance margins are the mean of the 8 seeds the balance test already uses, on its equal 3000-resource budgets; positive means the beam side came out better.

### The verdict

The axis does not survive as a fifth field. It survives as a restoration.

The finding is not the one the brief anticipated. Hold at Range does not become universally correct. It becomes correct or worthless depending on one binary fact the axis does not control, and the four values measure as two behaviours that the tactic field already selects between. What is left after the duplicates are removed is section 1's restoration, which is worth having and does not need a new field to deliver.

### D1 - the axis is a second, coarser copy of the tactic axis

Measured directly. Late tier, equal speed, the beam side fixed on Maximise Damage with the axis on Close; only the torpedo side's tactic and axis value vary.

| Torpedo side tactic | Tactic Decides | Close to Contact | Hold at Range |
|---|---|---|---|
| Maximise Damage | +0.94 | +0.94 | +0.04 |
| Maximise Damage Ratio | +0.04 | +0.94 | +0.04 |
| Maximise Net Damage | +0.04 | +0.94 | +0.04 |
| Minimise Damage to Self | +0.20 | +0.94 | +0.04 |

Tactic Decides is not a fifth value. It is a chameleon that equals Close to Contact under a closing tactic and equals Hold at Range under a stand-off tactic, to two decimal places, because once the restoration lands they are the same code. The axis therefore offers a commander who has already chosen a tactic exactly one new thing: the ability to contradict it. Section 2 argues that a separate "close to optimal range" value is unnecessary because "canon already computes the optimal band per tactic". That argument does not stop where the section stops it. It applies to the whole axis.

The consequence for the anti-degeneracy suite is concrete. `_variants` builds every axis matrix from the Balanced standard plan, whose tactic is Maximise Damage (`battle_plan.py:353`), and Balanced is `DEFAULT_EMPIRE_PLAN`. So for every fleet flying the default plan, two of the four values on the new dropdown are the same order under different names.

### D2 - the proposed round-robin criterion fails on three of its four values

Criterion 9 asks that the degeneracy suite gain the axis as a fourth per-axis round-robin, each value beaten somewhere and winning somewhere. Run as specified, using `_variants` and the existing nine force pairings, three seeds, two withdrawal contexts - 648 battles:

| Value | Total wins | Matchups beaten in | Matchups won |
|---|---|---|---|
| Tactic Decides | 92 | 0 | 9 |
| Close to Contact | 92 | 0 | 9 |
| Hold at Range | 66 | 12 | 0 |
| Salvo then Close | 70 | 8 | 2 |

`unbeaten` is `[Tactic Decides, Close to Contact]` and `inert` is `[Hold at Range]`. Both assertions in `_assert_non_degenerate` fire. Tactic Decides and Close to Contact are unbeaten because they are the same option and tie each other in all thirty-six cells, so neither can beat the other and nothing else can beat either. Hold at Range never wins a single matchup out of thirty-six.

The reason Hold is inert here and dominant in the balance matrix is the same reason, and it is D3. `ARCHETYPES` gives the long-ranged archetype the slowest speed - Missile Boat range 5 at speed 0.75, Beam Line range 2 at 1.0, Sabre Wing range 1 at 1.5 - so no stack in that fixture can ever hold range against anything. The two suites sit on opposite sides of a cliff. Writing criterion 9 as it stands asks for a test that cannot pass against a fixture that cannot detect the failure.

### D3 - Hold at Range is a step function of one binary fact, not a decision

Late tier, beam closing, torpedo holding, torpedo speed fixed at 1.0:

| Beam battle speed | 1.0 | 1.25 | 1.5 | 1.75 | 2.0 | 2.5 |
|---|---|---|---|---|---|---|
| late, margin | +0.04 | +0.86 | +0.91 | +0.92 | +0.93 | +0.94 |
| mid, margin | -0.11 | +0.92 | +0.95 | - | +0.96 | - |

Section 8 predicts a decay: "at one speed step of advantage to the beam fleet, 25 units per round, a 300-unit gap takes 12 rounds to cross". There is no decay. One quarter-step - the smallest increment `ShipDesign.battle_speed` can express, since it clamps to [0.5, 2.5] and rounds to 0.25 - erases 91 percent of the effect at late tier and 100 percent of it at mid. The mechanism is arithmetic: at equal speed the net closing rate is exactly zero and free fire is bounded only by `MAX_BATTLE_ROUNDS`; at any deficit it is finite and the beam fleet's raw throw weight decides the fight as it does today.

An axis whose value is decided by a single binary comparison the commander can read off the design screen before the battle is not a decision. It is a lookup with a dropdown attached.

### D4 - almost all of the measured gain is unbounded retreat, not reach

This is the sharpest result. Same equal-speed setup, capping how many give-ground moves a stack may spend in a battle:

| Give-ground budget | late | mid | early |
|---|---|---|---|
| 0 (halt only, no back-off) | +0.92 | +0.97 | +0.98 |
| 2 | +0.87 | +0.96 | +0.98 |
| 4 | +0.79 | +0.95 | +0.98 |
| 6 | +0.70 | +0.94 | +0.97 |
| 8 | +0.64 | +0.93 | +0.97 |
| unlimited | +0.04 | -0.11 | -0.04 |
| shipped behaviour, for reference | +0.94 | +0.98 | +0.98 |

Eight give-ground moves is more board movement than canon requires to leave a battle entirely (`DISENGAGE_MOVES = 7`) and it still leaves the beam side winning by 0.64. The payoff does not saturate at any canon-shaped number; it appears only when retreat is unlimited. Restoring the back-off half of the canonical rule and then bounding it at all reclaims between 0.02 and 0.30 of the 0.90 the design attributes to it.

Confirmed from the other direction by clamping positions to the nominal 1000-unit board:

| Late tier, equal speed | unbounded | bounded |
|---|---|---|
| torpedo on Hold at Range | +0.04 | +0.72 |
| mid tier, same | -0.11 | +0.94 |

Section 8 lists the board boundary as a prerequisite that stops Hold at Range being "the only order worth giving". It is not a guardrail on the mechanic. It is the mechanic. Criterion 8 ("a torpedo fleet on Hold at Range wins the late-tier pairing it currently loses") and criterion 10 ("the axis does not ship before the battle board has a boundary") cannot both be satisfied by this design, and criterion 8 was written against a measurement taken on the board criterion 10 forbids.

### D5 - the equal-speed premise is an artefact of the fixture, and the catalogue contradicts it

`tests/unit/test_battle_balance.py:143` hard-codes `battle_speed=1.0` on both sides and never charges the weapon's mass to the hull. The real formula does: `speed -= _summary_mass / 70.0 / 4.0 / num_engines` (`ship_design.py:298`). Catalogue masses - Mega Disruptor 2, Mark IV Blaster 2, Upsilon Torpedo 25, Epsilon Torpedo 25, Doomsday Missile 35. Four mounts of Upsilon Torpedo against four of Mega Disruptor is 92 extra mass, which on a single engine is 0.33 of battle speed and after rounding is one to two quarter-steps.

So in a real game the torpedo hull is the slower hull, systematically, by exactly the increment D3 measures as fatal. Measured at that ratio, torpedo 0.75 against beam 1.0 on the balance fixture: late +0.95 on Tactic Decides against +0.83 on Hold at Range, mid +0.97 against +0.93. Hold at Range buys the slower torpedo fleet between 0.04 and 0.12, not 0.90. On the degeneracy fixture's mixed force at the same speed ratio it buys 0.117 (-0.915 to -0.798).

Criterion 8 asks for a win by "an equal-cost, equal-speed" torpedo fleet. Equal cost and equal speed are not simultaneously purchasable in this catalogue. The criterion describes a fleet that cannot be built.

### D6 - Salvo then Close has no regime where it is the best answer

Measured against Hold at Range in both fixtures:

- degeneracy fixture, Missile Boat against Beam Line: Hold -0.798, Salvo -0.798. Identical to three decimals - the armour latch never fires before the fight is decided
- balance fixture at the real speed ratio, late tier: Hold +0.83, Salvo +0.85. Within noise
- balance fixture at equal speed, late tier: Hold +0.04, Salvo +0.73. Salvo gives back 77 percent of what Hold buys
- round-robin totals: 70 against Hold's 66 and Close's 92, winning 2 matchups of 36

The pattern is consistent. Where Hold is worthless, Salvo equals Hold and both equal doing nothing. Where Hold is decisive, Salvo is most of the way back to Close. There is no force pairing measured here in which Salvo then Close is the order a commander should have given. Section 3 already concedes the pricing argument is false under the shipped damage model; this is what that concession costs in the matrix. The value is deferred behind per-ship kills, which is honest, but it means the axis ships with three of its four values delivering either nothing or a duplicate.

### D7 - the back-off complication is unpriced

Section 2 argues at length that back-off must be measured against the nearest hostile armed stack rather than the assigned target. Measured both ways:

| | late | mid | early | long-range mirror, Hold against Close |
|---|---|---|---|---|
| nearest hostile armed | +0.04 | -0.11 | -0.04 | +0.42 |
| assigned target | -0.06 | -0.07 | -0.04 | +0.48 |

The simpler rule is equal or slightly better everywhere measured. The nearest-hostile scan costs a helper, a per-round scan over every stack, and a paragraph of justification, and buys nothing detectable. I also tested the obvious repair for the case the rule is meant to cover - evaluating the threat clause before the close clause, so a stack never walks toward a distant target while an armed enemy sits inside its band - and it made the missile mirror worse, not better (1 of 6 to 0 of 6). Neither the complication nor its repair earns its place.

### D8 - two of the design's own default assignments measure backwards

The six-plan round-robin was run twice on the existing `test_no_standard_plan_wins_every_matchup` fixture, once with every plan on Tactic Decides and once with the section 6 spread of 1 Close, 2 Salvo, 3 Hold, with Brace surrendering `holds_position` as section 5 recommends.

| Plan | Total, baseline | Total, proposed | Assigned value |
|---|---|---|---|
| Aggressive Assault | 65 | 70 | Close |
| Balanced | 91 | 86 | Salvo |
| Defensive Hold | 71 | 91 | Hold |
| Commerce Raid | 43 | 37 | Salvo |
| Escort Screen | 88 | 80 | Hold |
| Fighting Retreat | 28 | 21 | Hold |

Good news first: neither run produces an unbeaten or an inert plan, so the proposed spread does not break the existing test. That part of the design holds.

Two of the rationales do not. Fighting Retreat is assigned Hold at Range because it "keeps open the gap the withdrawal needs"; it drops from 28 to 21 and is beaten in 33 of 36 matchups. Escort Screen is assigned Hold because "a screen interposes, it does not chase"; it drops from 88 to 80. Both are Defensive plans on the stance whose authoring default is Hold, and both are worse for it.

And the Brace reconciliation is not the cheap re-tune section 5 estimates. Defensive Hold gains 20 points and becomes the strongest plan in the matrix, measured with Brace's `damage_dealt` 0.80 price still in place. DEF-31 added that 0.80 to stop Brace winning every matchup; removing `holds_position` while keeping the price makes the plan that carries Brace stronger, not weaker. Task 44 gets harder, not easier, and in the opposite direction to the one section 5 anticipates.

### The counter-pressure that would keep each option honest

Three of the four options need none, because after D1 they are not distinct options. The one that does is the stand-off behaviour, and the counter-pressure it needs is not a modifier - it is a bound on how far a stack may give ground.

**Bound the ground, not the board.** A per-stack give-ground allowance, spent one move at a time and never refunded, in the same idiom the engine already uses for `DISENGAGE_MOVES`. It converts the free-fire window from "unbounded at equal speed, zero otherwise" into `(allowance + range gap) / closing rate`, which is finite in every case and is the arithmetic canon actually describes. D4 gives the curve to pick from: the payoff is smooth and monotone in the allowance across late, mid and early tier, so it is a tunable with a plateau rather than a cliff. It also works on the unbounded board that ships today, which the board clamp does not - and unlike the clamp it does not depend on where the fight happened to start.

Set against `DISENGAGE_MOVES = 7`, an allowance of 3 or 4 reads as plain English: a stack may give a little ground to keep its guns bearing, but a stack that wants to open the range properly has to declare a withdrawal and take the withdrawal's costs. That is a doctrine statement, not a tuning constant.

**Charge the stand-off in the currency it saves.** If a second pressure is wanted after the allowance, the honest one is that giving ground is manoeuvring, not shooting. The engine has no fire-versus-move tradeoff anywhere today, so this is an invention and should be treated as one - listed here because it is the only other lever that scales with how much a stack actually kites, rather than with how the fight started.

**Do not use speed as the counter-pressure.** D3 and D5 together show why: it is already the counter-pressure, it is binary, and the catalogue has already picked the winner. Any tuning that leans on "buy engines to beat a kiter" is tuning against a comparison that torpedo hulls lose by construction.

### What survives, and what it should be replaced with

Section 1 survives intact and is the valuable half of this document. The port implements the closing half of the canonical rule and not the maintaining half, `ron_battle_engine.py:966-978` uses `max()` where Maximise Net Damage wants the shortest weapon that must bear, and both are defects with a canonical source. Fixing them is owed under the contract and needs no new field, no new dropdown, no encyclopedia text and no migration.

What should not ship is the fifth field. Measured, it offers four labels for two behaviours, its default value is a chameleon for the other two, its one distinct behaviour is decided by a speed comparison rather than by the commander, and its headline benefit exists only on the unbounded board the same document forbids. Adding it to an anti-degeneracy constraint system that task 44 already records as unsatisfied would add a fourth value that fails the constraint on the first run, which D2 measured.

The user's requirement - every strategy carries a fight doctrine - is met without the field. The tactic list is already the engagement-range axis; it has said so since 1995. Restore its missing half, give the four tactics plain-language labels in the composer so "Maximise Net Damage" reads as the stand-off order it is, and let each admiralty plan's existing tactic be its range order. That delivers three visibly different doctrines across the three stances, keeps the one-dial path at one dial, and adds nothing to the round-robin that is not already in it.

If a fifth field ships anyway, the minimum this review would ask for: drop Tactic Decides and Close to Contact into a single boolean override, bound the ground per D4 before any balance number is quoted, re-derive criterion 8 on a bounded board and at the speed ratio the catalogue actually produces, and strike criterion 9 until the degeneracy fixture's archetype table stops anti-correlating range with speed.

### Measurement notes

All margins are means over the 8 seeds in `test_battle_balance.SEEDS` or the 3 seeds and 2 withdrawal contexts in `test_battle_degeneracy`. The probe implements the axis as specified and inherits every shipped defect: the missile `/10` divisor, whole-token damage, no board boundary, `MAX_BATTLE_ROUNDS = 60`. Directions are trustworthy; absolute magnitudes will move once DEF-33 and the per-ship kills land, and D6 in particular should be re-measured after them, since Salvo then Close is the one option whose value those fixes are expected to raise. The give-ground allowance in the counter-pressure section was measured, not modelled - it is the `GROUND_BUDGET` column of D4.
