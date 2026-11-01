import { Badge } from './ui/badge'
import { Tip } from './tip'
import { ENV_STYLES, envOf } from '@/types/api'

const ENV_TIPS: Record<string, string> = {
  dev: 'Development grant — up to 31 days, re-activatable',
  stage: 'Staging grant — up to 7 days, single activation',
  prod: 'Production grant — max 2 hours, single activation',
}

/** Color indicator for the request's environment tier. */
export function EnvBadge({ environment }: { environment: string | null | undefined }) {
  const env = envOf(environment)
  const style = ENV_STYLES[env]
  return (
    <Tip label={ENV_TIPS[env]}>
      <Badge className={style.badgeClass} aria-label={`Environment: ${style.label}`}>
        <span className={`mr-1 inline-block h-1.5 w-1.5 rounded-full ${style.dotClass}`} aria-hidden="true" />
        {style.label}
      </Badge>
    </Tip>
  )
}
