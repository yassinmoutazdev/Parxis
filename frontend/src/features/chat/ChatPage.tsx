import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import {
  useThread,
  useCreateThread,
  useSendMessage,
  useCompleteQuiz,
  useCompleteWriting,
  useStartQuizDirect,
  useStartWritingDirect,
} from './api/chat'
import type { ChatMessage } from '../../api/types'
import { QuizRunner } from '../quizzes/components/QuizRunner'
import { ChatWritingWidget } from './components/ChatWritingWidget'
import { ComposerPlusMenu } from './components/ComposerPlusMenu'
import { getWritingPrompt } from '../../api/client'
import type { QuizSession, QuizQuestion, WritingPrompt } from '../../api/types'

interface QuizWidgetData {
  sessionId: number
  questions: QuizQuestion[]
  session: QuizSession
}

interface WritingWidgetData {
  promptId: number
  prompt: WritingPrompt
}

export default function ChatPage() {
  const { threadId } = useParams<{ threadId?: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const numericThreadId = threadId ? parseInt(threadId, 10) : null

  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Queries and mutations
  const { data: threadDetail, isLoading: isLoadingThread } = useThread(numericThreadId ?? null)
  const createThread = useCreateThread()
  const sendMessage = useSendMessage()
  const completeQuiz = useCompleteQuiz()
  const completeWriting = useCompleteWriting()
  const startQuizDirect = useStartQuizDirect()
  const startWritingDirect = useStartWritingDirect()

  // Quiz widget state
  const [quizWidget, setQuizWidget] = useState<QuizWidgetData | null>(null)

  // Writing widget state
  const [writingWidget, setWritingWidget] = useState<WritingWidgetData | null>(null)

  // Optimistic user message shown immediately on send, before the server
  // round-trip resolves and the thread query refetches with the real data.
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [threadDetail?.messages])

  // Load quiz/writing widget if last message triggered one
  useEffect(() => {
    if (threadDetail?.messages) {
      const lastMessage = threadDetail.messages[threadDetail.messages.length - 1]
      if (lastMessage?.action_type === 'QUIZ' && lastMessage.action_ref_id && !quizWidget) {
        loadQuizWidget(lastMessage.action_ref_id)
      }
      if (lastMessage?.action_type === 'WRITING' && lastMessage.action_ref_id && !writingWidget) {
        loadWritingWidget(lastMessage.action_ref_id)
      }
    }
  }, [threadDetail])

  const loadQuizWidget = async (sessionId: number) => {
    try {
      const res = await fetch(`/api/quizzes/${sessionId}`)
      if (res.ok) {
        const data = await res.json()
        setQuizWidget({
          sessionId,
          questions: data.questions,
          session: {
            id: data.id,
            quiz_scope: data.quiz_scope,
            quiz_mode: data.quiz_mode,
            started_at: data.started_at,
            completed_at: data.completed_at,
            week_id: data.week_id,
          },
        })
      }
    } catch (err) {
      console.error('Failed to load quiz:', err)
    }
  }

  const loadWritingWidget = async (promptId: number) => {
    try {
      const prompt = await getWritingPrompt(promptId)
      setWritingWidget({ promptId, prompt })
    } catch (err) {
      console.error('Failed to load writing prompt:', err)
    }
  }

  const ensureThread = async (): Promise<number> => {
    if (numericThreadId) return numericThreadId
    const newThread = await createThread.mutateAsync()
    navigate(`/chat/${newThread.id}`, { replace: true })
    return newThread.id
  }

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const content = input.trim()
    setError(null)
    setIsLoading(true)

    // Optimistic UI: clear the composer and show the bubble immediately,
    // instead of waiting for the full round-trip (user_message +
    // assistant_message) to come back.
    setInput('')
    setPendingMessage(content)

    try {
      const thread = await ensureThread()

      // Send message and get reply
      const result = await sendMessage.mutateAsync({
        threadId: thread,
        content,
      })

      // Make sure the real messages have landed in the cache before we drop
      // the optimistic bubble, so there's no gap where nothing is shown.
      await queryClient.refetchQueries({ queryKey: ['chat', 'thread', thread] })

      // Check if assistant triggered a quiz or writing session
      if (result.assistant_message.action_type === 'QUIZ' && result.assistant_message.action_ref_id) {
        await loadQuizWidget(result.assistant_message.action_ref_id)
      }
      if (result.assistant_message.action_type === 'WRITING' && result.assistant_message.action_ref_id) {
        await loadWritingWidget(result.assistant_message.action_ref_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message')
      // Restore the message to the composer so the user can retry.
      setInput(content)
    } finally {
      setIsLoading(false)
      setPendingMessage(null)
    }
  }

  // Manual "+" triggers (Work Item D): bypass the LLM entirely, calling the
  // direct-trigger endpoints, then following the same rendering path as the
  // LLM-triggered case (thread refetch -> widget appears from
  // action_type/action_ref_id).
  const handleStartQuizDirect = async (size: number) => {
    setError(null)
    try {
      const thread = await ensureThread()
      const message = await startQuizDirect.mutateAsync({ threadId: thread, size })
      await queryClient.refetchQueries({ queryKey: ['chat', 'thread', thread] })
      if (message.action_type === 'QUIZ' && message.action_ref_id) {
        await loadQuizWidget(message.action_ref_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start quiz')
    }
  }

  const handleStartWritingDirect = async (writingMode: 'mini' | 'weekly') => {
    setError(null)
    try {
      const thread = await ensureThread()
      const message = await startWritingDirect.mutateAsync({ threadId: thread, writingMode })
      await queryClient.refetchQueries({ queryKey: ['chat', 'thread', thread] })
      if (message.action_type === 'WRITING' && message.action_ref_id) {
        await loadWritingWidget(message.action_ref_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start writing session')
    }
  }

  const handleQuizComplete = async (answers: Record<number, string>) => {
    if (!numericThreadId || !quizWidget) return

    try {
      // Submit answers
      const res = await fetch(`/api/quizzes/${quizWidget.sessionId}/answers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ answers }),
      })

      if (res.ok) {
        // Notify chat that quiz is complete
        await completeQuiz.mutateAsync({
          threadId: numericThreadId,
          sessionId: quizWidget.sessionId,
        })

        // Clear widget
        setQuizWidget(null)
      }
    } catch (err) {
      console.error('Failed to complete quiz:', err)
    }
  }

  const handleWritingComplete = async (promptId: number) => {
    if (!numericThreadId) return

    try {
      // Notify chat that writing is complete (submission itself already
      // happened inside ChatWritingWidget via POST /writing/submissions).
      // Unlike the quiz widget, the writing widget stays mounted so the
      // learner can keep referring back to their submission + evaluation
      // feedback while the coach's follow-up message streams in below it.
      await completeWriting.mutateAsync({
        threadId: numericThreadId,
        promptId,
      })
    } catch (err) {
      console.error('Failed to complete writing:', err)
    }
  }

  const renderMessage = (msg: ChatMessage) => {
    const isUser = msg.role === 'USER'
    return (
      <div
        key={msg.id}
        className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}
      >
        <div
          className={`max-w-[70%] rounded-card px-4 py-2 ${
            isUser
              ? 'bg-accent text-white'
              : 'bg-surface text-ink'
          }`}
        >
          <p className="whitespace-pre-wrap">{msg.content}</p>
        </div>
      </div>
    )
  }

  // Loading state
  if (isLoadingThread) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-ink-muted">Loading...</div>
      </div>
    )
  }

  // Empty / new chat state
  if (!numericThreadId || !threadDetail) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center w-full max-w-2xl px-4">
            <h2 className="text-2xl font-serif text-ink mb-2">Chat Coach</h2>
            <p className="text-ink-muted mb-6">
              Ask anything, or try a quiz
            </p>
            <Composer
              value={input}
              onChange={setInput}
              onSubmit={handleSend}
              disabled={isLoading}
              placeholder="Type your message..."
              onStartQuiz={handleStartQuizDirect}
              onStartWriting={handleStartWritingDirect}
            />
            {error && <p className="text-red-500 mt-2">{error}</p>}
          </div>
        </div>
      </div>
    )
  }

  // Existing thread state
  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-4">
        {threadDetail.messages.map(renderMessage)}

        {/* Optimistic user bubble, shown immediately on send */}
        {pendingMessage && (
          <div className="flex justify-end mb-4">
            <div className="max-w-[70%] rounded-card px-4 py-2 bg-accent text-white">
              <p className="whitespace-pre-wrap">{pendingMessage}</p>
            </div>
          </div>
        )}

        {/* Quiz Widget */}
        {quizWidget && (
          <div className="my-4">
            <QuizRunner
              questions={quizWidget.questions}
              onSubmitAll={handleQuizComplete}
              submitting={completeQuiz.isPending}
            />
          </div>
        )}

        {/* Writing Widget */}
        {writingWidget && (
          <div className="my-4">
            <ChatWritingWidget
              prompt={writingWidget.prompt}
              onComplete={handleWritingComplete}
            />
          </div>
        )}

        {isLoading && (
          <div className="flex justify-start mb-4">
            <div className="bg-border text-ink rounded-lg px-4 py-2">
              <span className="inline-flex space-x-1">
                <span className="w-2 h-2 bg-ink-muted rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-2 h-2 bg-ink-muted rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-2 h-2 bg-ink-muted rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <div className="border-t border-border p-4">
        <Composer
          value={input}
          onChange={setInput}
          onSubmit={handleSend}
          disabled={isLoading}
          placeholder="Type your message..."
          onStartQuiz={handleStartQuizDirect}
          onStartWriting={handleStartWritingDirect}
        />
        {error && <p className="text-red-500 mt-2">{error}</p>}
      </div>
    </div>
  )
}

// Composer component
function Composer({
  value,
  onChange,
  onSubmit,
  disabled,
  placeholder,
  onStartQuiz,
  onStartWriting,
}: {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  disabled?: boolean
  placeholder?: string
  onStartQuiz?: (size: number) => void
  onStartWriting?: (mode: 'mini' | 'weekly') => void
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [plusMenuOpen, setPlusMenuOpen] = useState(false)

  // Auto-resize: start at one line, grow with content up to a max height,
  // then let the textarea's own scroll take over.
  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = 'auto'
    const maxHeight = 200 // px, roughly ~8 lines
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`
  }, [value])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSubmit()
    }
  }

  const showPlusMenu = onStartQuiz && onStartWriting

  return (
    <div className="relative flex items-end gap-2 rounded-card border border-border bg-surface px-3 py-2 focus-within:ring-2 focus-within:ring-accent/40">
      {showPlusMenu && (
        <>
          <button
            type="button"
            onClick={() => setPlusMenuOpen(prev => !prev)}
            disabled={disabled}
            aria-label="Start a quiz or writing session"
            aria-expanded={plusMenuOpen}
            className="flex items-center justify-center w-9 h-9 rounded-full text-ink-muted hover:bg-border hover:text-ink disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          </button>

          {plusMenuOpen && (
            <ComposerPlusMenu
              disabled={disabled}
              onClose={() => setPlusMenuOpen(false)}
              onStartQuiz={onStartQuiz!}
              onStartWriting={onStartWriting!}
            />
          )}
        </>
      )}

      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        className="flex-1 resize-none bg-transparent text-ink placeholder:text-ink-faint px-1 py-1.5 focus:outline-none disabled:opacity-50 max-h-[200px] overflow-y-auto"
        rows={1}
      />
      <button
        onClick={onSubmit}
        disabled={disabled || !value.trim()}
        aria-label="Send message"
        className="flex items-center justify-center w-9 h-9 rounded-full bg-accent text-white hover:bg-accent-hover disabled:bg-border disabled:text-ink-faint disabled:cursor-not-allowed transition-colors"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 15l7-7 7 7" />
        </svg>
      </button>
    </div>
  )
}

