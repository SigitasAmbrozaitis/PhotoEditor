import { describe, expect, it } from 'vitest'
import { boxBetween, cropInside, dragCrop, parseRatio, swapRatio, turnedSize, uprightPoint } from './cropMath'

const W = 6240
const H = 4160
const full = { left: 0, top: 0, right: 1, bottom: 1 }

describe('crop math', () => {
  it('turns the frame for quarter turns', () => {
    expect(turnedSize(W, H, 0)).toEqual([W, H])
    expect(turnedSize(W, H, 90)).toEqual([H, W])
    expect(turnedSize(W, H, 270)).toEqual([H, W])
  })

  it('matches core: the full frame fits only without an angle', () => {
    expect(cropInside(full, 0, W, H)).toBe(true)
    expect(cropInside(full, 0.1, W, H)).toBe(false)
    // core's largest_crop(None, 10, 6240, 4160): a centered crop of the frame's ratio, 0.8030 of it.
    const k = 0.803
    const largest = { left: 0.5 - k / 2, right: 0.5 + k / 2, top: 0.5 - k / 2, bottom: 0.5 + k / 2 }
    expect(cropInside(largest, 10, W, H)).toBe(true)
    const grown = { ...largest, left: largest.left - 0.002, right: largest.right + 0.002 }
    expect(cropInside(grown, 10, W, H)).toBe(false)
  })

  it('moves the crop and stops at the edge', () => {
    const crop = { left: 0.2, top: 0.2, right: 0.6, bottom: 0.6 }
    expect(dragCrop(crop, 'move', 0.1, 0.05, null, 0, W, H)).toEqual({ left: 0.30000000000000004, top: 0.25, right: 0.7, bottom: 0.65 })
    const pushed = dragCrop(crop, 'move', -0.5, 0, null, 0, W, H)
    expect(pushed.left).toBeCloseTo(0, 5)
    expect(pushed.right - pushed.left).toBeCloseTo(0.4)
  })

  it('slides along an edge when a move goes past it', () => {
    const crop = { left: 0, top: 0.2, right: 0.4, bottom: 0.6 }
    const slid = dragCrop(crop, 'move', -0.1, 0.1, null, 0, W, H)
    expect(slid.left).toBe(0)
    expect(slid.top).toBeCloseTo(0.3)
  })

  it('resizes from a corner and keeps a locked ratio', () => {
    const crop = { left: 0.2, top: 0.1, right: 0.5, bottom: 0.55 } // 1872 × 1872 px: 1:1
    const out = dragCrop(crop, 'se', 0.1, 0, 1, 0, W, H)
    expect(out.left).toBe(0.2)
    expect(out.top).toBe(0.1)
    expect(((out.right - out.left) * W) / ((out.bottom - out.top) * H)).toBeCloseTo(1)
    expect(out.right).toBeCloseTo(0.6)
  })

  it('never makes the crop too small or turns it inside out', () => {
    const crop = { left: 0.2, top: 0.2, right: 0.3, bottom: 0.3 }
    const out = dragCrop(crop, 'e', -0.5, 0, null, 0, W, H)
    expect(out.right - out.left).toBeGreaterThanOrEqual(0.012)
  })

  it('stops at the straightened photo edge', () => {
    const crop = { left: 0.3, top: 0.3, right: 0.7, bottom: 0.7 }
    const out = dragCrop(crop, 'nw', -0.3, -0.3, null, 8, W, H)
    expect(cropInside(out, 8, W, H)).toBe(true)
    expect(out.left).toBeLessThan(0.3)
    expect(out.left).toBeGreaterThan(0)
  })

  it('parses and swaps ratios', () => {
    expect(parseRatio('4:5')).toBe(0.8)
    expect(parseRatio(null)).toBeNull()
    expect(swapRatio('4:5')).toBe('5:4')
  })
})

describe('screen to upright', () => {
  // A 600 × 400 px upright image drawn around the frame's center.
  const at = (dx: number, dy: number, degrees: number, flipH = false, flipV = false) =>
    uprightPoint(dx, dy, 600, 400, degrees, flipH, flipV).map((v) => Math.round(v * 1000) / 1000)

  it('maps straight, turned and flipped drawings back', () => {
    expect(at(0, 0, 0)).toEqual([0.5, 0.5])
    expect(at(150, -100, 0)).toEqual([0.75, 0.25])
    // Turned 90° clockwise: what is right on screen was at the top of the upright photo.
    expect(at(100, 0, 90)).toEqual([0.5, 0.25])
    expect(at(0, 150, 90)).toEqual([0.75, 0.5])
    expect(at(0, 150, 270)).toEqual([0.25, 0.5])
    expect(at(150, -100, 180)).toEqual([0.25, 0.75])
    expect(at(150, -100, 0, true)).toEqual([0.25, 0.25])
    expect(at(150, -100, 0, false, true)).toEqual([0.75, 0.75])
  })

  it('clamps points off the photo and spans boxes either way', () => {
    expect(at(1000, -1000, 0)).toEqual([1, 0])
    expect(boxBetween([0.7, 0.2], [0.3, 0.6])).toEqual({ left: 0.3, top: 0.2, right: 0.7, bottom: 0.6 })
  })
})
