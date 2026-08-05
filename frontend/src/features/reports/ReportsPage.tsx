import { useState, useEffect } from 'react'
import {
  useStartWeeklyReview,
  useWeeklyQuiz,
  useWeeklyWriting,
  useWeeklyReports,
} from './hooks'
import ReportSummaryCard from './components/ReportSummaryCard'

type ReviewStep = 'select' | 'quiz' | 'writing' | 'complete'

export default function ReportsPage() {
  const [step, setStep] = useState<ReviewStep>('select')
  const [currentReport, setCurrentReport] = useState<number | null>(null)

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
      await weeklyQuiz.startQuiz()
      // Quiz step complete - move to writing
      setStep('writing')
    } catch (e) {
      console.error('Failed to start quiz:', e)
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
    } else if (step === 'writing') {
      setStep('quiz')
      weeklyQuiz.reset()
    } else if (step === 'complete') {
      setStep('select')
      weeklyReview.reset()
      weeklyQuiz.reset()
      weeklyWriting.reset()
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
              <p className="text-ink-muted">Loading reports...</p>
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

        {/* Error display */}
        {(weeklyReview.error || weeklyQuiz.error || weeklyWriting.error) && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {weeklyReview.error || weeklyQuiz.error || weeklyWriting.error}
          </div>
        )}

        {/* Quiz Step */}
        {step === 'quiz' && (
          <div>
            <h2 className="text-xl font-semibold text-ink mb-4">
              Weekly Quiz - {weeklyReview.reviewState.weekStart} to {weeklyReview.reviewState.weekEnd}
            </h2>
            <div className="bg-surface rounded-lg shadow p-6 mb-4">
              <p className="text-ink-muted mb-4">
                Complete your weekly quiz to assess your progress.
              </p>
              {weeklyQuiz.quizState.questions.length > 0 ? (
                <div className="space-y-4">
                  {weeklyQuiz.quizState.questions.map((q, i) => (
                    <div key={q.id} className="border-b pb-4">
                      <p className="font-medium mb-2">Question {i + 1}</p>
                      <p className="text-ink">{q.prompt}</p>
                    </div>
                  ))}
                  <p className="text-sm text-ink-muted">
                    (Quiz answers would be collected here in a full implementation)
                  </p>
                </div>
              ) : (
                <button
                  onClick={handleStartQuiz}
                  disabled={weeklyQuiz.loading}
                  className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover"
                >
                  {weeklyQuiz.loading ? 'Starting...' : 'Start Quiz'}
                </button>
              )}
            </div>
            {weeklyQuiz.quizState.questions.length > 0 && (
              <button
                onClick={() => setStep('writing')}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
              >
                Continue to Writing →
              </button>
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
                    <div>
                      <textarea
                        className="w-full h-48 p-4 bg-surface text-ink placeholder:text-ink-faint border border-border-strong rounded-lg resize-none"
                        placeholder="Write your response here..."
                      />
                      <button
                        onClick={() => handleSubmitWriting('Sample writing text')}
                        disabled={weeklyWriting.loading}
                        className="mt-2 px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover"
                      >
                        {weeklyWriting.loading ? 'Submitting...' : 'Submit'}
                      </button>
                    </div>
                  )}

                  {weeklyWriting.writingState.evaluation && (
                    <div>
                      <div className="mb-4">
                        <h4 className="font-medium text-ink mb-2">Scores</h4>
                        <div className="grid grid-cols-2 gap-2 text-sm">
                          <div>Grammar: {weeklyWriting.writingState.evaluation.grammar_score}%</div>
                          <div>Naturalness: {weeklyWriting.writingState.evaluation.naturalness_score}%</div>
                          <div>Vocabulary: {weeklyWriting.writingState.evaluation.vocabulary_score}%</div>
                          <div>Coherence: {weeklyWriting.writingState.evaluation.coherence_score}%</div>
                          <div className="col-span-2 font-medium">
                            Overall: {weeklyWriting.writingState.evaluation.overall_score}%
                          </div>
                        </div>
                      </div>
                      <button
                        onClick={handleFinalize}
                        disabled={weeklyWriting.loading}
                        className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
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