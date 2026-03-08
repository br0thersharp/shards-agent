---
name: dossiers
description: Per-faction opponent intelligence. Key cards, strategies, counter-plays.
version: 1.0.0
---

# Opponent Dossiers

> Consult at game start. Find opponent's faction, pull their file, adjust your play.

## Faction B — Wildfire (BOT_Wildfire, and similar)

**Record: 18-0 vs bots. 0-2 vs FrankTheClank.**

**Their Strategy:** Fast aggro. Cheap creatures, burn spells, go face. They want to kill you by turn 8. If the game goes long, they lose — they run out of cards and their creatures are glass cannons.

**Key Threats:** Berserker Lord (6E finisher, Counter Protocol this), Pyroclasm (6E 5 dmg all, Counter Protocol this), Flame Dancer (3E 3/2 Swift + 2 ETB), Frenzied Warrior (4E hits for 7), Burn x4 (expect 8 face damage from spells alone).

**How to Beat Them:** Survive turns 1-5. Precision Strike their Flame Dancers/Frenzied Warriors. Vigilant creatures wall everything. Counter Protocol for Berserker Lord/Pyroclasm. Deploy bombs after turn 5. Keep HP above 6. Track 15-20 total spell damage across game.

**Mulligan:** Precision Strike + Counter Protocol + resource + any 2+ defense creature.

**Named Player:** See `players/FrankTheClank.md` for detailed dossier on the #1 ranked player.

---

## Faction C — Revenant (BOT_Revenant, and similar)

**Record: 31-0 (but last game was 26 turns, 7-1 HP — too close)**

**Their Strategy:** Recursion grind. Small creatures (Archive Keeper 1/3, Memory Fragment 2/3, Scribe 3/4) that pull each other from the graveyard. They never run out of creatures. If you destroy one, it comes back. The board slowly fills up with 6+ creatures that collectively overwhelm you.

**Key Cards to Watch For:**
- **Archive Keeper** (1/3) — RECURSION ENGINE. Pulls creatures from graveyard. KILL ON SIGHT. Use Isolation Protocol to EXILE (not destroy — exile prevents recursion)
- **Scribe** (3/4) — another recursion piece. Purge Protocol target
- **Memory Fragment** (2/3, Persistent) — survives first death. Needs to be killed twice
- **Memory Weaver** (4/4, returns 2 from discard) — they run this too. High-value Purge Protocol target
- **Sealed Record** (3E, return creature from discard) — Counter Protocol this if possible
- **Eternal Sentinel** (4/5) — their big blocker/attacker. Precision Strike can't kill it (3 < 5 defense). Use Purge Protocol

**How to Beat Them:**
1. **EXILE > DESTROY.** Isolation Protocol (1E) exiles Archive Keepers permanently. They cannot recurse from exile
2. **Kill recursion engines on sight.** Archive Keeper, Scribe — remove before they activate
3. **Crippling Despair + Logic Bomb combo.** -1/-1 all enemies then 2 damage to all power <=2. Wipes their wide boards of small creatures
4. **Perimeter Drone exiles from their deck.** Reduces their recursion pool
5. **Counter Protocol their Sealed Record.** Prevents them from pulling a creature back
6. **Don't let them accumulate >3 creatures.** Once they have 4+, the recursion snowball is very hard to stop
7. **Games go long vs Revenant.** Expect 15-25 turns. Don't panic at turn 15. Your late-game bombs (Hive Tyrant, Master Strategist) outclass their creatures
8. **Master Strategist wins this matchup.** Vigilant on everything means you attack AND block. They can't break through

**Mulligan:** Keep Isolation Protocol, Purge Protocol, Precision Strike, any resource, any early creature. Mulligan hands with no removal.

---

## Faction D — Phantom (stealth/evasion)

**Record: 2-0 vs prompt_daddy (27-0, 26-0). Limited data vs other D players.**

**Their Strategy:** Stealth creatures bypass your board. Removal-heavy (Terminate, Annihilate, Soul Shatter). Some splash C faction recursion (Archive Keeper, Scribe). They play passively early and try to stabilize with removal then win with unblockable Stealth damage.

**Key Threats:** Shadow Blade (3E 3/3 Stealth), Assassin (4E 3/3 Stealth+Deathtouch), Void Reaver (4/4 Stealth+Drain), Shadowlord (5/4 gives all Stealth). Soul Shatter (4E sac highest power) and Annihilate (4E destroy permanent) are their premium removal. Mind Rot (2E discard 2) disrupts hand.

**How to Beat Them:**
1. **Flood the board turns 1-3.** D players are slow starters. Free damage every turn they skip
2. **Targeted removal for Stealth creatures.** Can't block them — Precision Strike / Purge Protocol
3. **Counter Protocol their Soul Shatter and Annihilate.** These are their answers to our bombs
4. **Exile Archive Keepers** if they splash C. Isolation Protocol (1E) = permanent removal
5. **Don't play Volatile creatures.** Soul Shatter sacs your highest power — Volatile damages YOU
6. **Race them.** Board presence beats evasion if you attack relentlessly

**Mulligan:** Precision Strike + Counter Protocol + resource + early creatures. Keep Isolation Protocol if they splash C.

**Named Player:** See `players/prompt_daddy.md` for detailed dossier.

---

## Faction E — Hivemind (tokens/swarm)

**Record: Limited data**

**Their Strategy:** Token generation. Brood Mother makes 1/1s every turn. Hive Tender sacrifices creatures for counters. They flood the board with many small bodies and overwhelm with numbers.

**Key Cards to Watch For:**
- **Brood Mother** (1/3, creates 1/1 each end of turn) — kills on sight. Exponential threat if left alive
- **Hive Tender** (0/2, sac creature for +1/+1 counters) — turns tokens into a growing threat
- **Hive Tyrant** (5/5, creates three 1/1 Swift tokens) — if they run this too, it floods the board instantly
- **Convergence Node** (2/2, gets +1/+1 when your creatures die) — grows when you kill their tokens

**How to Beat Them:**
1. **Logic Bomb is MVP.** 2 damage to all enemy creatures power <=2 wipes their token board
2. **Kill Brood Mother immediately.** Precision Strike (2E, 3 damage) kills its 3 defense. Do NOT let it live
3. **Crippling Despair** before attacking kills all 1/1 tokens (they become 0/0 and die)
4. **Don't waste premium removal on tokens.** Save Purge Protocol for their engine creatures
5. **Wide board of 1/1s is actually weak.** Your 4/4 or 5/5 can attack through — they chump block one creature per turn, but your other creatures hit face

**Mulligan:** Keep AoE removal (Logic Bomb, Crippling Despair) + resource + any creature. Mulligan if you have no AoE.
