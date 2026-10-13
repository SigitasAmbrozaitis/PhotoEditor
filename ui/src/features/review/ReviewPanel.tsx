import { Check, ChevronLeft, ChevronRight, Crosshair, Eye, EyeOff, SquareDashedMousePointer } from 'lucide-react'
import { useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { imageUrls } from '../../api/client'
import { useReviewFrames, useSetReviewSubject, useUpdateReviewItem } from '../../api/queries'
import type { CropRect, ExportReview, FramePosition, ReviewItem, SubjectBox } from '../../api/types'
import { DetectionOverlay } from '../../components/DetectionOverlay'
import { Button, Chip, ErrorState, Spinner, TextInput } from '../../components/ui'
import { useDetails } from '../../hooks/useDetails'
import { confidenceText, framesSubjects, needsFullDecode, RULE_LABELS, zoomText } from './reviewWords'

// A box drawn smaller than this (fraction of the photo) is taken as a click, not a subject.
const MIN_BOX = 0.01

type Box = { left: number; top: number; right: number; bottom: number }

const boxStyle = (b: Box) => ({
  left: `${b.left * 100}%`,
  top: `${b.top * 100}%`,
  width: `${(b.right - b.left) * 100}%`,
  height: `${(b.bottom - b.top) * 100}%`,
})

function between(a: [number, number], b: [number, number]): SubjectBox {
  return {
    left: Math.min(a[0], b[0]),
    top: Math.min(a[1], b[1]),
    right: Math.max(a[0], b[0]),
    bottom: Math.max(a[1], b[1]),
  }
}

/** ``crop`` moved by (dx, dy), kept inside the photo: display only while dragging; core places it on release. */
function moved(crop: CropRect, dx: number, dy: number): CropRect {
  const w = crop.right - crop.left
  const h = crop.bottom - crop.top
  const left = Math.min(1 - w, Math.max(0, crop.left + dx))
  const top = Math.min(1 - h, Math.max(0, crop.top + dy))
  return { left, top, right: left + w, bottom: top + h }
}

const center = (crop: CropRect): FramePosition => ({
  x: Math.min(1, Math.max(0, (crop.left + crop.right) / 2)),
  y: Math.min(1, Math.max(0, (crop.top + crop.bottom) / 2)),
})

/** The whole (edited) photo with the export's frame on it (drag it to move it) and what detection found. */
function FramedPhoto({
  item,
  frame,
  details,
  drawing,
  busy,
  subjects,
  onCandidate,
  onBox,
  onMove,
  onMoved,
}: {
  item: ReviewItem
  frame: CropRect
  details: boolean
  drawing: boolean
  busy: boolean
  subjects: boolean
  onCandidate: (index: number) => void
  onBox: (box: SubjectBox) => void
  onMove: (crop: CropRect) => void
  onMoved: (crop: CropRect) => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const [sketch, setSketch] = useState<SubjectBox | null>(null)
  const at = (e: { clientX: number; clientY: number }): [number, number] => {
    const rect = ref.current?.getBoundingClientRect()
    if (!rect || rect.width === 0 || rect.height === 0) return [0.5, 0.5]
    const clamp = (v: number) => Math.min(1, Math.max(0, v))
    return [clamp((e.clientX - rect.left) / rect.width), clamp((e.clientY - rect.top) / rect.height)]
  }
  const startSketch = (e: ReactMouseEvent) => {
    e.preventDefault()
    const start = at(e)
    setSketch(between(start, start))
    const onMoveSketch = (m: MouseEvent) => setSketch(between(start, at(m)))
    const onUp = (m: MouseEvent) => {
      window.removeEventListener('mousemove', onMoveSketch)
      window.removeEventListener('mouseup', onUp)
      const drawn = between(start, at(m))
      setSketch(null)
      if (drawn.right - drawn.left >= MIN_BOX && drawn.bottom - drawn.top >= MIN_BOX) onBox(drawn)
    }
    window.addEventListener('mousemove', onMoveSketch)
    window.addEventListener('mouseup', onUp)
  }
  const startMove = (e: ReactMouseEvent) => {
    if (busy) return
    e.preventDefault()
    const [x0, y0] = at(e)
    const from = frame
    let last = from
    const onDrag = (m: MouseEvent) => {
      const [x, y] = at(m)
      last = moved(from, x - x0, y - y0)
      onMove(last)
    }
    const onUp = () => {
      window.removeEventListener('mousemove', onDrag)
      window.removeEventListener('mouseup', onUp)
      if (last !== from) onMoved(last)
    }
    window.addEventListener('mousemove', onDrag)
    window.addEventListener('mouseup', onUp)
  }

  return (
    <div ref={ref} className="relative mx-auto w-fit select-none" data-testid="review-photo">
      <img
        src={imageUrls.preview(item.photo_id, { size: 1200, version: item.revision })}
        alt={item.filename}
        className="block max-h-[42vh] max-w-full"
        draggable={false}
      />
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        {/* Everything outside the export's frame is dimmed. */}
        <div className="absolute shadow-[0_0_0_9999px_rgba(0,0,0,0.55)]" style={boxStyle(frame)} />
      </div>
      {details && (
        <DetectionOverlay
          subject={item.subject_box}
          subjectLabel={confidenceText(item)}
          manual={item.subject === 'manual'}
          candidates={item.candidates}
          focus={item.focus}
          onCandidate={subjects ? onCandidate : undefined}
          disabled={busy || drawing}
        />
      )}
      {/* The frame itself, on top so it can be dragged; the candidates' boxes stay clickable beside it. */}
      <div
        aria-label="Export frame (drag to move it)"
        role="presentation"
        className="absolute cursor-move border-2 border-white"
        style={boxStyle(frame)}
        onMouseDown={startMove}
        data-testid="review-frame"
      />
      {sketch && <div className="absolute border-2 border-dashed border-amber-300" style={boxStyle(sketch)} />}
      {drawing && (
        <div
          aria-label="Draw the subject"
          className="absolute inset-0 cursor-crosshair"
          onMouseDown={startSketch}
          data-testid="review-draw"
        />
      )}
    </div>
  )
}

/** The export as it will look: the real framing preview, or (while zoom or position move) the loaded photo
 * cropped to the frame in the browser, until the real one for the new framing has loaded. */
function FramingPreview({ review, item, frame, live }: { review: ExportReview; item: ReviewItem; frame: CropRect; live: boolean }) {
  const [loaded, setLoaded] = useState<string | null>(null)
  const w = frame.right - frame.left
  const h = frame.bottom - frame.top
  const showReal = !live && loaded === item.revision
  return (
    <div
      className="relative max-h-48 overflow-hidden rounded border border-line"
      style={{ aspectRatio: `${item.width} / ${item.height}`, height: '12rem' }}
      data-testid="framing-preview"
    >
      <img
        src={imageUrls.preview(item.photo_id, { size: 1200, version: item.revision })}
        alt=""
        className="absolute max-w-none"
        style={{ width: `${100 / w}%`, height: `${100 / h}%`, left: `${(-frame.left / w) * 100}%`, top: `${(-frame.top / h) * 100}%` }}
        draggable={false}
      />
      <img
        src={imageUrls.reviewPreview(review.id, item.photo_id, item.revision)}
        alt={`${item.filename} as exported`}
        onLoad={() => setLoaded(item.revision)}
        className="absolute inset-0 size-full"
        style={{ visibility: showReal ? 'visible' : 'hidden' }}
      />
    </div>
  )
}

/** The zoom: Auto, or set by hand up to the quality limit; past the fast limit the export needs the full decode.
 * While the slider moves, `onLive` gets each step's zoom; the change is saved on release. */
function ZoomControl({
  item,
  busy,
  onLive,
  onZoom,
}: {
  item: ReviewItem
  busy: boolean
  onLive: (zoom: number | null) => void
  onZoom: (zoom: number | null) => void
}) {
  const { fast, quality } = item.limits
  const [value, setValue] = useState(item.zoom)
  const [text, setText] = useState(item.zoom.toFixed(2))
  const [shown, setShown] = useState(item.revision)
  if (shown !== item.revision) {
    // A new answer from the backend: show its zoom.
    setShown(item.revision)
    setValue(item.zoom)
    setText(item.zoom.toFixed(2))
  }
  const commit = (zoom: number) => {
    const clamped = Math.min(quality, Math.max(1, zoom))
    if (Math.abs(clamped - item.zoom) > 0.005) onZoom(Math.round(clamped * 100) / 100)
    else onLive(null)
  }
  if (quality <= 1.0001) {
    return <p className="text-xs text-muted">This export can't zoom: its crop already has no more pixels than the output.</p>
  }
  const mark = (z: number) => `${((z - 1) / (quality - 1)) * 100}%`
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2 text-xs">
        <span className="text-muted">Zoom</span>
        <TextInput
          type="number"
          aria-label="Zoom"
          className="h-7 w-20"
          step={0.01}
          min={1}
          max={quality}
          value={text}
          disabled={busy}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => {
            const n = Number(text)
            if (text.trim() !== '' && Number.isFinite(n)) commit(n)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') (e.target as HTMLInputElement).blur()
          }}
        />
        <span className="text-muted">×</span>
        <Button size="sm" variant="ghost" disabled={busy || item.zoom_override === null} onClick={() => onZoom(null)}>
          Auto ({zoomText(item.auto_zoom)})
        </Button>
        {item.zoom_override === null && <Chip>auto</Chip>}
      </div>
      <div className="relative">
        <input
          type="range"
          aria-label="Zoom slider"
          className="w-full accent-[var(--color-accent)]"
          min={1}
          max={quality}
          step={0.01}
          value={value}
          disabled={busy}
          onChange={(e) => {
            const zoom = Number(e.target.value)
            setValue(zoom)
            setText(zoom.toFixed(2))
            onLive(zoom)
          }}
          onMouseUp={() => commit(value)}
          onTouchEnd={() => commit(value)}
          onKeyUp={() => commit(value)}
        />
        <div className="relative h-4 text-[10px] text-muted">
          {fast < quality - 0.005 && (
            <span className="absolute -translate-x-1/2" style={{ left: mark(fast) }} title="Past this, the full decode (slower)">
              │ fast {zoomText(fast)}
            </span>
          )}
          <span className="absolute right-0">max {zoomText(quality)} │</span>
        </div>
      </div>
      {(value > fast + 1e-6 && item.decode === 'full') || needsFullDecode(item) ? (
        <p className="text-[11px] text-warn">Past {zoomText(fast)} this photo needs the full decode: its export is slower.</p>
      ) : null}
      {item.zoom >= quality - 0.005 && item.zoom > 1 && (
        <p className="text-[11px] text-muted">At the most zoom without enlarging.</p>
      )}
    </div>
  )
}

export function ReviewPanel({
  review,
  item,
  onPrev,
  onNext,
}: {
  review: ExportReview
  item: ReviewItem
  onPrev?: () => void
  onNext?: () => void
}) {
  const update = useUpdateReviewItem(review.id)
  const setSubject = useSetReviewSubject(review.id)
  const [details, toggleDetails] = useDetails()
  const [drawing, setDrawing] = useState(false)
  // The frame while the zoom slider or a drag moves it (display only), until the saved framing arrives.
  const [live, setLive] = useState<{ crop: CropRect; revision: string } | null>(null)
  const busy = update.isPending || setSubject.isPending
  const unusable = item.status === 'unusable'
  const subjects = framesSubjects(review)
  const frames = useReviewFrames(review.id, item.photo_id, item.revision, !unusable && item.limits.quality > 1.0001)
  const liveCrop = live && live.revision === item.revision ? live.crop : null
  const frame = liveCrop ?? item.crop

  const showZoom = (zoom: number | null) => {
    const list = frames.data?.frames
    if (zoom === null || !list?.length) return setLive(null)
    const nearest = list.reduce((best, f) => (Math.abs(f.zoom - zoom) < Math.abs(best.zoom - zoom) ? f : best))
    setLive({ crop: nearest.crop, revision: item.revision })
  }

  return (
    <section aria-label={`Review of ${item.filename}`} className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Button size="sm" variant="ghost" disabled={!onPrev} onClick={onPrev} aria-label="Previous photo">
          <ChevronLeft className="size-4" aria-hidden />
        </Button>
        <h2 className="min-w-0 flex-1 truncate text-sm font-semibold text-strong">{item.filename}</h2>
        {subjects && <Chip>{confidenceText(item)}</Chip>}
        {item.approved && (
          <Chip tone="ok">
            <Check className="mr-1 size-3" aria-hidden /> approved
          </Chip>
        )}
        <Chip tone={item.status === 'ready' ? 'ok' : item.status === 'check' ? 'warn' : 'err'}>{item.status}</Chip>
        <Button size="sm" variant="ghost" disabled={!onNext} onClick={onNext} aria-label="Next photo">
          <ChevronRight className="size-4" aria-hidden />
        </Button>
      </div>

      <FramedPhoto
        item={item}
        frame={frame}
        details={details && subjects}
        drawing={drawing}
        busy={busy || unusable}
        subjects={subjects}
        onCandidate={(index) => setSubject.mutate({ photoId: item.photo_id, update: { candidate: index } })}
        onBox={(box) => {
          setDrawing(false)
          setSubject.mutate({ photoId: item.photo_id, update: { box } })
        }}
        onMove={(crop) => setLive({ crop, revision: item.revision })}
        onMoved={(crop) => update.mutate({ photoId: item.photo_id, update: { position: center(crop) } })}
      />
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {subjects && (
          <>
            <Button
              size="sm"
              variant={drawing ? 'primary' : 'secondary'}
              disabled={busy || unusable}
              onClick={() => setDrawing((d) => !d)}
              title="Drag a box around the subject"
            >
              <SquareDashedMousePointer className="size-3.5" aria-hidden /> Set subject
            </Button>
            {item.subject === 'manual' && (
              <Button
                size="sm"
                variant="ghost"
                disabled={busy}
                onClick={() => setSubject.mutate({ photoId: item.photo_id, update: { box: null } })}
              >
                Use detected
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={toggleDetails} title="Show or hide what detection found (D)">
              {details ? <EyeOff className="size-3.5" aria-hidden /> : <Eye className="size-3.5" aria-hidden />}
              {details ? 'Hide details' : 'Show details'}
            </Button>
          </>
        )}
        {item.position && (
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => update.mutate({ photoId: item.photo_id, update: { position: null } })}
            title="Forget where the frame was dragged and place it by the rules again"
          >
            <Crosshair className="size-3.5" aria-hidden /> {subjects ? 'Re-center on subject' : 'Re-center'}
          </Button>
        )}
        {busy && <Spinner className="size-3.5" label="Saving" />}
      </div>
      <p className="text-[11px] text-muted">
        Drag the frame to move it{subjects && item.candidates.length > 0 ? ' · click a box to frame that subject' : ''}
        {subjects ? ' · D hides the details' : ''}
      </p>

      {item.reasons.length > 0 && (
        <ul className="flex flex-col gap-1" aria-label="Reasons">
          {item.reasons.map((r) => (
            <li key={r.code} className="flex items-start gap-2 text-xs">
              <Chip tone={r.code === 'unusable' ? 'err' : 'warn'}>{RULE_LABELS[r.code]}</Chip>
              <span className="pt-0.5">{r.text}</span>
            </li>
          ))}
        </ul>
      )}

      {!unusable && (
        <>
          <ZoomControl
            item={item}
            busy={busy}
            onLive={showZoom}
            onZoom={(zoom) => update.mutate({ photoId: item.photo_id, update: { zoom } })}
          />
          <div className="flex items-start gap-3">
            <FramingPreview review={review} item={item} frame={frame} live={liveCrop !== null} />
            <div className="flex flex-col gap-1 text-xs text-muted">
              <span>
                {item.width}×{item.height} · {item.decode} decode
              </span>
              {item.warnings.map((w) => (
                <span key={w}>{w}</span>
              ))}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {item.approved ? (
              <Button
                disabled={busy}
                onClick={() => update.mutate({ photoId: item.photo_id, update: { approved: false } })}
              >
                Unapprove
              </Button>
            ) : (
              <Button
                variant="primary"
                disabled={busy}
                onClick={() => update.mutate({ photoId: item.photo_id, update: { approved: true } })}
              >
                <Check className="size-4" aria-hidden /> Approve (A)
              </Button>
            )}
            <span className="text-[11px] text-muted">← → previous / next</span>
          </div>
        </>
      )}
      {update.isError && <ErrorState error={update.error} />}
      {setSubject.isError && <ErrorState error={setSubject.error} />}
    </section>
  )
}
