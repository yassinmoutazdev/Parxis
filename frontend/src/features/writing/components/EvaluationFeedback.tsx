import type { WritingEvaluation } from '../../../api/types'

interface MiniCorrection {
  wrong: string
  correct: string
  explanation: string
}

interface EvaluationFeedbackProps {
  evaluation: WritingEvaluation
}

export default function EvaluationFeedback({
  evaluation,
}: EvaluationFeedbackProps) {
  const isMini = !evaluation.grammar_score // Mini tasks don't have 5 dimension scores

  if (isMini) {
    return <MiniFeedback evaluation={evaluation} />
  }

  return <WeeklyFeedback evaluation={evaluation} />
}

function MiniFeedback({
  evaluation,
}: {
  evaluation: WritingEvaluation
}) {
  const feedback = evaluation.feedback_json as
    | { corrections: MiniCorrection[]; naturalness_notes: string[] }
    | null
    | undefined

  const corrections = feedback?.corrections || []
  const naturalnessNotes = feedback?.naturalness_notes || []

  // Calculate overall score based on corrections
  const score = evaluation.overall_score
    ? Math.round(evaluation.overall_score * 100)
    : null

  return (
    <div className="space-y-6">
      {/* Score */}
      {score !== null && (
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold">Mini Writing Evaluation</h3>
          <span className="text-2xl font-bold text-accent-text">{score}%</span>
        </div>
      )}

      {/* Corrections */}
      {corrections.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium text-ink">Corrections</h4>
          {corrections.map((correction, index) => (
            <div
              key={index}
              className="p-4 bg-red-50 border border-red-200 rounded-lg"
            >
              <div className="flex items-start gap-2">
                <span className="line-through text-red-600 font-medium">
                  {correction.wrong}
                </span>
                <span className="text-ink-faint">→</span>
                <span className="text-green-600 font-medium">
                  {correction.correct}
                </span>
              </div>
              {correction.explanation && (
                <p className="mt-2 text-sm text-ink-muted">
                  {correction.explanation}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Naturalness Notes */}
      {naturalnessNotes.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium text-ink">Naturalness Notes</h4>
          <ul className="space-y-2">
            {naturalnessNotes.map((note, index) => (
              <li
                key={index}
                className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-ink"
              >
                {note}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* No corrections message */}
      {corrections.length === 0 && naturalnessNotes.length === 0 && (
        <p className="text-ink-muted">No corrections or notes for this submission.</p>
      )}
    </div>
  )
}

function WeeklyFeedback({ evaluation }: { evaluation: WritingEvaluation }) {
  const feedback = evaluation.feedback_json as
    | {
        grammar: string
        naturalness: string
        vocabulary: string
        coherence: string
        overall: string
      }
    | null
    | undefined

  const dimensions: { key: string; label: string; score: number | null; feedback: string }[] = [
    { key: 'grammar', label: 'Grammar', score: evaluation.grammar_score, feedback: feedback?.grammar || '' },
    { key: 'naturalness', label: 'Naturalness', score: evaluation.naturalness_score, feedback: feedback?.naturalness || '' },
    { key: 'vocabulary', label: 'Vocabulary', score: evaluation.vocabulary_score, feedback: feedback?.vocabulary || '' },
    { key: 'coherence', label: 'Coherence', score: evaluation.coherence_score, feedback: feedback?.coherence || '' },
    { key: 'overall', label: 'Overall', score: evaluation.overall_score, feedback: feedback?.overall || '' },
  ]

  const getScoreColor = (score: number | null) => {
    if (score === null) return 'text-ink-faint'
    if (score >= 80) return 'text-green-600'
    if (score >= 60) return 'text-yellow-600'
    return 'text-red-600'
  }

  const getScoreBgColor = (score: number | null) => {
    if (score === null) return 'bg-cream-100'
    if (score >= 80) return 'bg-green-100'
    if (score >= 60) return 'bg-yellow-100'
    return 'bg-red-100'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Weekly Writing Evaluation</h3>
        {evaluation.overall_score !== null && (
          <span className="text-3xl font-bold text-accent-text">
            {Math.round(evaluation.overall_score)}%
          </span>
        )}
      </div>

      {/* Dimension Scores */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {dimensions.map((dim) => (
          <div
            key={dim.key}
            className={`p-4 rounded-lg ${getScoreBgColor(dim.score)}`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium text-ink">{dim.label}</span>
              <span className={`text-xl font-bold ${getScoreColor(dim.score)}`}>
                {dim.score !== null ? Math.round(dim.score) : '—'}
              </span>
            </div>
            {dim.feedback && (
              <p className="text-sm text-ink-muted">{dim.feedback}</p>
            )}
          </div>
        ))}
      </div>

      {/* Suggested Items */}
      {evaluation.suggested_items_json && evaluation.suggested_items_json.length > 0 && (
        <div className="space-y-3">
          <h4 className="font-medium text-ink">Suggested Learning Items</h4>
          <p className="text-sm text-ink-muted">
            Review these items in the Approvals page to add them to your learning
            collection.
          </p>
        </div>
      )}
    </div>
  )
}