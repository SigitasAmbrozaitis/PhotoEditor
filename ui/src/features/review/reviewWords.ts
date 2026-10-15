import type { ExportReview, ExportSettings, ReviewItem, ReviewRule } from '../../api/types'
import { subjectText } from '../../components/detectionWords'

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

/** Whether the review's export frames each photo's subject (else it centers, and subjects don't matter). */
export const framesSubjects = (review: ExportReview) =>
  review.settings.aspect.ratio !== null && review.settings.aspect.anchor === 'subject'

/** The item's subject and confidence in a few words, for its tag. */
export const confidenceText = (item: ReviewItem) => subjectText(item.subject, item.subject_kind, item.subject_score)

/** ``settings`` framed on each photo's subject (on) or on the center (off). Without an aspect ratio nothing is
 * cropped, so there is nothing to frame and the settings stay as they are. */
export function withSubjectFraming(settings: ExportSettings, on: boolean): ExportSettings {
  if (settings.aspect.ratio === null) return settings
  const aspect = on
    ? { ...settings.aspect, anchor: 'subject' as const }
    : { ...settings.aspect, anchor: 'center' as const, zoom: 'off' as const }
  return { ...settings, aspect }
}
