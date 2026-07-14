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

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="min-h-screen bg-gray-50">
          {/* Navigation */}
          <nav className="bg-white shadow-sm border-b border-gray-200">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="flex justify-between h-16">
                <div className="flex">
                  <div className="flex-shrink-0 flex items-center">
                    <span className="text-xl font-semibold text-gray-900">Praxis</span>
                  </div>
                  <div className="ml-6 flex space-x-8">
                    <Link to="/" className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-900">
                      Dashboard
                    </Link>
                    <Link to="/approvals" className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900">
                      Approvals
                    </Link>
                    <Link to="/quizzes" className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900">
                      Quizzes
                    </Link>
                    <Link to="/writing" className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900">
                      Writing
                    </Link>
                    <Link to="/reports" className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900">
                      Reports
                    </Link>
                    <Link to="/settings" className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-500 hover:text-gray-900">
                      Settings
                    </Link>
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