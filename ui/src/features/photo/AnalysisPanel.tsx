import { Eye, EyeOff, ScanSearch, SquareDashedMousePointer } from 'lucide-react'
import { useAnalysis, useDetectNow, useSetSubject, useSubject } from '../../api/queries'
import type { Photo } from '../../api/types'
import { candidateName, candidateText, KIND_NAMES, percent, subjectText } from '../../components/detectionWords'
import { Button, Chip, ErrorState, Loading, Spinner } from '../../components/ui'
import { useDetails } from '../../hooks/useDetails'

const SOURCE_TEXT = {
  detected: 'found by detection',
  manual: 'set by hand (always wins over detection)',
  af_point: 'nothing recognized: the crop follows the camera’s focus point',
  none: 'nothing recognized: crops are centered',
} as const

/** The Photo view's AI Analysis tab (Phase 6c feedback): what detection found in the photo, stored per photo,
 * with its confidence; the boxes are drawn on the photo while this tab is open (Hide details, D). */
export function AnalysisPanel({ photo, onSetSubject }: { photo: Photo; onSetSubject: () => void }) {
  const analysis = useAnalysis(photo.id, true)
  const detect = useDetectNow(photo.id)
  // The upright boxes, to make a candidate the subject (the analysis has them in the edited photo).
  const subject = useSubject(photo.id, Boolean(analysis.data?.detected))
  const setSubject = useSetSubject(photo.id)
  const [details, toggleDetails] = useDetails()

  if (analysis.isError) return <ErrorState error={analysis.error} />
  if (!analysis.data) return <Loading />
  const a = analysis.data
  const busy = detect.isPending || setSubject.isPending

  return (
    <div className="flex flex-col gap-4 p-3 text-xs" data-testid="analysis-panel">
      {!a.detected && a.source !== 'manual' ? (
        <div className="flex flex-col gap-2">
          <p className="text-muted">Not analysed yet. Detection looks for cars, animals, people and faces.</p>
          <Button variant="primary" disabled={busy} onClick={() => detect.mutate()}>
            <ScanSearch className="size-4" aria-hidden /> Detect now
          </Button>
          {detect.isPending && (
            <span className="flex items-center gap-2 text-muted">
              <Spinner className="size-3.5" label="Detecting" /> A few seconds the first time…
            </span>
          )}
        </div>
      ) : (
        <section aria-label="Subject" className="flex flex-col gap-1">
          <h3 className="text-[11px] font-medium tracking-wide text-muted uppercase">Subject</h3>
          <p className="text-sm text-strong" data-testid="analysis-subject">
            {subjectText(a.source, a.kind, a.score)}
          </p>
          <p className="text-muted">{SOURCE_TEXT[a.source]}</p>
          {a.source !== 'none' && !a.box && <p className="text-warn">It is outside the photo’s crop.</p>}
        </section>
      )}

      <div className="flex flex-wrap gap-2">
        <Button size="sm" onClick={onSetSubject} title="Open the crop tool and drag a box around the subject">
          <SquareDashedMousePointer className="size-3.5" aria-hidden /> Set subject
        </Button>
        {a.source === 'manual' && (
          <Button size="sm" variant="ghost" disabled={busy} onClick={() => setSubject.mutate(null)}>
            Use detected
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={toggleDetails} title="Show or hide the boxes on the photo (D)">
          {details ? <EyeOff className="size-3.5" aria-hidden /> : <Eye className="size-3.5" aria-hidden />}
          {details ? 'Hide details' : 'Show details'}
        </Button>
      </div>

      {a.candidates.length > 0 && (
        <section aria-label="Found" className="flex flex-col gap-1">
          <h3 className="text-[11px] font-medium tracking-wide text-muted uppercase">Everything found (best first)</h3>
          <ul className="flex flex-col gap-1">
            {a.candidates.map((c) => (
              <li key={c.index} className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate">
                  {candidateName(c)}
                  {c.recognized && c.label && c.label !== KIND_NAMES[c.kind] && (
                    <span className="text-muted"> ({KIND_NAMES[c.kind]})</span>
                  )}
                </span>
                {c.chosen && <Chip tone="warn">subject</Chip>}
                {!c.recognized && <Chip>guess</Chip>}
                <span className="w-10 text-right font-mono">{percent(c.score)}</span>
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={busy || c.chosen || !subject.data}
                  aria-label={`Use ${candidateText(c)} as the subject`}
                  onClick={() => {
                    const box = subject.data?.candidates[c.index]?.box
                    if (box) setSubject.mutate(box)
                  }}
                >
                  Use
                </Button>
              </li>
            ))}
          </ul>
          <p className="text-muted">
            Confidence is how likely each one is the photo’s main subject. Guesses (what stands out, what is sharp)
            are never chosen on their own.
          </p>
        </section>
      )}

      <section aria-label="Focus point" className="flex flex-col gap-1">
        <h3 className="text-[11px] font-medium tracking-wide text-muted uppercase">Camera focus point</h3>
        <p className="text-muted">
          {a.focus ? 'Shown as a dotted square with a dot.' : 'Not recorded in this photo (or outside its crop).'}
        </p>
      </section>

      {a.notes.length > 0 && (
        <ul className="flex flex-col gap-1 text-warn">
          {a.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      {a.detector && <p className="font-mono text-[10px] break-all text-muted">{a.detector}</p>}
      {detect.isError && <ErrorState error={detect.error} />}
      {setSubject.isError && <ErrorState error={setSubject.error} />}
    </div>
  )
}
