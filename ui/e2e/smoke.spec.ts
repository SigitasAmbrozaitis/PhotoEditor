/**
 * Smoke test of the full use loop against the real backend, on synthetic photos (scripts/e2e_setup.py):
 * open a folder → import → select photos → apply style → export preset → destination → confirm → job finishes,
 * then styles end to end (create from a photo, apply with "even out", edit, revert, delete), and real exports
 * with a custom preset. Styles live in output/e2e/styles (seeded with "E2E Moody"), exports in
 * output/e2e/exports. Screenshots of every screen go to output/screenshots/ for a quick visual review.
 */
import { expect, test, type Page } from '@playwright/test'
import { readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// Absolute, as the destination field needs; inside the project's own (git-ignored) output folder.
const EXPORTS = fileURLToPath(new URL('../../output/e2e/exports', import.meta.url))

const SHOTS = '../output/screenshots'
const PHOTO_COUNT = 10 // 8 scenes + a darker and a brighter shot of the first (a manual series)

async function shot(page: Page, name: string) {
  await page.screenshot({ path: `${SHOTS}/${name}.png` })
}

test('open a folder and import it', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/library$/)
  await expect(page.getByText(/backend v\d/)).toBeVisible()
  await expect(page.getByText('Open a folder')).toBeVisible()
  await expect(page.getByText('DEMO DATA')).toHaveCount(0)
  const field = page.getByRole('textbox', { name: 'Photo folder' })
  await expect(field).toHaveValue(/output\/e2e\/photos$/)
  await shot(page, '01-library-empty')

  // The folder browser starts at the typed folder and shows how many photos it holds.
  await page.getByRole('button', { name: /Browse/ }).click()
  const browser = page.getByRole('dialog', { name: 'Choose a photo folder' })
  await expect(browser.getByText(`${PHOTO_COUNT} photos in this folder`)).toBeVisible()
  await shot(page, '02-folder-browser')
  await browser.getByRole('button', { name: 'Choose this folder' }).click()

  await page.getByRole('button', { name: 'Open', exact: true }).click()
  const tiles = page.getByRole('listbox', { name: 'Photos' }).getByRole('option')
  await expect(tiles).toHaveCount(PHOTO_COUNT, { timeout: 30_000 })
  await expect(page.getByText(`Last import: ${PHOTO_COUNT} photos: ${PHOTO_COUNT} new; 1 other file skipped`)).toBeVisible({
    timeout: 30_000,
  })
  await expect(page.getByText(`${PHOTO_COUNT} photos · 0 selected`)).toBeVisible()
  await shot(page, '03-library-imported')
})

test('full use loop: select → apply style → export → job done', async ({ page }) => {
  await page.goto('/library')
  const tiles = page.getByRole('listbox', { name: 'Photos' }).getByRole('option')
  await expect(tiles).toHaveCount(PHOTO_COUNT)

  // Select photos 1-4 with click + shift-click, then add photo 6 with ctrl-click.
  await tiles.nth(0).click()
  await tiles.nth(3).click({ modifiers: ['Shift'] })
  await tiles.nth(5).click({ modifiers: ['Control'] })
  await expect(page.getByText(/5 selected/)).toBeVisible()
  await shot(page, '04-library-selected')

  // Apply & export wizard.
  await page.getByRole('button', { name: /Apply style/ }).click()
  const dialog = page.getByRole('dialog', { name: 'Apply style to 5 photos' })
  await dialog.getByRole('radio', { name: /E2E Moody/ }).click()
  await shot(page, '05-wizard-style')
  await dialog.getByRole('button', { name: 'Next' }).click()
  await expect(dialog.getByRole('combobox', { name: 'Export preset' })).toHaveValue('instagram-portrait')
  await dialog.getByRole('textbox', { name: 'Destination folder' }).fill(`${EXPORTS}/wizard`)
  await expect(dialog.getByText(/1080×1350 · 4:5 crop · JPEG q92 · sRGB → /)).toBeVisible()
  // The destination is checked and the export planned (5 rows + header) before Next is allowed.
  await expect(dialog.getByRole('table', { name: 'Export plan' }).getByRole('row')).toHaveCount(6)
  await shot(page, '06-wizard-export')
  await dialog.getByRole('button', { name: 'Next' }).click()
  await shot(page, '07-wizard-review')
  await dialog.getByRole('button', { name: 'Apply & export' }).click()

  // Lands on the job, which progresses to done.
  await expect(page).toHaveURL(/\/jobs\/j\d+$/)
  await expect(page.getByRole('heading', { name: /Apply E2E Moody to 5 photos/ })).toBeVisible()
  await shot(page, '08-job-running')
  await expect(page.getByRole('progressbar', { name: 'Job progress' })).toHaveAttribute('aria-valuenow', '100', {
    timeout: 15_000,
  })
  await expect(page.getByText('5 of 5 (100%)')).toBeVisible()
  await shot(page, '09-job-done')

  // The export job starts after the style is applied, and writes real files.
  await page.getByRole('link', { name: /Export 5 photos \(instagram-portrait\)/ }).click()
  await expect(page.getByRole('progressbar', { name: 'Job progress' })).toHaveAttribute('aria-valuenow', '100', {
    timeout: 60_000,
  })
  await expect(page.getByText(/5 exported →/)).toBeVisible()
  await expect(page.getByText(/^1080×1350 · \d+ KB$/)).toHaveCount(5)
  await shot(page, '09b-export-job-done')
  const written = readdirSync(`${EXPORTS}/wizard`)
  expect(written).toHaveLength(5)
  expect(written.every((name) => /^E2E_\d{4}_ig\.jpg$/.test(name))).toBe(true)
})

test('screens render: photo view, styles, presets', async ({ page }) => {
  await page.goto('/library')
  await page.getByRole('listbox', { name: 'Photos' }).getByRole('option', { name: 'E2E_0003.JPG' }).dblclick()
  await expect(page.getByRole('heading', { name: 'E2E_0003.JPG' })).toBeVisible()
  const preview = page.getByRole('img', { name: /E2E_0003.JPG \(after\)/ })
  await expect(preview).toBeVisible()
  await expect(page.getByRole('status', { name: 'Rendering preview' })).toHaveCount(0, { timeout: 15_000 })
  // Portrait original: the preview is taller than wide.
  const box = await preview.boundingBox()
  expect(box && box.height > box.width).toBe(true)
  await page.getByRole('tab', { name: 'Info' }).click()
  await expect(page.getByText('FUJIFILM X-T3')).toBeVisible()
  await shot(page, '10-photo-view')
  await page.getByRole('button', { name: /Split/ }).click()
  await page.getByRole('button', { name: 'Crop', exact: true }).click()
  await shot(page, '11-photo-split-crop')

  await page.getByRole('link', { name: 'Styles' }).click()
  await expect(page.getByRole('link', { name: /E2E Moody/ })).toBeVisible()
  await expect(page.getByText('DEMO DATA')).toHaveCount(0) // real styles since Phase 4
  await shot(page, '12-styles')
  await page.getByRole('link', { name: /E2E Moody/ }).click()
  await expect(page.getByRole('heading', { name: 'E2E Moody' })).toBeVisible()
  await shot(page, '13-style-detail')

  await page.getByRole('link', { name: 'Export presets' }).click()
  await page.getByRole('link', { name: /Print A3 fine art/ }).click()
  await expect(page.getByRole('heading', { name: /Print A3 fine art/ })).toBeVisible()
  await shot(page, '14-presets')

  await page.getByRole('link', { name: 'Jobs' }).click()
  await page.getByRole('link', { name: /Import 10 photos/ }).click()
  await expect(page.getByText(`${PHOTO_COUNT} photos: ${PHOTO_COUNT} new; 1 other file skipped`)).toBeVisible()
  await shot(page, '15-import-job')

  await page.getByRole('link', { name: 'Library' }).click()
  await page.getByRole('listbox', { name: 'Photos' }).getByRole('option').first().click()
  await page.getByRole('button', { name: /Export…/ }).click()
  await expect(page.getByTestId('export-summary')).toContainText('1080×1350')
  await shot(page, '16-export-dialog')
})

test('edit a photo: slider → preview updates → survives a reload → reset', async ({ page }) => {
  await page.goto('/library')
  await page.getByRole('listbox', { name: 'Photos' }).getByRole('option', { name: 'E2E_0001.JPG' }).dblclick()
  const panel = page.getByRole('complementary', { name: 'Photo details' })
  const preview = page.getByRole('img', { name: /E2E_0001.JPG \(after\)/ })
  await expect(page.getByRole('status', { name: 'Rendering preview' })).toHaveCount(0, { timeout: 15_000 })
  const firstSrc = await preview.getAttribute('src')

  // Keyboard on the Exposure slider: 10 steps of 0.05 EV, and the photo must not change.
  const exposure = panel.getByRole('slider', { name: 'Exposure' })
  await exposure.focus()
  for (let i = 0; i < 10; i++) await page.keyboard.press('ArrowRight')
  await expect(panel.getByRole('button', { name: '+0.5 EV' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'E2E_0001.JPG' })).toBeVisible()
  await expect(panel.getByText(/1 change for this photo · saved/)).toBeVisible({ timeout: 10_000 })
  await expect(preview).not.toHaveAttribute('src', firstSrc ?? '', { timeout: 10_000 })
  await expect(page.getByRole('status', { name: 'Rendering preview' })).toHaveCount(0, { timeout: 15_000 })
  await shot(page, '17-photo-edited')

  await page.reload()
  await expect(page.getByRole('complementary', { name: 'Photo details' }).getByRole('button', { name: '+0.5 EV' })).toBeVisible()

  // E2E_0001 got "E2E Moody" in the use-loop test (applied for real): a reset keeps the style.
  await page.getByRole('button', { name: 'Reset all' }).click()
  await expect(page.getByRole('complementary', { name: 'Photo details' }).getByText('The style only')).toBeVisible()
})

/** Thumbnail URLs carry the photo's image version, so they change whenever its look changes. */
async function thumbnailSources(page: Page) {
  const images = page.getByRole('listbox', { name: 'Photos' }).getByRole('option').locator('img')
  await expect(images).toHaveCount(PHOTO_COUNT)
  return images.evaluateAll((els) => els.map((el) => el.getAttribute('src')))
}

async function waitForJob(page: Page) {
  await expect(page).toHaveURL(/\/jobs\/j\d+$/)
  await expect(page.getByRole('progressbar', { name: 'Job progress' })).toHaveAttribute('aria-valuenow', '100', {
    timeout: 30_000,
  })
}

test('styles: save as style → apply with even out → edit → revert → delete', async ({ page, request }) => {
  // 1. Edit a photo and save its look as a new style.
  await page.goto('/library')
  await page.getByRole('listbox', { name: 'Photos' }).getByRole('option', { name: 'E2E_0001.JPG' }).dblclick()
  const panel = page.getByRole('complementary', { name: 'Photo details' })
  const contrast = panel.getByRole('slider', { name: 'Contrast' })
  await contrast.focus()
  for (let i = 0; i < 5; i++) await page.keyboard.press('ArrowRight')
  await expect(panel.getByText(/1 change for this photo · saved/)).toBeVisible({ timeout: 10_000 })
  await panel.getByRole('button', { name: /Save as style…/ }).click()
  const save = page.getByRole('dialog', { name: 'Save as style' })
  await save.getByRole('textbox', { name: 'Name' }).fill('E2E Look')
  await expect(save.getByRole('checkbox', { name: /Tone 1 changed/ })).toBeChecked()
  await shot(page, '18-save-as-style')
  await save.getByRole('button', { name: 'Create style' }).click()
  await expect(panel.getByRole('combobox', { name: 'Style' })).toHaveValue('e2e-look', { timeout: 10_000 })
  await expect(panel.getByRole('list', { name: "What the style's rules did" })).toContainText('Auto exposure')
  await shot(page, '19-photo-with-style')

  // 2. Apply it to the whole folder, evened out as a group.
  await page.getByRole('link', { name: 'Library' }).click()
  const before = await thumbnailSources(page)
  await page.getByRole('listbox', { name: 'Photos' }).getByRole('option').first().click()
  await page.keyboard.press('Control+a')
  await expect(page.getByText(`${PHOTO_COUNT} selected`)).toBeVisible()
  await page.getByRole('button', { name: /Apply style…/ }).click()
  const wizard = page.getByRole('dialog', { name: `Apply style to ${PHOTO_COUNT} photos` })
  await wizard.getByRole('radio', { name: /E2E Look/ }).click()
  await wizard.getByRole('switch', { name: 'Even out these photos' }).click()
  await wizard.getByRole('button', { name: 'Next' }).click()
  await wizard.getByRole('switch', { name: 'Export after applying the style' }).click()
  await wizard.getByRole('button', { name: 'Next' }).click()
  await expect(wizard.getByText(/evened out as a group/)).toBeVisible()
  await wizard.getByRole('button', { name: 'Apply style' }).click()
  await waitForJob(page)
  await expect(page.getByText(/evened out as a group of 10/)).toBeVisible()
  await shot(page, '20-apply-evened-out')

  await page.goto('/library')
  const applied = await thumbnailSources(page)
  expect(applied.filter((src, i) => src !== before[i]).length).toBe(PHOTO_COUNT) // every look changed
  await shot(page, '21-library-styled')

  // The manual series now matches: the spread of middle brightness shrinks.
  const photos = await (await request.get('/api/photos', { params: { limit: 500 } })).json()
  const ids = photos.items.map((p: { id: string }) => p.id)
  const report = await (await request.post('/api/styles/e2e-look/report', { data: { photo_ids: ids } })).json()
  const middle = report.spread.find((s: { measure: string }) => s.measure === 'middle')
  expect(middle.after_range).toBeLessThan(middle.before_range)

  // 3. The style detail: consistency, then an edit every photo follows.
  await page.goto('/styles/e2e-look')
  await expect(page.getByRole('heading', { name: 'E2E Look' })).toBeVisible()
  await expect(page.getByText(/Version 1 · .* · 10 photos/)).toBeVisible()
  await page.getByRole('button', { name: /Measure on the test set/ }).click()
  await expect(page.getByRole('table', { name: 'Spread before and after' })).toBeVisible({ timeout: 15_000 })
  await shot(page, '22-style-consistency')
  await page.getByRole('button', { name: 'Remove Tone › Contrast from the style' }).click()
  await expect(page.getByText(/Version 2 ·/)).toBeVisible()
  await page.goto('/library')
  const edited = await thumbnailSources(page)
  expect(edited.filter((src, i) => src !== applied[i]).length).toBe(PHOTO_COUNT)

  // 4. History: bring version 1 back (as version 3), then delete the style.
  await page.goto('/styles/e2e-look')
  const versions = page.getByRole('list', { name: 'Versions' })
  await expect(versions.getByText('removed Tone › Contrast')).toBeVisible()
  await expect(page.getByText('v1 → v2')).toBeVisible()
  await shot(page, '23-style-history')
  await versions.getByRole('button', { name: /Bring back/ }).click()
  await expect(page.getByText(/Version 3 ·/)).toBeVisible()
  await page.getByRole('button', { name: /Delete/ }).click()
  const confirm = page.getByRole('dialog', { name: /Delete "E2E Look"/ })
  await expect(confirm.getByText(/10 photos use this style/)).toBeVisible()
  await shot(page, '24-style-delete')
  await confirm.getByRole('button', { name: 'Delete style' }).click()
  await expect(page.getByRole('heading', { name: 'Styles' })).toBeVisible()
  await expect(page.getByRole('link', { name: /E2E Look/ })).toHaveCount(0)
})

test('custom preset → export → files written', async ({ page }) => {
  // Make an editable copy of a built-in preset and change it.
  await page.goto('/presets/instagram-square')
  await page.getByRole('button', { name: 'Duplicate to edit' }).click()
  const name = page.getByRole('textbox', { name: 'Preset name' })
  await expect(name).toHaveValue('Instagram square (1:1) copy')
  await name.fill('E2E square')
  const quality = page.getByLabel('Quality')
  await quality.fill('95')
  await page.getByRole('button', { name: 'Save' }).click()
  await expect(page.getByRole('link', { name: /E2E square/ })).toBeVisible()
  await shot(page, '18-preset-custom')

  // Export two photos with it.
  await page.getByRole('link', { name: 'Library' }).click()
  const tiles = page.getByRole('listbox', { name: 'Photos' }).getByRole('option')
  await tiles.nth(6).click()
  await tiles.nth(7).click({ modifiers: ['Shift'] })
  await page.getByRole('button', { name: /Export…/ }).click()
  const dialog = page.getByRole('dialog', { name: 'Export 2 photos' })
  await dialog.getByRole('combobox', { name: 'Export preset' }).selectOption({ label: 'E2E square' })
  await dialog.getByRole('textbox', { name: 'Destination folder' }).fill(`${EXPORTS}/custom`)
  const plan = dialog.getByRole('table', { name: 'Export plan' })
  await expect(plan.getByText('1080×1080')).toHaveCount(2)
  await shot(page, '19-export-plan')

  // A photo folder is refused.
  const photos = fileURLToPath(new URL('../../output/e2e/photos/sub', import.meta.url))
  await dialog.getByRole('textbox', { name: 'Destination folder' }).fill(photos)
  await expect(dialog.getByRole('alert')).toContainText('inside the photo folder')
  await expect(dialog.getByRole('button', { name: 'Export', exact: true })).toBeDisabled()

  await dialog.getByRole('textbox', { name: 'Destination folder' }).fill(`${EXPORTS}/custom`)
  await expect(plan.getByText('1080×1080')).toHaveCount(2)
  await dialog.getByRole('button', { name: 'Export', exact: true }).click()
  await expect(page).toHaveURL(/\/jobs\/j\d+$/)
  await expect(page.getByText(/2 exported →/)).toBeVisible({ timeout: 60_000 })
  await expect(page.getByRole('button', { name: /^Show E2E_\d{4}_ig\.jpg in folder$/ })).toHaveCount(2)
  await shot(page, '20-export-job')
  expect(readdirSync(`${EXPORTS}/custom`)).toHaveLength(2)
})
