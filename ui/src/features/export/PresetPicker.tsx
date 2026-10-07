import type { ExportPreset } from '../../api/types'
import { Field, Select } from '../../components/ui'

export function PresetPicker({
  presets,
  value,
  modified,
  onChange,
}: {
  presets: ExportPreset[]
  value: string | undefined
  modified: boolean
  onChange: (id: string) => void
}) {
  return (
    <Field label={modified ? 'Export preset (modified)' : 'Export preset'}>
      <Select value={value} onChange={(e) => onChange(e.target.value)} aria-label="Export preset">
        {presets.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </Select>
    </Field>
  )
}
