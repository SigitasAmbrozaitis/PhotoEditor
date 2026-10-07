import { useRef, useState } from 'react'
import { imageUrls } from '../../api/client'
import type { Photo } from '../../api/types'
import { Spinner } from '../../components/ui'
import { fitInside, useElementSize } from '../../hooks/useElementSize'

export type ViewMode = 'after' | 'before' | 'split'

interface Crop {
  left: number
  top: number
  right: number
  bottom: number
}

function CropOverlay({ crop }: { crop: Crop }) {
  const style = {
    left: `${crop.left * 100}%`,
    top: `${crop.top * 100}%`,
    width: `${(crop.right - crop.left) * 100}%`,
    height: `${(crop.bottom - crop.top) * 100}%`,
  }
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" data-testid="crop-overlay">
      <div className="absolute border border-white/80 shadow-[0_0_0_9999px_rgba(0,0,0,0.55)]" style={style}>
        {[1, 2].map((i) => (
          <div key={`v${i}`} className="absolute top-0 bottom-0 w-px bg-white/30" style={{ left: `${(i * 100) / 3}%` }} />
        ))}
        {[1, 2].map((i) => (
          <div key={`h${i}`} className="absolute right-0 left-0 h-px bg-white/30" style={{ top: `${(i * 100) / 3}%` }} />
        ))}
      </div>
    </div>
  )
}

/** Large preview with after / before / split-compare modes and an optional crop overlay. */
export function PhotoViewer({ photo, mode, crop }: { photo: Photo; mode: ViewMode; crop?: Crop | null }) {
  const boxRef = useRef<HTMLDivElement>(null)
  const box = useElementSize(boxRef)
  const fitted = fitInside(box, photo.width / photo.height)
  const [split, setSplit] = useState(50)
  const after = imageUrls.preview(photo.id, { size: 1600 })
  const before = imageUrls.preview(photo.id, { size: 1600, before: true })
  const shown = mode === 'before' ? before : after
  // The first preview of a RAW takes a second or two to render; show a spinner until the image arrives.
  const [settled, setSettled] = useState<{ src: string; ok: boolean } | null>(null)

  return (
    <div ref={boxRef} className="checker relative flex h-full w-full items-center justify-center overflow-hidden">
      <div className="relative" style={fitted.width ? { width: fitted.width, height: fitted.height } : undefined}>
        <img
          src={shown}
          alt={`${photo.filename} (${mode === 'before' ? 'before' : 'after'})`}
          draggable={false}
          onLoad={() => setSettled({ src: shown, ok: true })}
          onError={() => setSettled({ src: shown, ok: false })}
          className="block h-full w-full object-contain select-none"
        />
        {settled?.src !== shown ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <Spinner className="size-8" label="Rendering preview" />
          </div>
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
        {crop && <CropOverlay crop={crop} />}
      </div>
    </div>
  )
}
