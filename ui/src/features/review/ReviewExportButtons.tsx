import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useExportReview } from '../../api/queries'
import type { ExportReview, ReviewExportScope } from '../../api/types'
import { Button, Dialog, ErrorState } from '../../components/ui'

/** Export Approved / Force Export All, or one Export All once nothing is left to approve (P6c.11). */
export function ReviewExportButtons({ review }: { review: ExportReview }) {
  const navigate = useNavigate()
  const exportReview = useExportReview(review.id)
  const [confirm, setConfirm] = useState(false)
  const { counts } = review
  const approved = counts.ready + counts.approved
  const all = counts.total - counts.unusable
  const unapproved = review.items.filter((i) => i.status === 'check' && !i.approved)

  const run = (scope: ReviewExportScope) =>
    exportReview.mutate(scope, {
      onSuccess: (job) => {
        setConfirm(false)
        void navigate(`/jobs/${job.id}`)
      },
    })

  return (
    <>
      {counts.check === 0 ? (
        <Button variant="primary" disabled={all === 0 || exportReview.isPending} onClick={() => run('approved')}>
          Export All ({all})
        </Button>
      ) : (
        <>
          <Button variant="primary" disabled={approved === 0 || exportReview.isPending} onClick={() => run('approved')}>
            Export Approved ({approved})
          </Button>
          <Button variant="danger" disabled={exportReview.isPending} onClick={() => setConfirm(true)}>
            Force Export All ({all})
          </Button>
        </>
      )}
      {exportReview.isError && !confirm && <ErrorState error={exportReview.error} />}
      <Dialog
        open={confirm}
        onOpenChange={setConfirm}
        title={`Export ${unapproved.length} photo${unapproved.length === 1 ? '' : 's'} without a look?`}
        description="They are exported as the tool framed them."
        width="max-w-md"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirm(false)}>
              Cancel
            </Button>
            <Button variant="danger" disabled={exportReview.isPending} onClick={() => run('all')}>
              Force Export All ({all})
            </Button>
          </>
        }
      >
        <ul className="flex flex-col gap-1 text-sm" aria-label="Not approved">
          {unapproved.map((i) => (
            <li key={i.photo_id}>
              <span className="text-strong">{i.filename}</span>
              <span className="text-xs text-muted"> · {i.reasons.map((r) => r.text).join('; ')}</span>
            </li>
          ))}
        </ul>
        {exportReview.isError && <ErrorState error={exportReview.error} />}
      </Dialog>
    </>
  )
}
