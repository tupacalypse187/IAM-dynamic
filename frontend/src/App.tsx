import { useState, useEffect, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Lock,
  LogOut,
  Loader2,
  Menu,
  User,
  FilePlus2,
  FolderOpen,
  ShieldCheck,
  Settings as SettingsIcon,
  PanelLeft,
} from 'lucide-react'
import { api, getToken } from './lib/api'
import { desktop, isMacDesktop, queryPlatform } from './lib/desktop'
import { useGlobalShortcuts, useCaptureShortcut } from './lib/shortcuts'
import { hasSeenTour, launchTour } from './lib/tour'
import { useAuth } from './hooks/use-auth'
import { usePrefs } from './hooks/use-prefs'
import type { SubmitOutcome } from './hooks/use-policy-agent'
import { ThemeProvider } from './components/theme-provider'
import { PrefsProvider, Tip } from './components/tip'
import { PreviewBanner } from './components/preview-banner'
import { Toaster } from './components/toaster'
import { useToast } from './hooks/use-toast'
import { ErrorBoundary } from './components/error-boundary'
import UpdateBanner from './components/update-manager'
import Sidebar, { SidebarContent } from './components/sidebar'
import { Sheet, SheetContent, SheetTitle, SheetDescription } from './components/ui/sheet'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './components/ui/select'
import { Button } from './components/ui/button'
import { Badge } from './components/ui/badge'
import { Separator } from './components/ui/separator'
import type { AccessRequest, Credentials, PolicyResponse } from './types/api'
import type { GuardrailFinding } from './types/desktop'
import RequestView from './views/request-view'
import MyRequestsView from './views/my-requests-view'
import RequestDetailView from './views/request-detail-view'
import ReviewDashboardView from './views/review-dashboard-view'
import CredentialsView from './views/credentials-view'
import RejectedView from './views/rejected-view'
import SettingsView from './views/settings-view'
import LoginView from './views/login-view'

type ViewType = 'submit' | 'mine' | 'detail' | 'dashboard' | 'credentials' | 'rejected' | 'settings'

function focusRequestBox() {
  setTimeout(() => document.getElementById('request-textarea')?.focus(), 100)
}

function AppShell() {
  const { isAuthenticated, isLoading, username, isAdmin, login, impersonate, logout, authRequired } = useAuth()
  const { prefs, updatePrefs } = usePrefs()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [view, setView] = useState<ViewType>('submit')
  const [activeRequest, setActiveRequest] = useState<AccessRequest | null>(null)
  const [detailOrigin, setDetailOrigin] = useState<'mine' | 'dashboard'>('mine')
  const [findings, setFindings] = useState<GuardrailFinding[]>([])
  const [summary, setSummary] = useState<string | null>(null)
  const [appVersion, setAppVersion] = useState<string | null>(null)
  const [backendUrl, setBackendUrl] = useState<string | null>(null)
  const [appPlatform, setAppPlatform] = useState<string | null>(null)
  const [duration, setDuration] = useState(2)
  const [environment, setEnvironment] = useState<'dev' | 'stage' | 'prod'>('dev')
  const [credentials, setCredentials] = useState<Credentials | null>(null)
  const [deniedRequest, setDeniedRequest] = useState<AccessRequest | null>(null)
  const [requestText, setRequestText] = useState('')
  const [selectedProvider, setSelectedProvider] = useState<string>('muse')
  const [selectedModel, setSelectedModel] = useState<string>('muse-spark-1.3-contributor')
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  // TEMPORARY — hackathon demo aid. View-as session for a demo user:
  // the admin's real token is kept in memory while a short-lived
  // impersonation token drives the UI. Remove with PreviewBanner and the
  // impersonate endpoint before production (see that file).
  const [viewAs, setViewAs] = useState<{ username: string; adminToken: string; adminName: string } | null>(null)
  // Effective role for UI gating. Server enforcement is unchanged, and the
  // impersonation token itself verifies as non-admin.
  const showAdminUI = isAdmin && !viewAs

  // Demo view-as candidates (admins only; cached list stays while viewing as).
  const demoUsersQuery = useQuery({
    queryKey: ['demo-users'],
    queryFn: api.listDemoUsers,
    enabled: isAuthenticated && isAdmin && !viewAs,
  })
  const demoUsers = demoUsersQuery.data?.users ?? []

  const exitViewAs = useCallback(() => {
    if (!viewAs) return
    const { adminToken, adminName } = viewAs
    setViewAs(null)
    setView('submit')
    // Restores the admin session (and re-verifies is_admin).
    login(adminToken, adminName)
    queryClient.invalidateQueries()
  }, [viewAs, login, queryClient])

  const enterViewAs = useCallback(async (target: string) => {
    // While already viewing as someone, the stored admin session mints
    // the next switch — the localStorage token is the view-as one.
    const adminToken = viewAs?.adminToken ?? getToken()
    const adminName = viewAs?.adminName ?? username
    if (!adminToken || !adminName) return
    try {
      const session = await api.impersonate(target)
      // Vault untouched — the admin token is restored from memory on exit.
      setViewAs({ username: session.username, adminToken, adminName })
      setView('submit')
      impersonate(session.token, session.username)
      queryClient.invalidateQueries()
    } catch (err) {
      toast({
        title: 'View-as failed',
        description: err instanceof Error ? err.message : 'Could not switch user.',
        variant: 'destructive',
      })
    }
  }, [viewAs, username, impersonate, queryClient, toast])

  // macOS frameless clearance, most-authoritative first: the platform the
  // main process injected into the URL (?platform=darwin) — structural and
  // independent of bridge/navigator — then live detection, then the IPC
  // platform once the bridge answers.
  const [queryPlat] = useState(() => queryPlatform())
  const macDesktop =
    queryPlat === 'darwin' ||
    isMacDesktop() ||
    (desktop.isDesktop && appPlatform === 'darwin')

  // Fetch providers and config (only when authenticated)
  const {
    data: config,
    isLoading: configLoading,
    isError: configError,
  } = useQuery({
    queryKey: ['config'],
    queryFn: api.getProviders,
    enabled: isAuthenticated,
  })

  // Admin review queue count for the nav badge (admins only, not previewing)
  const queueCountQuery = useQuery({
    queryKey: ['requests', 'queue-count'],
    queryFn: () => api.listRequests({ status: 'pending_review' }),
    enabled: isAuthenticated && showAdminUI,
    refetchInterval: 30000,
  })
  const pendingCount = queueCountQuery.data?.length ?? 0

  // Saved LLM profiles; the active one's key evaluates new requests.
  const profilesQuery = useQuery({
    queryKey: ['profiles'],
    queryFn: api.listProfiles,
    enabled: isAuthenticated,
  })
  const profiles = profilesQuery.data ?? []
  const activeProfile = profiles.find((p) => p.active) ?? null

  // Surface forced 401 logouts with an explanation instead of silently
  // snapping back to the login screen
  useEffect(() => {
    const handler = () => {
      toast({
        title: 'Session expired',
        description: 'Please sign in again to continue.',
        variant: 'destructive',
      })
    }
    window.addEventListener('auth:logout', handler)
    return () => window.removeEventListener('auth:logout', handler)
  }, [toast])

  // Set default provider and model from backend config when loaded
  useEffect(() => {
    if (config?.current_provider) {
      setSelectedProvider(config.current_provider)
      const provider = config.providers.find(p => p.id === config.current_provider)
      if (provider?.model) {
        setSelectedModel(provider.model)
      }
    }
  }, [config])

  // Desktop app info for the title bar, About section, and platform check
  useEffect(() => {
    if (!desktop.isDesktop) return
    desktop
      .getAppInfo()
      .then((info) => {
        setAppVersion(info.version)
        setBackendUrl(info.backendUrl)
        setAppPlatform(info.platform)
      })
      .catch(() => undefined)
  }, [])

  // First-run guided tour (submit view only, once, unless disabled in Settings)
  useEffect(() => {
    if (!isAuthenticated || view !== 'submit') return
    if (!prefs.tourAutoplay || hasSeenTour()) return
    const timer = setTimeout(() => launchTour(), 800)
    return () => clearTimeout(timer)
  }, [isAuthenticated, view, prefs.tourAutoplay])

  // `?` opens Settings; global capture focuses the request box
  const openSettings = useCallback(() => setView('settings'), [])
  useGlobalShortcuts(openSettings)
  const handleCapture = useCallback(() => {
    setView('submit')
    toast({
      title: 'Quick capture',
      description: 'Describe the job below — voice transcription is coming soon.',
    })
    focusRequestBox()
  }, [toast])
  useCaptureShortcut(handleCapture)

  // Loading state
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-label="Loading" />
      </div>
    )
  }

  // Auth gate — show login when auth is required and user is not authenticated
  if (authRequired && !isAuthenticated) {
    return <LoginView />
  }

  const retryConfig = () => queryClient.invalidateQueries({ queryKey: ['config'] })
  const refreshRequests = () => {
    queryClient.invalidateQueries({ queryKey: ['requests'] })
    queryClient.invalidateQueries({ queryKey: ['audit'] })
  }

  const openDetail = (request: AccessRequest, origin: 'mine' | 'dashboard', keepContext = false) => {
    setActiveRequest(request)
    setDetailOrigin(origin)
    if (!keepContext) {
      setFindings([])
      setSummary(null)
    }
    setView('detail')
  }

  const handleSubmitted = (outcome: SubmitOutcome) => {
    refreshRequests()
    setActiveRequest(outcome.request)
    setFindings(outcome.findings)
    setSummary(outcome.summary)
    setDetailOrigin('mine')
    setView('detail')
  }

  const resetSubmitForm = () => {
    setRequestText('')
    setDuration(2)
  }

  const gotoSubmitForEdit = (text: string, requestDuration: number, provider: string, model: string | null, environment: string) => {
    setRequestText(text)
    setDuration(requestDuration)
    setSelectedProvider(provider)
    if (model) setSelectedModel(model)
    if (environment === 'stage' || environment === 'prod') setEnvironment(environment)
    setView('submit')
    focusRequestBox()
  }

  const handleClone = async (request: AccessRequest, edit: boolean) => {
    if (edit) {
      gotoSubmitForEdit(request.request_text, request.duration, request.provider, request.model, request.environment)
      return
    }
    // Clone as-is: resubmit the stored parameters directly.
    try {
      const cloned = await api.submitRequest({
        request_text: request.request_text,
        provider: request.provider,
        model: request.model ?? undefined,
        duration: request.duration,
        environment: request.environment,
      })
      refreshRequests()
      openDetail(cloned[0], 'mine')
    } catch (err) {
      toast({
        title: 'Clone failed',
        description: err instanceof Error ? err.message : 'Could not resubmit that request.',
        variant: 'destructive',
      })
    }
  }

  const handleChanged = (updated: AccessRequest) => {
    setActiveRequest(updated)
    refreshRequests()
  }

  const handleCredentialsIssued = (creds: Credentials) => {
    setCredentials(creds)
    refreshRequests()
    setView('credentials')
  }

  const deniedPolicy: PolicyResponse | null = deniedRequest
    ? {
        policy: deniedRequest.policy,
        risk: deniedRequest.risk,
        explanation: deniedRequest.explanation,
        approver_note: deniedRequest.approver_note,
        auto_approved: deniedRequest.auto_approved,
        max_duration: deniedRequest.duration,
      }
    : null

  const sidebarProps = {
    config,
    onRequestTextChange: setRequestText,
    macDesktop,
    showTopStrip: false,
    profiles,
    onSelectProfile: (id: number) => {
      void api
        .activateProfile(id)
        .then(() => queryClient.invalidateQueries({ queryKey: ['profiles'] }))
        .catch((err: Error) => {
          toast({
            title: 'Could not switch profile',
            description: err.message,
            variant: 'destructive',
          })
        })
    },
    onManageProfiles: () => setView('settings'),
  }

  const navButtonClass = (target: ViewType) =>
    view === target || (target === 'mine' && view === 'detail' && detailOrigin === 'mine')
      ? 'bg-muted text-foreground'
      : 'text-muted-foreground'

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      {/* Full-width traffic-light clearance (macOS frameless window only).
          Structural: sits above sidebar AND content, so the lights overlap
          nothing whether the rail is open or closed — independent of bridge
          and navigator detection, which both failed in the field. */}
      {macDesktop && (
        <div className="app-drag h-7 w-full shrink-0 select-none" aria-hidden="true" />
      )}

      <div className="flex min-h-0 flex-1">
        {/* Collapsible sidebar rail (toolbar toggle; drawer covers small screens) */}
        {!prefs.sidebarCollapsed && <Sidebar {...sidebarProps} />}

        {/* Mobile navigation drawer */}
        <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
          <SheetContent
            side="left"
            className="w-80 bg-sidebar p-0 text-sidebar-foreground [&>button]:text-sidebar-foreground"
          >
            <SheetTitle className="sr-only">Navigation and settings</SheetTitle>
            <SheetDescription className="sr-only">
              Quick request templates
            </SheetDescription>
            <SidebarContent {...sidebarProps} showTopStrip onTemplateSelected={() => setMobileNavOpen(false)} />
          </SheetContent>
        </Sheet>

        {/* Right column: fixed bars + independent scroll area */}
        <div className="flex min-w-0 flex-1 flex-col">
        {/* Title bar — the window drag region (see .app-drag). Text only,
            never clickable controls, so grabbing anywhere on this bar moves
            the window. Fully opaque: content scrolls underneath invisibly. */}
        <div
          className={`app-drag flex h-11 shrink-0 select-none items-center gap-2 border-b bg-muted px-4 ${
            macDesktop ? 'pl-20' : ''
          }`}
        >
          <Lock className="h-4 w-4 shrink-0 text-primary" aria-hidden="true" />
          <span className="truncate text-sm font-semibold">IAM-Dynamic</span>
          <Badge variant="outline" className="shrink-0 text-xs">
            {appVersion ? `v${appVersion}` : 'local'}
          </Badge>
          <Separator orientation="vertical" className="mx-1 h-5" />
          {username && (
            <span className="flex min-w-0 items-center gap-1.5 text-sm text-muted-foreground">
              <User className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
              <span className="truncate">{username}</span>
              {isAdmin && (
                <Badge variant="secondary" className="shrink-0 text-xs">
                  admin
                </Badge>
              )}
            </span>
          )}
        </div>

        {/* Toolbar — clickable app controls, explicitly outside the drag
            region so window buttons and actions never overlap. */}
        <header className="app-no-drag flex h-14 shrink-0 items-center gap-1 border-b bg-background px-4 sm:gap-2 sm:px-6">
          <Tip label={prefs.sidebarCollapsed ? 'Show sidebar' : 'Hide sidebar'}>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => updatePrefs({ sidebarCollapsed: !prefs.sidebarCollapsed })}
              aria-label={prefs.sidebarCollapsed ? 'Show sidebar' : 'Hide sidebar'}
              aria-expanded={!prefs.sidebarCollapsed}
              className="hidden lg:inline-flex"
            >
              <PanelLeft className="h-5 w-5" />
            </Button>
          </Tip>
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setMobileNavOpen(true)}
            aria-label="Open navigation menu"
          >
            <Menu className="h-5 w-5" />
          </Button>
          <nav className="flex min-w-0 items-center gap-1" aria-label="Primary">
            <Tip label="Describe a new access need">
              <Button variant="ghost" size="sm" className={navButtonClass('submit')} onClick={() => setView('submit')}>
                <FilePlus2 className="h-4 w-4 sm:mr-1.5" aria-hidden="true" />
                <span className="hidden sm:inline">New Request</span>
              </Button>
            </Tip>
            <Tip label="Your live sessions, open requests, and history">
              <Button variant="ghost" size="sm" className={navButtonClass('mine')} onClick={() => setView('mine')}>
                <FolderOpen className="h-4 w-4 sm:mr-1.5" aria-hidden="true" />
                <span className="hidden sm:inline">My Requests</span>
              </Button>
            </Tip>
            {showAdminUI && (
              <Tip label="Review every requester’s queue">
                <Button
                  variant="ghost"
                  size="sm"
                  className={view === 'dashboard' || (view === 'detail' && detailOrigin === 'dashboard') ? 'bg-muted text-foreground' : 'text-muted-foreground'}
                  onClick={() => setView('dashboard')}
                >
                  <ShieldCheck className="h-4 w-4 sm:mr-1.5" aria-hidden="true" />
                  <span className="hidden sm:inline">Review</span>
                  {pendingCount > 0 && (
                    <Badge className="ml-1.5 bg-warning/20 text-warning">{pendingCount}</Badge>
                  )}
                </Button>
              </Tip>
            )}
            <Tip label="Preferences, demo, help guides, and about">
              <Button variant="ghost" size="sm" className={navButtonClass('settings')} onClick={() => setView('settings')}>
                <SettingsIcon className="h-4 w-4 sm:mr-1.5" aria-hidden="true" />
                <span className="hidden sm:inline">Settings</span>
              </Button>
            </Tip>
          </nav>
          <div className="ml-auto flex items-center gap-1">
            {/* TEMPORARY — hackathon demo aid; remove with PreviewBanner. */}
            {(isAdmin || viewAs) && demoUsers.length > 0 && (
              <Tip label={viewAs ? `Viewing as ${viewAs.username} — switch user or exit below` : 'Switch to a seeded demo user (view-as, 15-minute token)'}>
                <Select value="" onValueChange={(v) => { if (v) void enterViewAs(v) }}>
                  <SelectTrigger
                    className="h-8 w-[8.5rem] border-transparent text-muted-foreground"
                    aria-label={viewAs ? `Viewing as ${viewAs.username}. Switch demo user` : 'View app as a demo user'}
                  >
                    <SelectValue placeholder={viewAs ? viewAs.username : 'View as…'} />
                  </SelectTrigger>
                  <SelectContent>
                    {demoUsers
                      .filter((u) => u.username !== viewAs?.username)
                      .map((u) => (
                        <SelectItem key={u.username} value={u.username}>
                          {u.username}
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </Tip>
            )}
            {authRequired && (
              <Tip label="Sign out of this session">
                <Button variant="ghost" size="sm" onClick={logout} aria-label="Sign out">
                  <LogOut className="h-4 w-4" />
                </Button>
              </Tip>
            )}
          </div>
        </header>

        {/* TEMPORARY — hackathon demo aid; remove with the menu above. */}
        {viewAs && <PreviewBanner username={viewAs.username} onExit={exitViewAs} />}

        {/* Content — the only scrolling region; bars stay fixed above it */}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
            <ErrorBoundary>
              {view === 'submit' && (
                <RequestView
                  requestText={requestText}
                  onRequestTextChange={setRequestText}
                  duration={duration}
                  onDurationChange={setDuration}
                  environment={environment}
                  onEnvironmentChange={setEnvironment}
                  selectedProvider={selectedProvider}
                  selectedModel={selectedModel}
                  activeProfileId={activeProfile?.id ?? null}
                  activeProfileName={activeProfile?.name ?? null}
                  onSubmitted={handleSubmitted}
                />
              )}

              {view === 'mine' && (
                <MyRequestsView
                  onNewRequest={() => {
                    resetSubmitForm()
                    setView('submit')
                    focusRequestBox()
                  }}
                  onOpenRequest={(request) => openDetail(request, 'mine')}
                  onCloneRequest={handleClone}
                />
              )}

              {view === 'dashboard' &&
                (showAdminUI ? (
                  <ReviewDashboardView onOpenRequest={(request) => openDetail(request, 'dashboard')} />
                ) : (
                  <MyRequestsView
                    onNewRequest={() => {
                      resetSubmitForm()
                      setView('submit')
                      focusRequestBox()
                    }}
                    onOpenRequest={(request) => openDetail(request, 'mine')}
                    onCloneRequest={handleClone}
                  />
                ))}

              {view === 'detail' && activeRequest && (
                <RequestDetailView
                  request={activeRequest}
                  isAdmin={showAdminUI}
                  isOwner={username !== null && activeRequest.requester === username}
                  findings={findings}
                  summary={summary}
                  onBack={() => setView(detailOrigin === 'dashboard' && showAdminUI ? 'dashboard' : 'mine')}
                  onChanged={handleChanged}
                  onCredentialsIssued={handleCredentialsIssued}
                  onResubmit={(request) =>
                    gotoSubmitForEdit(request.request_text, request.duration, request.provider, request.model, request.environment)
                  }
                  onShowGuidance={(request) => {
                    setDeniedRequest(request)
                    setView('rejected')
                  }}
                  onApplySuggestion={(suggestion) => {
                    setRequestText(
                      `${requestText}\n\nRequested fix from guardrail: ${suggestion}`.trim(),
                    )
                    setView('submit')
                    focusRequestBox()
                  }}
                />
              )}

              {view === 'settings' && (
                <SettingsView
                  appVersion={appVersion}
                  backendUrl={backendUrl}
                  isAdmin={showAdminUI}
                  authRequired={authRequired}
                  diagnostics={{
                    bridge: desktop.isDesktop,
                    urlPlatform: queryPlat,
                    liveDetect: isMacDesktop(),
                    effective: macDesktop,
                  }}
                  config={config}
                  configLoading={configLoading}
                  configError={configError}
                  onRetryConfig={retryConfig}
                  selectedProvider={selectedProvider}
                  onProviderChange={setSelectedProvider}
                  selectedModel={selectedModel}
                  onModelChange={setSelectedModel}
                />
              )}

              {view === 'rejected' && deniedPolicy && deniedRequest && (
                <RejectedView
                  policyData={deniedPolicy}
                  requestText={deniedRequest.request_text}
                  duration={deniedRequest.duration}
                  selectedProvider={deniedRequest.provider}
                  reviewer={deniedRequest.reviewer}
                  reviewerFeedback={deniedRequest.feedback}
                  onReviseRequest={(text) => {
                    gotoSubmitForEdit(text, deniedRequest.duration, deniedRequest.provider, deniedRequest.model, deniedRequest.environment)
                  }}
                  onStartFresh={() => {
                    setDeniedRequest(null)
                    resetSubmitForm()
                    setView('submit')
                    focusRequestBox()
                  }}
                />
              )}

              {view === 'credentials' && credentials && (
                <CredentialsView
                  credentials={credentials}
                  duration={duration}
                  onNewRequest={() => {
                    setCredentials(null)
                    setActiveRequest(null)
                    setFindings([])
                    setSummary(null)
                    resetSubmitForm()
                    setView('mine')
                  }}
                />
              )}
            </ErrorBoundary>
          </div>
        </main>
        </div>
      </div>

      <Toaster />
      <UpdateBanner />
    </div>
  )
}

function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="iam-theme">
      <PrefsProvider>
        <AppShell />
      </PrefsProvider>
    </ThemeProvider>
  )
}

export default App
