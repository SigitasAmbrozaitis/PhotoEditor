import { useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { imageUrls } from '../../api/client'
import { useZoomInfo } from '../../api/queries'
import type { Photo, ZoomLevel } from '../../api/types'
import { Spinner } from '../../components/ui'
import { useElementSize } from '../../hooks/useElementSize'
import type { ViewMode } from './PhotoViewer'
import { centeredOn, clampOffset, visibleTiles, type Point } from './zoomMath'

/**
 * The zoom view: the edited photo at 50 % or 100 % in tiles rendered by the backend (exact pipeline, the edit's
 * own sharpening). 100 % needs the full decode the first time (up to ~25 s); meanwhile the 50 % tiles are shown
 * enlarged. Drag to pan; a click without dragging goes back to fit.
 */
export function ZoomView({
  photo,
  level,
  mode,
  focus,
  onExit,
}: {
  photo: Photo
  level: ZoomLevel
  mode: ViewMode
  /** The point (0..1 of the edited photo) to center on when the view opens. */
  focus: Point
  onExit: () => void
}) {
  const wanted = useZoomInfo(photo.id, level, photo.image_version)
  // At 100 %, ask for 50 % too: it is quick and stands in until the full decode is done.
  const interim = useZoomInfo(photo.id, level === 100 ? 50 : null, photo.image_version)
  const ready = wanted.data?.state === 'ready' ? wanted.data : interim.data?.state === 'ready' ? interim.data : null
  const shownLevel = ready?.level ?? null
  const scale = shownLevel ? level / shownLevel : 1
  const size = ready?.width && ready.height ? { width: ready.width * scale, height: ready.height * scale } : null

  const viewRef = useRef<HTMLDivElement>(null)
  const viewport = useElementSize(viewRef)
  // Where the user panned to; until then the view is centered on the focus point.
  const [panned, setPanned] = useState<Point | null>(null)
  const [split, setSplit] = useState(50)
  const offset = size && viewport.width ? clampOffset(panned ?? centeredOn(focus, size, viewport), size, viewport) : null

  const startPan = (e: ReactMouseEvent) => {
    if (!size || !offset) return
    e.preventDefault()
    const origin = { x: e.clientX, y: e.clientY, offset }
    let moved = false
    const onMove = (m: MouseEvent) => {
      if (Math.abs(m.clientX - origin.x) + Math.abs(m.clientY - origin.y) > 3) moved = true
      setPanned(clampOffset({ x: origin.offset.x - (m.clientX - origin.x), y: origin.offset.y - (m.clientY - origin.y) }, size, viewport))
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      if (!moved) onExit()
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  const layer = (before: boolean) =>
    ready && offset
      ? visibleTiles({ width: ready.width!, height: ready.height!, tileSize: ready.tile_size, scale }, offset, viewport).map((t) => (
          <img
            key={`${before ? 'b' : 'a'}${shownLevel}-${t.tx}-${t.ty}`}
            src={imageUrls.tile(photo.id, shownLevel!, t.tx, t.ty, { before, version: photo.image_version })}
            alt=""
            draggable={false}
            className="absolute max-w-none select-none"
            style={{ left: t.left, top: t.top, width: t.width, height: t.height, imageRendering: scale > 1 ? 'pixelated' : undefined }}
          />
        ))
      : null

  const error = wanted.error ?? interim.error
  return (
    <div
      ref={viewRef}
      className="checker relative h-full w-full cursor-grab overflow-hidden active:cursor-grabbing"
      onMouseDown={startPan}
      data-testid="zoom-view"
      aria-label={`${photo.filename} at ${level} %`}
    >
      <div className="absolute inset-0" style={mode === 'split' ? { clipPath: `inset(0 0 0 ${split}%)` } : undefined}>
        {layer(mode === 'before')}
      </div>
      {mode === 'split' && (
        <>
          <div className="absolute inset-0" style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}>
            {layer(true)}
          </div>
          <div className="pointer-events-none absolute top-0 bottom-0 w-0.5 bg-white shadow" style={{ left: `${split}%` }} />
          <input
            type="range"
            min={0}
            max={100}
            value={split}
            onChange={(e) => setSplit(Number(e.target.value))}
            onMouseDown={(e) => e.stopPropagation()}
            aria-label="Before/after split position"
            className="absolute right-4 bottom-3 left-4 accent-accent"
          />
        </>
      )}
      {error ? (
        <div role="alert" className="absolute inset-0 flex items-center justify-center text-sm text-muted">
          Zoom view unavailable: {error.message}
        </div>
      ) : (
        shownLevel !== level && (
          <div className="absolute top-2 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full bg-black/70 px-3 py-1 text-xs">
            <Spinner className="size-3.5" label="Loading full size" />
            {level === 100 ? 'Loading full size… (up to ~25 s the first time)' : 'Loading…'}
          </div>
        )
      )}
      {size && offset && <Navigator photo={photo} size={size} offset={offset} viewport={viewport} />}
    </div>
  )
}

/** A small picture of the whole photo with the part in view outlined. */
function Navigator({
  photo,
  size,
  offset,
  viewport,
}: {
  photo: Photo
  size: { width: number; height: number }
  offset: Point
  viewport: { width: number; height: number }
}) {
  // Fits a 140 px square, so a portrait photo doesn't cover the view.
  const width = size.width >= size.height ? 140 : (140 * size.width) / size.height
  const height = (width * size.height) / size.width
  const k = width / size.width
  return (
    <div className="pointer-events-none absolute right-3 bottom-3 border border-white/40 bg-black/60" style={{ width, height }} data-testid="zoom-navigator">
      <img src={imageUrls.thumbnail(photo.id, photo.image_version)} alt="" className="h-full w-full object-contain" />
      <div
        className="absolute border border-accent"
        style={{
          left: Math.max(0, offset.x * k),
          top: Math.max(0, offset.y * k),
          width: Math.min(width, viewport.width * k),
          height: Math.min(height, viewport.height * k),
        }}
      />
    </div>
  )
}
