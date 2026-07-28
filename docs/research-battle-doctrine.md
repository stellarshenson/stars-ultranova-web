# Fleet Battle Doctrine and Tactical Orders - Research

Research for the Stars! Ultranova web port. Battles resolve server-side during turn generation with no player input during the fight, so every tactical decision must be expressible as a standing order set before the turn is submitted.

## Overview

A doctrine system has to decide two things and only two things: where a ship stands relative to its enemy, and which enemy it shoots. Everything a player calls "aggressive", "defensive", "brace", "flee" or "kill their tankers" reduces to a movement rule plus a target-selection rule, and the design work is making each choice genuinely costly so no single setting is always correct.

---

## 1. Canonical Stars! - what the 1995 game actually offered

The authoritative sources are the official 2.5 release notes (BATTLE.TXT, shipped with the patch) and the community reverse-engineering write-up "Guts of the Battle Engine". Both are hosted on the Stars! AutoHost wiki.

A Stars! battle plan has exactly four parts: a primary target type, a secondary target type, the set of races that are legitimate to attack, and one tactic. BATTLE.TXT: "Battle orders are comprised of 4 parts. A primary and secondary target type, legitimate races to attack and the tactic to use in battle."

**Target types** (BATTLE.TXT, TARGETING section - verbatim list):

- **None/Disengage** - "Don't look for a target just attempt to disengage"
- **Any** - "Any target will do"
- **Starbase** - "Go after the starbase if one exists"
- **Armed Ships** - "Target armed ships and armed starbases only"
- **Bombers/Freighters** - "Target bombers and freighters (ie possible troop xports) only"
- **Unarmed Ships** - "Target unarmed ships only"
- **Fuel Transports** - "Target fuel transports only"
- **Freighters** - "Target unarmed freighters only"

Two tiers only, not five. Fallback is strict: "If no token matching the primary target type is found then we attempt to match the secondary target type." Anything matching neither tier is never fired on - "Ships which are not listed as primary or secondary targets will not get shot at, even if they are shooting back" (Guts of the Battle Engine). Starbases are hard-coded to primary Armed Ships, secondary Any.

**Tactics** (BATTLE.TXT, TACTICS section - the six, with the official one-line definitions):

- **Disengage** - "Attempt to disengage as soon as possible"
- **Disengage if challenged** - "Attack as if 'Maximize damage ratio' until targeted or damaged and then change to 'Disengage'"
- **Minimize damage to self** - "Attempt to cause as much damage as possible while taking as little damage as possible"
- **Maximize net damage** - "Attempt to maximize damage to enemies minus damage to self"
- **Maximize damage ratio** - "Attempt to maximize damage to enemies divided by damage to self"
- **Maximize damage** - "Attempt to maximize damage to enemies without regard to damage to self"

The critical design point: **these tactics carry no stat modifiers whatsoever**. They are pure movement AI. Guts of the Battle Engine spells out what each does per square of movement - Maximise Net Damage "If out of range with ANY weapon then move towards target. If in range with all weapons them move as to maximise damage_done/damage_taken. The effect of this is if your weapons are longer range then try to stay at maximum range... If your weapons are shorter range and also beam weapons then attempt to close in to zero range." Maximise Damage Ratio is "As Maximise Net Damage but only considers the longest range weapon." Maximise Damage closes to range 0 whenever beams are mounted, because beams lose damage with separation - 10% of damage lost across the weapon's full range, so the loss is proportional to how much of that weapon's reach the gap consumes.

Two automatic overrides, both from BATTLE.TXT: "If token runs out of primary and secondary targets it will automatically switch to Disengage" and "If a token can no longer do any damage it will automatically Disengage" (the shield-buster-versus-shieldless case).

**Disengage mechanics.** Guts of the Battle Engine: "If there is any enemy ship in firing range then move to any square further away than your current square. If you are in range of an enemy weapon but cannot move further away then try move to a square that is of the same distance away. If you are in range of the enemies weapons and cannot move away or maintain distance then move to a random square. If you are not in range of the enemies weapons then move randomly. Also you will try and disengage which will require 7 squares of movement to be clocked up before you can leave from the battle board."

There is a **documented conflict on the square count**: BATTLE.TXT (the 2.5 release note) says "4 squares of movement are required to leave the battle", while Guts of the Battle Engine and Iztok's 2011 battle-speed article both say 7. Iztok: "for a ship to disengage, it needs to do 7 'regular' moves on battle board, then with 8th it disengages." The 7 figure describes the shipped 2.6/2.7 behaviour and is what the port already uses; the 4 appears to be a pre-release value. Flagged as a genuine source conflict, not resolved.

**Board, rounds, initiative, movement.** The grid is 10 x 10 squares, maximum 16 rounds, cap of 256 tokens per battle. Each round is target selection, then movement heaviest-to-lightest, then weapon fire highest-initiative-to-lowest. Battle speed is derived from the design: `Movement = (Ideal Speed of Engine - 4)/4 - weight/70/4/(Count of Engines) + 1/4 * Maneuvering jets + 1/2 * Overthrusters`, pegged between 1/2 and 2 1/2. The moves-per-round table is published in BATTLE.TXT (1 1/2 gives 2,1,2,1...; 2 1/4 gives 3,2,2,2...). Movement resolves in three passes - three-square tokens move one square, then two-plus-square tokens move one square, then everyone with any movement left moves - with heaviest first and "a random fudge factor" (Guts: under a 15% weight difference the lighter token may go first, more likely the closer the weights).

Speed interacts with orders directly. Iztok's practical thresholds: combat speed 2.50 lets you "disengage in 3rd round, so the opponent needs missiles in a 1+ speed ship, or R-3 weapons on an interceptor with 2.25 speed to catch you"; chaff wants "1 or less speed... Having more means chaff could come in range of R2 (gattling) weapons in the first combat round".

**Target selection inside a tier** is by attractiveness, "cost / defence" (Guts). Cost sums resource and boranium costs only; defence is shield plus armour dp adjusted for the attacker's torpedo accuracy and for deflectors versus beams, so a token has a different attractiveness against each weapon class. Also: "When picking targets we try to avoid targeting tokens that are already targeted by someone else" (BATTLE.TXT).

**Defaults.** BATTLE.TXT: "New fleets of unarmed ships are given the battle plan Default-Defense. New fleets of armed ships are given the battle plan Default-Attack... The initial behavior of Default-Defense is to try to avoid combat entirely. The initial behavior of Default-Attack is to automatically attack enemies." Two presets, auto-assigned by whether the fleet is armed. That is the original one-dial answer.

### What the port can and cannot express today

Read: `backend/server/battle/battle_plan.py`, `backend/server/battle/ron_battle_engine.py`, `backend/server/battle/stack.py`, `references/original-game/Common/DataStructures/BattlePlan.cs`, `references/original-game/ServerState/BattleEngine.cs`.

Can express:

- Five target tiers (primary through quinary) over a seven-value `Victims` enum - Starbase, Bomber, Capital Ship, Escort, Armed Ship, Any Ship, Support Ship. This is a superset of canon's two tiers and a different taxonomy
- All six canonical tactics as strings, consumed by `RonBattleEngine._move_stacks` and `_effective_tactic`
- Attack-who: Enemies, Enemies and Neutrals, Everyone, plus a specific `target_id`
- Named plans, capped at 14 (`MAX_BATTLE_PLANS`), assigned per fleet via `fleet.battle_plan`
- Disengage as a flee counter: `DISENGAGE_MOVES = 7`, one flee move per round, `disengaged` stacks stop firing and stop being targetable
- "Disengage if Challenged" via `stack.damage_taken`

Cannot express, or diverges from canon:

- **No stance axis at all.** There is no aggressive/defensive dial and no stat modifier anywhere in the plan
- **Board and clock are non-canonical.** `MAX_BATTLE_ROUNDS = 60` on a 1000-unit grid, versus canon's 16 rounds on 10 x 10. Any doctrine tuned to canon's 16-round attrition clock will behave differently here
- **Beam range dissipation is missing.** `_fire_beam` applies no distance falloff, so the whole reason Maximise Damage closes to range 0 is absent. Stand-off tactics are strictly better than closing tactics on damage, which is a live degenerate-strategy risk
- **Initiative order is inverted.** `_generate_attacks` ends with `all_attacks.sort()`, and `WeaponDetails.__lt__` compares ascending initiative - lowest initiative fires first. Canon is highest first
- **Attractiveness formula diverges.** `_get_attractiveness` uses `(mass + energy cost) / (armor + shields)`; canon uses resource-plus-boranium cost over a weapon-class-specific defence
- **No "avoid already-targeted tokens" rule**, no damage streaming to other tokens in the same square, no starbase +1 range bonus
- **No auto-switch to Disengage** when a token runs out of valid targets or can no longer do damage
- **Movement is not canonical** - no three-pass heaviest-first ordering, no weight fudge
- **Target taxonomy has no logistics classes** - no Fuel Transports, no Freighters, no Bombers/Freighters combined tier. `Victims.SUPPORT_SHIP` collapses every unarmed hull into one bucket
- Canon's "unarmed ships with orders to attack you make you a legitimate target for them" rule is not modelled

---

## 2. Stance systems in comparable games

### Stellaris - combat computers (the closest analogue to "one dial")

Stellaris is the clearest match: combat is fully automatic, and the player's only pre-battle lever is a component in the ship designer that sets both behaviour and stats. From the wiki's core-components table:

- **Swarm** - "charge straight at enemies and try to deal as much damage as possible from the range of their shortest range weapon". Specialized +5% fire rate / +5% evasion; Advanced +10%/+10%; Sapient or Autonomous +15% fire rate / +25% evasion; Precognitive +15% fire rate / +15% evasion / +20% sublight speed
- **Picket** - "advance to medium range and attempt to intercept incoming enemies". Specialized +5% fire rate / +10 tracking; Advanced +10%/+20; Sapient +15%/+30 plus +10% evasion
- **Line** - "hold advance to medium range and hold formation". Specialized +5% fire rate / +5% chance to hit; Advanced +10%/+10%; Sapient +20%/+20%
- **Artillery** - "stay at maximum range, firing its longest range weapons on the target". Specialized +5% fire rate / +5% weapons range; Advanced +10%/+10%; Sapient +20%/+20%
- **Carrier** - "stay at the maximum engagement range of its hangars". Specialized +25% engagement range; Advanced +50%; Sapient +100%
- **Siege** - strafing runs; +5/10/15% explosive damage and +50/65/80% damage versus starbases and bombardment

Formation distances quoted by the community: Swarm 10, Picket 40, Line 70, Artillery 100. The wiki documents the movement primitives precisely: "stay at range" makes a ship push to 70% of formation distance and stop; "maintain distance" holds the target between 70% and 90% of formation distance and backs off if it gets closer.

Fleet-level stance is separate and coarse: aggressive engages hostiles entering the system, passive ignores them, evasive leaves the system when a hostile arrives ("utility ships use the evasive fleet stance by default"). Empire-level doctrine sits in the War Doctrines policy - No Retreat, Hit and Run, Rapid Deployment.

### Endless Space 2 - battle cards, the no-input-during-battle model

ES2 is the most directly relevant precedent because the player commits everything before a fight that then plays out without input. Each Tactic Card bundles a **range preference per lane** (top/centre/bottom, each independently long/medium/short) with a **stat modifier**. Examples from the wiki table:

- **Turtle** (Defense, Short/Short/Medium) - +20% hull plating absorption
- **Power to Shields** (Defense, Medium/Long/Long) - +100% shield absorption, +10% maximum shield
- **Evasive Maneuvers** (Defense, Short/Short/Short) - +40% dodge at long range, +20% at medium
- **Prudent Positions** (Defense, Long/Long/Long) - "For both Fleets: -25% Damage on Weapon Modules"
- **Barrage Fire** (Offense, Long/Long/Long) - +3% damage at long range per enemy ship
- **Needs of the Many** (Offense, Long/Long/Long) - +30% crew lost per battle phase, +25% crew damage bonus
- **Berserker** (Offense, Short/Short/Short) - x1.5 damage if alone

Three phases of 40 seconds each; three card slots by default, five with Universal Aerodynamics and Quantum Communications. Note the design: several cards apply symmetrically to both fleets (Prudent Positions, Gravity Distortion, Temporal Drag, Unlucky Arms), turning card choice into "impose the battlefield condition that favours my build". ES1 had explicit rock-paper-scissors between cards; ES2 removed the interaction - community summary: "battle cards are independent, so your card gives you a bonus and their card gives them a bonus, they don't interact in any other way unlike before."

### Aurora 4X - fire control modes and conditional orders

Aurora has no aggressive/defensive dial. Posture is expressed as per-fire-control modes: "fire controls set to 'Final Defensive Fire' or 'Final Defensive Fire (Self Only)' will fire on hostile missiles, regardless of whether the fire control is set to 'Open Fire'", with Area Mode and AMM fire controls only firing defensively when set to Open Fire. Point Defence Mode chooses between firing at maximum range and firing at the last possible moment for maximum hit chance - the pure range-versus-accuracy trade in miniature.

The doctrine-template equivalent is the standing/conditional order system: a fleet may hold up to two standing orders and two conditional orders, and "Conditional Orders are Standing Orders linked to a Condition. When the condition is met, the associated conditional order will be executed where possible... the existing order queue is deleted." This is the "if damaged, withdraw" pattern generalised.

### Distant Worlds Universe - engagement scope, not posture

Distant Worlds separates **fleet posture** (Attack, Defend, plus a configurable range around the base or target) from **engagement stance** on ships: "Engage only when attacked", "Engage nearby targets", "Engage system targets", and, visible only at war, "Engage detected targets". Individual ship stances override fleet stances. Defaults are set per mission type in Empire Settings - a preset-by-role system rather than a preset-by-doctrine one. This is a scope dial (who counts as a target) rather than a damage dial.

### Star Ruler 2 - behaviour declared in the ship designer

SR2 puts the behaviour on the design, not the fleet: support ship designs carry a Behaviour setting defaulting to Cannon, with alternatives including Cavalry (leaves the fleet to flank) and Shield (intercepts incoming shots to protect the flagship). Behaviours activate once the flagship enters combat range. Fleets also carry a Supply bar; below 50% supply a fleet loses damage output, repair rate and operational effectiveness - a doctrine constraint imposed by logistics rather than by a stance setting.

### Master of Orion II - retreat as an order

MOO2's combat is player-controlled per turn, but its Retreat order is instructive: "Gives the selected ship the retreat order. This will attempt to withdraw them from combat on the next move (so plan ahead). If the battle is lost, any ships that successfully retreated will move to the nearest star system, but will not use warp points. If the battle is won they will remain with the fleet." Retreat costs a turn of exposure and costs strategic position.

### Sword of the Stars and Sins of a Solar Empire

Both are real-time with player input during the fight, so they are the least transferable. SotS offers tactical modes such as attack, pursuit and standoff; community consensus is that standoff is weak and pursuit is only useful for chasing fleeing ships. Sins exposes an engagement range and auto-attack target priority but is widely reported as under-documented and micromanagement-dependent. Neither is well enough documented in primary sources to build on; treat both as weak evidence.

---

## 3. The trade-off question - what stops "aggressive" from always being correct

Four mechanisms appear across the games, in increasing order of robustness.

**Geometry, not statistics (strongest).** Stars! attaches no stat modifiers to tactics at all. Aggression is expressed as closing distance, and closing is only correct if your weapons are short-ranged and the enemy's are not longer. Beam range dissipation (10% of damage lost across the weapon's full range, BATTLE.TXT) makes closing mandatory for beam fleets and suicidal for missile fleets, which fire at ranges 3 to 6 while beams reach 1 to 3. The trade-off is enforced by the enemy's build, which you cannot fully see. Stellaris does the same with formation distance - Swarm sits at 10, Artillery at 100 - and reinforces it by making combat computers hull-restricted, so the dial is not free.

**Different currencies per stance.** Stellaris never gives one computer strictly more of the same stat. Swarm buys evasion, Picket buys tracking, Line buys chance-to-hit, Artillery buys weapons range. Evasion is worthless against high-tracking weapons; tracking is worthless against low-evasion targets. The wiki states the counter-play explicitly: "Battleships, stingers, titans, juggernauts and ion cannons will avoid attacking ships with more than 70 evasion unless there are no enemies with less evasion", and "the goal is to pick a weapon that has just enough tracking to maintain the weapon's baseline accuracy, i.e. tracking equal to the enemy's evasion".

**Symmetric conditions.** ES2's Prudent Positions applies "-25% Damage on Weapon Modules" to both fleets. A card that hurts both sides equally is correct only when the resulting battlefield favours your composition - a durable fleet wants low damage, a glass-cannon fleet wants high damage. This makes the choice a read on the opponent rather than an optimisation.

**Compensating penalty on the same axis (weakest, but sometimes needed).** Stellaris' No Retreat War Doctrine gives +33% ship fire rate but removes disengagement entirely; Hit and Run gives +33% disengagement chance and -25% emergency FTL damage risk but no combat bonus. That is a real trade because it converts damage into survivability at a fixed rate. Note the published figures for these three policies come from community summaries rather than the wiki page itself and should be re-verified before being copied as design targets.

**Answer to the question.** Nothing in a pure damage-dealt-versus-damage-taken multiplier stops aggressive from being correct, because in a fight to annihilation a symmetric scaling of both sides changes only the round count, and the stronger fleet always wants a shorter fight. What stops it is (a) a hard round limit that makes surviving to the clock a win condition for the weaker side, and (b) a positional commitment that a differently-armed enemy can punish. Stars! has both natively: 16 rounds, and range asymmetry. Any stance layer added here should ride on those two, not replace them.

---

## 4. Target-class priorities

Three approaches exist for deciding what a ship is.

**Component inference (Stars!).** Bombers are hulls with bombs; freighters are unarmed hulls with cargo; fuel transports are hulls with fuel pods. The player never labels anything - the classifier reads the design. This is the only approach that survives arbitrary player-designed hulls, which is the case here.

**Hull class (Stellaris, MOO).** Corvette/destroyer/cruiser/battleship is a fixed taxonomy set by the hull, and targeting weights key off it. Robust but only because hull classes are fixed by the game, not the player.

**Player declaration (Star Ruler 2).** The designer sets a Behaviour on the design. Simple, but a player will lie about their own designs if lying helps, and it gives an opponent nothing reliable to target.

**Priority list versus weighted scoring.** Stars! uses a strict two-tier list with hard exclusion - anything outside the tiers is never fired on. Stellaris uses additive weights, published as defines: `COMBAT_SHIP_UNARMED_TARGETING_WEIGHT` 0.005 ("the lower this is, the less likely ships are to target unarmed enemies over armed ones"), `COMBAT_SHIP_STARBASE_TARGETING_WEIGHT` 0.75, `COMBAT_SHIP_LOW_HEALTH_TARGETING_WEIGHT` 1.5 above a 0.5 health threshold, `COMBAT_SHIP_EVASION_TARGETING_WEIGHT` 2.0, `COMBAT_SHIP_DISTANCE_TARGETING_WEIGHT` 0.002 with a floor of 0.10, and `COMBAT_SHIP_EVASION_AVOID_THRESHOLD` 0.7 for ships of size 8 or larger. Weights degrade gracefully and never produce "my whole fleet stood there doing nothing"; strict lists give the player exact control and produce sharper, more readable outcomes. Stars! chose control, and the port should too, because the player cannot intervene mid-battle and needs the order to mean what it says.

**Counter-play.** The classic answer to focused targeting is to give the priority something cheap to eat. Stars! chaff is the canonical example and is documented as an unintended consequence: "Attractiveness doesn't take into account the one missile one kill rule, thus chaff has become a fairly effective tactic" (Guts of the Battle Engine). Screening works because targeting operates on stacks and a cheap stack absorbs a whole salvo. Stellaris' equivalent is corvette evasion plus the `EVASION_AVOID_THRESHOLD` rule. Point defence, in both games, is a component that changes the arithmetic rather than a targeting order.

---

## 5. Retreat and withdrawal

**Stars!** - retreat is movement, not a state change. A disengaging token must accumulate 7 squares of board movement before it leaves, it remains a legal target the entire time, and it keeps firing (the tactic changes only the movement AI). Escape is therefore a speed problem: Iztok's rule of thumb is that combat speed 2.50 disengages on round 3, so catching it requires missiles on a speed-1-plus hull or range-3 beams on a 2.25-speed interceptor. Retreat is neither free nor impossible - it is a design decision made at the shipyard.

**Stellaris** - two separate mechanisms. Per-ship disengagement triggers at 50% hull loss with chance `damage/hull x 1.5 x ship multiplier`, x1.25 inside friendly borders; ship multipliers are 2 for science ships, 1.5 for destroyer/cruiser/transport, 1.25 for battleship/titan, 1 for corvette/frigate/construction, 0.5 for colony ships. Ships have zero disengagement opportunities by default and gain +1 each from a level 5-9 commander, the Hit and Run doctrine, an Enigmatic Encoder, or a hyperdrive (+2 for level 10 commander or a Psi Jump Drive). Fleet-wide emergency retreat requires 14 days in combat first, then inflicts "a 25% chance to take up to 75% hull damage" per ship plus "a 5% chance for each ship to be destroyed outright", and sends the fleet missing-in-action for months. Two clean anti-degenerate devices: a charge time that punishes retreating immediately, and a damage roll that makes retreat a cost rather than an escape hatch.

**MOO2** - the retreat order resolves on the next move, so the ship eats one more round of fire, and retreating ships land at the nearest star system without using warp points, which is a strategic penalty.

**Design lessons.** Every system that works charges for retreat in one of three currencies: rounds of exposure (Stars!, MOO2), hull damage or loss (Stellaris), or strategic position (Stellaris MIA, MOO2 nearest-system). None makes it a free button, and none makes it impossible, because a game where fleets cannot retreat becomes a single-battle-decides-everything game.

---

## 6. Presets and usability

The pattern that recurs is: a very small number of named defaults, auto-assigned by ship role, plus a composer for experts.

- **Stars!** ships exactly two auto-assigned presets - Default-Attack for armed fleets, Default-Defense for unarmed - and lets the player edit or add plans. The casual player never opens the battle-plans dialog
- **Stellaris** ships four to six combat computers, each with a default per hull class ("Default for corvette", "Default for destroyer", "Default for battleship"), so a player who never opens the ship designer still gets a coherent fleet
- **Distant Worlds** sets default engagement stances per mission type in Empire Settings
- **Aurora** offers standing orders (two per fleet) plus conditional orders, which is the expert composer end of the spectrum and is correspondingly heavy
- **ES2** gives every player five cards from the start (Turtle, Power to Shields, Take Trophies, Gravity Distortion, Plasma Distortion) and three slots, unlocking more via technology

The smallest set that covers most situations is four to six presets: an attack default, a defence default, a stand-off variant for long-ranged fleets, and a withdraw option. Naming convention across the genre is doctrinal rather than statistical - "Line", "Picket", "Artillery", "Swarm", "Hit and Run", "No Retreat" - and it reads better than "+10% damage" because it tells the player what the fleet will do, not what number changes.

---

## 7. Failure modes these systems produced

- **Attractiveness gaming (Stars!, chaff).** Cheap one-ship tokens with high cost-per-defence draw entire missile salvos because "one missile one kill" is not reflected in the attractiveness formula. Never fully patched; it became an accepted meta
- **Movement AI blind spots (Stars!, starbase range bug).** "The battle AI doesn't count the +1 range bonus when calculating movement... vs starbase with range 6 missiles, your ships will move to distance 7, the movement AI won't calculate that they are still in range even when they keep getting shot at". A stand-off tactic that mis-computes the enemy's range is worse than no tactic
- **Card interaction removed rather than balanced (ES2).** ES1's rock-paper-scissors card counters were dropped for independent cards in ES2, which cost the system its bluffing depth but removed a guessing game players could not read. Deleting interaction is a legitimate fix when the information to play it does not exist
- **Retreat that trivialises war (Stellaris).** Free emergency FTL would make fleets uncatchable; the 14-day charge, the 25%/75% damage roll and the 5% destruction chance exist specifically to price it. The No Retreat doctrine exists as the opposite pole and pays +33% fire rate for giving up the option
- **Dominant-role targeting.** Stellaris' unarmed targeting weight is set to 0.005, three orders of magnitude below default - if it were not, fleets would spend battles chasing science ships. A target-class order that lets a player say "shoot only the tankers" needs the same guard, or logistics becomes unplayable
- **Doomstack convergence.** Both Stellaris and Stars! converge on a single blob because there is no reason to split; splitting only helps if the doctrine system rewards specialised sub-fleets. Any preset list should make at least one preset (screening, standoff) useless alone and valuable in combination

---

## Comparison table

| Game | What the player sets | Concrete mechanical effect | Genuine trade-off? |
|---|---|---|---|
| Stars! (1995) | Primary + secondary target type, races to attack, one of six tactics | Movement AI only, no stat modifiers; closing versus standing off, mediated by 10%/square beam dissipation and weapon ranges 1-6 | Yes - closing is mandatory for beams and fatal for missile fleets; the enemy's build decides which is right |
| Stellaris | Combat computer per design (Swarm/Picket/Line/Artillery/Carrier/Siege) | Formation distance 10/40/70/100 plus a stat: +5/10/15-25% evasion (Swarm), +10/20/30 tracking (Picket), +5/10/20% chance to hit (Line), +5/10/20% weapons range (Artillery), +25/50/100% engagement range (Carrier) | Yes - each buys a different currency, and evasion/tracking cancel each other; computers are hull-restricted |
| Stellaris | Fleet stance (aggressive/passive/evasive), War Doctrine policy | Evasive auto-retreats and leaves systems on hostile arrival; No Retreat trades all disengagement for fire rate | Yes for doctrines, no for stance (scope only) |
| Endless Space 2 | Up to 3-5 tactic cards, each fixing a range per lane plus a modifier | e.g. Turtle short/short/medium +20% hull absorption; Barrage Fire long/long/long +3% damage per enemy ship; Prudent Positions -25% weapon damage for both fleets | Yes - range commitment plus symmetric cards that favour one composition |
| Aurora 4X | Fire control mode per fire control; standing and conditional orders | Final Defensive Fire fires regardless of Open Fire; PD mode picks max range versus max hit chance; conditional orders wipe the queue when a condition trips | Yes, but expressed as allocation of finite fire controls, not as a stance |
| Distant Worlds | Fleet posture + range; ship engagement stance (attacked / nearby / system / detected) | Controls which targets are engaged and how far the fleet ranges from its anchor; ship stance overrides fleet stance | No - scope dial, not a damage dial |
| Star Ruler 2 | Behaviour on the support-ship design (Cannon, Cavalry, Shield, ...) | Cavalry breaks formation to flank, Shield intercepts shots aimed at the flagship; supply below 50% cuts damage, repair and operations | Partly - a fleet needs a mix, so no single behaviour dominates |
| Master of Orion II | Per-ship Retreat order during the battle turn | Withdraws on the next move (one more round under fire); survivors go to the nearest star system without using warp points | Yes - retreat costs a round of exposure and strategic position |
| Sword of the Stars | Tactical mode (attack, pursuit, standoff) | Documented weakly; community reports standoff as ineffective and pursuit as niche | Unclear - weak evidence, do not build on it |
| Sins of a Solar Empire | Engagement range, auto-attack target priority | Poorly documented in primary sources; players report micromanagement outperforms auto-targeting | Unclear - weak evidence |

---

## Recommended model for this project

Opinionated design for a server-resolved, no-input-during-battle engine with fully player-designed ships. Every number below is a **design proposal, not a citation** - none of these figures come from a source, and all should be play-tested.

### Layering

Keep the canonical Stars! plan as the base layer and add exactly one new axis. Do not replace the tactic list - it already encodes the positional trade-off, and the port's engine already consumes it.

A doctrine is a named tuple of four things:

1. **Stance** - Aggressive / Balanced / Defensive (new)
2. **Tactic** - the six canonical tactics (existing)
3. **Target priorities** - an ordered list over the role taxonomy (existing, extended)
4. **Attack who** - Enemies / Enemies and Neutrals / Everyone / named empire (existing)

### Prerequisite - fix the geometry first

The stance layer is only safe once closing carries a real cost and standing off carries a real cost. Two engine fixes come before any doctrine work:

- **Implement beam range dissipation** - 10% of damage lost across the weapon's full range, per BATTLE.TXT ("a weapon that will do 100dp in the same square as its target will only do 90dp one square away"). Without it, stand-off tactics dominate unconditionally
- **Fix initiative ordering** - `_generate_attacks` must sort descending so the highest initiative fires first

Also recommended, in order of value: the "avoid tokens already targeted" rule, the auto-switch to Disengage when out of targets, and the starbase +1 range bonus.

### The stance axis and its numbers

Three stances, applied uniformly to every stack in the fleet. The intent is that the stance decides **how fast the battle resolves**, and the 16-round clock decides who that helps.

| Stance | Damage dealt | Shields | Movement | Disengage |
|---|---|---|---|---|
| Aggressive | x1.15 | x0.80 | closes one extra square of intent per round, ignores stand-off holds | cannot disengage |
| Balanced | x1.00 | x1.00 | as the tactic dictates | normal (7 moves) |
| Defensive | x0.85 | x1.20 | never closes inside its own longest weapon range | 5 moves instead of 7 |

Why this is a trade and not a button:

- Against a fleet you outgun, Aggressive converts your advantage into a decided battle inside the round limit. Against a fleet you do not outgun, it converts your disadvantage into a decided battle too
- Defensive is how you survive to the round limit and keep the fleet, which matters when a starbase, minefields or next turn's reinforcements are on your side. It is worthless when you must kill something this turn
- Aggressive giving up disengagement is the sharpest cost, and it is the one Stellaris also charges (No Retreat: +33% fire rate, zero disengagement). It means Aggressive is a commitment, not a modifier
- The shields multiplier rather than an armour multiplier is deliberate: shields regenerate between battles in the port's model, armour does not, so the Defensive bonus is genuinely temporary and does not compound across turns

Add the user's requested vocabulary as named presets rather than as new mechanics: "brace" is Defensive plus Minimise Damage to Self; "scatter" is Defensive plus Disengage with each stack fleeing independently (which the engine already does, since disengage is per-stack).

### Target-class taxonomy and role inference

Roles are **computed from the design's own components**, never declared, and the computed role is displayed in the ship designer so the player can see how their hull will be classified. Evaluation is a strict ordered cascade - first match wins:

1. **Starbase** - starbase hull
2. **Bomber** - mounts any bomb component
3. **Fuel tanker** - unarmed and mounts a fuel-pod or fuel-transport component (or fuel capacity above a threshold relative to hull size)
4. **Freighter** - unarmed and cargo capacity greater than zero
5. **Support ship** - unarmed, no cargo, mounts a utility component (mining robot, scanner, repair, remote terraformer)
6. **Capital ship** - armed and `power_rating` above the existing 2000 cut-off
7. **Escort** - armed and `power_rating` at or below 2000
8. **Armed ship** - any armed hull (a catch-all tier, not a computed role)
9. **Any ship** - final fallback

Retain the existing five priority tiers. Add Fuel Tanker and Freighter as new `Victims` values and keep Support Ship as the utility bucket, so the user's requested orders map directly: "attack capital ships" → Capital Ship, "attack small attack ships" → Escort, "attack support ships" → Support Ship, "attack logistic lines" → Fuel Tanker then Freighter.

Two guards, both learned from the failure modes:

- **Keep strict exclusion** (canon behaviour) - a token matching none of the tiers is not fired on. It is what makes "kill their tankers" mean what it says, and it is what makes screening a real counter
- **Never let a fleet with only unmatched targets stand idle** - implement the canonical auto-switch to Disengage. Without it, a "kill the tankers" order against an all-warship fleet produces a battle where one side does nothing for 16 rounds

The counter-play is inherent and should be documented rather than patched: a player who fears "kill the tankers" builds cheap unarmed decoy hulls with a fuel pod. That is Stars! chaff, and it is the same healthy dynamic.

### Retreat rules

Keep canon and add nothing exotic.

- Disengaging tokens accumulate flee moves (7 baseline, 5 under Defensive stance, unavailable under Aggressive) and **remain targetable and continue to fire** throughout. The port's current behaviour of zeroing a fleeing stack's fire is a deviation and should be corrected - canon changes movement only
- Escape is decided by battle speed against the pursuer's speed and weapon range, exactly as in canon. No dice roll, no percentage - the player buys retreat capability at the shipyard with engines, manoeuvring jets and overthrusters
- "Disengage if Challenged" stays per-stack, so a fleet naturally performs partial retreat: damaged tokens leave, undamaged tokens fight on
- Do not add a Stellaris-style hull-damage roll on withdrawal. It duplicates a cost the movement rules already impose, and it makes retreat non-deterministic in a game whose combat is otherwise fully determined by the orders

### Preset doctrine list

Six presets plus a composer. Presets are read-only; "Save as..." clones one into an editable named plan, capped at the existing 14. Auto-assign on fleet creation the way Stars! does: armed fleets get Line Battle, unarmed fleets get Withdraw.

| Preset | Stance | Tactic | Priorities (primary → ...) | Intended use |
|---|---|---|---|---|
| **Line Battle** | Balanced | Maximise Damage | Armed Ship → Any Ship | Default for armed fleets. Never wrong, rarely optimal |
| **Alpha Strike** | Aggressive | Maximise Damage | Capital Ship → Armed Ship → Any Ship | Kill the enemy fleet this turn. No retreat |
| **Standoff Barrage** | Defensive | Maximise Damage Ratio | Capital Ship → Armed Ship → Starbase | Missile fleets. Punishes beam fleets that must close |
| **Brace** | Defensive | Minimise Damage to Self | Armed Ship → Bomber → Any Ship | Hold the position, survive to the round limit, keep the hulls |
| **Commerce Raid** | Balanced | Maximise Damage | Fuel Tanker → Freighter → Bomber | Break the logistics train, ignore the warships |
| **Withdraw** | Defensive | Disengage | none | Default for unarmed fleets. Scatter and run |
| **Custom...** | - | - | - | Opens the full composer |

Names are doctrinal, not statistical, following the genre convention. The commander who wants one dial picks from six rows in the fleet panel; the power player opens the composer, sets stance, tactic, five tiers and attack-who, and names the result.

### Failure modes and how this model avoids each

- **A stance that is always right** - Aggressive gives up disengagement entirely and amplifies both sides' outcomes, so it is only correct when you already expect to win. Defensive cannot close, so it never fires if your weapons are short-ranged. Neither dominates without knowing the enemy's weapon ranges
- **Stand-off dominating unconditionally** - prevented by implementing beam range dissipation before shipping the stance layer. This is a prerequisite, not a nice-to-have
- **A target priority that trivialises the game** - strict exclusion is kept (so orders mean what they say), but the auto-switch to Disengage prevents the idle-fleet degenerate case, and the decoy counter-play is left intact rather than patched out
- **Retreat that makes wars unresolvable** - retreat costs rounds under fire and is bought with engine mass at the shipyard, so a fleet built to escape is a fleet built lighter. Aggressive fleets cannot retreat at all, which is the price of their damage
- **Attractiveness gaming** - not solved, and should not be. It is canonical Stars! behaviour and the intended counter to focused targeting. It should be documented in the encyclopedia rather than patched
- **Doomstack convergence** - Brace and Standoff Barrage are deliberately weak alone and strong in combination with each other, giving a reason to field two fleets with different doctrines at the same location
- **Numbers drifting from canon unnoticed** - the port's 60-round, 1000-unit board already diverges from canon's 16 rounds on 10 x 10, and every stance number above assumes a short attrition clock. Either restore the 16-round limit or re-derive the stance multipliers against 60 rounds; the two cannot both be left alone

---

## Sources

Primary - Stars! canon:

- BATTLE.TXT, official Stars! 2.5 release notes - https://wiki.starsautohost.org/wiki/BATTLE.TXT (retrieved via https://web.archive.org/web/20220523105811/https://wiki.starsautohost.org/wiki/BATTLE.TXT)
- Guts of the Battle Engine, James McGuigan - https://wiki.starsautohost.org/wiki/Guts_of_the_Battle_Engine (retrieved via https://web.archive.org/web/20211231133034/https://wiki.starsautohost.org/wiki/Guts_of_the_Battle_Engine)
- Things to Remember about Battle Speed, Iztok, July 2011 - https://wiki.starsautohost.org/wiki/Things_to_Remember_about_Battle_Speed_by_Iztok_-_July_2011 (retrieved via https://web.archive.org/web/20250210105449/)

Stellaris:

- Core components (combat computer table) - https://stellaris.paradoxwikis.com/Core_components (retrieved via https://web.archive.org/web/20260426184147/)
- Space warfare (disengagement, emergency retreat, targeting defines, force disparity) - https://stellaris.paradoxwikis.com/Space_warfare (retrieved via https://web.archive.org/web/20260424185532/)
- Ship (fleet stances) - https://stellaris.paradoxwikis.com/Ship (retrieved via https://web.archive.org/web/20260620231736/)
- Combat computer formation distances, community - https://steamcommunity.com/app/281990/discussions/0/1697168437865599190/
- War Doctrine effects, community summaries (figures unverified against the wiki) - https://forum.paradoxplaza.com/forum/threads/fleets-hit-and-run-or-no-retreat.1466418/

Endless Space 2:

- Battle Tactics card table - https://endless-space-2.fandom.com/wiki/Battle_Tactics (retrieved via https://web.archive.org/web/20260708213148/)
- Combat - https://endless-space-2.fandom.com/wiki/Combat
- Space Battle Guide, Amplitude community - https://community.amplitude-studios.com/amplitude-studios/endless-space-2/forums/68-game-help/threads/29219-space-battle-guide-explanation-of-game-mechanics
- Card independence versus ES1 rock-paper-scissors - https://steamcommunity.com/app/392110/discussions/0/2765630416817695503/

Aurora 4X:

- Ship Combat (fire control modes, final defensive fire) - https://aurorawiki.pentarch.org/index.php?title=C-Ship-Combat
- Point Defense - https://aurorawiki.pentarch.org/index.php?title=Point_Defense
- Orders (standing and conditional orders) - https://aurorawiki2.pentarch.org/index.php?title=Orders

Distant Worlds:

- Engagement Stance discussion - https://steamcommunity.com/app/261470/discussions/0/1681441347879477457/
- Fleet posture and auto settings - https://steamcommunity.com/app/261470/discussions/0/3112521650142796440/

Star Ruler 2:

- Ships and Combat - http://wiki.starruler2.com/Ships_and_Combat (host unreachable at time of research; content taken from search summaries and https://steamcommunity.com/app/282590/discussions/1/611703999968521444/)

Master of Orion II:

- Combat - https://strategywiki.org/wiki/Master_of_Orion_II:_Battle_at_Antares/Combat

Sword of the Stars and Sins of a Solar Empire (weak evidence, community only):

- https://steamcommunity.com/app/42890/discussions/0/357286663688016478/
- https://forums.sinsofasolarempire.com/312429/auto-attack-selection

Project code read for the gap analysis:

- `/home/lab/workspace/private/games/stars-ultranova-web/backend/server/battle/battle_plan.py`
- `/home/lab/workspace/private/games/stars-ultranova-web/backend/server/battle/ron_battle_engine.py`
- `/home/lab/workspace/private/games/stars-ultranova-web/backend/server/battle/stack.py`
- `/home/lab/workspace/private/games/stars-ultranova-web/backend/server/battle/weapon_details.py`
- `/home/lab/workspace/private/games/stars-ultranova-web/references/original-game/Common/DataStructures/BattlePlan.cs`
- `/home/lab/workspace/private/games/stars-ultranova-web/references/original-game/ServerState/BattleEngine.cs`
