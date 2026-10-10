import type { UseQueryResult } from '@tanstack/react-query'
import type { CollisionStatus, ExportPlan } from '../../api/types'
import { Chip, ErrorState, Loading } from '../../components/ui'

const COLLISION: Record<CollisionStatus, { label: string; tone: 'neutral' | 'warn' | 'err' }> = {
  new: { label: 'new', tone: 'neutral' },
  renamed: { label: 'renamed', tone: 'warn' },
  overwrite: { label: 'overwrites', tone: 'err' },
  skip: { label: 'exists: skipped', tone: 'warn' },
}

/** What the export will write, per photo: name, pixel size, decode, collisions and warnings. */
export function ExportPlanTable({ plan }: { plan: UseQueryResult<ExportPlan> }) {
  if (plan.isError) return <ErrorState error={plan.error} />
  if (!plan.data) return plan.isFetching ? <Loading label="Planning…" /> : null
  const items = plan.data.items
  const warnings = items.filter((i) => i.warnings.length > 0).length
  return (
    <div className="flex flex-col gap-1">
      <p className="text-xs text-muted">
        {items.length} file{items.length === 1 ? '' : 's'} into <span className="font-mono">{plan.data.destination}</span>
        {warnings > 0 && <span className="text-warn"> · {warnings} with warnings</span>}
      </p>
      <div className="max-h-56 overflow-y-auto rounded border border-line">
        <table aria-label="Export plan" className="w-full text-left text-xs">
          <thead className="sticky top-0 bg-raised text-muted">
            <tr>
              <th className="px-2 py-1 font-medium">Original</th>
              <th className="px-2 py-1 font-medium">File</th>
              <th className="px-2 py-1 font-medium">Size</th>
              <th className="px-2 py-1 font-medium">Decode</th>
              <th className="px-2 py-1 font-medium">Notes</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const collision = COLLISION[item.collision]
              return (
                <tr key={item.photo_id} className="border-t border-line">
                  <td className="px-2 py-1 font-mono">{item.filename}</td>
                  <td className="px-2 py-1 font-mono text-strong">{item.output_name}</td>
                  <td className="px-2 py-1 font-mono">
                    {item.width}×{item.height}
                  </td>
                  <td className="px-2 py-1">{item.decode === 'half' ? 'half size' : 'full size'}</td>
                  <td className="px-2 py-1">
                    <span className="flex flex-wrap gap-1">
                      {item.collision !== 'new' && <Chip tone={collision.tone}>{collision.label}</Chip>}
                      {item.warnings.map((w) => (
                        <Chip key={w} tone="warn">
                          {w}
                        </Chip>
                      ))}
                    </span>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
