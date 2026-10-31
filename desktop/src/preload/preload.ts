import { contextBridge, ipcRenderer } from 'electron'
import type {
  AppInfo,
  AuditEvent,
  GenerateInput,
  GenerateResult,
  IssueInput,
  LeaseCredentials,
  LeaseStatus,
  AgentProgress,
  UpdaterEvent,
} from '../shared/ipc-contract'
import { IpcChannels } from '../shared/ipc-contract'

/**
 * Secure preload bridge. Only the channels below are exposed to the
 * renderer — no blanket `ipcRenderer` access, no Node globals.
 */
const desktopApi = {
  getAppInfo: (): Promise<AppInfo> => ipcRenderer.invoke(IpcChannels.appInfo),

  generatePolicy: (input: GenerateInput): Promise<GenerateResult> =>
    ipcRenderer.invoke(IpcChannels.agentGenerate, input),
  onAgentProgress: (listener: (progress: AgentProgress) => void): (() => void) => {
    const handler = (_event: unknown, progress: AgentProgress) => listener(progress)
    ipcRenderer.on(IpcChannels.agentProgress, handler as never)
    return () => ipcRenderer.removeListener(IpcChannels.agentProgress, handler as never)
  },

  issueCredentials: (input: IssueInput): Promise<LeaseCredentials> =>
    ipcRenderer.invoke(IpcChannels.agentIssue, input),
  activateRequest: (requestId: number): Promise<LeaseCredentials> =>
    ipcRenderer.invoke(IpcChannels.agentActivate, requestId),
  logAudit: (kind: string, summary: string, details?: Record<string, unknown>): Promise<number> =>
    ipcRenderer.invoke(IpcChannels.ledgerAppend, kind, summary, details ?? {}),
  revokeCredentials: (): Promise<void> => ipcRenderer.invoke(IpcChannels.agentRevoke),
  getLeaseStatus: (): Promise<LeaseStatus> => ipcRenderer.invoke(IpcChannels.leaseStatus),

  getRecentEvents: (limit?: number): Promise<AuditEvent[]> =>
    ipcRenderer.invoke(IpcChannels.ledgerRecent, limit),
  exportLedger: (format: 'markdown' | 'json'): Promise<string> =>
    ipcRenderer.invoke(IpcChannels.ledgerExport, format),

  setToken: (token: string): Promise<void> => ipcRenderer.invoke(IpcChannels.vaultSetToken, token),
  clearToken: (): Promise<void> => ipcRenderer.invoke(IpcChannels.vaultClearToken),

  checkForUpdates: (): Promise<void> => ipcRenderer.invoke(IpcChannels.updaterCheck),
  quitAndInstall: (): Promise<void> => ipcRenderer.invoke(IpcChannels.updaterQuitInstall),
  onUpdaterEvent: (listener: (event: UpdaterEvent) => void): (() => void) => {
    const handler = (_event: unknown, event: UpdaterEvent) => listener(event)
    ipcRenderer.on(IpcChannels.updaterEvent, handler as never)
    return () => ipcRenderer.removeListener(IpcChannels.updaterEvent, handler as never)
  },

  onCaptureShortcut: (listener: () => void): (() => void) => {
    const handler = () => listener()
    ipcRenderer.on(IpcChannels.shortcutCapture, handler)
    return () => ipcRenderer.removeListener(IpcChannels.shortcutCapture, handler)
  },
}

export type DesktopApi = typeof desktopApi

contextBridge.exposeInMainWorld('desktopApi', desktopApi)
