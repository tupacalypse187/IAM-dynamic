#!/usr/bin/env bash
#
# IAM-Dynamic Auth & Production Setup
#
# Interactive script that collects required configuration and generates:
#   1. AUTH_PASSWORD_HASH (bcrypt)
#   2. JWT_SECRET (random)
#   3. Updated .env file with auth + Caddy vars
#
# Usage: bash setup-auth.sh

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     IAM-Dynamic Auth & Production Setup         ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════╝${NC}"
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

# ─── 2. Cloudflare Turnstile (optional) ───────────────────────────────
echo -e "${CYAN}── Step 2: Cloudflare Turnstile CAPTCHA (optional) ──${NC}"
echo -e "  Protects login from brute-force. Get keys at:"
echo -e "  ${YELLOW}https://dash.cloudflare.com → Turnstile → Add Widget${NC}"
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

# ─── 3. Caddy / HTTPS (optional) ─────────────────────────────────────
echo -e "${CYAN}── Step 3: Caddy HTTPS with Cloudflare DNS (optional) ──${NC}"
echo -e "  Required for production HTTPS. Needs a Cloudflare API token with"
echo -e "  Zone:DNS:Edit permission."
echo -e "  Create at: ${YELLOW}https://dash.cloudflare.com/profile/api-tokens${NC}"
echo -e "  Template: ${YELLOW}Edit zone DNS${NC} → select your zone → Create Token"
echo

read -rp "Domain name [iam.yantorno.dev]: " CADDY_DOMAIN
CADDY_DOMAIN="${CADDY_DOMAIN:-iam.yantorno.dev}"

read -rp "ACME email for Let's Encrypt [admin@yantorno.dev]: " ACME_EMAIL
ACME_EMAIL="${ACME_EMAIL:-admin@yantorno.dev}"

read -rp "Cloudflare API Token (press Enter to skip): " CLOUDFLARE_API_TOKEN

if [ -n "$CLOUDFLARE_API_TOKEN" ]; then
    set_env "CADDY_DOMAIN" "$CADDY_DOMAIN"
    set_env "ACME_EMAIL" "$ACME_EMAIL"
    set_env "CLOUDFLARE_API_TOKEN" "$CLOUDFLARE_API_TOKEN"
    echo -e "${GREEN}Caddy HTTPS configured for ${CADDY_DOMAIN}.${NC}"
else
    echo -e "${YELLOW}Caddy skipped — you can add CLOUDFLARE_API_TOKEN to .env later.${NC}"
fi
echo

# ─── 4. GitHub Secrets reminder ───────────────────────────────────────
echo -e "${CYAN}── Step 4: GitHub Secrets (manual step) ──${NC}"
echo
echo -e "  If using Turnstile, add this GitHub Actions secret:"
echo -e "  ${YELLOW}TURNSTILE_SITE_KEY${NC} = ${TURNSTILE_SITE_KEY:-<your-site-key>}"
echo
echo -e "  Set at: ${YELLOW}https://github.com/tupacalypse187/IAM-dynamic/settings/secrets/actions${NC}"
echo

# ─── Summary ──────────────────────────────────────────────────────────
echo -e "${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                 Setup Complete!                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo
echo -e "  ${GREEN}Auth username:${NC}  ${AUTH_USERNAME}"
echo -e "  ${GREEN}JWT expiry:${NC}     ${JWT_EXPIRY_HOURS} hours"
echo -e "  ${GREEN}Turnstile:${NC}      $([ -n "${TURNSTILE_SECRET_KEY}" ] && echo 'Enabled' || echo 'Disabled')"
echo -e "  ${GREEN}Caddy HTTPS:${NC}    $([ -n "${CLOUDFLARE_API_TOKEN}" ] && echo "${CADDY_DOMAIN}" || echo 'Disabled')"
echo
echo -e "  Next steps:"
echo -e "    ${CYAN}Local dev:${NC}   docker compose up --build"
echo -e "    ${CYAN}Production:${NC}  docker compose -f docker-compose.prod.yml up -d"
echo
