import { EyeOff } from 'lucide-react'
import { Button } from './ui/button'

// TEMPORARY — hackathon demo aid. Remove entirely for production:
// delete this file, the View-as menu in App.tsx, the use-auth impersonate
// seam, and the backend impersonate endpoint + DEMO_VIEW_USERS allowlist.
// This session runs on a short-lived impersonation token: the UI genuinely
// verifies as the demo user (non-admin), while the admin's real token is
// kept in memory for one-click exit. The switch itself is audit-logged
// server-side as impersonation_started with the admin as actor.
export function PreviewBanner({ username, onExit }: { username: string; onExit: () => void }) {
  return (
    <div
      className="app-no-drag flex items-center gap-2 border-b border-warning/40 bg-warning/15 px-4 py-1.5 text-xs sm:px-6"
      role="status"
    >
      <span className="min-w-0 flex-1 truncate">
        Viewing as {username} — temporary demo impersonation (15-minute token). Actions are
        audited as {username}; exit to restore the admin session.
      </span>
      <Button variant="outline" size="sm" className="h-7 shrink-0" onClick={onExit}>
        <EyeOff className="mr-1 h-3 w-3" aria-hidden="true" />
        Exit view-as
      </Button>
    </div>
  )
}
