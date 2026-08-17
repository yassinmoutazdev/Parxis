import { useState, useEffect } from 'react'
import {
  useStartWeeklyReview,
  useWeeklyQuiz,
  useWeeklyWriting,
  useWeeklyReports,
} from './hooks'
import ReportSummaryCard from './components/ReportSummaryCard'
import { QuizRunner } from '../quizzes/components/QuizRunner'
import type { RunnerQuestion } from '../quizzes/components/QuizRunner'
import WritingEditor from '../writing/components/WritingEditor'
import EvaluationFeedback from '../writing/components/EvaluationFeedback'
import { getQuizSession, submitQuizAnswers } from '../../api/client'
import { LoadingSpinner } from '../../shared/components/LoadingSpinner'

type ReviewStep = 'select' | 'quiz' | 'writing' | 'complete'

// Wizard steps shown in the step indicator (select/complete aren't part of
// the linear "answer questions" flow, so they're excluded).
const WIZARD_STEPS: { key: ReviewStep; label: string }[] = [
  { key: 'quiz', label: 'Quiz' },
  { key: 'writing', label: 'Writing' },
]

function StepIndicator({ step }: { step: ReviewStep }) {
  const currentIndex = WIZARD_STEPS.findIndex((s) => s.key === step)
  if (currentIndex === -1) return null

  return (
    <div className="flex items-center gap-2 mb-4 text-sm" aria-label={`Step ${currentIndex + 1} of ${WIZARD_STEPS.length}`}>
      {WIZARD_STEPS.map((s, i) => (
        <div key={s.key} className="flex items-center gap-2">
          <div
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full ${
              i === currentIndex
                ? 'bg-accent-tint text-accent-text font-medium'
                : i < currentIndex
                ? 'text-ink-muted'
                : 'text-ink-faint'
            }`}
          >
            <span
              className={`flex items-center justify-center w-4 h-4 rounded-full text-[10px] ${
                i <= currentIndex ? 'bg-accent text-white' : 'bg-border text-ink-faint'
              }`}
            >
              {i < currentIndex ? '✓' : i + 1}
            </span>
            {s.label}
          </div>
          {i < WIZARD_STEPS.length - 1 && <span className="text-ink-faint">→</span>}
        </div>
      ))}
    </div>
  )
}

export default function ReportsPage() {
  const [step, setStep] = useState<ReviewStep>('select')
  const [currentReport, setCurrentReport] = useState<number | null>(null)

  // Full questions (with options) for the quiz currently in progress --
  // useWeeklyQuiz's own state only carries {id, question_type, prompt} from
  // POST /reports/weekly/quiz, which is missing the options needed to
  // actually answer a multiple-choice question. Fetched separately below.
  const [quizQuestions, setQuizQuestions] = useState<RunnerQuestion[]>([])
  const [quizQuestionsLoading, setQuizQuestionsLoading] = useState(false)
  const [quizSubmitting, setQuizSubmitting] = useState(false)
  const [quizSubmitError, setQuizSubmitError] = useState<string | null>(null)

  const weeklyReview = useStartWeeklyReview()
  const weeklyQuiz = useWeeklyQuiz()
  const weeklyWriting = useWeeklyWriting()
  const reports = useWeeklyReports()

  // Load reports on mount
  useEffect(() => {
    reports.fetchReports()
  }, [])

  const handleStartReview = async () => {
    try {
      const result = await weeklyReview.start()
      if (result.existing_report_id) {
        // Already have a report for this week
        setCurrentReport(result.existing_report_id)
        setStep('complete')
      } else {
        // Start quiz step
        setStep('quiz')
      }
    } catch (e) {
      console.error('Failed to start review:', e)
    }
  }

  const handleStartQuiz = async () => {
    try {
      const result = await weeklyQuiz.startQuiz()
      // The weekly-quiz start endpoint doesn't return answer options, so
      // fetch the full session (same one chat's quiz widget fetches from)
      // to get questions we can actually answer.
      setQuizQuestionsLoading(true)
      try {
        const fullSession = await getQuizSession(result.session_id)
        setQuizQuestions(fullSession.questions)
      } finally {
        setQuizQuestionsLoading(false)
      }
    } catch (e) {
      console.error('Failed to start quiz:', e)
    }
  }

  const handleQuizSubmit = async (answers: Record<number, string>) => {
    if (!weeklyQuiz.quizState.sessionId) return
    setQuizSubmitError(null)
    setQuizSubmitting(true)
    try {
      await submitQuizAnswers(weeklyQuiz.quizState.sessionId, answers)
      // Quiz step complete - move to writing. The final combined report
      // (quiz + writing) is assembled server-side at finalize time, so
      // there's no separate per-quiz score screen here by design.
      setStep('writing')
    } catch (e) {
      setQuizSubmitError(e instanceof Error ? e.message : 'Failed to submit answers')
    } finally {
      setQuizSubmitting(false)
    }
  }

  const handleStartWriting = async () => {
    try {
      await weeklyWriting.createPrompt()
    } catch (e) {
      console.error('Failed to create writing prompt:', e)
    }
  }

  const handleSubmitWriting = async (text: string) => {
    if (!weeklyWriting.writingState.promptId) return
    try {
      await weeklyWriting.submitWriting(weeklyWriting.writingState.promptId, text)
    } catch (e) {
      console.error('Failed to submit writing:', e)
    }
  }

  const handleFinalize = async () => {
    try {
      const report = await weeklyWriting.finalizeReport(
        weeklyReview.reviewState.weekStart || undefined,
        weeklyReview.reviewState.weekEnd || undefined
      )
      setCurrentReport(report.id)
      setStep('complete')
      // Refresh reports list
      reports.fetchReports()
    } catch (e) {
      console.error('Failed to finalize report:', e)
    }
  }

  const handleBack = () => {
    if (step === 'quiz') {
      setStep('select')
      weeklyReview.reset()
      setQuizQuestions([])
      setQuizSubmitError(null)
    } else if (step === 'writing') {
      setStep('quiz')
      weeklyQuiz.reset()
      setQuizQuestions([])
      setQuizSubmitError(null)
    } else if (step === 'complete') {
      setStep('select')
      weeklyReview.reset()
      weeklyQuiz.reset()
      weeklyWriting.reset()
      setQuizQuestions([])
      setQuizSubmitError(null)
      setCurrentReport(null)
    }
  }

  // View: Past reports archive
  if (step === 'select' && !currentReport) {
    return (
      <div className="px-6 py-6">
        <div className="max-w-4xl mx-auto">
          <h1 className="font-serif text-2xl text-ink mb-6">Weekly Reports</h1>

          {/* Start New Review Button */}
          <div className="mb-8">
            <button
              onClick={handleStartReview}
              disabled={weeklyReview.loading}
              className="w-full md:w-auto px-6 py-3 bg-accent text-white rounded-lg hover:bg-accent-hover disabled:bg-border-strong"
            >
              {weeklyReview.loading ? 'Loading...' : 'Start Weekly Review'}
            </button>
          </div>

          {/* Past Reports */}
          <div>
            <h2 className="text-lg font-semibold text-ink mb-4">Past Reports</h2>
            {reports.loading ? (
              <div className="py-4">
                <LoadingSpinner />
              </div>
            ) : reports.reports.length === 0 ? (
              <p className="text-ink-muted">No reports yet. Start a weekly review to generate your first report.</p>
            ) : (
              <div className="space-y-4">
                {reports.reports.map((report) => (
                  <ReportSummaryCard key={report.id} report={report} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // View: Weekly Review Flow
  return (
    <div className="px-6 py-6">
      <div className="max-w-3xl mx-auto">
        {/* Back button */}
        <button
          onClick={handleBack}
          className="mb-4 text-ink-muted hover:text-ink flex items-center gap-1"
        >
          ← Back
        </button>

        {/* Error display -- quiz submit errors are shown inline by QuizRunner
            itself instead of duplicated here. */}
        {(weeklyReview.error || weeklyQuiz.error || weeklyWriting.error) && (
          <div className="mb-4 p-4 bg-danger-tint border border-danger-border rounded-lg text-danger-text">
            {weeklyReview.error || weeklyQuiz.error || weeklyWriting.error}
          </div>
        )}

        {/* Step indicator -- only shown during the quiz/writing wizard
            steps, so the user knows how far through the flow they are. */}
        <StepIndicator step={step} />

        {/* Quiz Step */}
        {step === 'quiz' && (
          <div>
            <h2 className="text-xl font-semibold text-ink mb-4">
              Weekly Quiz - {weeklyReview.reviewState.weekStart} to {weeklyReview.reviewState.weekEnd}
            </h2>
            {quizQuestions.length > 0 ? (
              <QuizRunner
                questions={quizQuestions}
                onSubmitAll={handleQuizSubmit}
                submitting={quizSubmitting}
                submitError={quizSubmitError}
              />
            ) : (
              <div className="bg-surface rounded-lg shadow p-6 mb-4">
                <p className="text-ink-muted mb-4">
                  Complete your weekly quiz to assess your progress.
                </p>
                <button
                  onClick={handleStartQuiz}
                  disabled={weeklyQuiz.loading || quizQuestionsLoading}
                  className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover"
                >
                  {weeklyQuiz.loading || quizQuestionsLoading ? 'Starting...' : 'Start Quiz'}
                </button>
              </div>
            )}
          </div>
        )}

        {/* Writing Step */}
        {step === 'writing' && (
          <div>
            <h2 className="text-xl font-semibold text-ink mb-4">Weekly Writing</h2>
            <div className="bg-surface rounded-lg shadow p-6 mb-4">
              {!weeklyWriting.writingState.promptId ? (
                <button
                  onClick={handleStartWriting}
                  disabled={weeklyWriting.loading}
                  className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover"
                >
                  {weeklyWriting.loading ? 'Loading...' : 'Get Writing Prompt'}
                </button>
              ) : (
                <div>
                  <div className="mb-4 p-4 bg-accent-tint border border-accent/30 rounded-lg">
                    <h3 className="font-medium text-ink mb-2">Topic</h3>
                    <p className="text-ink">{weeklyWriting.writingState.promptTopic}</p>
                  </div>

                  {!weeklyWriting.writingState.evaluation && (
                    <WritingEditor
                      onSubmit={handleSubmitWriting}
                      disabled={weeklyWriting.loading}
                      placeholder="Write your response here..."
                      minLength={50}
                    />
                  )}

                  {weeklyWriting.writingState.evaluation && (
                    <div>
                      {/* Reuses the same EvaluationFeedback component chat's
                          writing widget uses, instead of a hand-rolled score
                          grid that could drift from it. */}
                      <div className="mb-4">
                        <EvaluationFeedback evaluation={weeklyWriting.writingState.evaluation} />
                      </div>
                      <button
                        onClick={handleFinalize}
                        disabled={weeklyWriting.loading}
                        className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover"
                      >
                        {weeklyWriting.loading ? 'Finalizing...' : 'Generate Report'}
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Complete Step */}
        {step === 'complete' && currentReport && (
          <div>
            <h2 className="text-xl font-semibold text-ink mb-4">Weekly Review Complete!</h2>
            <div className="bg-surface rounded-lg shadow p-6">
              <p className="text-ink-muted mb-4">
                Your weekly report has been generated. View it in the archive below.
              </p>
              <button
                onClick={handleBack}
                className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover"
              >
                View All Reports
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}