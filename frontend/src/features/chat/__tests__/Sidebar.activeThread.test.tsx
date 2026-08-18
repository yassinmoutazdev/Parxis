import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import Sidebar from '../Sidebar'
import ChatPage from '../ChatPage'
import type { ChatThread, ChatThreadDetail } from '../../../api/types'

/**
 * Regression test for: Sidebar is rendered as a sibling of <Routes> in
 * App.tsx (not nested inside the matched <Route> element), so
 * useParams() inside Sidebar always returned {} regardless of the
 * current URL - it only has access to route params within the matched
 * route's own subtree.
 *
 * This silently broke two things that both depend on knowing which
 * thread is currently open:
 *   1. The "highlight the open thread in the sidebar list" styling.
 *   2. The "navigate home when you delete the thread you're currently
 *      viewing" behavior - `activeThreadId === threadId` was always
 *      `null === threadId`, i.e. always false, so the delete button
 *      never navigated away. The chat window only *appeared* to move
 *      on eventually because useThread(id)'s query for the now-deleted
 *      thread exhausted React Query's default 3 retries with
 *      exponential backoff (~7s) and fell back to the empty-state
 *      screen - which looked like a slow navigation but was actually a
 *      request timeout, still on the old (now-dead) URL.
 *
 * Fixed by switching Sidebar to useLocation() (path-based, works
 * anywhere under the Router) instead of useParams().
 */

function thread(id: number): ChatThread {
  return {
    id,
    title: `Thread ${id}`,
    last_message_preview: null,
    updated_at: '2026-01-01T00:00:00Z',
  }
}

function threadDetail(id: number): ChatThreadDetail {
  return { ...thread(id), created_at: '2026-01-01T00:00:00Z', messages: [] }
}

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response
}

function renderApp(initialPath: string, threadsAlive: number[]) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })

  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const u = typeof input === 'string' ? input : input.toString()
      const method = init?.method ?? 'GET'
      if (method === 'DELETE') {
        const match = u.match(/\/api\/chat\/threads\/(\d+)$/)
        if (match) {
          const id = parseInt(match[1], 10)
          threadsAlive = threadsAlive.filter((t) => t !== id)
          return { ok: true, status: 204, json: async () => ({}) } as Response
        }
      }
      if (u.match(/\/api\/chat\/threads\?/)) {
        return jsonResponse(threadsAlive.map(thread))
      }
      const detailMatch = u.match(/\/api\/chat\/threads\/(\d+)$/)
      if (detailMatch) {
        const id = parseInt(detailMatch[1], 10)
        if (threadsAlive.includes(id)) return jsonResponse(threadDetail(id))
        return jsonResponse({ detail: 'not found' }, false, 404)
      }
      return jsonResponse({})
    })
  )

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <div style={{ display: 'flex' }}>
          <Sidebar />
          <Routes>
            <Route path="/" element={<ChatPage />} />
            <Route path="/chat/:threadId" element={<ChatPage />} />
          </Routes>
        </div>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

Element.prototype.scrollIntoView = vi.fn()

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('Sidebar active-thread detection', () => {
  it('highlights the thread that matches the current /chat/:id route', async () => {
    renderApp('/chat/2', [1, 2])

    await waitFor(() => expect(screen.getByText('Thread 2')).toBeInTheDocument())

    const activeRow = screen.getByText('Thread 2').closest('a')
    const inactiveRow = screen.getByText('Thread 1').closest('a')

    expect(activeRow).toHaveAttribute('aria-current', 'page')
    expect(inactiveRow).not.toHaveAttribute('aria-current', 'page')
  })

  it('navigates to the empty chat screen promptly when the currently-open thread is deleted', async () => {
    renderApp('/chat/1', [1])

    await waitFor(() => expect(screen.getByTitle('Delete')).toBeInTheDocument())

    fireEvent.click(screen.getByTitle('Delete'))
    fireEvent.click(await screen.findByTitle('Click again to confirm'))

    // Should land on the empty-state screen quickly - not after burning
    // through several seconds of retrying a 404 for the deleted thread.
    await waitFor(() => expect(screen.getByText('Chat Coach')).toBeInTheDocument(), {
      timeout: 1000,
    })
  })

  it('does not navigate away when a different (non-open) thread is deleted', async () => {
    renderApp('/chat/1', [1, 2])

    await waitFor(() => expect(screen.getAllByTitle('Delete').length).toBe(2))

    const thread2Row = screen.getByText('Thread 2').closest('a') as HTMLElement
    const deleteBtn = thread2Row.querySelector('button[title="Delete"]') as HTMLElement
    fireEvent.click(deleteBtn)
    const confirmBtn = thread2Row.querySelector(
      'button[title="Click again to confirm"]'
    ) as HTMLElement
    fireEvent.click(confirmBtn)

    // Thread 1 is still the open thread - its detail view should remain.
    await waitFor(() => expect(screen.queryByText('Thread 2')).not.toBeInTheDocument())
    expect(screen.queryByText('Chat Coach')).not.toBeInTheDocument()
  })
})
