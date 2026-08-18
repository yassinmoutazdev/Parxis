import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useThreads, useDeleteThread } from './api/chat'
import { LoadingSpinner } from '../../shared/components/LoadingSpinner'

const COLLAPSE_STORAGE_KEY = 'parxis:sidebar-collapsed'

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === 'true'
  })
  const [searchQuery, setSearchQuery] = useState('')
  // Thread pending a second click to confirm deletion (replaces the native
  // confirm() dialog with an inline, undo-less-but-branded two-step button).
  const [confirmingDeleteId, setConfirmingDeleteId] = useState<number | null>(null)
  const navigate = useNavigate()
  const location = useLocation()
  // Sidebar is rendered as a sibling of <Routes> in App.tsx (not nested
  // inside the matched <Route> element), so useParams() here always
  // returns {} - it only has access to route params within the matched
  // route's own subtree. That silently broke both the "highlight the
  // open thread in the list" styling and the "navigate home when you
  // delete the thread you're currently viewing" behavior below (the
  // activeThreadId === threadId check was always comparing against
  // null). useLocation() works anywhere under the Router regardless of
  // route nesting, so parse the thread id out of the pathname instead.
  const activeThreadIdMatch = location.pathname.match(/^\/chat\/(\d+)/)
  const activeThreadId = activeThreadIdMatch ? parseInt(activeThreadIdMatch[1], 10) : null

  const { data: threads = [], isLoading } = useThreads()
  const deleteThread = useDeleteThread()

  useEffect(() => {
    window.localStorage.setItem(COLLAPSE_STORAGE_KEY, String(collapsed))
  }, [collapsed])

  // Filter threads by search query
  const filteredThreads = threads.filter((thread) => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      thread.title?.toLowerCase().includes(query) ||
      thread.last_message_preview?.toLowerCase().includes(query)
    )
  })

  const handleNewChat = () => {
    navigate('/')
  }

  const handleDeleteThread = async (e: React.MouseEvent, threadId: number) => {
    e.preventDefault()
    e.stopPropagation()
    if (confirmingDeleteId === threadId) {
      setConfirmingDeleteId(null)
      await deleteThread.mutateAsync(threadId)
      // If the deleted thread is the one currently open, the chat window
      // otherwise keeps showing it as-is (only the sidebar list updates) --
      // navigate away so the deleted conversation actually disappears.
      if (activeThreadId === threadId) {
        navigate('/')
      }
    } else {
      setConfirmingDeleteId(threadId)
    }
  }

  const navLinkClasses = (isActive: boolean) =>
    `flex items-center gap-3 px-4 py-2 transition-colors ${
      isActive
        ? 'bg-accent-tint text-accent-text border-r-2 border-accent'
        : 'text-ink-muted hover:bg-border hover:text-ink'
    }`

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))

    if (days === 0) return 'Today'
    if (days === 1) return 'Yesterday'
    if (days < 7) return `${days} days ago`
    return date.toLocaleDateString()
  }

  return (
    <div
      className={`flex flex-col h-full bg-cream border-r border-border transition-all duration-200 ${
        collapsed ? 'w-16' : 'w-64'
      }`}
    >
      {/* New Chat Button */}
      <div className="p-2">
        <button
          onClick={handleNewChat}
          className={`w-full flex items-center gap-2 px-3 py-2 border border-border-strong text-ink rounded-lg hover:bg-cream-100 transition-colors ${
            collapsed ? 'justify-center px-2' : ''
          }`}
        >
          <svg
            className="w-5 h-5 flex-shrink-0"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 4v16m8-8H4"
            />
          </svg>
          {!collapsed && <span>New chat</span>}
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {/* Dashboard */}
        <Link
          to="/dashboard"
          aria-current={location.pathname === '/dashboard' ? 'page' : undefined}
          className={navLinkClasses(location.pathname === '/dashboard')}
        >
          <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          {!collapsed && <span>Dashboard</span>}
        </Link>

        {/* Reports */}
        <Link
          to="/reports"
          aria-current={location.pathname === '/reports' ? 'page' : undefined}
          className={navLinkClasses(location.pathname === '/reports')}
        >
          <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          {!collapsed && <span>Reports</span>}
        </Link>

        {/* Search */}
        <div className="px-4 py-2">
          {!collapsed && (
            <input
              type="text"
              placeholder="Search conversations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-1.5 text-sm bg-cream-100 text-ink placeholder:text-ink-faint border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-accent/40"
            />
          )}
        </div>

        {/* Chat History */}
        <div className="py-2">
          {!collapsed && (
            <div className="px-4 py-1 text-xs font-medium text-ink-muted uppercase tracking-wider">
              Chat History
            </div>
          )}

          {isLoading ? (
            !collapsed && (
              <div className="px-4 py-3">
                <LoadingSpinner size="sm" />
              </div>
            )
          ) : filteredThreads.length === 0 ? (
            !collapsed && (
              <div className="px-4 py-2 text-ink-muted text-sm">
                {searchQuery ? 'No matches' : 'No conversations yet'}
              </div>
            )
          ) : (
            filteredThreads.map((thread) => {
              const isActive = activeThreadId === thread.id
              const isConfirmingDelete = confirmingDeleteId === thread.id
              return (
                <Link
                  key={thread.id}
                  to={`/chat/${thread.id}`}
                  aria-current={isActive ? 'page' : undefined}
                  onMouseLeave={() => {
                    if (isConfirmingDelete) setConfirmingDeleteId(null)
                  }}
                  className={`${navLinkClasses(isActive)} group`}
                >
                  <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                  </svg>
                  {!collapsed && (
                    <>
                      <div className="flex-1 min-w-0">
                        <div className="truncate text-sm font-medium">
                          {thread.title || 'New conversation'}
                        </div>
                        <div className="truncate text-xs text-ink-muted">
                          {thread.last_message_preview || 'No messages'}
                        </div>
                        <div className="text-xs text-ink-muted mt-0.5">
                          {formatDate(thread.updated_at)}
                        </div>
                      </div>
                      <button
                        onClick={(e) => handleDeleteThread(e, thread.id)}
                        className={`p-1 rounded transition-all ${
                          isConfirmingDelete
                            ? 'opacity-100 bg-danger-tint text-danger-text px-2 text-xs font-medium'
                            : 'opacity-0 group-hover:opacity-100 hover:text-danger-text'
                        }`}
                        title={isConfirmingDelete ? 'Click again to confirm' : 'Delete'}
                      >
                        {isConfirmingDelete ? (
                          'Confirm?'
                        ) : (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        )}
                      </button>
                    </>
                  )}
                </Link>
              )
            })
          )}
        </div>
      </nav>

      {/* Settings */}
      <div className="border-t border-border py-2">
        {/* Settings */}
        <Link
          to="/settings"
          aria-current={location.pathname.startsWith('/settings') ? 'page' : undefined}
          className={navLinkClasses(location.pathname.startsWith('/settings'))}
        >
          <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          {!collapsed && <span>Settings</span>}
        </Link>

        {/* Collapse Toggle */}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center gap-3 px-4 py-2 text-ink-muted hover:bg-border hover:text-ink transition-colors w-full"
        >
          <svg
            className={`w-5 h-5 flex-shrink-0 transition-transform ${collapsed ? 'rotate-180' : ''}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </div>
  )
}
