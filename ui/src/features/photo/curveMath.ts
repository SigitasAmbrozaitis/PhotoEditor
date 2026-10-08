/** Tone curve math shared by the editor and its tests (mirrors the backend's PCHIP and point rules). */

export type Point = { x: number; y: number }

/** Same limits as the backend model (points closer than this make the curve's slope explode). */
export const MIN_GAP = 0.01
export const MAX_POINTS = 16

/** Shape-preserving cubic through the points (the same PCHIP the renderer uses), sampled at `xs`. */
export function pchip(points: Point[], xs: number[]): number[] {
  const n = points.length
  const x = points.map((p) => p.x)
  const y = points.map((p) => p.y)
  const h = x.slice(1).map((v, i) => v - x[i]!)
  const d = y.slice(1).map((v, i) => (v - y[i]!) / h[i]!)
  const m = new Array<number>(n).fill(0)
  if (n === 2) m.fill(d[0]!)
  else {
    for (let k = 1; k < n - 1; k++) {
      if (d[k - 1]! * d[k]! > 0) {
        const w1 = 2 * h[k]! + h[k - 1]!
        const w2 = h[k]! + 2 * h[k - 1]!
        m[k] = ((w1 + w2) * d[k - 1]! * d[k]!) / (w1 * d[k]! + w2 * d[k - 1]!)
      }
    }
    const end = (h0: number, h1: number, d0: number, d1: number) => {
      const s = ((2 * h0 + h1) * d0 - h0 * d1) / (h0 + h1)
      if (Math.sign(s) !== Math.sign(d0)) return 0
      if (Math.sign(d0) !== Math.sign(d1) && Math.abs(s) > Math.abs(3 * d0)) return 3 * d0
      return s
    }
    m[0] = end(h[0]!, h[1]!, d[0]!, d[1]!)
    m[n - 1] = end(h[n - 2]!, h[n - 3]!, d[n - 2]!, d[n - 3]!)
  }
  return xs.map((q) => {
    const c = Math.min(Math.max(q, x[0]!), x[n - 1]!)
    let k = 0
    while (k < n - 2 && c > x[k + 1]!) k++
    const t = (c - x[k]!) / h[k]!
    const t2 = t * t
    const t3 = t2 * t
    return (
      (2 * t3 - 3 * t2 + 1) * y[k]! +
      (t3 - 2 * t2 + t) * h[k]! * m[k]! +
      (-2 * t3 + 3 * t2) * y[k + 1]! +
      (t3 - t2) * h[k]! * m[k + 1]!
    )
  })
}

export const SAMPLES = Array.from({ length: 101 }, (_, i) => i / 100)
export const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), hi)

export function polyline(points: Point[]): string {
  return pchip(points, SAMPLES)
    .map((v, i) => `${SAMPLES[i]! * 100},${100 - clamp(v, 0, 1) * 100}`)
    .join(' ')
}

/** Move point `index` to (x, y), keeping it between its neighbours and the ends pinned at x = 0 and 1. */
export function movePoint(points: Point[], index: number, x: number, y: number): Point[] {
  const last = points.length - 1
  const nx = index === 0 ? 0 : index === last ? 1 : clamp(x, points[index - 1]!.x + MIN_GAP, points[index + 1]!.x - MIN_GAP)
  return points.map((p, i) => (i === index ? { x: Math.round(nx * 1000) / 1000, y: Math.round(clamp(y, 0, 1) * 1000) / 1000 } : p))
}

/** Insert a point at (x, y) if there is room for it; null otherwise. */
export function addPoint(points: Point[], x: number, y: number): Point[] | null {
  if (points.length >= MAX_POINTS) return null
  const at = points.findIndex((p) => p.x > x)
  if (at <= 0) return null
  if (x - points[at - 1]!.x < MIN_GAP || points[at]!.x - x < MIN_GAP) return null
  const point = { x: Math.round(x * 1000) / 1000, y: Math.round(clamp(y, 0, 1) * 1000) / 1000 }
  return [...points.slice(0, at), point, ...points.slice(at)]
}
