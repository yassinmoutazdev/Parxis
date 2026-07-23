import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useThreads, useDeleteThread } from './api/chat'

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const navigate = useNavigate()

  const { data: threads = [], isLoading } = useThreads()
  const deleteThread = useDeleteThread()

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
    if (confirm('Delete this conversation?')) {
      await deleteThread.mutateAsync(threadId)
    }
  }

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
          className={`w-full flex items-center justify-center gap-2 px-4 py-2 bg-ink text-cream rounded-lg hover:bg-ink/90 transition-colors ${
            collapsed ? 'px-2' : ''
          }`}
        >
          <svg
            className="w-5 h-5"
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
          {!collapsed && <span>New Chat</span>}
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {/* Dashboard */}
        <Link
          to="/dashboard"
          className="flex items-center gap-3 px-4 py-2 text-ink-muted hover:bg-border hover:text-ink transition-colors"
        >
          <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          {!collapsed && <span>Dashboard</span>}
        </Link>

        {/* Reports */}
        <Link
          to="/reports"
          className="flex items-center gap-3 px-4 py-2 text-ink-muted hover:bg-border hover:text-ink transition-colors"
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
              className="w-full px-3 py-1.5 text-sm border border-border rounded-lg focus:outline-none focus:ring-2 focus:ring-ink/20"
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
            <div className="px-4 py-2 text-ink-muted text-sm">
              Loading...
            </div>
          ) : filteredThreads.length === 0 ? (
            <div className="px-4 py-2 text-ink-muted text-sm">
              {searchQuery ? 'No matches' : 'No conversations yet'}
            </div>
          ) : (
            filteredThreads.map((thread) => (
              <Link
                key={thread.id}
                to={`/chat/${thread.id}`}
                className="flex items-center gap-3 px-4 py-2 text-ink-muted hover:bg-border hover:text-ink transition-colors group"
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
                      className="opacity-0 group-hover:opacity-100 p-1 hover:text-red-500 transition-all"
                      title="Delete"
                    >
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </>
                )}
              </Link>
            ))
          )}
        </div>
      </nav>

      {/* Settings & Approvals */}
      <div className="border-t border-border py-2">
        {/* Settings */}
        <Link
          to="/settings"
          className="flex items-center gap-3 px-4 py-2 text-ink-muted hover:bg-border hover:text-ink transition-colors"
        >
          <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
          {!collapsed && <span>Settings</span>}
        </Link>

        {/* Approvals */}
        <Link
          to="/approvals"
          className="flex items-center gap-3 px-4 py-2 text-ink-muted hover:bg-border hover:text-ink transition-colors"
        >
          <svg className="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          {!collapsed && <span>Approvals</span>}
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
