import { Check, FlipHorizontal2, FlipVertical2, RotateCcw, RotateCcwSquare, RotateCwSquare, X } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { ApiError, imageUrls } from '../../api/client'
import { previewGeometry } from '../../api/queries'
import type { Geometry, GeometryChange as FullChange, Photo } from '../../api/types'
import { Button, Select, Spinner } from '../../components/ui'
import { fitInside, useElementSize } from '../../hooks/useElementSize'
import { cn } from '../../lib/cn'
import { dragCrop, parseRatio, swapRatio, turnedSize, type Handle } from './cropMath'

type GeometryChange = Partial<FullChange>

const ASPECTS = ['1:1', '4:5', '5:4', '2:3', '3:2', '16:9', '9:16']
const HANDLES: Handle[] = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']

const HANDLE_POSITION: Record<Exclude<Handle, 'move'>, string> = {
  nw: 'left-0 top-0 cursor-nwse-resize',
  n: 'left-1/2 top-0 cursor-ns-resize',
  ne: 'left-full top-0 cursor-nesw-resize',
  e: 'left-full top-1/2 cursor-ew-resize',
  se: 'left-full top-full cursor-nwse-resize',
  s: 'left-1/2 top-full cursor-ns-resize',
  sw: 'left-0 top-full cursor-nesw-resize',
  w: 'left-0 top-1/2 cursor-ew-resize',
}

function errorText(e: unknown): string {
  if (e instanceof ApiError && typeof e.detail === 'string') return e.detail
  return e instanceof Error ? e.message : 'The change was refused'
}

/**
 * The crop tool: the whole photo, turned and straightened on screen, with the crop rectangle on it.
 *
 * It edits a draft. Turning, flipping, straightening and the aspect lock go to core (which shrinks the crop to
 * fit the straightened photo); dragging the rectangle is checked locally with the same rule so it stops at the
 * edge. Done checks the draft with core once more and hands it back; nothing is saved here.
 */
export function CropTool({
  photo,
  geometry,
  onDone,
  onCancel,
}: {
  photo: Photo
  geometry: Geometry
  onDone: (geometry: Geometry) => void
  onCancel: () => void
}) {
  const [draft, setDraft] = useState<Geometry>(geometry)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  // The last draft core accepted: a refused change goes back to it.
  const accepted = useRef<Geometry>(geometry)
  const boxRef = useRef<HTMLDivElement>(null)
  const box = useElementSize(boxRef)
  const [frameW, frameH] = turnedSize(photo.width, photo.height, draft.rotate)
  const frame = fitInside(box, frameW / frameH)

  // Changes go to core one at a time; while one is out, only the newest waits (a straighten drag sends many).
  const inFlight = useRef(false)
  const waiting = useRef<GeometryChange | null>(null)
  const latest = useRef(draft)
  useEffect(() => {
    latest.current = draft
  })
  const send = useCallback(
    async (change: GeometryChange) => {
      if (inFlight.current) {
        waiting.current = { ...waiting.current, ...change }
        return
      }
      inFlight.current = true
      setBusy(true)
      let next: GeometryChange | null = change
      while (next) {
        waiting.current = null
        try {
          // From the crop as dragged since (core shrinks or checks it), with everything else as accepted.
          const result = await previewGeometry(photo.id, { ...accepted.current, crop: latest.current.crop }, next)
          accepted.current = result
          setError(null)
          // A newer change is waiting: keep showing the user's latest values until it comes back.
          if (!waiting.current) setDraft(result)
        } catch (e) {
          setError(errorText(e))
          if (!waiting.current) setDraft(accepted.current)
        }
        next = waiting.current
      }
      inFlight.current = false
      setBusy(false)
    },
    [photo.id],
  )

  const change = (c: GeometryChange) => {
    // Show the user's values at once; core's answer (with the crop fitted) replaces them.
    setDraft((d) => ({ ...d, ...(c as Partial<Geometry>), crop: d.crop }))
    void send(c)
  }

  const finish = useCallback(async () => {
    setBusy(true)
    try {
      // The crop may have been dragged since core last saw it: check it once more.
      const checked = await previewGeometry(photo.id, accepted.current, { crop: latest.current.crop })
      onDone(checked)
    } catch (e) {
      setError(errorText(e))
      setDraft(accepted.current)
    } finally {
      setBusy(false)
    }
  }, [photo.id, onDone])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if (target?.closest('input, select, textarea')) return
      if (e.key === 'Enter') {
        e.preventDefault()
        void finish()
      } else if (e.key === 'Escape') {
        e.preventDefault()
        onCancel()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [finish, onCancel])

  const startDrag = (handle: Handle) => (e: ReactMouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!frame.width || !frame.height) return
    const start = draft.crop
    const origin = { x: e.clientX, y: e.clientY }
    const ratio = parseRatio(draft.aspect)
    setDragging(true)
    const onMove = (m: MouseEvent) => {
      const dx = (m.clientX - origin.x) / frame.width
      const dy = (m.clientY - origin.y) / frame.height
      const crop = dragCrop(start, handle, dx, dy, ratio, draft.angle, frameW, frameH)
      setDraft((d) => ({ ...d, crop }))
    }
    const onUp = () => {
      setDragging(false)
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  // The photo as shot, sized for the frame and turned on screen: flip first, then the turn and the angle
  // (CSS applies the transform functions right to left).
  const turned = draft.rotate % 180 !== 0
  const imageW = turned ? frame.height : frame.width
  const imageH = turned ? frame.width : frame.height
  const transform =
    `translate(-50%, -50%) rotate(${draft.rotate + draft.angle}deg) ` +
    `scale(${draft.flip_horizontal ? -1 : 1}, ${draft.flip_vertical ? -1 : 1})`
  const crop = draft.crop
  const original = `${frameW}:${frameH}`
  const aspectValue = draft.aspect === null ? 'free' : ASPECTS.includes(draft.aspect) ? draft.aspect : 'original'

  return (
    <div className="flex h-full flex-col gap-2" data-testid="crop-tool">
      <div role="toolbar" aria-label="Crop" className="flex flex-wrap items-center gap-2 text-xs">
        <label className="flex items-center gap-1">
          <span className="text-muted">Aspect</span>
          <Select
            aria-label="Aspect ratio"
            value={aspectValue}
            onChange={(e) => {
              const value = e.target.value
              change({ aspect: value === 'free' ? null : value === 'original' ? original : value })
            }}
            className="h-7 text-xs"
          >
            <option value="free">Free</option>
            <option value="original">Original</option>
            {ASPECTS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </Select>
        </label>
        <Button
          size="sm"
          variant="ghost"
          disabled={draft.aspect === null}
          title="Swap portrait / landscape"
          onClick={() => draft.aspect && change({ aspect: swapRatio(draft.aspect) })}
        >
          Swap
        </Button>
        <label className="flex items-center gap-1">
          <span className="text-muted">Straighten</span>
          <input
            type="range"
            aria-label="Straighten"
            min={-45}
            max={45}
            step={0.1}
            value={draft.angle}
            onChange={(e) => change({ angle: Number(e.target.value) })}
            onDoubleClick={() => change({ angle: 0 })}
            className="w-32 accent-accent"
          />
          <input
            type="number"
            aria-label="Straighten angle"
            min={-45}
            max={45}
            step={0.1}
            value={Math.round(draft.angle * 10) / 10}
            onChange={(e) => {
              const value = Number(e.target.value)
              if (e.target.value !== '' && value >= -45 && value <= 45) change({ angle: value })
            }}
            className="h-7 w-14 rounded border border-line bg-bg px-1 text-xs"
          />
          <span className="text-muted">°</span>
        </label>
        <Button size="sm" variant="ghost" aria-label="Rotate left" title="Rotate left" onClick={() => change({ rotate: ((draft.rotate + 270) % 360) as Geometry['rotate'] })}>
          <RotateCcwSquare className="size-4" aria-hidden />
        </Button>
        <Button size="sm" variant="ghost" aria-label="Rotate right" title="Rotate right" onClick={() => change({ rotate: ((draft.rotate + 90) % 360) as Geometry['rotate'] })}>
          <RotateCwSquare className="size-4" aria-hidden />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label="Flip horizontal"
          aria-pressed={draft.flip_horizontal}
          title="Flip horizontal"
          onClick={() => change({ flip_horizontal: !draft.flip_horizontal })}
        >
          <FlipHorizontal2 className="size-4" aria-hidden />
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-label="Flip vertical"
          aria-pressed={draft.flip_vertical}
          title="Flip vertical"
          onClick={() => change({ flip_vertical: !draft.flip_vertical })}
        >
          <FlipVertical2 className="size-4" aria-hidden />
        </Button>
        <Button size="sm" variant="ghost" title="Back to the original framing" onClick={() => change({ reset: true })}>
          <RotateCcw className="size-3.5" aria-hidden /> Reset
        </Button>
        <div className="flex-1" />
        {busy && <Spinner className="size-3.5" label="Checking the crop" />}
        <Button size="sm" variant="ghost" onClick={onCancel} title="Cancel (Esc)">
          <X className="size-3.5" aria-hidden /> Cancel
        </Button>
        <Button size="sm" variant="primary" onClick={() => void finish()} title="Apply the crop (Enter)">
          <Check className="size-3.5" aria-hidden /> Done
        </Button>
      </div>
      {error && (
        <p role="alert" className="text-xs text-err">
          {error}
        </p>
      )}
      <div ref={boxRef} className="checker relative flex min-h-0 flex-1 items-center justify-center overflow-hidden">
        <div
          className="relative overflow-hidden"
          style={frame.width ? { width: frame.width, height: frame.height } : undefined}
          data-testid="crop-frame"
        >
          <img
            src={imageUrls.preview(photo.id, { upright: true, size: 1600, version: photo.image_version })}
            alt={`${photo.filename} (whole photo)`}
            draggable={false}
            className="absolute top-1/2 left-1/2 max-w-none select-none"
            style={{ width: imageW, height: imageH, transform }}
          />
          <div
            className="absolute border border-white/90 shadow-[0_0_0_9999px_rgba(0,0,0,0.6)]"
            style={{
              left: `${crop.left * 100}%`,
              top: `${crop.top * 100}%`,
              width: `${(crop.right - crop.left) * 100}%`,
              height: `${(crop.bottom - crop.top) * 100}%`,
            }}
            data-testid="crop-rect"
          >
            <div aria-label="Move crop" className="absolute inset-0 cursor-move" onMouseDown={startDrag('move')} />
            {dragging &&
              [1, 2].map((i) => (
                <div key={i} className="pointer-events-none">
                  <div className="absolute top-0 bottom-0 w-px bg-white/40" style={{ left: `${(i * 100) / 3}%` }} />
                  <div className="absolute right-0 left-0 h-px bg-white/40" style={{ top: `${(i * 100) / 3}%` }} />
                </div>
              ))}
            {HANDLES.map((h) => (
              <div
                key={h}
                aria-label={`Crop handle ${h}`}
                onMouseDown={startDrag(h as Handle)}
                className={cn(
                  'absolute size-3 -translate-x-1/2 -translate-y-1/2 rounded-sm border border-black/40 bg-white',
                  HANDLE_POSITION[h as Exclude<Handle, 'move'>],
                )}
              />
            ))}
          </div>
        </div>
      </div>
      <p className="text-[11px] text-muted">
        Drag the corners or edges, drag inside to move · Enter applies, Esc cancels · the crop stays inside the
        straightened photo
      </p>
    </div>
  )
}
