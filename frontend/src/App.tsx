import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Lock } from 'lucide-react'
import { api } from './lib/api'
import { ThemeProvider } from './components/theme-provider'
import Sidebar from './components/sidebar'
import RequestView from './views/request-view'
import ReviewView from './views/review-view'
import CredentialsView from './views/credentials-view'
import RejectedView from './views/rejected-view'

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
  const [view, setView] = useState<ViewType>('request')
  const [policyData, setPolicyData] = useState<PolicyData | null>(null)
  const [duration, setDuration] = useState(2)
  const [credentials, setCredentials] = useState<any>(null)
  const [requestText, setRequestText] = useState('')
  const [selectedProvider, setSelectedProvider] = useState<string>('gemini')

  // Fetch providers and config
  const { data: config } = useQuery({
    queryKey: ['config'],
    queryFn: api.getProviders,
  })

  return (
    <ThemeProvider defaultTheme="system" storageKey="iam-theme">
      <div className="flex h-screen overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          config={config}
          requestText={requestText}
          onRequestTextChange={setRequestText}
          selectedProvider={selectedProvider}
          onProviderChange={setSelectedProvider}
        />

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto">
          {/* Header */}
          <header className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
            <div className="container flex h-16 items-center px-6">
              <div className="flex items-center gap-2">
                <Lock className="h-6 w-6 text-primary" />
                <h1 className="text-xl font-bold">IAM-Dynamic Portal</h1>
              </div>
              <p className="ml-4 text-sm text-muted-foreground">
                AI-Driven Least Privilege Access
              </p>
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
                onPolicyGenerated={(data) => {
                  setPolicyData(data)
                  setView('review')
                }}
              />
            )}

            {view === 'review' && policyData && (
              <ReviewView
                policyData={policyData}
                requestText={requestText}
                duration={duration}
                onDurationChange={setDuration}
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
