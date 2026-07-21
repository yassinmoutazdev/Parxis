import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import DashboardPage from './features/dashboard/DashboardPage'
import ApprovalsPage from './features/approvals/ApprovalsPage'
import QuizPage from './features/quizzes/QuizPage'
import WritingPage from './features/writing/WritingPage'
import ReportsPage from './features/reports/ReportsPage'
import SettingsPage from './features/settings/SettingsPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60, // 1 minute
      refetchOnWindowFocus: false,
    },
  },
})

const navLinks = [
  { to: '/', label: 'Dashboard' },
  { to: '/approvals', label: 'Approvals' },
  { to: '/quizzes', label: 'Quizzes' },
  { to: '/writing', label: 'Writing' },
  { to: '/reports', label: 'Reports' },
  { to: '/settings', label: 'Settings' },
]

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-cream">
          {/* Navigation */}
          <nav className="bg-cream border-b border-border">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between h-16">
                <div className="flex">
                  <div className="flex-shrink-0 flex items-center">
                    <span className="font-serif text-xl text-ink">Praxis</span>
                  </div>
                  <div className="ml-8 flex space-x-6">
                    {navLinks.map((link) => (
                      <Link
                        key={link.to}
                        to={link.to}
                        className="inline-flex items-center px-1 pt-1 text-sm font-medium text-ink-muted hover:text-ink transition-colors"
                      >
                        {link.label}
                      </Link>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </nav>

          {/* Main Content */}
          <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/approvals" element={<ApprovalsPage />} />
              <Route path="/quizzes" element={<QuizPage />} />
              <Route path="/writing" element={<WritingPage />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>
    </QueryClientProvider>
  )
}

export default App
