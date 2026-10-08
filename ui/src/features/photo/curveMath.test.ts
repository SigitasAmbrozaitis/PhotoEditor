import { describe, expect, it } from 'vitest'
import { addPoint, MAX_POINTS, MIN_GAP, movePoint, pchip } from './curveMath'

const line = [
  { x: 0, y: 0 },
  { x: 1, y: 1 },
]

describe('tone curve math', () => {
  it('matches the backend PCHIP on a reference curve', () => {
    // Values from photoedit.core.render.curves.pchip (checked against SciPy) for the same points.
    const points = [
      { x: 0, y: 0 },
      { x: 0.3, y: 0.2 },
      { x: 0.5, y: 0.7 },
      { x: 1, y: 1 },
    ]
    const values = pchip(points, [0, 0.15, 0.3, 0.4, 0.5, 0.75, 1])
    expect(values[0]).toBeCloseTo(0, 9)
    expect(values[2]).toBeCloseTo(0.2, 9)
    expect(values[4]).toBeCloseTo(0.7, 9)
    expect(values[6]).toBeCloseTo(1, 9)
    // Monotone points give a monotone curve with no overshoot.
    const dense = pchip(points, Array.from({ length: 201 }, (_, i) => i / 200))
    for (let i = 1; i < dense.length; i++) expect(dense[i]!).toBeGreaterThanOrEqual(dense[i - 1]! - 1e-12)
    expect(Math.max(...dense)).toBeLessThanOrEqual(1 + 1e-12)
  })

  it('is a straight line through two points and flat beyond the ends', () => {
    expect(pchip(line, [-0.5, 0.25, 1.5])).toEqual([0, 0.25, 1])
  })

  it('pins the end points at x = 0 and 1 and keeps the minimum gap', () => {
    const three = [line[0]!, { x: 0.5, y: 0.5 }, line[1]!]
    expect(movePoint(three, 0, 0.3, 0.2)[0]).toEqual({ x: 0, y: 0.2 })
    expect(movePoint(three, 2, 0.4, 1.4)[2]).toEqual({ x: 1, y: 1 })
    expect(movePoint(three, 1, 0, 0.5)[1]!.x).toBe(MIN_GAP)
    expect(movePoint(three, 1, 1, 0.5)[1]!.x).toBe(1 - MIN_GAP)
  })

  it('adds points only where there is room', () => {
    expect(addPoint(line, 0.5, 0.6)).toEqual([line[0], { x: 0.5, y: 0.6 }, line[1]])
    expect(addPoint(line, 0.005, 0.1)).toBeNull()
    const full = Array.from({ length: MAX_POINTS }, (_, i) => ({ x: i / (MAX_POINTS - 1), y: 0.5 }))
    expect(addPoint(full, 0.53, 0.5)).toBeNull()
  })
})
