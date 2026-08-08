import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import DashboardPage from './features/dashboard/DashboardPage'
import ApprovalsPage from './features/approvals/ApprovalsPage'
import ReportsPage from './features/reports/ReportsPage'
import SettingsPage from './features/settings/SettingsPage'
import BackupsPage from './features/settings/BackupsPage'
import ChatPage from './features/chat/ChatPage'
import Sidebar from './features/chat/Sidebar'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      refetchOnWindowFocus: false,
    },
  },
})

function App() {
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
              <Route path="/approvals" element={<ApprovalsPage />} />
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
