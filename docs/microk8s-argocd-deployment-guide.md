# ☸️ MicroK8s ArgoCD Deployment Guide

Deploy **IAM-Dynamic** on your MicroK8s home lab using ArgoCD GitOps automation.

---

## 📋 Overview

This guide covers deploying IAM-Dynamic on a MicroK8s cluster with ArgoCD for continuous deployment. This approach follows the same patterns used in the [yantorno-party](https://github.com/tupacalypse187/yantorno-party) project.

### 🎯 What You'll Deploy

```
┌─────────────────────────────────────────────────────────────┐
│                        MicroK8s Cluster                      │
│  ┌─────────────────────────────────────────────────────────┐│
│  │                    ArgoCD                                ││
│  │  Monitors git repo → Syncs K8s manifests                ││
│  └─────────────────────────────────────────────────────────┘│
│                             │                                │
│                             ▼                                │
│  ┌─────────────────────────────────────────────────────────┐│
│  │              iam-dynamic Namespace                       ││
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ ││
│  │  │  Frontend   │  │   Backend   │  │  Traefik Ingress│ ││
│  │  │  (nginx)    │  │  (FastAPI)  │  │  + Let's Encrypt│ ││
│  │  │    :8080    │  │    :8000    │  │                 │ ││
│  │  └─────────────┘  └─────────────┘  └─────────────────┘ ││
│  │       │                │                                 ││
│  │       └────────────────┴─────────────────────────────────┘│
│  │                      │                                    │
│  │              ┌───────▼───────┐                            ││
│  │              │  PVC (SQLite) │                            ││
│  │              └───────────────┘                            ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │  Traefik LB   │
                    │  (Ingress)    │
                    └───────────────┘
                            │
                            ▼
                    https://iam.yourdomain.party
```

---

## 🎯 Prerequisites

### Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| RAM | 4 GB | 8 GB |
| Storage | 20 GB | 50 GB |
| CPU | 2 cores | 4 cores |

### Software Requirements

- **MicroK8s** (v1.28+) installed and running
- **ArgoCD** installed on the cluster
- **kubectl** configured to access MicroK8s
- **Traefik** Ingress Controller (optional but recommended)
- A domain with DNS pointing to your MicroK8s server

### Verify MicroK8s Installation

```bash
# Check MicroK8s status
microk8s status

# Enable required addons
microk8s enable dns
microk8s enable storage
microk8s enable ingress
```

### Verify ArgoCD Installation

```bash
# Access ArgoCD UI (default password: admin/initial password)
# Get initial password:
microk8s kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# Port forward to access UI
microk8s kubectl port-forward svc/argocd-server -n argocd 8080:443

# Open browser to https://localhost:8080
```

---

## 🏗️ Architecture Overview

### Directory Structure (in yantorno-party repo)

```
yantorno-party/
└── microk8s/
    └── apps/
        └── iam-dynamic/
            ├── application.yaml       # ArgoCD Application manifest
            ├── manifests.yaml          # All K8s resources
            ├── secret.template.yaml    # Secret template (not in git)
            └── README.md               # Quick reference
```

### Component Overview

| Component | Description | Image |
|-----------|-------------|-------|
| **Frontend** | React SPA served by nginx | `ghcr.io/tupacalypse187/iam-dynamic-frontend:latest` |
| **Backend** | FastAPI REST API | `ghcr.io/tupacalypse187/iam-dynamic-backend:latest` |
| **Ingress** | Traefik routing with TLS | Cluster's Traefik |
| **Secret** | Environment variables | `iam-dynamic-secret` |
| **PVC** | SQLite database storage | `microk8s-hostpath` |

---

## 📁 Step 1: Create Directory Structure

In your **yantorno-party** repository:

```bash
cd ~/apps/yantorno-party  # or wherever you cloned it

# Create the iam-dynamic app directory
mkdir -p microk8s/apps/iam-dynamic
cd microk8s/apps/iam-dynamic
```

---

## 🔐 Step 2: Create Kubernetes Secrets

First, create a secret template file:

```bash
cat > secret.template.yaml << 'EOF'
# IAM-Dynamic Secrets Template
#
# Instructions:
# 1. Copy this file: cp secret.template.yaml iam-dynamic-secret.yaml
# 2. Add to .gitignore: echo "iam-dynamic-secret.yaml" >> ../../.gitignore
# 3. Fill in your actual values
# 4. Apply: kubectl apply -f iam-dynamic-secret.yaml

apiVersion: v1
kind: Secret
metadata:
  name: iam-dynamic-secret
  namespace: iam-dynamic
type: Opaque
stringData:
  # ============================================
  # AI Provider Configuration
  # ============================================
  LLM_PROVIDER: "gemini"

  # --- Gemini Configuration (Google) ---
  GOOGLE_API_KEY: "AIzaSy..."  # Your Google API key
  GEMINI_MODEL: "gemini-3-pro-preview"

  # --- OpenAI Configuration (optional) ---
  # OPENAI_API_KEY: "sk-..."
  # OPENAI_MODEL: "gpt-5.1"

  # --- Anthropic Claude Configuration (optional) ---
  # ANTHROPIC_API_KEY: "sk-ant-..."
  # ANTHROPIC_MODEL: "claude-opus-4-5-20251101"

  # --- Z.AI GLM Configuration (optional) ---
  # ZAI_API_KEY: "..."
  # ZAI_MODEL: "glm-5.1"

  # ============================================
  # AWS Configuration
  # ============================================
  AWS_ACCOUNT_ID: "123456789012"
  AWS_ROLE_NAME: "AgentPOCSessionRole"
  AWS_DEFAULT_REGION: "us-east-1"

  # ============================================
  # Authentication
  # ============================================
  AUTH_USERNAME: "admin"
  AUTH_PASSWORD_HASH: "$2b$12$..."  # Generate with: python backend/scripts/hash_password.py
  JWT_SECRET: "your-random-secret-at-least-32-characters"
  JWT_EXPIRY_HOURS: "8"

  # Cloudflare Turnstile CAPTCHA (optional)
  # TURNSTILE_SECRET_KEY: "0x..."

  # ============================================
  # Slack Integration (Optional)
  # ============================================
  # SLACK_WEBHOOK_URL: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

  # ============================================
  # Optional Configuration
  # ============================================
  APPROVER_NAME: "Admin"
  DATABASE_PATH: "iam_dynamic.db"
EOF
```

Now create your actual secret file:

```bash
# Copy the template
cp secret.template.yaml iam-dynamic-secret.yaml

# Add to .gitignore (so secrets aren't committed)
echo "iam-dynamic-secret.yaml" >> ../../.gitignore

# Edit with your actual values
nano iam-dynamic-secret.yaml
```

**Generate a password hash:**

```bash
# From the IAM-dynamic repo
cd ~/apps/IAM-dynamic
python backend/scripts/hash_password.py
# Copy the output to AUTH_PASSWORD_HASH in your secret file
```

**Apply the secret to your cluster:**

```bash
cd ~/apps/yantorno-party/microk8s/apps/iam-dynamic

# Using microk8s kubectl
microk8s kubectl apply -f iam-dynamic-secret.yaml

# Or if kubectl is aliased/configured
kubectl apply -f iam-dynamic-secret.yaml

# Verify
microk8s kubectl get secret iam-dynamic-secret -n iam-dynamic
```

---

## 📝 Step 3: Create Kubernetes Manifests

Create `manifests.yaml` with all the K8s resources:

```yaml
# ===================================================================
# IAM-Dynamic Kubernetes Manifests
# ===================================================================
# This file contains all K8s resources for deploying IAM-Dynamic
# on MicroK8s with ArgoCD GitOps.
# ===================================================================

---
# Namespace
apiVersion: v1
kind: Namespace
metadata:
  name: iam-dynamic
  labels:
    app: iam-dynamic

---
# PersistentVolumeClaim for SQLite Database
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: iam-dynamic-data
  namespace: iam-dynamic
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 2Gi
  storageClassName: microk8s-hostpath

---
# Backend Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: iam-dynamic-backend
  namespace: iam-dynamic
  labels:
    app: iam-dynamic-backend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: iam-dynamic-backend
  template:
    metadata:
      labels:
        app: iam-dynamic-backend
    spec:
      containers:
      - name: backend
        image: ghcr.io/tupacalypse187/iam-dynamic-backend:latest
        ports:
        - containerPort: 8000
          name: http
        env:
        # AI Provider
        - name: LLM_PROVIDER
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: LLM_PROVIDER
        # Gemini
        - name: GOOGLE_API_KEY
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: GOOGLE_API_KEY
        - name: GEMINI_MODEL
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: GEMINI_MODEL
        # OpenAI (optional)
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: OPENAI_API_KEY
          optional: true
        - name: OPENAI_MODEL
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: OPENAI_MODEL
          optional: true
        # Anthropic (optional)
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: ANTHROPIC_API_KEY
          optional: true
        - name: ANTHROPIC_MODEL
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: ANTHROPIC_MODEL
          optional: true
        # Z.AI GLM (optional)
        - name: ZAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: ZAI_API_KEY
          optional: true
        - name: ZAI_MODEL
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: ZAI_MODEL
          optional: true
        # AWS Configuration
        - name: AWS_ACCOUNT_ID
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: AWS_ACCOUNT_ID
        - name: AWS_ROLE_NAME
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: AWS_ROLE_NAME
        - name: AWS_DEFAULT_REGION
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: AWS_DEFAULT_REGION
        # Authentication
        - name: AUTH_USERNAME
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: AUTH_USERNAME
        - name: AUTH_PASSWORD_HASH
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: AUTH_PASSWORD_HASH
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: JWT_SECRET
        - name: JWT_EXPIRY_HOURS
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: JWT_EXPIRY_HOURS
        # Optional
        - name: TURNSTILE_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: TURNSTILE_SECRET_KEY
          optional: true
        - name: SLACK_WEBHOOK_URL
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: SLACK_WEBHOOK_URL
          optional: true
        - name: APPROVER_NAME
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: APPROVER_NAME
        - name: DATABASE_PATH
          valueFrom:
            secretKeyRef:
              name: iam-dynamic-secret
              key: DATABASE_PATH
        # Security Context
        securityContext:
          runAsNonRoot: true
          runAsUser: 1001
          allowPrivilegeEscalation: false
          readOnlyRootFilesystem: false
        # Resources
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        # Health Check
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 15
          periodSeconds: 20
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
        volumeMounts:
        - name: data
          mountPath: /app/data
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: iam-dynamic-data

---
# Frontend Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: iam-dynamic-frontend
  namespace: iam-dynamic
  labels:
    app: iam-dynamic-frontend
spec:
  replicas: 1
  selector:
    matchLabels:
      app: iam-dynamic-frontend
  template:
    metadata:
      labels:
        app: iam-dynamic-frontend
    spec:
      containers:
      - name: frontend
        image: ghcr.io/tupacalypse187/iam-dynamic-frontend:latest
        ports:
        - containerPort: 8080
          name: http
        env:
        - name: BACKEND_URL
          value: "http://iam-dynamic-backend-service:8000"
        securityContext:
          runAsNonRoot: true
          runAsUser: 1001
          allowPrivilegeEscalation: false
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "256Mi"
            cpu: "200m"
        livenessProbe:
          httpGet:
            path: /nginx-health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /nginx-health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10

---
# Backend Service
apiVersion: v1
kind: Service
metadata:
  name: iam-dynamic-backend-service
  namespace: iam-dynamic
spec:
  selector:
    app: iam-dynamic-backend
  ports:
  - protocol: TCP
    port: 8000
    targetPort: 8000
  type: ClusterIP

---
# Frontend Service
apiVersion: v1
kind: Service
metadata:
  name: iam-dynamic-frontend-service
  namespace: iam-dynamic
spec:
  selector:
    app: iam-dynamic-frontend
  ports:
  - protocol: TCP
    port: 8080
    targetPort: 8080
  type: ClusterIP

---
# Ingress
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: iam-dynamic-ingress
  namespace: iam-dynamic
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
    traefik.ingress.kubernetes.io/router.tls.certresolver: letencrypt
    # Optional: Add authentik forward auth if you have it
    # traefik.ingress.kubernetes.io/router.middlewares: authentik-authentik-forward-auth@kubernetescrd
spec:
  ingressClassName: traefik
  tls:
  - hosts:
    - iam.yourdomain.party  # Change to your domain
    secretName: iam-dynamic-tls
  rules:
  - host: iam.yourdomain.party  # Change to your domain
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: iam-dynamic-backend-service
            port:
              number: 8000
      - path: /health
        pathType: Prefix
        backend:
          service:
            name: iam-dynamic-backend-service
            port:
              number: 8000
      - path: /config
        pathType: Prefix
        backend:
          service:
            name: iam-dynamic-backend-service
            port:
              number: 8000
      - path: /docs
        pathType: Prefix
        backend:
          service:
            name: iam-dynamic-backend-service
            port:
              number: 8000
      - path: /
        pathType: Prefix
        backend:
          service:
            name: iam-dynamic-frontend-service
            port:
              number: 8080
```

**Update the domain name** in the Ingress section to match your domain.

---

## 🚀 Step 4: Create ArgoCD Application Manifest

Create `application.yaml`:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: iam-dynamic
  namespace: argocd
  finalizers:
    - resources-finalizer.argocd.argoproj.io
spec:
  project: default
  source:
    repoURL: https://github.com/tupacalypse187/yantorno-party.git
    targetRevision: HEAD
    path: microk8s/apps/iam-dynamic
  destination:
    server: https://kubernetes.default.svc
    namespace: iam-dynamic
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=true
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

---

## 📤 Step 5: Push to GitHub

Commit and push all changes to your yantorno-party repository:

```bash
cd ~/apps/yantorno-party

# Add the new files
git add microk8s/apps/iam-dynamic/application.yaml
git add microk8s/apps/iam-dynamic/manifests.yaml
git add microk8s/apps/iam-dynamic/secret.template.yaml
git add .gitignore

# Commit
git commit -m "feat: Add IAM-Dynamic ArgoCD deployment"

# Push
git push origin main
```

> **⚠️ Important:** Never commit `iam-dynamic-secret.yaml` - it's already in .gitignore!

---

## 🎯 Step 6: Deploy via ArgoCD

### Option A: Via ArgoCD UI

1. Open ArgoCD UI: `https://localhost:8080` (after port-forward)
2. Click **"New App"** (or **"+ New App"**)
3. Select **"Edit as YAML"**
4. Paste the contents of `application.yaml`
5. Click **"Create"**

### Option B: Via kubectl

```bash
cd ~/apps/yantorno-party/microk8s/apps/iam-dynamic

# Apply the application manifest
microk8s kubectl apply -f application.yaml

# Verify in ArgoCD
microk8s kubectl get applications -n argocd
```

### Sync the Application

1. In ArgoCD UI, find the **iam-dynamic** application
2. Click **"Sync"**
3. Review the changes and click **"Synchronize"**

The application should sync and become **Healthy** within a minute.

---

## ✅ Step 7: Verify Deployment

```bash
# Check all resources in the iam-dynamic namespace
microk8s kubectl get all -n iam-dynamic

# Check pods
microk8s kubectl get pods -n iam-dynamic

# Check logs
microk8s kubectl logs -f deployment/iam-dynamic-backend -n iam-dynamic
microk8s kubectl logs -f deployment/iam-dynamic-frontend -n iam-dynamic

# Check ingress
microk8s kubectl get ingress -n iam-dynamic
```

**Expected output:**
```
NAME                                        READY   STATUS    RESTARTS   AGE
pod/iam-dynamic-backend-xxxxxxxxxx-xxxxx    1/1     Running   0          1m
pod/iam-dynamic-frontend-xxxxxxxxxx-xxxxx    1/1     Running   0          1m

NAME                                           TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)    AGE
service/iam-dynamic-backend-service            ClusterIP   10.152.183.1     <none>        8000/TCP   1m
service/iam-dynamic-frontend-service           ClusterIP   10.152.183.2     <none>        8080/TCP   1m

NAME                                           READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/iam-dynamic-backend            1/1     1            1           1m
deployment.apps/iam-dynamic-frontend           1/1     1            1           1m
```

### Access the Application

Open your browser to: `https://iam.yourdomain.party`

You should see the IAM-Dynamic login page (if auth is enabled) or the request form.

---

## 🔄 Updating the Application

With ArgoCD GitOps, updates are simple:

### Update Container Images

1. New images are pushed to GHCR from the IAM-dynamic CI/CD
2. ArgoCD detects the change (if using image tags) or you manually sync
3. ArgoCD updates the deployments automatically

### Update Manifests

```bash
cd ~/apps/yantorno-party

# Edit manifests.yaml or application.yaml
nano microk8s/apps/iam-dynamic/manifests.yaml

# Commit and push
git add microk8s/apps/iam-dynamic/manifests.yaml
git commit -m "fix: Update resource limits"
git push origin main
```

ArgoCD will automatically detect the change and sync the updates to your cluster.

### Manual Sync in ArgoCD

If you need to trigger an immediate sync:

1. Open ArgoCD UI
2. Click on **iam-dynamic** application
3. Click **"Sync"** button
4. Review and confirm

---

## 🔄 Rollback Procedures

### Via ArgoCD UI

1. Open the **iam-dynamic** application
2. Click **"History"** or **"Rollback"**
3. Select the revision you want to rollback to
4. Click **"Rollback"**

### Via kubectl

```bash
# View rollout history
microk8s kubectl rollout history deployment/iam-dynamic-backend -n iam-dynamic

# Rollback to previous revision
microk8s kubectl rollout undo deployment/iam-dynamic-backend -n iam-dynamic

# Rollback to specific revision
microk8s kubectl rollout undo deployment/iam-dynamic-backend -n iam-dynamic --to-revision=2
```

---

## 🔧 Troubleshooting

### Pod Not Starting

```bash
# Describe pod for detailed status
microk8s kubectl describe pod/<pod-name> -n iam-dynamic

# Check logs
microk8s kubectl logs <pod-name> -n iam-dynamic

# Common issues:
# - ImagePullBackOff: Check image name and GHCR access
# - CrashLoopBackOff: Check logs for application errors
# - Pending: Check resource requests/limits
```

### Secret Not Found

```bash
# Verify secret exists
microk8s kubectl get secret iam-dynamic-secret -n iam-dynamic

# If missing, re-apply
microk8s kubectl apply -f iam-dynamic-secret.yaml
```

### Ingress Not Working

```bash
# Check ingress resource
microk8s kubectl get ingress -n iam-dynamic

# Check Traefik logs
microk8s kubectl logs -n traefik deployment/traefik

# Verify DNS points to your cluster
nslookup iam.yourdomain.party
```

### PVC Not Binding

```bash
# Check PVC status
microk8s kubectl get pvc -n iam-dynamic

# Check storage class
microk8s kubectl get storageclass

# Verify MicroK8s storage is enabled
microk8s status | grep storage
```

### ArgoCD Sync Failures

```bash
# Check ArgoCD application status
microk8s kubectl get application iam-dynamic -n argocd -o yaml

# Check ArgoCD logs
microk8s kubectl logs -n argocd deployment/argocd-repo-server

# Force a fresh sync
microk8s kubectl patch application iam-dynamic -n argocd \
  --type='json' -p='[{"op": "replace", "path": "/spec/syncPolicy/automated/prune", "value": true}]'
```

---

## 🔒 Security Best Practices

### 1. Resource Limits

Always set resource requests and limits:

```yaml
resources:
  requests:
    memory: "256Mi"
    cpu: "100m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

### 2. Security Context

Run as non-root user:

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 1001
  allowPrivilegeEscalation: false
```

### 3. Network Policies

Consider adding network policies to restrict traffic:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: iam-dynamic-netpol
  namespace: iam-dynamic
spec:
  podSelector:
    matchLabels:
      app: iam-dynamic-backend
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 8000
  egress:
  - to:
    - namespaceSelector: {}
    ports:
    - protocol: TCP
      port: 53
```

### 4. Secrets Management

For production, consider using:
- **Sealed Secrets** - Encrypt secrets that can be safely committed to git
- **External Secrets Operator** - Sync secrets from external secret managers
- **Vault** - HashiCorp Vault for secret management

### 5. RBAC

Create appropriate RBAC policies:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: iam-dynamic-read-only
  namespace: iam-dynamic
subjects:
- kind: ServiceAccount
  name: iam-dynamic-sa
  namespace: iam-dynamic
roleRef:
  kind: Role
  name: read-only
  apiGroup: rbac.authorization.k8s.io
```

---

## 📊 Monitoring & Logging

### View Logs

```bash
# All pods
microk8s kubectl logs -l app=iam-dynamic-backend -n iam-dynamic

# Specific pod
microk8s kubectl logs -f <pod-name> -n iam-dynamic

# Previous container instance (if crashed)
microk8s kubectl logs <pod-name> -n iam-dynamic --previous
```

### Resource Usage

```bash
# Pod resource usage
microk8s kubectl top pods -n iam-dynamic

# Node resource usage
microk8s kubectl top nodes
```

### ArgoCD Application Health

In ArgoCD UI, check for:
- **Sync Status**: OK or Synced
- **Health Status**: Healthy
- **Resource Status**: All resources should be green

---

## 🎉 Next Steps

1. **Configure DNS**: Ensure your domain points to your MicroK8s server
2. **Set up monitoring**: Consider adding Prometheus/Grafana for observability
3. **Configure backup**: Back up your PVC data regularly
4. **Set up alerts**: Configure ArgoCD notifications for sync failures
5. **Test the full flow**: Create a test IAM access request

---

## 📚 Additional Resources

- [IAM-Dynamic Main README](../README.md)
- [Antsle Deployment Guide](antsle-deployment.md)
- [VPS Deployment Guide](vps-setup-guide.md)
- [CLAUDE.md](../CLAUDE.md) - Project documentation
- [yantorno-party](https://github.com/tupacalypse187/yantorno-party) - Home lab K8s manifests

---

**Enjoy your GitOps-powered IAM access portal! 🎊**
