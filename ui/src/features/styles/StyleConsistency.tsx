/** The consistency report: how far apart the photos come out, before vs. after the style. */
import { Gauge } from 'lucide-react'
import { useStyleReport } from '../../api/queries'
import type { ReportPhoto, Spread, Style } from '../../api/types'
import { Button, ErrorState, Spinner } from '../../components/ui'
import { cn } from '../../lib/cn'
import { Section } from './StyleSection'
import { OUTLIER_STOPS } from './styleWords'

const MEASURES: Record<string, { label: string; unit: string; digits: number }> = {
  middle: { label: 'Middle brightness', unit: ' stops', digits: 2 },
  white: { label: 'White point', unit: ' stops', digits: 2 },
  temperature: { label: 'Temperature', unit: ' K', digits: 0 },
  tint: { label: 'Tint', unit: '', digits: 1 },
}

export function StyleConsistency({ style }: { style: Style }) {
  const report = useStyleReport(style.id)
  const source = style.test_photo_ids.length
    ? `the test set (${style.test_photo_ids.length})`
    : `the photos using it (${style.photo_count})`
  const empty = style.test_photo_ids.length === 0 && style.photo_count === 0

  return (
    <Section
      title="Consistency"
      actions={
        <Button size="sm" onClick={() => report.mutate(undefined)} disabled={empty || report.isPending}>
          <Gauge className="size-3.5" aria-hidden /> Measure on {source}
        </Button>
      }
    >
      {empty && <p className="text-sm text-muted">Add a test set or apply the style to photos to measure it.</p>}
      {report.isPending && <Spinner label="Measuring" />}
      {report.isError && <ErrorState error={report.error} />}
      {report.data && report.data.look_hash !== style.look_hash && (
        <p className="text-xs text-warn">The style changed since this report: measure again.</p>
      )}
      {report.data && (
        <div className="flex flex-col gap-3">
          <SpreadTable spread={report.data.spread} />
          <PhotoTable photos={report.data.photos} />
        </div>
      )}
    </Section>
  )
}

function SpreadTable({ spread }: { spread: Spread[] }) {
  return (
    <table className="w-full max-w-2xl text-sm" aria-label="Spread before and after">
      <thead>
        <tr className="border-b border-line text-left text-xs text-muted">
          <th className="py-1.5 font-medium">Spread (smaller = more consistent)</th>
          <th className="py-1.5 text-right font-medium">Typical deviation</th>
          <th className="py-1.5 text-right font-medium">Range</th>
        </tr>
      </thead>
      <tbody>
        {spread.map((s) => {
          const m = MEASURES[s.measure] ?? { label: s.measure, unit: '', digits: 2 }
          const fmt = (v: number) => `${v.toFixed(m.digits)}${m.unit}`
          return (
            <tr key={s.measure} className="border-b border-line/50">
              <td className="py-1.5">{m.label}</td>
              <td className="py-1.5 text-right font-mono tabular-nums">
                {fmt(s.before_mad)} → <Better before={s.before_mad} after={s.after_mad} text={fmt(s.after_mad)} />
              </td>
              <td className="py-1.5 text-right font-mono tabular-nums">
                {fmt(s.before_range)} → <Better before={s.before_range} after={s.after_range} text={fmt(s.after_range)} />
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function Better({ before, after, text }: { before: number; after: number; text: string }) {
  return <span className={cn(after < before ? 'text-ok' : after > before ? 'text-err' : undefined)}>{text}</span>
}

function PhotoTable({ photos }: { photos: ReportPhoto[] }) {
  const sorted = [...photos].sort((a, b) => Math.abs(b.deviation) - Math.abs(a.deviation))
  const fmt = (v: number | null) => (v === null ? '—' : v.toFixed(2))
  return (
    <table className="w-full text-sm" aria-label="Photos in the report">
      <thead>
        <tr className="border-b border-line text-left text-xs text-muted">
          <th className="py-1.5 font-medium">Photo</th>
          <th className="py-1.5 text-right font-medium">Middle before → after</th>
          <th className="py-1.5 text-right font-medium">From the median</th>
          <th className="py-1.5 pl-4 font-medium">What the rules did</th>
        </tr>
      </thead>
      <tbody>
        {sorted.map((p) => {
          const outlier = Math.abs(p.deviation) >= OUTLIER_STOPS
          return (
            <tr key={p.photo_id} className={cn('border-b border-line/50', outlier && 'bg-err/10')}>
              <td className="py-1.5">
                {p.filename}
                {outlier && <span className="ml-2 text-[11px] text-err">needs attention</span>}
              </td>
              <td className="py-1.5 text-right font-mono tabular-nums">
                {fmt(p.before.middle)} → {fmt(p.after.middle)}
              </td>
              <td className="py-1.5 text-right font-mono tabular-nums">
                {p.deviation > 0 ? '+' : ''}
                {p.deviation.toFixed(2)}
              </td>
              <td className="py-1.5 pl-4 text-xs text-muted">
                {p.rules.map((r) => (
                  <div key={r.type}>
                    {r.summary}
                    {r.note && <span className="text-warn"> ({r.note})</span>}
                  </div>
                ))}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
