import {
  Check,
  FlipHorizontal2,
  FlipVertical2,
  Grid3x3,
  RotateCcw,
  RotateCcwSquare,
  RotateCwSquare,
  ScanSearch,
  SquareDashedMousePointer,
  Wand2,
  X,
} from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { ApiError, imageUrls } from '../../api/client'
import { previewGeometry, suggestCrop, useSetSubject, useSubject } from '../../api/queries'
import type {
  CropPlacement,
  CropSuggestion,
  Geometry,
  GeometryChange as FullChange,
  Photo,
  SubjectBox,
} from '../../api/types'
import { Button, Select, Spinner } from '../../components/ui'
import { fitInside, useElementSize } from '../../hooks/useElementSize'
import { ThirdsGrid } from '../../components/ThirdsGrid'
import { useGrid } from '../../hooks/useGrid'
import { cn } from '../../lib/cn'
import { subjectLabel } from './subjectLabel'
import { boxBetween, dragCrop, parseRatio, swapRatio, turnedSize, uprightPoint, type Handle } from './cropMath'

type GeometryChange = Partial<FullChange>

const ASPECTS = ['1:1', '4:5', '5:4', '2:3', '3:2', '16:9', '9:16']
const HANDLES: Handle[] = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w']
// Other things found are drawn faintly, at most this many.
const MAX_CANDIDATES = 8
// A box drawn by hand smaller than this (fraction of the photo) is taken as a click, not a subject.
const MIN_SUBJECT = 0.01

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

function boxStyle(box: SubjectBox) {
  return {
    left: `${box.left * 100}%`,
    top: `${box.top * 100}%`,
    width: `${(box.right - box.left) * 100}%`,
    height: `${(box.bottom - box.top) * 100}%`,
  }
}

/**
 * The crop tool: the whole photo, turned and straightened on screen, with the crop rectangle on it.
 *
 * It edits a draft. Turning, flipping, straightening and the aspect lock go to core (which shrinks the crop to
 * fit the straightened photo); dragging the rectangle is checked locally with the same rule so it stops at the
 * edge. Done checks the draft with core once more and hands it back; nothing is saved here.
 *
 * Subjects (P6b.12) are boxes on the upright photo, drawn in the same turned layer as the image so they follow
 * every flip and turn. Setting one by hand is saved at once: it changes no pixels.
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
  const [grid, toggleGrid] = useGrid({ key: true })
  // Subject overlay, drawing a subject by hand, and the last suggestion.
  const [showSubject, setShowSubject] = useState(false)
  const [drawing, setDrawing] = useState(false)
  const [sketch, setSketch] = useState<SubjectBox | null>(null)
  const [placement, setPlacement] = useState<CropPlacement>('centered')
  const [zoom, setZoom] = useState(1)
  const [suggestion, setSuggestion] = useState<CropSuggestion | null>(null)
  const subject = useSubject(photo.id, showSubject || drawing || suggestion !== null)
  const setSubject = useSetSubject(photo.id)
  // The last draft core accepted: a refused change goes back to it.
  const accepted = useRef<Geometry>(geometry)
  const boxRef = useRef<HTMLDivElement>(null)
  const frameRef = useRef<HTMLDivElement>(null)
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
    setSuggestion(null)
    void send(c)
  }

  // Suggestions: the newest request wins, older answers are dropped (the zoom slider sends many).
  const suggestSeq = useRef(0)
  const suggest = async (options: { placement?: CropPlacement; zoom?: number } = {}) => {
    const seq = ++suggestSeq.current
    const current = { ...accepted.current, crop: latest.current.crop }
    const aspect = latest.current.aspect ?? `${frameW}:${frameH}`
    // The ratio as locked in the tool (4:5 stays portrait on a landscape photo; Swap turns it).
    const ratio = parseRatio(aspect) ?? 1
    const orientation = ratio < 1 ? 'portrait' : ratio > 1 ? 'landscape' : 'auto'
    setBusy(true)
    try {
      const result = await suggestCrop(photo.id, {
        geometry: current,
        aspect,
        orientation,
        placement: options.placement ?? placement,
        zoom: options.zoom ?? zoom,
      })
      if (seq !== suggestSeq.current) return
      // Core made it fit the straightened photo: it is the accepted draft now.
      accepted.current = { ...accepted.current, crop: result.crop, aspect: result.aspect }
      setDraft((d) => ({ ...d, crop: result.crop, aspect: result.aspect }))
      setSuggestion(result)
      setError(null)
    } catch (e) {
      if (seq === suggestSeq.current) setError(errorText(e))
    } finally {
      if (seq === suggestSeq.current) setBusy(false)
    }
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
        if (drawing) {
          setDrawing(false)
          setSketch(null)
        } else onCancel()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [finish, onCancel, drawing])

  const startDrag = (handle: Handle) => (e: ReactMouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (!frame.width || !frame.height) return
    const start = draft.crop
    const origin = { x: e.clientX, y: e.clientY }
    const ratio = parseRatio(draft.aspect)
    setDragging(true)
    setSuggestion(null)
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
  const degrees = draft.rotate + draft.angle
  const flips = `scale(${draft.flip_horizontal ? -1 : 1}, ${draft.flip_vertical ? -1 : 1})`
  const transform = `translate(-50%, -50%) rotate(${degrees}deg) ${flips}`
  // Undoes the layer's turn and flips, so labels inside it read upright.
  const upright = `${flips} rotate(${-degrees}deg)`

  // Drawing a subject: from where the mouse went down to where it goes up, in upright coordinates.
  const toUpright = (e: { clientX: number; clientY: number }): [number, number] => {
    const rect = frameRef.current?.getBoundingClientRect()
    if (!rect) return [0.5, 0.5]
    const dx = e.clientX - (rect.left + rect.width / 2)
    const dy = e.clientY - (rect.top + rect.height / 2)
    return uprightPoint(dx, dy, imageW, imageH, degrees, draft.flip_horizontal, draft.flip_vertical)
  }
  const startSketch = (e: ReactMouseEvent) => {
    e.preventDefault()
    e.stopPropagation()
    const start = toUpright(e)
    setSketch(boxBetween(start, start))
    const onMove = (m: MouseEvent) => setSketch(boxBetween(start, toUpright(m)))
    const onUp = (m: MouseEvent) => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      const drawn = boxBetween(start, toUpright(m))
      setSketch(null)
      if (drawn.right - drawn.left < MIN_SUBJECT || drawn.bottom - drawn.top < MIN_SUBJECT) return
      setDrawing(false)
      setShowSubject(true)
      setSuggestion(null)
      setSubject.mutate(drawn, { onError: (err) => setError(errorText(err)) })
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  const info = subject.data
  const crop = draft.crop
  const original = `${frameW}:${frameH}`
  const aspectValue = draft.aspect === null ? 'free' : ASPECTS.includes(draft.aspect) ? draft.aspect : 'original'
  const candidates = (info?.candidates ?? [])
    .filter((c) => !(info?.box && c.box.left === info.box.left && c.box.top === info.box.top && c.box.right === info.box.right))
    .slice(0, MAX_CANDIDATES)

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
      <div role="toolbar" aria-label="Subject" className="flex flex-wrap items-center gap-2 text-xs">
        <Button
          size="sm"
          variant="secondary"
          title="The largest crop of the aspect ratio that keeps the photo's subject"
          onClick={() => void suggest()}
        >
          <Wand2 className="size-3.5" aria-hidden /> Suggest crop
        </Button>
        <label className="flex items-center gap-1">
          <span className="text-muted">Placement</span>
          <Select
            aria-label="Placement"
            value={placement}
            onChange={(e) => {
              const value = e.target.value as CropPlacement
              setPlacement(value)
              if (suggestion) void suggest({ placement: value })
            }}
            className="h-7 text-xs"
          >
            <option value="centered">Centered</option>
            <option value="thirds">On the thirds</option>
          </Select>
        </label>
        <label className="flex items-center gap-1" title="Tighter around the subject; it stops where the subject fills the crop">
          <span className="text-muted">Zoom</span>
          <input
            type="range"
            aria-label="Zoom"
            min={1}
            max={4}
            step={0.05}
            value={zoom}
            onChange={(e) => {
              const value = Number(e.target.value)
              setZoom(value)
              void suggest({ zoom: value })
            }}
            onDoubleClick={() => {
              setZoom(1)
              void suggest({ zoom: 1 })
            }}
            className="w-28 accent-accent"
          />
          <span className="w-10 tabular-nums text-muted">{(suggestion?.zoom ?? zoom).toFixed(2)}×</span>
        </label>
        <span className="mx-1 h-4 w-px bg-line" aria-hidden />
        <Button
          size="sm"
          variant={showSubject ? 'primary' : 'ghost'}
          aria-pressed={showSubject}
          title="Show the photo's subject and the other things found"
          onClick={() => setShowSubject(!showSubject)}
        >
          <ScanSearch className="size-3.5" aria-hidden /> Show subject
        </Button>
        <Button
          size="sm"
          variant={drawing ? 'primary' : 'ghost'}
          aria-pressed={drawing}
          title="Drag a box around the subject (Esc stops)"
          onClick={() => setDrawing(!drawing)}
        >
          <SquareDashedMousePointer className="size-3.5" aria-hidden /> Set subject
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={info?.source !== 'manual'}
          title="Forget the box set by hand and use the detected subject"
          onClick={() => {
            setSuggestion(null)
            setSubject.mutate(null, { onError: (err) => setError(errorText(err)) })
          }}
        >
          Use detected
        </Button>
        <Button
          size="sm"
          variant={grid ? 'primary' : 'ghost'}
          aria-pressed={grid}
          title="3×3 grid to compose by (G)"
          onClick={toggleGrid}
        >
          <Grid3x3 className="size-3.5" aria-hidden /> Grid
        </Button>
        {(showSubject || drawing) && (subject.isFetching || setSubject.isPending) && (
          <span className="flex items-center gap-1 text-muted">
            <Spinner className="size-3.5" label="Finding the subject" />
            Finding the subject (a few seconds the first time)…
          </span>
        )}
        {showSubject && info && !subject.isFetching && (
          <span className="text-muted" data-testid="subject-summary">
            Subject: {subjectLabel(info)}
            {info.score != null && ` · ${Math.round(info.score * 100)} %`}
          </span>
        )}
      </div>
      {suggestion && (
        <p className="text-xs text-muted" data-testid="suggestion">
          {suggestion.aspect} crop, {suggestion.placement === 'thirds' ? 'on the thirds' : 'centered'}, framed on:{' '}
          {subjectLabel({ ...suggestion, candidates: info?.candidates })}
          {suggestion.warnings.map((w) => (
            <span key={w} className="ml-2 text-warn">
              {w}
            </span>
          ))}
        </p>
      )}
      {error && (
        <p role="alert" className="text-xs text-err">
          {error}
        </p>
      )}
      <div ref={boxRef} className="checker relative flex min-h-0 flex-1 items-center justify-center overflow-hidden">
        <div
          ref={frameRef}
          className="relative overflow-hidden"
          style={frame.width ? { width: frame.width, height: frame.height } : undefined}
          data-testid="crop-frame"
        >
          <div className="absolute top-1/2 left-1/2" style={{ width: imageW, height: imageH, transform }} data-testid="upright-layer">
            <img
              src={imageUrls.preview(photo.id, { upright: true, size: 1600, version: photo.image_version })}
              alt={`${photo.filename} (whole photo)`}
              draggable={false}
              className="block h-full w-full max-w-none select-none"
            />
          </div>
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
            {(dragging || grid) && <ThirdsGrid />}
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
          {(showSubject || drawing || sketch) && (
            // Above the dimmed outside of the crop, in the same turned layer as the photo.
            <div
              className="pointer-events-none absolute top-1/2 left-1/2"
              style={{ width: imageW, height: imageH, transform }}
              data-testid="subject-layer"
            >
              {showSubject &&
                candidates.map((c, i) => (
                  <div
                    key={i}
                    className="absolute border border-dashed border-white/50"
                    style={boxStyle(c.box)}
                    data-testid="subject-candidate"
                    title={`${c.label ?? c.kind} ${Math.round(c.score * 100)} %`}
                  />
                ))}
              {showSubject && info?.box && (
                <div className="absolute border-2 border-amber-400" style={boxStyle(info.box)} data-testid="subject-box">
                  <span
                    className="absolute top-0 left-0 origin-top-left rounded-br bg-amber-400 px-1 text-[11px] whitespace-nowrap text-black"
                    style={{ transform: upright }}
                  >
                    {subjectLabel(info)}
                  </span>
                </div>
              )}
              {sketch && <div className="absolute border-2 border-dashed border-amber-300" style={boxStyle(sketch)} />}
            </div>
          )}
          {drawing && (
            <div
              aria-label="Draw the subject"
              className="absolute inset-0 z-10 cursor-crosshair"
              onMouseDown={startSketch}
              data-testid="subject-draw"
            />
          )}
        </div>
      </div>
      <p className="text-[11px] text-muted">
        {drawing
          ? 'Drag a box around the subject · Esc stops'
          : 'Drag the corners or edges, drag inside to move · Enter applies, Esc cancels · G shows the grid · the crop stays inside the straightened photo'}
      </p>
    </div>
  )
}
