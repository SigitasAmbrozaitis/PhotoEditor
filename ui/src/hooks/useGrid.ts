import { rememberedToggle } from './rememberedToggle'

/** The 3×3 rule-of-thirds grid (P6b.13): on or off, remembered per browser, shared by every view showing it. */
const grid = rememberedToggle({ storageKey: 'photoedit.grid', defaultOn: false, hotkey: 'g' })

/** The grid setting and a toggle. With `key`, the G key toggles it too (not while typing in a field). */
export const useGrid = grid.useToggle

/** For tests: forget the remembered setting and start from storage again. */
export const resetGridForTests = grid.resetForTests
