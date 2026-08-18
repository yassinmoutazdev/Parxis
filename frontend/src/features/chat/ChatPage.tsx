import { useState, useRef, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import {
  useThread,
  useCreateThread,
  useSendMessage,
  useEditMessage,
  useCompleteQuiz,
  useCompleteWriting,
  useStartQuizDirect,
  useStartWritingDirect,
} from './api/chat'
import type { ChatMessage } from '../../api/types'
import { QuizRunner } from '../quizzes/components/QuizRunner'
import { ChatWritingWidget } from './components/ChatWritingWidget'
import { ComposerPlusMenu } from './components/ComposerPlusMenu'
import { getWritingPrompt, saveNote } from '../../api/client'
import { getErrorMessage } from '../../api/errors'
import type { QuizSession, QuizQuestion, WritingPrompt } from '../../api/types'
import { LoadingSpinner } from '../../shared/components/LoadingSpinner'

// Attachment constraints shown in the composer (must match backend validation
// in app/chat/attachments.py).
const ACCEPTED_ATTACHMENT_TYPES = '.txt,.md,.pdf,.docx,image/*'
const ACCEPTED_ATTACHMENT_LABEL = '.txt, .md, .pdf, .docx, or images'
const MAX_ATTACHMENT_SIZE_MB = 10

// How close to the bottom (in px) counts as "already at the bottom" for
// auto-scroll purposes.
const AUTO_SCROLL_THRESHOLD_PX = 120

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

  // Proactive offline indicator: flips as soon as the browser notices the
  // connection drop, instead of the person only finding out after a send
  // silently fails.
  const [isOffline, setIsOffline] = useState(
    typeof navigator !== 'undefined' && navigator.onLine === false
  )
  useEffect(() => {
    const handleOnline = () => setIsOffline(false)
    const handleOffline = () => setIsOffline(true)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  // Queries and mutations
  const { data: threadDetail, isLoading: isLoadingThread } = useThread(numericThreadId ?? null)
  const createThread = useCreateThread()
  const sendMessage = useSendMessage()
  const editMessage = useEditMessage()
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

  // A send that failed: kept visible as its own bubble with an inline
  // retry, instead of vanishing and leaving only a generic caption under
  // the composer disconnected from where the message was.
  const [failedMessage, setFailedMessage] = useState<{ content: string; files: File[] } | null>(null)

  // Copy-to-clipboard feedback: briefly shows a checkmark on the message
  // that was just copied.
  const [copiedMessageId, setCopiedMessageId] = useState<number | null>(null)

  // Inline edit state for the message currently being edited (user
  // messages only).
  const [editingMessageId, setEditingMessageId] = useState<number | null>(null)
  const [editingContent, setEditingContent] = useState('')

  // Files staged in the composer, attached to the next outgoing message
  // (Epic B: ephemeral chat attachments).
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)

  // App.tsx routes both `/` and `/chat/:threadId` to this same <ChatPage />
  // element, so React Router never remounts it when threadId changes (e.g.
  // after a delete-and-navigate-to-/). Without this, any quiz/writing
  // widget, in-progress edit, or error/failed-message banner from the
  // previous thread stays frozen on screen even though the URL and message
  // list have already moved on.
  //
  // ensureThread() also changes numericThreadId itself - via
  // navigate(`/chat/${newThread.id}`, { replace: true }) right after
  // creating a brand-new thread for the first message of a conversation.
  // That's a legitimate in-flight send (isLoading/pendingMessage are
  // supposed to still be set at that point), not a "switched to a
  // different thread" navigation, so it must NOT trigger this reset. The
  // ref below lets ensureThread mark that one transition to be skipped.
  const skipNextResetRef = useRef(false)

  useEffect(() => {
    if (skipNextResetRef.current) {
      skipNextResetRef.current = false
      return
    }
    setQuizWidget(null)
    setWritingWidget(null)
    setEditingMessageId(null)
    setEditingContent('')
    setError(null)
    setFailedMessage(null)
    setPendingMessage(null)
    setSelectedFiles([])
    setCopiedMessageId(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [numericThreadId])

  // Whether there are new messages the user hasn't scrolled down to see yet.
  const [hasNewMessages, setHasNewMessages] = useState(false)

  const isNearBottom = () => {
    const el = messagesContainerRef.current
    if (!el) return true
    return el.scrollHeight - el.scrollTop - el.clientHeight < AUTO_SCROLL_THRESHOLD_PX
  }

  const scrollToBottom = (behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior })
    setHasNewMessages(false)
  }

  // Only auto-scroll to the newest message if the user was already near the
  // bottom -- otherwise leave their scroll position alone and surface a
  // "jump to latest" pill instead, so reading back through history doesn't
  // keep getting yanked down.
  useEffect(() => {
    if (isNearBottom()) {
      scrollToBottom()
    } else {
      setHasNewMessages(true)
    }
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
    // This navigation changes numericThreadId (null -> newThread.id) as a
    // side effect of the send that's already in flight - skip the next
    // thread-change reset so it doesn't clobber isLoading/pendingMessage
    // for that same send.
    skipNextResetRef.current = true
    navigate(`/chat/${newThread.id}`, { replace: true })
    return newThread.id
  }

  const handleSend = async (retry?: { content: string; files: File[] }) => {
    const content = retry ? retry.content : input.trim()
    const files = retry ? retry.files : selectedFiles
    if ((!content && files.length === 0) || isLoading) return

    setError(null)
    setFailedMessage(null)
    setIsLoading(true)

    // Optimistic UI: clear the composer and show the bubble immediately,
    // instead of waiting for the full round-trip (user_message +
    // assistant_message) to come back.
    if (!retry) {
      setInput('')
      setSelectedFiles([])
    }
    setPendingMessage(content || (files.length ? `${files.length} file(s) attached` : content))

    try {
      const thread = await ensureThread()

      // Send message and get reply
      const result = await sendMessage.mutateAsync({
        threadId: thread,
        content,
        files,
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
      setError(getErrorMessage(err, 'Failed to send message'))
      // Keep the message visible as a failed bubble with its own retry,
      // instead of just restoring it to the composer where it's disconnected
      // from where it appeared to fail.
      setFailedMessage({ content, files })
    } finally {
      setIsLoading(false)
      setPendingMessage(null)
    }
  }

  const handleRetrySend = () => {
    if (!failedMessage) return
    handleSend(failedMessage)
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
      setError(getErrorMessage(err, 'Failed to start quiz'))
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
      setError(getErrorMessage(err, 'Failed to start writing session'))
    }
  }

  const handleSaveNoteDirect = async (content: string) => {
    setError(null)
    try {
      const thread = await ensureThread()
      await saveNote(thread, content)
      await queryClient.refetchQueries({ queryKey: ['chat', 'thread', thread] })
      // No widget to load for notes - just a confirmation message appears in chat
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to save note'))
    }
  }

  const handleCopy = async (msg: ChatMessage) => {
    try {
      await navigator.clipboard.writeText(msg.content)
      setCopiedMessageId(msg.id)
      setTimeout(() => {
        setCopiedMessageId((id) => (id === msg.id ? null : id))
      }, 1500)
    } catch (err) {
      console.error('Failed to copy message:', err)
    }
  }

  const handleEditStart = (msg: ChatMessage) => {
    setEditingMessageId(msg.id)
    setEditingContent(msg.content)
  }

  const handleEditCancel = () => {
    setEditingMessageId(null)
    setEditingContent('')
  }

  const handleEditSave = async (messageId: number) => {
    const content = editingContent.trim()
    if (!numericThreadId || !content) return

    setError(null)
    setIsLoading(true)

    try {
      const result = await editMessage.mutateAsync({
        threadId: numericThreadId,
        messageId,
        content,
      })

      setEditingMessageId(null)

      // Editing hard-truncates everything after this message, so any
      // quiz/writing widget in flight is now stale -- clear it before
      // deciding (below, from the fresh reply) whether a new one replaces it.
      setQuizWidget(null)
      setWritingWidget(null)

      await queryClient.refetchQueries({ queryKey: ['chat', 'thread', numericThreadId] })

      if (result.assistant_message.action_type === 'QUIZ' && result.assistant_message.action_ref_id) {
        await loadQuizWidget(result.assistant_message.action_ref_id)
      }
      if (result.assistant_message.action_type === 'WRITING' && result.assistant_message.action_ref_id) {
        await loadWritingWidget(result.assistant_message.action_ref_id)
      }
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to save edit'))
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
    const isEditing = editingMessageId === msg.id
    const isCopied = copiedMessageId === msg.id

    return (
      <div
        key={msg.id}
        className={`group flex flex-col ${isUser ? 'items-end' : 'items-start'} mb-4`}
      >
        <div
          className={`max-w-[70%] rounded-card px-4 py-2 ${
            isUser
              ? 'bg-accent text-white'
              : 'bg-surface text-ink'
          } ${isEditing ? 'w-[70%]' : ''}`}
        >
          {isEditing ? (
            <div className="flex flex-col gap-2">
              <textarea
                value={editingContent}
                onChange={(e) => setEditingContent(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Escape') {
                    e.preventDefault()
                    handleEditCancel()
                  }
                }}
                autoFocus
                rows={Math.min(8, Math.max(2, editingContent.split('\n').length))}
                className="w-full resize-none bg-transparent text-white placeholder-white/70 focus:outline-none"
              />
              <div className="flex justify-end gap-2 text-sm">
                <button
                  type="button"
                  onClick={handleEditCancel}
                  className="px-2 py-1 rounded hover:bg-white/10 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => handleEditSave(msg.id)}
                  disabled={!editingContent.trim() || isLoading}
                  className="px-2 py-1 rounded bg-white/20 hover:bg-white/30 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Save
                </button>
              </div>
            </div>
          ) : isUser ? (
            <p className="whitespace-pre-wrap">{msg.content}</p>
          ) : (
            <div className="prose prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-p:my-3 prose-headings:font-semibold prose-h1:text-2xl prose-h1:mt-6 prose-h1:mb-3 prose-h2:text-xl prose-h2:mt-5 prose-h2:mb-2.5 prose-h3:text-lg prose-h3:mt-4 prose-h3:mb-2 prose-strong:font-semibold prose-ul:my-3 prose-ol:my-3 prose-li:my-1.5 prose-li:leading-relaxed prose-pre:my-3 prose-pre:bg-black/20 prose-code:before:content-none prose-code:after:content-none">
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            </div>
          )}

          {!isEditing && msg.attachments && msg.attachments.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-2">
              {msg.attachments.map((att) =>
                att.kind === 'image' ? (
                  <img
                    key={att.id}
                    src={`/api/chat/attachments/${att.id}/file`}
                    alt={att.filename}
                    className="max-w-[160px] max-h-[160px] rounded-lg border border-border object-cover"
                  />
                ) : (
                  <span
                    key={att.id}
                    className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-black/10 text-xs"
                  >
                    <svg className="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    {att.filename}
                  </span>
                )
              )}
            </div>
          )}
        </div>

        {/* Icon row: copy on every message, edit on user messages only.
            Hidden while this bubble is being edited. Revealed on hover for
            mouse users, and via `group-focus-within` for keyboard users --
            the buttons themselves are focusable (unlike the message text),
            so tabbing into the row keeps it visible instead of relying on
            `focus-within` on an unfocusable bubble. `focus:opacity-100` on
            each button also keeps it visible once it individually has
            focus, even after tabbing away from the rest of the group. */}
        {!isEditing && (
          <div className="flex gap-1 mt-1 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 transition-opacity">
            <button
              type="button"
              onClick={() => handleCopy(msg)}
              aria-label="Copy message"
              className="flex items-center justify-center w-6 h-6 rounded text-ink-muted hover:bg-border hover:text-ink focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-accent transition-colors"
            >
              {isCopied ? (
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
              )}
            </button>

            {isUser && (
              <button
                type="button"
                onClick={() => handleEditStart(msg)}
                aria-label="Edit message"
                className="flex items-center justify-center w-6 h-6 rounded text-ink-muted hover:bg-border hover:text-ink focus:opacity-100 focus:outline-none focus:ring-2 focus:ring-accent transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
              </button>
            )}
          </div>
        )}
      </div>
    )
  }

  // Loading state
  if (isLoadingThread) {
    return (
      <div className="flex items-center justify-center h-full">
        <LoadingSpinner size="lg" />
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
              onSaveNote={handleSaveNoteDirect}
              files={selectedFiles}
              onFilesChange={setSelectedFiles}
            />
            {isOffline && (
              <p className="text-warning-text mt-2">
                You&apos;re offline &mdash; messages won&apos;t send until your connection is back.
              </p>
            )}
            {error && <p className="text-danger-text mt-2">{error}</p>}
          </div>
        </div>
      </div>
    )
  }

  // Existing thread state
  return (
    <div className="flex flex-col h-full relative">
      {/* Messages */}
      <div
        ref={messagesContainerRef}
        onScroll={() => {
          if (hasNewMessages && isNearBottom()) setHasNewMessages(false)
        }}
        className="flex-1 overflow-y-auto px-4 py-4"
      >
        {threadDetail.messages.map(renderMessage)}

        {/* Optimistic user bubble, shown immediately on send */}
        {pendingMessage && (
          <div className="flex justify-end mb-4">
            <div className="max-w-[70%] rounded-card px-4 py-2 bg-accent text-white">
              <p className="whitespace-pre-wrap">{pendingMessage}</p>
            </div>
          </div>
        )}

        {/* Failed send, kept as its own bubble with an inline retry so the
            failure is tied to the message that didn't go through, instead
            of the message vanishing and only a generic caption appearing
            under the composer. */}
        {failedMessage && !pendingMessage && (
          <div className="flex flex-col items-end mb-4">
            <div className="max-w-[70%] rounded-card px-4 py-2 bg-accent/50 text-white">
              <p className="whitespace-pre-wrap">
                {failedMessage.content ||
                  (failedMessage.files.length ? `${failedMessage.files.length} file(s) attached` : '')}
              </p>
            </div>
            <button
              type="button"
              onClick={handleRetrySend}
              className="mt-1 text-xs text-danger-text hover:underline"
            >
              Failed to send · Tap to retry
            </button>
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

      {/* "New message" pill, shown when a message arrived while the user was
          scrolled up reading earlier history. */}
      {hasNewMessages && (
        <button
          type="button"
          onClick={() => scrollToBottom()}
          className="absolute left-1/2 -translate-x-1/2 bottom-24 px-3 py-1.5 rounded-full bg-accent text-white text-sm shadow-lg hover:bg-accent-hover transition-colors"
        >
          ↓ New message
        </button>
      )}

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
          files={selectedFiles}
          onFilesChange={setSelectedFiles}
        />
        {isOffline && (
          <p className="text-warning-text mt-2">
            You&apos;re offline &mdash; messages won&apos;t send until your connection is back.
          </p>
        )}
        {error && <p className="text-danger-text mt-2">{error}</p>}
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
  onSaveNote,
  files,
  onFilesChange,
}: {
  value: string
  onChange: (v: string) => void
  onSubmit: () => void
  disabled?: boolean
  placeholder?: string
  onStartQuiz?: (size: number) => void
  onStartWriting?: (mode: 'mini' | 'weekly') => void
  onSaveNote?: (content: string) => void
  files?: File[]
  onFilesChange?: (files: File[]) => void
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
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

  const [attachmentError, setAttachmentError] = useState<string | null>(null)

  const handleFilesSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(e.target.files ?? [])
    const maxBytes = MAX_ATTACHMENT_SIZE_MB * 1024 * 1024
    const tooLarge = picked.filter((f) => f.size > maxBytes)
    const accepted = picked.filter((f) => f.size <= maxBytes)

    if (tooLarge.length) {
      setAttachmentError(
        `${tooLarge.map((f) => f.name).join(', ')} exceeds the ${MAX_ATTACHMENT_SIZE_MB}MB limit and wasn't attached.`
      )
    } else {
      setAttachmentError(null)
    }

    if (accepted.length && onFilesChange) {
      onFilesChange([...(files ?? []), ...accepted])
    }
    // Reset so selecting the same file again still fires onChange.
    e.target.value = ''
  }

  const removeFile = (index: number) => {
    if (!onFilesChange) return
    onFilesChange((files ?? []).filter((_, i) => i !== index))
  }

  const showPlusMenu = onStartQuiz && onStartWriting

  return (
    <div className="flex flex-col gap-2">
      {attachmentError && (
        <p className="px-1 text-xs text-danger-text">{attachmentError}</p>
      )}

      {/* Selected file chips, shown above the composer before sending */}
      {files && files.length > 0 && (
        <div className="flex flex-wrap gap-2 px-1">
          {files.map((f, i) => (
            <span
              key={`${f.name}-${i}`}
              className="inline-flex items-center gap-1.5 px-2 py-1 rounded-lg bg-border text-xs text-ink"
            >
              {f.name}
              <button
                type="button"
                onClick={() => removeFile(i)}
                aria-label={`Remove ${f.name}`}
                className="text-ink-muted hover:text-ink"
              >
                &times;
              </button>
            </span>
          ))}
        </div>
      )}

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
                onSaveNote={onSaveNote!}
              />
            )}
          </>
        )}

        {onFilesChange && (
          <>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept={ACCEPTED_ATTACHMENT_TYPES}
              onChange={handleFilesSelected}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={disabled}
              aria-label="Attach files"
              title={`Attach ${ACCEPTED_ATTACHMENT_LABEL} (up to ${MAX_ATTACHMENT_SIZE_MB}MB each)`}
              className="flex items-center justify-center w-9 h-9 rounded-full text-ink-muted hover:bg-border hover:text-ink disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21.44 11.05l-9.19 9.19a5 5 0 01-7.07-7.07l9.19-9.19a3.5 3.5 0 014.95 4.95l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
              </svg>
            </button>
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
          disabled={disabled || (!value.trim() && !(files && files.length))}
          aria-label="Send message"
          className="flex items-center justify-center w-9 h-9 rounded-full bg-accent text-white hover:bg-accent-hover disabled:bg-border disabled:text-ink-faint disabled:cursor-not-allowed transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 15l7-7 7 7" />
          </svg>
        </button>
      </div>
    </div>
  )
}

