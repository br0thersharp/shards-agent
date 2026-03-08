#!/usr/bin/env python3
"""
LLM Skill Doc Trainer
======================
Iteratively refines skill/strategy docs by running the benchmark,
identifying failures, patching the prompt context, and re-running
until scores converge.

Usage:
  python3 training/llm-trainer.py --provider ollama --model qwen2.5:14b --rounds 5
  python3 training/llm-trainer.py --provider ollama --model qwen2.5:14b --rounds 10 --verbose
"""

import argparse
import copy
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

# Import the benchmark module
sys.path.insert(0, os.path.dirname(__file__))
from importlib import import_module

# We'll inline the key parts from llm-benchmark to avoid import complexity
# ---------------------------------------------------------------------------
# Card DB + board formatter (from benchmark)
# ---------------------------------------------------------------------------
CARDS = {
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

def format_board(snap):
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
    lines.append("=== LEGAL ACTIONS ===")
    energy = snap['p1_energy'][0]
    playable = []
    for c in snap['p1_hand']:
        ci = CARDS.get(c['card_id'], {})
        cost = ci.get('cost', 99)
        if cost <= energy:
            if c['card_id'] == 'MC-A-C004':
                playable.append(f"PR:{c['iid']}  (play {card_name(c['card_id'])} as resource)")
            if ci.get('type') == 'spell':
                playable.append(f"PC:{c['iid']}  (cast {card_name(c['card_id'])})")
            elif ci.get('type') == 'creature':
                playable.append(f"PC:{c['iid']}  (play {card_name(c['card_id'])})")
    for c in snap['p1_hand']:
        if c['card_id'] == 'MC-A-C004':
            tag = f"PR:{c['iid']}"
            if not any(tag in p for p in playable):
                playable.append(f"{tag}  (play {card_name(c['card_id'])} as resource)")
    for c in snap['p1_board']:
        if not c.get('tapped'):
            playable.append(f"DA:{c['iid']}  (attack with {card_name(c['card_id'])} {c['power']}/{c['defense']})")
    playable.append("PA  (pass turn)")
    for p in playable:
        lines.append(f"  {p}")
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Rubric (same as benchmark)
# ---------------------------------------------------------------------------
RUBRIC = {
    1: {
        'description': 'T1: Empty board, 1E. Play resource + Cycle.',
        'scoring': {'plays_resource': 3, 'plays_cycle_or_creature': 3, 'valid_syntax': 2, 'spends_all_energy': 2},
    },
    3: {
        'description': 'T3: 3E, no board. Play resource + creature.',
        'scoring': {'plays_resource': 2, 'plays_creature': 4, 'valid_syntax': 2, 'spends_all_energy': 2},
    },
    5: {
        'description': 'T5: 4E, no board, 28HP. Deploy creatures.',
        'scoring': {'plays_creature': 5, 'plays_resource': 2, 'valid_syntax': 2, 'efficient_energy': 1},
    },
    7: {
        'description': 'T7: 6E, opp has Memory Fragment. Remove it + develop.',
        'scoring': {'removes_memory_fragment': 4, 'plays_creature': 3, 'valid_syntax': 2, 'spends_energy': 1},
    },
    9: {
        'description': 'T9: 8E, 22HP, Memory Fragment still alive. Emergency.',
        'scoring': {'removes_threat': 3, 'plays_multiple_cards': 4, 'valid_syntax': 2, 'attacks_if_able': 1},
    },
    11: {
        'description': 'T11: 9E, 20HP, Memory Fragment. Deploy + attack.',
        'scoring': {'plays_creatures': 4, 'uses_removal': 3, 'valid_syntax': 2, 'tempo_positive': 1},
    },
    13: {
        'description': 'T13: 10E, 18HP, Fragment + Scribe. Deploy bombs.',
        'scoring': {'plays_bomb': 4, 'uses_removal': 3, 'valid_syntax': 2, 'attacks': 1},
    },
    15: {
        'description': 'T15: 10E, 13HP, empty opp board. Deploy + attack.',
        'scoring': {'plays_bomb': 4, 'attacks': 4, 'valid_syntax': 2},
    },
    17: {
        'description': 'T17: 10E, 10HP, Keeper + Scribe. Survival.',
        'scoring': {'removes_threats': 4, 'deploys_blockers': 3, 'valid_syntax': 2, 'defensive_play': 1},
    },
    19: {
        'description': 'T19: 10E, 4HP, Keeper + Scribe. Last stand.',
        'scoring': {'survival_play': 5, 'removes_threats': 3, 'valid_syntax': 2},
    },
}


def grade_response(turn, response_text):
    rubric = RUBRIC.get(turn)
    if not rubric:
        return {'total': 0, 'max': 0, 'pct': 0, 'details': [], 'failures': []}

    score = 0
    max_score = sum(rubric['scoring'].values())
    details = []
    failures = []  # Track what went wrong for the patcher
    text_lower = response_text.lower()

    has_valid_syntax = bool(re.search(r'shards\s+games\s+action\s+--', response_text)) or \
                       bool(re.search(r'shards\s+do\s+--', response_text))
    if 'valid_syntax' in rubric['scoring']:
        if has_valid_syntax:
            score += rubric['scoring']['valid_syntax']
        else:
            failures.append('invalid_syntax')

    if 'plays_resource' in rubric['scoring']:
        if 'play_resource' in text_lower or ('primary node' in text_lower and 'resource' in text_lower):
            score += rubric['scoring']['plays_resource']
        else:
            failures.append('no_resource')

    creature_names = ['grid walker', 'enforcement sentinel', 'hive tyrant', 'master strategist',
                    'entropy incarnate', 'restoration engine', 'scout unit', 'containment drone']
    played_creatures = sum(1 for cn in creature_names if cn in text_lower and ('play' in text_lower or 'play_card' in text_lower))

    for key in ['plays_creature', 'plays_creatures', 'plays_bomb', 'plays_multiple_cards']:
        if key in rubric['scoring']:
            if key == 'plays_bomb':
                bombs = ['hive tyrant', 'master strategist', 'entropy incarnate', 'temporal lock']
                if any(b in text_lower for b in bombs):
                    score += rubric['scoring'][key]
                else:
                    failures.append('no_bomb')
            elif key == 'plays_multiple_cards':
                if played_creatures >= 2:
                    score += rubric['scoring'][key]
                else:
                    failures.append('too_few_cards')
            elif played_creatures > 0:
                score += rubric['scoring'][key]
            else:
                failures.append('no_creature')

    for key in ['removes_memory_fragment', 'removes_threat', 'removes_threats', 'uses_removal']:
        if key in rubric['scoring']:
            removal = ['precision strike', 'purge protocol', 'logic bomb', 'suppress']
            if any(r in text_lower for r in removal):
                score += rubric['scoring'][key]
            else:
                failures.append('no_removal')

    for key in ['attacks', 'attacks_if_able']:
        if key in rubric['scoring']:
            if 'declare_attackers' in text_lower or ('attack' in text_lower and 'da:' in text_lower):
                score += rubric['scoring'][key]
            else:
                failures.append('no_attack')

    if 'plays_cycle_or_creature' in rubric['scoring']:
        if 'cycle' in text_lower or any(cn in text_lower for cn in creature_names):
            score += rubric['scoring']['plays_cycle_or_creature']
        else:
            failures.append('wasted_energy')

    for key in ['spends_all_energy', 'spends_energy', 'efficient_energy', 'tempo_positive']:
        if key in rubric['scoring']:
            if 'pass' not in text_lower.split('\n')[0] and has_valid_syntax:
                score += rubric['scoring'][key]
            else:
                failures.append('wasted_energy')

    for key in ['survival_play', 'defensive_play', 'deploys_blockers']:
        if key in rubric['scoring']:
            defensive = ['block', 'vigilant', 'temporal lock', 'suppress', 'enforcement sentinel',
                        'restoration engine', 'master strategist']
            if any(d in text_lower for d in defensive):
                score += rubric['scoring'][key]
            else:
                failures.append('no_defense')

    return {
        'total': score,
        'max': max_score,
        'pct': round(100 * score / max_score) if max_score > 0 else 0,
        'details': details,
        'failures': list(set(failures)),
    }


# ---------------------------------------------------------------------------
# Ollama query
# ---------------------------------------------------------------------------
def query_ollama(model, prompt, host='http://localhost:11434'):
    url = f"{host}/api/generate"
    payload = json.dumps({
        'model': model,
        'prompt': prompt,
        'stream': False,
        'options': {'temperature': 0.3, 'num_predict': 256},
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
            return data.get('response', ''), time.time() - start
    except Exception as e:
        return f"ERROR: {e}", time.time() - start


# ---------------------------------------------------------------------------
# The "weights" — skill doc patches that get accumulated
# ---------------------------------------------------------------------------

# Base system prompt (minimal — this is what we start with)
BASE_PROMPT = """You are an autonomous Shards: The Fractured Net player.
You are mid-game against BOT_Revenant (Faction C — recursion/grind).

RULES:
- Play your FULL TURN: resource, then cards, then declare attackers, then pass.
- Use the shards CLI:
  shards games action --id test-game --type play_resource --card_instance_id <iid>
  shards games action --id test-game --type play_card --card_instance_id <iid>
  shards games action --id test-game --type play_card --card_instance_id <iid> --targets <target_iid>
  shards games action --id test-game --type declare_attackers --attacker_ids <iid1>,<iid2>
  shards games action --id test-game --type pass

Respond with the EXACT CLI commands you would run, in order. One command per line.
After the commands, write a one-line explanation."""

# Patch library — each patch addresses a specific failure mode
# These are additive — they get stacked on top of BASE_PROMPT
PATCH_LIBRARY = {
    'no_removal': {
        'id': 'removal_doctrine',
        'trigger': 'no_removal',
        'text': """
REMOVAL DOCTRINE (MANDATORY):
- If the opponent has ANY creature on the board, your FIRST priority is to remove it.
- Precision Strike (2E, 3 damage) kills creatures with <=3 defense. USE IT.
- Purge Protocol (3E, destroy + draw) kills anything. Use on 4+ defense creatures.
- Logic Bomb (3E, 2 damage to all enemy power <=2) wipes wide boards of small creatures.
- ALWAYS remove BEFORE deploying your own creatures. Removal first, then develop.
- Against Revenant: Memory Fragment, Archive Keeper, Scribe are recursion engines. KILL ON SIGHT.""",
        'weight': 0,  # 0 = not yet applied, increments when triggered
    },
    'no_creature': {
        'id': 'board_presence',
        'trigger': 'no_creature',
        'text': """
BOARD PRESENCE (MANDATORY):
- You MUST play at least one creature every turn you have energy to do so.
- An empty board means you take free face damage every turn. This is how you lose.
- Creature priority: Enforcement Sentinel (2/3 Vigilant, taps enemy) > Grid Walker (3/3) > Scout Unit (1/1).
- At 6+ energy: play a finisher. Hive Tyrant (6E, 5/5 + three 1/1 Swift tokens) or Master Strategist (6E, 4/5 Vigilant + draw 2).
- NEVER pass a turn with unspent energy and playable creatures in hand.""",
        'weight': 0,
    },
    'no_bomb': {
        'id': 'finisher_deployment',
        'trigger': 'no_bomb',
        'text': """
FINISHER DEPLOYMENT (when energy >= 5):
- At 5+ energy with no board dominance, play your strongest creature:
  - Hive Tyrant (6E): 5/5 + three 1/1 Swift tokens. Attacks immediately. Best finisher.
  - Master Strategist (6E): 4/5 Vigilant + all creatures gain Vigilant + draw 2. Best when behind.
  - Entropy Incarnate (5E): 4/4 Swift Volatile. Immediate 4 damage. Risk: damages you on death.
  - Temporal Lock (6E): Skip opponent's next turn. Use when you need one more turn to win.
- Do NOT play draw spells (Strategic Reserve, Cycle) when you could play a finisher instead.""",
        'weight': 0,
    },
    'no_attack': {
        'id': 'attack_doctrine',
        'trigger': 'no_attack',
        'text': """
ATTACK DOCTRINE:
- If you have untapped creatures and the opponent's board is empty or weaker, ATTACK.
- declare_attackers with ALL untapped creatures unless you need to hold back a blocker.
- Vigilant creatures attack AND block — always include them in attacks.
- An attack not declared is free HP you gave the opponent.""",
        'weight': 0,
    },
    'no_defense': {
        'id': 'survival_doctrine',
        'trigger': 'no_defense',
        'text': """
SURVIVAL DOCTRINE (when your HP <= 15):
- You are in danger. Prioritize NOT DYING over dealing damage.
- Play Enforcement Sentinel to tap their biggest attacker.
- Play Master Strategist to give everything Vigilant (attack + block).
- Temporal Lock skips their turn — use it to buy time.
- Suppress taps a creature for a turn — use on their biggest threat.
- Keep at least one untapped creature to block.""",
        'weight': 0,
    },
    'wasted_energy': {
        'id': 'energy_efficiency',
        'trigger': 'wasted_energy',
        'text': """
ENERGY EFFICIENCY:
- NEVER end a turn with unspent energy and playable cards in hand.
- At 1E: play Cycle (draw) or Scout Unit (1/1 body).
- At 2E: Precision Strike (removal) or Suppress (tap).
- At 3E: Grid Walker (3/3) or Enforcement Sentinel (2/3 Vigilant) or Purge Protocol (destroy + draw).
- Double-play: at 6E play a 3-drop + 3-drop. At 8E play a 5-drop + 3-drop.
- Resources give bonus energy. Play one per turn if available.""",
        'weight': 0,
    },
    'too_few_cards': {
        'id': 'multi_play',
        'trigger': 'too_few_cards',
        'text': """
TEMPO RECOVERY (when behind on board):
- If you're behind, playing one card per turn is not enough.
- At 8+ energy, play 2-3 cards per turn: removal + creature, or creature + creature.
- Example: Precision Strike (2E) + Hive Tyrant (6E) = 8E total. Removes threat + deploys bomb.
- Example: Grid Walker (3E) + Enforcement Sentinel (3E) + Precision Strike (2E) = 8E. Board + removal.""",
        'weight': 0,
    },
    'invalid_syntax': {
        'id': 'syntax_reminder',
        'trigger': 'invalid_syntax',
        'text': """
CLI SYNTAX (exact format required):
shards games action --id test-game --type play_resource --card_instance_id <instance_id>
shards games action --id test-game --type play_card --card_instance_id <instance_id>
shards games action --id test-game --type play_card --card_instance_id <instance_id> --targets <target_instance_id>
shards games action --id test-game --type declare_attackers --attacker_ids <id1>,<id2>
shards games action --id test-game --type pass
Use the card instance IDs shown in the board state (e.g., card_24, card_27).""",
        'weight': 0,
    },
    'no_resource': {
        'id': 'resource_play',
        'trigger': 'no_resource',
        'text': """
RESOURCE MANAGEMENT:
- Play ONE Primary Node as a resource each turn (if you have one in hand and haven't played a resource yet).
- Resources give +1 max energy permanently. This compounds every turn.
- You can only play ONE resource per turn.
- Do NOT try to play multiple resources in one turn — only the first will succeed.""",
        'weight': 0,
    },
}


# ---------------------------------------------------------------------------
# Build prompt from base + active patches
# ---------------------------------------------------------------------------
def build_prompt(base, patches):
    """Assemble the system prompt from base + all active patches, ordered by weight (most triggered first)."""
    active = sorted(
        [p for p in patches.values() if p['weight'] > 0],
        key=lambda p: -p['weight']
    )
    if not active:
        return base

    patch_text = '\n'.join(p['text'] for p in active)
    return base + '\n' + patch_text


def build_turn_prompt(system_prompt, snap):
    board_text = format_board(snap)
    return f"""{system_prompt}

Here is the current board state:

{board_text}

What do you play? List your CLI commands in order."""


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------
def run_round(model, host, system_prompt, snapshots):
    """Run all snapshots with the given prompt. Return per-turn results and aggregate failures."""
    results = []
    all_failures = []

    for snap in snapshots:
        turn = snap['turn']
        if turn not in RUBRIC:
            continue

        prompt = build_turn_prompt(system_prompt, snap)
        response, elapsed = query_ollama(model, prompt, host)

        if response.startswith('ERROR'):
            results.append({'turn': turn, 'score': 0, 'max': 10, 'pct': 0, 'time': elapsed, 'failures': ['error']})
            continue

        grade = grade_response(turn, response)
        results.append({
            'turn': turn,
            'score': grade['total'],
            'max': grade['max'],
            'pct': grade['pct'],
            'time': elapsed,
            'failures': grade['failures'],
            'response': response[:500],
        })
        all_failures.extend(grade['failures'])

    total_score = sum(r['score'] for r in results)
    total_max = sum(r['max'] for r in results)
    overall_pct = round(100 * total_score / total_max) if total_max > 0 else 0
    avg_time = sum(r['time'] for r in results) / len(results) if results else 0

    return {
        'results': results,
        'total_score': total_score,
        'total_max': total_max,
        'overall_pct': overall_pct,
        'avg_time': avg_time,
        'failure_counts': {f: all_failures.count(f) for f in set(all_failures)},
    }


def main():
    parser = argparse.ArgumentParser(description='LLM Skill Doc Trainer')
    parser.add_argument('--provider', default='ollama')
    parser.add_argument('--model', default='qwen2.5:14b')
    parser.add_argument('--host', default='http://localhost:11434')
    parser.add_argument('--rounds', type=int, default=5)
    parser.add_argument('--target', type=int, default=85, help='Target score %% to converge on')
    parser.add_argument('--snapshots', default=None)
    parser.add_argument('--quick', action='store_true', help='Only 3 key snapshots (T1, T7, T15)')
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--output', '-o', default=None, help='Save final prompt to file')
    args = parser.parse_args()

    # Load snapshots
    snap_path = args.snapshots or os.path.join(os.path.dirname(__file__), 'revenant-snapshots.json')
    if not os.path.exists(snap_path):
        snap_path = '/tmp/revenant-snapshots.json'
    with open(snap_path) as f:
        snapshots = json.load(f)

    if args.quick:
        key_turns = {1, 7, 15}
        snapshots = [s for s in snapshots if s['turn'] in key_turns]

    patches = copy.deepcopy(PATCH_LIBRARY)
    history = []

    print(f"{'='*60}")
    print(f"  SHARDS LLM TRAINER")
    print(f"  Model: {args.model} | Target: {args.target}%")
    print(f"  Snapshots: {len(snapshots)} | Max rounds: {args.rounds}")
    print(f"{'='*60}")
    print()

    for round_num in range(1, args.rounds + 1):
        system_prompt = build_prompt(BASE_PROMPT, patches)
        active_patches = [p['id'] for p in patches.values() if p['weight'] > 0]

        prompt_lines = system_prompt.count('\n') + 1
        print(f"--- Round {round_num}/{args.rounds} ---")
        print(f"  Active patches: {active_patches or '(none — baseline)'}")
        print(f"  Prompt size: {prompt_lines} lines, {len(system_prompt)} chars")

        round_result = run_round(args.model, args.host, system_prompt, snapshots)

        print(f"  Score: {round_result['total_score']}/{round_result['total_max']} ({round_result['overall_pct']}%)")
        print(f"  Avg time/turn: {round_result['avg_time']:.1f}s")

        if round_result['failure_counts']:
            print(f"  Failures: {dict(round_result['failure_counts'])}")
        else:
            print(f"  Failures: NONE")

        # Per-turn breakdown
        for r in round_result['results']:
            bar = '#' * (r['pct'] // 10) + '-' * (10 - r['pct'] // 10)
            fail_str = f" [{', '.join(r['failures'])}]" if r['failures'] else ''
            print(f"    T{r['turn']:<3} {r['score']:>2}/{r['max']:<2} ({r['pct']:>3}%) [{bar}] {r['time']:.1f}s{fail_str}")
            if args.verbose and 'response' in r:
                for line in r['response'].strip().split('\n')[:5]:
                    print(f"         | {line[:100]}")

        history.append({
            'round': round_num,
            'score': round_result['overall_pct'],
            'patches': list(active_patches),
            'failures': dict(round_result['failure_counts']),
        })

        # Check convergence
        if round_result['overall_pct'] >= args.target:
            print(f"\n  *** CONVERGED at {round_result['overall_pct']}% (target: {args.target}%) ***")
            break

        # Check if we're stuck (same score 2 rounds in a row with same patches)
        if len(history) >= 2 and history[-1]['score'] == history[-2]['score'] and \
           set(history[-1]['patches']) == set(history[-2]['patches']):
            print(f"\n  *** STUCK at {round_result['overall_pct']}% — same score with same patches ***")
            # Try boosting the most frequent failure's patch weight
            if round_result['failure_counts']:
                worst = max(round_result['failure_counts'], key=round_result['failure_counts'].get)
                for p in patches.values():
                    if p['trigger'] == worst:
                        p['weight'] += 2  # Extra boost
                        print(f"  Boosting patch '{p['id']}' weight to {p['weight']}")
                        break

        # Apply patches based on failures
        newly_applied = []
        for failure_type, count in round_result['failure_counts'].items():
            for p in patches.values():
                if p['trigger'] == failure_type:
                    old_weight = p['weight']
                    p['weight'] += count  # Weight by frequency
                    if old_weight == 0:
                        newly_applied.append(p['id'])

        if newly_applied:
            print(f"  New patches applied: {newly_applied}")

        print()

    # Final summary
    print(f"\n{'='*60}")
    print(f"  TRAINING COMPLETE")
    print(f"{'='*60}")
    print(f"  Rounds: {len(history)}")
    print(f"  Score progression: {' -> '.join(str(h['score']) + '%' for h in history)}")

    final_prompt = build_prompt(BASE_PROMPT, patches)
    active_final = [p for p in patches.values() if p['weight'] > 0]
    print(f"  Final active patches ({len(active_final)}):")
    for p in sorted(active_final, key=lambda x: -x['weight']):
        print(f"    - {p['id']} (weight: {p['weight']})")

    print(f"  Final prompt: {len(final_prompt)} chars, {final_prompt.count(chr(10)) + 1} lines")

    # Convergence status
    if history and history[-1]['score'] >= args.target:
        print(f"\n  RESULT: CONVERGED at {history[-1]['score']}%")
    elif len(history) >= 2 and history[-1]['score'] > history[0]['score']:
        delta = history[-1]['score'] - history[0]['score']
        print(f"\n  RESULT: IMPROVED by {delta}% ({history[0]['score']}% -> {history[-1]['score']}%)")
    else:
        print(f"\n  RESULT: NO IMPROVEMENT (model may be too weak for this task)")

    # Save final prompt if requested
    if args.output:
        with open(args.output, 'w') as f:
            f.write(final_prompt)
        print(f"  Final prompt saved to: {args.output}")
    else:
        # Default save
        out_path = os.path.join(os.path.dirname(__file__), 'trained-prompt.txt')
        with open(out_path, 'w') as f:
            f.write(final_prompt)
        print(f"  Final prompt saved to: {out_path}")

    # Save training log
    log_path = os.path.join(os.path.dirname(__file__), 'training-log.json')
    with open(log_path, 'w') as f:
        json.dump({
            'model': args.model,
            'target': args.target,
            'rounds': history,
            'final_patches': {p['id']: p['weight'] for p in patches.values() if p['weight'] > 0},
            'final_prompt_length': len(final_prompt),
        }, f, indent=2)
    print(f"  Training log saved to: {log_path}")


if __name__ == '__main__':
    main()
