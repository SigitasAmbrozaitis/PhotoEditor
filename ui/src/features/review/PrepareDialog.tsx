import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router'
import { useCreateJob, useJob, useStyles } from '../../api/queries'
import { Button, Dialog, ErrorState, Field, Loading, ProgressBar, Select, Switch } from '../../components/ui'
import { DestinationField } from '../export/DestinationField'
import { ExportSettingsForm } from '../export/ExportSettingsForm'
import { exportSummary } from '../export/exportSummary'
import { PresetPicker } from '../export/PresetPicker'
import { useDestinationStatus } from '../export/useExportPlan'
import { usePresetSettings } from '../export/usePresetSettings'

/** Prepare an export for review (Phase 6c): an optional style, the export settings and the destination, then a
 * job frames every photo and the review opens. */
export function PrepareDialog({
  open,
  onOpenChange,
  photoIds,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  photoIds: string[]
}) {
  const navigate = useNavigate()
  const styles = useStyles()
  const createJob = useCreateJob()
  const { presets, preset, settings, modified, choosePreset, editSettings } = usePresetSettings()
  const [styleId, setStyleId] = useState('')
  const [evenOut, setEvenOut] = useState(false)
  const [destination, setDestination] = useState('')
  const [customize, setCustomize] = useState(false)
  const [jobId, setJobId] = useState<string>()
  const status = useDestinationStatus(destination)
  const job = useJob(jobId)
  const count = photoIds.length
  const framesSubjects = settings?.aspect.ratio != null && settings.aspect.anchor === 'subject'

  // The review opens once its job is done.
  const reviewId = job.data?.status === 'done' ? job.data.review_id : null
  useEffect(() => {
    if (!reviewId) return
    onOpenChange(false)
    void navigate(`/reviews/${reviewId}`)
  }, [reviewId, navigate, onOpenChange])

  const prepare = () => {
    if (!settings || !status?.ok) return
    createJob.mutate(
      {
        kind: 'prepare_export',
        photo_ids: photoIds,
        style_id: styleId || null,
        even_out: Boolean(styleId) && evenOut,
        preset_id: preset?.id ?? null,
        settings,
        destination: status.path,
      },
      { onSuccess: (created) => setJobId(created.id) },
    )
  }

  const running = jobId !== undefined
  const failed = job.data && (job.data.status === 'failed' || job.data.status === 'cancelled')

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Prepare ${count} photo${count === 1 ? '' : 's'} for export`}
      description="Frames every photo as the export will and lists the ones worth a look before anything is written."
      width="max-w-3xl"
      footer={
        <>
          {settings && !running && (
            <p data-testid="prepare-summary" className="mr-auto truncate font-mono text-xs text-muted">
              {exportSummary(settings, destination)}
            </p>
          )}
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {running ? 'Close' : 'Cancel'}
          </Button>
          {!running && (
            <Button
              variant="primary"
              disabled={!settings || !status?.ok || count === 0 || createJob.isPending}
              onClick={prepare}
            >
              Prepare
            </Button>
          )}
        </>
      }
    >
      {running ? (
        <div className="flex flex-col gap-3" data-testid="prepare-progress">
          <p className="text-sm">
            {job.data?.status === 'queued' ? 'Waiting for the style to be applied…' : 'Finding subjects and framing the photos…'}
          </p>
          <ProgressBar value={job.data?.progress ?? 0} label="Preparing" />
          <p className="text-xs text-muted">
            {job.data ? `${job.data.completed} of ${job.data.total}` : ''} · Detection takes a few seconds per photo
            the first time. You can close this; the review appears under Reviews when it is ready.
          </p>
          {failed && <ErrorState error={new Error(job.data?.summary ?? `The job ${job.data?.status}.`)} />}
        </div>
      ) : presets.isError ? (
        <ErrorState error={presets.error} />
      ) : !settings || !presets.data ? (
        <Loading />
      ) : (
        <div className="flex flex-col gap-4">
          {count === 0 && (
            <p className="rounded border border-warn/40 bg-warn/10 p-2 text-xs text-warn">
              No photos selected. Select photos in the Library first.
            </p>
          )}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <Field label="Style (applied first)">
              <Select aria-label="Style" value={styleId} onChange={(e) => setStyleId(e.target.value)}>
                <option value="">No style: keep the photos' edits</option>
                {styles.data?.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </Select>
            </Field>
            <div className="flex items-end pb-1.5">
              <Switch
                label="Even out these photos"
                checked={evenOut}
                onCheckedChange={setEvenOut}
                disabled={!styleId || count < 2}
              />
            </div>
          </div>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <PresetPicker presets={presets.data} value={preset?.id} modified={modified} onChange={choosePreset} />
            <p className="self-end pb-1.5 text-xs text-muted">{preset?.description}</p>
          </div>
          {!framesSubjects && (
            <p className="text-xs text-muted">
              These settings don't frame subjects, so every photo will be Ready: the review only shows the framing.
            </p>
          )}
          <DestinationField value={destination} onChange={setDestination} status={status} />
          <button
            type="button"
            className="self-start text-xs text-accent hover:underline"
            onClick={() => setCustomize((v) => !v)}
          >
            {customize ? 'Hide export settings' : 'Customize export settings…'}
          </button>
          {customize && <ExportSettingsForm value={settings} onChange={editSettings} />}
        </div>
      )}
      {createJob.isError && <ErrorState error={createJob.error} />}
    </Dialog>
  )
}
