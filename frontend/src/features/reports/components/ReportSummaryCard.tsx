import type { WeeklyReport, CefrBand } from '../../../api/types'

// CEFR band colors (consistent with ProficiencyCard)
function getCefrColor(band: CefrBand): string {
  if (!band) return '#6B6963'
  const colors: Record<Exclude<CefrBand, null>, string> = {
    'A1': '#8B5CF6',
    'A2': '#3B82F6',
    'B1': '#10B981',
    'B2': '#F59E0B',
    'C1': '#EF4444',
    'C2': '#EC4899',
  }
  return colors[band]
}

interface ReportSummaryCardProps {
  report: WeeklyReport
}

export default function ReportSummaryCard({ report }: ReportSummaryCardProps) {
  const quizSummary = report.quiz_summary_json as {
    total_sessions?: number
    score?: number
  } | null

  const writingSummary = report.mini_writing_summary_json as {
    total_submissions?: number
    average_score?: number
  } | null

  const masterySnapshot = report.mastery_snapshot_json as Record<string, {
    items: number
    average_mastery: number
  }> | null

  return (
    <div className="bg-surface rounded-lg shadow p-6">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h3 className="text-lg font-semibold text-ink">
            Week of {report.week_start} - {report.week_end}
          </h3>
          <p className="text-sm text-ink-muted">
            {report.items_studied_count} items studied
          </p>
        </div>
        <span className="text-sm text-ink-faint">
          {new Date(report.created_at).toLocaleDateString()}
        </span>
      </div>

      {/* CEFR Band (Part B) */}
      {report.weekly_cefr_band && (
        <div className="mb-4 p-3 bg-accent-tint border border-accent/30 rounded-lg">
          <div className="flex items-center gap-3">
            <span
              className="text-2xl font-bold"
              style={{ color: getCefrColor(report.weekly_cefr_band) }}
            >
              {report.weekly_cefr_band}
            </span>
            <div>
              <p className="font-medium text-ink">CEFR Proficiency</p>
              {report.weekly_cefr_justification && (
                <p className="text-sm text-ink-muted">{report.weekly_cefr_justification}</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Quiz Summary */}
      {quizSummary && (
        <div className="mb-4">
          <h4 className="font-medium text-ink mb-2">Quiz Performance</h4>
          <div className="flex gap-4 text-sm">
            <div>
              <span className="text-ink-muted">Sessions: </span>
              <span className="font-medium">{quizSummary.total_sessions || 0}</span>
            </div>
            {quizSummary.score !== null && quizSummary.score !== undefined && (
              <div>
                <span className="text-ink-muted">Score: </span>
                <span className="font-medium">{Math.round(quizSummary.score)}%</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Writing Summary */}
      {writingSummary && (
        <div className="mb-4">
          <h4 className="font-medium text-ink mb-2">Writing Practice</h4>
          <div className="flex gap-4 text-sm">
            <div>
              <span className="text-ink-muted">Submissions: </span>
              <span className="font-medium">{writingSummary.total_submissions || 0}</span>
            </div>
            {writingSummary.average_score !== null && writingSummary.average_score !== undefined && (
              <div>
                <span className="text-ink-muted">Avg Score: </span>
                <span className="font-medium">{Math.round(writingSummary.average_score)}%</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Mastery Snapshot */}
      {masterySnapshot && Object.keys(masterySnapshot).length > 0 && (
        <div className="mb-4">
          <h4 className="font-medium text-ink mb-2">Category Mastery</h4>
          <div className="flex flex-wrap gap-3">
            {Object.entries(masterySnapshot).map(([category, data]) => (
              <div key={category} className="text-sm">
                <span className="text-ink-muted">{category}: </span>
                <span className="font-medium">{Math.round(data.average_mastery * 100)}%</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Narrative */}
      {report.narrative_report && (
        <div>
          <h4 className="font-medium text-ink mb-2">Summary</h4>
          <p className="text-ink-muted text-sm">{report.narrative_report}</p>
        </div>
      )}
    </div>
  )
}