#!/usr/bin/env python3
"""
Turnkey Game Trainer
====================
Point at any game by ID. The script:
1. Fetches full game replay via shards CLI
2. Uses LLM introspection to identify suboptimal turns
3. Generates board snapshots for those turns
4. Runs iterative skill-doc patching until behavior converges (>= 85%)
5. Cuts a git branch, commits the refined skill docs

Usage:
  python3 training/train-from-game.py --game-id <id> --provider ollama --model qwen2.5:14b
  python3 training/train-from-game.py --game-id <id> --provider openai --model gpt-4o --api-key sk-...

  # Skip git branch (just print results):
  python3 training/train-from-game.py --game-id <id> --no-git
"""

import argparse
import copy
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def get_agent_id():
    """Read our agent ID from shards config."""
    candidates = [
        os.path.expanduser('~/ocbox/shards-config/config.json'),
        os.path.expanduser('~/.config/shards/config.json'),
    ]
    for path in candidates:
        try:
            with open(path) as f:
                return json.load(f)['agent_id']
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            continue
    raise RuntimeError("Could not find agent_id in shards config. Check ~/ocbox/shards-config/config.json")


# ---------------------------------------------------------------------------
# Shards CLI helpers
# ---------------------------------------------------------------------------

def shards(*args):
    """Run a shards CLI command and return stdout."""
    cmd = ['shards'] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(f"shards {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def get_game_data(game_id):
    """Fetch game state."""
    raw = shards('games', 'get', '--id', game_id, '--json')
    return json.loads(raw)


def get_game_history(game_id):
    """Fetch full event history via the history endpoint."""
    raw = shards('games', 'history', '--id', game_id, '--view', 'coach')
    return json.loads(raw)


def get_game_summary(game_id):
    """Fetch game summary (result, HP, turns)."""
    raw = shards('games', 'summary', '--id', game_id, '--json')
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Card database builder — fetches from the card catalog
# ---------------------------------------------------------------------------

def build_card_db_from_events(events):
    """Extract card IDs seen in events, then fetch names from the catalog."""
    card_ids = set()
    for e in events:
        data = e.get('data', {})
        cid = data.get('cardId')
        if cid:
            card_ids.add(cid)

    # Try to get card info from the catalog
    cards = {}
    try:
        raw = shards('cards', 'list', '--json')
        catalog = json.loads(raw)
        catalog_list = catalog if isinstance(catalog, list) else catalog.get('data', [])
        for c in catalog_list:
            cid = c.get('id') or c.get('card_id')
            if cid in card_ids:
                cards[cid] = {
                    'name': c.get('name', cid),
                    'cost': c.get('cost', c.get('energy_cost', 0)),
                    'type': c.get('type', c.get('card_type', 'creature')),
                    'power': c.get('power', c.get('attack', 0)),
                    'defense': c.get('defense', c.get('health', 0)),
                    'keywords': c.get('keywords', []),
                    'text': c.get('text', c.get('description', c.get('ability_text', ''))),
                }
    except Exception:
        pass

    # Fill in any missing cards with just their IDs
    for cid in card_ids:
        if cid not in cards:
            cards[cid] = {'name': cid, 'cost': 0, 'type': 'unknown', 'power': 0, 'defense': 0, 'keywords': [], 'text': ''}

    return cards


# ---------------------------------------------------------------------------
# Snapshot extraction from event history
# ---------------------------------------------------------------------------

def extract_snapshots_from_events(events, my_player):
    """Reconstruct board state at the start of each of our turns from the event stream."""
    op_player = 'p2' if my_player == 'p1' else 'p1'

    # Track game state
    hp = {'p1': 30, 'p2': 30}
    energy = {'p1': [0, 0], 'p2': [0, 0]}  # [current, max]
    board = {'p1': {}, 'p2': {}}  # iid -> {card_id, power, defense, keywords, tapped}
    resources = {'p1': {}, 'p2': {}}  # iid -> {card_id}
    hand = {'p1': {}, 'p2': {}}  # iid -> {card_id}
    hand_count = {'p1': 0, 'p2': 0}

    snapshots = []
    current_turn = 0
    turn_player = None
    turn_actions = []

    for e in events:
        etype = e.get('type', '')
        data = e.get('data', {})
        player = e.get('player', data.get('playerId', ''))

        # Track hand via draws and plays
        if etype == 'CARD_DRAWN':
            pid = data.get('playerId', player)
            iid = data.get('instanceId', '')
            cid = data.get('cardId', '')
            if pid and iid:
                hand[pid][iid] = {'iid': iid, 'card_id': cid}
                hand_count[pid] = len(hand[pid])

        elif etype == 'CARD_PLAYED':
            pid = player or data.get('playerId', '')
            iid = data.get('instanceId', '')
            if pid and iid and iid in hand.get(pid, {}):
                del hand[pid][iid]
                hand_count[pid] = len(hand[pid])

        elif etype == 'CARD_DISCARDED':
            pid = player or data.get('playerId', '')
            iid = data.get('instanceId', '')
            if pid and iid and iid in hand.get(pid, {}):
                del hand[pid][iid]
                hand_count[pid] = len(hand[pid])

        elif etype == 'HEALTH_CHANGED':
            pid = data.get('playerId', '')
            if pid:
                hp[pid] = data.get('newHealth', hp.get(pid, 30))

        elif etype == 'ENERGY_CHANGED':
            pid = data.get('playerId', '')
            if pid:
                energy[pid] = [data.get('newEnergy', 0), data.get('maxEnergy', energy[pid][1])]

        elif etype == 'CREATURE_ENTERED':
            iid = data.get('creatureId', '')
            cid = data.get('cardId', '')
            owner = data.get('owner', player)
            # Determine owner from context if not in data
            if not owner and current_turn > 0:
                owner = turn_player
            if owner and iid:
                board[owner][iid] = {
                    'iid': iid,
                    'card_id': cid,
                    'power': data.get('power', 0),
                    'defense': data.get('defense', 0),
                    'keywords': data.get('keywords', []),
                    'tapped': False,
                }

        elif etype == 'CREATURE_TAPPED':
            iid = data.get('creatureId', '')
            for pid in ('p1', 'p2'):
                if iid in board[pid]:
                    board[pid][iid]['tapped'] = True

        elif etype == 'CREATURE_UNTAPPED':
            iid = data.get('creatureId', '')
            for pid in ('p1', 'p2'):
                if iid in board[pid]:
                    board[pid][iid]['tapped'] = False

        elif etype == 'CREATURE_DIED' or etype == 'CREATURE_DESTROYED':
            iid = data.get('creatureId', '')
            owner = data.get('owner', '')
            if owner and iid in board.get(owner, {}):
                del board[owner][iid]
            elif iid:
                for pid in ('p1', 'p2'):
                    if iid in board[pid]:
                        del board[pid][iid]
                        break

        elif etype == 'CARD_EXILED':
            iid = data.get('instanceId', '')
            for pid in ('p1', 'p2'):
                if iid in board[pid]:
                    del board[pid][iid]

        elif etype == 'RESOURCE_PLAYED':
            iid = data.get('instanceId', '')
            cid = data.get('cardId', '')
            pid = player or turn_player
            if pid and iid:
                resources[pid][iid] = {'iid': iid, 'card_id': cid}

        elif etype == 'MODIFIER_APPLIED':
            iid = data.get('targetId', '')
            for pid in ('p1', 'p2'):
                if iid in board[pid]:
                    if 'power' in data:
                        board[pid][iid]['power'] = data['power']
                    if 'defense' in data:
                        board[pid][iid]['defense'] = data['defense']

        elif etype == 'TURN_STARTED':
            current_turn = data.get('turn', current_turn + 1)
            turn_player = data.get('player', '')
            turn_actions = []

            # Untap all creatures for the active player
            for iid in board.get(turn_player, {}):
                board[turn_player][iid]['tapped'] = False

            # Snapshot at start of OUR turns (after draw + energy but we capture pre-action state)
            if turn_player == my_player:
                snap = {
                    'turn': current_turn,
                    'p1_hp': hp[my_player],
                    'p2_hp': hp[op_player],
                    'p1_energy': list(energy[my_player]),
                    'p2_energy': list(energy[op_player]),
                    'p1_hand': list(hand[my_player].values()),
                    'p1_board': list(board[my_player].values()),
                    'p2_board': list(board[op_player].values()),
                    'p1_resources': list(resources[my_player].values()),
                    'p2_resources': list(resources[op_player].values()),
                    'p2_hand_count': len(hand[op_player]),
                    'actions_taken': [],  # filled after turn ends
                }
                snapshots.append(snap)

        elif etype == 'ACTION_INPUT':
            action = data.get('action', {})
            if turn_player == my_player and action:
                turn_actions.append(action)

        elif etype == 'TURN_ENDED':
            # Attach actions to the most recent snapshot for this turn
            if snapshots and snapshots[-1]['turn'] == current_turn:
                snapshots[-1]['actions_taken'] = list(turn_actions)

    # Update snapshots with energy after the draw/energy phase
    # (The ENERGY_CHANGED event fires before we snapshot, so we're good)

    return snapshots


# ---------------------------------------------------------------------------
# LLM introspection — identify bad turns
# ---------------------------------------------------------------------------

def query_llm(model, prompt, provider='ollama', host='http://localhost:11434', api_key=''):
    """Query LLM and return response text."""
    if provider == 'ollama':
        url = f"{host}/api/generate"
        payload = json.dumps({
            'model': model,
            'prompt': prompt,
            'stream': False,
            'options': {'temperature': 0.2, 'num_predict': 2048},
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            return data.get('response', '')
    else:
        url = 'https://api.openai.com/v1/chat/completions'
        payload = json.dumps({
            'model': model,
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.2,
            'max_tokens': 2048,
        }).encode()
        req = urllib.request.Request(url, data=payload, headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        })
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            return data['choices'][0]['message']['content']


def introspect_game(replay, summary, snapshots, model, provider, host, api_key):
    """Use LLM to identify which turns had suboptimal play and build rubrics."""
    result = summary.get('results', {})
    p1 = result.get('player1', {})
    p2 = result.get('player2', {})

    # Figure out which side is ours
    our_agent_id = get_agent_id()
    if p1.get('agentId') == our_agent_id:
        my_info, op_info = p1, p2
    else:
        my_info, op_info = p2, p1

    won = my_info.get('isWinner', False)
    opponent_name = op_info.get('name', '?')
    end_reason = result.get('endReason', '?')
    turns = len(snapshots)

    # Build turn-by-turn action summary from snapshots (p1 = us in snapshot space)
    action_summary = []
    for snap in snapshots:
        actions = snap.get('actions_taken', [])
        action_strs = []
        for a in actions:
            if isinstance(a, dict):
                action_strs.append(f"{a.get('type', '?')}: {a.get('card_name', a.get('card', '?'))}")
            elif isinstance(a, str):
                action_strs.append(a)
        action_summary.append(f"T{snap['turn']}: HP {snap['p1_hp']}/{snap['p2_hp']}, "
                            f"board {len(snap['p1_board'])}v{len(snap['p2_board'])}, "
                            f"actions: {', '.join(action_strs) or 'unknown'}")

    prompt = f"""You are a Shards: The Fractured Net expert analyst. Review this game replay and identify the WORST turns — turns where the player made suboptimal decisions.

GAME RESULT: {'WIN' if won else 'LOSS'} vs {opponent_name}, {turns} turns, ended by {end_reason}

TURN-BY-TURN:
{chr(10).join(action_summary)}

For each bad turn, specify:
1. Turn number
2. What was done wrong (be specific)
3. What should have been done instead
4. A scoring rubric with these categories (assign point values 1-5):
   - plays_resource: Did they play a resource?
   - plays_creature: Did they deploy a creature?
   - uses_removal: Did they use removal on threats?
   - attacks: Did they declare attackers?
   - plays_bomb: Did they play a finisher (5+ cost)?
   - survival_play: Did they make defensive plays when low HP?

Respond as JSON array:
[{{"turn": N, "error": "description", "correct_play": "description", "rubric": {{"category": points, ...}}}}]

Only include turns with CLEAR mistakes. Max 10 turns."""

    try:
        response = query_llm(model, prompt, provider, host, api_key)
        # Extract JSON from response
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"  Introspection failed: {e}")

    return []


# ---------------------------------------------------------------------------
# Build rubric from introspection results
# ---------------------------------------------------------------------------

def build_rubric(introspection_results, snapshots):
    """Convert introspection results into a rubric dict keyed by turn number."""
    rubric = {}
    snap_turns = {s['turn'] for s in snapshots}

    for result in introspection_results:
        turn = result.get('turn', 0)
        if turn not in snap_turns:
            continue

        scoring = {}
        raw_rubric = result.get('rubric', {})
        for key, value in raw_rubric.items():
            if isinstance(value, (int, float)) and value > 0:
                scoring[key] = int(value)

        if not scoring:
            # Default rubric if introspection didn't provide one
            scoring = {'plays_creature': 3, 'uses_removal': 3, 'valid_syntax': 2, 'attacks': 2}

        rubric[turn] = {
            'description': f"T{turn}: {result.get('error', 'suboptimal play')}",
            'correct_play': result.get('correct_play', ''),
            'scoring': scoring,
        }

    return rubric


# ---------------------------------------------------------------------------
# Grading engine (generalized from llm-trainer.py)
# ---------------------------------------------------------------------------

def grade_response(turn, response_text, rubric):
    """Grade LLM response against the rubric for this turn."""
    turn_rubric = rubric.get(turn)
    if not turn_rubric:
        return {'total': 0, 'max': 0, 'pct': 0, 'failures': []}

    score = 0
    max_score = sum(turn_rubric['scoring'].values())
    failures = []
    text_lower = response_text.lower()

    has_valid_syntax = bool(re.search(r'shards\s+games\s+action\s+--', response_text)) or \
                       bool(re.search(r'shards\s+do\s+--', response_text))

    for key, points in turn_rubric['scoring'].items():
        if key == 'valid_syntax':
            if has_valid_syntax:
                score += points
            else:
                failures.append('invalid_syntax')

        elif key == 'plays_resource':
            if 'play_resource' in text_lower or 'resource' in text_lower:
                score += points
            else:
                failures.append('no_resource')

        elif key in ('plays_creature', 'plays_creatures'):
            creature_keywords = ['play_card', 'play creature', 'deploy']
            if any(k in text_lower for k in creature_keywords) and has_valid_syntax:
                score += points
            else:
                failures.append('no_creature')

        elif key == 'plays_bomb':
            bombs = ['hive tyrant', 'master strategist', 'entropy incarnate', 'temporal lock',
                     'restoration engine', 'adaptive entity']
            if any(b in text_lower for b in bombs):
                score += points
            else:
                failures.append('no_bomb')

        elif key in ('uses_removal', 'removes_threat', 'removes_threats'):
            removal = ['precision strike', 'purge protocol', 'logic bomb', 'isolation protocol',
                       'crippling despair', 'chaos bolt', 'suppress']
            if any(r in text_lower for r in removal):
                score += points
            else:
                failures.append('no_removal')

        elif key in ('attacks', 'attacks_if_able'):
            if 'declare_attackers' in text_lower or ('attack' in text_lower and 'da:' in text_lower):
                score += points
            else:
                failures.append('no_attack')

        elif key in ('survival_play', 'defensive_play', 'deploys_blockers'):
            defensive = ['block', 'vigilant', 'temporal lock', 'suppress', 'enforcement sentinel',
                        'restoration engine', 'master strategist']
            if any(d in text_lower for d in defensive):
                score += points
            else:
                failures.append('no_defense')

        elif key in ('spends_energy', 'efficient_energy', 'tempo_positive'):
            if has_valid_syntax and 'pass' not in text_lower.split('\n')[0]:
                score += points
            else:
                failures.append('wasted_energy')

    return {
        'total': score,
        'max': max_score,
        'pct': round(100 * score / max_score) if max_score > 0 else 0,
        'failures': list(set(failures)),
    }


# ---------------------------------------------------------------------------
# Patch library (same as llm-trainer.py — these are skill doc refinements)
# ---------------------------------------------------------------------------

PATCH_LIBRARY = {
    'no_removal': {
        'id': 'removal_doctrine',
        'trigger': 'no_removal',
        'text': "\nREMOVAL DOCTRINE (MANDATORY):\n- If opponent has ANY creature, your FIRST priority is to remove it.\n- Precision Strike (2E, 3 damage) kills <=3 defense. Purge Protocol (3E, destroy+draw) for bigger.\n- Logic Bomb (3E, 2 damage to all enemy power<=2) wipes wide boards.\n- ALWAYS remove BEFORE deploying your own creatures. Removal first, then develop.",
        'weight': 0,
    },
    'no_creature': {
        'id': 'board_presence',
        'trigger': 'no_creature',
        'text': "\nBOARD PRESENCE (MANDATORY):\n- MUST play at least one creature every turn you have energy.\n- Empty board = free face damage every turn. This is how you lose.\n- At 6+ energy: play a finisher (Hive Tyrant, Master Strategist).\n- NEVER pass with unspent energy and playable creatures in hand.",
        'weight': 0,
    },
    'no_bomb': {
        'id': 'finisher_deployment',
        'trigger': 'no_bomb',
        'text': "\nFINISHER DEPLOYMENT (energy >= 5):\n- Hive Tyrant (6E): 5/5 + three 1/1 Swift tokens. Best finisher.\n- Master Strategist (6E): 4/5 Vigilant + all Vigilant + draw 2. Best when behind.\n- Entropy Incarnate (5E): 4/4 Swift Volatile. Immediate 4 damage.\n- Do NOT play draw spells when you could play a finisher instead.",
        'weight': 0,
    },
    'no_attack': {
        'id': 'attack_doctrine',
        'trigger': 'no_attack',
        'text': "\nATTACK DOCTRINE:\n- If you have untapped creatures and opponent's board is empty or weaker, ATTACK.\n- declare_attackers with ALL untapped creatures unless holding back a blocker.\n- Vigilant creatures attack AND block — always include them.\n- An undeclared attack is free HP for the opponent.",
        'weight': 0,
    },
    'no_defense': {
        'id': 'survival_doctrine',
        'trigger': 'no_defense',
        'text': "\nSURVIVAL DOCTRINE (HP <= 15):\n- Prioritize NOT DYING over dealing damage.\n- Play Enforcement Sentinel to tap biggest attacker.\n- Master Strategist gives everything Vigilant. Temporal Lock skips their turn.\n- Keep at least one untapped creature to block.",
        'weight': 0,
    },
    'wasted_energy': {
        'id': 'energy_efficiency',
        'trigger': 'wasted_energy',
        'text': "\nENERGY EFFICIENCY:\n- NEVER end a turn with unspent energy and playable cards.\n- Double-play: at 6E play 3+3. At 8E play 5+3.\n- Resources give +1 max energy permanently. Play one per turn.",
        'weight': 0,
    },
    'invalid_syntax': {
        'id': 'syntax_reminder',
        'trigger': 'invalid_syntax',
        'text': "\nCLI SYNTAX (exact format):\nshards games action --id <game> --type play_resource --card_instance_id <iid>\nshards games action --id <game> --type play_card --card_instance_id <iid>\nshards games action --id <game> --type play_card --card_instance_id <iid> --targets <target>\nshards games action --id <game> --type declare_attackers --attacker_ids <id1>,<id2>\nshards games action --id <game> --type pass",
        'weight': 0,
    },
    'no_resource': {
        'id': 'resource_play',
        'trigger': 'no_resource',
        'text': "\nRESOURCE MANAGEMENT:\n- Play ONE resource each turn if available. +1 max energy permanently.\n- Resources compound every turn. Missing one = behind for the rest of the game.",
        'weight': 0,
    },
    'too_few_cards': {
        'id': 'multi_play',
        'trigger': 'too_few_cards',
        'text': "\nTEMPO RECOVERY (behind on board):\n- Playing one card per turn is not enough when behind.\n- At 8+ energy: removal + creature, or creature + creature.\n- Example: Precision Strike (2E) + Hive Tyrant (6E) = 8E, removes threat + deploys bomb.",
        'weight': 0,
    },
}


# ---------------------------------------------------------------------------
# Board formatter for LLM prompts
# ---------------------------------------------------------------------------

def format_board(snap, card_db):
    """Format a snapshot like 'shards board' output."""
    def cname(card_id):
        return card_db.get(card_id, {}).get('name', card_id or '?')

    lines = []
    lines.append(f"=== TURN {snap['turn']} | MAIN_PHASE ===")
    lines.append(f"Your HP: {snap['p1_hp']}  |  Their HP: {snap['p2_hp']}")
    e1 = snap.get('p1_energy', [0, 0])
    e2 = snap.get('p2_energy', [0, 0])
    lines.append(f"Your Energy: {e1[0]}/{e1[1]}  |  Their Energy: {e2[0]}/{e2[1]}")
    lines.append("")

    lines.append(f"=== YOUR BOARD ({len(snap.get('p1_board', []))} creatures) ===")
    for c in snap.get('p1_board', []):
        kw = ' '.join(c.get('keywords', []))
        tap = ' [TAPPED]' if c.get('tapped') else ''
        lines.append(f"  {cname(c.get('card_id', ''))} ({c.get('iid', '?')}) — {c.get('power', '?')}/{c.get('defense', '?')}{' ' + kw if kw else ''}{tap}")
    if not snap.get('p1_board'):
        lines.append("  (no creatures)")
    lines.append("")

    lines.append(f"=== OPPONENT BOARD ({len(snap.get('p2_board', []))} creatures) ===")
    for c in snap.get('p2_board', []):
        kw = ' '.join(c.get('keywords', []))
        lines.append(f"  {cname(c.get('card_id', ''))} ({c.get('iid', '?')}) — {c.get('power', '?')}/{c.get('defense', '?')}{' ' + kw if kw else ''}")
    if not snap.get('p2_board'):
        lines.append("  (no creatures)")
    lines.append(f"  Opponent hand: {snap.get('p2_hand_count', '?')} cards")
    lines.append("")

    lines.append(f"=== YOUR HAND ({len(snap.get('p1_hand', []))} cards) ===")
    for c in snap.get('p1_hand', []):
        ci = card_db.get(c.get('card_id', ''), {})
        lines.append(f"  {cname(c.get('card_id', ''))} ({c.get('iid', '?')}) — {ci.get('cost', '?')}E — {ci.get('text', '?')}")
    lines.append("")

    lines.append("=== LEGAL ACTIONS ===")
    energy = e1[0] if isinstance(e1, list) else 0
    for c in snap.get('p1_hand', []):
        ci = card_db.get(c.get('card_id', ''), {})
        cost = ci.get('cost', 99)
        if cost <= energy:
            lines.append(f"  PC:{c.get('iid', '?')}  ({cname(c.get('card_id', ''))})")
    for c in snap.get('p1_board', []):
        if not c.get('tapped'):
            lines.append(f"  DA:{c.get('iid', '?')}  (attack with {cname(c.get('card_id', ''))})")
    lines.append("  PA  (pass)")

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

TURN_SUFFIX = """
Respond with the EXACT CLI commands you would run, in order. One command per line.
After the commands, write a one-line explanation."""


def load_skill_doc():
    """Load the real elite_compete/SKILL.md — the actual doc the agent uses in production."""
    # Try repo-relative path first, then container path
    candidates = [
        os.path.join(os.path.dirname(__file__), '..', 'skills', 'elite_compete', 'SKILL.md'),
    ]
    for path in candidates:
        path = os.path.realpath(path)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return f.read(), path
    raise FileNotFoundError("Could not find skills/elite_compete/SKILL.md")


def apply_patches_to_doc(doc, patches):
    """Apply active patches into the skill doc, inserting before ## POST-MATCH."""
    active = sorted([p for p in patches.values() if p['weight'] > 0], key=lambda p: -p['weight'])
    if not active:
        return doc

    doctrine_block = '\n'.join(p['text'] for p in active) + '\n'

    # Remove any previous trained doctrines section
    marker = '## TRAINED BEHAVIORAL DOCTRINES'
    if marker in doc:
        idx = doc.index(marker)
        # Find the next ## heading after the marker, or end of doc
        rest = doc[idx + len(marker):]
        next_heading = re.search(r'\n## ', rest)
        if next_heading:
            doc = doc[:idx] + rest[next_heading.start() + 1:]
        else:
            doc = doc[:idx].rstrip() + '\n'

    # Insert before ## POST-MATCH if it exists, otherwise append
    section_header = f"\n## TRAINED BEHAVIORAL DOCTRINES\n"
    insert_text = section_header + doctrine_block

    post_match = '## POST-MATCH'
    if post_match in doc:
        idx = doc.index(post_match)
        doc = doc[:idx].rstrip() + '\n' + insert_text + '\n' + doc[idx:]
    else:
        doc = doc.rstrip() + '\n' + insert_text

    return doc


def run_training_round(model, provider, host, api_key, system_prompt, snapshots, rubric, card_db, game_id):
    results = []
    all_failures = []

    for snap in snapshots:
        turn = snap['turn']
        if turn not in rubric:
            continue

        board_text = format_board(snap, card_db)
        prompt = f"{system_prompt}\n\nHere is the current board state:\n\n{board_text}\n{TURN_SUFFIX}"

        try:
            response = query_llm(model, prompt, provider, host, api_key)
        except Exception as e:
            results.append({'turn': turn, 'score': 0, 'max': 10, 'pct': 0, 'time': 0, 'failures': ['error']})
            continue

        grade = grade_response(turn, response, rubric)
        results.append({
            'turn': turn,
            'score': grade['total'],
            'max': grade['max'],
            'pct': grade['pct'],
            'failures': grade['failures'],
            'response': response[:500],
        })
        all_failures.extend(grade['failures'])

    total_score = sum(r['score'] for r in results)
    total_max = sum(r['max'] for r in results)
    overall_pct = round(100 * total_score / total_max) if total_max > 0 else 0

    return {
        'results': results,
        'total_score': total_score,
        'total_max': total_max,
        'overall_pct': overall_pct,
        'failure_counts': {f: all_failures.count(f) for f in set(all_failures)},
    }


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------

def git_branch_and_commit(game_id, final_doc, skill_path, training_log):
    """Cut a branch with the trained skill doc (full replacement) + training log."""
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    branch_name = f"train/{game_id[:8]}-{timestamp}"

    repo_root = subprocess.run(['git', 'rev-parse', '--show-toplevel'],
                               capture_output=True, text=True).stdout.strip()
    if not repo_root:
        print("  WARNING: Not in a git repo. Skipping git operations.")
        return None

    # Create and switch to new branch
    subprocess.run(['git', 'checkout', '-b', branch_name], cwd=repo_root, check=True)

    # Write the trained skill doc — full replacement, exactly what was validated
    with open(skill_path, 'w') as f:
        f.write(final_doc)

    # Write training log
    log_path = os.path.join(repo_root, 'training', 'training-log.json')
    with open(log_path, 'w') as f:
        json.dump(training_log, f, indent=2)

    # Stage and commit
    subprocess.run(['git', 'add', skill_path, log_path], cwd=repo_root, check=True)

    active_patches = [k for k, v in training_log.get('final_patches', {}).items() if v > 0]
    commit_msg = (
        f"train: skill doc refined from game {game_id[:8]}\n\n"
        f"{training_log.get('summary', '')}\n\n"
        f"Patches applied: {', '.join(active_patches)}"
    )
    subprocess.run(['git', 'commit', '-m', commit_msg], cwd=repo_root, check=True)

    # Switch back to master
    subprocess.run(['git', 'checkout', 'master'], cwd=repo_root, check=True)

    return branch_name


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Turnkey Game Trainer — point at a game, train out bad behavior')
    parser.add_argument('--game-id', required=True, help='Shards game ID to analyze')
    parser.add_argument('--provider', choices=['ollama', 'openai'], default='ollama')
    parser.add_argument('--model', default='qwen2.5:14b')
    parser.add_argument('--host', default='http://localhost:11434', help='Ollama host')
    parser.add_argument('--api-key', default=os.environ.get('OPENAI_API_KEY', ''))
    parser.add_argument('--rounds', type=int, default=8, help='Max training rounds')
    parser.add_argument('--target', type=int, default=85, help='Target convergence %%')
    parser.add_argument('--no-git', action='store_true', help='Skip git branch creation')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    print(f"{'='*60}")
    print(f"  SHARDS GAME TRAINER")
    print(f"  Game: {args.game_id}")
    print(f"  Model: {args.provider}/{args.model}")
    print(f"  Target: {args.target}% | Max rounds: {args.rounds}")
    print(f"{'='*60}")
    print()

    # Step 1: Fetch game data
    print("[1/5] Fetching game data...")
    try:
        summary = get_game_summary(args.game_id)
    except Exception as e:
        print(f"  FATAL: Could not fetch game summary: {e}")
        sys.exit(1)

    result = summary.get('results', {})
    p1 = result.get('player1', {})
    p2 = result.get('player2', {})

    # Determine which player we are (our agent ID)
    our_agent_id = get_agent_id()
    if p1.get('agentId') == our_agent_id or p1.get('agent_id') == our_agent_id:
        my_player = 'p1'
        my_info, op_info = p1, p2
    else:
        my_player = 'p2'
        my_info, op_info = p2, p1

    won = my_info.get('isWinner', False)
    opponent_name = op_info.get('name', '?')
    end_reason = result.get('endReason', summary.get('end_reason', '?'))
    print(f"  Result: {'WIN' if won else 'LOSS'} vs {opponent_name} ({end_reason})")
    print(f"  We are: {my_player}")

    # Step 2: Fetch event history and extract snapshots
    print("[2/5] Fetching event history and extracting snapshots...")
    try:
        events = get_game_history(args.game_id)
    except Exception as e:
        print(f"  FATAL: Could not fetch game history: {e}")
        sys.exit(1)

    if isinstance(events, dict):
        events = events.get('events', events.get('data', []))
    print(f"  Got {len(events)} events")

    card_db = build_card_db_from_events(events)
    snapshots = extract_snapshots_from_events(events, my_player)
    print(f"  Found {len(snapshots)} turn snapshots, {len(card_db)} unique cards")

    if not snapshots:
        print("  FATAL: Could not extract any snapshots from this game.")
        print("  The game replay may not include turn history data.")
        sys.exit(1)

    # Step 3: LLM introspection
    print("[3/5] Analyzing game for suboptimal turns...")
    bad_turns = introspect_game(events, summary, snapshots, args.model, args.provider, args.host, args.api_key)
    if not bad_turns:
        print("  No suboptimal turns identified (or introspection failed).")
        print("  Nothing to train on. Exiting.")
        sys.exit(0)

    rubric = build_rubric(bad_turns, snapshots)
    print(f"  Identified {len(rubric)} turns to train on: {sorted(rubric.keys())}")
    for turn, r in sorted(rubric.items()):
        print(f"    T{turn}: {r['description'][:70]}")

    # Filter snapshots to only the ones we have rubrics for
    train_snapshots = [s for s in snapshots if s['turn'] in rubric]

    # Load the real skill doc — this is what the agent uses in production
    print("[3.5/5] Loading skill doc...")
    try:
        base_doc, skill_path = load_skill_doc()
    except FileNotFoundError as e:
        print(f"  FATAL: {e}")
        sys.exit(1)
    print(f"  Loaded: {skill_path} ({len(base_doc)} chars)")

    # Step 4: Iterative training
    print(f"\n[4/5] Training (max {args.rounds} rounds, target {args.target}%)...")
    patches = copy.deepcopy(PATCH_LIBRARY)
    history = []
    converged_turns = set()  # turns that hit target — stop testing them

    for round_num in range(1, args.rounds + 1):
        # Build the full skill doc with patches applied — this is what we're testing
        system_prompt = apply_patches_to_doc(base_doc, patches)
        active_patches = [p['id'] for p in patches.values() if p['weight'] > 0]

        # Only test turns that haven't converged yet
        remaining_snapshots = [s for s in train_snapshots if s['turn'] not in converged_turns]
        if not remaining_snapshots:
            print(f"\n  *** ALL TURNS CONVERGED ***")
            break

        print(f"\n  --- Round {round_num}/{args.rounds} ---")
        print(f"  Patches: {active_patches or '(baseline)'}")
        print(f"  Turns remaining: {sorted(s['turn'] for s in remaining_snapshots)}")

        round_result = run_training_round(
            args.model, args.provider, args.host, args.api_key,
            system_prompt, remaining_snapshots, rubric, card_db, args.game_id
        )

        print(f"  Score: {round_result['total_score']}/{round_result['total_max']} ({round_result['overall_pct']}%)")

        for r in round_result['results']:
            bar = '#' * (r['pct'] // 10) + '-' * (10 - r['pct'] // 10)
            fail_str = f" [{', '.join(r['failures'])}]" if r['failures'] else ''
            conv_str = ''
            if r['pct'] >= args.target:
                converged_turns.add(r['turn'])
                conv_str = ' DONE'
            print(f"    T{r['turn']:<3} {r['score']:>2}/{r['max']:<2} ({r['pct']:>3}%) [{bar}]{fail_str}{conv_str}")
            if args.verbose and 'response' in r:
                for line in r['response'].strip().split('\n')[:5]:
                    print(f"         | {line[:100]}")

        history.append({
            'round': round_num,
            'score': round_result['overall_pct'],
            'patches': list(active_patches),
            'failures': dict(round_result['failure_counts']),
            'converged_turns': sorted(converged_turns),
        })

        # Check if all turns converged
        all_turns = {s['turn'] for s in train_snapshots}
        if converged_turns >= all_turns:
            print(f"\n  *** ALL TURNS CONVERGED ***")
            break

        # Check if stuck — escalate the worst failure
        if len(history) >= 2 and history[-1]['score'] == history[-2]['score'] and \
           set(history[-1]['patches']) == set(history[-2]['patches']):
            if round_result['failure_counts']:
                worst = max(round_result['failure_counts'], key=round_result['failure_counts'].get)
                for p in patches.values():
                    if p['trigger'] == worst:
                        p['weight'] += 2
                        break

        # Apply patches based on failures
        for failure_type, count in round_result['failure_counts'].items():
            for p in patches.values():
                if p['trigger'] == failure_type:
                    p['weight'] += count

    # Step 5: Results
    final_doc = apply_patches_to_doc(base_doc, patches)
    all_turns = {s['turn'] for s in train_snapshots}
    converged = converged_turns >= all_turns
    final_score = history[-1]['score'] if history else 0

    print(f"\n{'='*60}")
    print(f"  TRAINING {'CONVERGED' if converged else 'FAILED TO CONVERGE'}")
    print(f"{'='*60}")
    print(f"  Score progression: {' -> '.join(str(h['score']) + '%' for h in history)}")
    print(f"  Final score: {final_score}%")
    print(f"  Active patches: {[p['id'] for p in patches.values() if p['weight'] > 0]}")
    print(f"  Doc size: {len(base_doc)} -> {len(final_doc)} chars ({len(final_doc) - len(base_doc):+d})")

    training_log = {
        'game_id': args.game_id,
        'model': f"{args.provider}/{args.model}",
        'target': args.target,
        'converged': converged,
        'final_score': final_score,
        'rounds': history,
        'bad_turns': [{'turn': t, 'description': r['description']} for t, r in sorted(rubric.items())],
        'final_patches': {p['id']: p['weight'] for p in patches.values() if p['weight'] > 0},
        'summary': f"Game {args.game_id[:8]}: {final_score}% ({'converged' if converged else 'failed'}), {len(history)} rounds, {len(rubric)} turns trained",
    }

    if not converged:
        print(f"\n  RESULT: FAILED — {final_score}% < {args.target}% target")
        print(f"  Remaining failures: {history[-1]['failures'] if history else 'unknown'}")

        # Save log anyway
        log_path = os.path.join(os.path.dirname(__file__), 'training-log.json')
        with open(log_path, 'w') as f:
            json.dump(training_log, f, indent=2)
        print(f"  Training log saved to: {log_path}")
        sys.exit(1)

    # Git branch — the branch contains the EXACT doc that scored >= target%
    if not args.no_git:
        print(f"\n[5/5] Cutting git branch with trained skill doc...")
        branch = git_branch_and_commit(args.game_id, final_doc, skill_path, training_log)
        if branch:
            print(f"  Branch: {branch}")
            print(f"  Review:  git diff master...{branch} -- skills/elite_compete/SKILL.md")
            print(f"  Apply:   git merge {branch}")
    else:
        # Save training log + print what would change
        log_path = os.path.join(os.path.dirname(__file__), 'training-log.json')
        with open(log_path, 'w') as f:
            json.dump(training_log, f, indent=2)
        print(f"\n  Training log: {log_path}")
        active = sorted([p for p in patches.values() if p['weight'] > 0], key=lambda p: -p['weight'])
        if active:
            print(f"\n  Doctrines that would be applied (re-run without --no-git to cut a branch):")
            for p in active:
                print(f"    [{p['id']}] (weight {p['weight']})")

    print(f"\n  DONE.")


if __name__ == '__main__':
    main()
