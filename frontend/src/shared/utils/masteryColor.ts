// Single warm color ramp for mastery/score display, used everywhere a score
// is rendered — badges, chart bars, big numbers. A continuous decaying score
// isn't pass/fail, so it shouldn't read as red/yellow/green.
// (see docs/Praxis_PRD_v1.0.md, "Score displays use consistent color
// semantics ... a single mastery/score gradient")
//
// Dark theme: pill backgrounds are dark tinted fills, text is the light
// stop of the same hue family (inverse of a light-mode ramp).

export const MASTERY_RAMP = [
  { bg: '#332D24', text: '#B7A87C', hex: '#8A7A4A' }, // low
  { bg: '#402A20', text: '#D99E7A', hex: '#B3703F' }, // mid
  { bg: '#4A2A1C', text: '#F0997B', hex: '#E0825A' }, // high
]

/** fraction is a 0-1 score. */
export function masteryStop(fraction: number) {
  const index = Math.min(MASTERY_RAMP.length - 1, Math.floor(Math.max(0, fraction) * MASTERY_RAMP.length))
  return MASTERY_RAMP[index]
}
