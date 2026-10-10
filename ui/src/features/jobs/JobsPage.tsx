import { Ban, CircleCheck, CircleX, Clock, FolderSearch, LoaderCircle } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { useCancelJob, useJob, useJobs, usePresets, useRevealFile, useStyles } from '../../api/queries'
import type { Job, JobItem, JobStatus } from '../../api/types'
import { Button, Chip, EmptyState, ErrorState, Loading, PageHeader, ProgressBar } from '../../components/ui'
import { cn } from '../../lib/cn'

const STATUS: Record<JobStatus, { label: string; className: string; icon: typeof Clock }> = {
  queued: { label: 'Queued', className: 'text-muted', icon: Clock },
  running: { label: 'Running', className: 'text-accent', icon: LoaderCircle },
  done: { label: 'Done', className: 'text-ok', icon: CircleCheck },
  failed: { label: 'Failed', className: 'text-err', icon: CircleX },
  cancelled: { label: 'Cancelled', className: 'text-warn', icon: Ban },
}

export function StatusLabel({ status }: { status: JobStatus }) {
  const { label, className, icon: Icon } = STATUS[status]
  return (
    <span className={cn('inline-flex items-center gap-1 text-xs', className)}>
      <Icon className={cn('size-3.5', status === 'running' && 'animate-spin')} aria-hidden />
      {label}
    </span>
  )
}

function JobRow({ job, active }: { job: Job; active: boolean }) {
  return (
    <li>
      <Link
        to={`/jobs/${job.id}`}
        aria-current={active ? 'page' : undefined}
        className={cn(
          'flex flex-col gap-1.5 border-b border-line px-3 py-2.5',
          active ? 'bg-raised' : 'hover:bg-hover',
        )}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="truncate text-sm text-strong">{job.title}</span>
          <StatusLabel status={job.status} />
        </div>
        <ProgressBar value={job.progress} label={`${job.title} progress`} />
        <div className="flex justify-between text-[11px] text-muted">
          <span>
            {job.completed} / {job.total}
            {job.failed > 0 && <span className="text-err"> · {job.failed} failed</span>}
          </span>
          <span>{new Date(job.created_at).toLocaleTimeString()}</span>
        </div>
      </Link>
    </li>
  )
}

function JobDetail({ jobId }: { jobId: string }) {
  const job = useJob(jobId)
  const cancel = useCancelJob()
  const styles = useStyles()
  const presets = usePresets()
  if (job.isError) return <ErrorState error={job.error} />
  if (!job.data) return <Loading />
  const j = job.data
  const active = j.status === 'queued' || j.status === 'running'
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-col gap-2 border-b border-line p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-strong">{j.title}</h2>
            <p className="text-xs text-muted">
              Started {new Date(j.created_at).toLocaleString()}
              {j.finished_at && ` · finished ${new Date(j.finished_at).toLocaleTimeString()}`}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <StatusLabel status={j.status} />
            {active && (
              <Button size="sm" variant="danger" disabled={cancel.isPending} onClick={() => cancel.mutate(j.id)}>
                Cancel
              </Button>
            )}
          </div>
        </div>
        <ProgressBar value={j.progress} label="Job progress" />
        <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-0.5 text-xs">
          <dt className="text-muted">Progress</dt>
          <dd>
            {j.completed} of {j.total} ({Math.round(j.progress * 100)}%)
            {j.failed > 0 && <span className="text-err"> · {j.failed} failed</span>}
          </dd>
          {j.summary && (
            <>
              <dt className="text-muted">Result</dt>
              <dd>{j.summary}</dd>
            </>
          )}
          {j.folder && (
            <>
              <dt className="text-muted">Folder</dt>
              <dd className="font-mono break-all">{j.folder}</dd>
            </>
          )}
          {j.style_id && (
            <>
              <dt className="text-muted">Style</dt>
              <dd>
                <Link className="text-accent hover:underline" to={`/styles/${j.style_id}`}>
                  {styles.data?.find((s) => s.id === j.style_id)?.name ?? j.style_id}
                </Link>
              </dd>
            </>
          )}
          {j.preset_id && (
            <>
              <dt className="text-muted">Export preset</dt>
              <dd>{presets.data?.find((p) => p.id === j.preset_id)?.name ?? j.preset_id}</dd>
            </>
          )}
          {j.destination && (
            <>
              <dt className="text-muted">Destination</dt>
              <dd className="font-mono break-all">{j.destination}</dd>
            </>
          )}
        </dl>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <table className="w-full text-xs">
          <thead className="sticky top-0 bg-panel">
            <tr className="border-b border-line text-left text-muted">
              <th className="px-4 py-1.5 font-medium">Photo</th>
              <th className="px-4 py-1.5 font-medium">Status</th>
              <th className="px-4 py-1.5 font-medium">Output / message</th>
            </tr>
          </thead>
          <tbody>
            {j.items.map((item, index) => (
              // Import items have no photo id until the file is identified, so rows are keyed by position.
              <tr key={index} className="border-b border-line/50">
                <td className="px-4 py-1.5 font-mono">
                  {item.photo_id ? (
                    <Link className="hover:underline" to={`/library/${item.photo_id}`}>
                      {item.filename}
                    </Link>
                  ) : (
                    item.filename
                  )}
                </td>
                <td className="px-4 py-1.5">
                  <StatusLabel status={item.status} />
                </td>
                <td
                  className={cn(
                    'px-4 py-1.5 break-all',
                    item.status === 'failed' ? 'text-err' : item.output_path ? 'font-mono text-muted' : 'text-muted',
                  )}
                >
                  {item.status === 'failed' ? (
                    item.message
                  ) : item.output_bytes !== null ? (
                    <ExportedFile item={item} />
                  ) : (
                    (item.output_path ?? item.message ?? '')
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function formatBytes(bytes: number): string {
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`
}

/** One written export file: its name, pixel and file size, warnings, and a button to show it in Explorer. */
function ExportedFile({ item }: { item: JobItem }) {
  const reveal = useRevealFile()
  const path = item.output_path ?? ''
  const name = path.split(/[\\/]/).pop()
  return (
    <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <span className="text-fg" title={path}>
        {name}
      </span>
      <span>
        {item.output_width}×{item.output_height} · {formatBytes(item.output_bytes ?? 0)}
      </span>
      {item.message && <Chip>{item.message}</Chip>}
      {item.warnings.map((w) => (
        <Chip key={w} tone="warn">
          {w}
        </Chip>
      ))}
      <Button size="sm" variant="ghost" aria-label={`Show ${name} in folder`} onClick={() => reveal.mutate(path)}>
        <FolderSearch className="size-3.5" aria-hidden /> Show in folder
      </Button>
      {reveal.isError && <span className="text-err">{reveal.error.message}</span>}
    </span>
  )
}

export function JobsPage() {
  const { jobId } = useParams()
  const jobs = useJobs()
  const running = jobs.data?.filter((j) => j.status === 'running' || j.status === 'queued').length ?? 0
  return (
    <>
      <PageHeader
        title="Jobs"
        subtitle={jobs.data ? `${jobs.data.length} jobs · ${running} running` : undefined}
      />
      <div className="flex min-h-0 flex-1">
        <div className="w-96 shrink-0 overflow-y-auto border-r border-line bg-panel">
          {jobs.isError ? (
            <ErrorState error={jobs.error} />
          ) : jobs.isLoading ? (
            <Loading />
          ) : !jobs.data?.length ? (
            <EmptyState title="No jobs yet." />
          ) : (
            <ul aria-label="Jobs">
              {jobs.data.map((job) => (
                <JobRow key={job.id} job={job} active={job.id === jobId} />
              ))}
            </ul>
          )}
        </div>
        {jobId ? (
          <JobDetail key={jobId} jobId={jobId} />
        ) : (
          <EmptyState title="Select a job to see its details." />
        )}
      </div>
    </>
  )
}
