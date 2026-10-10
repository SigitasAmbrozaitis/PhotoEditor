import { useState } from 'react'
import { useCreatePreset } from '../../api/queries'
import type { ExportPreset, ExportSettings } from '../../api/types'
import { Button, ErrorState, TextInput } from '../../components/ui'

/** "Save as preset…": keeps the dialog's modified settings as a new custom preset. */
export function SaveAsPreset({
  settings,
  base,
  onSaved,
}: {
  settings: ExportSettings
  base: ExportPreset | undefined
  onSaved: (preset: ExportPreset) => void
}) {
  const create = useCreatePreset()
  const [name, setName] = useState<string | null>(null)
  if (name === null) {
    return (
      <Button size="sm" variant="ghost" onClick={() => setName(base ? `${base.name} (custom)` : 'My preset')}>
        Save as preset…
      </Button>
    )
  }
  const save = () =>
    create.mutate(
      { name: name.trim(), description: base?.description ?? '', target: base?.target ?? 'custom', settings },
      {
        onSuccess: (preset) => {
          setName(null)
          onSaved(preset)
        },
      },
    )
  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <TextInput
          autoFocus
          aria-label="Preset name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && name.trim() && save()}
        />
        <Button size="sm" variant="primary" disabled={!name.trim() || create.isPending} onClick={save}>
          Save preset
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setName(null)}>
          Cancel
        </Button>
      </div>
      {create.isError && <ErrorState error={create.error} />}
    </div>
  )
}
