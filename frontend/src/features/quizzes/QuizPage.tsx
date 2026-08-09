import { useState, useCallback } from 'react'
import { useStartQuiz, useSubmitAnswer } from './hooks'
import { QuizRunner } from './components/QuizRunner'
import { SessionSummary } from './components/SessionSummary'
import { LoadingOverlay, Button } from '../../shared/components'
import { Card, CardContent } from '../../shared/components/Card'

type QuizView = 'quiz' | 'summary'

export default function QuizPage() {
  const [view, setView] = useState<QuizView>('quiz')
  const [size, setSize] = useState(10)

  const { session, loading: startLoading, error: startError, start, reset } = useStartQuiz()
  const { result, loading: submitLoading, error: submitError, submit, reset: resetResult } = useSubmitAnswer()

  const handleStartQuiz = useCallback(async (quizSize: number) => {
    try {
      await start(quizSize)
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
    setView('quiz')
  }, [reset, resetResult])

  const handleSizeChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setSize(Number(e.target.value))
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
      <div className="min-h-screen bg-cream px-6 py-8">
        <div className="max-w-xl mx-auto">
          <Card className="mb-6">
            <CardContent className="space-y-4">
              <h2 className="text-2xl font-semibold text-ink">Practice Quiz</h2>
              <p className="text-ink-muted">
                All questions are multiple choice. Select the number of questions and start.
              </p>
              <div className="flex items-center gap-4">
                <label className="text-ink-muted">
                  Number of Questions:
                  <select
                    value={size}
                    onChange={handleSizeChange}
                    disabled={startLoading}
                    className="ml-2 px-3 py-1.5 bg-surface border border-border rounded-lg text-ink focus:border-accent focus:outline-none"
                  >
                    <option value={5}>5</option>
                    <option value={10}>10</option>
                    <option value={15}>15</option>
                    <option value={20}>20</option>
                  </select>
                </label>
              </div>
              <Button
                onClick={() => handleStartQuiz(size)}
                disabled={startLoading}
                size="lg"
                className="w-full"
              >
                Start Quiz
              </Button>
            </CardContent>
          </Card>
          {startLoading && <LoadingOverlay message="Generating your quiz..." />}
          {startError && (
            <div className="mt-4 p-4 bg-red-900/20 border border-red-500 rounded-lg text-red-400">{startError}</div>
          )}
        </div>
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