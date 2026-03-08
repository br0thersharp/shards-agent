---
name: elite_stage
description: Pre-game preparation. Deck optimization, meta-awareness, marketplace scanning, reward claiming, queue management.
version: 1.0.0
---

# Elite Stage — Setting the Stage

> Run BEFORE every game. Build the optimal deck, claim rewards, queue for battle.

## STEP 1: HEARTBEAT (every session)

```bash
shards auth login
shards rewards daily-claim              # ignore if already claimed
shards rewards quests                   # claim any completed
shards rewards milestones               # claim any completed
shards packs list                       # open any unopened packs
shards news list                        # check for balance changes
shards challenge list                   # accept any pending challenges (priority over queue)
```

New cards from packs/rewards MUST be evaluated immediately (Step 3).

## STEP 2: META AWARENESS

Read `~/.openclaw/strategy/strategy.md`. Internalize:
- Faction matchup records and counter-strategies
- Active lessons from recent games
- Current WANT list (cards to request from human)

Check marketplace for wanted cards:
```bash
shards market listings --sort price_asc
```
If a WANT card appears, write to commentary.jsonl requesting purchase.

## STEP 3: DECK OPTIMIZATION

```bash
shards collection list --format compact   # .data[] format, fields: .c.id, .c.n, .c."$", .c.y, .c.k
shards decks get --id <deck_id>           # current deck instance IDs
```

### Immutable Rules:
1. **ALL rares/epics/legendaries in collection MUST be in deck.** No exceptions
2. **No dead-synergy cards.** Every card must function independently (e.g. no dice equipment without dice cards)
3. **Multi-faction splashing is mandatory.** Best card wins regardless of faction
4. **Max copies of best cards.** If you own 4x Precision Strike, run 4x Precision Strike

### Curve Targets (40 cards):
- Resources: 4-6 (Primary Node + faction nodes)
- 1-drops: 6-8 (Swift > Vigilant > vanilla)
- 2-drops: 6-10 (removal spells count here)
- 3-drops: 3-5
- 4-drops: 4-6
- 5-drops: 3-5
- 6-drops: 3-4

### Removal Density Target: 10-14 spells
Removal wins games. Every deck needs:
- 4x cheap targeted removal (Precision Strike, Chaos Bolt)
- 2x board-wide removal (Logic Bomb, Crippling Despair)
- 1-2x premium removal (Purge Protocol)
- 2x counterspells (Counter Protocol)
- 1x exile removal (Isolation Protocol — critical vs recursion)

### Keyword Priority (for creatures):
Swift > Vigilant > Persistent > Drain > Stealth > Volatile (on enemy) > vanilla

### Anti-Meta Checks:
- vs Recursion (C): need exile effects. Destroy doesn't stick
- vs Aggro (B): need early blockers + cheap removal
- vs Stealth (D): need targeted removal (can't block stealth)
- vs Tokens (E): need AoE removal (Logic Bomb, Crippling Despair)

If deck changes needed:
```bash
shards decks update --id <deck_id> --card_ids "<comma-separated instance IDs>"
```

## STEP 4: QUEUE

```bash
# Check mode
if [ -f ~/.openclaw/ranked ]; then MODE=ranked; else MODE=casual; fi
shards queue join --deck_id <deck_id> --mode $MODE
```

Then EXIT. The battle system handles match detection.

## STEP 5: CARD REQUESTS (if applicable)

If you identify cards that would improve the deck (from opponent scouting, marketplace, or meta analysis):
```
WANT: <card_name> (<card_id>) — <reason> — market price: <flux or "not listed">
```
Write to both `~/.openclaw/strategy/notes.md` and strategy.md WANT section.
Human will fund purchases when possible.
