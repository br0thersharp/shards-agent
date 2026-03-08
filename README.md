# OpenClaw Agent Harness

An autonomous game-playing agent for [Shards: The Fractured Net](https://play-shards.com), built on top of the `openclaw` CLI and Claude. The agent queues for matches, plays full games with per-turn decision-making, conducts post-game analysis (BDA), and iterates on its own strategy document across a campaign of games.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  entrypoint.sh (bash harness)                       │
│                                                     │
│  ┌──────────┐   ┌──────────┐   ┌─────────────────┐  │
│  │ Phase 1  │──>│ Phase 2  │──>│    Phase 3      │  │
│  │ Pre-game │   │ Match    │   │  Combat Loop    │  │
│  │ (agent)  │   │ Wait     │   │  (poll + agent) │  │
│  │          │   │ (bash)   │   │                 │  │
│  │ strategy │   │ zero     │   │ bash detects    │  │
│  │ review,  │   │ tokens   │   │ turn → wakes    │  │
│  │ deck,    │   │          │   │ agent session   │  │
│  │ queue    │   │          │   │ per game        │  │
│  └──────────┘   └──────────┘   └────────┬────────┘  │
│                                         │           │
│                                  ┌──────v────────┐  │
│                                  │   Phase 4     │  │
│                                  │  Post-game    │  │
│                                  │  BDA (agent)  │  │
│                                  │               │  │
│                                  │  debrief,     │  │
│                                  │  strategy     │  │
│                                  │  compaction   │  │
│                                  └───────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Lessons Learned Building Autonomous Agents

These are hard-won insights from building, deploying, and babysitting this agent through live competitive games. Some are specific to game-playing agents; most apply to any long-running autonomous agent system.

### 1. Don't trust the interfaces your agent talks to

The agent interacts with a CLI (`shards`) that wraps a game API. We assumed the CLI was a reliable surface. It wasn't.

**The Logic Bomb incident:** The agent played a damage spell targeting `p1` (the opponent). Our safety wrapper — designed to prevent self-targeting — had hardcoded `p1 = self`. But the agent was `p2` in this game. The wrapper "corrected" the target to `p2`, and the agent nuked its own board. We won anyway (20-0), but only because the opponent was already behind.

The fix was straightforward (dynamically resolve player ID via API), but the lesson is deeper: **any interface your agent touches — APIs, CLIs, wrappers, even your own guardrails — can have assumptions that break at runtime.** Guardrails need their own guardrails. If you write a safety layer, make sure it doesn't introduce a new failure mode that's worse than the one it prevents.

Other examples we hit:
- CLI action syntax wasn't what we assumed (`--type play_card` not `--action "PC:card_50"`)
- Game state field paths differed from documentation (`.state.t` not `.state.turn`)
- The `GAME_END` phase wasn't surfaced in the status field we were checking, causing infinite post-game loops

### 2. Context windows are a resource — manage them like memory

Each agent session has a finite context window. How you allocate it determines whether the agent is sharp on turn 15 or hallucinating by turn 8.

**The timeout problem:** Our agent originally ran as a single monolithic session per game. By mid-game, the context window was packed with previous board states, action outputs, and accumulated reasoning. Turn processing slowed down. Eventually turns started timing out at the 120-second limit — the agent was spending all its time processing context instead of playing cards. Two consecutive timeouts on Turn 11 nearly cost us a game we were winning.

**Compaction isn't free either.** The agent maintains a `strategy.md` that it compacts after every game (rewriting the whole doc with new learnings merged in). This is necessary — without it, the strategy file grows unbounded and eats context in every future session. But compaction itself is expensive: the agent has to read the old strategy, reason about what's still relevant, and produce a clean rewrite. If this happens during a time-sensitive phase, it creates latency at the worst moment.

Principles that emerged:
- **Separate concerns by session.** Pre-game prep, in-game combat, and post-game analysis are different cognitive tasks with different context needs. Don't cram them into one session.
- **Design for the context budget.** If your agent reads a 200-line skill document every turn, that's 200 lines * N turns of redundant context. Read it once, keep it in session memory.
- **Scratchpads should be logs, not plans.** We give the agent a per-game log file where it records factual observations after each turn. It reads this at the start of each turn for continuity. But we deliberately made it a logbook ("what happened"), not a playbook ("what to do next"). Agents that write plans tend to feel beholden to follow them even when the board state has changed. Facts age gracefully; plans don't.

### 3. Push deterministic work out of the agent and into procedural code

This one sounds obvious. It isn't, because the boundary between "deterministic" and "requires judgment" is blurrier than you'd think.

**The token math:** Our agent was originally responsible for everything — polling for matches, detecting whose turn it was, playing cards, analyzing results. But polling a queue and checking `can_act == true` are purely mechanical operations. Every poll cycle the agent spent on these tasks cost real tokens and consumed context window space, for zero cognitive value. It's like paying a surgeon to also check the waiting room.

We moved match detection and turn detection into bash. The harness polls the game API (3-second intervals, zero tokens) and only wakes the agent when it's actually time to make a decision. This cut per-game token usage significantly and eliminated the "agent wasting a turn re-reading the board to figure out if it's even its turn" problem.

**Is this conventional wisdom?** In the function-calling / tool-use paradigm, the default assumption is that the agent drives everything — it decides when to call tools, it loops on results, it manages its own control flow. And for genuinely judgment-heavy loops, that's correct. But there's a large class of operations (polling, retrying, waiting, parsing structured data, validating outputs) where the agent adds no value over a bash `while` loop or a Python script. The wisdom isn't "never let the agent loop" — it's **"don't spend intelligence on tasks that don't require intelligence."**

Where we draw the line:
- **Bash does:** match detection, turn detection, game-over detection, encouragement phrase selection, rate limit backoff, pause/unpause, session lifecycle
- **Agent does:** board evaluation, card sequencing, attack/block decisions, taunting, post-game analysis, strategy evolution

The rule of thumb: if you can write the logic as an `if/else` in bash without losing decision quality, it shouldn't be in the agent's context window.

### 4. Agents learn — but only from what you give them feedback loops for

The agent has a post-game Battle Damage Assessment (BDA) protocol. After every game it reviews its plays, identifies the best and worst decisions, scouts the opponent's strategy, and rewrites its strategy document. This works. Over a campaign, the strategy doc evolves — matchup-specific plans get refined, bad habits get identified, deck composition changes based on card performance data.

But the agent can only improve on things it can observe. Two blind spots we found:

- **Execution speed:** The agent had no idea it was timing out. From its perspective, the session just... ended. No error, no feedback. The harness killed it at 120s and spawned a new session. The agent couldn't learn "I need to play faster" because it never knew it was slow. Lesson: **if there's a failure mode outside the agent's observation window, the agent can't self-correct on it.** You need external monitoring or explicit feedback injection.

- **Cross-game behavioral patterns:** The agent would repeatedly play passively in winning positions — developing threats but not attacking, holding removal "just in case." The BDA would note the best and worst plays, but never identified the systemic pattern because each game was analyzed in isolation. We had to inject an Active Lesson manually ("if you have board advantage, ATTACK EVERY TURN"). Lesson: **per-instance analysis misses per-pattern problems.** If your agent's self-improvement loop operates at the wrong granularity, some failure modes will persist indefinitely.

### 5. The harness is as important as the agent

We spent more time debugging and improving `entrypoint.sh` (the bash harness) and `shards-wrapper.sh` (the CLI safety layer) than we did on the agent's prompts or strategy documents. The harness handles:

- Session lifecycle (which sessions to create, when, with what context)
- Failure recovery (timeouts, rate limits, WebSocket drops, stale game state)
- Safety rails (self-targeting prevention, empty-block detection, pass validation)
- Observability (commentary feed, game scratchpad, session logs)
- Operational control (pause/unpause, campaign counting, cooldown backoff)

None of this is "AI." It's bash scripts, jq parsing, and polling loops. But without it, the agent would self-target its own creatures, timeout on easy turns, spin in infinite loops after game-over, and burn tokens polling for matches. **The scaffolding around an agent determines its ceiling more than the agent's raw capability.**

### 6. Design for human takeover

No matter how good your agent gets, there will be moments where you need to grab the wheel. We built the system with a pause file (`~/.openclaw/paused`) and the ability to kill agent processes and play manually through the CLI. We used this multiple times — against a top-ranked player, and when the agent was losing a game we couldn't afford to drop.

Design implications:
- Make it easy to quiesce the agent without losing game state
- Ensure the CLI/API the agent uses is also usable by humans
- Keep game state in files/APIs that are inspectable from outside the agent
- Log everything — you need to diagnose "what happened on turn 7" after the fact

## Setup

### Prerequisites

- Docker and Docker Compose
- A [Shards: The Fractured Net](https://play-shards.com) agent account
- An [OpenClaw](https://openclaw.dev) installation with OAuth configured

### 1. Shards credentials

Register an agent on the Shards platform. You'll receive three values:

| Key | Description |
|-----|-------------|
| `access_token` | OAuth bearer token for the Shards API |
| `api_key` | Agent API key (identifies your agent to the game server) |
| `agent_id` | Your agent's unique ID on the platform |

Create the config file on your host machine:

```bash
mkdir -p ~/ocbox/shards-config

cat > ~/ocbox/shards-config/config.json << 'EOF'
{
  "access_token": "<your-access-token>",
  "api_key": "<your-api-key>",
  "agent_id": "<your-agent-id>"
}
EOF
```

At container startup, `entrypoint.sh` reads this file and calls `shards config set` to configure the CLI inside the container. The config file is mounted read-write at `/home/node/.config/shards/` via Docker volumes — no credentials are baked into the image.

### 2. OpenClaw (LLM gateway)

The agent runs on [OpenClaw](https://openclaw.dev), which provides the `openclaw` CLI and gateway process. OpenClaw handles LLM authentication, session management, and tool execution.

You have two options for the LLM backend:

#### Option A: Cloud LLM (OpenAI Codex — default)

Uses OpenAI's Codex API via OAuth. Smarter model, but requires an OpenAI account and is subject to rate limits.

```bash
mkdir -p ~/ocbox/openclaw-state

# Run openclaw login interactively to complete the OAuth flow.
openclaw login --provider openai-codex
```

The OAuth flow will open a browser window. After authenticating, OpenClaw writes the session config to `openclaw.json`. The relevant auth block looks like:

```json
{
  "auth": {
    "profiles": {
      "openai-codex:default": {
        "provider": "openai-codex",
        "mode": "oauth"
      }
    }
  }
}
```

#### Option B: Local LLM (Ollama)

Runs a model on your own machine. No API keys, no rate limits, no cost. Requires a machine with enough RAM (16-24GB recommended).

**Install Ollama:**

```bash
# macOS
brew install ollama
brew services start ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh
```

**Pull a model:**

```bash
# Recommended for 24GB RAM (M2/M3 Mac or similar)
ollama pull qwen2.5:14b

# Lighter option for 16GB RAM
ollama pull qwen2.5:7b

# Heavier option for 32GB+ RAM (slower but smarter)
ollama pull qwen2.5:32b
```

Verify it's running: `curl -s http://localhost:11434/api/tags | jq '.models[].name'`

No `openclaw.json` auth setup is needed for Ollama — the entrypoint configures it automatically.

---

The `openclaw.json` (and related state) lives in `~/ocbox/openclaw-state/`, which is mounted into the agent container at `/home/node/.openclaw/`.

### 3. Local directory structure

Before running, your host machine needs these directories:

```
~/ocbox/
├── shards-config/
│   └── config.json          # Shards API credentials (step 1)
└── openclaw-state/
    ├── openclaw.json         # OpenClaw auth + config (step 2)
    └── strategy/
        ├── strategy.md       # Agent strategy doc (created automatically)
        └── notes.md          # BDA journal (created automatically)
```

The `strategy/` directory and its contents are created by the agent on first run. Everything else must exist before `docker compose up`.

### 4. Build and run

```bash
# Cloud mode (default — uses OpenAI Codex, requires OAuth setup)
docker compose up --build -d

# Local mode (uses Ollama on your machine — no API keys needed)
LLM_PROVIDER=ollama docker compose up --build -d

# With a specific model
LLM_PROVIDER=ollama OLLAMA_MODEL=qwen2.5:32b docker compose up --build -d

# Watch agent logs
docker logs -f oc-agent

# Dashboard available at http://localhost:3000
```

### 5. Configuration

All settings can be passed as environment variables to `docker compose up`:

```bash
# Example: local LLM, 5-game ranked campaign
LLM_PROVIDER=ollama CAMPAIGN_GAMES=5 CAMPAIGN_MODE=ranked docker compose up --build -d
```

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_PROVIDER` | `openai-codex` | `openai-codex` (cloud) or `ollama` (local) |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Ollama model name (only used when `LLM_PROVIDER=ollama`) |
| `OLLAMA_HOST` | `http://host.docker.internal:11434` | Ollama API URL (change if running on a remote machine) |
| `CAMPAIGN_GAMES` | `10` | Number of games per campaign (`0` = infinite) |
| `AGENT_STATE` | `paused` | Initial agent state: `paused`, `campaign`, `challengers`, `single` |
| `QUEUE_MODE` | `casual` | `casual` or `ranked` |

### Operations

```bash
# Agent states (default is paused)
echo "paused" > ~/ocbox/openclaw-state/agent-state       # Do nothing
echo "campaign" > ~/ocbox/openclaw-state/agent-state     # Loop games
echo "challengers" > ~/ocbox/openclaw-state/agent-state  # Accept incoming challenges only
echo "single" > ~/ocbox/openclaw-state/agent-state       # Play one game, then pause

# Queue mode
echo "ranked" > ~/ocbox/openclaw-state/queue-mode
echo "casual" > ~/ocbox/openclaw-state/queue-mode

# Rebuild after code changes
docker compose up --build -d agent

# Rebuild dashboard only
docker compose up --build -d dashboard
```

---

## Project Structure

```
entrypoint.sh          — Main harness (phases, combat loop, encouragement)
shards-wrapper.sh      — CLI safety layer (self-target, empty-block, pass validation)
Dockerfile             — Agent container build
docker-compose.yml     — Agent + dashboard services
dashboard/server.js    — Express API (status, match, coach chat, state control)
dashboard/public/      — SPA dashboard
skills/                — Agent skill documents (read-only, mounted into container)
skills/dossiers/       — Per-player opponent intelligence files
training/                 — LLM benchmark, trainer, and game replay tools
```

## State (shared volume)

```
~/ocbox/openclaw-state/
  strategy/strategy.md   — Compacted strategy (rewritten after every game)
  sessions.jsonl         — Session loop events
  agent-state            — Agent mode: paused|campaign|challengers|single
  queue-mode             — Queue type: casual|ranked
  rate-limited           — Rate limit marker (timestamp)
  game-complete          — Per-game completion signal
  coach-msg.txt          — Coach message for agent (per-game, wiped on game end)
  coach-reply.txt        — Agent reply to coach (per-game, wiped on game end)
  coach-history.jsonl    — Coach chat history (per-game, wiped on game end)
```

## Opponent Dossier System

Per-player intelligence files in `skills/dossiers/players/`. Each file tracks:
- Confirmed deck lists (card IDs, costs, stats)
- Playstyle analysis and win conditions
- Specific counter-strategies
- Match history with HHR

The dossier index (`skills/dossiers/DOSSIERS.md`) has faction-level intel.
When a game starts, the harness loads the opponent's dossier (if one exists) into
the agent's session context.

## LLM Trainer

The test harness (`training/`) includes tools for offline evaluation and iterative
skill-doc refinement:

- **`training/llm-benchmark.py`** — Replays board state snapshots and grades LLM
  decisions against expert rubrics (resource play, creature deployment, removal
  targeting, attack declarations).
- **`training/train-from-game.py`** — Turnkey trainer. Point it at any game ID:
  1. Fetches the full replay via `shards` CLI
  2. Uses LLM introspection to identify suboptimal turns
  3. Generates board snapshots for those turns
  4. Iteratively patches the system prompt with behavioral doctrines
  5. Converges on >= 85% optimal play or fails out with a report
  6. Cuts a git branch with the refined prompt and training log

```bash
# Train from a specific game
python3 training/train-from-game.py --game-id <id> --provider ollama --model qwen2.5:14b

# Skip git branch (dry run)
python3 training/train-from-game.py --game-id <id> --no-git --verbose
```
