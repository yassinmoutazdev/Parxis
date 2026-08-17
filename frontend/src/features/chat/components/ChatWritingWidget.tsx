import { useState } from 'react'
import WritingPromptCard from '../../writing/components/WritingPromptCard'
import WritingEditor from '../../writing/components/WritingEditor'
import EvaluationFeedback from '../../writing/components/EvaluationFeedback'
import { submitWriting } from '../../../api/client'
import type { WritingPrompt, WritingSubmission, WritingEvaluation } from '../../../api/types'

interface ChatWritingWidgetProps {
  prompt: WritingPrompt
  onComplete: (promptId: number) => void | Promise<void>
}

/**
 * In-chat writing widget: prompt card -> editor -> submit -> evaluation
 * feedback, built from the shared writing components (WritingPromptCard /
 * WritingEditor / EvaluationFeedback) also used by the Reports weekly-review
 * flow, matching the chat quiz widget's reuse-not-duplicate pattern
 * (Work Item B).
 *
 * On submit, POSTs to the existing /api/writing/submissions endpoint, then
 * calls onComplete (the chat thread's /writing/{prompt_id}/complete
 * follow-up), the same pattern handleQuizComplete already follows.
 */
export function ChatWritingWidget({ prompt, onComplete }: ChatWritingWidgetProps) {
  const [submission, setSubmission] = useState<WritingSubmission | null>(null)
  const [evaluation, setEvaluation] = useState<WritingEvaluation | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const isMini = prompt.prompt_type === 'MINI'

  const handleSubmit = async (text: string) => {
    setSubmitting(true)
    setError(null)
    try {
      const result = await submitWriting(prompt.id, text)
      setSubmission(result.submission)
      setEvaluation(result.evaluation)
      await onComplete(prompt.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to submit writing')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="w-full bg-surface rounded-card p-6 space-y-6">
      {!evaluation && <WritingPromptCard prompt={prompt} />}

      {!evaluation ? (
        <WritingEditor
          onSubmit={handleSubmit}
          disabled={submitting}
          placeholder={
            isMini
              ? 'Write 2-3 sentences about the topic...'
              : 'Write your essay on the given topic...'
          }
          minLength={isMini ? 5 : 50}
        />
      ) : (
        <div className="space-y-6">
          {submission && (
            <div className="p-4 bg-cream-100 border border-border rounded-lg">
              <h4 className="font-medium text-ink mb-2">Your Submission</h4>
              <p className="text-ink-muted whitespace-pre-wrap">{submission.submitted_text}</p>
              <p className="text-sm text-ink-faint mt-2">{submission.word_count} words</p>
            </div>
          )}
          <EvaluationFeedback evaluation={evaluation} />
        </div>
      )}

      {error && (
        <div className="p-4 bg-danger-tint border border-danger-border rounded-lg text-danger-text">{error}</div>
      )}
    </div>
  )
}
