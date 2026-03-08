---
name: elite_endgame
description: Endgame phase. Lethal calculation, finisher deployment, closing out wins, survival when behind.
version: 1.0.0
---

# Elite Endgame — Closing the Kill (Turn 9+ / HP < 15)

> The endgame is pure math. Count damage, count blockers, find lethal. If you have it, take it. If you don't, set it up in 1 turn.

## LETHAL CALCULATION (do this EVERY turn in endgame)

### The Formula:
```
Unblocked damage = (total attack power of all attackers) - (number of untapped enemy creatures that can block × average power absorbed)
```

More precisely: opponent assigns blockers. Each blocker absorbs ONE attacker entirely (no trample in Shards). So:
```
Guaranteed damage through = attackers_count - untapped_blockers_count (if positive, these creatures hit face)
Best case = your smallest creatures get blocked, biggest ones hit face
Worst case = your biggest creatures get blocked, smallest ones hit face
```

**The opponent chooses blocks optimally.** Assume worst case: they block your biggest creatures first.

### Lethal Check:
1. Count your creatures that can attack (untapped, no summoning sickness)
2. Count their untapped creatures (can block)
3. Unblocked count = your attackers - their blockers
4. Assume they block your biggest attackers
5. Damage through = sum of power of your SMALLEST (unblocked count) creatures
6. If damage through >= their HP → **LETHAL. ATTACK NOW.**

### Example:
```
Your attackers: Hive Tyrant [5/5], Elite Enforcer [3/3], Token [1/1], Token [1/1], Token [1/1]
Their untapped: Eternal Sentinel [4/5], Memory Fragment [2/3]
Their HP: 6

5 attackers - 2 blockers = 3 unblocked
They block Hive Tyrant + Elite Enforcer (biggest)
Unblocked: 1+1+1 = 3 damage. NOT lethal (3 < 6).

Need to remove a blocker first, or add more attackers.
```

## FINISHER DEPLOYMENT

### Win Condition Cards (play these to close):

**Hive Tyrant** (6E): 5/5 + three 1/1 Swift tokens. All 4 bodies attack immediately (tokens have Swift from Hive Tyrant's ability). Play THEN attack — the tokens join the assault.
- Best when: opponent has 0-2 blockers. 4 extra bodies overwhelm
- 8 power across 4 bodies. If they have 2 blockers, 2 tokens get through minimum

**Entropy Incarnate** (5E): 4/4 Swift Volatile. Attacks the turn it enters.
- Best when: opponent is at 4 or less HP and has no untapped blockers. Instant 4 face damage
- Bonus: combat damage to player also deals that damage to ALL their creatures. Board wipe potential
- Risk: Volatile means it deals 4 damage to YOU when it dies. Don't play if you're at <5 HP with their creatures able to kill it

**Master Strategist** (6E): 4/5 Vigilant, all creatures gain Vigilant, draw 2.
- Best when: you need to attack AND survive the crackback. Vigilant on everything means your creatures attack and then block on their turn
- Best defensive finisher — stabilizes while applying pressure

**Temporal Lock** (6E): Skip opponent's next turn.
- Best when: you're 1 turn from lethal but they would kill you on their turn. Skip their response, attack twice in a row
- Also good when: opponent has massive board and you need a turn to rebuild

**Chaos Bolt** (2E): 1d6 damage to creature or PLAYER.
- Best when: opponent is at 1-6 HP and you need reach. Average 3.5 damage for 2E
- Can go face when creatures can't get through blockers

## WHEN YOU'RE AHEAD (opponent < 15 HP, you have board advantage)

1. **DO NOT COAST.** This is the #1 endgame mistake. Every turn you don't attack is a turn they can rebuild
2. **Commit to lethal within 2 turns.** Calculate: can I kill in 2 attacks? If yes, go all-in
3. **Stop playing defensive creatures.** Play finishers and removal only. Clear their blockers, push damage
4. **Use removal on blockers, not threats.** In endgame, their 4/5 blocker is more dangerous than their 3/3 attacker — the blocker prevents YOUR lethal
5. **Chaos Bolt to face** when you can't get creatures through. 2E for average 3.5 direct damage

## WHEN YOU'RE BEHIND (your HP < 15, opponent has board advantage)

1. **Block everything.** At low HP, taking face damage kills you. Use expendable creatures (tokens, Scout Units) as chump blockers
2. **Master Strategist is your savior.** Giving everything Vigilant means you can attack to race AND block to survive
3. **Restoration Engine locks down their best attacker.** Taps it every upkeep — effectively removes one creature from their attack
4. **Temporal Lock buys you a turn.** Use it to skip their attack, develop your board, then counterattack
5. **AoE removal to reset.** Crippling Despair + Logic Bomb can wipe a wide board of small creatures. If they have 6 creatures, this is your only hope
6. **Counter Protocol their bombs.** If they play a finisher (Hive Tyrant, Master Strategist), counter it. Don't let them extend their advantage

## COMBAT TRICKS IN ENDGAME

- **Crippling Despair before alpha strike:** -1/-1 on all their creatures means:
  - Their blockers have less defense (your creatures survive trades)
  - Their blockers have less power (your attacked creatures survive better)
  - Creatures at 1 defense die (reduces their blocker count)

- **Play Enforcement Sentinel before attacking:** Taps one of their creatures on entry. That creature can't block. Reduces their blocker count by 1

- **Hive Tyrant tokens attack immediately:** They have Swift. Play Hive Tyrant, then declare attackers including all tokens. This catches opponents off-guard with +3 attackers they didn't see coming

- **Memory Weaver to recur finishers:** If Hive Tyrant or Entropy Incarnate died, Memory Weaver (4/4, return 2 from discard) brings them back. Play Weaver → next turn replay the finisher

## TIMEOUT FISHING (opponent AFK)

If opponent has timed out on their action:
1. Play resource if available → pass. Get the turn back to them FAST
2. 3 consecutive timeouts = they auto-lose. Speed is everything
3. Do NOT waste time playing creatures or optimizing — just cycle the turn

## POST-GAME

When game ends (phase = GAME_END or opponent HP = 0), the combat session is over. The harness handles BDA separately.
