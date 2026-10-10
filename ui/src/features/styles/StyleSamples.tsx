/** Before/after sample pairs, re-rendered from selected Library photos. */
import { useQueryClient } from '@tanstack/react-query'
import { Images } from 'lucide-react'
import { useEffect, useState } from 'react'
import { isActive, queryKeys, useJob, useRenderSamples } from '../../api/queries'
import type { Style } from '../../api/types'
import { Button, Chip, ProgressBar } from '../../components/ui'
import { useSelection } from '../../state/selection'
import { Section } from './StyleSection'

const MAX_SAMPLES = 12

export function StyleSamples({ style }: { style: Style }) {
  const selection = useSelection()
  const client = useQueryClient()
  const render = useRenderSamples(style.id)
  const [jobId, setJobId] = useState<string>()
  const job = useJob(jobId)
  const running = job.data !== undefined && isActive(job.data)
  const count = Math.min(selection.ids.length, MAX_SAMPLES)

  useEffect(() => {
    if (job.data && !isActive(job.data)) void client.invalidateQueries({ queryKey: queryKeys.style(style.id) })
  }, [job.data, client, style.id])

  const start = () =>
    render.mutate(selection.ids.slice(0, MAX_SAMPLES), { onSuccess: (created) => setJobId(created.id) })

  return (
    <Section
      title="Expected result (before → after)"
      actions={
        <>
          {style.samples_stale && <Chip tone="err">Some samples show an older version</Chip>}
          <Button size="sm" onClick={start} disabled={count === 0 || running || render.isPending}>
            <Images className="size-3.5" aria-hidden /> Render from {count} selected
          </Button>
        </>
      }
    >
      {running && <ProgressBar value={job.data?.progress ?? 0} label="Rendering samples" />}
      {style.samples.length === 0 ? (
        <p className="text-sm text-muted">No samples yet. Select a few photos in the Library and render them here.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {style.samples.map((sample, i) => (
            <figure key={i} className="grid grid-cols-2 gap-2">
              <div className="relative">
                <img src={sample.before_url} alt={`${sample.caption} before`} className="w-full rounded" />
                <span className="absolute top-1.5 left-1.5 rounded bg-black/70 px-1.5 text-[11px]">Before</span>
              </div>
              <div className="relative">
                <img src={sample.after_url} alt={`${sample.caption} after`} className="w-full rounded" />
                <span className="absolute top-1.5 left-1.5 rounded bg-black/70 px-1.5 text-[11px]">After</span>
                {sample.stale && (
                  <span className="absolute top-1.5 right-1.5 rounded bg-err/80 px-1.5 text-[11px] text-white">
                    older version
                  </span>
                )}
              </div>
              {sample.caption && <figcaption className="col-span-2 text-xs text-muted">{sample.caption}</figcaption>}
            </figure>
          ))}
        </div>
      )}
    </Section>
  )
}
