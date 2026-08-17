import { useState, useCallback } from 'react'
import { QuestionCard } from './QuestionCard'
import { Button } from '../../../shared/components/Button'
import type { QuizMode } from '../../../api/types'

// Structurally compatible with both QuizQuestionState (fresh, in-progress
// questions from useStartQuiz) and QuizQuestion (chat widget's
// GET /api/quizzes/{session_id} shape) - either can be passed in directly.
export interface RunnerQuestion {
  id: number
  question_type: QuizMode
  prompt: string
  options?: string[] | null
}

interface QuizRunnerProps {
  questions: RunnerQuestion[]
  onSubmitAll: (answers: Record<number, string>) => void | Promise<void>
  submitting?: boolean
  submitError?: string | null
}

/**
 * Shared "taking a quiz" UI: progress header, QuestionCard, Prev/Next/Submit
 * navigation, and question dots. Used by the in-chat quiz widget and the
 * Reports weekly-review flow so the two surfaces never drift out of sync
 * (see Work Item B, Praxis chat-integration refactor).
 */
export function QuizRunner({
  questions,
  onSubmitAll,
  submitting = false,
  submitError = null,
}: QuizRunnerProps) {
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, string>>({})

  const handleAnswer = useCallback((questionId: number, answer: string) => {
    setAnswers(prev => ({ ...prev, [questionId]: answer }))
  }, [])

  const canSubmit = questions.length > 0 && Object.keys(answers).length === questions.length

  const currentQuestion = questions[currentQuestionIndex]
  const currentAnswer = currentQuestion ? answers[currentQuestion.id] || '' : ''

  if (!currentQuestion) return null

  return (
    <div className="w-full bg-surface rounded-card p-6 space-y-6">
      {/* Header with progress */}
      <div className="space-y-2">
        <h2 className="text-xl font-medium text-ink">
          Question {currentQuestionIndex + 1} of {questions.length}
        </h2>
        <div className="h-2 bg-border rounded-full overflow-hidden">
          <div
            className="h-full bg-accent transition-all duration-300"
            style={{ width: `${((currentQuestionIndex + 1) / questions.length) * 100}%` }}
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

        {currentQuestionIndex < questions.length - 1 ? (
          <Button
            variant="primary"
            onClick={() => setCurrentQuestionIndex(prev => prev + 1)}
          >
            Next
          </Button>
        ) : (
          <Button
            variant="primary"
            onClick={() => onSubmitAll(answers)}
            disabled={!canSubmit || submitting}
          >
            {submitting ? 'Submitting...' : 'Submit All'}
          </Button>
        )}
      </div>

      {/* Question dots */}
      <div className="flex justify-center gap-2 flex-wrap">
        {questions.map((q, index) => (
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
        <div className="p-4 bg-danger-tint border border-danger-border rounded-lg text-danger-text">{submitError}</div>
      )}
    </div>
  )
}
