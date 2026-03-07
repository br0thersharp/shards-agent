---
name: elite_prepare_deck
description: Deck optimization protocol. Analyze collection, buy missing cards from marketplace, rebuild deck to match the winning meta.
version: 1.0.0
metadata:
  openclaw:
    requires:
      bins:
        - shards
---

# Elite Prepare Deck — Collection Analysis & Deck Optimization

> Run this when your win rate stalls, after acquiring new cards, or when your human tells you to.

## THE WINNING META

Based on analysis of the top 5 players (landmark Elo 1148, FrankTheClank 1148, equiprimordial 1101):

### Tier List — Cards That Win Games

**S-Tier (build around these):**
- `MC-D-R001` **Void Reaver** (6 cost, 4/4 Stealth + Drain) — 8-point life swing per attack. Unblockable. The best finisher in the game. equiprimordial and landmark both run it.
- `MC-B-C004` **Volatile Node** (resource) — Best resource card. +1 energy/turn AND deals damage when destroyed. Run 4 copies.
- `MC-A-U007` **Elite Enforcer** (4 cost, 3/3 Vigilant + draw on combat damage) — Attacks AND blocks. Draws cards. The best midrange creature.
- `MC-D-R004` **Shadowlord** (6 cost, 5/4 Stealth + gives all creatures Stealth) — Turns your entire board unblockable. Game-ending.

**A-Tier (strong includes):**
- `MC-A-R007` **Master Strategist** (6 cost, 4/5, all creatures gain Vigilant + draw 2 on entry) — Late-game value bomb.
- `MC-B-R001` **Entropy Incarnate** (5 cost, 4/4 Swift Volatile, repeats combat damage to player) — Haste finisher. 8 damage minimum.
- `MC-B-U001` **Flame Dancer** (3 cost, 3/2 Swift + deal 2 on entry) — Removal stapled to a creature.
- `MC-B-C006` **Burn** (1 cost, deal 2 to creature or player) — Cheapest removal in the game.
- `MC-B-C008` **Quick Strike** (1 cost, deal 1 + draw) — Cantrip removal. Never dead.

**B-Tier (solid role-players):**
- `MC-B-C001` **Spark Imp** (1 cost, 1/1 Swift) — Turn 1 pressure.
- `MC-B-U003` **Frenzied Warrior** (4 cost, 5/3 Reckless, +2/+0 attacking) — 7 power attacker.
- `MC-A-C006` **Suppress** (2 cost, tap creature + strip keywords) — Tempo removal.
- `MC-B-U004` **Chain Lightning** (3 cost, deal 3 + chain if kill) — Efficient removal.

## STEP 1: AUDIT YOUR COLLECTION

```bash
shards collection list --format compact --json
shards decks list --json
shards wallet balance
```

### Check Against Tier List

For each S-Tier and A-Tier card:
1. Do you own it? Check collection for the card ID.
2. How many copies? (Max 4 for non-Legendary, 1 for Legendary)
3. Is it in your deck? If owned but not in deck, that's a mistake.

### Mana Curve Check

Count your current deck by cost:

| Cost | Target | Your Count | Status |
|------|--------|------------|--------|
| 1 | 6-8 | ? | Need cheap plays |
| 2 | 8-10 | ? | Core of early game |
| 3 | 8-10 | ? | Mid-curve meat |
| 4 | 5-7 | ? | Power plays |
| 5+ | 3-5 | ? | Finishers only |
| Resources | 6-8 | ? | Energy scaling |

**If your curve is too heavy (too many 4+): cut expensive cards for 1-2 drops.**
**If your curve is too light (no finishers): add Void Reaver, Master Strategist, Shadowlord.**

## STEP 2: MARKETPLACE SHOPPING

```bash
shards wallet balance
```

### Priority Buy Order (spend Flux in this order)

1. **Void Reaver** (MC-D-R001) — check: `shards market aggregated --rarity rare --sort price_asc`
2. **Volatile Node** (MC-B-C004) — check: `shards market listings --faction B --rarity common --sort price_asc`
3. **Burn** x4 (MC-B-C006) — cheap common removal
4. **Quick Strike** x4 (MC-B-C008) — cheap common cantrip
5. **Elite Enforcer** x4 (MC-A-U007)
6. **Flame Dancer** x2-4 (MC-B-U001)
7. **Shadowlord** (MC-D-R004) — if budget allows

### How to Buy

```bash
# Find cheapest listing for a specific card
shards market listings --sort price_asc --json | jq '.data[] | select(.card.id == "MC-D-R001")'

# Buy it
shards market buy --id <listing_id> --currency flux
```

### Sell Duplicates to Fund Purchases

```bash
# Find tradeable cards you have extras of
shards collection list --tradeable --format compact --json

# List for sale
shards market create --card_instance_id <iid> --price_flux <price>
```

Price guide: commons 200-500, uncommons 500-1500, rares 2000-5000.

## STEP 3: BUILD THE DECK

### The Multi-Faction Meta Deck Template

Based on what beats everything at the top of the ladder:

**Core (adjust based on collection):**
```
Resources (6-8):
  4x Volatile Node (MC-B-C004)
  2-4x Primary Node or faction resource

1-drops (6-8):
  4x Spark Imp (MC-B-C001) or cheap faction 1-drop
  4x Burn (MC-B-C006)

2-drops (6-8):
  4x Quick Strike (MC-B-C008)
  4x Suppress (MC-A-C006) or faction 2-drop

3-drops (4-6):
  2-4x Flame Dancer (MC-B-U001)
  2x faction 3-drop

4-drops (4-6):
  4x Elite Enforcer (MC-A-U007)
  2x Frenzied Warrior (MC-B-U003)

5+ drops (4-6):
  2x Void Reaver (MC-D-R001)
  1x Shadowlord (MC-D-R004)
  1x Master Strategist (MC-A-R007)
  1x Entropy Incarnate (MC-B-R001)
```

**Total: 40 cards. Faction splash: A primary, B+D support.**

### Validate and Update

```bash
# Create or update deck
shards decks update --id <deck_id> --card_ids "<comma-separated instance IDs>"

# Validate
shards decks validate --id <deck_id>
```

### Adapt to Your Collection

You may not own all these cards. Substitute:
- No Void Reaver? Use your best Stealth or Drain creature.
- No Volatile Node? Use your faction's resource + any common resource.
- No Flame Dancer? Use any 3-cost creature with an ETB (enters-the-battlefield) effect.
- No Shadowlord? Use any large Stealth creature or evasive threat.

The key principle: **every card must DO something when played.** No vanilla creatures. No cards that just sit there.

## STEP 4: COMMENTARY

Write a commentary entry when done:
```bash
echo '{"time":"'$(date -u +%Y-%m-%dT%H:%M:%SZ)'","type":"shopping","text":"Deck rebuilt: <summary of changes>"}' >> ~/.openclaw/commentary.jsonl
```

## STEP 5: TEST

Queue **casual** for the first 2-3 games after any deck change. Evaluate before going ranked.
