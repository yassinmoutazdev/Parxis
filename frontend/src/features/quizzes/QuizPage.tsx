import { useState, useCallback } from 'react'
import { useStartQuiz, useSubmitAnswer } from './hooks'
import { QuizModeSelector } from './components/QuizModeSelector'
import { QuizRunner } from './components/QuizRunner'
import { SessionSummary } from './components/SessionSummary'
import { LoadingOverlay } from '../../shared/components/LoadingSpinner'
import type { QuizMode } from '../../api/types'

type QuizView = 'selector' | 'quiz' | 'summary'

export default function QuizPage() {
  const [view, setView] = useState<QuizView>('selector')

  const { session, loading: startLoading, error: startError, start, reset } = useStartQuiz()
  const { result, loading: submitLoading, error: submitError, submit, reset: resetResult } = useSubmitAnswer()

  const handleSelectMode = useCallback(async (mode: QuizMode, size: number) => {
    try {
      await start(mode, size)
      setView('quiz')
    } catch (e) {
      console.error('Failed to start quiz:', e)
    }
  }, [start])

  const handleSubmitAll = useCallback(async (answers: Record<number, string>) => {
    if (!session) return

    try {
      await submit(session.id, answers)
      setView('summary')
    } catch (e) {
      console.error('Failed to submit answers:', e)
    }
  }, [session, submit])

  const handleRestart = useCallback(() => {
    reset()
    resetResult()
    setView('selector')
  }, [reset, resetResult])

  if (view === 'selector') {
    return (
      <div className="min-h-screen bg-cream px-6 py-8">
        <div className="max-w-4xl mx-auto relative">
          <QuizModeSelector
            onSelectMode={handleSelectMode}
            disabled={startLoading}
          />
          {startLoading && <LoadingOverlay message="Generating your quiz..." />}
          {startError && (
            <div className="mt-4 p-4 bg-red-900/20 border border-red-500 rounded-lg text-red-400">{startError}</div>
          )}
        </div>
      </div>
    )
  }

  if (view === 'summary' && result) {
    return (
      <div className="min-h-screen bg-cream px-6 py-8">
        <div className="max-w-2xl mx-auto">
          <SessionSummary
            totalQuestions={result.total_questions}
            correctCount={result.correct_count}
            incorrectCount={result.incorrect_count}
            questions={result.questions}
            onRestart={handleRestart}
          />
        </div>
      </div>
    )
  }

  // view === 'quiz'
  if (!session) {
    return (
      <div className="min-h-screen bg-cream flex items-center justify-center">
        <p className="text-ink-muted">Loading quiz...</p>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-cream px-6 py-8">
      <div className="max-w-2xl mx-auto">
        <QuizRunner
          questions={session.questions}
          onSubmitAll={handleSubmitAll}
          submitting={submitLoading}
          submitError={submitError}
        />
      </div>
    </div>
  )
}