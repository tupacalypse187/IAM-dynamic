import { useMemo, useState } from 'react'
import { Lightbulb, X } from 'lucide-react'
import { usePrefs } from '@/hooks/use-prefs'
import { tipFor } from '@/lib/tips'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'

/**
 * Startup tip card: bottom-right overlay with the tip of the day, themed
 * like the rest of the app. Session-dismissed with X; permanently off via
 * the checkbox or the Settings switch (same pref).
 */
export function StartupTip() {
  const { prefs, updatePrefs } = usePrefs()
  const [dismissed, setDismissed] = useState(false)
  const tip = useMemo(() => tipFor(), [])

  if (!prefs.startupTips || dismissed) return null

  return (
    <Card
      className="fixed bottom-4 right-4 z-50 w-80 shadow-lg"
      role="complementary"
      aria-label="Tip of the day"
    >
      <CardHeader className="flex flex-row items-center gap-2 space-y-0 pb-2">
        <Lightbulb className="h-4 w-4 text-primary" aria-hidden="true" />
        <CardTitle className="text-sm">Tip of the day</CardTitle>
        <Button
          variant="ghost"
          size="sm"
          className="ml-auto h-6 w-6 p-0"
          onClick={() => setDismissed(true)}
          aria-label="Dismiss tip"
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">{tip}</p>
        <div className="flex items-center justify-between gap-4">
          <Label htmlFor="startup-tip-hide" className="text-xs font-normal">
            Show on startup
          </Label>
          <Switch
            id="startup-tip-hide"
            checked={prefs.startupTips}
            onCheckedChange={(checked) => updatePrefs({ startupTips: checked })}
            aria-label="Show tips on startup"
          />
        </div>
      </CardContent>
    </Card>
  )
}
