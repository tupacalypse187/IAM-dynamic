/** Deployment-tier grant windows (mirrors ENVIRONMENTS in backend/main.py). */

export type EnvironmentId = 'dev' | 'stage' | 'prod'

export interface EnvConfig {
  label: string
  maxHours: number
  windowNote: string
  presets: number[]
}

export const ENVIRONMENTS: Record<EnvironmentId, EnvConfig> = {
  dev: {
    label: 'Development',
    maxHours: 744,
    windowNote: 'Up to 31 days. Approved grants re-activate in fresh ≤12h sessions — no resubmission.',
    presets: [2, 12, 168, 744],
  },
  stage: {
    label: 'Staging',
    maxHours: 168,
    windowNote: 'Up to 7 days, single activation within 72h of approval.',
    presets: [2, 12, 72, 168],
  },
  prod: {
    label: 'Production',
    maxHours: 2,
    windowNote: 'Max 2 hours, single activation within 24h of approval. Low-risk still auto-approves.',
    presets: [1, 2],
  },
}

export function formatGrantLength(hours: number): string {
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'}`
  const days = hours / 24
  return `${Number.isInteger(days) ? days : days.toFixed(1)} day${days === 1 ? '' : 's'}`
}
