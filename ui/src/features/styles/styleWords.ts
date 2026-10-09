/** Words and small helpers for the style screens (kept apart from the components for fast refresh). */
import type { ExposureMetering, StyleRule, WhiteBalanceMode } from '../../api/types'

export const METERING: Record<ExposureMetering, { label: string; hint: string }> = {
  middle: { label: 'Middle', hint: 'Brings the median brightness to the target. For ordinary scenes.' },
  highlights: {
    label: 'Highlights',
    hint: 'Puts the brightest tones at the target, so dark subjects stay dark (a black cat, night streets).',
  },
  camera_settings: {
    label: 'Camera settings',
    hint:
      'Evens out the exposure you dialed in (shutter, aperture, ISO) against the group. For a series in the ' +
      'same light with changing settings; needs "Even out" when applying. Without it, meters like Middle.',
  },
}

export const WB_MODES: Record<WhiteBalanceMode, { label: string; hint: string }> = {
  as_shot: { label: 'As shot + offset', hint: "The camera's white balance, shifted by the offsets." },
  auto: {
    label: 'Auto + offset',
    hint: 'A neutral estimate from the photo, shifted by the offsets. Can remove intentional warm light.',
  },
  fixed: { label: 'Fixed', hint: 'The same Kelvin and tint on every photo (studio light).' },
}

export function describeRule(rule: StyleRule): string {
  if (rule.type === 'exposure') {
    const target = rule.target === null ? 'default target' : `target ${signed(rule.target)} stops`
    const strength = rule.strength === 100 ? '' : `, ${rule.strength} %`
    return `Auto exposure: ${METERING[rule.metering].label.toLowerCase()}, ${target}${strength}, max ±${rule.max_change} EV${
      rule.use_group ? ', uses the group when evened out' : ''
    }`
  }
  if (rule.mode === 'fixed') return `White balance: fixed ${rule.temperature} K, tint ${signed(rule.tint ?? 0)}`
  const base = rule.mode === 'auto' ? 'auto (neutral estimate)' : 'as shot'
  return `White balance: ${base} ${signed(rule.temperature_offset)} K, tint ${signed(rule.tint_offset)}`
}

const signed = (n: number) => (n > 0 ? `+${n}` : String(n))

/** Photos further than this from the set's median middle (in stops) need attention. */
export const OUTLIER_STOPS = 0.5

/** "portraits, golden hour" ⇄ ["portraits", "golden hour"] */
export const listToText = (items: string[]) => items.join(', ')
export const textToList = (text: string) =>
  text
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
