# Contabo Ubuntu VPS Setup Guide

This guide walks through setting up your Contabo Ubuntu VPS to receive automated deployments from GitHub Actions.

## Prerequisites

- A Contabo VPS with Ubuntu (22.04 or 24.04 recommended)
- Root SSH access to the VPS
- Your IAM-Dynamic repo at https://github.com/tupacalypse187/IAM-dynamic

---

## 1. Initial Server Access

```bash
ssh root@<your-contabo-ip>
```

## 2. Create a Deploy User

Don't run containers as root. Create a dedicated `deploy` user:

```bash
adduser deploy
usermod -aG sudo deploy
```

## 3. Install Docker & Docker Compose

```bash
# Install Docker using the official convenience script
curl -fsSL https://get.docker.com | sh

# Add deploy user to docker group (avoids needing sudo for docker commands)
usermod -aG docker deploy

# Verify installation
docker --version
docker compose version
```

> **Note:** Log out and back in as `deploy` for the docker group membership to take effect.

## 4. Set Up SSH Key Authentication for GitHub Actions

On **your local machine**, generate a dedicated deploy key:

```bash
ssh-keygen -t ed25519 -C "iam-dynamic-deploy" -f ~/.ssh/iam_dynamic_deploy
# Press Enter for no passphrase (required for automated deploys)
```

Copy the **public key** to the VPS:

```bash
ssh-copy-id -i ~/.ssh/iam_dynamic_deploy.pub deploy@<your-contabo-ip>
```

Verify passwordless login works:

```bash
ssh -i ~/.ssh/iam_dynamic_deploy deploy@<your-contabo-ip>
```

## 5. Create the Application Directory

On the VPS as the `deploy` user:

```bash
sudo mkdir -p /opt/iam-dynamic
sudo chown deploy:deploy /opt/iam-dynamic
```

## 6. Copy Production Files to the VPS

From your local machine, copy `docker-compose.prod.yml`:

```bash
scp docker-compose.prod.yml deploy@<your-contabo-ip>:/opt/iam-dynamic/
```

## 7. Create the `.env` File on the VPS

SSH into the VPS and create the environment file with your secrets:

```bash
ssh deploy@<your-contabo-ip>

cat > /opt/iam-dynamic/.env << 'EOF'
# ============================================
# AI Provider Configuration
# ============================================
LLM_PROVIDER=gemini

# --- Gemini (Google) ---
GOOGLE_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-3-pro-preview

# --- OpenAI (optional) ---
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-5.1

# --- Anthropic Claude (optional) ---
# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-opus-4-5-20251101

# --- Zhipu GLM (optional) ---
# ZHIPUAI_API_KEY=...
# ZHIPUAI_MODEL=glm-4.7

# ============================================
# AWS Configuration
# ============================================
AWS_ACCOUNT_ID=123456789012
AWS_ROLE_NAME=AgentPOCSessionRole
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1

# ============================================
# Authentication (required for production)
# ============================================
AUTH_USERNAME=admin
AUTH_PASSWORD_HASH=$2b$12$...   # Generate with: python backend/scripts/hash_password.py
JWT_SECRET=your-random-secret-at-least-32-characters
JWT_EXPIRY_HOURS=8

# Cloudflare Turnstile CAPTCHA (optional but recommended)
# TURNSTILE_SECRET_KEY=0x...

# ============================================
# Caddy / HTTPS
# ============================================
CLOUDFLARE_API_TOKEN=your-cloudflare-api-token
CADDY_DOMAIN=iam.yantorno.dev
ACME_EMAIL=admin@yantorno.dev

# ============================================
# Optional
# ============================================
APPROVER_NAME=Admin
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
EOF

chmod 600 /opt/iam-dynamic/.env
```

### Generate the password hash

On your local machine (or the VPS):

```bash
cd IAM-Dynamic
pip install passlib[bcrypt]
python backend/scripts/hash_password.py
# Enter your password, then copy the AUTH_PASSWORD_HASH=... output into .env
```

## 8. Authenticate Docker with GHCR

The VPS needs to pull container images from GitHub Container Registry (GHCR).

### Create a GitHub Personal Access Token (PAT)

1. Go to https://github.com/settings/tokens
2. Click **"Generate new token (classic)"**
3. Give it a name like `contabo-ghcr-pull`
4. Select scope: **`read:packages`** (that's all you need)
5. Generate and copy the token

### Log into GHCR on the VPS

```bash
echo "<your-github-pat>" | docker login ghcr.io -u tupacalypse187 --password-stdin
```

You should see `Login Succeeded`.

## 9. Test Deployment Manually

```bash
cd /opt/iam-dynamic
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

Verify the services are healthy:

```bash
# Check containers are running
docker compose -f docker-compose.prod.yml ps

# Test health endpoints (via docker exec since ports are internal)
docker compose -f docker-compose.prod.yml exec -T frontend wget -qO- http://localhost:8080/nginx-health && echo " OK"
docker compose -f docker-compose.prod.yml exec -T frontend wget -qO- http://localhost:8080/health && echo " OK"

# If Caddy is configured with your domain, test externally:
curl -sf https://iam.yantorno.dev/health && echo " OK" || echo " FAIL"
```

The app is accessible at `https://iam.yantorno.dev` (via Caddy). Frontend/backend ports are not exposed to the host in production.

## 10. Configure GitHub Secrets

Go to https://github.com/tupacalypse187/IAM-dynamic/settings/secrets/actions and add these repository secrets:

| Secret | Value | Example |
|--------|-------|---------|
| `PROD_HOST` | Your Contabo VPS IP address | `123.45.67.89` |
| `PROD_USER` | The deploy user | `deploy` |
| `PROD_SSH_KEY` | Contents of the **private** key file | `cat ~/.ssh/iam_dynamic_deploy` and paste the entire output including the `-----BEGIN/END-----` lines |
| `TURNSTILE_SITE_KEY` | Cloudflare Turnstile public site key (optional) | `0x4AAAAAAA...` |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL (optional) | `https://hooks.slack.com/services/T.../B.../xxx` |

> **Important:** For `PROD_SSH_KEY`, paste the entire private key including the header and footer lines.

## 11. Firewall Setup

```bash
# Allow SSH, HTTP, and HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Verify rules
sudo ufw status
```

## 12. Trigger a Deployment

Once secrets are configured, either:

1. Push a commit to `main` branch, or
2. Go to **Actions** tab > **Deploy** workflow > **Run workflow**

The pipeline will:
1. Run security checks and tests
2. Build and push Docker images to GHCR
3. SSH into your VPS
4. Pull the latest images
5. Restart containers with `docker compose up -d`
6. Run health checks to verify the deployment

## HTTPS with Caddy (Built-in)

Caddy is included in the production Docker Compose stack (`docker-compose.prod.yml`). It uses the Cloudflare DNS challenge to obtain Let's Encrypt certificates automatically — no port 80 challenge needed.

**Prerequisites:**
1. Domain DNS pointed at your VPS (e.g., `iam.yantorno.dev` → your VPS IP)
2. Cloudflare API token with `Zone:DNS:Edit` permission

**Configuration:** Set these in your `.env` file (see step 7):
- `CLOUDFLARE_API_TOKEN` — Cloudflare API token
- `CADDY_DOMAIN` — your domain (default: `iam.yantorno.dev`)
- `ACME_EMAIL` — email for Let's Encrypt (default: `admin@yantorno.dev`)

Caddy runs as a Docker container and reverse-proxies to the nginx frontend. The frontend and backend ports are no longer exposed to the host in production — all traffic goes through Caddy on ports 80/443.

Certificate data is persisted in the `caddy_data` Docker volume.

---

## Troubleshooting

### Containers won't start
```bash
cd /opt/iam-dynamic
docker compose -f docker-compose.prod.yml logs
```

### SSH deploy fails in GitHub Actions
- Verify the private key in `PROD_SSH_KEY` matches the public key on the VPS (`~deploy/.ssh/authorized_keys`)
- Test SSH manually: `ssh -i ~/.ssh/iam_dynamic_deploy deploy@<ip>`
- Check VPS firewall allows port 22

### Images fail to pull
- Verify GHCR login: `docker login ghcr.io`
- Check the PAT has `read:packages` scope
- Verify images exist: https://github.com/tupacalypse187?tab=packages

### Health checks fail after deployment
```bash
# Check container status
docker compose -f docker-compose.prod.yml ps

# Check individual logs
docker compose -f docker-compose.prod.yml logs frontend
docker compose -f docker-compose.prod.yml logs backend

# Check if ports are bound
ss -tlnp | grep -E '8080|8000'
```
