import { Check, ChevronLeft, ChevronRight, SquareDashedMousePointer } from 'lucide-react'
import { useRef, useState, type MouseEvent as ReactMouseEvent } from 'react'
import { imageUrls } from '../../api/client'
import { useSetReviewSubject, useUpdateReviewItem } from '../../api/queries'
import type { ExportReview, ReviewItem, SubjectBox } from '../../api/types'
import { Button, Chip, ErrorState, Spinner, TextInput } from '../../components/ui'
import { cn } from '../../lib/cn'
import { needsFullDecode, RULE_LABELS, zoomText } from './reviewWords'

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

/** The whole (edited) photo with the export's frame on it and the candidates as boxes to click. */
function FramedPhoto({
  item,
  drawing,
  busy,
  onCandidate,
  onBox,
}: {
  item: ReviewItem
  drawing: boolean
  busy: boolean
  onCandidate: (index: number) => void
  onBox: (box: SubjectBox) => void
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
    const onMove = (m: MouseEvent) => setSketch(between(start, at(m)))
    const onUp = (m: MouseEvent) => {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      const drawn = between(start, at(m))
      setSketch(null)
      if (drawn.right - drawn.left >= MIN_BOX && drawn.bottom - drawn.top >= MIN_BOX) onBox(drawn)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  return (
    <div ref={ref} className="relative mx-auto w-fit overflow-hidden" data-testid="review-photo">
      <img
        src={imageUrls.preview(item.photo_id, { size: 1200, version: item.revision })}
        alt={item.filename}
        className="block max-h-[42vh] max-w-full"
        draggable={false}
      />
      {/* The export's frame: everything outside it is dimmed. */}
      <div
        className="pointer-events-none absolute border-2 border-white shadow-[0_0_0_9999px_rgba(0,0,0,0.55)]"
        style={boxStyle(item.crop)}
        data-testid="review-frame"
      />
      {item.candidates.map((c) => (
        <button
          key={c.index}
          type="button"
          disabled={busy || drawing}
          aria-label={`Use the ${c.label ?? c.kind} (${Math.round(c.score * 100)} %)`}
          aria-pressed={c.chosen}
          onClick={() => onCandidate(c.index)}
          className={cn(
            'absolute border-2',
            c.chosen ? 'border-amber-400' : 'border-dashed border-sky-300 hover:bg-sky-300/20',
          )}
          style={boxStyle(c.box)}
          title={`${c.label ?? c.kind} ${Math.round(c.score * 100)} %`}
        />
      ))}
      {item.subject === 'manual' && item.subject_box && (
        <div
          className="pointer-events-none absolute border-2 border-amber-400"
          style={boxStyle(item.subject_box)}
          data-testid="review-manual-subject"
        />
      )}
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

/** The zoom: Auto, or set by hand up to the quality limit; past the fast limit the export needs the full decode. */
function ZoomControl({
  item,
  busy,
  onZoom,
}: {
  item: ReviewItem
  busy: boolean
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
          onChange={(e) => setValue(Number(e.target.value))}
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
      {needsFullDecode(item) && (
        <p className="text-[11px] text-warn">Past {zoomText(fast)} this photo needs the full decode: its export is slower.</p>
      )}
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
  const [drawing, setDrawing] = useState(false)
  const busy = update.isPending || setSubject.isPending
  const unusable = item.status === 'unusable'

  return (
    <section aria-label={`Review of ${item.filename}`} className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <Button size="sm" variant="ghost" disabled={!onPrev} onClick={onPrev} aria-label="Previous photo">
          <ChevronLeft className="size-4" aria-hidden />
        </Button>
        <h2 className="min-w-0 flex-1 truncate text-sm font-semibold text-strong">{item.filename}</h2>
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
        drawing={drawing}
        busy={busy || unusable}
        onCandidate={(index) => setSubject.mutate({ photoId: item.photo_id, update: { candidate: index } })}
        onBox={(box) => {
          setDrawing(false)
          setSubject.mutate({ photoId: item.photo_id, update: { box } })
        }}
      />
      <div className="flex flex-wrap items-center gap-2 text-xs">
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
        {item.candidates.length > 1 && <span className="text-muted">Click a box to frame that subject.</span>}
        {busy && <Spinner className="size-3.5" label="Saving" />}
      </div>

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
            onZoom={(zoom) => update.mutate({ photoId: item.photo_id, update: { zoom } })}
          />
          <div className="flex items-start gap-3">
            <img
              src={imageUrls.reviewPreview(review.id, item.photo_id, item.revision)}
              alt={`${item.filename} as exported`}
              className="max-h-48 max-w-[60%] rounded border border-line"
            />
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
