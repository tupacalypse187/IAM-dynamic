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
import { Ledger, eventsToMarkdown } from './ledger'
import { vault } from './vault'
import { createBackendClient } from './agentkit/backend-client'
import {
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
  type GenerateInput,
  type IssueInput,
  type UpdaterEvent,
} from '../shared/ipc-contract'

const CAPTURE_SHORTCUT = 'CommandOrControl+Shift+I'
const DEV_URL = 'http://localhost:3000'

const config = loadConfig(app.isPackaged)
const lease: LeaseState = { credentials: null, issuedAt: null }
let mainWindow: BrowserWindow | null = null
let ledger: Ledger | null = null
let leaseTray: LeaseTray | null = null

const backend = createBackendClient({ baseUrl: config.backendUrl, getToken: () => vault.getToken() })

function sendToRenderer(channel: string, payload: unknown): void {
  mainWindow?.webContents.send(channel, payload)
}

function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 960,
    minHeight: 640,
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

  if (config.isDev) {
    void window.loadURL(DEV_URL)
    window.webContents.openDevTools({ mode: 'detach' })
  } else {
    void window.loadFile(path.join(__dirname, '../../frontend-dist/index.html'))
  }

  // Keep navigation inside the app; external links open in the browser.
  window.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url)
    return { action: 'deny' }
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

function showWindow(): void {
  if (!mainWindow) {
    mainWindow = createWindow()
  } else if (mainWindow.isMinimized()) {
    mainWindow.restore()
  }
  mainWindow.show()
  mainWindow.focus()
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

  ipcMain.handle(IpcChannels.agentRevoke, () => {
    if (!ledger) throw new Error('Audit ledger is not initialized.')
    revokeCredentials({ backend, ledger }, lease)
    leaseTray?.refresh()
  })

  ipcMain.handle(IpcChannels.leaseStatus, () => leaseStatus(lease))

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
  showWindow()

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
