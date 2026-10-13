import type { ReviewItem, ReviewRule } from '../../api/types'

/** Short chip labels for the review rules (the reason's text says the rest). */
export const RULE_LABELS: Record<ReviewRule, string> = {
  no_subject: 'No subject',
  uncertain: 'Uncertain',
  ambiguous: 'Two candidates',
  cut_off: 'Cut off',
  zoom_limit: 'Zoom limit',
  changed: 'Changed',
  unusable: "Can't export",
}

/** Check first (the decisions left), then Ready, then what can't be exported: the order of the screen. */
export function reviewGroups(items: ReviewItem[]) {
  return {
    check: items.filter((i) => i.status === 'check'),
    ready: items.filter((i) => i.status === 'ready'),
    unusable: items.filter((i) => i.status === 'unusable'),
  }
}

export function reviewOrder(items: ReviewItem[]): ReviewItem[] {
  const { check, ready, unusable } = reviewGroups(items)
  return [...check, ...ready, ...unusable]
}

/** Zoom as shown: "1.54×". */
export const zoomText = (zoom: number) => `${zoom.toFixed(2)}×`

/** True when the photo's export needs the full decode because of its zoom (past the fast limit). */
export const needsFullDecode = (item: ReviewItem) => item.decode === 'full' && item.zoom > item.limits.fast + 1e-6
