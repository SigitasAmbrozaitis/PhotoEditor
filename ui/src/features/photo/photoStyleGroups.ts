/** Which parameter groups a style can take from a photo, and how many values differ in each. */
import type { AdjustmentGroup, AdjustmentParams } from '../../api/types'

/** In the order of the Adjust panel. White balance and exposure have their own choices (rules). */
export const STYLE_GROUPS: { id: AdjustmentGroup; label: string }[] = [
  { id: 'tone', label: 'Tone' },
  { id: 'presence', label: 'Presence' },
  { id: 'tone_curve', label: 'Tone curve' },
  { id: 'hsl', label: 'HSL / color mixer' },
  { id: 'color_grading', label: 'Color grading' },
  { id: 'detail', label: 'Detail' },
  { id: 'effects', label: 'Effects' },
]

/** Dotted names whose value differs between ``a`` and ``b`` (lists, such as curves, compare as a whole). */
export function differingPaths(a: unknown, b: unknown, prefix = ''): string[] {
  const isObject = (v: unknown): v is Record<string, unknown> =>
    typeof v === 'object' && v !== null && !Array.isArray(v)
  if (isObject(a) && isObject(b)) {
    return Object.keys(b).flatMap((key) => differingPaths(a[key], b[key], `${prefix}${key}.`))
  }
  return JSON.stringify(a) === JSON.stringify(b) ? [] : [prefix.slice(0, -1)]
}

/** Per style group: how many of the photo's values differ from its unedited look (exposure not counted). */
export function changedPerGroup(params: AdjustmentParams, unedited: AdjustmentParams): Record<string, number> {
  const counts: Record<string, number> = {}
  for (const path of differingPaths(unedited, params)) {
    if (path === 'tone.exposure') continue
    const group = path.split('.')[0]!
    counts[group] = (counts[group] ?? 0) + 1
  }
  return counts
}
