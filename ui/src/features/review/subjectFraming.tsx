import type { ExportSettings } from '../../api/types'
import { Switch } from '../../components/ui'

/** The review's "Frame the crop on the subject" switch (on by default, Phase 6c feedback), with what it means. */
export function SubjectFramingSwitch({
  settings,
  on,
  onChange,
}: {
  settings: ExportSettings
  on: boolean
  onChange: (on: boolean) => void
}) {
  const cropped = settings.aspect.ratio !== null
  return (
    <div className="flex flex-col gap-1">
      <Switch label="Frame the crop on the subject" checked={cropped && on} disabled={!cropped} onCheckedChange={onChange} />
      <p className="pl-10 text-xs text-muted">
        {!cropped
          ? "This preset keeps each photo's own aspect, so there is no crop to frame: every photo will be Ready."
          : on
            ? 'Each photo is cropped around what detection finds (or the subject you set); the doubtful ones are listed to check.'
            : 'Crops are centered and subjects are not looked at: every photo will be Ready.'}
      </p>
    </div>
  )
}
