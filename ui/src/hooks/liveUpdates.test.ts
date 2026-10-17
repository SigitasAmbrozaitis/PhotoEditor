import { describe, expect, it } from 'vitest'
import type { ChangeEvent } from '../api/types'
import { ACTIVITY_WINDOW_MS, addActivity, describeActivity, invalidationsFor, uniqueKeys } from './liveUpdates'

let seq = 0
function event(kind: ChangeEvent['kind'], ids: string[] = [], origin: ChangeEvent['origin'] = 'ai'): ChangeEvent {
  return { seq: ++seq, kind, ids, origin, summary: null }
}

describe('invalidationsFor', () => {
  it('refetches what each kind of change touches', () => {
    expect(invalidationsFor(event('photo_edit', ['p1']))).toEqual([
      ['photos'],
      ['photo', 'p1'],
      ['subject', 'p1'],
      ['analysis', 'p1'],
      ['styles'],
      ['export', 'plan'],
    ])
    expect(invalidationsFor(event('style', ['warm']))).toEqual([['styles'], ['style', 'warm'], ['photos'], ['photo']])
    expect(invalidationsFor(event('preset', ['mine']))).toEqual([['presets']])
    expect(invalidationsFor(event('review', ['r1']))).toEqual([['reviews'], ['review', 'r1']])
    expect(invalidationsFor(event('review'))).toEqual([['reviews'], ['review'], ['review-settings']])
    expect(invalidationsFor(event('job', ['j0001']))).toEqual([['jobs'], ['job', 'j0001']])
    expect(invalidationsFor(event('library', ['C:/Photos']))).toEqual([['library'], ['photos']])
    expect(invalidationsFor(event('subject', ['p2']))).toEqual([['subject', 'p2'], ['analysis', 'p2'], ['export', 'plan']])
    expect(invalidationsFor(event('resync'))).toEqual([[]])
  })

  it('refetches each query once per burst', () => {
    const keys = [event('photo_edit', ['p1']), event('photo_edit', ['p2']), event('photo_edit', ['p1'])].flatMap(
      invalidationsFor,
    )
    const unique = uniqueKeys(keys)
    expect(unique.filter((k) => k[0] === 'photos')).toHaveLength(1)
    expect(unique.filter((k) => k[0] === 'photo')).toEqual([['photo', 'p1'], ['photo', 'p2']])
  })
})

describe('activity', () => {
  it("collects only Claude's changes and starts a new burst after a pause", () => {
    expect(addActivity(null, [event('photo_edit', ['p1'], 'ui'), event('job', ['j1'])], 1000)).toBeNull()
    const first = addActivity(null, [event('photo_edit', ['p1']), event('photo_edit', ['p2', 'p1'])], 1000)
    expect(first).toMatchObject({ id: 1, photos: ['p1', 'p2'], lastAt: 1000 })
    const same = addActivity(first, [event('style', ['warm'])], 1000 + ACTIVITY_WINDOW_MS)
    expect(same).toMatchObject({ id: 1, photos: ['p1', 'p2'], styles: ['warm'] })
    const next = addActivity(same, [event('preset', ['mine'])], 2000 + 2 * ACTIVITY_WINDOW_MS)
    expect(next).toMatchObject({ id: 2, photos: [], styles: [], presets: ['mine'] })
    // Detection isn't Claude's decision.
    expect(addActivity(null, [event('subject', ['p1'])], 1000)).toBeNull()
  })

  it('says what changed and where to look', () => {
    const table: Record<string, string> = { 'photo:p1': 'DSCF5437.RAF', 'style:warm': 'Warm film' }
    const names = (kind: string, id: string) => table[`${kind}:${id}`]
    const base = { id: 1, photos: [], styles: [], presets: [], reviews: [], lastAt: 0 }
    expect(describeActivity({ ...base, photos: ['p1'] }, names)).toEqual({
      text: 'Claude edited DSCF5437.RAF',
      link: '/library/p1',
    })
    expect(describeActivity({ ...base, photos: ['p1', 'p2'], styles: ['warm'] }, names)).toEqual({
      text: 'Claude edited 2 photos · changed style Warm film',
      link: '/library',
    })
    expect(describeActivity({ ...base, photos: ['p9'] }, names).text).toBe('Claude edited a photo')
    expect(describeActivity({ ...base, reviews: ['r1'], presets: ['mine'] }, names)).toEqual({
      text: 'Claude changed export preset mine · updated a review',
      link: '/reviews/r1',
    })
  })
})
