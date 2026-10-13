import { Check } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useCreateJob, useStyles } from '../../api/queries'
import { Button, Dialog, ErrorState, Loading, Switch } from '../../components/ui'
import { cn } from '../../lib/cn'
import { DestinationField } from '../export/DestinationField'
import { ExportPlanTable } from '../export/ExportPlanTable'
import { useDestinationStatus, useExportRequest } from '../export/useExportPlan'
import { PresetPicker } from '../export/PresetPicker'
import { usePresetSettings } from '../export/usePresetSettings'
import { ExportSettingsForm } from '../export/ExportSettingsForm'
import { exportSummary } from '../export/exportSummary'
import { withSubjectFraming } from '../review/reviewWords'
import { SubjectFramingSwitch } from '../review/subjectFraming'

const STEPS = ['Style', 'Export', 'Confirm'] as const
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

/** The full use loop: selected photos → style → export preset → destination → confirm → the style job, then
 * the pre-export review (Phase 6c feedback: the wizard ends in the review instead of exporting directly). */
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
  const [evenOut, setEvenOut] = useState(false)
  const [doExport, setDoExport] = useState(true)
  const [destination, setDestination] = useState('')
  const [customize, setCustomize] = useState(false)
  const [frameOnSubject, setFrameOnSubject] = useState(true)

  const count = photoIds.length
  const style = styles.data?.find((s) => s.id === styleId)
  const { preset } = exportState
  const settings = exportState.settings ? withSubjectFraming(exportState.settings, frameOnSubject) : null
  const status = useDestinationStatus(destination)
  const { request: exportRequest, plan } = useExportRequest(photoIds, preset?.id, doExport ? settings : null, status)
  const exportReady = !doExport || (exportRequest !== null && !plan.isError)
  const canNext = step === 'Style' ? Boolean(styleId) : step === 'Export' ? exportReady : true

  const confirm = () => {
    if (!styleId) return
    if (doExport && exportRequest) {
      // The style is applied first (its own job), then the photos are framed for the review.
      const { photo_ids, preset_id, settings: framed, destination: dest } = exportRequest
      createJob.mutate(
        { kind: 'prepare_export', photo_ids, preset_id, settings: framed, destination: dest, style_id: styleId, even_out: evenOut },
        {
          onSuccess: (job) => {
            onOpenChange(false)
            void navigate(`/reviews/${job.review_id}`)
          },
        },
      )
      return
    }
    createJob.mutate(
      { kind: 'apply_style', photo_ids: photoIds, style_id: styleId, even_out: evenOut },
      {
        onSuccess: (job) => {
          onOpenChange(false)
          void navigate(`/jobs/${job.id}`)
        },
      },
    )
  }

  const back = () => setStep(STEPS[Math.max(0, STEPS.indexOf(step) - 1)] ?? 'Style')
  const next = () => setStep(STEPS[Math.min(STEPS.length - 1, STEPS.indexOf(step) + 1)] ?? 'Confirm')

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
          {step !== 'Confirm' ? (
            <Button variant="primary" disabled={!canNext} onClick={next}>
              Next
            </Button>
          ) : (
            <Button variant="primary" disabled={createJob.isPending || count === 0} onClick={confirm}>
              {doExport ? 'Apply & prepare for review' : 'Apply style'}
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
      {step === 'Style' && (
        <div className="mt-4 flex flex-col gap-1">
          <Switch label="Even out these photos" checked={evenOut} onCheckedChange={setEvenOut} disabled={count < 2} />
          <p className="text-xs text-muted">
            For a series shot in the same light with changing settings: the style's auto exposure brings the photos to
            the group's middle instead of a fixed target. Needs a style with auto exposure.
          </p>
        </div>
      )}

      {step === 'Export' && (
        <div className="flex flex-col gap-4">
          <Switch label="Prepare an export after applying the style" checked={doExport} onCheckedChange={setDoExport} />
          <p className="-mt-3 pl-10 text-xs text-muted">
            The photos are framed as the export will be and the review opens: nothing is written until you export there.
          </p>
          {doExport &&
            (exportState.presets.data && settings ? (
              <>
                <PresetPicker
                  presets={exportState.presets.data}
                  value={preset?.id}
                  modified={exportState.modified}
                  onChange={exportState.choosePreset}
                />
                <SubjectFramingSwitch settings={settings} on={frameOnSubject} onChange={setFrameOnSubject} />
                <DestinationField value={destination} onChange={setDestination} status={status} />
                {exportRequest && <ExportPlanTable plan={plan} />}
                <button
                  type="button"
                  className="self-start text-xs text-accent hover:underline"
                  onClick={() => setCustomize((v) => !v)}
                >
                  {customize ? 'Hide export settings' : 'Customize export settings…'}
                </button>
                {customize && (
                  <ExportSettingsForm
                    value={settings}
                    onChange={(next) => {
                      setFrameOnSubject(next.aspect.anchor === 'subject')
                      exportState.editSettings(next)
                    }}
                  />
                )}
                <p className="font-mono text-xs text-muted">{exportSummary(settings, destination)}</p>
              </>
            ) : (
              <Loading />
            ))}
        </div>
      )}

      {step === 'Confirm' && (
        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-muted">Photos</dt>
          <dd>{count}</dd>
          <dt className="text-muted">Style</dt>
          <dd>
            {style?.name}
            {evenOut && ', evened out as a group'}
          </dd>
          <dt className="text-muted">Then</dt>
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
              'No export (the style is applied only)'
            )}
          </dd>
        </dl>
      )}
      {createJob.isError && <ErrorState error={createJob.error} />}
    </Dialog>
  )
}
