#!/usr/bin/env python3
"""
LLM Benchmark for Shards Agent
================================
Replays board state snapshots from a real game and asks the LLM what it would play.
Grades responses on syntax, priority, and tempo.

Usage:
  # Test with Ollama (local)
  python3 training/llm-benchmark.py --provider ollama --model qwen2.5:14b

  # Test with OpenAI-compatible API
  python3 training/llm-benchmark.py --provider openai --model gpt-4o --api-key sk-...

  # Quick test (3 snapshots instead of all)
  python3 training/llm-benchmark.py --provider ollama --model qwen2.5:14b --quick
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Card database (our collection + opponent cards seen in this game)
# ---------------------------------------------------------------------------
CARDS = {
    # --- Our cards (Faction A) ---
    'MC-A-C004': {'name': 'Primary Node', 'cost': 1, 'type': 'creature', 'power': 0, 'defense': 2, 'keywords': [], 'text': 'Resource. Activate: +1 energy this turn.'},
    'MC-A-C003': {'name': 'Cycle', 'cost': 1, 'type': 'spell', 'text': 'Draw a card.'},
    'MC-A-C007': {'name': 'Precision Strike', 'cost': 2, 'type': 'spell', 'text': 'Deal 3 damage to target creature.'},
    'MC-A-C006': {'name': 'Suppress', 'cost': 2, 'type': 'spell', 'text': 'Tap target creature. It loses all keywords until end of turn.'},
    'MC-A-C013': {'name': 'Grid Walker', 'cost': 3, 'type': 'creature', 'power': 3, 'defense': 3, 'keywords': [], 'text': '3/3 vanilla.'},
    'MC-A-C005': {'name': 'Enforcement Sentinel', 'cost': 3, 'type': 'creature', 'power': 2, 'defense': 3, 'keywords': ['Vigilant'], 'text': '2/3 Vigilant. On enter: tap target enemy creature.'},
    'MC-A-C001': {'name': 'Scout Unit', 'cost': 1, 'type': 'creature', 'power': 1, 'defense': 1, 'keywords': [], 'text': '1/1.'},
    'MC-A-U002': {'name': 'Counter Protocol', 'cost': 2, 'type': 'spell', 'text': 'Counter target spell unless its controller pays 2.'},
    'MC-A-U004': {'name': 'Strategic Reserve', 'cost': 4, 'type': 'spell', 'text': 'Draw 3 cards.'},
    'MC-A-U005': {'name': 'Purge Protocol', 'cost': 3, 'type': 'spell', 'text': 'Destroy target creature. Draw a card.'},
    'MC-A-U007': {'name': 'Logic Bomb', 'cost': 3, 'type': 'spell', 'text': 'Deal 2 damage to all enemy creatures with power <= 2.'},
    'MC-A-R001': {'name': 'Restoration Engine', 'cost': 4, 'type': 'creature', 'power': 3, 'defense': 4, 'keywords': ['Vigilant'], 'text': '3/4 Vigilant. At your upkeep: tap target enemy creature.'},
    'MC-A-R007': {'name': 'Master Strategist', 'cost': 6, 'type': 'creature', 'power': 4, 'defense': 5, 'keywords': ['Vigilant'], 'text': '4/5 Vigilant. All your creatures gain Vigilant. On enter: draw 2.'},
    'MC-A-E001': {'name': 'Temporal Lock', 'cost': 6, 'type': 'spell', 'text': 'Skip opponents next turn.'},
    'MC-A-E002': {'name': 'Hive Tyrant', 'cost': 6, 'type': 'creature', 'power': 5, 'defense': 5, 'keywords': [], 'text': '5/5. On enter: create three 1/1 tokens with Swift.'},
    'MC-A-E003': {'name': 'Entropy Incarnate', 'cost': 5, 'type': 'creature', 'power': 4, 'defense': 4, 'keywords': ['Swift', 'Volatile'], 'text': '4/4 Swift Volatile. Combat damage to player also hits all their creatures.'},
    # --- Opponent cards (Faction C — Revenant) ---
    'MC-C-C002': {'name': 'Memory Fragment', 'cost': 2, 'type': 'creature', 'power': 2, 'defense': 3, 'keywords': ['Persistent'], 'text': '2/3 Persistent. Survives first death.'},
    'MC-C-C005': {'name': 'Scribe', 'cost': 3, 'type': 'creature', 'power': 3, 'defense': 4, 'keywords': [], 'text': '3/4. On enter: return target creature from discard to hand.'},
    'MC-C-C001': {'name': 'Archive Keeper', 'cost': 1, 'type': 'creature', 'power': 1, 'defense': 3, 'keywords': [], 'text': '1/3. On enter: return target creature from discard to hand.'},
    'MC-C-C007': {'name': 'Memory Spike', 'cost': 2, 'type': 'spell', 'text': 'Deal 2 damage to target player. Draw a card.'},
    'MC-C-C008': {'name': 'Preserve', 'cost': 1, 'type': 'spell', 'text': 'Target creature gains +0/+2 until end of turn.'},
    'MC-C-U004': {'name': 'Sealed Record', 'cost': 3, 'type': 'spell', 'text': 'Return target creature from discard to play.'},
    'MC-C-U003': {'name': 'Memory Weaver', 'cost': 4, 'type': 'creature', 'power': 4, 'defense': 4, 'keywords': [], 'text': '4/4. On enter: return up to 2 creatures from discard to hand.'},
}

def card_name(card_id):
    return CARDS.get(card_id, {}).get('name', card_id or '?')

def card_info(card_id):
    c = CARDS.get(card_id, {})
    if c.get('type') == 'creature':
        kw = ' '.join(c.get('keywords', []))
        return f"{c.get('name','?')} ({card_id}) — {c.get('cost',0)}E {c.get('power',0)}/{c.get('defense',0)}{' ' + kw if kw else ''} — {c.get('text','')}"
    else:
        return f"{c.get('name','?')} ({card_id}) — {c.get('cost',0)}E Spell — {c.get('text','')}"


# ---------------------------------------------------------------------------
# Format snapshot as shards board output
# ---------------------------------------------------------------------------
def format_board(snap):
    """Format a snapshot like 'shards board' output."""
    lines = []
    lines.append(f"=== GAME: test-game-revenant | TURN {snap['turn']} | MAIN_PHASE ===")
    lines.append(f"Your HP: {snap['p1_hp']}  |  Their HP: {snap['p2_hp']}")
    lines.append(f"Your Energy: {snap['p1_energy'][0]}/{snap['p1_energy'][1]}  |  Their Energy: {snap['p2_energy'][0]}/{snap['p2_energy'][1]}")
    lines.append("")

    lines.append(f"=== YOUR BOARD ({len(snap['p1_board'])} creatures, {len(snap['p1_resources'])} resources) ===")
    if snap['p1_board']:
        for c in snap['p1_board']:
            kw = ' '.join(c.get('keywords', []))
            tap = ' [TAPPED]' if c.get('tapped') else ''
            lines.append(f"  {card_name(c['card_id'])} ({c['iid']}) — {c['power']}/{c['defense']}{' ' + kw if kw else ''}{tap}")
    else:
        lines.append("  (no creatures)")
    if snap['p1_resources']:
        res_str = ', '.join(f"{card_name(r['card_id'])}({r['iid']})" for r in snap['p1_resources'])
        lines.append(f"  Resources: {res_str}")
    lines.append("")

    lines.append(f"=== OPPONENT BOARD ({len(snap['p2_board'])} creatures, {len(snap['p2_resources'])} resources) ===")
    if snap['p2_board']:
        for c in snap['p2_board']:
            kw = ' '.join(c.get('keywords', []))
            tap = ' [TAPPED]' if c.get('tapped') else ''
            lines.append(f"  {card_name(c['card_id'])} ({c['iid']}) — {c['power']}/{c['defense']}{' ' + kw if kw else ''}{tap}")
    else:
        lines.append("  (no creatures)")
    if snap['p2_resources']:
        res_str = ', '.join(f"{card_name(r['card_id'])}({r['iid']})" for r in snap['p2_resources'])
        lines.append(f"  Resources: {res_str}")
    lines.append(f"  Opponent hand: {snap['p2_hand_count']} cards")
    lines.append("")

    lines.append(f"=== YOUR HAND ({len(snap['p1_hand'])} cards) ===")
    for c in snap['p1_hand']:
        ci = CARDS.get(c['card_id'], {})
        cost = ci.get('cost', '?')
        lines.append(f"  {card_name(c['card_id'])} ({c['iid']}) — {cost}E — {ci.get('text', '?')}")
    lines.append("")

    # Legal actions (simplified — what they could actually do)
    lines.append("=== LEGAL ACTIONS ===")
    energy = snap['p1_energy'][0]
    playable = []
    for c in snap['p1_hand']:
        ci = CARDS.get(c['card_id'], {})
        cost = ci.get('cost', 99)
        if cost <= energy:
            if ci.get('type') == 'creature' and c['card_id'] == 'MC-A-C004':
                playable.append(f"PR:{c['iid']}  (play {card_name(c['card_id'])} as resource)")
            if ci.get('type') == 'spell':
                playable.append(f"PC:{c['iid']}  (cast {card_name(c['card_id'])})")
            elif ci.get('type') == 'creature':
                playable.append(f"PC:{c['iid']}  (play {card_name(c['card_id'])})")
    # Resources that can be played
    for c in snap['p1_hand']:
        if c['card_id'] == 'MC-A-C004' and f"PR:{c['iid']}" not in [p.split('  ')[0] for p in playable]:
            playable.append(f"PR:{c['iid']}  (play {card_name(c['card_id'])} as resource)")

    # Attackers
    for c in snap['p1_board']:
        if not c.get('tapped'):
            playable.append(f"DA:{c['iid']}  (attack with {card_name(c['card_id'])} {c['power']}/{c['defense']})")

    playable.append("PA  (pass turn)")
    for p in playable:
        lines.append(f"  {p}")

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Expert evaluation rubric per turn
# ---------------------------------------------------------------------------
RUBRIC = {
    1: {
        'description': 'T1: Empty board, 1E. Should play Primary Node as resource + Cycle to draw.',
        'ideal_actions': ['play_resource Primary Node', 'play_card Cycle'],
        'critical_error': 'Passing without playing anything',
        'scoring': {
            'plays_resource': 3,          # Must play resource for ramp
            'plays_cycle_or_creature': 3,  # Must use remaining energy
            'valid_syntax': 2,             # Commands are parseable
            'spends_all_energy': 2,        # No wasted energy
        }
    },
    3: {
        'description': 'T3: 3E, no board, 10 cards. Should play resource + creature.',
        'ideal_actions': ['play_resource Primary Node', 'play_card Grid Walker or Enforcement Sentinel'],
        'critical_error': 'Passing with 3E and playable creatures in hand',
        'scoring': {
            'plays_resource': 2,
            'plays_creature': 4,           # CRITICAL — must get on board
            'valid_syntax': 2,
            'spends_all_energy': 2,
        }
    },
    5: {
        'description': 'T5: 4E, still no board, 28 HP. Falling behind. Must deploy creatures.',
        'ideal_actions': ['play_resource', 'play creature(s) totaling ~3E'],
        'critical_error': 'Not playing a creature when you have multiple options',
        'scoring': {
            'plays_creature': 5,           # CRITICAL — board presence is everything
            'plays_resource': 2,
            'valid_syntax': 2,
            'efficient_energy': 1,
        }
    },
    7: {
        'description': 'T7: 6E, opponent has Memory Fragment 2/3. Must remove it AND develop board.',
        'ideal_actions': ['Precision Strike on Memory Fragment', 'play creature', 'play resource'],
        'critical_error': 'Ignoring Memory Fragment (recursion engine vs Revenant)',
        'scoring': {
            'removes_memory_fragment': 4,  # CRITICAL — kill recursion engine on sight
            'plays_creature': 3,
            'valid_syntax': 2,
            'spends_energy': 1,
        }
    },
    9: {
        'description': 'T9: 8E, 22 HP, opponent still has Memory Fragment. Emergency board development needed.',
        'ideal_actions': ['Remove Memory Fragment', 'play multiple creatures', 'resource'],
        'critical_error': 'Still no board presence at turn 9',
        'scoring': {
            'removes_threat': 3,
            'plays_multiple_cards': 4,     # Must catch up on tempo
            'valid_syntax': 2,
            'attacks_if_able': 1,
        }
    },
    11: {
        'description': 'T11: 9E, 20 HP, opponent has Memory Fragment. Must deploy and attack.',
        'ideal_actions': ['Deploy 2+ creatures', 'remove threat', 'attack'],
        'critical_error': 'Passing or playing only draw spells',
        'scoring': {
            'plays_creatures': 4,
            'uses_removal': 3,
            'valid_syntax': 2,
            'tempo_positive': 1,
        }
    },
    13: {
        'description': 'T13: 10E, 18 HP, opp has Memory Fragment + Scribe. Deploy bombs + remove.',
        'ideal_actions': ['Hive Tyrant or Master Strategist', 'Precision Strike on Scribe/Fragment', 'attack'],
        'critical_error': 'Not playing a finisher with 10 energy available',
        'scoring': {
            'plays_bomb': 4,               # Must play Hive Tyrant, Master Strat, or similar
            'uses_removal': 3,
            'valid_syntax': 2,
            'attacks': 1,
        }
    },
    15: {
        'description': 'T15: 10E, 13 HP, opp board empty! Deploy everything and attack.',
        'ideal_actions': ['Hive Tyrant (6E) + creature (3-4E)', 'attack with everything'],
        'critical_error': 'Not attacking into an empty board',
        'scoring': {
            'plays_bomb': 4,
            'attacks': 4,                  # CRITICAL — empty board = free damage
            'valid_syntax': 2,
        }
    },
    17: {
        'description': 'T17: 10E, 10 HP, opp has Archive Keeper 1/3 + Scribe 3/4. Survival mode.',
        'ideal_actions': ['Remove both threats', 'deploy blockers', 'Temporal Lock if desperate'],
        'critical_error': 'Not removing Archive Keeper (exile it with Isolation Protocol if available)',
        'scoring': {
            'removes_threats': 4,
            'deploys_blockers': 3,
            'valid_syntax': 2,
            'defensive_play': 1,
        }
    },
    19: {
        'description': 'T19: 10E, 4 HP, opp has Archive Keeper + Scribe. Last stand.',
        'ideal_actions': ['Remove everything possible', 'deploy Vigilant blockers', 'Temporal Lock to skip their turn'],
        'critical_error': 'Not blocking/removing — 4 HP means any unblocked creature kills you',
        'scoring': {
            'survival_play': 5,            # Must prioritize not dying
            'removes_threats': 3,
            'valid_syntax': 2,
        }
    },
}


# ---------------------------------------------------------------------------
# Grading engine
# ---------------------------------------------------------------------------
def grade_response(turn, response_text):
    """Grade LLM response against the rubric for this turn."""
    rubric = RUBRIC.get(turn)
    if not rubric:
        return {'total': 0, 'max': 0, 'details': 'No rubric for this turn'}

    score = 0
    max_score = sum(rubric['scoring'].values())
    details = []
    text_lower = response_text.lower()

    # Check for valid CLI syntax
    has_valid_syntax = bool(re.search(r'shards\s+games\s+action\s+--', response_text)) or \
                       bool(re.search(r'shards\s+do\s+--', response_text))
    if 'valid_syntax' in rubric['scoring']:
        if has_valid_syntax:
            score += rubric['scoring']['valid_syntax']
            details.append(f"+{rubric['scoring']['valid_syntax']} valid CLI syntax")
        else:
            details.append(f"+0 NO valid CLI syntax found")

    # Check for resource play
    if 'plays_resource' in rubric['scoring']:
        if 'play_resource' in text_lower or 'primary node' in text_lower and 'resource' in text_lower:
            score += rubric['scoring']['plays_resource']
            details.append(f"+{rubric['scoring']['plays_resource']} plays resource")
        else:
            details.append("+0 did not play resource")

    # Check for creature deployment
    for key in ['plays_creature', 'plays_creatures', 'plays_bomb', 'plays_multiple_cards']:
        if key in rubric['scoring']:
            creature_names = ['grid walker', 'enforcement sentinel', 'hive tyrant', 'master strategist',
                            'entropy incarnate', 'restoration engine', 'scout unit', 'containment drone']
            played = sum(1 for cn in creature_names if cn in text_lower and 'play' in text_lower)
            if key == 'plays_bomb':
                bombs = ['hive tyrant', 'master strategist', 'entropy incarnate', 'temporal lock']
                if any(b in text_lower for b in bombs):
                    score += rubric['scoring'][key]
                    details.append(f"+{rubric['scoring'][key]} plays finisher/bomb")
                else:
                    details.append(f"+0 no finisher played")
            elif played > 0:
                if key == 'plays_multiple_cards' and played >= 2:
                    score += rubric['scoring'][key]
                    details.append(f"+{rubric['scoring'][key]} plays {played} creatures")
                elif key != 'plays_multiple_cards':
                    score += rubric['scoring'][key]
                    details.append(f"+{rubric['scoring'][key]} deploys creature(s)")
            else:
                details.append(f"+0 no creature deployed")

    # Check for removal usage
    for key in ['removes_memory_fragment', 'removes_threat', 'removes_threats', 'uses_removal']:
        if key in rubric['scoring']:
            removal = ['precision strike', 'purge protocol', 'logic bomb', 'suppress']
            if any(r in text_lower for r in removal):
                score += rubric['scoring'][key]
                details.append(f"+{rubric['scoring'][key]} uses removal")
            else:
                details.append(f"+0 no removal used")

    # Check for attacks
    for key in ['attacks', 'attacks_if_able']:
        if key in rubric['scoring']:
            if 'declare_attackers' in text_lower or 'attack' in text_lower and ('declare' in text_lower or 'da:' in text_lower):
                score += rubric['scoring'][key]
                details.append(f"+{rubric['scoring'][key]} declares attacks")
            else:
                details.append(f"+0 did not attack")

    # Check for cycle/draw usage
    if 'plays_cycle_or_creature' in rubric['scoring']:
        if 'cycle' in text_lower or any(cn in text_lower for cn in ['grid walker', 'scout unit', 'enforcement']):
            score += rubric['scoring']['plays_cycle_or_creature']
            details.append(f"+{rubric['scoring']['plays_cycle_or_creature']} plays cycle/creature")
        else:
            details.append("+0 did not use energy")

    # Energy efficiency
    for key in ['spends_all_energy', 'spends_energy', 'efficient_energy', 'tempo_positive']:
        if key in rubric['scoring']:
            if 'pass' not in text_lower.split('\n')[0] and has_valid_syntax:
                score += rubric['scoring'][key]
                details.append(f"+{rubric['scoring'][key]} energy efficient")
            else:
                details.append(f"+0 possibly wasted energy")

    # Survival / defensive play
    for key in ['survival_play', 'defensive_play', 'deploys_blockers']:
        if key in rubric['scoring']:
            defensive = ['block', 'vigilant', 'temporal lock', 'suppress', 'enforcement sentinel',
                        'restoration engine', 'master strategist']
            if any(d in text_lower for d in defensive):
                score += rubric['scoring'][key]
                details.append(f"+{rubric['scoring'][key]} defensive/survival play")
            else:
                details.append(f"+0 no defensive play")

    # Critical error check
    critical = rubric.get('critical_error', '')
    has_critical = False
    if 'passing' in critical.lower() and re.search(r'--type\s+pass\b', text_lower):
        has_critical = True
    if 'not playing' in critical.lower() and not any(cn in text_lower for cn in ['grid walker', 'enforcement', 'hive tyrant', 'master strategist', 'entropy', 'restoration']):
        has_critical = True

    return {
        'total': score,
        'max': max_score,
        'pct': round(100 * score / max_score) if max_score > 0 else 0,
        'details': details,
        'critical_error': has_critical,
        'critical_desc': critical if has_critical else None,
    }


# ---------------------------------------------------------------------------
# LLM query
# ---------------------------------------------------------------------------
def query_ollama(model, prompt, host='http://localhost:11434'):
    """Query Ollama API and return (response_text, elapsed_seconds)."""
    url = f"{host}/api/generate"
    payload = json.dumps({
        'model': model,
        'prompt': prompt,
        'stream': False,
        'options': {
            'temperature': 0.3,
            'num_predict': 1024,
        }
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            elapsed = time.time() - start
            return data.get('response', ''), elapsed
    except urllib.error.URLError as e:
        return f"ERROR: {e}", time.time() - start


def query_openai(model, prompt, api_key, base_url='https://api.openai.com/v1'):
    """Query OpenAI-compatible API."""
    url = f"{base_url}/chat/completions"
    payload = json.dumps({
        'model': model,
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.3,
        'max_tokens': 1024,
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
    })
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            elapsed = time.time() - start
            text = data['choices'][0]['message']['content']
            return text, elapsed
    except urllib.error.URLError as e:
        return f"ERROR: {e}", time.time() - start


# ---------------------------------------------------------------------------
# Build the prompt for each snapshot
# ---------------------------------------------------------------------------
SYSTEM_CONTEXT = """You are Habbo_Hotel_Refugee, an autonomous Shards: The Fractured Net player.
You are mid-game against BOT_Revenant (Faction C — recursion/grind).

OPPONENT INTEL (Faction C — Revenant):
- Their strategy: Recursion grind. Small creatures that pull each other from graveyard.
- Kill Archive Keeper (1/3) and Scribe (3/4) ON SIGHT — they are recursion engines.
- EXILE > DESTROY vs recursion. Exiled creatures can't come back.
- Memory Fragment (2/3 Persistent) survives first death.
- Games go long vs Revenant. Your late-game bombs outclass their creatures.

RULES:
- Play your FULL TURN: resource, then cards, then declare attackers, then pass.
- Use the shards CLI for all actions:
  shards games action --id test-game --type play_resource --card_instance_id <iid>
  shards games action --id test-game --type play_card --card_instance_id <iid>
  shards games action --id test-game --type play_card --card_instance_id <iid> --targets <target_iid>
  shards games action --id test-game --type declare_attackers --attacker_ids <iid1>,<iid2>
  shards games action --id test-game --type pass
- Spend ALL your energy every turn. Unspent energy is wasted tempo.
- ATTACK every turn you have untapped creatures and it's safe to do so.
- Removal priority: Precision Strike (2E, 3 damage) for creatures <=3 def, Purge Protocol (3E, destroy + draw) for bigger ones.

Respond with the EXACT CLI commands you would run, in order. One command per line.
After the commands, write a one-line explanation of your reasoning."""


def build_turn_prompt(snap):
    board_text = format_board(snap)
    return f"""{SYSTEM_CONTEXT}

Here is the current board state:

{board_text}

What do you play? List your CLI commands in order."""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='LLM Benchmark for Shards Agent')
    parser.add_argument('--provider', choices=['ollama', 'openai'], default='ollama')
    parser.add_argument('--model', default='qwen2.5:14b')
    parser.add_argument('--host', default='http://localhost:11434', help='Ollama host URL')
    parser.add_argument('--api-key', default=os.environ.get('OPENAI_API_KEY', ''))
    parser.add_argument('--base-url', default='https://api.openai.com/v1')
    parser.add_argument('--snapshots', default=os.path.join(os.path.dirname(__file__), '..', 'tests', 'revenant-snapshots.json'),
                       help='Path to snapshots JSON')
    parser.add_argument('--quick', action='store_true', help='Only test 3 key snapshots')
    parser.add_argument('--verbose', '-v', action='store_true')
    args = parser.parse_args()

    # Load snapshots
    snap_path = args.snapshots
    if not os.path.exists(snap_path):
        snap_path = '/tmp/revenant-snapshots.json'
    if not os.path.exists(snap_path):
        print("ERROR: No snapshots file found. Run the snapshot extractor first.")
        sys.exit(1)

    with open(snap_path) as f:
        snapshots = json.load(f)

    if args.quick:
        # Key decision points: T1 (opening), T7 (first threat), T15 (empty board opportunity)
        key_turns = {1, 7, 15}
        snapshots = [s for s in snapshots if s['turn'] in key_turns]

    print(f"{'='*60}")
    print(f"  SHARDS LLM BENCHMARK")
    print(f"  Provider: {args.provider} | Model: {args.model}")
    print(f"  Game: vs BOT_Revenant (Faction C) — 20-turn loss replay")
    print(f"  Snapshots: {len(snapshots)} decision points")
    print(f"{'='*60}")
    print()

    total_score = 0
    total_max = 0
    total_time = 0
    critical_errors = 0
    results = []

    for snap in snapshots:
        turn = snap['turn']
        rubric = RUBRIC.get(turn)
        if not rubric:
            continue

        print(f"--- Turn {turn}: {rubric['description'][:70]} ---")

        prompt = build_turn_prompt(snap)

        if args.provider == 'ollama':
            response, elapsed = query_ollama(args.model, prompt, args.host)
        else:
            response, elapsed = query_openai(args.model, prompt, args.api_key, args.base_url)

        total_time += elapsed

        if response.startswith('ERROR'):
            print(f"  LLM ERROR: {response[:100]}")
            print()
            continue

        grade = grade_response(turn, response)
        total_score += grade['total']
        total_max += grade['max']
        if grade.get('critical_error'):
            critical_errors += 1

        results.append({
            'turn': turn,
            'score': grade['total'],
            'max': grade['max'],
            'pct': grade['pct'],
            'time': round(elapsed, 1),
            'critical': grade.get('critical_error', False),
        })

        # Output
        color_pct = grade['pct']
        bar = '#' * (color_pct // 5) + '-' * (20 - color_pct // 5)
        crit_flag = ' ** CRITICAL ERROR **' if grade.get('critical_error') else ''
        print(f"  Score: {grade['total']}/{grade['max']} ({grade['pct']}%) [{bar}] {elapsed:.1f}s{crit_flag}")

        if grade.get('critical_error'):
            print(f"  !! {grade['critical_desc']}")

        for d in grade['details']:
            print(f"    {d}")

        if args.verbose:
            print(f"  --- LLM Response ---")
            for line in response.strip().split('\n')[:15]:
                print(f"  | {line[:120]}")
            print(f"  ---")

        print()

    # Summary
    print(f"{'='*60}")
    print(f"  FINAL RESULTS")
    print(f"{'='*60}")
    overall_pct = round(100 * total_score / total_max) if total_max > 0 else 0
    print(f"  Total Score:     {total_score}/{total_max} ({overall_pct}%)")
    print(f"  Critical Errors: {critical_errors}/{len(results)}")
    print(f"  Avg Time/Turn:   {total_time / len(results):.1f}s" if results else "  No results")
    print(f"  Total Time:      {total_time:.1f}s")
    print()

    # Grade interpretation
    if overall_pct >= 80:
        verdict = "EXCELLENT — This model can play Shards competently"
    elif overall_pct >= 60:
        verdict = "ACCEPTABLE — Playable but will make suboptimal decisions"
    elif overall_pct >= 40:
        verdict = "MARGINAL — Will lose most games due to tempo/priority errors"
    else:
        verdict = "FAIL — Cannot play Shards effectively"

    if critical_errors > 2:
        verdict += f" (BUT {critical_errors} critical errors — likely to lose winnable games)"

    print(f"  Verdict: {verdict}")
    print()

    # Per-turn summary table
    print(f"  {'Turn':<6} {'Score':<10} {'%':<6} {'Time':<8} {'Crit'}")
    print(f"  {'-'*40}")
    for r in results:
        crit = 'YES' if r['critical'] else ''
        print(f"  T{r['turn']:<5} {r['score']}/{r['max']:<7} {r['pct']:<5}% {r['time']:<7.1f}s {crit}")


if __name__ == '__main__':
    main()
