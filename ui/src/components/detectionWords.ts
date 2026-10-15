import type { FoundCandidate, SubjectKind, SubjectSource } from '../api/types'

/** Words for what detection found. */
export const KIND_NAMES: Record<SubjectKind, string> = {
  car: 'car',
  motorcycle: 'motorcycle',
  aircraft: 'aircraft',
  animal: 'animal',
  person: 'person',
  face: 'face',
  salient: 'stands out',
  af_point: 'focus point',
}

export const percent = (score: number) => `${Math.round(score * 100)} %`

/** A candidate's name: the detector's own ("truck") when it gave one; a guess by what found it. */
export function candidateName(c: Pick<FoundCandidate, 'kind' | 'label' | 'recognized'>): string {
  if (!c.recognized) return c.label === 'sharp' ? 'sharp area' : KIND_NAMES[c.kind]
  return c.label ?? KIND_NAMES[c.kind]
}

/** "truck 84 %". */
export function candidateText(c: Pick<FoundCandidate, 'kind' | 'label' | 'score' | 'recognized'>): string {
  return `${candidateName(c)} ${percent(c.score)}`
}

/** The subject in a few words with its confidence: "car 84 %", "set by hand", "focus point", "no subject". */
export function subjectText(source: SubjectSource, kind: SubjectKind | null, score: number | null): string {
  if (source === 'manual') return 'set by hand'
  if (source === 'af_point') return 'focus point only'
  if (source === 'none' || !kind) return 'no subject'
  return score === null ? KIND_NAMES[kind] : `${KIND_NAMES[kind]} ${percent(score)}`
}
