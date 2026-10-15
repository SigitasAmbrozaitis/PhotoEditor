import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

// The suite runs its files in parallel workers; on a busy machine a role query over a big screen (the preset form)
// can take longer than Testing Library's default 1 s wait, which made findBy* fail only in the full run.
configure({ asyncUtilTimeout: 5000 })

// jsdom lacks a few browser APIs that layout code and Radix primitives use.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver
// Guarded: some tests run in the plain Node environment, which has no DOM.
if (typeof Element !== 'undefined') {
  Element.prototype.scrollIntoView ??= () => {}
  Element.prototype.hasPointerCapture ??= () => false
  Element.prototype.releasePointerCapture ??= () => {}
}

afterEach(() => {
  cleanup()
  if (typeof sessionStorage !== 'undefined') sessionStorage.clear()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})
