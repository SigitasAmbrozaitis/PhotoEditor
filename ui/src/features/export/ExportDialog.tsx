import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useCreateJob } from '../../api/queries'
import { Button, Dialog, ErrorState, Loading } from '../../components/ui'
import { DestinationField } from './DestinationField'
import { ExportSettingsForm } from './ExportSettingsForm'
import { exportSummary } from './exportSummary'
import { PresetPicker } from './PresetPicker'
import { usePresetSettings } from './usePresetSettings'

export function ExportDialog({
  open,
  onOpenChange,
  photoIds,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  photoIds: string[]
}) {
  const navigate = useNavigate()
  const createJob = useCreateJob()
  const { presets, preset, settings, modified, choosePreset, editSettings } = usePresetSettings()
  const [destination, setDestination] = useState('')
  const count = photoIds.length

  const submit = () => {
    if (!settings) return
    createJob.mutate(
      { kind: 'export', photo_ids: photoIds, preset_id: preset?.id ?? null, settings, destination: destination.trim() },
      {
        onSuccess: (job) => {
          onOpenChange(false)
          void navigate(`/jobs/${job.id}`)
        },
      },
    )
  }

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Export ${count} photo${count === 1 ? '' : 's'}`}
      description="Writes new files to the destination folder. Originals are never changed."
      width="max-w-3xl"
      footer={
        <>
          {settings && (
            <p data-testid="export-summary" className="mr-auto truncate font-mono text-xs text-muted">
              {exportSummary(settings, destination)}
            </p>
          )}
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="primary"
            disabled={!settings || count === 0 || !destination.trim() || createJob.isPending}
            onClick={submit}
          >
            Export
          </Button>
        </>
      }
    >
      {presets.isError && <ErrorState error={presets.error} />}
      {!settings || !presets.data ? (
        <Loading />
      ) : (
        <div className="flex flex-col gap-4">
          {count === 0 && (
            <p className="rounded border border-warn/40 bg-warn/10 p-2 text-xs text-warn">
              No photos selected. Select photos in the Library first.
            </p>
          )}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <PresetPicker presets={presets.data} value={preset?.id} modified={modified} onChange={choosePreset} />
            <p className="self-end pb-1.5 text-xs text-muted">{preset?.description}</p>
          </div>
          <DestinationField value={destination} onChange={setDestination} />
          <ExportSettingsForm value={settings} onChange={editSettings} />
          {createJob.isError && <ErrorState error={createJob.error} />}
        </div>
      )}
    </Dialog>
  )
}
