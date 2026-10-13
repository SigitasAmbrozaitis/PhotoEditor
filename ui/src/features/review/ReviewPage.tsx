import { Check } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { ApiError, imageUrls } from '../../api/client'
import { useDiscardReview, useReview, useUpdateReviewItem } from '../../api/queries'
import type { ExportReview, ReviewItem } from '../../api/types'
import { Button, Chip, EmptyState, ErrorState, Loading, PageHeader } from '../../components/ui'
import { cn } from '../../lib/cn'
import { ReviewExportButtons } from './ReviewExportButtons'
import { ReviewPanel } from './ReviewPanel'
import { ReviewRules } from './ReviewRules'
import { RULE_LABELS, reviewGroups, reviewOrder, zoomText } from './reviewWords'

function Card({
  review,
  item,
  selected,
  onSelect,
}: {
  review: ExportReview
  item: ReviewItem
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={item.filename}
      className={cn(
        'flex flex-col overflow-hidden rounded border bg-panel text-left',
        selected ? 'border-accent ring-2 ring-accent' : 'border-line hover:border-muted',
      )}
    >
      <div className="flex aspect-square items-center justify-center bg-black/40">
        {item.status !== 'unusable' && (
          <img
            src={imageUrls.reviewPreview(review.id, item.photo_id, item.revision)}
            alt=""
            loading="lazy"
            className="max-h-full max-w-full object-contain"
          />
        )}
      </div>
      <div className="flex flex-col gap-1 p-1.5">
        <span className="flex items-center gap-1 truncate text-xs text-strong">
          {item.approved && <Check className="size-3.5 shrink-0 text-ok" aria-label="approved" />}
          {item.filename}
          {item.zoom > 1.005 && <span className="ml-auto font-mono text-[10px] text-muted">{zoomText(item.zoom)}</span>}
        </span>
        {item.reasons.length > 0 && (
          <span className="flex flex-wrap gap-1">
            {item.reasons.map((r) => (
              <Chip key={r.code} tone={r.code === 'unusable' ? 'err' : 'warn'}>
                {RULE_LABELS[r.code]}
              </Chip>
            ))}
          </span>
        )}
      </div>
    </button>
  )
}

function Group({
  title,
  items,
  review,
  current,
  onSelect,
}: {
  title: string
  items: ReviewItem[]
  review: ExportReview
  current: string | undefined
  onSelect: (id: string) => void
}) {
  if (items.length === 0) return null
  return (
    <section aria-label={title} className="flex flex-col gap-2">
      <h2 className="text-xs font-semibold tracking-wide text-muted uppercase">
        {title} ({items.length})
      </h2>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(150px,1fr))] gap-2">
        {items.map((item) => (
          <Card
            key={item.photo_id}
            review={review}
            item={item}
            selected={item.photo_id === current}
            onSelect={() => onSelect(item.photo_id)}
          />
        ))}
      </div>
    </section>
  )
}

function Review({ review }: { review: ExportReview }) {
  const navigate = useNavigate()
  const discard = useDiscardReview()
  const update = useUpdateReviewItem(review.id)
  const order = reviewOrder(review.items)
  const groups = reviewGroups(review.items)
  const [selected, setSelected] = useState<string | undefined>(order[0]?.photo_id)
  const index = Math.max(0, order.findIndex((i) => i.photo_id === selected))
  const current = order[index]
  const prev = index > 0 ? () => setSelected(order[index - 1]?.photo_id) : undefined
  const next = index < order.length - 1 ? () => setSelected(order[index + 1]?.photo_id) : undefined

  // A approves (or takes it back), ← → move through the photos; not while typing in a field. The listener
  // stays; it always calls the latest handler.
  const onKey = useRef<(e: KeyboardEvent) => void>(() => {})
  useEffect(() => {
    onKey.current = (e) => {
      const target = e.target as HTMLElement | null
      if (target && ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)) return
      if (e.key === 'ArrowRight' && next) next()
      else if (e.key === 'ArrowLeft' && prev) prev()
      else if ((e.key === 'a' || e.key === 'A') && current && current.status !== 'unusable' && !update.isPending) {
        update.mutate({ photoId: current.photo_id, update: { approved: !current.approved } })
      } else return
      e.preventDefault()
    }
  })
  useEffect(() => {
    const listener = (e: KeyboardEvent) => onKey.current(e)
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [])

  const { counts } = review
  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title={`Review · ${review.preset_id ?? 'custom settings'}`}
        subtitle={
          <span>
            {counts.total} photos → <span className="font-mono">{review.destination}</span> · {counts.ready} ready ·{' '}
            {counts.check} to check · {counts.approved} approved
            {counts.unusable > 0 && ` · ${counts.unusable} can't be exported`}
          </span>
        }
        actions={
          <>
            <ReviewRules />
            <Button
              variant="ghost"
              onClick={() => discard.mutate(review.id, { onSuccess: () => void navigate('/reviews') })}
            >
              Discard
            </Button>
            <ReviewExportButtons review={review} />
          </>
        }
      />
      <div className="flex min-h-0 flex-1">
        <div className="min-w-0 flex-1 overflow-y-auto p-3">
          <div className="flex flex-col gap-4">
            <Group title="Check" items={groups.check} review={review} current={current?.photo_id} onSelect={setSelected} />
            <Group title="Ready" items={groups.ready} review={review} current={current?.photo_id} onSelect={setSelected} />
            <Group
              title="Can't be exported"
              items={groups.unusable}
              review={review}
              current={current?.photo_id}
              onSelect={setSelected}
            />
          </div>
        </div>
        {current && (
          <aside className="w-[460px] shrink-0 overflow-y-auto border-l border-line bg-panel p-3">
            <ReviewPanel key={current.photo_id} review={review} item={current} onPrev={prev} onNext={next} />
          </aside>
        )}
      </div>
      {discard.isError && <ErrorState error={discard.error} />}
    </div>
  )
}

/** A prepared export: Check first, then Ready; fix or approve, then export (P6c.10). */
export function ReviewPage() {
  const { reviewId } = useParams()
  const review = useReview(reviewId)
  if (review.isLoading) return <Loading />
  if (review.error instanceof ApiError && review.error.status === 404) {
    return (
      <EmptyState title="This review is done or was discarded.">
        <Link to="/reviews" className="text-accent hover:underline">
          Open reviews
        </Link>
      </EmptyState>
    )
  }
  if (review.isError) return <ErrorState error={review.error} />
  if (!review.data) return null
  return <Review review={review.data} />
}
