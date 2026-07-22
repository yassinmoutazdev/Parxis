import { useState, useCallback } from 'react'
import { useStartQuiz, useSubmitAnswer } from './hooks'
import { QuizModeSelector } from './components/QuizModeSelector'
import { QuestionCard } from './components/QuestionCard'
import { SessionSummary } from './components/SessionSummary'
import { Button } from '../../shared/components/Button'
import { LoadingOverlay } from '../../shared/components/LoadingSpinner'
import type { QuizMode } from '../../api/types'

type QuizView = 'selector' | 'quiz' | 'summary'

export default function QuizPage() {
  const [view, setView] = useState<QuizView>('selector')
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})

  const { session, loading: startLoading, error: startError, start, reset } = useStartQuiz()
  const { result, loading: submitLoading, error: submitError, submit, reset: resetResult } = useSubmitAnswer()

  const handleSelectMode = useCallback(async (mode: QuizMode, size: number) => {
    try {
      await start(mode, size)
      setAnswers({})
      setCurrentQuestionIndex(0)
      setView('quiz')
    } catch (e) {
      console.error('Failed to start quiz:', e)
    }
  }, [start])

  const handleAnswer = useCallback((questionId: number, answer: string) => {
    setAnswers(prev => ({ ...prev, [questionId]: answer }))
    // Navigation is handled via Prev/Next buttons and question dots, not auto-advance
  }, [])

  const handleSubmitAll = useCallback(async () => {
    if (!session) return

    try {
      await submit(session.id, answers)
      setView('summary')
    } catch (e) {
      console.error('Failed to submit answers:', e)
    }
  }, [session, submit, answers])

  const handleRestart = useCallback(() => {
    reset()
    resetResult()
    setView('selector')
    setCurrentQuestionIndex(0)
    setAnswers({})
  }, [reset, resetResult])

  const canSubmit = session && Object.keys(answers).length === session.questions.length

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

  const currentQuestion = session.questions[currentQuestionIndex]
  const currentAnswer = answers[currentQuestion.id] || ''

  return (
    <div className="min-h-screen bg-cream px-6 py-8">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header with progress */}
        <div className="space-y-2">
          <h2 className="text-xl font-medium text-ink">
            Question {currentQuestionIndex + 1} of {session.questions.length}
          </h2>
          <div className="h-2 bg-border rounded-full overflow-hidden">
            <div
              className="h-full bg-accent transition-all duration-300"
              style={{ width: `${((currentQuestionIndex + 1) / session.questions.length) * 100}%` }}
            />
          </div>
        </div>

        {/* Question Card */}
        <QuestionCard
          id={currentQuestion.id}
          questionType={currentQuestion.question_type}
          prompt={currentQuestion.prompt}
          options={currentQuestion.options}
          userAnswer={currentAnswer}
          onAnswer={handleAnswer}
        />

        {/* Navigation */}
        <div className="flex justify-between">
          <Button
            variant="secondary"
            onClick={() => setCurrentQuestionIndex(prev => prev - 1)}
            disabled={currentQuestionIndex === 0}
          >
            Previous
          </Button>

          {currentQuestionIndex < session.questions.length - 1 ? (
            <Button
              variant="primary"
              onClick={() => setCurrentQuestionIndex(prev => prev + 1)}
            >
              Next
            </Button>
          ) : (
            <Button
              variant="primary"
              onClick={handleSubmitAll}
              disabled={!canSubmit || submitLoading}
            >
              {submitLoading ? 'Submitting...' : 'Submit All'}
            </Button>
          )}
        </div>

        {/* Question dots */}
        <div className="flex justify-center gap-2 flex-wrap">
          {session.questions.map((q, index) => (
            <button
              key={q.id}
              onClick={() => setCurrentQuestionIndex(index)}
              className={`
                w-8 h-8 rounded-full text-sm font-medium transition-all
                ${index === currentQuestionIndex
                  ? 'ring-2 ring-accent text-ink'
                  : answers[q.id]
                    ? 'bg-accent-tint text-accent-text'
                    : 'bg-border text-ink-muted hover:bg-border-strong'}
              `}
            >
              {index + 1}
            </button>
          ))}
        </div>

        {submitError && (
          <div className="p-4 bg-red-900/20 border border-red-500 rounded-lg text-red-400">{submitError}</div>
        )}
      </div>
    </div>
  )
}