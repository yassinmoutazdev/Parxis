import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import { useThread, useCreateThread, useSendMessage, useCompleteQuiz } from './api/chat'
import type { ChatMessage } from '../../api/types'
import { QuestionCard } from '../quizzes/components/QuestionCard'
import type { QuizSession, QuizQuestion } from '../../api/types'

interface QuizWidgetData {
  sessionId: number
  questions: QuizQuestion[]
  session: QuizSession
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

  // Quiz widget state
  const [quizWidget, setQuizWidget] = useState<QuizWidgetData | null>(null)

  // Optimistic user message shown immediately on send, before the server
  // round-trip resolves and the thread query refetches with the real data.
  const [pendingMessage, setPendingMessage] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [threadDetail?.messages])

  // Load quiz widget if last message is a quiz action
  useEffect(() => {
    if (threadDetail?.messages) {
      const lastMessage = threadDetail.messages[threadDetail.messages.length - 1]
      if (lastMessage?.action_type === 'QUIZ' && lastMessage.action_ref_id && !quizWidget) {
        loadQuizWidget(lastMessage.action_ref_id)
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
      let thread = numericThreadId

      // Create thread if doesn't exist
      if (!thread) {
        const newThread = await createThread.mutateAsync()
        thread = newThread.id
        navigate(`/chat/${thread}`, { replace: true })
      }

      // Send message and get reply
      const result = await sendMessage.mutateAsync({
        threadId: thread,
        content,
      })

      // Make sure the real messages have landed in the cache before we drop
      // the optimistic bubble, so there's no gap where nothing is shown.
      await queryClient.refetchQueries({ queryKey: ['chat', 'thread', thread] })

      // Check if assistant triggered a quiz
      if (result.assistant_message.action_type === 'QUIZ' && result.assistant_message.action_ref_id) {
        await loadQuizWidget(result.assistant_message.action_ref_id)
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
            <QuizWidgetWrapper
              questions={quizWidget.questions}
              onComplete={handleQuizComplete}
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
}: {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  disabled?: boolean
  placeholder?: string
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

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

  return (
    <div className="flex items-end gap-2 rounded-card border border-border bg-surface px-3 py-2 focus-within:ring-2 focus-within:ring-accent/40">
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

// Quiz widget wrapper
function QuizWidgetWrapper({
  questions,
  onComplete,
}: {
  questions: QuizQuestion[]
  onComplete: (answers: Record<number, string>) => void
}) {
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [isComplete, setIsComplete] = useState(false)

  const handleAnswer = (questionId: number, answer: string) => {
    setAnswers(prev => ({ ...prev, [questionId]: answer }))
  }

  const handleNext = () => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(currentIndex + 1)
    }
  }

  const handlePrev = () => {
    if (currentIndex > 0) {
      setCurrentIndex(currentIndex - 1)
    }
  }

  const handleSubmit = () => {
    setIsComplete(true)
    onComplete(answers)
  }

  const currentQuestion = questions[currentIndex]
  const hasAnswer = currentQuestion ? !!answers[currentQuestion.id] : false
  const allAnswered = questions.every(q => !!answers[q.id])

  if (isComplete) {
    return (
      <div className="p-4 bg-border rounded-lg">
        <p className="text-ink-muted">Quiz submitted! Processing results...</p>
      </div>
    )
  }

  return (
    <div className="p-4 bg-border rounded-lg">
      {currentQuestion && (
        <div className="mb-4">
          <QuestionCard
            id={currentQuestion.id}
            questionType={currentQuestion.question_type}
            prompt={currentQuestion.prompt}
            options={currentQuestion.options}
            userAnswer={answers[currentQuestion.id]}
            onAnswer={handleAnswer}
          />
        </div>
      )}

      {/* Navigation */}
      <div className="flex justify-between items-center">
        <button
          onClick={handlePrev}
          disabled={currentIndex === 0}
          className="px-3 py-1 text-sm text-ink-muted hover:text-ink disabled:opacity-50"
        >
          Previous
        </button>

        <div className="flex gap-1">
          {questions.map((_, idx) => (
            <button
              key={idx}
              onClick={() => setCurrentIndex(idx)}
              className={`w-2 h-2 rounded-full ${
                idx === currentIndex
                  ? 'bg-accent'
                  : answers[questions[idx].id]
                    ? 'bg-accent/50'
                    : 'bg-border'
              }`}
            />
          ))}
        </div>

        {currentIndex < questions.length - 1 ? (
          <button
            onClick={handleNext}
            disabled={!hasAnswer}
            className="px-3 py-1 text-sm text-ink hover:text-ink/80 disabled:opacity-50"
          >
            Next
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!allAnswered}
            className="px-4 py-1 bg-accent text-white rounded-lg text-sm hover:bg-accent-hover disabled:opacity-50"
          >
            Submit All
          </button>
        )}
      </div>
    </div>
  )
}
