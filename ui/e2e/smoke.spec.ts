/**
 * Smoke test of the full use loop against the real backend, on synthetic photos (scripts/e2e_setup.py):
 * open a folder → import → select photos → apply style → export preset → destination → confirm → job finishes.
 * Styles and the apply/export jobs are still simulated (Phases 4–5). Screenshots of every screen go to
 * output/screenshots/ for a quick visual review.
 */
import { expect, test, type Page } from '@playwright/test'

const SHOTS = '../output/screenshots'
const PHOTO_COUNT = 8

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
  await dialog.getByRole('radio', { name: /Moody Forest/ }).click()
  await shot(page, '05-wizard-style')
  await dialog.getByRole('button', { name: 'Next' }).click()
  await expect(dialog.getByRole('combobox', { name: 'Export preset' })).toHaveValue('instagram-portrait')
  await dialog.getByRole('textbox', { name: 'Destination folder' }).fill('C:/Users/ambro/Pictures/Exports/test')
  await expect(dialog.getByText(/1080×1350 · 4:5 crop · JPEG q92 · sRGB → C:\/Users/)).toBeVisible()
  await shot(page, '06-wizard-export')
  await dialog.getByRole('button', { name: 'Next' }).click()
  await shot(page, '07-wizard-review')
  await dialog.getByRole('button', { name: 'Apply & export' }).click()

  // Lands on the job, which progresses to done.
  await expect(page).toHaveURL(/\/jobs\/j\d+$/)
  await expect(page.getByRole('heading', { name: /Apply Moody Forest and export 5 photos/ })).toBeVisible()
  await shot(page, '08-job-running')
  await expect(page.getByRole('progressbar', { name: 'Job progress' })).toHaveAttribute('aria-valuenow', '100', {
    timeout: 15_000,
  })
  await expect(page.getByText('5 of 5 (100%)')).toBeVisible()
  await shot(page, '09-job-done')
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
  await expect(page.getByRole('link', { name: /Warm Film/ })).toBeVisible()
  await expect(page.getByText('DEMO DATA')).toBeVisible()
  await shot(page, '12-styles')
  await page.getByRole('link', { name: /Warm Film/ }).click()
  await expect(page.getByRole('heading', { name: 'Warm Film' })).toBeVisible()
  await shot(page, '13-style-detail')

  await page.getByRole('link', { name: 'Export presets' }).click()
  await page.getByRole('link', { name: /Print A3 fine art/ }).click()
  await expect(page.getByRole('heading', { name: /Print A3 fine art/ })).toBeVisible()
  await shot(page, '14-presets')

  await page.getByRole('link', { name: 'Jobs' }).click()
  await page.getByRole('link', { name: /Import 8 photos/ }).click()
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
  await expect(panel.getByText(/1 change · saved/)).toBeVisible({ timeout: 10_000 })
  await expect(preview).not.toHaveAttribute('src', firstSrc ?? '', { timeout: 10_000 })
  await expect(page.getByRole('status', { name: 'Rendering preview' })).toHaveCount(0, { timeout: 15_000 })
  await shot(page, '17-photo-edited')

  await page.reload()
  await expect(page.getByRole('complementary', { name: 'Photo details' }).getByRole('button', { name: '+0.5 EV' })).toBeVisible()

  await page.getByRole('button', { name: 'Reset all' }).click()
  await expect(page.getByRole('complementary', { name: 'Photo details' }).getByText('Unedited')).toBeVisible()
})
