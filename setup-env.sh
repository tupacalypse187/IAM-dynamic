#!/usr/bin/env bash
# =============================================================================
# setup-env.sh — Interactive .env builder / editor for IAM-Dynamic
#
# Walks through AI providers, AWS account details, and Slack integration.
# For every value that already exists in .env it shows a masked preview so
# you can verify it, then keep it as-is or replace it. Missing values are
# prompted for (secrets are entered with hidden input).
#
# Usage:
#   ./setup-env.sh            # interactive
#   ./setup-env.sh --fresh    # start from .env.example (existing .env kept as .env.bak)
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
EXAMPLE_FILE="${SCRIPT_DIR}/.env.example"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# ─── .env primitives ───────────────────────────────────────────────────

# Read a value from .env (strips surrounding quotes and inline comments).
get_env() {
    [ -f "$ENV_FILE" ] || return 1
    local line
    line=$(grep -m1 "^$1=" "$ENV_FILE" 2>/dev/null) || return 1
    printf '%s' "${line#*=}" | sed 's/^"//; s/"$//; s/[[:space:]]*#.*$//'
}

# Write KEY=VALUE: replaces an existing (uncommented) line or appends.
set_env() {
    local key="$1" value="$2"
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        awk -v k="$key" -v v="$value" '
            $0 ~ "^" k "=" { print k "=" v; replaced=1; next }
            { print }
            END { if (!replaced) print k "=" v }
        ' "$ENV_FILE" > "${ENV_FILE}.tmp" && mv "${ENV_FILE}.tmp" "$ENV_FILE"
    else
        printf '%s=%s\n' "$key" "$value" >> "$ENV_FILE"
    fi
}

# ─── Helpers ───────────────────────────────────────────────────────────

# Mask a secret for display: first 4 + last 4 characters.
mask() {
    local v="$1" len
    len=${#v}
    if [ -z "$v" ]; then
        printf '%s' "${YELLOW}(not set)${NC}"
    elif [ "$len" -le 10 ]; then
        printf '%s' "**** (${len} chars)"
    else
        printf '%s' "${v:0:4}…${v: -4} (${len} chars)"
    fi
}

# Ask a yes/no question. $1=question, $2=default (y|n).
confirm() {
    local question="$1" default="$2" hint answer
    if [ "$default" = "y" ]; then hint="[Y/n]"; else hint="[y/N]"; fi
    while true; do
        read -rp "$(printf '%b' "${question} ${hint} ")" answer
        answer=${answer:-$default}
        case "$answer" in
            [Yy]*) return 0 ;;
            [Nn]*) return 1 ;;
            *) printf '  Please answer y or n.\n' ;;
        esac
    done
}

# Prompt for a secret with hidden input; empty keeps any existing value.
prompt_secret() {  # prompt_secret <key> <label> <url-hint>
    local key="$1" label="$2" url_hint="$3" existing value
    existing=$(get_env "$key" 2>/dev/null || true)

    if [ -n "$existing" ]; then
        printf '  Current %s: ' "$label"
        mask "$existing"; printf '\n'
        if confirm "  Keep this value?" "y"; then
            printf '  %b kept.\n' "${GREEN}${label}${NC}"
            return 0
        fi
    fi
    [ -n "$url_hint" ] && printf '  Get it at: %b\n' "${YELLOW}${url_hint}${NC}"
    printf '  Enter %s (input hidden, blank to skip): ' "$label"
    read -rs value
    printf '\n'
    if [ -n "$value" ]; then
        set_env "$key" "$value"
        printf '  %b saved.\n' "${GREEN}${label}${NC}"
    else
        printf '  %b skipped.\n' "${YELLOW}${label}${NC}"
    fi
}

# Prompt for a plain (visible) value with a default.
prompt_value() {  # prompt_value <key> <label> <default>
    local key="$1" label="$2" default="$3" existing value
    existing=$(get_env "$key" 2>/dev/null || true)
    local show="${existing:-$default}"

    printf '  Current %s: %s\n' "$label" "$( [ -n "$existing" ] && printf '%s' "$existing" || printf '%s' "${YELLOW}(not set)${NC}")"
    read -rp "$(printf '%b' "  ${label} [${show}]: ")" value
    value=${value:-$show}
    set_env "$key" "$value"
    printf '  %b saved: %s\n' "${GREEN}${label}${NC}" "$value"
}

# ─── Init ──────────────────────────────────────────────────────────────

# Neutralise the example's uncommented placeholder values
neutralise_placeholders() {
    awk '{
        if ($0 ~ /^(GOOGLE_API_KEY|SLACK_WEBHOOK_URL)=/) print "# " $0
        else print
    }' "$ENV_FILE" > "${ENV_FILE}.tmp" && mv "${ENV_FILE}.tmp" "$ENV_FILE"
}

if [ "${1:-}" = "--fresh" ]; then
    if [ -f "$ENV_FILE" ]; then
        cp "$ENV_FILE" "${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"
        printf '%b A backup of your current .env was saved next to it.\n' "${YELLOW}ℹ${NC}"
    fi
    cp "$EXAMPLE_FILE" "$ENV_FILE"
    neutralise_placeholders
    printf '%b Started a fresh .env from the template.\n\n' "${GREEN}✓${NC}"
elif [ ! -f "$ENV_FILE" ]; then
    cp "$EXAMPLE_FILE" "$ENV_FILE"
    neutralise_placeholders
    printf '%b Created .env from the template.\n\n' "${GREEN}✓${NC}"
fi

printf '%b' "${CYAN}${BOLD}═══════════════════════════════════════════════════════════${NC}\n"
printf '%b' "${CYAN}${BOLD}  IAM-Dynamic .env Setup${NC}\n"
printf '%b' "${CYAN}${BOLD}  Existing values are shown masked — keep or replace them.${NC}\n"
printf '%b' "${CYAN}${BOLD}═══════════════════════════════════════════════════════════${NC}\n\n"

# ─── 1. AI Providers ───────────────────────────────────────────────────

printf '%b' "${CYAN}${BOLD}── 1. AI Providers ──${NC}\n"
printf '  Choose which providers to configure. Configure as many as you\n'
printf '  have keys for — you can switch between them in the UI at runtime.\n\n'

declare -a PROVIDER_IDS=(gemini openai anthropic zhipu muse openrouter)
declare -A PROVIDER_NAMES=(
    [gemini]="Google Gemini"
    [openai]="OpenAI"
    [anthropic]="Anthropic Claude"
    [zhipu]="Z.AI GLM"
    [muse]="Meta Muse"
    [openrouter]="OpenRouter (gateway)"
)
declare -A PROVIDER_KEYS=(
    [gemini]="GOOGLE_API_KEY"
    [openai]="OPENAI_API_KEY"
    [anthropic]="ANTHROPIC_API_KEY"
    [zhipu]="ZAI_API_KEY"
    [muse]="MUSE_API_KEY"
    [openrouter]="OPENROUTER_API_KEY"
)
declare -A MODEL_KEYS=(
    [gemini]="GEMINI_MODEL"
    [openai]="OPENAI_MODEL"
    [anthropic]="ANTHROPIC_MODEL"
    [zhipu]="ZAI_MODEL"
    [muse]="MUSE_MODEL"
    [openrouter]="OPENROUTER_MODEL"
)
declare -A MODEL_DEFAULTS=(
    [gemini]="gemini-3.1-pro-preview"
    [openai]="gpt-5.6"
    [anthropic]="claude-opus-5"
    [zhipu]="glm-5.3"
    [muse]="muse-spark-1.3-contributor"
    [openrouter]="z-ai/glm-5.3"
)
declare -A KEY_URLS=(
    [gemini]="https://aistudio.google.com/apikey"
    [openai]="https://platform.openai.com/api-keys"
    [anthropic]="https://console.anthropic.com/settings/keys"
    [zhipu]="https://api.z.ai"
    [muse]="https://ai.developer.meta.com/"
    [openrouter]="https://openrouter.ai/settings/keys"
)

declare -a CONFIGURED=()

for pid in "${PROVIDER_IDS[@]}"; do
    name="${PROVIDER_NAMES[$pid]}"
    key_var="${PROVIDER_KEYS[$pid]}"
    existing=$(get_env "$key_var" 2>/dev/null || true)

    if [ -n "$existing" ]; then
        printf '%b' "  ${GREEN}●${NC} ${name} — API key set: "
        mask "$existing"; printf '\n'
        if confirm "    Review / re-enter this provider's key?" "n"; then
            prompt_secret "$key_var" "${name} API key" "${KEY_URLS[$pid]}"
        else
            printf '    %b kept.\n' "${GREEN}${name} key${NC}"
        fi
        CONFIGURED+=("$pid")
    else
        printf '%b' "  ${YELLOW}○${NC} ${name} — not configured\n"
        if confirm "    Configure ${name}?" "n"; then
            prompt_secret "$key_var" "${name} API key" "${KEY_URLS[$pid]}"
            if [ -n "$(get_env "$key_var" 2>/dev/null || true)" ]; then
                CONFIGURED+=("$pid")
            fi
        fi
    fi
done

# Model per configured provider (kept as-is unless you change it)
printf '\n  %b Model selection for configured providers\n' "${CYAN}${BOLD}›${NC}"
for pid in "${CONFIGURED[@]:-}"; do
    [ -z "$pid" ] && continue
    name="${PROVIDER_NAMES[$pid]}"
    model_key="${MODEL_KEYS[$pid]}"
    default="${MODEL_DEFAULTS[$pid]}"
    existing=$(get_env "$model_key" 2>/dev/null || true)
    show="${existing:-$default}"
    read -rp "$(printf '%b' "    ${name} model [${show}]: ")" value
    value=${value:-$show}
    set_env "$model_key" "$value"
done

# Default LLM_PROVIDER: prefer the single configured provider
if [ "${#CONFIGURED[@]}" -ge 1 ]; then
    current_provider=$(get_env "LLM_PROVIDER" 2>/dev/null || true)
    printf '\n  Current default provider: %s\n' "${current_provider:-${YELLOW}(not set)${NC}}"
    if [ "${#CONFIGURED[@]}" -eq 1 ]; then
        suggestion="${CONFIGURED[0]}"
    else
        printf '  Configured providers:\n'
        local_i=1
        for pid in "${CONFIGURED[@]}"; do
            printf '    %d) %s\n' "$local_i" "${PROVIDER_NAMES[$pid]}"
            local_i=$((local_i + 1))
        done
        read -rp "$(printf '%b' "  Which should be the default? [${CONFIGURED[0]}]: ")" pick
        pick=${pick:-1}
        if [[ "$pick" =~ ^[0-9]+$ ]] && [ "$pick" -ge 1 ] && [ "$pick" -le "${#CONFIGURED[@]}" ]; then
            suggestion="${CONFIGURED[$((pick - 1))]}"
        else
            suggestion="${CONFIGURED[0]}"
        fi
    fi
    read -rp "$(printf '%b' "  Default LLM_PROVIDER [${suggestion}]: ")" provider_choice
    provider_choice=${provider_choice:-$suggestion}
    set_env "LLM_PROVIDER" "$provider_choice"
fi

# ─── 2. AWS ────────────────────────────────────────────────────────────

printf '\n%b' "${CYAN}${BOLD}── 2. AWS Account ──${NC}\n"
printf '  Note: AWS session tokens are temporary (STS-issued per request) and\n'
printf '  are never stored in .env. The app assumes the role configured below.\n\n'

prompt_value "AWS_ACCOUNT_ID" "AWS account ID (12 digits)" "123456789012"
prompt_value "AWS_ROLE_NAME"  "IAM role to assume"          "AgentPOCSessionRole"
prompt_value "AWS_DEFAULT_REGION" "Default region"          "us-east-1"

# ─── 3. Slack ──────────────────────────────────────────────────────────

printf '\n%b' "${CYAN}${BOLD}── 3. Slack Integration (optional) ──${NC}\n"
prompt_secret "SLACK_WEBHOOK_URL" "Slack webhook URL" "https://api.slack.com/messaging/webhooks"

# ─── 4. Approver (optional) ────────────────────────────────────────────

printf '\n%b' "${CYAN}${BOLD}── 4. Approver Name (optional) ──${NC}\n"
prompt_value "APPROVER_NAME" "Approver display name" "Admin"

# ─── Summary ───────────────────────────────────────────────────────────

printf '\n%b' "${CYAN}${BOLD}═══════════════════════════════════════════════════════════${NC}\n"
printf '%b  Setup complete. Summary:\n\n' "${GREEN}✓${NC}"

for pid in "${PROVIDER_IDS[@]}"; do
    key_var="${PROVIDER_KEYS[$pid]}"
    existing=$(get_env "$key_var" 2>/dev/null || true)
    if [ -n "$existing" ]; then
        model=$(get_env "${MODEL_KEYS[$pid]}" 2>/dev/null || echo "default")
        printf '    %b %-18s %s (model: %s)\n' "${GREEN}●${NC}" "${PROVIDER_NAMES[$pid]}" "$(mask "$existing")" "$model"
    fi
done
printf '    AWS account:  %s (role: %s)\n' "$(get_env AWS_ACCOUNT_ID 2>/dev/null || echo '?')" "$(get_env AWS_ROLE_NAME 2>/dev/null || echo '?')"
printf '    Slack:        %s\n' "$(mask "$(get_env SLACK_WEBHOOK_URL 2>/dev/null || true)")"
printf '\n  Default provider: %s\n' "$(get_env LLM_PROVIDER 2>/dev/null || echo '?')"
printf '  %b Restart the backend after changing .env values.\n' "${YELLOW}ℹ${NC}"
printf '%b' "${CYAN}${BOLD}═══════════════════════════════════════════════════════════${NC}\n"
