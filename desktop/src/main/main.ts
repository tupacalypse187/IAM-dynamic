/**
 * IAM-Dynamic Desktop — Electron main process.
 *
 * Responsibilities: native window chrome per OS, typed IPC handlers that
 * delegate to Agent_Kit, lease tray + expiry notifications, global voice
 * capture shortcut, auto-updates, and single-instance enforcement.
 * No policy or credential *content* decisions live here.
 */

import path from 'node:path'
import { app, BrowserWindow, globalShortcut, ipcMain, shell } from 'electron'
import { autoUpdater } from 'electron-updater'
import { loadConfig } from './config'
import { DEV_URL, isAllowedExternalUrl, isInternalNavigationUrl } from './navigation'
import { Ledger, eventsToMarkdown } from './ledger'
import { vault } from './vault'
import { createBackendClient } from './agentkit/backend-client'
import {
  activateRequest,
  generatePolicy,
  issueCredentials,
  leaseStatus,
  revokeCredentials,
  type LeaseState,
} from './agentkit/index'
import { setupAutoUpdater, quitAndInstall } from './updater'
import { LeaseTray } from './tray-manager'
import {
  IpcChannels,
  type AgentProgress,
  type AuditKind,
  type GenerateInput,
  type IssueInput,
  type UpdaterEvent,
} from '../shared/ipc-contract'

const CAPTURE_SHORTCUT = 'CommandOrControl+Shift+I'

const config = loadConfig(app.isPackaged)
const lease: LeaseState = { credentials: null, issuedAt: null }
let mainWindow: BrowserWindow | null = null
let ledger: Ledger | null = null
let leaseTray: LeaseTray | null = null

const backend = createBackendClient({ baseUrl: config.backendUrl, getToken: () => vault.getToken() })

function sendToRenderer(channel: string, payload: unknown): void {
  mainWindow?.webContents.send(channel, payload)
}

/** Minimum splash visibility: the brand moment is never a flash frame. */
const SPLASH_MIN_MS = 3000

function splashAssetPath(): string {
  // dist/main/main.js -> <app-root>/assets in dev and packaged builds alike.
  return path.join(__dirname, '../../assets/splash.html')
}

function createSplash(version: string, onShown: () => void): BrowserWindow {
  const splash = new BrowserWindow({
    width: 520,
    height: 380,
    resizable: false,
    minimizable: false,
    maximizable: false,
    fullscreenable: false,
    // macOS: plain window (traffic lights would overlap the art).
    // Win/Linux: frameless for the same centered-card look.
    ...(process.platform === 'darwin'
      ? { titleBarStyle: 'hidden' as const }
      : { frame: false }),
    backgroundColor: '#0f172a',
    center: true,
    show: false,
    // The splash is the only window for its 3 seconds: above everything,
    // focused on show, main window stays hidden until handover.
    // screen-saver level keeps it above other apps' windows for the
    // brief brand moment (dropped on close).
    alwaysOnTop: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })
  splash.setAlwaysOnTop(true, 'screen-saver')
  let shown = false
  const showSplash = () => {
    if (shown || splash.isDestroyed()) return
    shown = true
    splash.show()
    // show() alone does not bring the app forward on macOS when launched
    // behind other apps: lift the window, then (macOS only) activate the
    // app. Other platforms keep plain show+focus so we never steal focus
    // aggressively there (focus() alone just flashes the taskbar).
    splash.moveTop()
    if (process.platform === 'darwin') app.focus({ steal: true })
    splash.focus()
    onShown()
  }
  splash.once('ready-to-show', showSplash)
  // Fallback: a static local page should always emit ready-to-show, but
  // if it never fires the splash must still appear promptly instead of
  // leaving a hidden app behind.
  splash.webContents.once('did-finish-load', showSplash)
  const fallback = setTimeout(showSplash, 1500)
  fallback.unref?.()
  void splash.loadFile(splashAssetPath(), { hash: `v=${version}` })
  return splash
}

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
    // Hidden until the splash lifecycle releases it (dev skips the splash).
    show: false,
    // macOS: borderless w/ traffic lights; Win/Linux fall back to native frame.
    ...(process.platform === 'darwin'
      ? { titleBarStyle: 'hiddenInset' as const, vibrancy: 'under-window' as const }
      : {}),
    backgroundColor: '#0f172a',
    webPreferences: {
      preload: path.join(__dirname, '../preload/preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  })

  // The main process knows the OS with certainty; inject it as a query
  // param so the renderer reserves traffic-light clearance structurally
  // instead of depending on bridge/navigator sniffing (both have failed in
  // the field). No client router exists, so the query string is inert.
  const platformQuery = { platform: process.platform }
  if (config.isDev) {
    void window.loadURL(`${DEV_URL}?platform=${process.platform}`)
    window.webContents.openDevTools({ mode: 'detach' })
  } else {
    void window.loadFile(path.join(__dirname, '../../frontend-dist/index.html'), {
      query: platformQuery,
    })
  }

  // Keep navigation inside the app; http(s) links open in the OS browser,
  // everything else is denied outright (never handed to a file or protocol
  // handler). The will-navigate guard below covers same-window navigation
  // (e.g. a clicked Markdown link without target=_blank), which would
  // otherwise load an external page inside the window with preload bridge
  // (vault token) access.
  window.webContents.setWindowOpenHandler(({ url }) => {
    if (isAllowedExternalUrl(url)) {
      void shell.openExternal(url)
    }
    return { action: 'deny' }
  })
  window.webContents.on('will-navigate', (event, url) => {
    if (isInternalNavigationUrl(url)) return
    event.preventDefault()
    if (isAllowedExternalUrl(url)) {
      void shell.openExternal(url)
    }
  })

  // Never show a blank window silently: surface load failures in-window
  // with the URL and error code so a bad base path or missing bundle
  // is diagnosable instead of a blue screen.
  window.webContents.on('did-fail-load', (_event, code, description, url) => {
    // eslint-disable-next-line no-console
    console.error(`Renderer failed to load ${url}: [${code}] ${description}`)
    if (window.isDestroyed() || url.startsWith('data:')) return
    const safeUrl = url.replace(/[<>&"]/g, '')
    const safeDescription = description.replace(/[<>&"]/g, '')
    void window.loadURL(
      `data:text/html,<html><body style="font-family:sans-serif;padding:40px;background:#0f172a;color:#e2e8f0">` +
        `<h1>Could not load the app</h1><p>${safeDescription} (code ${code})</p>` +
        `<p><code>${safeUrl}</code></p>` +
        `<p>Check IAM_DESKTOP_BACKEND_URL and reinstall from a fresh download.</p>` +
        `</body></html>`,
    )
  })

  window.on('closed', () => {
    if (mainWindow === window) mainWindow = null
  })
  return window
}

function ensureWindow(): BrowserWindow {
  if (!mainWindow) {
    mainWindow = createWindow()
  } else if (mainWindow.isMinimized()) {
    mainWindow.restore()
  }
  return mainWindow
}

function showWindow(): void {
  const window = ensureWindow()
  window.show()
  window.focus()
}

function registerIpc(): void {
  ipcMain.handle(IpcChannels.appInfo, () => ({
    version: app.getVersion(),
    platform: process.platform,
    backendUrl: config.backendUrl,
    updatesEnabled: !config.isDev && config.updateFeedUrl !== null,
  }))

  ipcMain.handle(IpcChannels.agentGenerate, (event, input: GenerateInput) => {
    const progress = (p: AgentProgress) => {
      event.sender.send(IpcChannels.agentProgress, p)
    }
    if (!ledger) throw new Error('Audit ledger is not initialized.')
    return generatePolicy({ backend, ledger }, input, progress)
  })

  ipcMain.handle(IpcChannels.agentIssue, (_event, input: IssueInput) => {
    if (!ledger) throw new Error('Audit ledger is not initialized.')
    return issueCredentials({ backend, ledger }, lease, input).finally(() => leaseTray?.refresh())
  })

  ipcMain.handle(IpcChannels.agentActivate, (_event, requestId: number) => {
    if (!ledger) throw new Error('Audit ledger is not initialized.')
    return activateRequest({ backend, ledger }, lease, requestId).finally(() => leaseTray?.refresh())
  })

  ipcMain.handle(IpcChannels.agentRevoke, () => {
    if (!ledger) throw new Error('Audit ledger is not initialized.')
    revokeCredentials({ backend, ledger }, lease)
    leaseTray?.refresh()
  })

  ipcMain.handle(IpcChannels.leaseStatus, () => leaseStatus(lease))

  ipcMain.handle(
    IpcChannels.ledgerAppend,
    (_event, kind: AuditKind, summary: string, details?: Record<string, unknown>) => {
      if (!ledger) throw new Error('Audit ledger is not initialized.')
      return ledger.append(kind, summary, details ?? {})
    },
  )

  ipcMain.handle(IpcChannels.ledgerRecent, (_event, limit?: number) => {
    if (!ledger) return []
    return ledger.recent(typeof limit === 'number' ? limit : 100)
  })

  ipcMain.handle(IpcChannels.ledgerExport, (_event, format: 'markdown' | 'json') => {
    if (!ledger) return format === 'json' ? '[]' : '# No audit events yet\n'
    const events = ledger.recent(500)
    return format === 'json' ? JSON.stringify(events, null, 2) : eventsToMarkdown(events)
  })

  ipcMain.handle(IpcChannels.vaultSetToken, (_event, token: string) => vault.setToken(token))
  ipcMain.handle(IpcChannels.vaultGetToken, () => vault.getToken())
  ipcMain.handle(IpcChannels.vaultClearToken, () => vault.clearToken())

  ipcMain.handle(IpcChannels.updaterCheck, () => {
    if (config.isDev || !config.updateFeedUrl) return
    void autoUpdater.checkForUpdates()
  })
  ipcMain.handle(IpcChannels.updaterQuitInstall, () => quitAndInstall())
}

function registerCaptureShortcut(): void {
  const ok = globalShortcut.register(CAPTURE_SHORTCUT, () => {
    showWindow()
    sendToRenderer(IpcChannels.shortcutCapture, undefined)
  })
  if (!ok) {
    // eslint-disable-next-line no-console
    console.warn(`Global shortcut ${CAPTURE_SHORTCUT} could not be registered (already in use?).`)
  }
}

async function startup(): Promise<void> {
  ledger = new Ledger(path.join(app.getPath('userData'), 'ledger.db'))
  registerIpc()

  if (config.isDev) {
    // Dev loop stays fast: no splash, main window straight up.
    showWindow()
  } else {
    // Cold start: brand splash for at least SPLASH_MIN_MS of *visible*
    // time, then hand over to the main window once it has painted. The
    // did-finish-load fallback covers renderers that never emit
    // ready-to-show. The main window is never shown before the splash
    // closes, so the splash owns the screen.
    // The 3s clock starts when the splash actually appears (anchored in
    // the onShown callback), not when createSplash is called: loadFile
    // and ready-to-show are async, so anchoring at call time would make
    // the visible time shorter than SPLASH_MIN_MS.
    let splashShownAt: number | null = null
    let released = false
    let releasePendingSplash = false
    const finish = () => {
      if (!splash.isDestroyed()) splash.close()
      if (!window.isDestroyed()) {
        if (!window.isVisible()) window.show()
        window.focus()
      }
    }
    const scheduleFinish = () => {
      const shownAt = splashShownAt ?? Date.now()
      const wait = Math.max(0, SPLASH_MIN_MS - (Date.now() - shownAt))
      setTimeout(finish, wait)
    }
    const splash = createSplash(app.getVersion(), () => {
      splashShownAt = Date.now()
      // Main window was already ready while the splash was still
      // loading: start the 3s visible clock now.
      if (releasePendingSplash) {
        releasePendingSplash = false
        scheduleFinish()
      }
    })
    const window = ensureWindow()
    const release = () => {
      if (released) return
      released = true
      if (splashShownAt === null) {
        // Splash not visible yet: wait for it to appear so the user
        // still gets the full brand moment instead of a flash frame.
        // Absolute failsafe: if the splash never appears, hand over
        // anyway rather than leaving the app hidden behind nothing.
        releasePendingSplash = true
        const force = setTimeout(() => {
          if (releasePendingSplash) {
            releasePendingSplash = false
            finish()
          }
        }, SPLASH_MIN_MS + 5000)
        force.unref?.()
        return
      }
      scheduleFinish()
    }
    window.once('ready-to-show', release)
    window.webContents.once('did-finish-load', release)
  }

  leaseTray = new LeaseTray({
    onShow: showWindow,
    onRevoke: () => {
      if (ledger && lease.credentials) {
        revokeCredentials({ backend, ledger }, lease)
        leaseTray?.refresh()
      }
    },
    onQuit: () => app.quit(),
    getStatus: () => leaseStatus(lease),
  })
  leaseTray.attach()
  const tick = setInterval(() => leaseTray?.refresh(), 1000)
  tick.unref?.()

  setupAutoUpdater({
    feedUrl: config.updateFeedUrl,
    isDev: config.isDev,
    getWindow: () => mainWindow,
    send: (window, event: UpdaterEvent) => window?.webContents.send(IpcChannels.updaterEvent, event),
    log: (...args: unknown[]) => console.log('[updater]', ...args),
  })

  registerCaptureShortcut()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) showWindow()
  })
}

// Single instance: a second launch focuses the running app.
const gotLock = app.requestSingleInstanceLock()
if (!gotLock) {
  app.quit()
} else {
  app.on('second-instance', showWindow)
  void app.whenReady().then(startup)
}

app.on('window-all-closed', () => {
  // Keep the tray lease manager alive on macOS; quit elsewhere.
  if (process.platform !== 'darwin') app.quit()
})

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
  leaseTray?.destroy()
  // Lease credentials are memory-only and die with the process by design.
  lease.credentials = null
  ledger?.close()
})
