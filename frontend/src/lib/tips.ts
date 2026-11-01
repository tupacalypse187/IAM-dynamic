/**
 * Rotating startup tips: one per day, deterministic from the date so every
 * launch on the same day shows the same tip. Keep entries short, factual,
 * and tied to real UI (view names, control labels).
 */
export const TIPS: string[] = [
  'Search the review queue by req-00001, request text, or person name.',
  'Clone any prior request to resubmit it, or clone & edit to adjust it first.',
  'The Technical tab highlights IAM actions and ARNs as code spans.',
  'Pick a policy JSON theme in Settings — One Dark and GitHub Dark avoid the stock brown.',
  'Dev grants stay re-activatable for 31 days; stage must activate within 72 hours, prod within 24.',
  'Low-risk dev units activate immediately while riskier units wait for review.',
  'Cancel an approved grant early from its detail page — issued sessions still run to expiry.',
  'Press ? anywhere to open Help with shortcuts and guides.',
  'Save a request profile to pin your provider, model, and key for one-click submits.',
  'Admins: the Audit trail tab opens any request straight from an event row.',
]

/** Zero-based day-of-year (UTC) for rotation. */
function dayOfYear(date: Date): number {
  const start = Date.UTC(date.getUTCFullYear(), 0, 0)
  return Math.floor((date.getTime() - start) / 86_400_000)
}

/** The tip for a given date (defaults to today). */
export function tipFor(date: Date = new Date()): string {
  return TIPS[dayOfYear(date) % TIPS.length]
}
