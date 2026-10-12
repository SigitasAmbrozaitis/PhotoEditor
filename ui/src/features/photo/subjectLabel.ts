import type { SubjectInfo } from '../../api/types'

const KIND_NAME: Record<string, string> = {
  car: 'car',
  motorcycle: 'motorcycle',
  aircraft: 'aircraft',
  animal: 'animal',
  person: 'person',
  face: 'face',
  salient: 'area that stands out',
  af_point: 'camera focus point',
}

/** "cat (detected)", "set by hand", "camera focus point" or "none". The detector's own name ("cat", "truck")
 * is used when `info` lists the candidates, else the kind ("animal", "car"). */
export function subjectLabel(info: Pick<SubjectInfo, 'source' | 'kind'> & { candidates?: SubjectInfo['candidates'] }): string {
  if (info.source === 'manual') return 'set by hand'
  if (info.source === 'none') return 'none'
  if (info.source === 'af_point') return 'camera focus point'
  const named = info.candidates?.find((c) => c.kind === info.kind)?.label
  const name = named ?? (info.kind ? KIND_NAME[info.kind] ?? info.kind : 'subject')
  return `${name} (detected)`
}
