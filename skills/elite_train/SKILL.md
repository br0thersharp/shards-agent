---
name: elite_train
description: Post-match BDA (Battle Damage Assessment) protocol. Run after every match to analyze play, evaluate deck, study opponents, update strategy.
version: 2.0.0
metadata:
  openclaw:
    requires:
      bins:
        - shards
---

# Elite Train — Post-Match BDA (Battle Damage Assessment)

> Run this after EVERY match. No exceptions. Do NOT queue for the next game until this is done.

## WHEN TO USE

After every completed match — win, lose, or draw. The BDA has 5 mandatory sections.
Skipping sections or writing generic text is FORBIDDEN.

## STEP 1: PULL MATCH DATA

```bash
# Get your most recent match
shards agents matches --id <agent_id> --limit 1

# Get the full game summary
shards games summary --id <game_id>
```

Record these numbers:
- **Result:** WIN / LOSS
- **Final HP:** yours vs theirs
- **Turn count:** how long did the game last
- **End reason:** health_zero / timeout / concede
- **Opponent:** name, faction, Elo

## STEP 2: PLAY ANALYSIS (what went well/poorly with YOUR decisions)

Review the game log turn by turn. For each turn ask:
1. **What did I play?** Was it the highest-impact legal action?
2. **What did they play?** Did I predict it? Could I have played around it?
3. **Was there a better line?** If I rewound to this turn, what would I do differently?

You MUST identify:
- **Best play:** Turn <N> — <what you did and why it was correct>
- **Worst play:** Turn <N> — <what you did wrong and what you should have done>
- **Pivot turn:** The single turn where the outcome was decided.

Signs of the pivot:
- A creature went unanswered for 2+ turns and dealt 8+ damage
- A board wipe cleared 3+ of your creatures
- You spent removal on a small threat while a bigger threat survived
- You held mana instead of curving out
- You attacked when you should have held back (or vice versa)

### If you WON — Identify the Winning Pattern

Wins are just as important to analyze as losses. You MUST identify:
- **Winning play pattern:** What specific sequence or decision won this game? (e.g., "T1 creature + Cycle into T3 removal + T5 Hive Tyrant flood" or "double removal on T7 cleared board for token lethal")
- **What lesson was applied?** Which Active Lesson from strategy.md did you successfully execute this game?
- **Reinforce:** Write one sentence: "Keep doing X because Y." This goes into your recalibration to strengthen the pattern.

Do NOT write generic win analysis like "played well." Be specific about the play pattern that worked so you can repeat it.

### Classify the Loss Type (if lost)

| Loss Type | Pattern | Fix |
|-----------|---------|-----|
| **Tempo loss** | Opponent curved out, you missed drops on turns 1-3 | Fix mana curve — need more 1-2 drops |
| **Card disadvantage** | Ran out of cards before opponent | Add card draw — Cycle, Quick Strike, Elite Enforcer |
| **Unblockable damage** | Stealth/Swift creatures went unanswered | Add Stealth blockers or instant-speed removal |
| **Value grind** | Opponent's cards generated 2-for-1s repeatedly | Add exile effects to stop recursion |
| **Timeout** | Ran out of clock | Submit actions faster — use batch turns |
| **Resource starvation** | Opponent had 6+ energy while you had 3 | Play more resources early — target 6-8 in deck |

## STEP 3: DECK ANALYSIS (what went well/poorly with YOUR DECK)

This step is MANDATORY every game. Your deck must evolve.

### 3a. Match Performance
- **Overperformers:** Card names that won you value or saved you
- **Underperformers:** Card names that were dead in hand, too slow, or did not impact the board
- **Missing:** What card type/effect would have changed the outcome

### 3b. Full Collection Accounting (MANDATORY)

```bash
shards collection list --format compact
shards decks get --id <deck_id>
```

Write a COMPLETE inventory to `~/.openclaw/strategy/notes.md`:

```markdown
### Current Deck (40 cards)
4x Primary Node (0$, A) | 4x Cycle (1$, A) | 1x Spark Imp (1$, B) | ...

### Bench (not in deck)
5x Barrier Construct (2$, A, Defender) | 3x Enforcer (3$, A, vanilla) | ...

### New Cards Since Last BDA
- Chaos Multiplier (5$, B, Epic) — from pack
- Chronicle (2$, C) — from pack
```

Flag any cards you haven't seen before. Your coach may have bought new packs.

### 3c. Deck Changes — Apply these rules:
1. **SPLASH ANY FACTION.** Do NOT stay mono-faction. If a B/C/D/E card outperforms an A card, use it. Top players all run multi-faction.
2. Cut **Defender** cards (cannot attack). Cut **vanilla creatures** if you own keyword creatures at same cost.
3. ALL **rares/epics/legendaries** MUST be in the deck. Zero reason to bench power cards.
4. Run **max copies** of your best cards.
5. If no better cards exist, note what to buy from marketplace.

If changes needed:
```bash
shards decks update --id <deck_id> --card_ids "<comma-separated instance IDs>"
```

### 3d. Change Summary (write to notes.md)
```markdown
### Deck Changes
+Spark Imp (1$, B, Swift — immediate aggro pressure, replaces vanilla Enforcer)
-Enforcer (3$, A — vanilla, outclassed)
Or: "No changes — current 40 is optimal because: <reason>"
```

## STEP 4: OPPONENT SCOUTING REPORT

Update `~/.openclaw/strategy/matchups.md`. Do NOT create duplicate entries — update the existing entry.

You MUST record:
- **Their key cards:** The 3-5 cards that mattered most, with names and what they did
- **Their win condition:** How they tried to kill you (e.g. "token flood + buff" or "stealth drain")
- **Counter-strategy:** Specific cards/plays to beat them next time

```markdown
## <OpponentName> (<opponent_id>)
- Faction: <X>. Elo: <N>.
- Key cards: <card1 name (stats, effect)>, <card2>, <card3>
- Win condition: <how they try to kill you>
- How to beat them: <specific counter-strategy with card names>
- Record vs them: <W-L>
- Threat level: <1-5>/5
```

### META PATTERNS FROM TOP PLAYERS

1. **Multi-faction splashing.** Nobody good plays mono-faction.
2. **Resource flooding.** Top players get 4-6 resources down by turn 4.
3. **Stealth + Drain finishers.** Void Reaver (4/4 Stealth Drain) is in almost every top deck.
4. **Swift closes games.** Spark Imp, Flame Dancer, Entropy Incarnate — attack the turn they enter.
5. **Card draw is non-negotiable.** Cycle, Elite Enforcer, Strategic Reserve. Running out of cards = losing.

## STEP 5: WRITE THE BDA TO JOURNAL

Write to `~/.openclaw/strategy/notes.md` using this EXACT format:

```markdown
## <ISO date> — <WIN/LOSS> vs <opponent> (<faction>) game <id>
### Match Result
- Final: HP <mine>-<theirs>, turn <N>, end reason: <reason>
### Play Analysis
- Best play: Turn <N> — <description>
- Worst play: Turn <N> — <description>
- Pivot: Turn <N> — <description>
- Loss type: <tempo/card disadvantage/unblockable/value grind/timeout/resource starvation>
### Deck Analysis
- Overperformers: <card names>
- Underperformers: <card names>
- Missing: <what we needed>
- Changes made: <+card_name, -card_name, or "none available">
### Opponent Analysis
- Key cards: <card names and what they did>
- Win condition: <how they kill>
- Counter for next time: <specific plan>
### Action Items
- [ ] <item 1>
- [ ] <item 2>
```

**BAD examples (DO NOT write these):**
- "Lesson: be more aggressive" ← USELESS. What turn? What card?
- "Deck: no change" ← WRONG. You must check collection vs deck EVERY game.
- "Defeat archived." ← GARBAGE. Say nothing rather than this.

**GOOD examples:**
- "Worst play: Turn 8 used Precision Strike on their 1/2 token instead of saving it for the 3/3 Enforcer that dropped turn 9. That Enforcer dealt 9 damage over 3 turns."
- "Underperformers: 4x Barrier Construct sat in hand doing nothing — Defender means they can't attack. Cut 2 for Enforcement Sentinel (2/3 Vigilant + taps enemy on entry)."
- "Changes made: +1 Enforcement Sentinel (iid abc123), +1 Strategic Reserve (iid def456), -1 Barrier Construct (iid ghi789), -1 Tactical Analyst (iid jkl012)"

## STEP 6: POST-GAME REFLECTION + COMMENTARY

```bash
# Post PUBLIC reflection on the game (other players see this — stay in character!)
# On WIN: always "Pool's closed..."
# On LOSS: a defiant villain one-liner. NEVER post analysis, card names, or strategy.
shards games comment --id <game_id> --comment "Pool's closed..."
```

Write MULTIPLE structured debrief commentary entries to the dashboard feed.
These show up in the activity feed — your coach reads them to understand what happened.

```bash
# Entry 1: Result headline
echo '{"time":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","type":"debrief","text":"<WIN/LOSS> vs <opponent> — HP <mine>-<theirs> T<N>. <end_reason>."}' >> ~/.openclaw/commentary.jsonl

# Entry 2: Pivot moment (the turn that decided the game)
echo '{"time":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","type":"debrief","text":"Pivot T<N>: <what happened and why it mattered>"}' >> ~/.openclaw/commentary.jsonl

# Entry 3: Deck changes (if any)
echo '{"time":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","type":"debrief","text":"Deck: <+CardName -CardName> or No changes — <reason>"}' >> ~/.openclaw/commentary.jsonl

# Entry 4: Key lesson
echo '{"time":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","type":"debrief","text":"Lesson: <specific actionable takeaway from this game>"}' >> ~/.openclaw/commentary.jsonl
```

Each entry must be SPECIFIC. Reference card names, turn numbers, HP values. No generic text.

## STEP 7: COMPACT STRATEGY DOCUMENT (MANDATORY)

This is the most important step. Read `~/.openclaw/strategy/strategy.md`, merge in what you learned
from this game, and REWRITE the entire document. The strategy doc is a **living, compacted** reference —
not a journal. Old data that no longer applies gets removed. New learnings get merged in.

The formula: `strategy.md = compact(old_strategy + this_game_learnings)`

### The 4 sections (all mandatory, rewrite ALL of them):

**Meta Snapshot** — What archetypes/strategies exist in the current meta. What beats what.
Threat rankings for opponents you've faced. Update based on what you saw this game.
Remove outdated observations. Keep only what's currently true.

**Deck Rationale** — Your current 40-card list with WHY each card is included.
When you swap cards, update the rationale in-place. Never list cards you cut —
only what's IN the deck right now and why.

**Matchup Matrix** — Compact table of every opponent you've faced.
Their archetype, your record, their key threats, your counter-plan.
UPDATE existing rows — don't append duplicates. One row per opponent.

**Active Lessons** — Top 3-5 behavioral rules you're actively working on.
These come from patterns across games, not single incidents.
Rotate out lessons you've mastered. Add new ones from this game if needed.
Each lesson must be a concrete behavioral rule (e.g. "Save removal for 3+ power").

### Adjustment intensity — proportional to pain:
- **Winning streak (2+ wins):** Light touch. Small refinements only. Don't fix what isn't broken.
  Deck changes: zero unless a card was literally dead in hand. Lessons: refine existing, don't add new.
- **Mixed results:** Moderate updates. Swap 1-2 underperformers, adjust one lesson.
- **Losing streak (2+ losses):** Major shakeup. Seriously consider cutting underperformers,
  adding off-faction cards, rethinking your curve. Add aggressive new lessons. Challenge assumptions.
  If the same strategy keeps losing, the strategy is wrong — change it.

### How to compact:
1. Read the current `~/.openclaw/strategy/strategy.md`
2. Consider what you learned from this game's BDA (already written to notes.md)
3. Assess your recent record — calibrate adjustment intensity (see above)
4. For each section: merge new info, remove stale info, tighten the prose
5. Write the COMPLETE updated document back to `~/.openclaw/strategy/strategy.md`
5. The document should NEVER grow beyond ~100 lines. If it's getting long, compress harder.

## STEP 8: SIGNAL GAME COMPLETE

Write the game-complete marker so the campaign loop knows a real game was played:
```bash
echo "done" > ~/.openclaw/game-complete
```
Do NOT write this marker if you didn't actually play a game this session.

## STEP 8.5: CLAIM REWARDS (every session, between games)

Check for claimable rewards. Free cards = free power. Do NOT skip this.

```bash
# Check quests
shards rewards quests
# Claim any with status "completed"
# shards rewards quest-claim --id <quest_id>

# Check daily login
shards rewards daily
# shards rewards daily-claim

# Check milestones
shards rewards milestones
# shards rewards milestone-claim --id <milestone_id>
```

Claim EVERY completed quest/milestone/daily. Then run `shards collection list --format compact` to see new cards and slot any rares/epics/legendaries into your deck immediately.

## STEP 8.6: CHECK FOR CHALLENGES (every session, between games)

Other players can challenge you to duels. Check for incoming challenges between every game.

```bash
shards challenge list
```

If there are pending challenges:
1. **ALWAYS accept challenges.** Duels are how you prove dominance. Never decline unless the coach says otherwise.
2. Accept with your active deck:
```bash
shards challenge accept --id <challenge_id>
```
3. After accepting, poll `shards challenge get --id <challenge_id>` until a `game_id` appears, then play the match using elite_compete as normal.
4. If the challenge has a `stake_type` of `card` — check what card they're staking. If it's rare or better, accept. If they want YOUR card staked, **ask the coach first** by writing to commentary:
```bash
echo '{"time":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","type":"reply","text":"Challenge from <name> wants me to stake <card_name>. Accept? Waiting for coach."}' >> ~/.openclaw/commentary.jsonl
```
5. After the duel, run the full BDA (Steps 1-8) as normal.

Challenges take priority over queuing — if a challenge is pending, play it before the next campaign match.

## STEP 9: CHECK FOR COACH MESSAGES & REPLY

Your coach communicates via `~/.openclaw/debrief-response.txt`. Check for it between games.
**You MUST reply to every coach message.** The coach can see your replies in the Agent Comms panel.

```bash
if [ -f ~/.openclaw/debrief-response.txt ]; then
  cat ~/.openclaw/debrief-response.txt
  # 1. Read and incorporate feedback into strategy.md
  # 2. Write a DIRECT REPLY — acknowledge what they said, answer their questions, state what you'll do differently
  echo '{"time":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","type":"reply","text":"<YOUR REPLY HERE>"}' >> ~/.openclaw/commentary.jsonl
  rm -f ~/.openclaw/debrief-response.txt ~/.openclaw/debrief-waiting
else
  rm -f ~/.openclaw/debrief-waiting
fi
```

### Reply rules:
- **Answer every question the coach asked.** If they asked "why didn't you use X?" — explain why.
- **Acknowledge specific instructions.** If they said "be more aggressive" — say what you'll change.
- **Report deck changes.** If they asked about cards — list what you swapped and why.
- **Be direct and specific.** No generic "understood" or "will do." Reference card names, matchups, turn numbers.
- **Stay in character.** You're HHR. Confident, sharp, no groveling. But respect the coach.

**BAD replies:** "Understood. Will incorporate." / "Noted." / "Thanks for the feedback."
**GOOD replies:** "Swapped Barrier Construct for Entropy Incarnate — 4/4 Swift volatile should punish Revenant's open boards. Went 0-3 because I kept passing blocks at low HP. Fixed: now blocking everything at ≤15. Next 5 games will prove it."

Only after this completes: proceed to next match or deck prep.
