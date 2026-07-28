# The Damage Model: Granularity, Attrition and the Torpedo Failure

An audit of how this engine converts weapon fire into dead ships, whether that matches canonical Stars!, and how much of the measured torpedo and missile collapse it accounts for. Companion document to `docs/research-long-range-warfare.md`, which owns movement and reach. This one owns damage. The two were commissioned together because the torpedo failure has two suspects and they needed measuring separately.

Prior work this document builds on rather than repeats: `docs/research-battle-doctrine.md` (the BATTLE.TXT and Guts of the Battle Engine quotations), `docs/research-standoff-canon.md` (the first measurement of the missile divisor), `docs/design-engagement-range.md` (the orders layer).

## The finding, first

Damage in this engine is **lumpy, not granular**. A token of N ships carries one pooled armour float. Every point of fire subtracts from that pool, and the instant it crosses zero all N ships die simultaneously. Until that frame, the token fights at full strength: firepower is `weapon.power * token.quantity * percent` (`ron_battle_engine.py:1265`) and `quantity` is never decremented by gunfire anywhere in the engine. The only combat decrement of `quantity` in the whole package is boarding capture (`ron_battle_engine.py:582`, `:615`).

Instrumented proof, mid-tier mirror, seed 20260730: stack `0x000200000005` fired `hit_power` 462.0 in round 9 at 100 percent armour and fired the identical 462.0 in round 11 with 22 armour points left of 1750 - 98.7 percent of the hull gone, all seven ships still shooting at full rate. Across the same run, armour hits that reduced a ship count: **0 of 29**.

That **is** a divergence from canonical Stars!, and the C# reference says so in its own words. `references/original-game/ServerState/BattleEngine.cs:857`, sitting directly above the line that subtracts damage:

```
// FIXME (Priority 6) - damage is being spread over all ships in the stack.
// Should destroy whole ships first, then spread remaining damage.
```

That sentence is the canonical algorithm, written by the porters in the act of admitting they did not implement it. The sibling admission at `BattleEngine.cs:713` ("What about losses of a single ship within the token???") sits above the destroy trigger, and both are carried in the reference project's own `BUGS.txt`. There is no reading under which per-ship kills are a web invention.

**And it is a contributing cause to the torpedo failure, but a second-order one that is currently invisible.** This is the load-bearing result of the whole audit, so it gets its own section.

## How much of the torpedo failure this explains

Measured by instrumenting the live `RonBattleEngine` against the fixture in `tests/unit/test_battle_balance.py` - equal 3000-resource budgets, identical hulls at 250 armour and 100 shields, three fleets a side, the eight seeds the test already uses. Positive margin means the beam side won.

| Pairing | As shipped | Per-ship kills only | Divisor removed only | Both fixes |
|---|---|---|---|---|
| early Laser vs Beta Torpedo | +0.98 | +0.98 | +0.72 | +0.53 |
| mid Mk IV Blaster vs Epsilon Torpedo | +0.98 | +0.98 | +0.68 | +0.56 |
| mid Mk IV Blaster vs Juggernaut Missile | +0.98 | +0.99 | +0.76 | +0.64 |
| late Mega Disruptor vs Upsilon Torpedo | +0.94 | +0.94 | +0.10 | +0.03 |
| late Mega Disruptor vs Doomsday Missile | +0.97 | +0.97 | +0.41 | +0.30 |

Read the ordering, because it is the actionable part. **Fixing granularity alone moves nothing at all** - +0.98 to +0.98, +0.94 to +0.94. Not because granularity is harmless, but because a first-order defect means torpedoes land so little armour damage that there is nothing left to granulate.

That first-order defect is the missile-only divisor at `ron_battle_engine.py:1343-1344`, `hit_power = hit_power / 10`, with the comment "Scale down damage (10 rounds per turn)". `_fire_beam` has no such divisor. Full budget accounting of every point of hit power reaching `_fire_missile`, mid tier, 8 seeds, 34320 points offered:

- 30888 (90.0 percent) destroyed outright by the `/10`
- 1066 (3.1 percent) discarded as the un-splashed seven eighths of the miss fraction
- 1107 (3.2 percent) absorbed by shields
- 1107 (3.2 percent) actually reaching armour

The beam path over the same battles offered 60758 and landed 45558 on armour (75.0 percent), losing the rest to shields and nothing else. Per shot: **beam delivers 376.5 armour points, missile delivers 10.0**, on identical `power * quantity * percent` inputs. A late-tier Doomsday Missile fleet offers 11200 damage across sixty rounds, puts 140 points onto armour, loses 14 of 14 hulls and kills nothing.

Once the divisor is lifted, per-ship kills are worth a further 0.07 to 0.19 to the torpedo side, and in ship terms the early-tier beam fleet goes from losing 0.0 of 27 hulls to losing 6.1.

So the honest verdict, in the terms the brief asked for: the damage model **is** a contributing cause, it is **not** the leading cause, and it is **masked**. A workflow that lands granularity first will measure a no-op and risk having good work reverted as ineffective. Sequence the divisor first.

### Why lumpiness taxes reach specifically

Within a single battle, whole-token resolution discards no damage arithmetically. The armour pool persists across all sixty rounds and chip damage accumulates perfectly. The hypothesis that "sustained chip damage from long range accumulates into nothing" is **false as stated**.

What the rule discards is not damage, it is **attrition**. A token's output is proportional to `quantity`, and `quantity` never falls, so a token shot to its last armour point still fires at one hundred percent. In canon a token that has lost sixty percent of its armour has lost roughly sixty percent of its guns, permanently, and that loss compounds every subsequent round.

That is exactly the mechanism that annihilates reach. A stand-off fleet's entire edge is free rounds of fire before the enemy can reply, and the value of those rounds comes from converting them into dead enemy guns. Under a lump rule they buy nothing unless they alone exceed a whole token's armour pool, which two or three rounds never do. A beam fleet loses nothing to the rule because it fights to annihilation at contact anyway. The rule is not neutral between weapon classes: **it is a tax paid only by the class that fights at range.**

Measured as stranded armour - damage sitting inside tokens that survived, which per-ship kills would have converted into dead ships. Early tier, Laser 27 hulls versus Beta Torpedo 22 hulls, with the divisor lifted so torpedoes actually land: 1919 armour points stranded on the beam side out of a 6750 pool. Twenty-eight percent of the beam fleet's armour destroyed, ships killed by it zero, incoming beam fire reduced by it zero. Mid tier versus Juggernaut Missile: 1268 stranded of 5750. Late tier versus Upsilon Torpedo: 483 of 4500 beam side, 275 of 4000 torpedo side.

## Three other damage losses, measured

**Overkill past zero - real, about 8 percent, and symmetric.** `_damage_armor` subtracts the full hit power even when it drives the pool far below zero. The excess is neither carried to another stack nor refunded. Over an 8-seed mid-tier mirror: empire 1 dealt 36412 armour damage of which 2817 landed past zero (7.7 percent); empire 2 dealt 44457 of which 3673 (8.3 percent). Single battles show tokens destroyed at armour -590.7, -276.4, -122.1. Canon spills beam overkill to adjacent stacks, capped at one extra stack per ship in the firing stack (`BattleEngine.cs:777`, TODO Priority 6). Since this loss falls on both sides roughly equally, it is a parity item, not a balance item.

**Carry-in erasure between battles - 100 percent, and this one is a port regression.** DEF-27 restored the write-back: `_write_back_damage` (`ron_battle_engine.py:409-444`) converts surviving armour into `ShipToken.damage_percent`. But nothing ever reads it back. `StackToken.from_ship_token` (`stack.py:61-63`) builds `armor = token.armor * token.quantity` with no reference to `damage_percent`, and `grep -rn damage_percent backend/` finds readers only in the repair step, the mine and storm attrition loops, and the UI payload. Demonstrated directly on two consecutive battles with live fleets: battle 1 ended a token at armour 910 of 2000 and wrote back `damage_percent 54.51`; battle 2 opened the same token at armour 2000. **1090 armour points erased at the battle boundary.** In canon this cannot happen, because `Stack.cs:125` holds the fleet's own token by reference and armour points persist as absolute numbers. The round trip here is lossy in three ways - a per-token average, a 99.0 cap, and no reader at all.

**The port is better than the reference in one place.** C# truncates with `(int)hitPower` at `BattleEngine.cs:858`, so sub-1.0 hits vanish. Python subtracts the float. Keep that.

## The proposed damage system

Only if the sequencing above is respected. Every item below is a restoration of something canon does and the reference declines to do.

### Granularity: per-ship accumulation inside a token

Keep the pooled armour float. It is the correct arithmetic and it is what the C# stores (`ShipToken.cs:90`: "the total number of Armor points remaining for the whole Token (of Quantity ships) ... Each ship has Armor / Quantity"). Add one derived step after each armour subtraction: recompute how many whole ships the remaining pool still supports, and set `quantity` to that number.

```
per_ship = initial_armor / initial_quantity
quantity = ceil(max(0.0, armor) / per_ship)
```

That single line does the whole job, because firepower already reads `token.quantity` at `ron_battle_engine.py:1265`. Ships die one at a time, output falls in step, and the remainder stays live in the pool as partial damage on the survivors - which is precisely canon's "destroy whole ships first, then spread remaining damage".

The codebase already runs this exact idiom elsewhere: `turn_generator.py:1348-1352` (storms) and `:1540-1544` (minefields) both loop `while token.damage_percent >= 100 and token.quantity > 0: quantity -= 1; damage_percent -= 100`. Ships already die one at a time to mines and storms. Only weapons are exempt.

**Remainder carry.** Beam residue after a ship dies carries into the next ship of the same token - free in a pool model, no code needed. Residue that kills nothing persists as the token's damage percentage and leaves the battle, which is what `_write_back_damage` already does. The one canonical rule that does **not** fall out for free is the missile "one missile, one kill" discard, where residue inside a single ship is thrown away rather than carried. That rule exists to make chaff work, chaff does not exist in this port, and its sourcing is the weakest claim in this audit (community consensus, no citable line in this tree). **Defer it.** Nothing above depends on it.

**Overkill past zero.** Leave it discarded for now. Canon spills it to adjacent stacks and the reference admits the gap, but it is an 8 percent symmetric loss that helps the beam side if restored, and restoring it while torpedoes are still broken would widen the very gap being closed. Restore it after the balance bars are green, not before.

### Armour and shields

Two changes, both small, both canon.

**The shield pool must shrink as ships die.** `StackToken.shields` is built as `token.shields * quantity` at `stack.py:61` and never rescaled. Under per-ship kills, a token down to two ships would still carry a seven-ship shield wall. Rescale it on the same line that decrements `quantity`, proportionally. Without this, per-ship kills would create a new defect rather than remove one.

**Everything else about shields is already right.** Two separate pools, shields absorbing first, no in-battle regeneration, full restoration between turns (`TurnGenerator.cs:369`), armour repairing at a location-dependent rate. The one canonical exception is the Regenerating Shields LRT, whose game text the reference carries verbatim at `SecondaryTraits.cs:74` ("Shields regenerate 10% of maxium strength after every round of battle") and which no battle code in either codebase reads - `grep -rni "regenerat" backend/ --include=*.py` returns nothing in `backend/server/battle/`. RS is a purchasable trait that currently does nothing at all. Worth a defect entry; not on the torpedo critical path.

**Sappers are a live documentation overclaim.** `docs/ORIGINAL_GAME_MECHANICS.md:66` lists "gatling multi-hit, sapper shield-only" as done in the Ron engine. Both halves are false in both codebases. The engine branches only on `Weapon.is_missile`, so a shield sapper takes the ordinary beam path and cuts armour. `docs/research-standoff-canon.md` measures the consequence: the Syncro Sapper beats Mega Disruptor, Big Mutha Cannon and Upsilon Torpedo 16 of 16 each and is currently the strongest weapon in the game. Correct that documentation line before anyone plans work against it.

**Capital-ship missile double damage against bare armour** is missing and the reference admits it in the same terms (`BattleEngine.cs:802`, FIXME Priority 5). Canonical scoping matters: capital-ship missiles only, torpedoes never, and only once shields read zero. That makes sappers and missiles a designed combination and gives the missile class a reason to exist that the engine currently denies it twice over. The port's own xfail at `tests/e2e/test_battle_scenarios_engine.py:718-729` already names the gap.

### What a damaged ship should fight like

**Nothing changes, and that is the point.** Canonical Stars! ships fight at full effectiveness until they are destroyed. Do not add a "damaged ships shoot weaker" rule - it is not canon, it is not in the reference, and it would be an invention with no source. The entire attrition feedback loop is delivered by the ship count falling, because output is already `power * quantity`. One derived line buys the whole effect. Anything more is scope the game does not want.

### How it should read to a commander

Governing principle from the user: some commanders run grand strategy and never open a battle. A damage model the player must study has failed.

The current report already emits per-shot `BattleStepWeapons` events. Under per-ship kills it would emit ship-death events too, which is more detail, not less - and detail is the failure mode here. The summary the commander sees should collapse to one line per token per battle:

```
Warmonger x7  ->  4 destroyed, 3 survived at 38% damage
```

Three facts: how many went in, how many came out, how hurt the survivors are. No pool arithmetic, no per-round ledger, no shields-versus-armour breakdown at summary level. The battle viewer keeps the step detail for the commander who wants it, and the fleet panel keeps showing the single `damage_percent` number it already shows.

The reason this reads better than today is that today it cannot be written at all. With whole-token lumps the only two possible summaries are "7 of 7 destroyed" or "0 of 7 destroyed", and the survivors' damage percentage is the average of a fiction. Per-ship kills make "4 destroyed, 3 at 38 percent" a true statement. **Granularity reduces cognitive load rather than adding to it** - it replaces a binary outcome the player cannot reason about with a proportional one that matches the intuition they brought to the game.

## The contract tension, stated plainly

This project's rule is to preserve the C# reference's logic exactly and not modernize algorithms. That rule and the rule "match canonical Stars!" point in opposite directions on this line, and the reference itself breaks the tie.

**In contract, strong case - restoring what canon does and the reference admits it does not.** Per-ship kills (`BattleEngine.cs:857`), shield pool scaling with ship count, capital-ship missile double damage (`:802`), beam overkill spill (`:777`), sapper shields-only, the Regenerating Shields LRT (`SecondaryTraits.cs:74`), no-target stacks fleeing (`:603`). Every one of these is a C# admission of divergence from Stars!, and every one is tracked in the reference project's own `BUGS.txt`. Implementing them is restoration work. There is no cost to state, because these are not deviations from the reference's intent - they are the reference's stated intent, unimplemented.

**Also in contract, but a different argument - fixing what the port broke.** Reading `damage_percent` back at stack construction restores canon's by-reference persistence (`Stack.cs:125`), which the port lost by building copies. And the missile `/10` at `ron_battle_engine.py:1344` has **no canonical ancestor at all**: C# `FireMissile` applies hit power directly with no scaling of any kind. The port's own docstring cites `ServerState/RonBattleEngine.cs` as its source and that file **does not exist** in `references/original-game/` - verified, no file matches and the string "RonBattle" appears nowhere in the tree. What can be checked is internal consistency, and the divisor fails that too: the engine's own fire allocator at `:1199` and `:1203` sizes both weapon classes as `power * quantity / 10.0`, so it is the beam path that contradicts the engine's own model by delivering ten times what was budgeted. Removing the divisor is not a deviation from the reference - the reference has nothing here to deviate from.

**Out of contract, and the user must decide.** Nothing in the recommendation below. Two items deliberately excluded for this reason: the missile one-missile-one-kill overkill discard (canon by community consensus, no citable line in this tree) and any "damaged ships fight weaker" rule (not canon, not in the reference, pure invention).

One correction for anyone acting on the original diagnosis: `ron_battle_engine.py:1046-1050` was cited as the losses computation. That range is now `_effective_tactic`. Losses are booked at `ron_battle_engine.py:1424-1425` inside `_destroy_stack` (1414-1461). The file has moved under an in-flight edit.

## Recommendation

Land the divisor first, then granularity, then the rest. Landing them in any other order produces measurements that argue against correct work.

| # | Change | Canon-legal | Engine cost | Moves the torpedo/missile numbers |
|---|---|---|---|---|
| 1 | Remove or re-derive the missile `/10` at `ron_battle_engine.py:1344` | Yes - no C# ancestor exists, and the engine's own allocator contradicts the beam path | Trivial, one line plus a rebalance pass on the allocator | **Decisive.** +0.98 -> +0.72 early, +0.94 -> +0.10 late |
| 2 | Per-ship kills: derive `quantity` from the armour pool after each hit | Yes - `BattleEngine.cs:857` states the rule | Small, one derived line in `_damage_armor` | **Yes, but only after #1.** Zero alone; a further 0.07 to 0.19 once #1 lands |
| 3 | Scale the shield pool with surviving `quantity` | Yes - implied by canon's per-ship model | Trivial, same line as #2 | Small further gain; **required** to keep #2 from creating a defect |
| 4 | Read `damage_percent` back in `StackToken.from_ship_token` | Yes - restores canon's by-reference persistence (`Stack.cs:125`) | Trivial | No effect on the single-battle balance test; fixes 1090 armour points per token per campaign battle |
| 5 | Capital-ship missile double damage vs bare armour | Yes - `BattleEngine.cs:802` FIXME | Small, needs a weapon-class check | Yes, missile class specifically; magnitude unmeasured |
| 6 | Sapper shields-only branch, and correct `ORIGINAL_GAME_MECHANICS.md:66` | Yes - canon and the doc already claims it | Small | No help to torpedoes; removes the Syncro Sapper as the strongest weapon in the game |
| 7 | Beam overkill spill to adjacent stacks | Yes - `BattleEngine.cs:777` TODO | Medium, needs stack-adjacency targeting | **Widens the gap.** Defer until the bars are green |
| 8 | Missile one-missile-one-kill overkill discard | Weak sourcing, no citable line in this tree | Medium, needs true per-ship tracking | Slightly negative for missiles; pointless without chaff. Defer |
| 9 | Regenerating Shields LRT (`SecondaryTraits.cs:74`) | Yes | Small | No effect on the pairings; closes a trait that currently does nothing |

Items 1 through 4 are the package. They are cheap, they are all canon-legal on the strong argument, and together they take the worst pairing from +0.94 to +0.03. Items 5 and 6 are the next tier and both are restoration. Items 7 through 9 are correctness work with no bearing on the balance bars.

## Caveats

The per-ship-kill prototype used for the counterfactual table is a stand-in, not a proposed implementation. It kills ships as the pool crosses per-ship boundaries but does not scale the shield pool down (item 3), does not carry the remainder onto a named survivor, and does not implement overkill spill. A faithful implementation would help the torpedo side somewhat **more** than the table shows, since a shrinking shield pool is another attrition channel the lump rule currently freezes. Every direction in the table is safe; the magnitudes are a floor.

All measurements come from instrumenting the live `RonBattleEngine` in throwaway processes that imported the fixture helpers from `tests/unit/test_battle_balance.py` and monkeypatched `_fire_beam`, `_fire_missile`, `_damage_armor`, `_damage_shields`, `_execute_attack` and `_destroy_stack` in memory. No file under `backend/`, `frontend/` or `tests/` was modified by this work.

BATTLE.TXT and Guts of the Battle Engine are not in this repository and the web was not consulted. Every canonical claim above is anchored either in the C# reference's own prose - the strongest primary source available here, because it is the porters describing Stars! while conceding they did not reproduce it - or in the verbatim quotations already captured in `docs/research-battle-doctrine.md`.
