import { useState, useEffect } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Lock, LogOut, Loader2, Menu, User } from 'lucide-react'
import { api } from './lib/api'
import { useAuth } from './hooks/use-auth'
import { ThemeProvider } from './components/theme-provider'
import { Toaster } from './components/toaster'
import { useToast } from './hooks/use-toast'
import { ErrorBoundary } from './components/error-boundary'
import Sidebar, { SidebarContent } from './components/sidebar'
import { Sheet, SheetContent, SheetTitle, SheetDescription } from './components/ui/sheet'
import { Button } from './components/ui/button'
import type { PolicyResponse, Credentials } from './types/api'
import RequestView from './views/request-view'
import ReviewView from './views/review-view'
import CredentialsView from './views/credentials-view'
import RejectedView from './views/rejected-view'
import LoginView from './views/login-view'

type ViewType = 'request' | 'review' | 'credentials' | 'rejected'

function AppShell() {
  const { isAuthenticated, isLoading, username, logout, authRequired } = useAuth()
  const { toast } = useToast()
  const queryClient = useQueryClient()
  const [view, setView] = useState<ViewType>('request')
  const [policyData, setPolicyData] = useState<PolicyResponse | null>(null)
  const [duration, setDuration] = useState(2)
  const [credentials, setCredentials] = useState<Credentials | null>(null)
  const [requestText, setRequestText] = useState('')
  const [selectedProvider, setSelectedProvider] = useState<string>('gemini')
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [mobileNavOpen, setMobileNavOpen] = useState(false)

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

  const sidebarProps = {
    config,
    configLoading,
    configError,
    onRetryConfig: retryConfig,
    onRequestTextChange: setRequestText,
    selectedProvider,
    onProviderChange: setSelectedProvider,
    selectedModel,
    onModelChange: setSelectedModel,
  }

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Desktop sidebar rail */}
      <Sidebar {...sidebarProps} />

      {/* Mobile navigation drawer */}
      <Sheet open={mobileNavOpen} onOpenChange={setMobileNavOpen}>
        <SheetContent
          side="left"
          className="w-80 bg-sidebar p-0 text-sidebar-foreground [&>button]:text-sidebar-foreground"
        >
          <SheetTitle className="sr-only">Navigation and settings</SheetTitle>
          <SheetDescription className="sr-only">
            AI provider, model and quick request templates
          </SheetDescription>
          <SidebarContent {...sidebarProps} onTemplateSelected={() => setMobileNavOpen(false)} />
        </SheetContent>
      </Sheet>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        {/* Header */}
        <header className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/75">
          <div className="flex h-16 items-center justify-between gap-3 px-4 sm:px-6">
            <div className="flex min-w-0 items-center">
              <Button
                variant="ghost"
                size="icon"
                className="mr-1 lg:hidden"
                onClick={() => setMobileNavOpen(true)}
                aria-label="Open navigation menu"
              >
                <Menu className="h-5 w-5" />
              </Button>
              <div className="flex items-center gap-2">
                <Lock className="h-6 w-6 shrink-0 text-primary" aria-hidden="true" />
                <h1 className="truncate text-lg font-bold sm:text-xl">IAM-Dynamic Portal</h1>
              </div>
              <p className="ml-4 hidden text-sm text-muted-foreground md:block">
                AI-Driven Least Privilege Access
              </p>
            </div>
            {authRequired && (
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <User className="h-4 w-4" aria-hidden="true" />
                  {username}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={logout}
                  aria-label="Sign out"
                >
                  <LogOut className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        </header>

        {/* Content */}
        <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
          <ErrorBoundary>
            {view === 'request' && (
              <RequestView
                requestText={requestText}
                onRequestTextChange={setRequestText}
                duration={duration}
                onDurationChange={setDuration}
                selectedProvider={selectedProvider}
                selectedModel={selectedModel}
                onPolicyGenerated={(data) => {
                  setPolicyData(data)
                  setView('review')
                }}
              />
            )}

            {view === 'review' && policyData && (
              <ReviewView
                policyData={policyData}
                onBack={() => setView('request')}
                onCredentialsIssued={(creds) => {
                  setCredentials(creds)
                  setView('credentials')
                }}
                onRejected={() => setView('rejected')}
              />
            )}

            {view === 'rejected' && policyData && (
              <RejectedView
                policyData={policyData}
                requestText={requestText}
                duration={duration}
                selectedProvider={selectedProvider}
                selectedModel={selectedModel}
                onReviseRequest={(text) => {
                  setRequestText(text)
                  setView('request')
                }}
                onStartFresh={() => {
                  setPolicyData(null)
                  setRequestText('')
                  setDuration(2)
                  setView('request')
                }}
              />
            )}

            {view === 'credentials' && credentials && (
              <CredentialsView
                credentials={credentials}
                duration={duration}
                onNewRequest={() => {
                  setPolicyData(null)
                  setCredentials(null)
                  setRequestText('')
                  setDuration(2)
                  setView('request')
                }}
              />
            )}
          </ErrorBoundary>
        </div>
      </main>

      <Toaster />
    </div>
  )
}

function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="iam-theme">
      <AppShell />
    </ThemeProvider>
  )
}

export default App
