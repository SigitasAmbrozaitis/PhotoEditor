/**
 * Interaction math for the crop tool: dragging the crop rectangle inside the straightened photo.
 *
 * Coordinates are normalized to the frame (the photo after flips and the quarter turn), as in core's geometry.
 * The "inside" test mirrors `core/geometry.py` so a drag stops at the photo's edge; core stays the authority
 * (every change is checked again there before it is saved).
 */
import type { CropRect } from '../../api/types'

export type Handle = 'move' | 'n' | 's' | 'e' | 'w' | 'ne' | 'nw' | 'se' | 'sw'

export const MIN_CROP = 0.012 // a little above core's 1 % minimum
const TOLERANCE = 1e-7

/** The frame's size after the quarter turn. */
export function turnedSize(width: number, height: number, rotate: number): [number, number] {
  return rotate % 180 === 0 ? [width, height] : [height, width]
}

/** True when `crop` lies inside the photo straightened by `angle` (degrees, clockwise) in a width × height frame. */
export function cropInside(crop: CropRect, angle: number, width: number, height: number): boolean {
  const a = (-angle * Math.PI) / 180
  const cos = Math.cos(a)
  const sin = Math.sin(a)
  const corners: [number, number][] = [
    [crop.left, crop.top],
    [crop.right, crop.top],
    [crop.right, crop.bottom],
    [crop.left, crop.bottom],
  ]
  return corners.every(([nx, ny]) => {
    const x = nx * width - width / 2
    const y = ny * height - height / 2
    // Turned back by the angle, every corner must land inside the frame.
    const bx = cos * x - sin * y
    const by = sin * x + cos * y
    return Math.abs(bx) <= width / 2 + TOLERANCE * width && Math.abs(by) <= height / 2 + TOLERANCE * height
  })
}

function valid(crop: CropRect, angle: number, width: number, height: number): boolean {
  return (
    crop.left >= 0 &&
    crop.top >= 0 &&
    crop.right <= 1 &&
    crop.bottom <= 1 &&
    crop.right - crop.left >= MIN_CROP &&
    crop.bottom - crop.top >= MIN_CROP &&
    cropInside(crop, angle, width, height)
  )
}

/** The crop after moving `handle` by (dx, dy) (normalized), before any limit. `ratio` = width ÷ height in pixels. */
function moved(start: CropRect, handle: Handle, dx: number, dy: number, ratio: number | null, width: number, height: number): CropRect {
  if (handle === 'move') {
    return { left: start.left + dx, right: start.right + dx, top: start.top + dy, bottom: start.bottom + dy }
  }
  let { left, top, right, bottom } = start
  if (handle.includes('w')) left += dx
  if (handle.includes('e')) right += dx
  if (handle.includes('n')) top += dy
  if (handle.includes('s')) bottom += dy
  if (ratio === null) return { left, top, right, bottom }
  // Height ÷ width in normalized units for this pixel ratio.
  const perWidth = width / (ratio * height)
  if (handle === 'n' || handle === 's') {
    // An edge drag keeps the crop centered on the other axis.
    const w = (bottom - top) / perWidth
    const cx = (start.left + start.right) / 2
    return { left: cx - w / 2, right: cx + w / 2, top, bottom }
  }
  if (handle === 'e' || handle === 'w') {
    const h = (right - left) * perWidth
    const cy = (start.top + start.bottom) / 2
    return { left, right, top: cy - h / 2, bottom: cy + h / 2 }
  }
  // A corner drag follows the width; the opposite corner stays put.
  const h = (right - left) * perWidth
  return handle.includes('n') ? { left, right, top: bottom - h, bottom } : { left, right, top, bottom: top + h }
}

/**
 * The crop while dragging `handle` from `start` by (dx, dy). If the full move would leave the straightened photo
 * (or make the crop too small), it goes as far as it can in that direction.
 */
export function dragCrop(
  start: CropRect,
  handle: Handle,
  dx: number,
  dy: number,
  ratio: number | null,
  angle: number,
  width: number,
  height: number,
): CropRect {
  const farthest = (from: CropRect, mx: number, my: number): CropRect => {
    const at = (t: number) => moved(from, handle, mx * t, my * t, ratio, width, height)
    if (valid(at(1), angle, width, height)) return at(1)
    let low = 0
    let high = 1
    for (let i = 0; i < 24; i++) {
      const middle = (low + high) / 2
      if (valid(at(middle), angle, width, height)) low = middle
      else high = middle
    }
    return low === 0 ? from : at(low)
  }
  const whole = moved(start, handle, dx, dy, ratio, width, height)
  if (valid(whole, angle, width, height)) return whole
  // A move slides along the edge it hits: as far as it can across, then as far as it can down.
  return handle === 'move' ? farthest(farthest(start, dx, 0), 0, dy) : farthest(start, dx, dy)
}

/** '4:5' → 0.8; null for a free crop. */
export function parseRatio(aspect: string | null): number | null {
  if (!aspect) return null
  const [w, h] = aspect.split(':').map(Number)
  return w && h ? w / h : null
}

/** '4:5' → '5:4'. */
export function swapRatio(aspect: string): string {
  const [w, h] = aspect.split(':')
  return `${h}:${w}`
}

/**
 * A point on screen, as an offset (px) from the frame's center, in upright photo coordinates (0..1, clamped).
 *
 * The crop tool draws the upright photo `imageW` × `imageH` px around the frame's center, flipped and then
 * turned by `degrees` clockwise (the quarter turn plus the straighten angle); this undoes that.
 */
export function uprightPoint(
  dx: number,
  dy: number,
  imageW: number,
  imageH: number,
  degrees: number,
  flipH: boolean,
  flipV: boolean,
): [number, number] {
  const a = (-degrees * Math.PI) / 180
  let x = dx * Math.cos(a) - dy * Math.sin(a)
  let y = dx * Math.sin(a) + dy * Math.cos(a)
  if (flipH) x = -x
  if (flipV) y = -y
  const clamp = (v: number) => Math.min(1, Math.max(0, v))
  return [clamp(x / imageW + 0.5), clamp(y / imageH + 0.5)]
}

/** The box spanned by two upright points (left, top, right, bottom). */
export function boxBetween(a: [number, number], b: [number, number]) {
  return {
    left: Math.min(a[0], b[0]),
    top: Math.min(a[1], b[1]),
    right: Math.max(a[0], b[0]),
    bottom: Math.max(a[1], b[1]),
  }
}
