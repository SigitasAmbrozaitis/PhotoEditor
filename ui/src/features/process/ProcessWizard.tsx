import { Check } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useCreateJob, useStyles } from '../../api/queries'
import { Button, Dialog, ErrorState, Loading, Switch } from '../../components/ui'
import { cn } from '../../lib/cn'
import { DestinationField } from '../export/DestinationField'
import { PresetPicker } from '../export/PresetPicker'
import { usePresetSettings } from '../export/usePresetSettings'
import { ExportSettingsForm } from '../export/ExportSettingsForm'
import { exportSummary } from '../export/exportSummary'

const STEPS = ['Style', 'Export', 'Review'] as const
type Step = (typeof STEPS)[number]

function StepIndicator({ current }: { current: Step }) {
  const index = STEPS.indexOf(current)
  return (
    <ol className="mb-4 flex items-center gap-2 text-xs" aria-label="Steps">
      {STEPS.map((step, i) => (
        <li key={step} className="flex items-center gap-2" aria-current={i === index ? 'step' : undefined}>
          <span
            className={cn(
              'flex size-5 items-center justify-center rounded-full border text-[11px]',
              i < index && 'border-accent bg-accent text-white',
              i === index && 'border-accent text-strong',
              i > index && 'border-line text-muted',
            )}
          >
            {i < index ? <Check className="size-3" aria-hidden /> : i + 1}
          </span>
          <span className={i === index ? 'text-strong' : 'text-muted'}>{step}</span>
          {i < STEPS.length - 1 && <span className="h-px w-8 bg-line" />}
        </li>
      ))}
    </ol>
  )
}

/** The full use loop: selected photos → style → export preset → destination → confirm → job. */
export function ProcessWizard({
  open,
  onOpenChange,
  photoIds,
  initialStyleId,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  photoIds: string[]
  initialStyleId?: string
}) {
  const navigate = useNavigate()
  const styles = useStyles()
  const createJob = useCreateJob()
  const exportState = usePresetSettings()
  const [step, setStep] = useState<Step>('Style')
  const [styleId, setStyleId] = useState<string | undefined>(initialStyleId)
  const [doExport, setDoExport] = useState(true)
  const [destination, setDestination] = useState('')
  const [customize, setCustomize] = useState(false)

  const count = photoIds.length
  const style = styles.data?.find((s) => s.id === styleId)
  const { settings, preset } = exportState
  const exportReady = !doExport || (settings !== null && destination.trim() !== '')
  const canNext = step === 'Style' ? Boolean(styleId) : step === 'Export' ? exportReady : true

  const confirm = () => {
    if (!styleId) return
    const request =
      doExport && settings
        ? {
            kind: 'apply_and_export' as const,
            photo_ids: photoIds,
            style_id: styleId,
            preset_id: preset?.id ?? null,
            settings,
            destination: destination.trim(),
          }
        : { kind: 'apply_style' as const, photo_ids: photoIds, style_id: styleId }
    createJob.mutate(request, {
      onSuccess: (job) => {
        onOpenChange(false)
        void navigate(`/jobs/${job.id}`)
      },
    })
  }

  const back = () => setStep(STEPS[Math.max(0, STEPS.indexOf(step) - 1)] ?? 'Style')
  const next = () => setStep(STEPS[Math.min(STEPS.length - 1, STEPS.indexOf(step) + 1)] ?? 'Review')

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Apply style to ${count} photo${count === 1 ? '' : 's'}`}
      description="Applying a style only saves edit settings. Originals are never changed."
      width="max-w-3xl"
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          {step !== 'Style' && <Button onClick={back}>Back</Button>}
          {step !== 'Review' ? (
            <Button variant="primary" disabled={!canNext} onClick={next}>
              Next
            </Button>
          ) : (
            <Button variant="primary" disabled={createJob.isPending || count === 0} onClick={confirm}>
              {doExport ? 'Apply & export' : 'Apply style'}
            </Button>
          )}
        </>
      }
    >
      <StepIndicator current={step} />

      {step === 'Style' &&
        (styles.isLoading ? (
          <Loading />
        ) : styles.isError ? (
          <ErrorState error={styles.error} />
        ) : (
          <div role="radiogroup" aria-label="Style" className="grid grid-cols-2 gap-3 md:grid-cols-3">
            {styles.data?.map((s) => (
              <button
                key={s.id}
                type="button"
                role="radio"
                aria-checked={s.id === styleId}
                onClick={() => setStyleId(s.id)}
                className={cn(
                  'overflow-hidden rounded border text-left transition-colors',
                  s.id === styleId ? 'border-accent ring-2 ring-accent' : 'border-line hover:border-muted',
                )}
              >
                {s.cover_url && <img src={s.cover_url} alt="" className="aspect-[3/2] w-full object-cover" />}
                <div className="p-2">
                  <p className="text-sm font-medium text-strong">{s.name}</p>
                  <p className="line-clamp-2 text-xs text-muted">{s.description}</p>
                </div>
              </button>
            ))}
          </div>
        ))}

      {step === 'Export' && (
        <div className="flex flex-col gap-4">
          <Switch label="Export after applying the style" checked={doExport} onCheckedChange={setDoExport} />
          {doExport &&
            (exportState.presets.data && settings ? (
              <>
                <PresetPicker
                  presets={exportState.presets.data}
                  value={preset?.id}
                  modified={exportState.modified}
                  onChange={exportState.choosePreset}
                />
                <DestinationField value={destination} onChange={setDestination} />
                <button
                  type="button"
                  className="self-start text-xs text-accent hover:underline"
                  onClick={() => setCustomize((v) => !v)}
                >
                  {customize ? 'Hide export settings' : 'Customize export settings…'}
                </button>
                {customize && <ExportSettingsForm value={settings} onChange={exportState.editSettings} />}
                <p className="font-mono text-xs text-muted">{exportSummary(settings, destination)}</p>
              </>
            ) : (
              <Loading />
            ))}
        </div>
      )}

      {step === 'Review' && (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-muted">Photos</dt>
          <dd>{count}</dd>
          <dt className="text-muted">Style</dt>
          <dd>{style?.name}</dd>
          <dt className="text-muted">Export</dt>
          <dd>
            {doExport && settings ? (
              <>
                <span>
                  {preset?.name}
                  {exportState.modified ? ' (modified)' : ''}
                </span>
                <p className="font-mono text-xs text-muted">{exportSummary(settings, destination)}</p>
              </>
            ) : (
              'No export (style is applied only)'
            )}
          </dd>
        </dl>
      )}
      {createJob.isError && <ErrorState error={createJob.error} />}
    </Dialog>
  )
}
