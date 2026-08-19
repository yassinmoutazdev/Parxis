import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import ChatPage from '../ChatPage'
import type { ChatMessage, ChatThreadDetail } from '../../../api/types'

/**
 * Regression test for the first message of a brand-new thread either not
 * appearing right away, or appearing twice.
 *
 * Both came from the same root cause: creating the thread and navigating to
 * it enables useThread(threadId) for the first time, firing a GET that can
 * resolve *while* the POST to /messages is still waiting on the LLM - the
 * backend commits the user message to the DB immediately, well before
 * generating the reply. If that GET lands before the POST does,
 * threadDetail.messages already contains the real user message while the
 * optimistic pendingMessage bubble (only cleared once the POST resolves) is
 * still showing its own copy of the same text.
 *
 * This test controls the timing of all three requests explicitly (create
 * thread, GET the new thread, POST the message) so it can assert the exact
 * mid-flight state the production race hits, not just the eventual outcome.
 */

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function jsonResponse(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as Response
}

function userMessage(content: string): ChatMessage {
  return {
    id: 101,
    thread_id: 5,
    role: 'USER',
    content,
    action_type: 'NONE',
    action_ref_id: null,
    created_at: '2026-01-01T00:00:00Z',
  }
}

function assistantMessage(content: string): ChatMessage {
  return {
    id: 102,
    thread_id: 5,
    role: 'ASSISTANT',
    content,
    action_type: 'NONE',
    action_ref_id: null,
    created_at: '2026-01-01T00:00:01Z',
  }
}

function threadDetail(messages: ChatMessage[]): ChatThreadDetail {
  return {
    id: 5,
    title: null,
    last_message_preview: null,
    updated_at: '2026-01-01T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    messages,
  }
}

function renderChatRoutes() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<ChatPage />} />
          <Route path="/chat/:threadId" element={<ChatPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('ChatPage - first message of a new thread', () => {
  const createThreadDeferred = deferred<Response>()
  const getThreadDeferred = deferred<Response>()
  const sendMessageDeferred = deferred<Response>()

  beforeEach(() => {
    Element.prototype.scrollIntoView = vi.fn()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('shows the bubble immediately and never duplicates it while the reply is pending', async () => {
    let getThreadCallCount = 0

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input.toString()
        const method = init?.method ?? 'GET'

        if (method === 'POST' && /\/api\/chat\/threads$/.test(url)) {
          return createThreadDeferred.promise
        }
        if (method === 'GET' && /\/api\/chat\/threads\/5$/.test(url)) {
          getThreadCallCount++
          // First call: the controlled mid-race response used below. Any
          // call after that (react-query's own invalidate-triggered
          // refetch, plus the explicit refetchQueries in handleSend) is a
          // real refetch happening after the send already completed, so it
          // should reflect the final state - both messages - same as the
          // real backend would return by then.
          if (getThreadCallCount === 1) {
            return getThreadDeferred.promise
          }
          return jsonResponse(threadDetail([userMessage('hello world'), assistantMessage('hi there')]))
        }
        if (method === 'POST' && /\/api\/chat\/threads\/5\/messages$/.test(url)) {
          return sendMessageDeferred.promise
        }

        throw new Error(`Unhandled fetch in test: ${method} ${url}`)
      })
    )

    renderChatRoutes()

    const textarea = await screen.findByPlaceholderText('Type your message...')
    fireEvent.change(textarea, { target: { value: 'hello world' } })
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' })

    // 1. "Doesn't show immediately": the bubble must appear before either
    // the create-thread or get-thread requests have resolved at all -
    // neither the spinner branch nor the welcome-screen branch should be
    // hiding it during that window.
    await screen.findByText('hello world')

    // 2. Create-thread resolves -> navigates to /chat/5 -> the first GET
    // for thread 5 fires. Resolve it as the backend would really return it
    // mid-race: the user message already committed, assistant not yet
    // replied. The POST /messages call is still pending at this point.
    createThreadDeferred.resolve(jsonResponse({ id: 5, title: null, last_message_preview: null, updated_at: '2026-01-01T00:00:00Z' }))
    getThreadDeferred.resolve(jsonResponse(threadDetail([userMessage('hello world')])))

    // Give react-query a tick to apply the resolved GET into the cache and
    // re-render - this is exactly the moment the old code showed two
    // copies of "hello world" (one from threadDetail.messages, one from
    // the still-active pendingMessage bubble).
    await waitFor(() => {
      expect(screen.getAllByText('hello world')).toHaveLength(1)
    })

    // 3. Now let the send itself finish (assistant replies).
    sendMessageDeferred.resolve(
      jsonResponse({
        user_message: userMessage('hello world'),
        assistant_message: assistantMessage('hi there'),
      })
    )

    // Final state: exactly one of each bubble, nothing duplicated or lost.
    await screen.findByText('hi there')
    expect(screen.getAllByText('hello world')).toHaveLength(1)
  })
})
