# 📣 Slack App Setup

Connects the backend's Block Kit audit posts (`backend/services/slack_service.py`) to a Slack channel via an incoming webhook. Verified end-to-end with a live test post.

## 📑 Table of Contents

- [🧾 App Manifest](#-app-manifest)
- [🖼️ App Icon](#-app-icon)
- [🚀 Setup Steps](#-setup-steps)
- [🔌 Wiring the Backend](#-wiring-the-backend)
- [🧪 Testing](#-testing)
- [🛠️ Troubleshooting](#-troubleshooting)

## 🧾 App Manifest

Create at [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From manifest** → paste:

```yaml
display_information:
  name: IAM-Dynamic
  description: Just-in-time IAM access requests with AI-generated least-privilege policies.
  background_color: "#0f172a"
features:
  bot_user:
    display_name: IAM-Dynamic
    always_online: false
oauth_config:
  scopes:
    bot:
      - incoming-webhook
      - chat:write
      - channels:join
      - channels:history
      - canvases:write
      - reactions:write
settings:
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
```

Threaded one-thread-per-request posts need the Web API (`chat:write`) in
addition to the webhook. Webhook-only installs keep working — they post
top-level exactly as before, with no threading.

## 🖼️ App Icon

Upload under **Basic Information** → **Display information** (manifests can't carry the image). Requirements: square PNG, 512–2000px per side. The in-repo icon (`generated_images/slack-app-icon-1280.png`, shield + keyhole on navy, 1280×1280) matches the desktop app branding.

## 🚀 Setup Steps

1. Create the app from the manifest above (pick the workspace, **Create**).
2. Upload the icon (see above).
3. Left sidebar **Incoming Webhooks** → toggle **Activate Incoming Webhooks** to On.
4. **Add New Webhook to Workspace** → pick the audit channel (e.g. `#iam-audit`) → **Allow**.
5. Copy the URL (`https://hooks.slack.com/services/…`) — Slack shows it once; the API never reveals it again, and the Slack CLI cannot mint or list it.

If the workspace requires admin approval for apps, approve the request first, then continue at step 3.

## 🔌 Wiring the Backend

```bash
# in .env (gitignored, never committed)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/…
# Threaded posts (optional but recommended — one thread per access request):
# install the app with the chat:write scope, then copy the Bot User OAuth
# Token (xoxb-…) and the channel ID (right-click channel → Copy link, or
# View channel details; looks like C012AB345CD).
SLACK_BOT_TOKEN=xoxb-…
SLACK_CHANNEL_ID=C012AB345CD
```

Restart the backend. Every credential issuance, approval, and error path in `slack_service.py` posts automatically; with no webhook configured the service logs and skips.

## 🧵 Threaded posts (one thread per request)

When `SLACK_BOT_TOKEN` + `SLACK_CHANNEL_ID` are set, the backend posts via
`chat.postMessage`: each request opens exactly one thread root (requester,
`req-00001` ref, risk, status, timestamp) and every later event for that
request — decision, resubmission, activation/issuance — lands as a threaded
reply carrying actor + timestamp. The root id (`ts`) is persisted in the
request row (`slack_thread_ts`), claimed atomically so retries never open a
second thread. Requests created before threading was enabled get their root
created lazily on the next event (no backfill needed).

Without the bot token the backend keeps the exact webhook top-level
behaviour. **After adding `chat:write` to the manifest the workspace owner
must reinstall the app** (Slack prompts on the app's install page) —
the implementer cannot do this step.

## 🧪 Testing

```bash
cd backend
./venv/bin/python -c "
from dotenv import load_dotenv; load_dotenv('../.env')
import os
from services.slack_service import SlackService
print('sent:', SlackService(os.getenv('SLACK_WEBHOOK_URL')).send_notification('IAM-Dynamic webhook check — safe to delete.'))
"
```

Confirm the message lands in-channel.

## 🛠️ Troubleshooting

| Symptom | Cause / Fix |
| ------- | ----------- |
| No posts, no errors | Webhook URL missing/blank in `.env`, or backend not restarted after adding it |
| `404` / `invalid_token` | Webhook revoked or pasted with truncation — regenerate at Incoming Webhooks and replace the full URL |
| Posts land in the wrong channel | Webhooks are pinned to the channel chosen at creation — add another webhook per channel and swap the URL |
| Want per-user DMs instead | Not supported — the backend posts to the one audit channel only (the bot token enables threading there, not DMs) |
| Threaded replies land top-level | Bot token/channel missing or app not reinstalled after adding `chat:write` — webhook fallback posts top-level by design |
