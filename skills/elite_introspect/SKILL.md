---
name: elite_introspect
description: Campaign introspection protocol. Run after BDA and before queuing the next game. Pattern recognition across games, confidence recalibration, and setting focus areas.
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - shards
---

# Elite Introspect — Campaign Self-Guided Introspection

> Run this AFTER the BDA (elite_train) and BEFORE queuing the next game. MANDATORY in campaign mode.

## WHEN TO USE

After every BDA during a campaign. This is the higher-level feedback loop — the BDA handles match data and deck changes, introspection handles **patterns across games** and **behavioral recalibration**.

## STEP 1: REVIEW CAMPAIGN ARC

Read `~/.openclaw/strategy/notes.md`. Scan all BDAs from this campaign session.

Count your **W/L record** for this campaign so far. Note:
- How many games played
- Win rate trend (improving, declining, flat)
- Which opponents you've faced and results

## STEP 2: PATTERN DETECTION

Look across ALL games in this campaign for recurring issues. You MUST check each category:

### Recurring Loss Types
Has the same loss type appeared **2+ times**? If so, it's a **systemic problem**, not bad luck.
- Tempo loss 2+ times → mana curve is fundamentally broken, not just one bad draw
- Card disadvantage 2+ times → need more draw engines, not just "play better"
- Unblockable damage 2+ times → deck lacks answers to stealth/swift, need structural fix

### Underperforming Cards
Has the same card been flagged as underperformer in **2+ BDAs**? If so, it MUST be cut.
- Don't give a card three chances. Two strikes = out.
- Note: if a card overperformed once and underperformed once, that's fine — keep it.

### Opponent Strategies Beating You
Is the same archetype or strategy winning against you repeatedly?
- Token flood beating you 2+ times → need board wipes or AoE
- Stealth aggro beating you 2+ times → need instant-speed removal or stealth blockers
- Check `~/.openclaw/strategy/matchups.md` for patterns across opponents

### Repeating Play Mistakes
Are you making the same decision error across games?
- Wasting removal on small threats while big threats survive
- Not curving out in early turns
- Attacking into unfavorable trades
- Holding cards too long instead of playing on curve

## STEP 3: CONFIDENCE CALIBRATION

Rate yourself 1-5 on each skill area. Be HONEST — compare to how the games actually went, not how you feel.

| Skill Area | Rating (1-5) | Evidence |
|-----------|-------------|----------|
| Early curve (turns 1-3) | ? | Did you play on curve? How many games did you miss early drops? |
| Midgame trades | ? | Did you make favorable trades? Did you lose creatures for nothing? |
| Removal targeting | ? | Did you remove the right threats? Or waste removal on low-value targets? |
| Attack/block decisions | ? | Did you attack when you should have? Block correctly? |
| Resource management | ? | Did you hit enough resources? Play them at the right time? |

Compare to your last calibration (if one exists in notes.md). Note any changes.

## ADJUSTMENT INTENSITY RULE

Your adjustment level must be **proportional to pain**:
- **Winning streak (2+ wins):** Light touch. Don't fix what isn't broken. Focus on refinement, not revolution.
- **Mixed results:** Moderate changes. Target specific weak spots.
- **Losing streak (2+ losses):** Shakeup time. Challenge core assumptions. Consider radical deck changes,
  new archetypes, off-faction splashes. If the current approach keeps losing, the approach is wrong.

## STEP 4: SET FOCUS CARD

Pick **ONE** specific focus area for the next game. Not a vague goal — a concrete behavioral rule.

**BAD focus areas:**
- "Play better" ← useless
- "Win more" ← not actionable
- "Improve deck" ← that's the BDA's job

**GOOD focus areas:**
- "Use removal only on 3+ power creatures"
- "Always resource before playing creatures each turn"
- "Never attack with a creature that would trade down"
- "Hold Cycle until turn 3+ to dig for specific answers"
- "If opponent has 2+ creatures, play defensively until I can trade favorably"

## STEP 5: WRITE RECALIBRATION ENTRY

Write to `~/.openclaw/strategy/notes.md` under the most recent BDA:

```markdown
### Recalibration
**Campaign Progress:** Game X/N complete. Record: W-L.
**Patterns Detected:**
- <pattern 1 with evidence from specific games>
- <pattern 2 with evidence> (or "No recurring patterns yet" if <3 games played)
**Confidence Ratings:** Early curve: X/5 | Midgame: X/5 | Removal: X/5 | Attack/block: X/5 | Resources: X/5
**Focus for Next Game:** "<specific behavioral rule>"
```

## STEP 6: CAMPAIGN PROGRESS LOG

Write a one-line campaign status to the commentary feed:

```bash
echo '{"time":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","type":"assessment","text":"Campaign game X/N complete. Record: W-L. Focus: <focus area>."}' >> ~/.openclaw/commentary.jsonl
```

Only after this completes: proceed to queue the next game.
