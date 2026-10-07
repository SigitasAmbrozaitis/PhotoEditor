import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { SelectionContext, type Selection } from './selection'

const STORAGE_KEY = 'photoedit.selection'

function loadStored(): string[] {
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? '[]')
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}

/** Selection survives page reloads within the browser tab (sessionStorage), not across tabs or restarts. */
export function SelectionProvider({ children, initial }: { children: ReactNode; initial?: string[] }) {
  const [ids, setIds] = useState<string[]>(() => initial ?? loadStored())
  const [anchor, setAnchor] = useState<string | null>(ids[0] ?? null)

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(ids))
    } catch {
      // Storage can be unavailable (private mode, quota); selection still works in memory.
    }
  }, [ids])

  const selectOnly = useCallback((id: string) => {
    setIds([id])
    setAnchor(id)
  }, [])

  const toggle = useCallback((id: string) => {
    setIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
    setAnchor(id)
  }, [])

  const selectRange = useCallback(
    (orderedIds: string[], id: string) => {
      const from = anchor === null ? -1 : orderedIds.indexOf(anchor)
      const to = orderedIds.indexOf(id)
      if (from === -1 || to === -1) {
        setIds([id])
        setAnchor(id)
        return
      }
      const [start, end] = from <= to ? [from, to] : [to, from]
      setIds(orderedIds.slice(start, end + 1))
    },
    [anchor],
  )

  const value = useMemo<Selection>(() => {
    const set = new Set(ids)
    return {
      ids,
      has: (id) => set.has(id),
      selectOnly,
      toggle,
      selectRange,
      selectAll: (orderedIds) => setIds([...orderedIds]),
      set: (next) => setIds([...next]),
      clear: () => {
        setIds([])
        setAnchor(null)
      },
    }
  }, [ids, selectOnly, toggle, selectRange])

  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>
}
