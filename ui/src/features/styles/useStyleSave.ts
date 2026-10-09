/** Saving a change to a style: optimistic versioning, with a clear state when someone else saved first. */
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError } from '../../api/client'
import { queryKeys, useUpdateStyle } from '../../api/queries'
import type { Style, StyleUpdate } from '../../api/types'

export type StyleChanges = Omit<StyleUpdate, 'expected_version' | 'change_note'>

export interface StyleSave {
  /** Save ``changes`` on top of the version on screen. Resolves to true when saved. */
  save: (changes: StyleChanges, note?: string) => Promise<boolean>
  saving: boolean
  /** Another change came first (HTTP 409): reload, then redo the edit. */
  conflict: boolean
  error: string | null
  reload: () => void
}

export function useStyleSave(style: Style): StyleSave {
  const client = useQueryClient()
  const update = useUpdateStyle(style.id)
  const [conflict, setConflict] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const save = async (changes: StyleChanges, note = '') => {
    setError(null)
    try {
      await update.mutateAsync({ ...changes, expected_version: style.version, change_note: note })
      return true
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) setConflict(true)
      else setError(e instanceof Error ? e.message : 'Saving failed.')
      return false
    }
  }

  const reload = () => {
    setConflict(false)
    void client.invalidateQueries({ queryKey: queryKeys.style(style.id) })
  }

  return { save, saving: update.isPending, conflict, error, reload }
}
