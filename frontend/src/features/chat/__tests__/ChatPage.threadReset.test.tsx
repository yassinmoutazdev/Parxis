import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route, Link } from 'react-router-dom'
import ChatPage from '../ChatPage'
import type { ChatThreadDetail } from '../../../api/types'

/**
 * Regression test for: deleting/leaving a chat thread left stale UI (error
 * banner, in this case) frozen on screen after navigating to a different
 * thread route, because App.tsx routes both `/` and `/chat/:threadId` to
 * the same <ChatPage /> element and React Router never remounts it.
 *
 * This renders the same route shape as App.tsx (two <Route>s pointing at
 * one <ChatPage /> element) and navigates between them via a real <Link>,
 * so React Router treats it exactly like the production case - no remount.
 */

function threadDetail(id: number): ChatThreadDetail {
  return {
    id,
    title: null,
    last_message_preview: null,
    updated_at: '2026-01-01T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    messages: [],
  }
}

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return {
    ok,
    status,
    json: async () => body,
  } as Response
}

function renderChatRoutes(initialPath: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        {/* Stands in for the Sidebar link the user actually clicks in
            App.tsx - what matters is that it's a real router navigation,
            not a remount trigger. */}
        <Link to="/chat/2">go to thread 2</Link>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/chat/:threadId" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ChatPage - state reset on thread change', () => {
  beforeEach(() => {
    // jsdom doesn't implement scrollIntoView; ChatPage calls it on every
    // messages-list update to auto-scroll.
    Element.prototype.scrollIntoView = vi.fn()

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString()
        const method = init?.method ?? 'GET'

        if (method === 'GET' && /\/api\/chat\/threads\/1$/.test(url)) {
          return jsonResponse(threadDetail(1))
        }
        if (method === 'GET' && /\/api\/chat\/threads\/2$/.test(url)) {
          return jsonResponse(threadDetail(2))
        }
        if (method === 'POST' && /\/api\/chat\/threads\/1\/messages$/.test(url)) {
          // Simulate a failed send on thread 1 - this is what sets the
          // `error` state we're using as our canary for stale UI.
          return jsonResponse({ detail: 'boom' }, false, 500)
        }

        throw new Error(`Unhandled fetch in test: ${method} ${url}`)
      })
    )
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('clears a failed-send error banner after navigating to a different thread', async () => {
    renderChatRoutes('/chat/1')

    const textarea = await screen.findByPlaceholderText('Type your message...')
    fireEvent.change(textarea, { target: { value: 'hello' } })
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' })

    // The failed send should surface an error banner on thread 1.
    await screen.findByText('Failed to send message')

    // Navigate to a different thread - same <ChatPage /> element/instance
    // stays mounted, exactly like the production bug scenario.
    fireEvent.click(screen.getByText('go to thread 2'))

    // Thread 2 briefly shows ChatPage's own loading-spinner branch (which
    // has no error banner regardless of state), so wait for that to clear
    // and the composer to come back before checking - otherwise this
    // assertion would pass trivially during the loading flash even
    // without the fix.
    await screen.findByPlaceholderText('Type your message...')

    // Previously: the error banner from thread 1 stayed frozen on screen
    // because nothing reset local state on the threadId change.
    await waitFor(() => {
      expect(screen.queryByText('Failed to send message')).not.toBeInTheDocument()
    })
  })
})
