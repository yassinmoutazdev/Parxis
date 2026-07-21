import { useState } from 'react'
import { Button } from '../../../shared/components/Button'
import type { QuizMode } from '../../../api/types'

interface QuizModeSelectorProps {
  onSelectMode: (mode: QuizMode, size: number) => void
  disabled?: boolean
}

const QUIZ_MODES: { value: QuizMode; label: string; description: string }[] = [
  { value: 'RECALL', label: 'Recall', description: 'Remember the meaning' },
  { value: 'FILL_BLANK', label: 'Fill in the Blank', description: 'Complete the sentence' },
  { value: 'MULTIPLE_CHOICE', label: 'Multiple Choice', description: 'Choose the correct answer' },
  { value: 'ERROR_CORRECTION', label: 'Error Correction', description: 'Find and fix the error' },
  { value: 'REWRITE_NATURALLY', label: 'Rewrite Naturally', description: 'Make it sound natural' },
  { value: 'CONVERSATION', label: 'Conversation', description: 'Use in a dialogue' },
  { value: 'MINI_ESSAY', label: 'Mini Essay', description: 'Write about a topic' },
  { value: 'RANDOM', label: 'Random Mix', description: 'Mix of all modes' },
]

export function QuizModeSelector({ onSelectMode, disabled }: QuizModeSelectorProps) {
  const [selectedMode, setSelectedMode] = useState<QuizMode>('RECALL')
  const [size, setSize] = useState(10)

  const handleStart = () => {
    onSelectMode(selectedMode, size)
  }

  return (
    <div className="quiz-mode-selector space-y-6">
      <h2 className="text-2xl font-semibold text-ink">Choose Quiz Mode</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {QUIZ_MODES.map((mode) => (
          <button
            key={mode.value}
            type="button"
            onClick={() => setSelectedMode(mode.value)}
            disabled={disabled}
            className={`
              text-left p-4 rounded-card border transition-all
              ${selectedMode === mode.value
                ? 'bg-accent-tint border-accent text-ink'
                : 'bg-surface border-border hover:border-border-strong text-ink'}
            `}
          >
            <div className="font-medium">{mode.label}</div>
            <div className="text-sm text-ink-muted mt-1">{mode.description}</div>
          </button>
        ))}
      </div>

      <div className="flex items-center gap-4">
        <label className="text-ink-muted">
          Number of Questions:
          <select
            value={size}
            onChange={(e) => setSize(Number(e.target.value))}
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
        onClick={handleStart}
        disabled={disabled}
        size="lg"
      >
        Start Quiz
      </Button>
    </div>
  )
}