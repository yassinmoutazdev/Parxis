import { useState } from 'react'
import { useMiniTask, useWeeklyAssessment } from './hooks'
import WritingPromptCard from './components/WritingPromptCard'
import WritingEditor from './components/WritingEditor'
import EvaluationFeedback from './components/EvaluationFeedback'

type WritingMode = 'select' | 'mini' | 'weekly'

export default function WritingPage() {
  const [mode, setMode] = useState<WritingMode>('select')

  // Use the appropriate hook based on mode
  const miniTask = useMiniTask()
  const weeklyAssessment = useWeeklyAssessment()

  const isMini = mode === 'mini'
  const activeHook = isMini ? miniTask : weeklyAssessment
  const currentPrompt = activeHook.prompt
  const currentSubmission = activeHook.submission
  const currentEvaluation = activeHook.evaluation
  const loading = activeHook.loading
  const error = activeHook.error

  const handleStart = async (selectedMode: 'mini' | 'weekly') => {
    setMode(selectedMode)
    if (selectedMode === 'mini') {
      await miniTask.startMiniTask()
    } else {
      await weeklyAssessment.startWeeklyAssessment()
    }
  }

  const handleSubmit = async (text: string) => {
    if (!currentPrompt) return

    if (isMini) {
      await miniTask.submitMiniTask(currentPrompt.id, text)
    } else {
      await weeklyAssessment.submitWeeklyAssessment(currentPrompt.id, text)
    }
  }

  const handleRetry = async () => {
    if (!currentSubmission) return
    await activeHook.retryEvaluation(currentSubmission.id)
  }

  const handleBack = () => {
    setMode('select')
    activeHook.reset()
  }

  // Selection screen
  if (mode === 'select') {
    return (
      <div className="px-4 py-6 sm:px-0">
        <div className="max-w-2xl mx-auto">
          <h1 className="font-serif text-2xl text-ink mb-6">Writing Practice</h1>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Mini Writing Card */}
            <button
              onClick={() => handleStart('mini')}
              className="p-6 text-left bg-surface border-2 border-border rounded-lg hover:border-accent hover:shadow-md transition-all"
            >
              <h3 className="text-lg font-semibold text-ink mb-2">
                Mini Writing
              </h3>
              <p className="text-ink-muted mb-4">
                Practice writing 2-3 sentences on a given topic. Get quick
                feedback on grammar and naturalness.
              </p>
              <div className="flex items-center text-sm text-ink-muted">
                <span className="inline-flex items-center px-2 py-1 bg-accent-tint text-accent-text rounded">
                  ~2-3 sentences
                </span>
              </div>
            </button>

            {/* Weekly Writing Card */}
            <button
              onClick={() => handleStart('weekly')}
              className="p-6 text-left bg-surface border-2 border-border rounded-lg hover:border-accent hover:shadow-md transition-all"
            >
              <h3 className="text-lg font-semibold text-ink mb-2">
                Weekly Assessment
              </h3>
              <p className="text-ink-muted mb-4">
                Write a longer essay on a generated topic. Receive detailed
                feedback across 5 dimensions.
              </p>
              <div className="flex items-center text-sm text-ink-muted">
                <span className="inline-flex items-center px-2 py-1 bg-green-100 text-green-700 rounded">
                  1-2 paragraphs
                </span>
              </div>
            </button>
          </div>
        </div>
      </div>
    )
  }

  // Writing in progress or completed
  return (
    <div className="px-4 py-6 sm:px-0">
      <div className="max-w-3xl mx-auto">
        {/* Back button */}
        <button
          onClick={handleBack}
          className="mb-4 text-ink-muted hover:text-ink flex items-center gap-1"
        >
          ← Back to Writing Options
        </button>

        {/* Error display */}
        {error && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
            {error}
            {!currentEvaluation && currentSubmission && (
              <button
                onClick={handleRetry}
                className="ml-2 underline"
                disabled={loading}
              >
                Retry evaluation
              </button>
            )}
          </div>
        )}

        {/* Prompt */}
        {currentPrompt && !currentEvaluation && (
          <div className="mb-6">
            <WritingPromptCard prompt={currentPrompt} />
          </div>
        )}

        {/* Editor or Feedback */}
        {!currentEvaluation ? (
          <WritingEditor
            onSubmit={handleSubmit}
            disabled={loading}
            placeholder={
              isMini
                ? 'Write 2-3 sentences about the topic...'
                : 'Write your essay on the given topic...'
            }
            minLength={isMini ? 5 : 50}
          />
        ) : (
          <div className="space-y-6">
            {/* Submission text for reference */}
            {currentSubmission && (
              <div className="p-4 bg-cream-100 border border-border rounded-lg">
                <h4 className="font-medium text-ink mb-2">Your Submission</h4>
                <p className="text-ink-muted whitespace-pre-wrap">
                  {currentSubmission.submitted_text}
                </p>
                <p className="text-sm text-ink-faint mt-2">
                  {currentSubmission.word_count} words
                </p>
              </div>
            )}

            {/* Evaluation */}
            <EvaluationFeedback evaluation={currentEvaluation} />

            {/* Retry button if needed */}
            <div className="flex justify-center">
              <button
                onClick={handleRetry}
                disabled={loading}
                className="px-4 py-2 text-ink-muted hover:text-ink"
              >
                {loading ? 'Retrying...' : 'Retry Evaluation'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}