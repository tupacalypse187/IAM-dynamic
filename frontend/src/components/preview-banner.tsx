import { EyeOff } from 'lucide-react'
import { Button } from './ui/button'

// TEMPORARY — hackathon demo aid. Remove entirely for production:
// delete this file, the toggle in App.tsx, and the preview branch logic.
// This is client-side UI masking ONLY. It never changes tokens, requests,
// or server-side role enforcement: forged review calls still get 403s,
// and every action keeps the admin's real identity in the audit trail.
export function PreviewBanner({ onExit }: { onExit: () => void }) {
  return (
    <div
      className="app-no-drag flex items-center gap-2 border-b border-warning/40 bg-warning/15 px-4 py-1.5 text-xs sm:px-6"
      role="status"
    >
      <span className="min-w-0 flex-1 truncate">
        Viewing as a regular user — temporary demo mode. Admin controls are hidden, not disabled
        server-side.
      </span>
      <Button variant="outline" size="sm" className="h-7 shrink-0" onClick={onExit}>
        <EyeOff className="mr-1 h-3 w-3" aria-hidden="true" />
        Exit preview
      </Button>
    </div>
  )
}
