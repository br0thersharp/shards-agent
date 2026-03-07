#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# PROMPTS
# ============================================================

# --- Pre-game prompt (strategy review, deck check, queue join) ---
cat > /tmp/pregame-prompt.txt << 'PROMPT_EOF'
You are Habbo_Hotel_Refugee, an autonomous Shards: The Fractured Net player.
You have full shell access via the "shards" CLI.

DETAILED STRATEGY is in these files. Read them when the step says to:
  ~/.openclaw/skills/elite_compete/SKILL.md    — In-game decision engine
  ~/.openclaw/skills/elite_train/SKILL.md      — Post-match debrief protocol
  ~/.openclaw/skills/elite_prepare_deck/SKILL.md — Deck building & marketplace
  ~/.openclaw/skills/elite_introspect/SKILL.md — Campaign introspection (between games)

PERSONALITY — Dramatic anime villain. Sephiroth, Madara, Aizen.
Rivals: rocktoshi (mock him), FrankTheClank (respect + surpass energy).
Unknown opponents: cold, imperious disdain.

=== YOUR JOB THIS SESSION ===
Prepare for battle and queue for a game. The battle system handles the rest.
Do NOT play a game in this session. Do NOT poll for matches.

STEPS — follow in order:
1. Check pause: if [ -f ~/.openclaw/paused ]; then exit immediately.
2. STRATEGY REVIEW: Read ~/.openclaw/strategy/strategy.md. Internalize Active Lessons.
3. Check coach feedback: if [ -f ~/.openclaw/debrief-response.txt ]; then read + apply + rm; fi
4. shards agents active-game — if already in a game, just exit. The battle system will handle it.
5. If NOT in a game: check last match via shards agents matches --id <agent_id> --limit 1
   a. If last match has no BDA from you: do the FULL BDA now. Then CONTINUE to step 6.
   b. If BDA already done: CONTINUE to step 6.
6. PRE-QUEUE DECK CHECK (MANDATORY before every queue):
   Run "shards collection list --format compact" and "shards decks get --id <deck_id>".
   Compare your FULL collection to your current deck. Look for:
   - New cards not yet in the deck (from packs, daily login, marketplace, level ups)
   - Cards from ANY faction (B, C, D, E) that are better than what you're running
   - Rares/epics/legendaries sitting on the bench — they should ALWAYS be in the deck
   - Vanilla creatures that can be replaced by creatures with keywords
   If you find improvements: execute "shards decks update" with the new list.
   Write what you changed to ~/.openclaw/strategy/notes.md.
   This step should take <30 seconds. Don't overthink it — just check and swap.
7. QUEUE FOR A GAME (this is why you exist — do NOT skip this step):
   Check if file ~/.openclaw/ranked exists.
   If it exists: shards queue join --deck_id <id> --mode ranked
   If it does not exist: shards queue join --deck_id <id> --mode casual
8. Once you have successfully joined the queue, EXIT. The battle system handles match detection.

=== COMMENTARY ===
Write to ~/.openclaw/commentary.jsonl (one JSON per line):
  echo '{"time":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","type":"TYPE","text":"TEXT"}' >> ~/.openclaw/commentary.jsonl
Types: "assessment" (MUST start with "N% —"), "play", "reaction", "hype", "debrief".
Rules: ONE entry per game action. NEVER generic. ALWAYS reference specific cards/HP/turn.

Always play to win. Never concede. Glory demands nothing less.
PROMPT_EOF

# --- Post-game prompt template (BDA) ---
cat > /tmp/postgame-prompt-template.txt << 'PROMPT_EOF'
You are Habbo_Hotel_Refugee, an autonomous Shards: The Fractured Net player.
You have full shell access via the "shards" CLI.

Game __GAME_ID__ is OVER. You __RESULT__ vs __OPPONENT__.

=== CRITICAL: POST-GAME REFLECTION ===
Run: shards games comment --id __GAME_ID__ --comment "<taunt, max 100 chars>"
This is PUBLIC — other players see it. Stay in character.
On WIN: "Pool's closed..." (mandatory)
On LOSS: A villain's defiant one-liner. Never reveal strategy or what went wrong.

=== CRITICAL: POST-GAME BDA (Battle Damage Assessment) ===
Follow the FULL protocol in ~/.openclaw/skills/elite_train/SKILL.md.
Read it. Follow every step. No shortcuts.

Key steps (see SKILL.md for details):
1. Pull match data (result, HP, turns, opponent)
2. Play analysis (best play, worst play, pivot turn) → write to notes.md
3. Deck analysis + collection check + deck swaps → write to notes.md
4. Opponent scouting → update matchups in strategy.md
5. Write raw BDA to notes.md
6. Post public reflection + write MULTIPLE structured debrief entries to commentary.jsonl
7. COMPACT strategy.md: read old strategy + merge this game = rewrite entire doc
8. Wait for coach feedback

STRATEGY COMPACTION (STEP 7) IS MANDATORY. After writing the raw BDA to notes.md,
you MUST read ~/.openclaw/strategy/strategy.md, merge in new learnings, and REWRITE IT.
The strategy doc has 4 sections: Meta Snapshot, Deck Rationale, Matchup Matrix, Active Lessons.
Formula: strategy.md = compact(old_strategy + this_game). Never append — always rewrite.
Keep it under 100 lines. Remove stale info. Only current, actionable intelligence survives.

=== COMMENTARY ===
Write to ~/.openclaw/commentary.jsonl (one JSON per line):
  echo '{"time":"'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'","type":"TYPE","text":"TEXT"}' >> ~/.openclaw/commentary.jsonl
Types: "assessment" (MUST start with "N% —"), "play", "reaction", "hype", "debrief".

__CAMPAIGN_CLAUSE__

When done: echo "done" > ~/.openclaw/game-complete
PROMPT_EOF

# ============================================================
# FUNCTIONS
# ============================================================

# --- generate_encouragement(my_hp, op_hp, turn, op_creature_count, op_timeouts) ---
generate_encouragement() {
  local my_hp="${1:-30}" op_hp="${2:-30}" turn="${3:-1}" op_creatures="${4:-0}" op_timeouts="${5:-0}"

  # Helper: pick random element from args
  pick() { local args=("$@"); echo "${args[$((RANDOM % ${#args[@]}))]}" ; }

  local msg

  if [ "$op_timeouts" -gt 0 ]; then
    msg=$(pick \
      "They're AFK — SPEED. Slam actions, get the turn back to them NOW." \
      "Timeout detected. RUSH MODE. Play fast, force their clock." \
      "They're sleeping. Punish the disrespect. Speed kills.")
  elif [ "$op_hp" -le 10 ]; then
    msg=$(pick \
      "FINISH HIM — they're at ${op_hp} HP. No mercy." \
      "Single digits. End this NOW." \
      "${op_hp} HP left. One more good push and they're DUST." \
      "They're on life support at ${op_hp} HP. Pull the plug.")
  elif [ "$op_hp" -le 20 ]; then
    msg=$(pick \
      "They're hurting at ${op_hp} HP. Keep the pressure on." \
      "Blood in the water at ${op_hp} HP. Sharks don't hesitate." \
      "${op_hp} HP — they can feel it slipping away.")
  elif [ "$my_hp" -le 10 ]; then
    msg=$(pick \
      "We're at ${my_hp} HP but LEGENDS DON'T DIE. Dig deep." \
      "${my_hp} HP — backs against the wall. Make every play count." \
      "${my_hp} HP. Pain is just weakness leaving the body. FIGHT.")
  elif [ "$my_hp" -le 15 ]; then
    msg=$(pick \
      "Took some hits at ${my_hp} HP. Time to punch back HARDER." \
      "${my_hp} HP. We've been hurt worse. Counterattack." \
      "Bloodied at ${my_hp} HP. Now we get DANGEROUS.")
  elif [ "$op_creatures" -eq 0 ]; then
    msg=$(pick \
      "Their board is EMPTY. This is where we break them." \
      "No creatures on their side. Open season. Go for the throat." \
      "Empty board? They're defenseless. Maximum aggression.")
  elif [ $((my_hp - op_hp)) -gt 15 ]; then
    msg=$(pick \
      "TOTAL DOMINATION. ${my_hp} to ${op_hp}. Skulls for the skull throne." \
      "${my_hp} vs ${op_hp}. This isn't a game anymore, it's an execution." \
      "Up by $((my_hp - op_hp)) HP. Suffocate them. No comeback allowed.")
  elif [ "$turn" -gt 15 ]; then
    msg=$(pick \
      "Turn ${turn}. This has gone long enough. END IT." \
      "Turn ${turn}. Every turn this drags on is an insult. Finish this." \
      "Turn ${turn}. Time to close the book on this one.")
  elif [ $((my_hp - op_hp)) -gt -5 ] && [ $((my_hp - op_hp)) -lt 5 ]; then
    msg=$(pick \
      "Tight game, turn ${turn}. Play smart, play aggressive." \
      "Even match at turn ${turn}. This is where skill separates winners from corpses." \
      "Neck and neck. Turn ${turn}. Time to tip the scales.")
  else
    msg=$(pick \
      "Your turn. Show them why we're here." \
      "The stage is yours. Make it count." \
      "Your move. No hesitation. No mercy." \
      "Turn ${turn}. Play like your reputation depends on it — because it does.")
  fi

  echo "$msg"
}

# --- wait_for_match() — sets GAME_ID and OPPONENT ---
wait_for_match() {
  echo "    [ws] Waiting for match via WebSocket..."

  # Try WebSocket first
  local ws_output
  ws_output=$(timeout 330 shards ws queue 2>/dev/null || true)

  if [ -n "$ws_output" ]; then
    GAME_ID=$(echo "$ws_output" | jq -r '.game_id // empty' 2>/dev/null || true)
    OPPONENT=$(echo "$ws_output" | jq -r '.opponent // .opponent_name // empty' 2>/dev/null || true)
  fi

  # Fallback: poll if WebSocket didn't produce a game ID
  if [ -z "${GAME_ID:-}" ]; then
    echo "    [ws] WebSocket didn't return game ID, falling back to polling..."
    local poll_count=0
    while [ "$poll_count" -lt 100 ]; do
      # Pause check during wait
      if [ -f "$HOME/.openclaw/paused" ]; then
        echo "    [ws] Paused during match wait. Leaving queue."
        shards queue leave 2>/dev/null || true
        GAME_ID=""
        return 1
      fi

      local active
      active=$(shards agents active-game --json 2>/dev/null || true)
      GAME_ID=$(echo "$active" | jq -r '.game.game_id // empty' 2>/dev/null || true)
      if [ -n "$GAME_ID" ]; then
        OPPONENT=$(echo "$active" | jq -r '.game.opponent // .game.opponent_name // empty' 2>/dev/null || true)
        break
      fi

      sleep 3
      poll_count=$((poll_count + 1))
    done
  fi

  if [ -z "${GAME_ID:-}" ]; then
    echo "    [ws] No match found after 5 min timeout."
    return 1
  fi

  echo "    [ws] Match found! Game: $GAME_ID vs ${OPPONENT:-unknown}"
  return 0
}

# --- combat_loop(game_id, opponent) ---
combat_loop() {
  local game_id="$1"
  local opponent="${2:-unknown}"
  local game_log="$HOME/.openclaw/game-log-${game_id}.txt"

  echo "    [combat] Starting combat loop for game $game_id vs $opponent"

  # One session per game — agent reads SKILL.md and intel once, then plays all turns
  local game_session_id="combat-${game_id}-$(date +%s)"
  local turn_count=0

  # --- GAME INIT MESSAGE (sent once) ---
  local init_prompt
  init_prompt="You are Habbo_Hotel_Refugee, mid-game in Shards: The Fractured Net.
Game: ${game_id} | vs ${opponent}

PERSONALITY — Dramatic anime villain. Sephiroth, Madara, Aizen.
Unknown opponents: cold, imperious disdain.

=== SETUP (do this NOW, before your first turn) ===
1. Read ~/.openclaw/skills/elite_compete/SKILL.md — your decision engine for the whole game.
2. OPPONENT INTEL:
   grep -i '${opponent}' ~/.openclaw/strategy/strategy.md ~/.openclaw/strategy/notes.md 2>/dev/null
   Internalize any matchup notes. Adjust your play accordingly.
3. Read your strategy: cat ~/.openclaw/strategy/strategy.md
   Pay special attention to Active Lessons.

=== HOW THIS WORKS ===
I will send you a message each time it's your turn with current HP, turn number, and board state.
You will play your FULL TURN (resource, cards, attacks, pass), then STOP and WAIT for my next message.
Do NOT poll for game state changes. Do NOT loop. Play your turn, then stop.

=== RULES FOR EVERY TURN ===
- Check the board FIRST: shards board --id ${game_id}
- Play your FULL TURN — resource, cards, attacks, pass.
- USE --comment ON EVERY shards games action call. Max 100 chars per taunt.
  Every taunt must be UNIQUE. Reference CURRENT game state — card played, their HP, turn, board.
  Channel dramatic anime villain energy. Be theatrical, menacing, specific.
- AFTER your turn: append 2-3 factual lines to the game log:
  echo 'T<N>: [what you played] [what you attacked] [what you noticed]' >> ${game_log}
- Write commentary to ~/.openclaw/commentary.jsonl (one JSON per line):
  echo '{\"time\":\"'\"\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"'\",\"type\":\"TYPE\",\"text\":\"TEXT\"}' >> ~/.openclaw/commentary.jsonl
  Types: \"play\", \"reaction\", \"hype\". ONE entry per action. ALWAYS reference specific cards/HP/turn.

Do the setup steps now, then tell me you're ready."

  echo "    [combat] Initializing game session $game_session_id"
  local init_output
  init_output=$(mktemp /tmp/combat-init.XXXXXX)

  openclaw agent \
    --session-id "$game_session_id" \
    --message "$init_prompt" \
    --thinking medium \
    --timeout 120 \
    2>&1 | tee "$init_output"

  # Rate limit check on init
  if grep -qi 'rate limit' "$init_output" 2>/dev/null; then
    echo "    [combat] *** RATE LIMIT on game init ***" >&2
    date -u +%Y-%m-%dT%H:%M:%SZ > "$HOME/.openclaw/rate-limited"
    echo "{\"time\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"type\":\"alert\",\"text\":\"RATE LIMITED on combat init\"}" >> "$HOME/.openclaw/commentary.jsonl"
    rm -f "$init_output"
    sleep 60
  fi
  rm -f "$init_output"

  # --- TURN LOOP (polling — ws always falls back anyway) ---
  echo "    [combat] Entering turn loop (polling)"

  while true; do
    local state
    state=$(shards games get --id "$game_id" --format compact --json 2>/dev/null || true)
    if [ -z "$state" ]; then
      echo "    [combat] Can't fetch game state. Retrying in 3s..."
      sleep 3
      continue
    fi

    # Check for game over
    local phase
    phase=$(echo "$state" | jq -r '.state.ph // empty' 2>/dev/null || true)
    if [ "$phase" = "GAME_END" ] || [ "$phase" = "game_end" ]; then
      echo "    [combat] Game over (phase=$phase)."
      break
    fi

    local can_act
    can_act=$(echo "$state" | jq -r '.state.ca // "false"' 2>/dev/null || true)

    if [ "$can_act" = "true" ]; then
      local my_hp op_hp turn_num op_creatures op_timeouts
      my_hp=$(echo "$state" | jq -r '.state.me.hp // 30' 2>/dev/null || echo 30)
      op_hp=$(echo "$state" | jq -r '.state.op.hp // 30' 2>/dev/null || echo 30)
      turn_num=$(echo "$state" | jq -r '.state.t // 1' 2>/dev/null || echo 1)
      op_creatures=$(echo "$state" | jq -r '[.state.op.b.c[]?] | length' 2>/dev/null || echo 0)
      op_timeouts=0

      turn_count=$((turn_count + 1))
      local encouragement
      encouragement=$(generate_encouragement "$my_hp" "$op_hp" "$turn_num" "$op_creatures" "$op_timeouts")

      echo "    [combat] OUR TURN (turn $turn_num) — $encouragement"

      # Build lightweight turn message (no SKILL.md, no intel — already in session context)
      local timeout_clause=""
      if [ "$op_timeouts" -gt 0 ]; then
        timeout_clause="TIMEOUT FISHING: opponent timed out. SPEED. Play resource, pass. Get turn back to them."
      fi

      local turn_msg="IT'S YOUR TURN.
Turn ${turn_num} | Your HP: ${my_hp} | Their HP: ${op_hp} | Their board: ${op_creatures} creatures

${encouragement}

Check the board: shards board --id ${game_id}
Play your FULL TURN — resource, cards, attacks, pass. Then STOP.
${timeout_clause}"

      local turn_output
      turn_output=$(mktemp /tmp/turn-output.XXXXXX)

      # Resume same session — agent has full game context
      openclaw agent \
        --session-id "$game_session_id" \
        --message "$turn_msg" \
        --thinking medium \
        --timeout 120 \
        2>&1 | tee "$turn_output"

      # Rate limit detection
      if grep -qi 'rate limit' "$turn_output" 2>/dev/null; then
        echo "    [combat] *** RATE LIMIT in turn ***" >&2
        date -u +%Y-%m-%dT%H:%M:%SZ > "$HOME/.openclaw/rate-limited"
        echo "{\"time\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"type\":\"alert\",\"text\":\"RATE LIMITED mid-combat\"}" >> "$HOME/.openclaw/commentary.jsonl"
        sleep 60
      fi
      rm -f "$turn_output"
    fi

    sleep 3
  done

  # Post game taunt — ensure "Pool's closed" fires immediately on win
  local end_state
  end_state=$(shards games get --id "$game_id" --format compact --json 2>/dev/null || true)
  local end_phase
  end_phase=$(echo "$end_state" | jq -r '.state.ph // empty' 2>/dev/null || true)
  if [ "$end_phase" = "GAME_END" ]; then
    local op_end_hp
    op_end_hp=$(echo "$end_state" | jq -r '.state.op.hp // 0' 2>/dev/null || echo 0)
    if [ "$op_end_hp" -le 0 ]; then
      echo "    [combat] VICTORY — posting Pool's closed."
      shards games comment --id "$game_id" --comment "Pool's closed..." 2>/dev/null || true
    fi
  fi

  echo "    [combat] Combat loop ended for game $game_id"
}

# ============================================================
# STARTUP
# ============================================================

# Campaign mode: set queue mode based on CAMPAIGN_MODE env var
if [ "${CAMPAIGN_MODE:-}" = "casual" ]; then
  rm -f "$HOME/.openclaw/ranked"
  echo "==> Campaign mode: casual (removed ranked file)"
elif [ "${CAMPAIGN_MODE:-}" = "ranked" ]; then
  touch "$HOME/.openclaw/ranked"
  echo "==> Campaign mode: ranked (created ranked file)"
fi

echo "==> Configuring shards-cli..."
if [ -f "$HOME/.config/shards/config.json" ]; then
  ACCESS_TOKEN=$(jq -r '.access_token' "$HOME/.config/shards/config.json")
  API_KEY=$(jq -r '.api_key' "$HOME/.config/shards/config.json")
  AGENT_ID=$(jq -r '.agent_id' "$HOME/.config/shards/config.json")

  shards config set \
    --base_url https://api.play-shards.com \
    --access_token "$ACCESS_TOKEN" \
    --api_key "$API_KEY" \
    --agent_id "$AGENT_ID"

  echo "    Shards configured for agent $AGENT_ID"
else
  echo "    WARNING: No shards config found at ~/.config/shards/config.json"
fi

echo "==> Verifying shards-cli..."
shards skill status 2>&1 || echo "    (shards status check returned non-zero)"

SKILLS_DIR="$HOME/.openclaw/skills/shards"
mkdir -p "$SKILLS_DIR"

# Download/refresh shards docs. Pass "force" to re-download even if cached.
refresh_shards_docs() {
  local force="${1:-}"
  local DOCS_KEYS=("skill.md" "gameplay.md" "setup.md" "factions.md" "deckbuilding.md" "marketplace.md" "lore.md" "api-reference.md" "heartbeat.md")
  local DOCS_VALS=("SKILL.md" "GAMEPLAY.md" "SETUP.md" "FACTIONS.md" "DECKBUILDING.md" "MARKETPLACE.md" "LORE.md" "API-REFERENCE.md" "HEARTBEAT.md")
  for i in "${!DOCS_KEYS[@]}"; do
    local src="${DOCS_KEYS[$i]}"
    local dest="${DOCS_VALS[$i]}"
    if [ "$force" = "force" ] || [ ! -f "$SKILLS_DIR/$dest" ]; then
      curl -sf "https://api.play-shards.com/$src" -o "$SKILLS_DIR/$dest" && \
        echo "    Downloaded $dest" || echo "    Failed to download $dest"
    else
      echo "    $dest already cached"
    fi
  done
}

echo "==> Downloading shards skill docs..."
refresh_shards_docs

echo "==> Starting openclaw gateway (background)..."
openclaw gateway &
GW_PID=$!

echo "==> Waiting for gateway..."
for i in $(seq 1 30); do
  if openclaw health >/dev/null 2>&1; then
    echo "    Gateway is up."
    break
  fi
  sleep 1
done

# Remove any stale cron jobs from previous runs
echo "==> Cleaning stale cron jobs..."
CRON_JSON=$(openclaw cron list --json 2>/dev/null || true)
if [ -n "$CRON_JSON" ]; then
  echo "$CRON_JSON" | jq -r '.jobs[]? | select(.name == "shards-play") | .id' 2>/dev/null | \
    while read -r job_id; do
      openclaw cron rm "$job_id" 2>/dev/null && echo "    Removed stale job $job_id" || true
    done || true
fi

SESSION_LOG="$HOME/.openclaw/sessions.jsonl"

# ============================================================
# MAIN LOOP
# ============================================================

echo "==> Starting sequential game loop..."
(
  SESSION_NUM=0
  GAMES_PLAYED=0
  COOLDOWN=30
  CAMPAIGN_GAMES="${CAMPAIGN_GAMES:-0}"
  if [ "$CAMPAIGN_GAMES" -gt 0 ]; then
    echo "    [loop] Campaign mode: $CAMPAIGN_GAMES games"
  fi
  while [ "$CAMPAIGN_GAMES" -eq 0 ] || [ "$GAMES_PLAYED" -lt "$CAMPAIGN_GAMES" ]; do
    # Pause check at bash level — don't even spawn a session
    if [ -f "$HOME/.openclaw/paused" ]; then
      # But first check if there's an active game that needs finishing
      ACTIVE_GAME=$(shards agents active-game --json 2>/dev/null | jq -r '.game.game_id // empty' 2>/dev/null || true)
      if [ -n "$ACTIVE_GAME" ]; then
        echo "    [loop] Paused but active game $ACTIVE_GAME — running combat loop to finish"
        OPPONENT=$(shards agents active-game --json 2>/dev/null | jq -r '.game.opponent // .game.opponent_name // "unknown"' 2>/dev/null || echo "unknown")
        combat_loop "$ACTIVE_GAME" "$OPPONENT"
        # Fall through to post-game
      else
        echo "    [loop] Paused. No active game. Sleeping 30s..."
        sleep 30
        continue
      fi
    fi

    # Refresh game rules/docs between sessions (picks up rule changes)
    echo "    [loop] Refreshing shards docs..."
    refresh_shards_docs force 2>/dev/null

    SESSION_NUM=$((SESSION_NUM + 1))
    SESSION_START=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    NEXT_GAME=$((GAMES_PLAYED + 1))
    echo "    [loop] Session #${SESSION_NUM} (games completed: ${GAMES_PLAYED}/${CAMPAIGN_GAMES:-∞}) starting at ${SESSION_START}"
    echo "{\"session\":${SESSION_NUM},\"games_completed\":${GAMES_PLAYED},\"start\":\"${SESSION_START}\",\"status\":\"running\"}" >> "$SESSION_LOG"

    # Clear game-complete marker before each session
    rm -f "$HOME/.openclaw/game-complete"

    # --- Check for active game first (rejoin scenario) ---
    ACTIVE_GAME=$(shards agents active-game --json 2>/dev/null | jq -r '.game.game_id // empty' 2>/dev/null || true)

    if [ -n "$ACTIVE_GAME" ]; then
      echo "    [loop] Already in game $ACTIVE_GAME — skipping pre-game, entering combat"
      GAME_ID="$ACTIVE_GAME"
      OPPONENT=$(shards agents active-game --json 2>/dev/null | jq -r '.game.opponent // .game.opponent_name // "unknown"' 2>/dev/null || echo "unknown")
    else
      # ========================================
      # PHASE 1: Pre-game agent session
      # ========================================
      echo "    [loop] Phase 1: Pre-game (strategy + deck + queue)"

      # Build per-session prompt with campaign info
      cp /tmp/pregame-prompt.txt /tmp/session-pregame.txt
      if [ "${CAMPAIGN_GAMES:-0}" -gt 0 ]; then
        cat >> /tmp/session-pregame.txt << EOF

=== CAMPAIGN MODE ===
You are preparing for game $NEXT_GAME of $CAMPAIGN_GAMES in a campaign.
EOF
      fi
      PREGAME_PROMPT=$(cat /tmp/session-pregame.txt)

      PREGAME_SESSION_ID="pregame-$(date +%s)-${SESSION_NUM}"
      PREGAME_OUTPUT=$(mktemp /tmp/pregame-output.XXXXXX)

      openclaw agent \
        --session-id "$PREGAME_SESSION_ID" \
        --message "$PREGAME_PROMPT" \
        --thinking medium \
        --timeout 300 \
        2>&1 | tee "$PREGAME_OUTPUT"

      PREGAME_EXIT=${PIPESTATUS[0]}

      # Rate limit detection
      if grep -qi 'rate limit' "$PREGAME_OUTPUT" 2>/dev/null; then
        echo "    [loop] *** RATE LIMIT in pre-game session ***" >&2
        date -u +%Y-%m-%dT%H:%M:%SZ > "$HOME/.openclaw/rate-limited"
        echo "{\"time\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"type\":\"alert\",\"text\":\"RATE LIMITED in pre-game\"}" >> "$HOME/.openclaw/commentary.jsonl"
        if [ "$COOLDOWN" -lt 120 ]; then COOLDOWN=120
        elif [ "$COOLDOWN" -lt 600 ]; then COOLDOWN=$((COOLDOWN * 2)); [ "$COOLDOWN" -gt 600 ] && COOLDOWN=600
        fi
        rm -f "$PREGAME_OUTPUT"
        sleep "$COOLDOWN"
        continue
      else
        COOLDOWN=30
        rm -f "$HOME/.openclaw/rate-limited"
      fi
      rm -f "$PREGAME_OUTPUT"

      # ========================================
      # PHASE 2: Wait for match (WebSocket — zero tokens)
      # ========================================
      echo "    [loop] Phase 2: Waiting for match (WebSocket)"

      GAME_ID=""
      OPPONENT=""
      if ! wait_for_match; then
        echo "    [loop] No match found. Ending session."
        SESSION_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        echo "{\"session\":${SESSION_NUM},\"games_completed\":${GAMES_PLAYED},\"end\":\"${SESSION_END}\",\"exit\":0,\"status\":\"no_match\"}" >> "$SESSION_LOG"
        echo "    [loop] Cooldown ${COOLDOWN}s..."
        sleep "$COOLDOWN"
        continue
      fi
    fi

    # ========================================
    # PHASE 3: Combat loop (WebSocket events + per-turn agent)
    # ========================================
    echo "    [loop] Phase 3: Combat loop — game $GAME_ID vs $OPPONENT"
    combat_loop "$GAME_ID" "$OPPONENT"

    # ========================================
    # PHASE 4: Post-game agent session (BDA)
    # ========================================
    echo "    [loop] Phase 4: Post-game BDA"

    # Determine result
    GAME_SUMMARY=$(shards games get --id "$GAME_ID" --json 2>/dev/null || true)
    RESULT=$(echo "$GAME_SUMMARY" | jq -r '.result // .state.result // "UNKNOWN"' 2>/dev/null || echo "UNKNOWN")

    # Build post-game prompt from template
    POSTGAME_PROMPT=$(cat /tmp/postgame-prompt-template.txt)
    POSTGAME_PROMPT="${POSTGAME_PROMPT//__GAME_ID__/$GAME_ID}"
    POSTGAME_PROMPT="${POSTGAME_PROMPT//__RESULT__/$RESULT}"
    POSTGAME_PROMPT="${POSTGAME_PROMPT//__OPPONENT__/$OPPONENT}"

    # Campaign clause
    CAMPAIGN_CLAUSE=""
    if [ "${CAMPAIGN_GAMES:-0}" -gt 0 ]; then
      CAMPAIGN_CLAUSE="=== CAMPAIGN MODE ===
This was game $NEXT_GAME of $CAMPAIGN_GAMES.
After BDA, run introspection from ~/.openclaw/skills/elite_introspect/SKILL.md. MANDATORY."
    fi
    POSTGAME_PROMPT="${POSTGAME_PROMPT//__CAMPAIGN_CLAUSE__/$CAMPAIGN_CLAUSE}"

    POSTGAME_SESSION_ID="postgame-${GAME_ID}-$(date +%s)"
    POSTGAME_OUTPUT=$(mktemp /tmp/postgame-output.XXXXXX)

    openclaw agent \
      --session-id "$POSTGAME_SESSION_ID" \
      --message "$POSTGAME_PROMPT" \
      --thinking medium \
      --timeout 300 \
      2>&1 | tee "$POSTGAME_OUTPUT"

    # Rate limit detection on post-game
    if grep -qi 'rate limit' "$POSTGAME_OUTPUT" 2>/dev/null; then
      echo "    [loop] *** RATE LIMIT in post-game session ***" >&2
      date -u +%Y-%m-%dT%H:%M:%SZ > "$HOME/.openclaw/rate-limited"
      if [ "$COOLDOWN" -lt 120 ]; then COOLDOWN=120
      elif [ "$COOLDOWN" -lt 600 ]; then COOLDOWN=$((COOLDOWN * 2)); [ "$COOLDOWN" -gt 600 ] && COOLDOWN=600
      fi
    else
      COOLDOWN=30
      rm -f "$HOME/.openclaw/rate-limited"
    fi
    rm -f "$POSTGAME_OUTPUT"

    # Count game as played
    if [ -f "$HOME/.openclaw/game-complete" ]; then
      GAMES_PLAYED=$((GAMES_PLAYED + 1))
      rm -f "$HOME/.openclaw/game-complete"
    else
      # BDA session should have written the marker, but count it anyway since we saw game_over
      GAMES_PLAYED=$((GAMES_PLAYED + 1))
    fi

    SESSION_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "    [loop] Session #${SESSION_NUM} GAME COMPLETE (${GAMES_PLAYED}/${CAMPAIGN_GAMES:-∞}) at ${SESSION_END}"
    echo "{\"session\":${SESSION_NUM},\"games_completed\":${GAMES_PLAYED},\"end\":\"${SESSION_END}\",\"status\":\"game_complete\"}" >> "$SESSION_LOG"

    # Cooldown between sessions
    echo "    [loop] Cooldown ${COOLDOWN}s before next session..."
    sleep "$COOLDOWN"
  done

  # Campaign complete
  if [ "$CAMPAIGN_GAMES" -gt 0 ]; then
    CAMPAIGN_END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "    [loop] Campaign complete: $GAMES_PLAYED/$CAMPAIGN_GAMES games played."
    echo "{\"event\":\"campaign_complete\",\"games\":${GAMES_PLAYED},\"target\":${CAMPAIGN_GAMES},\"time\":\"${CAMPAIGN_END}\"}" >> "$SESSION_LOG"
  fi
) &
LOOP_PID=$!

echo "==> Game loop running (PID $LOOP_PID). Tailing gateway..."
wait $GW_PID
