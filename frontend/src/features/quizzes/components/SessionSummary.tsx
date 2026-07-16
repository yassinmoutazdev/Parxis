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
    <div className="session-summary">
      <h2>Quiz Complete!</h2>

      <div className="summary-stats">
        <div className="stat">
          <span className="stat-value">{totalQuestions}</span>
          <span className="stat-label">Total</span>
        </div>
        <div className="stat correct">
          <span className="stat-value">{correctCount}</span>
          <span className="stat-label">Correct</span>
        </div>
        <div className="stat incorrect">
          <span className="stat-value">{incorrectCount}</span>
          <span className="stat-label">Incorrect</span>
        </div>
        <div className="stat percentage">
          <span className="stat-value">{percentage}%</span>
          <span className="stat-label">Score</span>
        </div>
      </div>

      <div className="question-review">
        <h3>Review Your Answers</h3>
        {questions.map((q, index) => (
          <div
            key={q.id}
            className={`review-item ${q.is_correct ? 'correct' : 'incorrect'}`}
          >
            <div className="review-number">{index + 1}</div>
            <div className="review-content">
              <div className="review-prompt">{q.prompt}</div>
              <div className="review-answer">
                <span className="label">Your answer:</span>
                <span className="answer">{q.user_answer || '(no answer)'}</span>
              </div>
              {!q.is_correct && q.feedback && (
                <div className="review-feedback">
                  <span className="label">Feedback:</span>
                  <span className="feedback">{q.feedback}</span>
                </div>
              )}
            </div>
            <div className="review-result">
              {q.is_correct ? '✓' : '✗'}
            </div>
          </div>
        ))}
      </div>

      <button className="restart-button" onClick={onRestart}>
        Start Another Quiz
      </button>
    </div>
  )
}