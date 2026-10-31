/**
 * Auto-update wiring (electron-updater, generic provider).
 *
 * Policy: check on launch and every 4 hours; NEVER force-install.
 * The renderer is notified of every state change over IPC and owns all
 * user-facing copy via toasts — this module only moves bytes and reports.
 * Updates are disabled when no feed URL is configured (local dev) so
 * unpacked builds never phone home.
 */

import { BrowserWindow } from 'electron'
import { autoUpdater } from 'electron-updater'
import type { UpdaterEvent } from '../shared/ipc-contract'
import { IpcChannels } from '../shared/ipc-contract'

const CHECK_INTERVAL_MS = 4 * 60 * 60 * 1000

export interface UpdaterOptions {
  feedUrl: string | null
  isDev: boolean
  send: (window: BrowserWindow | null, event: UpdaterEvent) => void
  getWindow: () => BrowserWindow | null
  log: (...args: unknown[]) => void
}

function emit(opts: UpdaterOptions, event: UpdaterEvent): void {
  opts.send(opts.getWindow(), event)
}

export function setupAutoUpdater(opts: UpdaterOptions): void {
  if (opts.isDev || !opts.feedUrl) {
    opts.log('Auto-update disabled (dev mode or no feed URL configured).')
    return
  }

  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = false

  autoUpdater.on('checking-for-update', () => emit(opts, { type: 'checking' }))
  autoUpdater.on('update-available', (info) => {
    emit(opts, { type: 'available', version: info.version })
    // Pre-download in the background; the user still chooses when to restart.
    void autoUpdater.downloadUpdate().catch((err: unknown) => {
      opts.log('Update download failed:', err)
      emit(opts, {
        type: 'error',
        message: err instanceof Error ? err.message : 'Update download failed.',
      })
    })
  })
  autoUpdater.on('update-downloaded', (info) => emit(opts, { type: 'downloaded', version: info.version }))
  autoUpdater.on('update-not-available', () => emit(opts, { type: 'not-available' }))
  autoUpdater.on('error', (err: Error) => {
    opts.log('Auto-update error:', err)
    emit(opts, { type: 'error', message: err.message })
  })

  void autoUpdater.checkForUpdates().catch((err: unknown) => opts.log('Initial update check failed:', err))
  setInterval(() => {
    void autoUpdater.checkForUpdates().catch((err: unknown) => opts.log('Periodic update check failed:', err))
  }, CHECK_INTERVAL_MS).unref?.()
}

export function quitAndInstall(): void {
  autoUpdater.quitAndInstall(false, true)
}
