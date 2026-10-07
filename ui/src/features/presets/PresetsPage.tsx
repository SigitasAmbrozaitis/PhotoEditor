import { Copy, Lock } from 'lucide-react'
import { Link, useParams } from 'react-router'
import { usePresets } from '../../api/queries'
import type { ExportTarget } from '../../api/types'
import { Button, Chip, EmptyState, ErrorState, Loading, PageHeader, Tooltip } from '../../components/ui'
import { cn } from '../../lib/cn'
import { ExportSettingsForm } from '../export/ExportSettingsForm'
import { exportSummary } from '../export/exportSummary'

const TARGET_LABELS: Record<ExportTarget, string> = {
  instagram: 'Instagram',
  print: 'Print',
  web: 'Web',
  custom: 'Custom',
}

export function PresetsPage() {
  const { presetId } = useParams()
  const presets = usePresets()
  const selected = presets.data?.find((p) => p.id === presetId) ?? presets.data?.[0]

  return (
    <>
      <PageHeader title="Export presets" subtitle="Reusable export settings. Built-in presets are read-only." />
      {presets.isError ? (
        <ErrorState error={presets.error} />
      ) : presets.isLoading ? (
        <Loading />
      ) : !presets.data?.length || !selected ? (
        <EmptyState title="No export presets." />
      ) : (
        <div className="flex min-h-0 flex-1">
          <ul aria-label="Export presets" className="w-80 shrink-0 overflow-y-auto border-r border-line bg-panel">
            {presets.data.map((p) => (
              <li key={p.id}>
                <Link
                  to={`/presets/${p.id}`}
                  aria-current={p.id === selected.id ? 'page' : undefined}
                  className={cn(
                    'flex flex-col gap-0.5 border-b border-line px-3 py-2',
                    p.id === selected.id ? 'bg-raised' : 'hover:bg-hover',
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="text-sm text-strong">{p.name}</span>
                    <Chip>{TARGET_LABELS[p.target]}</Chip>
                  </span>
                  <span className="truncate font-mono text-[11px] text-muted">{exportSummary(p.settings).split(' → ')[0]}</span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            <div className="mx-auto flex max-w-3xl flex-col gap-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="flex items-center gap-2 text-base font-semibold text-strong">
                    {selected.name}
                    {selected.builtin && <Lock className="size-3.5 text-muted" aria-label="built-in (read-only)" />}
                  </h2>
                  <p className="text-sm text-muted">{selected.description}</p>
                </div>
                <Tooltip content="Custom presets arrive in Phase 5.">
                  <span>
                    <Button disabled>
                      <Copy className="size-4" aria-hidden /> Duplicate
                    </Button>
                  </span>
                </Tooltip>
              </div>
              <ExportSettingsForm value={selected.settings} onChange={() => undefined} disabled />
            </div>
          </div>
        </div>
      )}
    </>
  )
}
