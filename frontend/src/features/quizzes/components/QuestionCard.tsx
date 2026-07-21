import { useState, useEffect } from 'react'
import type { QuizMode } from '../../../api/types'

interface QuestionCardProps {
  id: number
  questionType: QuizMode
  prompt: string
  distractors?: string[] | null
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
  distractors,
  userAnswer = '',
  isCorrect,
  score,
  feedback,
  readOnly = false,
  onAnswer,
}: QuestionCardProps) {
  const [answer, setAnswer] = useState(userAnswer)

  useEffect(() => {
    setAnswer(userAnswer)
  }, [userAnswer])

  const handleSubmit = () => {
    if (answer.trim()) {
      onAnswer(id, answer)
    }
  }

  const renderInput = () => {
    // Show result if graded
    if (isCorrect !== null && isCorrect !== undefined) {
      return (
        <div className="question-result">
          <div className={`result-badge ${isCorrect ? 'correct' : 'incorrect'}`}>
            {isCorrect ? '✓ Correct' : '✗ Incorrect'}
          </div>
          {score != null && (
            <div className="score">Score: {Math.round((score ?? 0) * 100)}%</div>
          )}
          {feedback && <div className="feedback">{feedback}</div>}
        </div>
      )
    }

    switch (questionType) {
      case 'FILL_BLANK':
        return (
          <div className="fill-blank-input">
            {prompt.split('[blank]').map((part, index) => (
              <span key={index}>
                {part}
                {index < prompt.split('[blank]').length - 1 && (
                  <input
                    type="text"
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    placeholder="type your answer"
                    disabled={readOnly}
                    onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
                  />
                )}
              </span>
            ))}
            <button onClick={handleSubmit} disabled={!answer.trim() || readOnly}>
              Submit
            </button>
          </div>
        )

      case 'MULTIPLE_CHOICE':
        if (distractors && distractors.length > 0) {
          // Render radio buttons with options
          const allOptions = [prompt.match(/\[blank\](.*)$/)?.[1]?.trim() || '', ...distractors]
            .filter(Boolean)
            .sort(() => Math.random() - 0.5)

          return (
            <div className="multiple-choice-input">
              {allOptions.map((option, index) => (
                <label key={index} className={`option ${answer === option ? 'selected' : ''}`}>
                  <input
                    type="radio"
                    name={`question-${id}`}
                    value={option}
                    checked={answer === option}
                    onChange={(e) => {
                      setAnswer(e.target.value)
                      onAnswer(id, e.target.value)
                    }}
                    disabled={readOnly}
                  />
                  {option}
                </label>
              ))}
            </div>
          )
        }
        // Fallback to text input if no distractors
        return (
          <div className="text-input">
            <input
              type="text"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Type your answer"
              disabled={readOnly}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            />
            <button onClick={handleSubmit} disabled={!answer.trim() || readOnly}>
              Submit
            </button>
          </div>
        )

      case 'RECALL':
        return (
          <div className="text-input">
            <input
              type="text"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="What does it mean?"
              disabled={readOnly}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            />
            <button onClick={handleSubmit} disabled={!answer.trim() || readOnly}>
              Submit
            </button>
          </div>
        )

      case 'ERROR_CORRECTION':
        return (
          <div className="textarea-input">
            <p className="prompt">{prompt}</p>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Write your correction here..."
              disabled={readOnly}
              rows={3}
            />
            <button onClick={handleSubmit} disabled={!answer.trim() || readOnly}>
              Submit
            </button>
          </div>
        )

      case 'REWRITE_NATURALLY':
      case 'CONVERSATION':
      case 'MINI_ESSAY':
        return (
          <div className="textarea-input">
            <p className="prompt">{prompt}</p>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Write your response..."
              disabled={readOnly}
              rows={5}
            />
            <button onClick={handleSubmit} disabled={!answer.trim() || readOnly}>
              Submit
            </button>
          </div>
        )

      default:
        return (
          <div className="text-input">
            <input
              type="text"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Your answer"
              disabled={readOnly}
              onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
            />
            <button onClick={handleSubmit} disabled={!answer.trim() || readOnly}>
              Submit
            </button>
          </div>
        )
    }
  }

  return (
    <div className={`question-card question-type-${questionType.toLowerCase()}`}>
      <div className="question-type-badge">{questionType}</div>
      {renderInput()}
    </div>
  )
}