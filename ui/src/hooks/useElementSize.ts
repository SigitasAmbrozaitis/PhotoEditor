import { useLayoutEffect, useState, type RefObject } from 'react'

/** Current content-box size of an element, updated on resize. */
export function useElementSize(ref: RefObject<HTMLElement | null>): { width: number; height: number } {
  const [size, setSize] = useState({ width: 0, height: 0 })

  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    const update = () => setSize({ width: el.clientWidth, height: el.clientHeight })
    update()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(update)
    observer.observe(el)
    return () => observer.disconnect()
  }, [ref])

  return size
}

/** Largest size with the given aspect ratio that fits inside the box. */
export function fitInside(box: { width: number; height: number }, aspect: number): { width: number; height: number } {
  if (box.width <= 0 || box.height <= 0 || aspect <= 0) return { width: 0, height: 0 }
  const width = Math.min(box.width, box.height * aspect)
  return { width: Math.floor(width), height: Math.floor(width / aspect) }
}
