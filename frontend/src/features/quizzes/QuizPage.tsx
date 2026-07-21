import { useState, useCallback } from 'react'
import { useStartQuiz, useSubmitAnswer } from './hooks'
import { QuizModeSelector } from './components/QuizModeSelector'
import { QuestionCard } from './components/QuestionCard'
import { SessionSummary } from './components/SessionSummary'
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

    // Move to next question if available
    if (session && currentQuestionIndex < session.questions.length - 1) {
      setCurrentQuestionIndex(prev => prev + 1)
    }
  }, [session, currentQuestionIndex])

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
      <div className="quiz-page">
        <QuizModeSelector
          onSelectMode={handleSelectMode}
          disabled={startLoading}
        />
        {startError && (
          <div className="error-message">{startError}</div>
        )}
      </div>
    )
  }

  if (view === 'summary' && result) {
    return (
      <div className="quiz-page">
        <SessionSummary
          totalQuestions={result.total_questions}
          correctCount={result.correct_count}
          incorrectCount={result.incorrect_count}
          questions={result.questions}
          onRestart={handleRestart}
        />
      </div>
    )
  }

  // view === 'quiz'
  if (!session) {
    return (
      <div className="quiz-page">
        <p>Loading quiz...</p>
      </div>
    )
  }

  const currentQuestion = session.questions[currentQuestionIndex]
  const currentAnswer = answers[currentQuestion.id] || ''

  return (
    <div className="quiz-page">
      <div className="quiz-header">
        <h2>Question {currentQuestionIndex + 1} of {session.questions.length}</h2>
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${((currentQuestionIndex + 1) / session.questions.length) * 100}%` }}
          />
        </div>
      </div>

      <QuestionCard
        id={currentQuestion.id}
        questionType={currentQuestion.question_type}
        prompt={currentQuestion.prompt}
        distractors={currentQuestion.distractors}
        userAnswer={currentAnswer}
        onAnswer={handleAnswer}
      />

      <div className="quiz-navigation">
        {currentQuestionIndex > 0 && (
          <button
            className="nav-button prev"
            onClick={() => setCurrentQuestionIndex(prev => prev - 1)}
          >
            Previous
          </button>
        )}

        {currentQuestionIndex < session.questions.length - 1 ? (
          <button
            className="nav-button next"
            onClick={() => setCurrentQuestionIndex(prev => prev + 1)}
            disabled={!currentAnswer}
          >
            Next
          </button>
        ) : (
          <button
            className="nav-button submit"
            onClick={handleSubmitAll}
            disabled={!canSubmit || submitLoading}
          >
            {submitLoading ? 'Submitting...' : 'Submit All'}
          </button>
        )}
      </div>

      <div className="question-dots">
        {session.questions.map((q, index) => (
          <button
            key={q.id}
            className={`dot ${index === currentQuestionIndex ? 'current' : ''} ${answers[q.id] ? 'answered' : ''}`}
            onClick={() => setCurrentQuestionIndex(index)}
          >
            {index + 1}
          </button>
        ))}
      </div>

      {submitError && (
        <div className="error-message">{submitError}</div>
      )}
    </div>
  )
}