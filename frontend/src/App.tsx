import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Lock, LogOut, Loader2, User } from 'lucide-react'
import { api } from './lib/api'
import { useAuth } from './components/auth-provider'
import { ThemeProvider } from './components/theme-provider'
import Sidebar from './components/sidebar'
import RequestView from './views/request-view'
import ReviewView from './views/review-view'
import CredentialsView from './views/credentials-view'
import RejectedView from './views/rejected-view'
import LoginView from './views/login-view'
import { Button } from './components/ui/button'

type ViewType = 'request' | 'review' | 'credentials' | 'rejected'

interface PolicyData {
  policy: Record<string, unknown>
  risk: 'low' | 'medium' | 'high' | 'critical'
  explanation: string
  approver_note: string
  auto_approved: boolean
  max_duration: number
}

function App() {
  const { isAuthenticated, isLoading, username, logout, authRequired } = useAuth()
  const [view, setView] = useState<ViewType>('request')
  const [policyData, setPolicyData] = useState<PolicyData | null>(null)
  const [duration, setDuration] = useState(2)
  const [credentials, setCredentials] = useState<any>(null)
  const [requestText, setRequestText] = useState('')
  const [selectedProvider, setSelectedProvider] = useState<string>('gemini')
  const [selectedModel, setSelectedModel] = useState<string>('')

  // Fetch providers and config (only when authenticated)
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: api.getProviders,
    enabled: isAuthenticated,
  })

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
      <ThemeProvider defaultTheme="system" storageKey="iam-theme">
        <div className="flex h-screen items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      </ThemeProvider>
    )
  }

  // Auth gate — show login when auth is required and user is not authenticated
  if (authRequired && !isAuthenticated) {
    return (
      <ThemeProvider defaultTheme="system" storageKey="iam-theme">
        <LoginView />
      </ThemeProvider>
    )
  }

  return (
    <ThemeProvider defaultTheme="system" storageKey="iam-theme">
      <div className="flex h-screen overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          config={config}
          onRequestTextChange={setRequestText}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
          selectedModel={selectedModel}
          onModelChange={setSelectedModel}
        />

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto">
          {/* Header */}
          <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container flex h-16 items-center justify-between px-6">
              <div className="flex items-center">
                <div className="flex items-center gap-2">
                  <Lock className="h-6 w-6 text-primary" />
                  <h1 className="text-xl font-bold">IAM-Dynamic Portal</h1>
                </div>
                <p className="ml-4 text-sm text-muted-foreground">
                  AI-Driven Least Privilege Access
                </p>
              </div>
              {authRequired && (
                <div className="flex items-center gap-3">
                  <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <User className="h-4 w-4" />
                    {username}
                  </span>
                  <Button variant="ghost" size="sm" onClick={logout} title="Sign out">
                    <LogOut className="h-4 w-4" />
                  </Button>
                </div>
              )}
            </div>
          </header>

          {/* Content */}
          <div className="container py-6 px-6">
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
          </div>
        </main>
      </div>
    </ThemeProvider>
  )
}

export default App
