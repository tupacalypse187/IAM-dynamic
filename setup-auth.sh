#!/usr/bin/env bash
#
# IAM-Dynamic Auth & Environment Setup
#
# Interactive script that collects required configuration and generates:
#   1. AUTH_PASSWORD_HASH (bcrypt)
#   2. JWT_SECRET (random)
#   3. Updated .env file with auth + (optionally) Caddy/Turnstile vars
#
# Usage:
#   bash setup-auth.sh --dev     # Local dev — auth only, skip Turnstile/Caddy
#   bash setup-auth.sh --prod    # Production  — full setup with Caddy HTTPS + Turnstile
#   bash setup-auth.sh           # Interactive — asks which mode

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ─── Parse mode ───────────────────────────────────────────────────────
MODE=""
case "${1:-}" in
    --dev)  MODE="dev" ;;
    --prod) MODE="prod" ;;
    -h|--help)
        echo "Usage: bash setup-auth.sh [--dev|--prod]"
        echo
        echo "  --dev   Local development — sets up auth only (skip Turnstile/Caddy)"
        echo "  --prod  Production — full setup with Caddy HTTPS and Turnstile CAPTCHA"
        echo "  (none)  Interactive — asks which mode to use"
        exit 0
        ;;
esac

if [ -z "$MODE" ]; then
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║       IAM-Dynamic Environment Setup             ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
    echo
    echo "  1) dev   — Local development (auth only)"
    echo "  2) prod  — Production (auth + Caddy HTTPS + Turnstile)"
    echo
    read -rp "Select mode [1/2]: " mode_choice
    case "$mode_choice" in
        1|dev)  MODE="dev" ;;
        2|prod) MODE="prod" ;;
        *)
            echo -e "${RED}Invalid choice. Run with --help for usage.${NC}"
            exit 1
            ;;
    esac
fi

if [ "$MODE" = "dev" ]; then
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║       IAM-Dynamic Dev Setup                     ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
else
    echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║       IAM-Dynamic Production Setup              ║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
fi
echo

# ─── Check dependencies ───────────────────────────────────────────────
check_deps() {
    local missing=()
    if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
        missing+=("python3")
    fi
    if [ ${#missing[@]} -gt 0 ]; then
        echo -e "${RED}Missing dependencies: ${missing[*]}${NC}"
        echo "Please install them and re-run this script."
        exit 1
    fi
}
check_deps

PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)

# Ensure passlib is available
if ! $PYTHON -c "from passlib.hash import bcrypt" 2>/dev/null; then
    echo -e "${YELLOW}Installing passlib[bcrypt]...${NC}"
    $PYTHON -m pip install -q "passlib[bcrypt]>=1.7.4"
fi

# ─── Locate .env file ─────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}No .env file found at ${ENV_FILE}${NC}"
    echo "Creating a new .env file. You can add AI provider keys later."
    touch "$ENV_FILE"
fi

echo -e "${GREEN}Using .env file:${NC} ${ENV_FILE}"
echo

# ─── Helper: add or update a key in .env ──────────────────────────────
set_env() {
    local key="$1" value="$2"
    if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
        # Update existing (use | as sed delimiter since values may contain /)
        sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    elif grep -q "^# *${key}=" "$ENV_FILE" 2>/dev/null; then
        # Uncomment and set
        sed -i "s|^# *${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
        echo "${key}=${value}" >> "$ENV_FILE"
    fi
}

# ─── 1. Authentication ────────────────────────────────────────────────
echo -e "${CYAN}── Step 1: Authentication ──${NC}"
echo

read -rp "Admin username [admin]: " AUTH_USERNAME
AUTH_USERNAME="${AUTH_USERNAME:-admin}"

while true; do
    echo -n "Admin password: "
    read -rs AUTH_PASSWORD
    echo
    echo -n "Confirm password: "
    read -rs AUTH_PASSWORD_CONFIRM
    echo
    if [ "$AUTH_PASSWORD" = "$AUTH_PASSWORD_CONFIRM" ]; then
        if [ -z "$AUTH_PASSWORD" ]; then
            echo -e "${RED}Password cannot be empty.${NC}"
            continue
        fi
        break
    else
        echo -e "${RED}Passwords do not match. Try again.${NC}"
    fi
done

echo -e "${YELLOW}Generating bcrypt hash...${NC}"
AUTH_PASSWORD_HASH=$(IAM_PASSWORD="$AUTH_PASSWORD" $PYTHON -c "
import os
from passlib.hash import bcrypt
print(bcrypt.hash(os.environ['IAM_PASSWORD']))
")

# Generate JWT secret (random 48-char base64 string)
JWT_SECRET=$($PYTHON -c "import secrets; print(secrets.token_urlsafe(36))")

read -rp "JWT session duration in hours [8]: " JWT_EXPIRY_HOURS
JWT_EXPIRY_HOURS="${JWT_EXPIRY_HOURS:-8}"

set_env "AUTH_USERNAME" "$AUTH_USERNAME"
set_env "AUTH_PASSWORD_HASH" "$AUTH_PASSWORD_HASH"
set_env "JWT_SECRET" "$JWT_SECRET"
set_env "JWT_EXPIRY_HOURS" "$JWT_EXPIRY_HOURS"

echo -e "${GREEN}Auth configured.${NC}"
echo

# ─── Track what was configured for summary ────────────────────────────
TURNSTILE_SECRET_KEY=""
CLOUDFLARE_API_TOKEN=""
CADDY_DOMAIN=""
TURNSTILE_SITE_KEY=""

# ─── 2. Cloudflare Turnstile (prod only) ──────────────────────────────
if [ "$MODE" = "prod" ]; then
    echo -e "${CYAN}── Step 2: Cloudflare Turnstile CAPTCHA (optional) ──${NC}"
    echo -e "  Protects login from brute-force. Get keys at:"
    echo -e "  ${YELLOW}https://dash.cloudflare.com → Turnstile → Add Widget${NC}"
    echo
    echo -e "  Create a widget for your domain, then copy the Site Key and Secret Key."
    echo

    read -rp "Turnstile Site Key (public, press Enter to skip): " TURNSTILE_SITE_KEY
    read -rp "Turnstile Secret Key (server, press Enter to skip): " TURNSTILE_SECRET_KEY

    if [ -n "$TURNSTILE_SECRET_KEY" ]; then
        set_env "TURNSTILE_SECRET_KEY" "$TURNSTILE_SECRET_KEY"
        echo -e "${GREEN}Turnstile server key configured.${NC}"
    else
        echo -e "${YELLOW}Turnstile skipped — login will work without CAPTCHA.${NC}"
    fi
    echo
fi

# ─── 3. Caddy / HTTPS (prod only) ────────────────────────────────────
if [ "$MODE" = "prod" ]; then
    echo -e "${CYAN}── Step 3: Caddy HTTPS with Cloudflare DNS ──${NC}"
    echo -e "  Required for production HTTPS. Needs a Cloudflare API token with"
    echo -e "  Zone:DNS:Edit permission."
    echo -e "  Create at: ${YELLOW}https://dash.cloudflare.com/profile/api-tokens${NC}"
    echo -e "  Template: ${YELLOW}Edit zone DNS${NC} → select your zone → Create Token"
    echo

    read -rp "Domain name [iam.yantorno.dev]: " CADDY_DOMAIN
    CADDY_DOMAIN="${CADDY_DOMAIN:-iam.yantorno.dev}"

    read -rp "ACME email for Let's Encrypt [admin@yantorno.dev]: " ACME_EMAIL
    ACME_EMAIL="${ACME_EMAIL:-admin@yantorno.dev}"

    read -rp "Cloudflare API Token: " CLOUDFLARE_API_TOKEN

    if [ -n "$CLOUDFLARE_API_TOKEN" ]; then
        set_env "CADDY_DOMAIN" "$CADDY_DOMAIN"
        set_env "ACME_EMAIL" "$ACME_EMAIL"
        set_env "CLOUDFLARE_API_TOKEN" "$CLOUDFLARE_API_TOKEN"
        echo -e "${GREEN}Caddy HTTPS configured for ${CADDY_DOMAIN}.${NC}"
    else
        echo -e "${RED}Warning: Caddy requires CLOUDFLARE_API_TOKEN for TLS certificates.${NC}"
        echo -e "${YELLOW}You must add it to .env before running docker-compose.prod.yml.${NC}"
    fi
    echo
fi

# ─── 4. GitHub Secrets reminder (prod only) ───────────────────────────
if [ "$MODE" = "prod" ]; then
    echo -e "${CYAN}── Step 4: GitHub Secrets (manual step) ──${NC}"
    echo
    if [ -n "$TURNSTILE_SITE_KEY" ]; then
        echo -e "  Add this GitHub Actions secret for the Turnstile build arg:"
        echo -e "  ${YELLOW}TURNSTILE_SITE_KEY${NC} = ${TURNSTILE_SITE_KEY}"
        echo
    fi
    echo -e "  Set secrets at: ${YELLOW}https://github.com/tupacalypse187/IAM-dynamic/settings/secrets/actions${NC}"
    echo
fi

# ─── Summary ──────────────────────────────────────────────────────────
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                 Setup Complete!                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo
echo -e "  ${GREEN}Mode:${NC}           ${MODE}"
echo -e "  ${GREEN}Auth username:${NC}  ${AUTH_USERNAME}"
echo -e "  ${GREEN}JWT expiry:${NC}     ${JWT_EXPIRY_HOURS} hours"
if [ "$MODE" = "prod" ]; then
    echo -e "  ${GREEN}Turnstile:${NC}      $([ -n "${TURNSTILE_SECRET_KEY}" ] && echo 'Enabled' || echo 'Disabled')"
    echo -e "  ${GREEN}Caddy HTTPS:${NC}    $([ -n "${CLOUDFLARE_API_TOKEN}" ] && echo "${CADDY_DOMAIN}" || echo 'Not configured')"
fi
echo
echo -e "  Next steps:"
if [ "$MODE" = "dev" ]; then
    echo -e "    ${CYAN}docker compose up --build${NC}"
    echo -e "    Then open ${YELLOW}http://localhost:8080${NC}"
else
    echo -e "    ${CYAN}docker compose -f docker-compose.prod.yml up -d${NC}"
    if [ -n "$CADDY_DOMAIN" ]; then
        echo -e "    Then open ${YELLOW}https://${CADDY_DOMAIN}${NC}"
    fi
fi
echo
