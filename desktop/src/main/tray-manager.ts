/**
 * Lease tray manager — countdown display, expiry warning, revocation.
 *
 * macOS shows the remaining lease in the menu-bar title (no icon asset
 * required); other platforms use tooltip + menu state. A native
 * notification fires 5 minutes before expiry with the window refocused
 * on click. All credential state stays in the in-memory LeaseState —
 * this module never persists secrets.
 */

import { Menu, Notification, Tray, nativeImage } from 'electron'
import type { LeaseStatus } from '../shared/ipc-contract'

export interface TrayCallbacks {
  onShow: () => void
  onRevoke: () => void
  onQuit: () => void
  getStatus: () => LeaseStatus
}

const WARN_BEFORE_SECONDS = 5 * 60

function formatRemaining(totalSeconds: number): string {
  const h = Math.floor(totalSeconds / 3600)
  const m = Math.floor((totalSeconds % 3600) / 60)
  const s = totalSeconds % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s.toString().padStart(2, '0')}s`
  return `${s}s`
}

export class LeaseTray {
  private tray: Tray | null = null
  private warnedForExpiry: string | null = null

  constructor(private callbacks: TrayCallbacks) {}

  attach(): void {
    if (this.tray) return
    // Empty image: macOS renders title-only; tooltip carries state elsewhere.
    this.tray = new Tray(nativeImage.createEmpty())
    this.tray.setToolTip('IAM Dynamic — no active lease')
    this.tray.on('click', () => this.callbacks.onShow())
    this.refresh()
  }

  /** Re-render title/menu from current lease state; also fires the 5-minute warning. */
  refresh(): void {
    if (!this.tray) return
    const status = this.callbacks.getStatus()

    if (!status.active || !status.expiresAt) {
      this.tray.setTitle('')
      this.tray.setToolTip('IAM Dynamic — no active lease')
      this.warnedForExpiry = null
    } else {
      const label = `⏳ ${formatRemaining(status.secondsRemaining)}`
      if (process.platform === 'darwin') this.tray.setTitle(label)
      this.tray.setToolTip(`IAM Dynamic — credentials expire in ${formatRemaining(status.secondsRemaining)}`)
      if (
        status.secondsRemaining <= WARN_BEFORE_SECONDS &&
        status.secondsRemaining > 0 &&
        this.warnedForExpiry !== status.expiresAt
      ) {
        this.warnedForExpiry = status.expiresAt
        this.notifyExpiring(status.secondsRemaining)
      }
      if (status.secondsRemaining === 0) {
        this.callbacks.onRevoke()
      }
    }

    this.tray.setContextMenu(
      Menu.buildFromTemplate([
        {
          label: status.active
            ? `Lease expires in ${formatRemaining(status.secondsRemaining)}`
            : 'No active credential lease',
          enabled: false,
        },
        { type: 'separator' },
        { label: 'Show IAM Dynamic', click: () => this.callbacks.onShow() },
        {
          label: 'Revoke Credentials',
          enabled: status.active,
          click: () => this.callbacks.onRevoke(),
        },
        { type: 'separator' },
        { label: 'Quit', click: () => this.callbacks.onQuit() },
      ]),
    )
  }

  private notifyExpiring(secondsRemaining: number): void {
    const note = new Notification({
      title: 'Credentials expiring soon',
      body: `Your temporary credentials expire in ${formatRemaining(secondsRemaining)}. Request an extension or revoke them from the tray.`,
    })
    note.on('click', () => this.callbacks.onShow())
    note.show()
  }

  destroy(): void {
    this.tray?.destroy()
    this.tray = null
  }
}
