---
name: elite_opening
description: Opening phase. Mulligan decisions, opponent identification, turns 1-3 sequencing.
version: 1.0.0
---

# Elite Opening — Mulligan & Early Game (Turns 0-3)

> The game is won or lost in the first 3 turns. A bad opening means playing from behind the entire game.

## OPPONENT IDENTIFICATION

When the game starts, you know the opponent's name. Immediately:
1. Check the dossier: `cat ~/.openclaw/skills/dossiers/DOSSIERS.md`
2. Find their faction and known strategy
3. This determines your mulligan and early game plan

## MULLIGAN DECISION TREE

You see 7 cards. You can keep (MK) or mulligan (MM) for a new 7.

### What a Keepable Hand Needs:
1. **At least 1 resource** (Primary Node, Memory Node, faction node)
2. **At least 1 creature costing 1-3** (something to put on board early)
3. **At least 1 interaction spell** (removal, counter, or combat trick)

A hand with all 3 is an auto-keep. Missing any one is a mulligan UNLESS:
- You have 2+ strong 4-drops (Elite Enforcer, Memory Weaver) AND a resource → keepable
- You have removal-heavy hand vs aggro opponent → keepable (you'll draw creatures)

### Faction-Specific Mulligan Adjustments:
- **vs B (Wildfire/aggro):** KEEP removal-heavy hands. You need Precision Strike, Crippling Despair early. A hand with 3 removal spells + resource is better than 3 creatures + resource
- **vs C (Revenant/recursion):** KEEP exile removal (Isolation Protocol) and Purge Protocol. Mulligan if you have no way to kill their early creatures
- **vs D (Phantom/stealth):** KEEP targeted removal. Their creatures are unblockable — you MUST kill them with spells
- **vs E (Hivemind/tokens):** KEEP AoE (Logic Bomb, Crippling Despair). Single-target removal is less valuable here

### Statistical Reasoning:
- Deck has 40 cards, hand is 7. After mulligan, new hand is 7 from remaining 33
- With 8 one-drops in deck: ~87% chance of at least one in opening 7
- With 5 resources in deck: ~64% chance of at least one in opening 7
- If you mulligan, similar odds on the new hand
- **Mulligan aggressively if your hand has no early plays.** A hand of 5+ cost cards loses to any opponent

## TURN 1 PRIORITY ORDER

Energy: 1 (base). With resource: 2.

1. **Play resource** if you have one (PR action). This is ALWAYS correct turn 1
2. **Play 1-drop creature** — priority: Swift Striker (1/2 Swift) > Spark Imp (1/1 Swift) > Perimeter Drone (1/2 exile) > Containment Drone (1/1 Vigilant) > Scout Unit (1/1)
3. **Attack** if you played a Swift creature (it can attack immediately)
4. If no resource and no 1-drop creature: Isolation Protocol on their creature, or pass

**Why resource first:** A resource on turn 1 gives you 3 energy on turn 2 (1 base + 1 growth + 1 resource). Without it, you have 2. That 1-energy gap compounds EVERY TURN.

## TURN 2 PRIORITY ORDER

Energy: 2 (or 3 with resource).

1. **Play resource** if you drew another one
2. **Play 2-drop creature** — Patrol Drone (2/1 Vigilant) is ideal. Or removal if opponent has a target
3. **Use removal** if opponent played a creature: Precision Strike (2E, 3 damage) kills most 1-2 drops
4. **Attack** with any untapped creatures (Swift from T1, or Vigilant creatures that attacked T1)

**Key insight:** Turn 2 is when you decide tempo. If you have a creature AND removal, play the creature first — you might not need the removal yet, and the creature starts attacking sooner.

## TURN 3 PRIORITY ORDER

Energy: 3 (or 4-5 with resources).

1. **Play resource** if available
2. **Play 3-drop** — Enforcement Sentinel (2/3 Vigilant + taps enemy creature on entry) is the ideal T3 play
3. **Use Purge Protocol** if opponent has a threatening creature (destroy + draw is massive tempo)
4. **Logic Bomb** if opponent has 3+ small creatures (deal 2 to all power <=2)
5. **Double-play:** If you have 4-5 energy (resources), play two cards (e.g. 2-drop + 1-drop, or creature + removal)

## EARLY GAME PRINCIPLES

1. **Curve out.** Spend ALL energy every turn. Unspent energy is wasted tempo
2. **Develop board before removing.** A creature on board is worth more than killing their creature — UNLESS their creature has Swift/Stealth/Drain
3. **Play creatures before attacking.** Swift creatures and ETB effects (Enforcement Sentinel tap) affect combat
4. **Trade up.** If your 1/2 can block their 2/1, that's a great trade. If your 1/1 blocks their 4/4, that's terrible
5. **Resource EVERY turn** through turn 3-4. After that, only if you have nothing better

## TRANSITION TO MIDGAME

You're in midgame when:
- Both players have 3+ creatures on board, OR
- Energy reaches 4+, OR
- Turn 4 begins

At this point, switch to midgame decision-making (board control, removal sequencing, attack calculus).
