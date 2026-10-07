import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

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
