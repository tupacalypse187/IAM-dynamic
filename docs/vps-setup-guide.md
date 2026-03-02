# 🌐 Contabo VPS Deployment Guide

Deploy **IAM-Dynamic** on your Contabo Ubuntu VPS with automated GitHub Actions deployments.

---

## 📋 Overview

This guide covers setting up a Contabo Ubuntu VPS to receive automated deployments from GitHub Actions. Perfect for production hosting with CI/CD automation.

**What You'll Deploy:**

```
┌─────────────────────────────────────────────────────────────┐
│                    Contabo VPS                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    Caddy (TLS)                           ││
│  │                 :443 → :8080                             ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                Frontend (nginx)                          ││
│  │                   :8080                                  ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                Backend (FastAPI)                         ││
│  │                   :8000                                  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Prerequisites

| Requirement | Details |
|-------------|---------|
| **VPS** | Contabo VPS with Ubuntu 22.04 or 24.04 |
| **Access** | Root SSH access to the VPS |
| **Repo** | Your fork of https://github.com/tupacalypse187/IAM-dynamic |
| **Domain** | Domain with DNS pointed at your VPS (for HTTPS) |
| **Cloudflare** | Cloudflare API token (for Let's Encrypt via DNS challenge) |

---

## 🚀 Step 1: Initial Server Access

```bash
ssh root@<your-contabo-ip>
```

---

## 👤 Step 2: Create a Deploy User

Don't run containers as root. Create a dedicated `deploy` user:

```bash
adduser deploy
usermod -aG sudo deploy
```

---

## 🐳 Step 3: Install Docker & Docker Compose

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

---

## 🔑 Step 4: Set Up SSH Key Authentication

On **your local machine**, generate a dedicated deploy key:

```bash
ssh-keygen -t ed25519 -C "iam-dynamic-deploy" -f ~/.ssh/iam_dynamic_deploy
# Press Enter for no passphrase (required for automated deploys)
```

### Copy Public Key to VPS

```bash
ssh-copy-id -i ~/.ssh/iam_dynamic_deploy.pub deploy@<your-contabo-ip>
```

### Verify Passwordless Login

```bash
ssh -i ~/.ssh/iam_dynamic_deploy deploy@<your-contabo-ip>
```

You should be logged in without a password prompt.

---

## 📁 Step 5: Create the Application Directory

On the VPS as the `deploy` user:

```bash
sudo mkdir -p /opt/iam-dynamic
sudo chown deploy:deploy /opt/iam-dynamic
```

---

## 📦 Step 6: Copy Production Files to the VPS

From your local machine, copy `docker-compose.prod.yml`:

```bash
scp docker-compose.prod.yml deploy@<your-contabo-ip>:/opt/iam-dynamic/
```

---

## ⚙️ Step 7: Create the `.env` File

There are two approaches: the interactive setup script (recommended) or manual `.env` creation.

### Option A: Setup Script (Recommended) 🎯

Clone the repo on the VPS (or scp the script) and run:

```bash
ssh deploy@<your-contabo-ip>
cd /opt/iam-dynamic
bash setup-auth.sh --prod
```

The `--prod` flag walks you through:

| Step | Description |
|------|-------------|
| 1️⃣ | Admin username + password (generates bcrypt hash and JWT secret) |
| 2️⃣ | Cloudflare Turnstile CAPTCHA keys (optional) |
| 3️⃣ | Caddy HTTPS domain + Cloudflare API token |
| 4️⃣ | GitHub Secrets reminder |

You'll still need to manually add your AI provider keys and AWS config to `.env` afterward.

### Option B: Manual `.env` Creation

SSH into the VPS and create the environment file:

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

**Generate password hash:**

```bash
pip install passlib[bcrypt]
python backend/scripts/hash_password.py
# Enter your password, then copy the AUTH_PASSWORD_HASH=... output into .env
```

---

## 🔐 Step 8: Authenticate Docker with GHCR

The VPS needs to pull container images from GitHub Container Registry (GHCR).

### Create a GitHub Personal Access Token (PAT)

1. Go to https://github.com/settings/tokens
2. Click **"Generate new token (classic)"**
3. Name it `contabo-ghcr-pull`
4. Select scope: **`read:packages`** (that's all you need)
5. Generate and copy the token

### Log into GHCR on the VPS

```bash
echo "<your-github-pat>" | docker login ghcr.io -u tupacalypse187 --password-stdin
```

You should see `Login Succeeded`.

---

## 🧪 Step 9: Test Deployment Manually

```bash
cd /opt/iam-dynamic
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
```

### Verify Services are Healthy

```bash
# Check container status
docker compose -f docker-compose.prod.yml ps

# Test health endpoints (via docker exec since ports are internal)
docker compose -f docker-compose.prod.yml exec -T frontend wget -qO- http://localhost:8080/nginx-health && echo " OK"
docker compose -f docker-compose.prod.yml exec -T frontend wget -qO- http://localhost:8080/health && echo " OK"

# If Caddy is configured with your domain, test externally:
curl -sf https://iam.yantorno.dev/health && echo " OK" || echo " FAIL"
```

**Expected output:**

```
NAME                IMAGE                      STATUS
caddy               ghcr.io/.../caddy         running
frontend            ghcr.io/.../frontend      healthy
backend             ghcr.io/.../backend       healthy
```

The app is accessible at `https://iam.yantorno.dev` (via Caddy). Frontend/backend ports are not exposed to the host in production.

---

## 🔧 Step 10: Configure GitHub Secrets

Go to https://github.com/tupacalypse187/IAM-dynamic/settings/secrets/actions and add these repository secrets:

| Secret | Value | Example |
|--------|-------|---------|
| `PROD_HOST` | Your Contabo VPS IP address | `123.45.67.89` |
| `PROD_USER` | The deploy user | `deploy` |
| `PROD_SSH_KEY` | Contents of the **private** key file | `cat ~/.ssh/iam_dynamic_deploy` and paste the entire output including the `-----BEGIN/END-----` lines |
| `TURNSTILE_SITE_KEY` | Cloudflare Turnstile public site key (optional) | `0x4AAAAAAA...` |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook URL (optional) | `https://hooks.slack.com/services/T.../B.../xxx` |

> **Important:** For `PROD_SSH_KEY`, paste the entire private key including the header and footer lines.

---

## 🔥 Step 11: Firewall Setup

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

**Expected output:**

```
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere
80/tcp                     ALLOW       Anywhere
443/tcp                    ALLOW       Anywhere
```

---

## 🚀 Step 12: Trigger a Deployment

Once secrets are configured, either:

1. **Push a commit** to `main` branch, or
2. **Go to Actions tab** > **Deploy workflow** > **Run workflow**

The deployment pipeline will:

| Step | Description |
|------|-------------|
| 1️⃣ | Run security checks and tests |
| 2️⃣ | Build and push Docker images to GHCR |
| 3️⃣ | SSH into your VPS |
| 4️⃣ | Pull the latest images |
| 5️⃣ | Restart containers with `docker compose up -d` |
| 6️⃣ | Run health checks to verify deployment |

---

## 🔒 HTTPS with Caddy (Built-in)

Caddy is included in the production Docker Compose stack (`docker-compose.prod.yml`). It uses the Cloudflare DNS challenge to obtain Let's Encrypt certificates automatically — no port 80 challenge needed.

### Prerequisites

| Requirement | Description |
|-------------|-------------|
| **Domain** | DNS pointed at your VPS (e.g., `iam.yantorno.dev` → your VPS IP) |
| **Cloudflare Token** | API token with `Zone:DNS:Edit` permission |

### Configuration

Set these in your `.env` file:

| Variable | Description | Example |
|----------|-------------|---------|
| `CLOUDFLARE_API_TOKEN` | Cloudflare API token | `your-cloudflare-api-token` |
| `CADDY_DOMAIN` | Your domain | `iam.yantorno.dev` |
| `ACME_EMAIL` | Email for Let's Encrypt | `admin@yantorno.dev` |

Caddy runs as a Docker container and reverse-proxies to the nginx frontend. The frontend and backend ports are not exposed to the host in production — all traffic goes through Caddy on ports 80/443.

Certificate data is persisted in the `caddy_data` Docker volume.

---

## 🔧 Troubleshooting

### Containers Won't Start

```bash
cd /opt/iam-dynamic
docker compose -f docker-compose.prod.yml logs
```

### SSH Deploy Fails in GitHub Actions

| Issue | Solution |
|-------|----------|
| Key mismatch | Verify the private key in `PROD_SSH_KEY` matches the public key on the VPS (`~deploy/.ssh/authorized_keys`) |
| Connection refused | Test SSH manually: `ssh -i ~/.ssh/iam_dynamic_deploy deploy@<ip>` |
| Firewall blocking | Check VPS firewall allows port 22 |

### Images Fail to Pull

| Issue | Solution |
|-------|----------|
| Not logged in | Verify GHCR login: `docker login ghcr.io` |
| Wrong PAT scope | Check the PAT has `read:packages` scope |
| Images don't exist | Verify images exist: https://github.com/tupacalypse187?tab=packages |

### Health Checks Fail After Deployment

```bash
# Check container status
docker compose -f docker-compose.prod.yml ps

# Check individual logs
docker compose -f docker-compose.prod.yml logs frontend
docker compose -f docker-compose.prod.yml logs backend

# Check if ports are bound
ss -tlnp | grep -E '8080|8000'
```

---

## 📚 Additional Resources

- [Local Docker Testing Guide](local-docker-testing.md) 🐳
- [Antsle Deployment Guide](antsle-deployment-guide.md) 🐜
- [MicroK8s ArgoCD Guide](microk8s-argocd-deployment-guide.md) ☸️
- [CLAUDE.md](../CLAUDE.md) - Project documentation

---

**Your production IAM portal is ready! 🎉**
