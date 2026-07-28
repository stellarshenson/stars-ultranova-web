# Stand-off Warfare: Canon versus This Port

An audit of what canonical Stars! gives a long-ranged fleet, what the C# reference actually implements, and what this port has. Nothing here is a design proposal. Every claim carries a file and line, and every number was measured by running the shipped engine rather than reasoned about.

Read `docs/research-battle-doctrine.md` first for the BATTLE.TXT and Guts of the Battle Engine quotations. This document does not repeat that research; it tests it against the code.

## Overview

The standing hypothesis was that range buys nothing because every stack closes regardless of tactic. That is half right and it is not the main problem. Measurement puts the causes in this order:

- **A missile-only damage divisor of 10.** `RonBattleEngine._fire_missile` divides hit power by 10 (`ron_battle_engine.py:1344`); `_fire_beam` does not. Every torpedo and missile in the game delivers a tenth of the damage its printed power implies, while every beam delivers all of it. This alone is worth roughly 13x in damage per shot after accuracy
- **No range maintenance.** The stand-off tactics stop closing when the target enters their own maximum range (`ron_battle_engine.py:966-978`); they never back off as the enemy keeps coming. Canon's Maximise Net Damage explicitly holds at maximum range. Patching in that one behaviour, with the divisor left in place, moves late-tier torpedo from 0 of 16 to 10 of 16 against beams
- **Weapon classes below the beam/missile split do not exist in the engine.** `WeaponType` is defined at `backend/core/components/component.py:31-36` and referenced nowhere else in `backend/`. Gatlings, shield sappers and capital-ship missiles all resolve through the two generic paths

The last of those is not only a missing feature. Treated as an ordinary beam, the Syncro Sapper (power 541, range 3, cost 29, mass 1) beats Mega Disruptor, Big Mutha Cannon and Upsilon Torpedo 16 of 16 each at equal budget. It is currently the strongest weapon in the game by a wide margin, and it is only strong because a shields-only weapon is being allowed to cut armour.

## Canonical movement, and whether range can be held

Canon runs 16 rounds (`BattleEngine.cs:42`) with 3 movement phases per round (`BattleEngine.cs:41`) on a 10 by 10 board. Battle speed comes from the design: `(engine optimal speed - 4)/4 - mass/70/4/engines + jets/4 + overthrusters/2`, clamped to 0.5 through 2.5 and rounded to quarters (`ShipDesign.cs:296-329`). That speed indexes a moves-per-round table (`BattleEngine.cs:44-73`), so speed 1.5 gives 2,1,2,1 and speed 2.25 gives 3,2,2,2 across an 8-round cycle. The three phases then deal those moves out one square at a time: phase 1 moves anything with 3 moves this round, phase 2 anything with 2 or more, phase 3 anything with 1 or more (`BattleEngine.cs:522-589`). Starbases never move (`BattleEngine.cs:527`). A move is one square, diagonals included, and an axis steps only while it is strictly farther away, which is why closing converges instead of oscillating (`PointUtilities.cs:224-247`).

Then the important part. **The C# reference never consumes the tactic at all.** `MoveStacks` calls `PointUtilities.BattleMoveTo(from, to)` unconditionally (`BattleEngine.cs:594`). Everything closes, every round, whatever the battle plan says, and the file admits the gap: "shouldn't stacks without targets flee the battle if their strategy says to do so? they're sitting ducks now!" (`BattleEngine.cs:603`). Mass-ordered movement with the 15 percent juggle is also only a TODO (`BattleEngine.cs:524`).

So the answer to "can a faster ship hold range" splits by source. In the C# reference, no: nothing holds range, nothing flees, tactics are inert. In canonical Stars! as documented in Guts of the Battle Engine, yes: Maximise Net Damage moves toward the target only while out of range with any weapon, and once in range moves to maximise damage done over damage taken, whose stated effect is "if your weapons are longer range then try to stay at maximum range". Iztok's battle-speed thresholds only make sense under that reading, and they are quantitative: combat speed 2.50 disengages in round 3, so catching it needs missiles on a speed-1-or-better hull or range-3 beams on a 2.25 interceptor.

This port sits between the two. It does consume the tactic (`ron_battle_engine.py:929-978`), and stand-off tactics stop closing at their own weapon range, but they never re-open the gap. The result is a one-way ratchet: the enemy walks in and the stand-off fleet stays where it stopped.

Two further divergences matter for stand-off specifically. The board is 60 rounds on a 1000-unit grid at 100 units per square (`ron_battle_engine.py:71-73`), and the two sides start about 14 squares apart (`SpaceAllocator.get_box` places 2 empires at (0,0) and (1000,1000)). There is no boundary clamp anywhere in the engine, so nothing stops a stack drifting off the notional board. Any future range-maintenance rule needs a board edge or an equal-speed kiter holds range for all 60 rounds.

## The damage model per class

Canon assigns five weapon groups (`Weapon.cs:40-47`), of which the C# collapses to two by `IsBeam`/`IsMissile` (`Weapon.cs:297-305`). The port copies that collapse exactly (`component.py:68-81`) and never looks at the group again.

| Mechanic | Canon | C# reference | This port |
|---|---|---|---|
| Beam range dissipation | 10 percent of damage lost across the weapon's full range (BATTLE.TXT) | commented-out stub; the intent switches on the weapon's own range band for a flat 5/10/15 percent, not on actual distance (`BattleEngine.cs:869-908`) | implemented, quadratic in distance: `100 - 10*(d^2/R^2)` (`weapon_details.py:57-70`). Half range loses 2.5 percent, not 5 |
| Torpedo split half shields, half armour | yes | yes (`BattleEngine.cs:800-803`) | yes (`ron_battle_engine.py:1354-1359`) |
| Torpedo miss does 1/8 splash to shields | yes | yes (`BattleEngine.cs:806-808`) | yes (`ron_battle_engine.py:1350-1352`) |
| Missile double damage to armour once shields are down | yes | **missing**, recorded as a FIXME (`BattleEngine.cs:802`, echoed in `BUGS.txt:120`) | **missing**; torpedo and missile groups resolve identically, the only difference anywhere being a 115 versus 101 percent-to-fire factor (`ron_battle_engine.py:1200-1204`) |
| Gatling sweeps every stack in range | yes | **missing** | **missing**; the gatlingGun group takes the beam path |
| Shield sapper damages shields only | yes | **missing** | **missing**; a sapper cuts armour like any beam |
| Beam overkill spilling to other stacks | yes | **missing**, TODO (`BattleEngine.cs:777`) | partly: `_generate_attacks` spills leftover fire percentage down the target list (`ron_battle_engine.py:1186-1225`), but see below |
| Missile accuracy from computers and jammers | yes | **missing**, TODO (`BattleEngine.cs:920-929`) | implemented (`weapon_details.py:71-101`) |
| Capacitors and deflectors on beam power | yes | **missing**, stub returns base power (`BattleEngine.cs:880-883`) | implemented (`weapon_details.py:103-133`) |
| Starbase plus one square of range | yes | **missing** | **missing**; range bonus comes only from the Brace posture (`ron_battle_engine.py:1176`), xfail in `tests/e2e/test_battle_scenarios_engine.py:791` |
| Highest initiative fires first | yes | **inverted**; `WeaponDetails.CompareTo` sorts ascending and `allAttacks.Sort()` is unreversed (`WeaponDetails.cs:40-44`, `BattleEngine.cs:638`) | fixed, sorts descending (`ron_battle_engine.py:1229`) |
| Missile damage divisor | none | none | **`hit_power / 10`, missiles only** (`ron_battle_engine.py:1344`). Not canon, not in the C#, and not applied to beams |

The overkill spill row deserves a note. `_generate_attacks` computes how much of a weapon's fire is needed to kill the current target using `damage_per = power * quantity / 10.0` for both classes (`ron_battle_engine.py:1198-1204`). For missiles that matches what `_fire_missile` actually delivers. For beams it understates real output tenfold, so `percent_to_fire` saturates at 100 and a beam stack always dumps its whole salvo into one target no matter how much is wasted. The spill mechanism exists but never fires at realistic force sizes. That is the same `/10` defect seen from the other side, and it suggests the divisor was meant to apply to everything and was simply dropped from the beam path.

## Why a torpedo fleet should ever win

Canon gives a missile boat four things, and this port currently delivers one and a half of them.

The one it delivers is the shields-armour split. A torpedo puts half its hit into armour while the shield is still standing, so against a heavily shielded fleet it starts killing on the first round of contact where a beam has to grind the shield down first. Both engines implement this, and the port has a passing scenario for it (`test_battle_scenarios_engine.py:700-707`).

The half is range. Free shots are worth exactly the range gap divided by the closing rate. Upsilon Torpedo at range 5 against Mega Disruptor at range 3 is a 2-square gap, both sides move 1 square per round, so the gap closes at 2 squares per round and the torpedo gets one free round. Instrumenting the shipped engine confirms it: the torpedo side first fires in round 6, the beam side in round 7. That is the whole return on paying 24 percent more per weapon, 12 times the mass and a quarter of the accuracy. Canon inflates that return by letting the longer-ranged fleet refuse to be closed with; this port does not.

The two it does not deliver are the anti-capital role and the rock-paper-scissors triangle. Capital-ship missiles doubling their damage against armour is what makes a missile the correct answer to a big expensive hull, and it is the entire justification for accuracy figures of 20 to 30 percent. Chaff is the counter to that, and the gatling sweep is the counter to chaff. With no sweep and no double damage, the triangle collapses to a single ranking, and the two classes whose worth depends on the missing rules are exactly the two classes that lose everything.

The honest conditions under which a torpedo fleet should beat a beam fleet, then: the enemy carries a large fraction of its durability in shields; the enemy's beams are range 0 to 2 while the torpedoes reach 4 to 6; the torpedo fleet is fast enough to keep the gap open; the torpedo designs mount battle computers (Battle Computer +20, Battle Super Computer +30, Battle Nexus +50 accuracy, cutting miss chance multiplicatively via `weapon_details.py:71-101`); and the targets are few and expensive rather than many and cheap. The balance harness satisfies none of these. It mounts no electronics, sets both sides to battle speed 1.0, gives both the Balanced plan whose tactic is Maximise Damage, and buys many cheap identical hulls. It is measuring the worst case for torpedoes, which is fine as a floor test but should be read as one.

## The measured gap

All figures below come from `tests/unit/test_battle_balance.py` run against the shipped engine, with candidate mechanics monkeypatched in memory only. Cells are wins out of 16 (8 seeds, both role assignments summed).

Shipped, late tier: torpedo 0 of 16 against every class, missile 0 of 16 against every class, gatlingGun beats everything. Mid and early tiers are the same shape with standardBeam on top. The instrumented late-tier fight shows why: over one battle the torpedo side dealt 295 damage across 4 shots while the beam side dealt 7155 across 9. That is 74 damage per shot against 795, a factor of 10.7, which is the divisor times the 0.75 accuracy roll.

What each candidate fix buys, measured:

| Change | Late tier result |
|---|---|
| Shipped | torpedo 0/16 and missile 0/16 against every class; gatling dominates |
| Missile double damage to armour, alone | unchanged at late tier; mid tier missile 6/16 against torpedo, still 0 against beams |
| Gatling sweep, alone | gatling goes from 16/16 to 16/16 against beams and now beats missile 16/16 at mid tier. Strictly worse |
| Missile divisor removed, alone | torpedo 7/16 against beam, 5/16 against gatling; missile still 0 or 1 everywhere |
| Divisor removed plus missile double damage | **no class dominates.** beam beaten by missile and gatling, torpedo beaten by beam and gatling, missile beaten by torpedo, gatling beaten by missile |
| The above plus gatling sweep | gatling returns to dominance at both mid and late tiers |
| Range maintenance alone, divisor left in | torpedo 10/16 against beam at equal speed |

Mid and early tiers do not come right under any of these. Mark IV Blaster is simply the best purchase at mid tier on raw damage per resource: 23 hulls times 66 power is 1518 nominal, against 682 for the Gatling Gun and 912 for the Epsilon Torpedo before its 65 percent accuracy. Early tier is the same story with Laser at 270 against Beta Torpedo at 264 before a 45 percent accuracy. Those are catalogue tuning facts, not engine facts, and no mechanic fix will move them.

So the direct answer to the question asked: implementing the two known-missing mechanics **would not** make torpedoes and missiles competitive. The missile armour bonus alone changes almost nothing, and the gatling sweep makes the imbalance worse. What makes them competitive is removing the missile-only divisor, and the armour bonus then becomes the thing that separates missiles from torpedoes rather than leaving them a strictly worse torpedo. The sweep should land only after the gatling is no longer the top class on its own, or it will simply entrench it.

## Confidence, and what is not established

High confidence on the divisor: it is a single line, its absence from the beam path is visible in the same file, neither canon source nor the C# has anything like it, and removing it moves the matrix in the predicted direction and magnitude. High confidence on the missing class handling: `WeaponType` has zero references outside its own definition.

Medium confidence on the range-maintenance measurement. The kiting rule used for the probe is a rough back-off along the closing line applied after the normal move; it is not a canonical implementation, and it produced a non-monotonic result (a speed-2.5 kiter did worse, 5 of 16, than an equal-speed one at 10 of 16), which points at an artefact in the patch rather than a property of the mechanic. The direction is trustworthy, the size is not.

Medium confidence on the sapper exploit. The 16 of 16 result is unambiguous, but the balance harness is a synthetic hull with no shields research behind it, and a sapper's real-game value depends on what it is fired at. It is a genuine dominant purchase in the harness and a strong candidate in a real game, not a proven one.

Low confidence on the mid and early tier conclusions holding after the divisor is fixed, because both tiers are cost-dominated rather than mechanic-dominated and the catalogue has not been reviewed against canonical Stars! weapon costs. The three-source conflict on beam dissipation is also unresolved: BATTLE.TXT reads linear in distance, the C# comment reads as a flat penalty by weapon range band, and the port implements quadratic in distance. All three give 90 percent at maximum range and disagree everywhere else.

Finally, the docstring on `RonBattleEngine` claims it is "Ported from RonBattleEngine.cs". No such file exists under `references/original-game/`. The engine that decides every battle in this game has no reference implementation in the repository to check against, which is why the divisor survived.

## Sources

Canon, read in this repository:

- `references/original-game/ServerState/BattleEngine.cs` - rounds and phases (41-42), movement table (44-73), DoBattle (377-397), SelectTargets (404-439), MoveStacks (501-606), GenerateAttacks (612-641), ProcessAttack range gate (667), FireBeam (761-778), FireMissile (790-810), CalculateWeaponPower stub (880-908), CalculateWeaponAccuracy stub (920-930)
- `references/original-game/ServerState/WeaponDetails.cs:40-44` - initiative comparison
- `references/original-game/Common/Components/Weapon.cs:40-47, 297-305` - the five groups and the two-way collapse
- `references/original-game/Common/Components/ShipDesign.cs:296-329` - battle speed formula
- `references/original-game/Common/PointUtilities.cs:224-247` - BattleMoveTo
- `references/original-game/BUGS.txt:120` - the missile double-damage FIXME

BATTLE.TXT, Guts of the Battle Engine and Iztok's battle-speed article are quoted through `docs/research-battle-doctrine.md` sections 1 and 3, which carry the retrieval URLs.

Port code audited:

- `backend/server/battle/ron_battle_engine.py`
- `backend/server/battle/weapon_details.py`
- `backend/server/battle/battle_plan.py`
- `backend/server/battle/space_allocator.py`
- `backend/core/components/component.py`
- `backend/data/components.xml`

Measurements were produced by running `tests/unit/test_battle_balance.py` and by in-memory monkeypatch probes over the same harness. No repository file was modified.
