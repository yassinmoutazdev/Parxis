import { useState } from 'react'
import { Button } from '../../../shared/components/Button'

type PlusTab = 'quiz' | 'writing'
type WritingChoiceMode = 'mini' | 'weekly'

interface ComposerPlusMenuProps {
  onClose: () => void
  onStartQuiz: (size: number) => void
  onStartWriting: (mode: WritingChoiceMode) => void
  disabled?: boolean
}

/**
 * Popover opened by the composer's "+" button (Work Item D). Lets the
 * learner trigger a quiz or writing session directly, bypassing the LLM
 * entirely -- a second entry point into the same start_quiz_action /
 * start_writing_action backend code paths the LLM tool-call already uses.
 */
export function ComposerPlusMenu({
  onClose,
  onStartQuiz,
  onStartWriting,
  disabled,
}: ComposerPlusMenuProps) {
  const [tab, setTab] = useState<PlusTab>('quiz')
  const [writingChoice, setWritingChoice] = useState<WritingChoiceMode>('mini')
  const [quizSize, setQuizSize] = useState(10)

  return (
    <div className="absolute bottom-full left-0 mb-2 w-[min(90vw,640px)] max-h-[70vh] overflow-y-auto bg-surface border border-border rounded-card shadow-lg p-4 z-20">
      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-border">
        <button
          type="button"
          onClick={() => setTab('quiz')}
          className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            tab === 'quiz'
              ? 'border-accent text-ink'
              : 'border-transparent text-ink-muted hover:text-ink'
          }`}
        >
          Quiz
        </button>
        <button
          type="button"
          onClick={() => setTab('writing')}
          className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
            tab === 'writing'
              ? 'border-accent text-ink'
              : 'border-transparent text-ink-muted hover:text-ink'
          }`}
        >
          Writing
        </button>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close"
          className="ml-auto text-ink-muted hover:text-ink px-2"
        >
          ✕
        </button>
      </div>

      {tab === 'quiz' ? (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-ink">Start Quiz</h2>
          <p className="text-sm text-ink-muted">
            Multiple choice questions to test your knowledge.
          </p>
          <div className="flex items-center gap-4">
            <label className="text-ink-muted">
              Number of Questions:
              <select
                value={quizSize}
                onChange={(e) => setQuizSize(Number(e.target.value))}
                disabled={disabled}
                className="ml-2 px-3 py-1.5 bg-surface border border-border rounded-lg text-ink focus:border-accent focus:outline-none"
              >
                <option value={5}>5</option>
                <option value={10}>10</option>
                <option value={15}>15</option>
                <option value={20}>20</option>
              </select>
            </label>
          </div>
          <Button
            onClick={() => {
              onStartQuiz(quizSize)
              onClose()
            }}
            disabled={disabled}
            size="lg"
            className="w-full"
          >
            Start Quiz
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-ink">Choose Writing Type</h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <button
              type="button"
              onClick={() => setWritingChoice('mini')}
              disabled={disabled}
              className={`text-left p-4 rounded-card border transition-all ${
                writingChoice === 'mini'
                  ? 'bg-accent-tint border-accent text-ink'
                  : 'bg-surface border-border hover:border-border-strong text-ink'
              }`}
            >
              <div className="font-medium">Quick Prompt</div>
              <div className="text-sm text-ink-muted mt-1">2-3 sentences, quick feedback</div>
            </button>

            <button
              type="button"
              onClick={() => setWritingChoice('weekly')}
              disabled={disabled}
              className={`text-left p-4 rounded-card border transition-all ${
                writingChoice === 'weekly'
                  ? 'bg-accent-tint border-accent text-ink'
                  : 'bg-surface border-border hover:border-border-strong text-ink'
              }`}
            >
              <div className="font-medium">Topic Prompt</div>
              <div className="text-sm text-ink-muted mt-1">Auto-generated topic, longer essay</div>
            </button>
          </div>

          <button
            type="button"
            onClick={() => {
              onStartWriting(writingChoice)
              onClose()
            }}
            disabled={disabled}
            className="px-6 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover disabled:bg-border-strong disabled:cursor-not-allowed transition-colors w-full"
          >
            Start Writing
          </button>
        </div>
      )}
    </div>
  )
}