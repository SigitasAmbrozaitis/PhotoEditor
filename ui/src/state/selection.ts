/** Photo selection shared by the Library, Photo view and the action dialogs. */
import { createContext, useContext } from 'react'

export interface Selection {
  /** Selected photo ids, in the order they were selected. */
  ids: string[]
  has: (id: string) => boolean
  /** Plain click: select only this photo. */
  selectOnly: (id: string) => void
  /** Ctrl/Cmd click: add or remove one photo. */
  toggle: (id: string) => void
  /** Shift click: select the range between the last clicked photo and this one, in the given display order. */
  selectRange: (orderedIds: string[], id: string) => void
  selectAll: (orderedIds: string[]) => void
  set: (ids: string[]) => void
  clear: () => void
}

export const SelectionContext = createContext<Selection | null>(null)

export function useSelection(): Selection {
  const ctx = useContext(SelectionContext)
  if (!ctx) throw new Error('useSelection must be used inside <SelectionProvider>')
  return ctx
}
