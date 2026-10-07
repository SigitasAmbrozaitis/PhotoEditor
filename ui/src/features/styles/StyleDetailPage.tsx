import { ArrowLeft, Wand2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { useStyle } from '../../api/queries'
import { Button, Chip, ErrorState, Loading, PageHeader, Tooltip } from '../../components/ui'
import { useSelection } from '../../state/selection'
import { ProcessWizard } from '../process/ProcessWizard'
import { parameterLabel, parameterValue } from './parameterFormat'

export function StyleDetailPage() {
  const { styleId = '' } = useParams()
  const navigate = useNavigate()
  const selection = useSelection()
  const style = useStyle(styleId)
  const [applying, setApplying] = useState(false)

  if (style.isError) return <ErrorState error={style.error} />
  if (!style.data) return <Loading label="Loading style…" />
  const s = style.data
  const changed = Object.entries(s.changed_parameters)
  const count = selection.ids.length

  const applyButton = (
    <Button variant="primary" disabled={count === 0} onClick={() => setApplying(true)}>
      <Wand2 className="size-4" aria-hidden /> Apply to {count} selected
    </Button>
  )

  return (
    <>
      <PageHeader
        title={s.name}
        subtitle={`Version ${s.version} · updated ${new Date(s.updated_at).toLocaleDateString()}`}
        actions={
          <>
            <Button variant="ghost" onClick={() => void navigate('/styles')}>
              <ArrowLeft className="size-4" aria-hidden /> All styles
            </Button>
            {count === 0 ? (
              <Tooltip content="Select photos in the Library first.">
                <span>{applyButton}</span>
              </Tooltip>
            ) : (
              applyButton
            )}
          </>
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4">
          <section className="grid gap-4 md:grid-cols-3">
            <div className="md:col-span-2">
              <h2 className="mb-1 text-xs font-semibold tracking-wide text-muted uppercase">Description</h2>
              <p className="text-sm leading-relaxed">{s.description}</p>
            </div>
            <div className="flex flex-col gap-3">
              <div>
                <h2 className="mb-1 text-xs font-semibold tracking-wide text-muted uppercase">Best for</h2>
                <div className="flex flex-wrap gap-1.5">
                  {s.best_for.map((t) => (
                    <Chip key={t} tone="ok">
                      {t}
                    </Chip>
                  ))}
                </div>
              </div>
              <div>
                <h2 className="mb-1 text-xs font-semibold tracking-wide text-muted uppercase">Avoid on</h2>
                <div className="flex flex-wrap gap-1.5">
                  {s.avoid_on.map((t) => (
                    <Chip key={t} tone="err">
                      {t}
                    </Chip>
                  ))}
                </div>
              </div>
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">
              Expected result (before → after)
            </h2>
            <div className="flex flex-col gap-3">
              {s.samples.map((sample, i) => (
                <figure key={i} className="grid grid-cols-2 gap-2">
                  <div className="relative">
                    <img src={sample.before_url} alt={`${sample.caption} before`} className="w-full rounded" />
                    <span className="absolute top-1.5 left-1.5 rounded bg-black/70 px-1.5 text-[11px]">Before</span>
                  </div>
                  <div className="relative">
                    <img src={sample.after_url} alt={`${sample.caption} after`} className="w-full rounded" />
                    <span className="absolute top-1.5 left-1.5 rounded bg-black/70 px-1.5 text-[11px]">After</span>
                  </div>
                  {sample.caption && (
                    <figcaption className="col-span-2 text-xs text-muted">{sample.caption}</figcaption>
                  )}
                </figure>
              ))}
            </div>
          </section>

          <section>
            <h2 className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">
              Parameters ({changed.length} changed from neutral)
            </h2>
            <table className="w-full max-w-2xl text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  <th className="py-1.5 font-medium">Parameter</th>
                  <th className="py-1.5 text-right font-medium">Value</th>
                </tr>
              </thead>
              <tbody>
                {changed.map(([path, value]) => (
                  <tr key={path} className="border-b border-line/50">
                    <td className="py-1.5">{parameterLabel(path)}</td>
                    <td className="py-1.5 text-right font-mono tabular-nums">{parameterValue(path, value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      </div>
      {applying && (
        <ProcessWizard
          open
          onOpenChange={(o) => !o && setApplying(false)}
          photoIds={selection.ids}
          initialStyleId={s.id}
        />
      )}
    </>
  )
}
