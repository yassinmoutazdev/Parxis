import { Card } from '../../../shared/components/Card'
import { Button } from '../../../shared/components/Button'
import type { QuizMode } from '../../../api/types'

interface GradedQuestion {
  id: number
  question_type: QuizMode
  prompt: string
  user_answer: string | null
  is_correct: boolean | null
  score: number | null
  feedback: string | null
  graded_by: string | null
}

interface SessionSummaryProps {
  totalQuestions: number
  correctCount: number
  incorrectCount: number
  questions: GradedQuestion[]
  onRestart: () => void
}

export function SessionSummary({
  totalQuestions,
  correctCount,
  incorrectCount,
  questions,
  onRestart,
}: SessionSummaryProps) {
  const percentage = totalQuestions > 0 ? Math.round((correctCount / totalQuestions) * 100) : 0

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold text-ink">Quiz Complete!</h2>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="text-3xl font-bold text-ink">{totalQuestions}</div>
          <div className="text-sm text-ink-muted">Total</div>
        </Card>
        <Card className="text-center">
          <div className="text-3xl font-bold text-green-400">{correctCount}</div>
          <div className="text-sm text-ink-muted">Correct</div>
        </Card>
        <Card className="text-center">
          <div className="text-3xl font-bold text-red-400">{incorrectCount}</div>
          <div className="text-sm text-ink-muted">Incorrect</div>
        </Card>
        <Card className="text-center">
          <div className="text-3xl font-bold text-accent">{percentage}%</div>
          <div className="text-sm text-ink-muted">Score</div>
        </Card>
      </div>

      {/* Question Review */}
      <div className="space-y-4">
        <h3 className="text-lg font-medium text-ink">Review Your Answers</h3>
        {questions.map((q) => (
          <Card key={q.id} className={q.is_correct ? 'border-green-700/50' : 'border-red-700/50'}>
            <div className="flex items-start gap-4">
              <div className={`
                w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 font-medium
                ${q.is_correct ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'}
              `}>
                {q.is_correct ? '✓' : '✗'}
              </div>
              <div className="flex-1 space-y-2">
                <div className="text-ink-muted text-sm">{q.prompt}</div>
                <div className="text-sm">
                  <span className="text-ink-faint">Your answer: </span>
                  <span className="text-ink">{q.user_answer || '(no answer)'}</span>
                </div>
                {!q.is_correct && q.feedback && (
                  <div className="text-sm">
                    <span className="text-ink-faint">Feedback: </span>
                    <span className="text-ink-muted">{q.feedback}</span>
                  </div>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Button variant="primary" onClick={onRestart} size="lg">
        Start Another Quiz
      </Button>
    </div>
  )
}