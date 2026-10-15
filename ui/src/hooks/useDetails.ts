import { rememberedToggle } from './rememberedToggle'

/** Detection details drawn on photos (what was found, with confidence): on by default, remembered per browser,
 * shared by the review and the Photo view's AI Analysis tab (Phase 6c feedback). */
const details = rememberedToggle({ storageKey: 'photoedit.details', defaultOn: true, hotkey: 'd' })

/** The details setting and a toggle. With `key`, the D key toggles it too (not while typing in a field). */
export const useDetails = details.useToggle

/** For tests: forget the remembered setting and start from storage again. */
export const resetDetailsForTests = details.resetForTests
