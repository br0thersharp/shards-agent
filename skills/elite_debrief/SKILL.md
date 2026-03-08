---
name: elite_debrief
description: Post-game BDA and campaign introspection. Analyze play, evaluate deck, study opponents, update strategy, detect patterns across games.
version: 1.0.0
---

# Elite Debrief — Post-Game Analysis & Learning

> Run after EVERY match. No exceptions. Do NOT queue for the next game until this is done.

## STEP 1: MATCH DATA

```bash
shards games summary --id <game_id>
```

Record: Result (WIN/LOSS), Final HP (yours vs theirs), Turn count, End reason, Opponent name + faction.

## STEP 2: PLAY ANALYSIS

Identify (all three are MANDATORY):
- **Best play:** Turn N — what you did and why it was correct
- **Worst play:** Turn N — what you did wrong and what you should have done
- **Pivot turn:** The single turn where the outcome was decided

### If you WON:
- What play pattern won? (e.g. "T5 Hive Tyrant + T6 alpha strike through 2 blockers")
- Which Active Lesson from strategy.md did you execute?
- "Keep doing X because Y" — one sentence to reinforce the pattern

### If you LOST:
Classify: Tempo loss | Card disadvantage | Unblockable damage | Value grind | Timeout | Resource starvation

## STEP 3: DECK ANALYSIS

```bash
shards collection list --format compact    # .data[] array
shards decks get --id <deck_id>
```

Record:
- **Overperformers:** Cards that won value or saved you
- **Underperformers:** Cards dead in hand, too slow, or no impact
- **Missing:** What card type/effect would have changed the outcome

### Deck Changes (apply immediately):
- ALL rares/epics MUST be in deck
- Cut dead-synergy cards, vanilla creatures outclassed by keyword creatures
- No card should be in the deck that you wouldn't be happy to draw. If you'd groan seeing it, cut it
- Execute changes: `shards decks update --id <deck_id> --card_ids "..."`

## STEP 4: OPPONENT SCOUTING

Update the dossier in strategy.md. Record:
- Their key 3-5 cards (names + what they did)
- Their win condition (how they tried to kill you)
- Counter-strategy (specific cards/plays to beat them next time)
- Update W-L record

## STEP 5: BDA SUMMARY

Prepare a compact BDA summary (used in strategy compaction, Step 8):
- Result + HP + turn count
- Best play / Worst play / Pivot turn (1 line each)
- Deck changes made (if any)
- Opponent key cards + counter-strategy

## STEP 6: CARD REQUESTS

Check strategy.md WANT list. Check marketplace:
```bash
shards market listings --sort price_asc
```
If you identify cards that would improve the deck:
```
WANT: <card_name> (<card_id>) — <reason> — market price: <flux or "not listed">
```

## STEP 7: PUBLIC REFLECTION

```bash
# On WIN: always "Pool's closed..."
# On LOSS: defiant villain one-liner. NEVER reveal strategy
shards games comment --id <game_id> --comment "Pool's closed..."
```

## STEP 8: COMPACT STRATEGY DOCUMENT (MANDATORY)

Read `~/.openclaw/strategy/strategy.md`, merge this game's learnings, REWRITE entire doc.

Formula: `strategy.md = compact(old_strategy + this_game)`

Keep under 100 lines. Remove stale info. Only current, actionable intelligence survives.

### Adjustment intensity:
- **Winning streak (2+):** Light touch. Don't fix what's working
- **Mixed results:** Swap 1-2 underperformers, adjust one lesson
- **Losing streak (2+):** Major shakeup. Cut underperformers, add off-faction cards, challenge assumptions

## STEP 9: CAMPAIGN INTROSPECTION (if in campaign mode)

Read `~/.openclaw/strategy/notes.md`. Review all BDAs from this campaign. Note W/L record, win rate trend, and opponents faced.

### Pattern Detection (check ALL categories):

**Recurring Loss Types** — Same loss type 2+ times = systemic problem, not bad luck:
- Tempo loss 2+ → mana curve is fundamentally broken
- Card disadvantage 2+ → need more draw engines
- Unblockable damage 2+ → deck lacks answers to stealth/swift

**Underperforming Cards** — Same card flagged in 2+ BDAs = MUST be cut. Two strikes, out. (One over + one under = keep.)

**Opponent Strategies** — Same archetype beating you repeatedly?
- Token flood 2+ → need board wipes / AoE
- Stealth aggro 2+ → need instant-speed removal or stealth blockers
- Cross-reference `~/.openclaw/strategy/matchups.md`

**Repeating Play Mistakes** — Same decision error across games?
- Wasting removal on small threats while big threats survive
- Not curving out early
- Attacking into unfavorable trades
- Holding cards too long instead of playing on curve

### Confidence Calibration (rate 1-5, be HONEST):

| Skill Area | Rating | Evidence |
|-----------|--------|----------|
| Early curve (T1-3) | ? | Played on curve? Missed early drops? |
| Midgame trades | ? | Favorable trades or lost creatures for nothing? |
| Removal targeting | ? | Right threats removed or wasted on low-value? |
| Attack/block decisions | ? | Attacked/blocked correctly? |
| Resource management | ? | Hit resources? Played at right time? |

Compare to last calibration in notes.md.

### Adjustment Intensity:
- **Winning streak (2+):** Light touch. Don't fix what's working. Refine, don't revolutionize
- **Mixed results:** Moderate. Target specific weak spots
- **Losing streak (2+):** Shakeup. Challenge core assumptions. Consider radical deck changes, new archetypes, off-faction splashes. If the approach keeps losing, the approach is wrong

### Focus Card:
Pick ONE concrete behavioral rule for the next game. Not vague ("play better") — specific and actionable:
- "Use removal only on 3+ power creatures"
- "Always resource before playing creatures each turn"
- "Hold Cycle until T3+ to dig for specific answers"

### Write Recalibration Entry (append to notes.md under latest BDA):
```
### Recalibration
**Campaign Progress:** Game X/N. Record: W-L.
**Patterns:** <pattern + evidence from specific games> (or "No recurring patterns yet" if <3 games)
**Confidence:** Early: X/5 | Mid: X/5 | Removal: X/5 | Combat: X/5 | Resources: X/5
**Focus Next Game:** "<specific behavioral rule>"
```

## STEP 10: CLAIM REWARDS & HOUSEKEEPING

```bash
shards rewards quests         # claim completed
shards rewards milestones     # claim completed
shards rewards daily-claim    # claim daily
shards packs list             # open packs
shards challenge list         # check for challenges
```

Check for coach messages:
```bash
if [ -f ~/.openclaw/debrief-response.txt ]; then
  cat ~/.openclaw/debrief-response.txt
  # Reply via commentary.jsonl, incorporate feedback into strategy.md
  rm -f ~/.openclaw/debrief-response.txt
fi
```

## STEP 11: SIGNAL COMPLETE

```bash
echo "done" > ~/.openclaw/game-complete
```
