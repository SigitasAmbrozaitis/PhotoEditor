import { Link } from 'react-router'
import { useDiscardReview, useReviews } from '../../api/queries'
import { Button, Chip, EmptyState, ErrorState, Loading, PageHeader } from '../../components/ui'

/** Open reviews (prepared exports waiting for decisions), newest first. */
export function ReviewsPage() {
  const reviews = useReviews()
  const discard = useDiscardReview()

  return (
    <div className="flex h-full flex-col">
      <PageHeader
        title="Reviews"
        subtitle="Prepared exports. Start one with Prepare export… in the Library; exported photos leave the review."
      />
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {reviews.isLoading ? (
          <Loading />
        ) : reviews.isError ? (
          <ErrorState error={reviews.error} />
        ) : !reviews.data?.length ? (
          <EmptyState title="No open reviews.">Select photos in the Library and choose Prepare export….</EmptyState>
        ) : (
          <ul className="flex flex-col gap-2" aria-label="Open reviews">
            {reviews.data.map((r) => (
              <li key={r.id} className="flex items-center gap-3 rounded border border-line bg-panel px-3 py-2">
                <Link to={`/reviews/${r.id}`} className="min-w-0 flex-1 hover:underline">
                  <p className="text-sm text-strong">
                    {r.counts.total} photo{r.counts.total === 1 ? '' : 's'} · {r.preset_id ?? 'custom settings'}
                  </p>
                  <p className="truncate font-mono text-xs text-muted">
                    {new Date(r.created_at).toLocaleString()} → {r.destination}
                  </p>
                </Link>
                {r.counts.check > 0 ? (
                  <Chip tone="warn">{r.counts.check} to check</Chip>
                ) : (
                  <Chip tone="ok">all approved</Chip>
                )}
                <Button size="sm" variant="ghost" onClick={() => discard.mutate(r.id)} aria-label={`Discard review ${r.id}`}>
                  Discard
                </Button>
              </li>
            ))}
          </ul>
        )}
        {discard.isError && <ErrorState error={discard.error} />}
      </div>
    </div>
  )
}
