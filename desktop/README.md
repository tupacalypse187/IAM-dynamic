# 🖥️ IAM-Dynamic Desktop

Electron shell for the IAM-Dynamic Security Studio. Reuses the web frontend and remote FastAPI backend; adds tray lease tracking, OS credential storage, global capture, guided tour, and auto-updates.

Full guide: [`docs/desktop-app.md`](../docs/desktop-app.md) · Updates & releases: [`docs/auto-update.md`](../docs/auto-update.md)

## Quick start

```bash
npm install          # includes native rebuild (better-sqlite3, keytar)
npm run dev          # needs backend on :8000 + frontend dev server on :3000

npm run typecheck    # CI gate (no native bindings required)
npm run build        # compile main + preload to dist/

npm run dist:mac     # arm64 .dmg (signs when CSC_NAME / Apple creds exist)
npm run dist:win     # x64 NSIS — prefer CodeBuild (see docs/auto-update.md)
npm run dist:linux   # arm64 AppImage + deb
```

## Config

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `IAM_DESKTOP_BACKEND_URL` | `http://localhost:8000` | FastAPI base URL |
| `IAM_DESKTOP_UPDATE_FEED_URL` | *(unset = updates off)* | Release feed for `electron-updater` |
| `IAM_DESKTOP_DEV` | *(unset = auto)* | `1` forces dev mode; packaged apps use `app.isPackaged` |
| `CSC_NAME` | auto | macOS signing identity |
| `APPLE_ID` / `APPLE_APP_SPECIFIC_PASSWORD` / `APPLE_TEAM_ID` | *(unset = skip)* | Notarization |

Icons regenerate via `npm run icons` (needs Pillow) and are gitignored. Windows releases publish with `-p always -c.publish.provider=generic -c.publish.url="$UPDATE_FEED_URL"` — publishing is CLI-only so local builds never phone home.
