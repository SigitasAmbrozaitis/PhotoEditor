import { useState } from 'react'
import { usePresets } from '../../api/queries'
import type { ExportPreset, ExportSettings } from '../../api/types'

/** Preset choice plus (possibly edited) settings, shared by the Export dialog and the Apply flow. */
export function usePresetSettings(initialPresetId = 'instagram-portrait') {
  const presets = usePresets()
  const [presetId, setPresetId] = useState(initialPresetId)
  // null = use the chosen preset's settings unchanged.
  const [edited, setEdited] = useState<ExportSettings | null>(null)
  const preset: ExportPreset | undefined = presets.data?.find((p) => p.id === presetId) ?? presets.data?.[0]
  const settings: ExportSettings | null = edited ?? preset?.settings ?? null

  return {
    presets,
    preset,
    settings,
    modified: edited !== null,
    choosePreset: (id: string) => {
      setPresetId(id)
      setEdited(null)
    },
    editSettings: (next: ExportSettings) => setEdited(next),
  }
}
