/** Every saved version of the style: what changed, the two side by side on the test set, and revert. */
import { History, RotateCcw } from 'lucide-react'
import { useState } from 'react'
import { imageUrls } from '../../api/client'
import { useRevertStyle, useStyleDiff, useStyleHistory } from '../../api/queries'
import type { Style, StyleDiff } from '../../api/types'
import { Button, ErrorState, Spinner, Switch } from '../../components/ui'
import { cn } from '../../lib/cn'
import { Section } from './StyleSection'
import { parameterLabel, parameterValue } from './parameterFormat'

export function StyleHistory({ style }: { style: Style }) {
  const history = useStyleHistory(style.id)
  const revert = useRevertStyle(style.id)
  const [older, setOlder] = useState<number>()
  const [compare, setCompare] = useState(false)
  const versions = history.data ?? []
  const a = older ?? versions[1]?.version
  const diff = useStyleDiff(style.id, a, style.version)

  return (
    <Section title={`History (${versions.length} version${versions.length === 1 ? '' : 's'})`}>
      {history.isLoading && <Spinner />}
      {history.isError && <ErrorState error={history.error} />}
      <ul className="flex flex-col divide-y divide-line/50 text-sm" aria-label="Versions">
        {versions.map((v) => {
          const current = v.version === style.version
          return (
            <li key={v.version} className={cn('flex items-center gap-3 py-1.5', v.version === a && 'bg-raised/50')}>
              <span className="w-10 font-mono">v{v.version}</span>
              <span className="w-36 text-xs text-muted">{new Date(v.updated_at).toLocaleString()}</span>
              <span className="flex-1">{v.change_note || <span className="text-muted">—</span>}</span>
              {current ? (
                <span className="text-xs text-muted">current</span>
              ) : (
                <>
                  <Button size="sm" variant="ghost" onClick={() => setOlder(v.version)} aria-pressed={v.version === a}>
                    <History className="size-3.5" aria-hidden /> Compare
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={revert.isPending}
                    onClick={() => revert.mutate({ version: v.version, expected_version: style.version })}
                  >
                    <RotateCcw className="size-3.5" aria-hidden /> Bring back
                  </Button>
                </>
              )}
            </li>
          )
        })}
      </ul>
      {revert.isError && <ErrorState error={revert.error} />}
      {a !== undefined && diff.data && (
        <div className="flex flex-col gap-2 rounded border border-line p-3">
          <DiffView diff={diff.data} />
          {style.test_photo_ids.length > 0 && (
            <Switch label={`Compare v${a} and v${style.version} on the test set`} checked={compare} onCheckedChange={setCompare} />
          )}
          {compare && <CompareGrid style={style} older={a} />}
        </div>
      )}
    </Section>
  )
}

function DiffView({ diff }: { diff: StyleDiff }) {
  if (!diff.values.length && !diff.rules.length && !diff.fields.length) {
    return <p className="text-sm text-muted">No differences between v{diff.a} and v{diff.b}.</p>
  }
  const show = (name: string, v: unknown) => (v === null || v === undefined ? 'not set' : parameterValue(name, v))
  return (
    <div className="flex flex-col gap-1 text-sm">
      <p className="text-xs text-muted">
        v{diff.a} → v{diff.b}
        {diff.same_look && ' (same look)'}
      </p>
      {diff.values.map((c) => (
        <div key={c.name}>
          {parameterLabel(c.name)}: <span className="font-mono">{show(c.name, c.before)}</span> →{' '}
          <span className="font-mono">{show(c.name, c.after)}</span>
        </div>
      ))}
      {diff.rules.map((r) => (
        <div key={r.type}>
          Rule {r.type.replace('_', ' ')}: {r.before ? 'changed' : 'added'}
          {!r.after && ' → removed'}
        </div>
      ))}
      {diff.fields.length > 0 && <div className="text-xs text-muted">Also changed: {diff.fields.join(', ')}</div>}
    </div>
  )
}

function CompareGrid({ style, older }: { style: Style; older: number }) {
  return (
    <ul className="grid grid-cols-[repeat(auto-fill,minmax(320px,1fr))] gap-3" aria-label="Version comparison">
      {style.test_photo_ids.map((id) => (
        <li key={id} className="grid grid-cols-2 gap-1">
          {[older, style.version].map((version) => (
            <figure key={version} className="relative">
              <img
                src={imageUrls.styleVersion(style.id, version, id, 480)}
                alt={`${id} with version ${version}`}
                className="aspect-[3/2] w-full rounded bg-raised object-cover"
              />
              <span className="absolute top-1 left-1 rounded bg-black/70 px-1.5 text-[11px]">v{version}</span>
            </figure>
          ))}
        </li>
      ))}
    </ul>
  )
}
