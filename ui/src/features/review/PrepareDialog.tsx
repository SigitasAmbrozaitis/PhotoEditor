import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useCreateJob, useStyles } from '../../api/queries'
import { Button, Dialog, ErrorState, Field, Loading, Select, Switch } from '../../components/ui'
import { DestinationField } from '../export/DestinationField'
import { ExportSettingsForm } from '../export/ExportSettingsForm'
import { exportSummary } from '../export/exportSummary'
import { PresetPicker } from '../export/PresetPicker'
import { useDestinationStatus } from '../export/useExportPlan'
import { usePresetSettings } from '../export/usePresetSettings'
import { withSubjectFraming } from './reviewWords'
import { SubjectFramingSwitch } from './subjectFraming'

/** Prepare an export for review (Phase 6c): an optional style, the export settings and the destination, then a
 * job frames every photo; the review opens at once and shows the job's progress until it is ready. */
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
  const { presets, preset, settings: presetSettings, modified, choosePreset, editSettings } = usePresetSettings()
  const [styleId, setStyleId] = useState('')
  const [evenOut, setEvenOut] = useState(false)
  const [frameOnSubject, setFrameOnSubject] = useState(true)
  const [destination, setDestination] = useState('')
  const [customize, setCustomize] = useState(false)
  const status = useDestinationStatus(destination)
  const count = photoIds.length
  const settings = presetSettings ? withSubjectFraming(presetSettings, frameOnSubject) : null

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
      {
        onSuccess: (job) => {
          onOpenChange(false)
          void navigate(`/reviews/${job.review_id}`)
        },
      },
    )
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Prepare ${count} photo${count === 1 ? '' : 's'} for export`}
      description="Frames every photo as the export will and lists the ones worth a look before anything is written."
      width="max-w-3xl"
      footer={
        <>
          {settings && (
            <p data-testid="prepare-summary" className="mr-auto truncate font-mono text-xs text-muted">
              {exportSummary(settings, destination)}
            </p>
          )}
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={!settings || !status?.ok || count === 0 || createJob.isPending}
            onClick={prepare}
          >
            Prepare
          </Button>
        </>
      }
    >
      {presets.isError ? (
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
          <SubjectFramingSwitch settings={settings} on={frameOnSubject} onChange={setFrameOnSubject} />
          <DestinationField value={destination} onChange={setDestination} status={status} />
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
                // The anchor chosen in the form decides the switch from then on.
                setFrameOnSubject(next.aspect.anchor === 'subject')
                editSettings(next)
              }}
            />
          )}
        </div>
      )}
      {createJob.isError && <ErrorState error={createJob.error} />}
    </Dialog>
  )
}
