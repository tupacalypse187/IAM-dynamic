# 🐜 Antsle Deployment Guide

Deploy **IAM-Dynamic** on your antsle home lab appliance with Ubuntu 24 or AlmaLinux 24.

---

## 📋 Overview

The **antsle** is a compact home lab appliance that provides a perfect environment for self-hosted services. This guide covers deploying IAM-Dynamic using Docker Compose on your antsle, with support for:

- 🐧 **Ubuntu 24.04 LTS** (Noble Numbat)
- 🔴 **AlmaLinux 24** (RHEL-compatible)

You'll have two deployment options:
1. **Build locally** on the antsle (fully self-contained, slower first build)
2. **Pull from GHCR** (faster setup, requires internet connection)

---

## 🎯 Prerequisites

### Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 2 GB | 4 GB |
| Storage | 10 GB | 20 GB |
| CPU | 2 cores | 4 cores |

### Software Requirements

**Ubuntu 24:**
```bash
# Verify your OS
cat /etc/os-release
# Should show: Ubuntu 24.04 LTS or similar
```

**AlmaLinux 24:**
```bash
# Verify your OS
cat /etc/os-release
# Should show: AlmaLinux 24 or similar
```

### Network Access

- SSH access to your antsle (typically `root@antsle.local` or via the antsle UI)
- Internet connection for pulling images (GHCR option) or building locally
- Optional: Internal DNS configured for your home network domain

---

## 🚀 Initial Server Setup

### Step 1: Access Your Antsle

**Via antsle UI:**
1. Open your browser to `https://antsle.local` (or your antsle's IP)
2. Log in with your antsle admin credentials
3. Open a web terminal to your chosen VM/container

**Via SSH:**
```bash
# From your local machine
ssh root@antsle.local
# Or use the IP address
ssh root@<antsle-ip>
```

### Step 2: Create a Dedicated User

Don't run containers as root. Create a dedicated `iamuser`:

**Ubuntu 24:**
```bash
adduser iamuser
usermod -aG sudo iamuser
usermod -aG docker iamuser  # We'll add docker group later
```

**AlmaLinux 24:**
```bash
adduser iamuser
usermod -aG wheel iamuser
usermod -aG docker iamuser  # We'll add docker group later
```

### Step 3: Install Docker & Docker Compose

**Ubuntu 24:**
```bash
# Update package index
apt update

# Install Docker using the official convenience script
curl -fsSL https://get.docker.com | sh

# Add iamuser to docker group
usermod -aG docker iamuser

# Verify installation
docker --version
docker compose version
```

**AlmaLinux 24:**
```bash
# Update packages
dnf update -y

# Install Docker
dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Enable and start Docker
systemctl enable --now docker

# Add iamuser to docker group
usermod -aG docker iamuser

# Verify installation
docker --version
docker compose version
```

> **Note:** Log out and back in as `iamuser` for the docker group membership to take effect.

---

## 🔑 SSH Key Authentication (Optional)

For passwordless SSH access from your local machine:

```bash
# On your local machine
ssh-keygen -t ed25519 -C "iam-dynamic-antsle" -f ~/.ssh/iam_antsle
# Press Enter for no passphrase (required for automated access)

# Copy the public key to the antsle
ssh-copy-id -i ~/.ssh/iam_antsle.pub iamuser@<antsle-ip>

# Test passwordless login
ssh -i ~/.ssh/iam_antsle iamuser@<antsle-ip>
```

---

## 📁 Clone the Repository

As the `iamuser`:

```bash
# Create application directory
mkdir -p ~/apps
cd ~/apps

# Clone the repository
git clone https://github.com/tupacalypse187/IAM-dynamic.git
cd IAM-dynamic
```

---

## ⚙️ Environment Configuration

### Option A: Using the Setup Script (Recommended)

The interactive setup script handles authentication and HTTPS configuration:

```bash
bash setup-auth.sh
```

Follow the prompts:
1. Choose `prod` mode for full setup
2. Enter admin username and password
3. Optionally add Cloudflare Turnstile CAPTCHA keys
4. Configure Caddy HTTPS with your domain

### Option B: Manual .env Creation

Create the `.env` file manually:

```bash
cat > .env << 'EOF'
# ============================================
# AI Provider Configuration
# ============================================
LLM_PROVIDER=gemini

# --- Gemini Configuration (Google) ---
GOOGLE_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-3-pro-preview

# --- OpenAI Configuration (optional) ---
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-5.1

# --- Anthropic Claude Configuration (optional) ---
# ANTHROPIC_API_KEY=sk-ant-...
# ANTHROPIC_MODEL=claude-opus-4-5-20251101

# --- Z.AI GLM Configuration (optional) ---
# ZAI_API_KEY=...
# ZAI_MODEL=glm-5.1

# ============================================
# AWS Configuration
# ============================================
AWS_ACCOUNT_ID=123456789012
AWS_ROLE_NAME=AgentPOCSessionRole
AWS_DEFAULT_REGION=us-east-1

# ============================================
# Authentication
# ============================================
AUTH_USERNAME=admin
AUTH_PASSWORD_HASH=$2b$12$...   # Generate with: python backend/scripts/hash_password.py
JWT_SECRET=your-random-secret-at-least-32-characters
JWT_EXPIRY_HOURS=8

# Cloudflare Turnstile CAPTCHA (optional)
# TURNSTILE_SECRET_KEY=0x...

# ============================================
# Caddy / HTTPS
# ============================================
CLOUDFLARE_API_TOKEN=...        # Cloudflare token with Zone:DNS:Edit
CADDY_DOMAIN=iam.yourdomain.local
ACME_EMAIL=admin@yourdomain.local

# ============================================
# Optional Configuration
# ============================================
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
APPROVER_NAME=Admin
DATABASE_PATH=iam_dynamic.db
EOF

chmod 600 .env
```

> **Note for Home Labs:** If you're using an internal domain (like `.local` or `.lan`), you may need to skip Caddy HTTPS or use self-signed certificates. See the HTTPS section below.

---

## 🐳 Deployment Option 1: Build Locally

Build all images from source on your antsle. Fully self-contained but slower initial build.

```bash
cd ~/apps/IAM-dynamic

# Build and start all containers
docker compose -f docker-compose.prod.yml build

# Start in detached mode
docker compose -f docker-compose.prod.yml up -d
```

**Expected build time:** 5-10 minutes on first run (depending on your antsle's CPU).

---

## 🐳 Deployment Option 2: Pull from GHCR

Use pre-built images from GitHub Container Registry. Much faster setup.

### Step 1: Authenticate with GHCR

You'll need a GitHub Personal Access Token with `read:packages` scope:

1. Go to https://github.com/settings/tokens
2. Click **"Generate new token (classic)"**
3. Name it `antsle-ghcr-pull`
4. Select scope: **`read:packages`**
5. Generate and copy the token

```bash
echo "<your-github-pat>" | docker login ghcr.io -u tupacalypse187 --password-stdin
```

You should see `Login Succeeded`.

### Step 2: Update docker-compose.prod.yml for GHCR

Edit `docker-compose.prod.yml` to use pre-built images:

```yaml
services:
  caddy:
    image: ghcr.io/tupacalypse187/iam-dynamic-caddy:latest
    # ... rest of caddy config

  backend:
    image: ghcr.io/tupacalypse187/iam-dynamic-backend:latest
    # ... rest of backend config

  frontend:
    image: ghcr.io/tupacalypse187/iam-dynamic-frontend:latest
    # ... rest of frontend config
```

> **Note:** The official `docker-compose.prod.yml` already uses GHCR images by default.

### Step 3: Pull and Start

```bash
cd ~/apps/IAM-dynamic

# Pull latest images
docker compose -f docker-compose.prod.yml pull

# Start containers
docker compose -f docker-compose.prod.yml up -d
```

---

## 🔥 Firewall Configuration

### Ubuntu 24 (ufw)

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable

# Verify rules
sudo ufw status
```

### AlmaLinux 24 (firewalld)

```bash
# Allow SSH
sudo firewall-cmd --permanent --add-service=ssh

# Allow HTTP and HTTPS
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https

# Reload firewall
sudo firewall-cmd --reload

# Verify rules
sudo firewall-cmd --list-all
```

> **Home Network Note:** If your antsle is behind your home router's NAT, you may not need to open external ports. Use port forwarding on your router if you want external access.

---

## 🔒 HTTPS Setup

### Option A: Public Domain with Cloudflare DNS

If you have a public domain pointed at your antsle (via port forwarding or DMZ):

```bash
# Ensure these are in your .env
CLOUDFLARE_API_TOKEN=your-cloudflare-api-token
CADDY_DOMAIN=iam.yourdomain.com
ACME_EMAIL=admin@yourdomain.com
```

Caddy will automatically obtain Let's Encrypt certificates.

### Option B: Internal Domain with Self-Signed Certs

For internal-only access (e.g., `iam.home.lab`), use self-signed certificates:

```bash
# Generate self-signed certificate
sudo mkdir -p /etc/ssl/local
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/local/iam.key \
  -out /etc/ssl/local/iam.crt \
  -subj "/CN=iam.home.lab"

# Trust the certificate on your local machines (for each client)
# Copy iam.crt to your client and add to OS trust store
```

Then update Caddy configuration to use the self-signed cert, or simply skip HTTPS for internal-only deployments.

### Option C: Skip HTTPS (Internal Only)

For a purely internal deployment on your trusted home network, you can run without HTTPS:

```bash
# Use docker-compose.yml instead of docker-compose.prod.yml
docker compose up -d
```

Access at `http://<antsle-ip>:8080`

---

## ✅ Health Checks & Verification

```bash
cd ~/apps/IAM-dynamic

# Check container status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f

# Test health endpoints
curl http://localhost:8080/nginx-health
curl http://localhost:8080/health
```

**Expected output:**
```
iam-frontend-1   healthy
iam-backend-1    healthy
iam-caddy-1      running
```

### Access the Application

| URL | Description |
|-----|-------------|
| `http://<antsle-ip>:8080` | HTTP (no Caddy) |
| `https://<domain>` | HTTPS (with Caddy) |
| `http://<antsle-ip>:8080/docs` | API Documentation |

---

## 🔄 Auto-Start on Boot

Create a systemd service to automatically start IAM-Dynamic when the antsle boots.

### Ubuntu 24 & AlmaLinux 24

```bash
# Create systemd service file
sudo nano /etc/systemd/system/iam-dynamic.service
```

Add the following content:

```ini
[Unit]
Description=IAM-Dynamic Docker Compose Service
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/iamuser/apps/IAM-dynamic
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable iam-dynamic.service

# Start the service now
sudo systemctl start iam-dynamic.service

# Check status
sudo systemctl status iam-dynamic.service
```

---

## 🛠️ AlmaLinux-Specific Considerations

### SELinux

AlmaLinux comes with SELinux enabled by default. You may need to adjust policies:

```bash
# Check SELinux status
sestatus

# If running in enforcing mode, you may need to set permissive mode for testing
sudo setenforce 0

# To make permanent, edit /etc/selinux/config
sudo nano /etc/selinux/config
# Change: SELINUX=permissive
```

### Package Management Differences

| Action | Ubuntu | AlmaLinux |
|--------|--------|-----------|
| Install | `apt install` | `dnf install` |
| Update | `apt update && apt upgrade` | `dnf update` |
| Search | `apt search` | `dnf search` |
| Firewall | `ufw` | `firewalld` |
| Service | `systemctl` | `systemctl` |

---

## 📊 Monitoring & Logs

```bash
# View all logs
docker compose -f docker-compose.prod.yml logs

# Follow logs in real-time
docker compose -f docker-compose.prod.yml logs -f

# View specific service logs
docker compose -f docker-compose.prod.yml logs backend
docker compose -f docker-compose.prod.yml logs frontend
docker compose -f docker-compose.prod.yml logs caddy

# Check resource usage
docker stats
```

---

## 🔧 Troubleshooting

### Container won't start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs <service-name>

# Verify .env file exists and is correct
cat .env

# Check Docker is running
sudo systemctl status docker
```

### Port already in use

```bash
# Find what's using the port
sudo lsof -i :80
sudo lsof -i :443
sudo lsof -i :8080

# Stop conflicting service
sudo systemctl stop <conflicting-service>
```

### Permission denied errors

```bash
# Ensure your user is in the docker group
groups

# If not, add yourself (then log out and back in)
sudo usermod -aG docker $USER
```

### Can't access from other devices

1. Check firewall rules
2. Verify antsle's IP address: `ip addr show`
3. Check router port forwarding (if accessing from outside home network)
4. Ensure Docker containers are binding to 0.0.0.0 not 127.0.0.1

### Images fail to pull

```bash
# Verify GHCR login
docker login ghcr.io

# Re-authenticate if needed
echo "<token>" | docker login ghcr.io -u tupacalypse187 --password-stdin

# Check network connectivity
ping ghcr.io
```

### Rebuild from scratch

```bash
# Stop and remove everything
docker compose -f docker-compose.prod.yml down -v

# Remove images
docker rmi ghcr.io/tupacalypse187/iam-dynamic-frontend:latest
docker rmi ghcr.io/tupacalypse187/iam-dynamic-backend:latest
docker rmi ghcr.io/tupacalypse187/iam-dynamic-caddy:latest

# Prune Docker system
docker system prune -a

# Start fresh
docker compose -f docker-compose.prod.yml up -d
```

---

## 🔄 Updating the Deployment

```bash
cd ~/apps/IAM-dynamic

# Pull latest code
git pull origin main

# Pull new images (if using GHCR)
docker compose -f docker-compose.prod.yml pull

# Recreate containers with new images
docker compose -f docker-compose.prod.yml up -d

# Or rebuild locally
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 📚 Useful Commands

```bash
# Stop the application
docker compose -f docker-compose.prod.yml down

# Start the application
docker compose -f docker-compose.prod.yml up -d

# Restart a specific service
docker compose -f docker-compose.prod.yml restart backend

# Shell into a container
docker compose -f docker-compose.prod.yml exec backend bash
docker compose -f docker-compose.prod.yml exec frontend sh

# View container resource usage
docker stats

# Clean up unused resources
docker system prune -f
```

---

## 🎉 Next Steps

1. **Configure your DNS:** Add an A record for your domain pointing to the antsle's IP
2. **Test the full flow:** Create a test IAM access request
3. **Set up backups:** Back up your SQLite database regularly
4. **Monitor resources:** Use `docker stats` to ensure adequate resources
5. **Configure external access:** Set up port forwarding on your router if needed

---

## 📖 Additional Resources

- [Main README](../README.md)
- [Local Docker Testing Guide](local-docker-testing.md)
- [VPS Deployment Guide](vps-setup-guide.md)
- [CLAUDE.md](../CLAUDE.md) - Project documentation

---

**Enjoy your home-hosted IAM access portal! 🎊**
