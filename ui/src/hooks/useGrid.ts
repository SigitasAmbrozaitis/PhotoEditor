import { useCallback, useEffect, useSyncExternalStore } from 'react'

/** The 3×3 rule-of-thirds grid (P6b.13): on or off, remembered per browser, shared by every view showing it. */
const KEY = 'photoedit.grid'
const listeners = new Set<() => void>()

function read(): boolean {
  try {
    return window.localStorage.getItem(KEY) === 'on'
  } catch {
    return false // storage blocked: the grid just starts off
  }
}

function write(on: boolean) {
  try {
    window.localStorage.setItem(KEY, on ? 'on' : 'off')
  } catch {
    // not remembered, but still toggled for this page
  }
  current = on
  listeners.forEach((l) => l())
}

let current = read()

function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** The grid setting and a toggle. With `key`, the G key toggles it too (not while typing in a field). */
export function useGrid({ key = false }: { key?: boolean } = {}): [boolean, () => void] {
  const on = useSyncExternalStore(subscribe, () => current)
  const toggle = useCallback(() => write(!current), [])
  useEffect(() => {
    if (!key) return
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      if (target?.closest('input, select, textarea') || e.ctrlKey || e.metaKey || e.altKey) return
      if (e.key === 'g' || e.key === 'G') {
        e.preventDefault()
        toggle()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [key, toggle])
  return [on, toggle]
}

/** For tests: forget the remembered setting and start from storage again. */
export function resetGridForTests() {
  current = read()
  listeners.forEach((l) => l())
}
