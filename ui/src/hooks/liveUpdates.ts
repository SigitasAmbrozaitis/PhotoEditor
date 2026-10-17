/** What a server change event means for the UI (P7.16): which queries to refetch, and how changes Claude
 * made add up to one activity message. Pure, so it's tested without a server. */
import type { QueryKey } from '@tanstack/react-query'
import type { ChangeEvent } from '../api/types'

/** The queries an event makes stale (prefix keys: ['photo'] covers every photo's detail). */
export function invalidationsFor(event: ChangeEvent): QueryKey[] {
  const each = (prefix: string) => event.ids.map((id) => [prefix, id] as QueryKey)
  switch (event.kind) {
    case 'photo_edit':
      // The look, the subject box or the note changed; style counts and export plans follow the photos.
      return [['photos'], ...each('photo'), ...each('subject'), ...each('analysis'), ['styles'], ['export', 'plan']]
    case 'subject':
      return [...each('subject'), ...each('analysis'), ['export', 'plan']]
    case 'style':
      // Every photo using the style renders differently.
      return [['styles'], ...each('style'), ['photos'], ['photo']]
    case 'preset':
      return [['presets']]
    case 'review':
      return event.ids.length ? [['reviews'], ...each('review')] : [['reviews'], ['review'], ['review-settings']]
    case 'job':
      return [['jobs'], ...each('job')]
    case 'library':
      return [['library'], ['photos']]
    case 'resync':
      return [[]] // the empty prefix matches every query
  }
}

/** Distinct keys (by their JSON), so a burst of events refetches each query once. */
export function uniqueKeys(keys: QueryKey[]): QueryKey[] {
  const seen = new Map<string, QueryKey>()
  for (const key of keys) seen.set(JSON.stringify(key), key)
  return [...seen.values()]
}

/** What Claude changed in one burst (events less than ACTIVITY_WINDOW_MS apart). */
export interface Activity {
  /** Changes with each new burst, so its toast shows again. */
  id: number
  photos: string[]
  styles: string[]
  presets: string[]
  reviews: string[]
  lastAt: number
}

export const ACTIVITY_WINDOW_MS = 5000

// Detection results (`subject`) aren't Claude's decisions; a subject Claude sets arrives as a `photo_edit`.
const FIELDS = { photo_edit: 'photos', style: 'styles', preset: 'presets', review: 'reviews' } as const

/** ``previous`` with ``events`` (Claude's) added, or a new burst once the window has passed. */
export function addActivity(previous: Activity | null, events: ChangeEvent[], now: number): Activity | null {
  const relevant = events.filter((e) => e.origin === 'ai' && e.kind in FIELDS)
  if (relevant.length === 0) return previous
  const fresh = previous === null || now - previous.lastAt > ACTIVITY_WINDOW_MS
  const next: Activity = fresh
    ? { id: (previous?.id ?? 0) + 1, photos: [], styles: [], presets: [], reviews: [], lastAt: now }
    : { ...previous, lastAt: now }
  for (const event of relevant) {
    const field = FIELDS[event.kind as keyof typeof FIELDS]
    next[field] = [...new Set([...next[field], ...event.ids])]
  }
  return next
}

export interface ActivityMessage {
  text: string
  link: string | null
}

/** "Claude edited DSCF5437 · changed style Warm film", and where to look. ``name`` finds a display name. */
export function describeActivity(
  activity: Activity,
  name: (kind: 'photo' | 'style' | 'preset', id: string) => string | undefined,
): ActivityMessage {
  const parts: string[] = []
  const { photos, styles, presets, reviews } = activity
  const [photo] = photos
  const [style] = styles
  const [preset] = presets
  const [review] = reviews
  if (photos.length > 1) parts.push(`edited ${photos.length} photos`)
  else if (photo) parts.push(`edited ${name('photo', photo) ?? 'a photo'}`)
  if (styles.length > 1) parts.push(`changed ${styles.length} styles`)
  else if (style) parts.push(`changed style ${name('style', style) ?? style}`)
  if (presets.length > 1) parts.push(`changed ${presets.length} export presets`)
  else if (preset) parts.push(`changed export preset ${name('preset', preset) ?? preset}`)
  if (reviews.length > 1) parts.push(`updated ${reviews.length} reviews`)
  else if (review) parts.push('updated a review')
  const link =
    photos.length > 1
      ? '/library'
      : photo
        ? `/library/${photo}`
        : style
          ? `/styles/${style}`
          : review
            ? `/reviews/${review}`
            : preset
              ? `/presets/${preset}`
              : null
  return { text: `Claude ${parts.join(' · ')}`, link }
}
