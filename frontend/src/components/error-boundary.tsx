import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'
import { Button } from './ui/button'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
}

/**
 * Catches render errors in the app shell so a crash in one view
 * shows a recoverable fallback instead of a blank page.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled render error:', error, info.componentStack)
  }

  private handleReset = () => {
    this.setState({ hasError: false })
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-[50vh] items-center justify-center p-6">
          <div className="max-w-md rounded-lg border border-destructive/30 bg-destructive/5 p-6 text-center">
            <AlertTriangle className="mx-auto h-8 w-8 text-destructive" aria-hidden="true" />
            <h2 className="mt-3 text-lg font-semibold">Something went wrong</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              An unexpected error occurred while rendering this page. Your session is
              still active — try again, or reload if the problem persists.
            </p>
            <div className="mt-4 flex justify-center gap-2">
              <Button onClick={this.handleReset} variant="outline">
                <RotateCcw className="h-4 w-4" />
                Try again
              </Button>
              <Button onClick={() => window.location.reload()}>Reload page</Button>
            </div>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
