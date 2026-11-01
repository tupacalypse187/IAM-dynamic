import type { AccessRequest, RequestStatus } from '@/types/api'

// Static class maps — Tailwind's JIT scanner must see full class names,
// so status/risk colors can never be assembled at runtime.
export const statusStyles: Record<RequestStatus, { badge: string; label: string }> = {
  pending_review: { badge: 'bg-warning/15 text-warning', label: 'Needs review' },
  approved: { badge: 'bg-success/15 text-success', label: 'Approved' },
  denied: { badge: 'bg-destructive/15 text-destructive', label: 'Denied' },
  changes_requested: { badge: 'bg-orange-600/15 text-orange-700 dark:text-orange-400', label: 'Changes requested' },
  activated: { badge: 'bg-primary/15 text-primary', label: 'Active' },
  discarded: { badge: 'bg-muted text-muted-foreground', label: 'Discarded' },
  cancelled: { badge: 'bg-muted text-muted-foreground', label: 'Cancelled' },
}

export const riskBadgeClass: Record<string, string> = {
  low: 'bg-success/15 text-success',
  medium: 'bg-warning/15 text-warning',
  high: 'bg-orange-600/15 text-orange-700 dark:text-orange-400',
  critical: 'bg-destructive/15 text-destructive',
}

export const riskLabel: Record<string, string> = {
  low: 'Low Risk',
  medium: 'Medium Risk',
  high: 'High Risk',
  critical: 'Critical Risk',
}

/** Terminal states — no further action is possible on the request. */
export function isTerminal(status: RequestStatus): boolean {
  return status === 'denied' || status === 'activated' || status === 'discarded' || status === 'cancelled'
}

/** Group rows by batch (single-unit batches stand alone). */
export function groupByBatch(rows: AccessRequest[]): { batchId: number; rows: AccessRequest[] }[] {
  const groups = new Map<number, AccessRequest[]>()
  for (const row of rows) {
    const key = row.batch_id ?? row.id
    const list = groups.get(key)
    if (list) list.push(row)
    else groups.set(key, [row])
  }
  return [...groups.entries()]
    .map(([batchId, batchRows]) => ({ batchId, rows: batchRows }))
    .sort((a, b) => b.batchId - a.batchId)
}

/** Requests still waiting on someone: a reviewer, or the owner. */
export function isOpen(status: RequestStatus): boolean {
  return status === 'pending_review' || status === 'changes_requested' || status === 'approved'
}

/**
 * Who decided this request, from the requester's perspective. Auto-approved
 * rows with no human reviewer report the automated system, never nobody.
 */
export function reviewerDisplay(request: Pick<AccessRequest, 'reviewer' | 'auto_approved' | 'status'>): string {
  if (request.reviewer) return request.reviewer
  if (request.auto_approved && (request.status === 'approved' || request.status === 'activated')) {
    return 'Automated system'
  }
  return 'Awaiting reviewer'
}

/** Live sessions: activated and not yet expired. */
export function isLiveSession(
  request: Pick<AccessRequest, 'status' | 'credentials_expires_at'>,
  now: number = Date.now(),
): boolean {
  if (request.status !== 'activated' || !request.credentials_expires_at) return false
  return Date.parse(request.credentials_expires_at) > now
}

/** One-line excerpt for queue rows. */
export function requestExcerpt(text: string, maxLength = 120): string {
  const singleLine = text.replace(/\s+/g, ' ').trim()
  if (singleLine.length <= maxLength) return singleLine
  return `${singleLine.slice(0, maxLength - 1).trimEnd()}…`
}
