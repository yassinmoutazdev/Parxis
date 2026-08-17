import { useEffect, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import DashboardPage from './features/dashboard/DashboardPage'
import ReportsPage from './features/reports/ReportsPage'
import SettingsPage from './features/settings/SettingsPage'
import BackupsPage from './features/settings/BackupsPage'
import ChatPage from './features/chat/ChatPage'
import Sidebar from './features/chat/Sidebar'
import { ConnectScreen } from './features/settings/components/ConnectScreen'
import { getOllamaKeyStatus } from './api/client'
import * as ApiClient from './api/client'
import { LoadingSpinner } from './shared/components/LoadingSpinner'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      refetchOnWindowFocus: false,
    },
  },
})

// Global error handler for ollama_auth_failed
// We patch the request function to dispatch a custom event on auth failure
const originalRequest = (ApiClient as any).request || (async () => {})
if (typeof originalRequest === 'function') {
  // Wrap the request function to catch ollama_auth_failed
  const originalFetch = window.fetch
  window.fetch = async function fetchWithAuthCheck(...args) {
    const response = await originalFetch.apply(this, args)
    // Check for ollama_auth_failed error shape
    if (response.status === 424 || response.status === 401) {
      const contentType = response.headers.get('content-type')
      if (contentType?.includes('application/json')) {
        // Clone response to read body without consuming original
        const cloned = response.clone()
        try {
          const body = await cloned.json()
          if (body.error === 'ollama_auth_failed' || body.code === 'ollama_auth_failed') {
            // Dispatch custom event for app-level handler
            window.dispatchEvent(new CustomEvent('ollama-auth-failed'))
          }
        } catch {
          // Ignore parse errors
        }
      }
    }
    return response
  }
}

function App() {
  const [isCheckingAuth, setIsCheckingAuth] = useState(true)
  const [showConnectScreen, setShowConnectScreen] = useState(false)

  useEffect(() => {
    checkAuthStatus()
  }, [])

  const checkAuthStatus = async () => {
    try {
      const status = await getOllamaKeyStatus()
      setShowConnectScreen(!status.configured)
    } catch {
      // On any error, assume not configured
      setShowConnectScreen(true)
    } finally {
      setIsCheckingAuth(false)
    }
  }

  const handleAuthFailed = () => {
    setShowConnectScreen(true)
  }

  const handleConnected = () => {
    setShowConnectScreen(false)
    // Invalidate queries to refresh data that may need the key
    queryClient.invalidateQueries()
  }

  // Listen for global ollama_auth_failed events
  useEffect(() => {
    window.addEventListener('ollama-auth-failed', handleAuthFailed)
    return () => window.removeEventListener('ollama-auth-failed', handleAuthFailed)
  }, [])

  // Show a branded launch screen while checking auth, instead of a bare
  // unbranded spinner on an otherwise-empty page. Reuses the shared
  // LoadingSpinner so this stays in sync with its styling everywhere else.
  if (isCheckingAuth) {
    return (
      <div className="flex flex-col min-h-screen items-center justify-center gap-4 bg-cream">
        <h1 className="text-2xl font-serif text-ink">Parxis</h1>
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  // Show ConnectScreen if no valid key
  if (showConnectScreen) {
    return (
      <ConnectScreen
        onConnected={handleConnected}
      />
    )
  }

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex h-screen bg-cream">
          {/* Sidebar */}
          <div className="flex-shrink-0">
            <Sidebar />
          </div>

          {/* Main Content */}
          <main className="flex-1 overflow-y-auto">
            <Routes>
              {/* Chat - root goes to new chat */}
              <Route path="/" element={<ChatPage />} />
              <Route path="/chat/:threadId" element={<ChatPage />} />

              {/* Other pages - render in content area */}
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/settings/backups" element={<BackupsPage />} />

              {/* Fallback - redirect to chat */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
