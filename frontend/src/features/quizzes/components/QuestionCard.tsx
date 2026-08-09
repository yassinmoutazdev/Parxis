import { useEffect } from 'react'
import { Card, CardContent } from '../../../shared/components/Card'
import type { QuizMode } from '../../../api/types'

interface QuestionCardProps {
  id: number
  questionType: QuizMode
  prompt: string
  options?: string[] | null
  userAnswer?: string
  isCorrect?: boolean | null
  score?: number | null
  feedback?: string | null
  readOnly?: boolean
  onAnswer: (questionId: number, answer: string) => void
}

export function QuestionCard({
  id,
  questionType,
  prompt,
  options,
  userAnswer = '',
  isCorrect,
  score,
  feedback,
  readOnly = false,
  onAnswer,
}: QuestionCardProps) {
  // Sync with parent state - keep in sync with answers from QuizPage
  useEffect(() => {
    // This ensures the component stays in sync with parent state
  }, [userAnswer])

  const renderInput = () => {
    // Show result if graded
    if (isCorrect !== null && isCorrect !== undefined) {
      return (
        <div className="space-y-3">
          <div className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
            isCorrect
              ? 'bg-green-900/30 text-green-400 border border-green-700'
              : 'bg-red-900/30 text-red-400 border border-red-700'
          }`}>
            {isCorrect ? '✓ Correct' : '✗ Incorrect'}
          </div>
          {score != null && (
            <div className="text-ink-muted">Score: {Math.round((score ?? 0) * 100)}%</div>
          )}
          {feedback && <div className="text-ink-muted text-sm">{feedback}</div>}
        </div>
      )
    }

    // Only MULTIPLE_CHOICE is supported now
    if (options && options.length > 0) {
      // Render options as clickable cards
      return (
        <div className="space-y-4">
          <p className="text-lg text-ink font-medium">{prompt}</p>
          <div className="grid grid-cols-1 gap-3">
            {options.map((option, index) => (
              <button
                key={index}
                type="button"
                onClick={() => onAnswer(id, option)}
                disabled={readOnly}
                className={`
                  p-4 rounded-card border text-left transition-all
                  ${userAnswer === option
                    ? 'bg-accent-tint border-accent text-ink'
                    : 'bg-surface border-border hover:border-border-strong text-ink'}
                `}
              >
                {option}
              </button>
            ))}
          </div>
        </div>
      )
    }

    // Fallback (should not happen with current backend)
    return (
      <div className="space-y-3">
        <p className="text-lg text-ink font-medium">{prompt}</p>
        <input
          type="text"
          value={userAnswer}
          onChange={(e) => onAnswer(id, e.target.value)}
          placeholder="Type your answer"
          disabled={readOnly}
          className="w-full px-4 py-2 bg-cream border border-border rounded-lg text-ink placeholder:text-ink-faint focus:border-accent focus:outline-none"
        />
      </div>
    )
  }

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex items-center">
          <span className="px-2 py-1 bg-surface text-ink-muted text-xs uppercase tracking-wide rounded">
            {questionType.replace('_', ' ')}
          </span>
        </div>
        {renderInput()}
      </CardContent>
    </Card>
  )
}