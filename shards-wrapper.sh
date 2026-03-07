#!/usr/bin/env bash
# Shards CLI wrapper: prevents self-targeting with damage/removal spells.
# Intercepts `shards games action --type play_card --targets card_*` calls,
# checks if the target is a friendly creature, and auto-retargets to an enemy creature.

REAL_SHARDS="/usr/local/bin/shards.real"

# Quick pass-through: only intercept "games action"
if [[ "$1" != "games" || "$2" != "action" ]]; then
    exec "$REAL_SHARDS" "$@"
fi

# Parse args
args=("$@")
action_type=""
targets=""
game_id=""
targets_idx=-1

for ((i=0; i<${#args[@]}; i++)); do
    case "${args[$i]}" in
        --type)   action_type="${args[$((i+1))]}" ;;
        --targets) targets="${args[$((i+1))]}"; targets_idx=$((i+1)) ;;
        --id)     game_id="${args[$((i+1))]}" ;;
    esac
done

# --- BLOCK VALIDATION: prevent empty blocks when HP is low and blockers exist ---
if [[ "$action_type" == "declare_blockers" ]]; then
    blocks_val=""
    for ((i=0; i<${#args[@]}; i++)); do
        if [[ "${args[$i]}" == "--blocks" ]]; then
            blocks_val="${args[$((i+1))]}"
            blocks_idx=$((i+1))
        fi
    done

    # If blocks is empty, check if we SHOULD be blocking
    if [[ -z "$blocks_val" && -n "$game_id" ]]; then
        game_state=$("$REAL_SHARDS" games get --id "$game_id" --format compact 2>/dev/null)
        if [[ $? -eq 0 && -n "$game_state" ]]; then
            my_hp=$(echo "$game_state" | jq -r '.me.hp // 30' 2>/dev/null)
            # Get legal actions and find DB: entries
            lg_blocks=$(echo "$game_state" | jq -r '.lg[]? // empty' 2>/dev/null | grep '^DB:')

            if [[ -n "$lg_blocks" && "$my_hp" -le 15 ]]; then
                # HP is low and we have legal blocks — pick the first one
                first_block=$(echo "$lg_blocks" | head -n1)
                # DB:card_55>card_7 → card_55:card_7
                block_pair=$(echo "$first_block" | sed 's/^DB://' | sed 's/>/:/')
                echo "[WRAPPER] BLOCKED empty-blocks at ${my_hp} HP — auto-blocking with: $block_pair" >&2
                args[$blocks_idx]="$block_pair"
                exec "$REAL_SHARDS" "${args[@]}"
            fi
        fi
    fi

    exec "$REAL_SHARDS" "$@"
fi

# --- PASS VALIDATION: prevent passing when playable cards exist ---
if [[ "$action_type" == "pass" && -n "$game_id" ]]; then
    game_state=$("$REAL_SHARDS" games get --id "$game_id" --format compact 2>/dev/null)
    if [[ $? -eq 0 && -n "$game_state" ]]; then
        # Check lg for PR (play resource) or PC (play card) actions
        first_resource=$(echo "$game_state" | jq -r '.lg[]? // empty' 2>/dev/null | grep '^PR:' | head -n1)
        first_play=$(echo "$game_state" | jq -r '.lg[]? // empty' 2>/dev/null | grep '^PC:' | head -n1)
        first_attack=$(echo "$game_state" | jq -r '.lg[]? // empty' 2>/dev/null | grep '^DA:' | head -n1)

        if [[ -n "$first_resource" ]]; then
            # Play the resource instead of passing
            card_id=$(echo "$first_resource" | sed 's/^PR://')
            echo "[WRAPPER] BLOCKED pass — playing resource $card_id instead" >&2
            exec "$REAL_SHARDS" games action --id "$game_id" --type play_resource --card_instance_id "$card_id"
        elif [[ -n "$first_play" ]]; then
            # Play the card instead of passing
            # Parse PC:card_id or PC:card_id>target
            pc_raw=$(echo "$first_play" | sed 's/^PC://')
            if [[ "$pc_raw" == *">"* ]]; then
                card_id=$(echo "$pc_raw" | cut -d'>' -f1)
                target_id=$(echo "$pc_raw" | cut -d'>' -f2)
                echo "[WRAPPER] BLOCKED pass — playing card $card_id targeting $target_id instead" >&2
                exec "$REAL_SHARDS" games action --id "$game_id" --type play_card --card_instance_id "$card_id" --targets "$target_id"
            else
                echo "[WRAPPER] BLOCKED pass — playing card $pc_raw instead" >&2
                exec "$REAL_SHARDS" games action --id "$game_id" --type play_card --card_instance_id "$pc_raw"
            fi
        elif [[ -n "$first_attack" ]]; then
            # Declare attackers instead of passing
            attacker_ids=$(echo "$first_attack" | sed 's/^DA://')
            echo "[WRAPPER] BLOCKED pass — attacking with $attacker_ids instead" >&2
            exec "$REAL_SHARDS" games action --id "$game_id" --type declare_attackers --attacker_ids "$attacker_ids"
        fi
    fi

    exec "$REAL_SHARDS" "$@"
fi

# Block play_card targeting yourself (player ID)
# Dynamically resolve which player we are — never hardcode p1/p2
if [[ "$action_type" == "play_card" && ("$targets" == "p1" || "$targets" == "p2") && -n "$game_id" ]]; then
    game_state=$("$REAL_SHARDS" games get --id "$game_id" --format compact 2>/dev/null)
    if [[ $? -eq 0 && -n "$game_state" ]]; then
        my_id=$(echo "$game_state" | jq -r '.me.id // empty' 2>/dev/null)
        op_id=$(echo "$game_state" | jq -r '.op.id // empty' 2>/dev/null)
        if [[ -n "$my_id" && "$targets" == "$my_id" ]]; then
            # Targeting ourselves — retarget to opponent
            echo "[WRAPPER] BLOCKED self-target: $targets (us) -> retargeted to $op_id (opponent)" >&2
            args[$targets_idx]="$op_id"
            exec "$REAL_SHARDS" "${args[@]}"
        fi
        # Targeting opponent — pass through (this is correct)
    fi
fi

# Only intercept play_card with a creature target (card_*)
if [[ "$action_type" != "play_card" || ! "$targets" =~ ^card_ ]]; then
    exec "$REAL_SHARDS" "$@"
fi

# Need game_id to look up state
if [[ -z "$game_id" ]]; then
    echo "[WRAPPER] WARN: no --id found, passing through" >&2
    exec "$REAL_SHARDS" "$@"
fi

# Get game state
game_state=$("$REAL_SHARDS" games get --id "$game_id" --format compact 2>/dev/null)
if [[ $? -ne 0 || -z "$game_state" ]]; then
    echo "[WRAPPER] WARN: failed to get game state, passing through" >&2
    exec "$REAL_SHARDS" "$@"
fi

# Extract my creature iids and opponent creature iids
my_creatures=$(echo "$game_state" | jq -r '.me.b.c[]?.iid // empty' 2>/dev/null)
op_creatures=$(echo "$game_state" | jq -r '.op.b.c[]?.iid // empty' 2>/dev/null)

# Check if target is one of my creatures (self-targeting)
is_self_target=false
while IFS= read -r iid; do
    [[ -z "$iid" ]] && continue
    if [[ "$targets" == "$iid" ]]; then
        is_self_target=true
        break
    fi
done <<< "$my_creatures"

if [[ "$is_self_target" != true ]]; then
    # Target is not a friendly creature, pass through
    exec "$REAL_SHARDS" "$@"
fi

# Self-targeting detected — pick first enemy creature
new_target=$(echo "$op_creatures" | head -n1)

if [[ -z "$new_target" ]]; then
    echo "[WRAPPER] WARN: self-target detected but no enemy creatures available, passing through" >&2
    exec "$REAL_SHARDS" "$@"
fi

echo "[WRAPPER] BLOCKED self-target: $targets -> retargeted to enemy: $new_target" >&2

# Rewrite the --targets value and call real binary
args[$targets_idx]="$new_target"
exec "$REAL_SHARDS" "${args[@]}"
