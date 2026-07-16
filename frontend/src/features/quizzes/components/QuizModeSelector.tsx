import { useState } from 'react'
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
    <div className="quiz-mode-selector">
      <h2>Choose Quiz Mode</h2>

      <div className="mode-grid">
        {QUIZ_MODES.map((mode) => (
          <label
            key={mode.value}
            className={`mode-option ${selectedMode === mode.value ? 'selected' : ''}`}
          >
            <input
              type="radio"
              name="quizMode"
              value={mode.value}
              checked={selectedMode === mode.value}
              onChange={() => setSelectedMode(mode.value)}
              disabled={disabled}
            />
            <div className="mode-label">{mode.label}</div>
            <div className="mode-description">{mode.description}</div>
          </label>
        ))}
      </div>

      <div className="size-selector">
        <label>
          Number of Questions:
          <select
            value={size}
            onChange={(e) => setSize(Number(e.target.value))}
            disabled={disabled}
          >
            <option value={5}>5</option>
            <option value={10}>10</option>
            <option value={15}>15</option>
            <option value={20}>20</option>
          </select>
        </label>
      </div>

      <button
        className="start-button"
        onClick={handleStart}
        disabled={disabled}
      >
        Start Quiz
      </button>
    </div>
  )
}