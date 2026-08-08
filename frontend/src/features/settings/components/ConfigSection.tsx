import { useEffect, useMemo, useState } from 'react'
import { Card, CardHeader, CardContent } from '../../../shared/components/Card'
import { LoadingSpinner } from '../../../shared/components/LoadingSpinner'
import { useConfig, useSetConfig } from '../hooks'

// Each preset is a bundle of the underlying scheduler/mastery knobs. The user
// only ever sees three named stops on a slider - the raw keys stay internal.
const PRESETS = [
  {
    label: 'Forgive faster',
    blurb: "Reviews things less often and is more lenient about what counts as 'correct'.",
    values: {
      decay_rate: 0.004,
      correct_threshold: 0.6,
      ease_factor_increment: 0.15,
      ease_factor_decrement: 0.1,
      ease_factor_max: 3.0,
      ease_factor_min: 1.3,
      mastery_bonus: 0.2,
      mastery_penalty: 0.15,
      category_balance_ratio: 0.5,
    },
  },
  {
    label: 'Standard',
    blurb: 'A balanced pace - the default for most learners.',
    values: {
      decay_rate: 0.0077,
      correct_threshold: 0.7,
      ease_factor_increment: 0.1,
      ease_factor_decrement: 0.2,
      ease_factor_max: 3.0,
      ease_factor_min: 1.3,
      mastery_bonus: 0.15,
      mastery_penalty: 0.25,
      category_balance_ratio: 0.6,
    },
  },
  {
    label: 'Drill harder',
    blurb: 'Re-quizzes you sooner and grades stricter, so items need more repetition to feel mastered.',
    values: {
      decay_rate: 0.014,
      correct_threshold: 0.8,
      ease_factor_increment: 0.07,
      ease_factor_decrement: 0.3,
      ease_factor_max: 2.6,
      ease_factor_min: 1.3,
      mastery_bonus: 0.1,
      mastery_penalty: 0.35,
      category_balance_ratio: 0.7,
    },
  },
] as const

type ConfigKey = keyof (typeof PRESETS)[number]['values']
const CONFIG_KEYS = Object.keys(PRESETS[1].values) as ConfigKey[]

function closestPresetIndex(config: Record<string, { value: unknown }>): number {
  let bestIdx = 1
  let bestDist = Infinity
  PRESETS.forEach((preset, idx) => {
    const decay = config['decay_rate']?.value
    if (typeof decay !== 'number') return
    const dist = Math.abs(decay - preset.values.decay_rate)
    if (dist < bestDist) {
      bestDist = dist
      bestIdx = idx
    }
  })
  return bestIdx
}

export function ConfigSection() {
  const { data: config, isLoading, error } = useConfig()
  const setConfigMutation = useSetConfig()

  const [selected, setSelected] = useState(1)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    if (config) setSelected(closestPresetIndex(config))
  }, [config])

  const currentIdx = useMemo(() => (config ? closestPresetIndex(config) : 1), [config])
  const isDirty = selected !== currentIdx

  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-12">
          <LoadingSpinner />
        </CardContent>
      </Card>
    )
  }

  if (error || !config) {
    return (
      <Card>
        <CardContent>
          <p className="text-sm text-red-400">Failed to load configuration.</p>
        </CardContent>
      </Card>
    )
  }

  async function applyPreset() {
    const preset = PRESETS[selected]
    for (const key of CONFIG_KEYS) {
      await setConfigMutation.mutateAsync({ key, value: preset.values[key] })
    }
    setSaved(true)
    setTimeout(() => setSaved(false), 1500)
  }

  return (
    <Card>
      <CardHeader>
        <h2 className="font-serif text-lg text-ink">Review pace</h2>
        <p className="text-sm text-ink-muted mt-1">
          How often Praxis brings things back for review, and how strict it is about
          grading.
        </p>
      </CardHeader>
      <CardContent>
        <div className="px-2">
          <input
            type="range"
            min={0}
            max={2}
            step={1}
            value={selected}
            onChange={(e) => setSelected(Number(e.target.value))}
            className="w-full accent-accent"
            aria-label="Review pace"
          />
          <div className="flex justify-between text-xs text-ink-muted mt-1">
            {PRESETS.map((p, idx) => (
              <span
                key={p.label}
                className={idx === selected ? 'text-ink font-medium' : undefined}
              >
                {p.label}
              </span>
            ))}
          </div>
        </div>

        <p className="text-sm text-ink-muted mt-4">{PRESETS[selected].blurb}</p>

        {isDirty && (
          <div className="mt-4 flex items-center gap-3">
            <button
              onClick={applyPreset}
              disabled={setConfigMutation.isPending}
              className="text-sm bg-accent text-white rounded-lg px-4 py-1.5 hover:opacity-90 disabled:opacity-50"
            >
              {setConfigMutation.isPending ? 'Saving…' : saved ? 'Saved' : 'Apply'}
            </button>
            <button
              onClick={() => setSelected(currentIdx)}
              className="text-sm text-ink-muted hover:text-ink"
            >
              Cancel
            </button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}