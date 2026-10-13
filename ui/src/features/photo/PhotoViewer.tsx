import { useRef, useState, type ReactNode } from 'react'
import { imageUrls } from '../../api/client'
import type { Photo } from '../../api/types'
import { Spinner } from '../../components/ui'
import { fitInside, useElementSize } from '../../hooks/useElementSize'
import { ThirdsGrid } from '../../components/ThirdsGrid'
import { cn } from '../../lib/cn'

export type ViewMode = 'after' | 'before' | 'split' | 'camera'

/** Large preview (the edited photo, cropped) with after / before / split-compare modes. A click on the photo
 * calls `onZoomAt` with the point clicked (0..1 of the photo), to zoom in there. */
export function PhotoViewer({
  photo,
  mode,
  grid = false,
  overlay,
  onZoomAt,
}: {
  photo: Photo
  mode: ViewMode
  grid?: boolean
  /** Drawn over the edited photo (not over the camera JPEG, whose frame differs). */
  overlay?: ReactNode
  onZoomAt?: (point: { x: number; y: number }) => void
}) {
  const boxRef = useRef<HTMLDivElement>(null)
  const box = useElementSize(boxRef)
  // The camera JPEG is the whole frame; the renders show the edit's crop and turn.
  const aspect = mode === 'camera' ? photo.width / photo.height : photo.edited_width / photo.edited_height
  const fitted = fitInside(box, aspect)
  const [split, setSplit] = useState(50)
  const after = imageUrls.preview(photo.id, { size: 1600, version: photo.image_version })
  // "Before" keeps the edit's geometry, so it changes with the edit too.
  const before = imageUrls.preview(photo.id, { size: 1600, before: true, version: photo.image_version })
  const shown = mode === 'before' ? before : mode === 'camera' ? imageUrls.sidecar(photo.id, 1600) : after
  // The first preview of a RAW takes a second or two to render; show a spinner until the image arrives.
  const [settled, setSettled] = useState<{ src: string; ok: boolean } | null>(null)

  return (
    <div ref={boxRef} className="checker relative flex h-full w-full items-center justify-center overflow-hidden">
      <div className="relative" style={fitted.width ? { width: fitted.width, height: fitted.height } : undefined}>
        <img
          src={shown}
          alt={`${photo.filename} (${mode === 'split' ? 'after' : mode === 'camera' ? 'camera JPEG' : mode})`}
          draggable={false}
          onLoad={() => setSettled({ src: shown, ok: true })}
          onError={() => setSettled({ src: shown, ok: false })}
          onClick={(e) => {
            if (!onZoomAt || mode === 'camera') return
            const rect = e.currentTarget.getBoundingClientRect()
            if (!rect.width || !rect.height) return onZoomAt({ x: 0.5, y: 0.5 })
            onZoomAt({ x: (e.clientX - rect.left) / rect.width, y: (e.clientY - rect.top) / rect.height })
          }}
          className={cn('block h-full w-full object-contain select-none', onZoomAt && mode !== 'camera' && 'cursor-zoom-in')}
        />
        {grid && <ThirdsGrid />}
        {mode !== 'camera' && overlay}
        {settled?.src !== shown ? (
          settled?.ok ? (
            // An earlier image is still showing: keep it in view and just signal the update in a corner.
            <div className="absolute top-2 right-2 rounded-full bg-black/60 p-1">
              <Spinner className="size-4" label="Rendering preview" />
            </div>
          ) : (
            <div className="absolute inset-0 flex items-center justify-center">
              <Spinner className="size-8" label="Rendering preview" />
            </div>
          )
        ) : (
          !settled.ok && (
            <div role="alert" className="absolute inset-0 flex items-center justify-center text-sm text-muted">
              Preview unavailable (is the original still in its folder?)
            </div>
          )
        )}
        {mode === 'split' && (
          <>
            <img
              src={before}
              alt={`${photo.filename} (before)`}
              draggable={false}
              className="absolute inset-0 block h-full w-full object-contain select-none"
              style={{ clipPath: `inset(0 ${100 - split}% 0 0)` }}
            />
            <div className="pointer-events-none absolute top-0 bottom-0 w-0.5 bg-white shadow" style={{ left: `${split}%` }}>
              <span className="absolute top-2 right-2 rounded bg-black/70 px-1.5 text-[11px] whitespace-nowrap">Before</span>
              <span className="absolute top-2 left-2 rounded bg-black/70 px-1.5 text-[11px] whitespace-nowrap">After</span>
            </div>
            <input
              type="range"
              min={0}
              max={100}
              value={split}
              onChange={(e) => setSplit(Number(e.target.value))}
              aria-label="Before/after split position"
              className="absolute inset-0 h-full w-full cursor-ew-resize opacity-0"
            />
          </>
        )}
      </div>
    </div>
  )
}
