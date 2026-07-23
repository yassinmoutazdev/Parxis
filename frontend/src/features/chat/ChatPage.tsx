import { useState, useRef, useEffect } from 'react'
import { useParams } from 'react-router-dom'
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

    setError(null)
    setIsLoading(true)

    try {
      let thread = numericThreadId

      // Create thread if doesn't exist
      if (!thread) {
        const newThread = await createThread.mutateAsync()
        thread = newThread.id
        window.history.pushState({}, '', `/chat/${thread}`)
      }

      // Send message and get reply
      const result = await sendMessage.mutateAsync({
        threadId: thread,
        content: input.trim(),
      })

      setInput('')

      // Check if assistant triggered a quiz
      if (result.assistant_message.action_type === 'QUIZ' && result.assistant_message.action_ref_id) {
        await loadQuizWidget(result.assistant_message.action_ref_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send message')
    } finally {
      setIsLoading(false)
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
          className={`max-w-[70%] rounded-lg px-4 py-2 ${
            isUser
              ? 'bg-ink text-cream'
              : 'bg-border text-ink'
          }`}
        >
          <p className="whitespace-pre-wrap">{msg.content}</p>
          {msg.action_type !== 'NONE' && (
            <div className="mt-2 text-xs text-ink-muted">
              Action: {msg.action_type} (ID: {msg.action_ref_id})
            </div>
          )}
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
          <div className="text-center max-w-md">
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
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSubmit()
    }
  }

  return (
    <div className="flex gap-2">
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        placeholder={placeholder}
        className="flex-1 resize-none rounded-lg border border-border px-4 py-2 focus:outline-none focus:ring-2 focus:ring-ink/20 disabled:opacity-50"
        rows={2}
      />
      <button
        onClick={onSubmit}
        disabled={disabled || !value.trim()}
        className="px-4 py-2 bg-ink text-cream rounded-lg hover:bg-ink/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        Send
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
                  ? 'bg-ink'
                  : answers[questions[idx].id]
                    ? 'bg-ink/50'
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
            className="px-4 py-1 bg-ink text-cream rounded-lg text-sm hover:bg-ink/90 disabled:opacity-50"
          >
            Submit All
          </button>
        )}
      </div>
    </div>
  )
}
