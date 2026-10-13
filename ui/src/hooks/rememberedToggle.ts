import { useCallback, useEffect, useSyncExternalStore } from 'react'

/** An on/off view setting remembered per browser and shared by every component showing it, with a hotkey. */
export function rememberedToggle({ storageKey, defaultOn, hotkey }: { storageKey: string; defaultOn: boolean; hotkey: string }) {
  const listeners = new Set<() => void>()

  function read(): boolean {
    try {
      const stored = window.localStorage.getItem(storageKey)
      return stored === null ? defaultOn : stored === 'on'
    } catch {
      return defaultOn // storage blocked: the default for this page
    }
  }

  let current = read()

  function write(on: boolean) {
    try {
      window.localStorage.setItem(storageKey, on ? 'on' : 'off')
    } catch {
      // not remembered, but still toggled for this page
    }
    current = on
    listeners.forEach((l) => l())
  }

  function subscribe(listener: () => void) {
    listeners.add(listener)
    return () => listeners.delete(listener)
  }

  /** The setting and a toggle. With `key`, the hotkey toggles it too (not while typing in a field). */
  function useToggle({ key = false }: { key?: boolean } = {}): [boolean, () => void] {
    const on = useSyncExternalStore(subscribe, () => current)
    const toggle = useCallback(() => write(!current), [])
    useEffect(() => {
      if (!key) return
      const onKey = (e: KeyboardEvent) => {
        const target = e.target as HTMLElement | null
        if (target?.closest('input, select, textarea') || e.ctrlKey || e.metaKey || e.altKey) return
        if (e.key.toLowerCase() === hotkey) {
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
  function resetForTests() {
    current = read()
    listeners.forEach((l) => l())
  }

  return { useToggle, resetForTests }
}
