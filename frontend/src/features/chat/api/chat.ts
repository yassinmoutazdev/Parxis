import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import type { ChatThread, ChatThreadDetail, ChatMessage } from '../../../api/types'

const API_BASE = '/api/chat'

// Fetch all threads
export function useThreads(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ['chat', 'threads', limit, offset],
    queryFn: async (): Promise<ChatThread[]> => {
      const params = new URLSearchParams({
        limit: String(limit),
        offset: String(offset),
      })
      const res = await fetch(`${API_BASE}/threads?${params}`)
      if (!res.ok) throw new Error('Failed to fetch threads')
      return res.json()
    },
  })
}

// Fetch single thread with messages
export function useThread(threadId: number | null) {
  return useQuery({
    queryKey: ['chat', 'thread', threadId],
    queryFn: async (): Promise<ChatThreadDetail> => {
      if (!threadId) throw new Error('No thread ID')
      const res = await fetch(`${API_BASE}/threads/${threadId}`)
      if (!res.ok) throw new Error('Failed to fetch thread')
      return res.json()
    },
    enabled: !!threadId,
  })
}

// Create a new thread
export function useCreateThread() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (): Promise<ChatThread> => {
      const res = await fetch(`${API_BASE}/threads`, {
        method: 'POST',
      })
      if (!res.ok) throw new Error('Failed to create thread')
      return res.json()
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'threads'] })
    },
  })
}

// Send a message and get reply
export function useSendMessage() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      threadId,
      content,
    }: {
      threadId: number
      content: string
    }): Promise<{ user_message: ChatMessage; assistant_message: ChatMessage }> => {
      const res = await fetch(`${API_BASE}/threads/${threadId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      })
      if (!res.ok) throw new Error('Failed to send message')
      return res.json()
    },
    onSuccess: (_, { threadId }) => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'thread', threadId] })
      queryClient.invalidateQueries({ queryKey: ['chat', 'threads'] })
    },
  })
}

// Delete a thread
export function useDeleteThread() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (threadId: number): Promise<void> => {
      const res = await fetch(`${API_BASE}/threads/${threadId}`, {
        method: 'DELETE',
      })
      if (!res.ok) throw new Error('Failed to delete thread')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'threads'] })
    },
  })
}

// Start a quiz directly from the composer's "+" menu (bypasses the LLM)
export function useStartQuizDirect() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      threadId,
      mode,
      size,
    }: {
      threadId: number
      mode: string
      size: number
    }): Promise<ChatMessage> => {
      const res = await fetch(`${API_BASE}/threads/${threadId}/quiz`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, size }),
      })
      if (!res.ok) throw new Error('Failed to start quiz')
      return res.json()
    },
    onSuccess: (_, { threadId }) => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'thread', threadId] })
      queryClient.invalidateQueries({ queryKey: ['chat', 'threads'] })
    },
  })
}

// Start a writing session directly from the composer's "+" menu (bypasses the LLM)
export function useStartWritingDirect() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      threadId,
      writingMode,
    }: {
      threadId: number
      writingMode: 'mini' | 'weekly'
    }): Promise<ChatMessage> => {
      const res = await fetch(`${API_BASE}/threads/${threadId}/writing`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ writing_mode: writingMode }),
      })
      if (!res.ok) throw new Error('Failed to start writing session')
      return res.json()
    },
    onSuccess: (_, { threadId }) => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'thread', threadId] })
      queryClient.invalidateQueries({ queryKey: ['chat', 'threads'] })
    },
  })
}

// Complete quiz and get follow-up
export function useCompleteQuiz() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      threadId,
      sessionId,
    }: {
      threadId: number
      sessionId: number
    }): Promise<ChatMessage> => {
      const res = await fetch(
        `${API_BASE}/threads/${threadId}/quiz/${sessionId}/complete`,
        { method: 'POST' }
      )
      if (!res.ok) throw new Error('Failed to complete quiz')
      return res.json()
    },
    onSuccess: (_, { threadId }) => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'thread', threadId] })
    },
  })
}

// Complete writing and get follow-up
export function useCompleteWriting() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async ({
      threadId,
      promptId,
    }: {
      threadId: number
      promptId: number
    }): Promise<ChatMessage> => {
      const res = await fetch(
        `${API_BASE}/threads/${threadId}/writing/${promptId}/complete`,
        { method: 'POST' }
      )
      if (!res.ok) throw new Error('Failed to complete writing')
      return res.json()
    },
    onSuccess: (_, { threadId }) => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'thread', threadId] })
    },
  })
}
