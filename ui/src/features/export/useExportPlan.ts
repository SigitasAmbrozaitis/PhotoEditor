import { useMemo } from 'react'
import { useDestinationCheck, useExportPlan } from '../../api/queries'
import type { DestinationCheck, ExportRequest, ExportSettings } from '../../api/types'
import { useDebounced } from '../../lib/useDebounced'

/** The export request for the current dialog state (null until it can be sent) and its dry-run plan. */
export function useExportRequest(
  photoIds: string[],
  presetId: string | undefined,
  settings: ExportSettings | null,
  destination: DestinationCheck | undefined,
) {
  const request: ExportRequest | null =
    settings && destination?.ok && photoIds.length > 0
      ? { kind: 'export', photo_ids: photoIds, preset_id: presetId ?? null, settings, destination: destination.path }
      : null
  // Settings change on every keystroke; plan once they settle (keyed by content, not object identity).
  const key = useDebounced(request ? JSON.stringify(request) : '', 300)
  const planned = useMemo(() => (key ? (JSON.parse(key) as ExportRequest) : null), [key])
  const plan = useExportPlan(planned)
  return { request, plan }
}

/** Whether the typed destination may be used: undefined while it's being checked or empty. */
export function useDestinationStatus(value: string): DestinationCheck | undefined {
  const path = useDebounced(value.trim())
  const check = useDestinationCheck(path)
  return path === value.trim() ? check.data : undefined
}
