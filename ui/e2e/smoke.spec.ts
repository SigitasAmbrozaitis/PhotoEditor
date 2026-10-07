/**
 * Smoke test of the full use loop against the real (mock-data) backend:
 * select photos → apply style → choose export preset → destination → confirm → job finishes.
 * Screenshots of every screen go to output/screenshots/ for a quick visual review.
 */
import { expect, test, type Page } from '@playwright/test'

const SHOTS = '../output/screenshots'

async function shot(page: Page, name: string) {
  await page.screenshot({ path: `${SHOTS}/${name}.png` })
}

test('full use loop: select → apply style → export → job done', async ({ page }) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/library$/)
  await expect(page.getByText(/backend v\d/)).toBeVisible()

  const grid = page.getByRole('listbox', { name: 'Photos' })
  const tiles = grid.getByRole('option')
  await expect(tiles).toHaveCount(24)
  await shot(page, '01-library')

  // Select photos 1-4 with click + shift-click, then add photo 6 with ctrl-click.
  await tiles.nth(0).click()
  await tiles.nth(3).click({ modifiers: ['Shift'] })
  await tiles.nth(5).click({ modifiers: ['Control'] })
  await expect(page.getByText(/5 selected/)).toBeVisible()
  await shot(page, '02-library-selected')

  // Apply & export wizard.
  await page.getByRole('button', { name: /Apply style/ }).click()
  const dialog = page.getByRole('dialog', { name: 'Apply style to 5 photos' })
  await dialog.getByRole('radio', { name: /Moody Forest/ }).click()
  await shot(page, '03-wizard-style')
  await dialog.getByRole('button', { name: 'Next' }).click()
  await expect(dialog.getByRole('combobox', { name: 'Export preset' })).toHaveValue('instagram-portrait')
  await dialog.getByRole('textbox', { name: 'Destination folder' }).fill('C:/Users/ambro/Pictures/Exports/test')
  await expect(dialog.getByText(/1080×1350 · 4:5 crop · JPEG q92 · sRGB → C:\/Users/)).toBeVisible()
  await shot(page, '04-wizard-export')
  await dialog.getByRole('button', { name: 'Next' }).click()
  await shot(page, '05-wizard-review')
  await dialog.getByRole('button', { name: 'Apply & export' }).click()

  // Lands on the job, which progresses to done.
  await expect(page).toHaveURL(/\/jobs\/j\d+$/)
  await expect(page.getByRole('heading', { name: /Apply Moody Forest and export 5 photos/ })).toBeVisible()
  await shot(page, '06-job-running')
  await expect(page.getByRole('progressbar', { name: 'Job progress' })).toHaveAttribute('aria-valuenow', '100', {
    timeout: 15_000,
  })
  await expect(page.getByText('5 of 5 (100%)')).toBeVisible()
  await shot(page, '07-job-done')
})

test('screens render: photo view, styles, presets', async ({ page }) => {
  await page.goto('/library/p002')
  await expect(page.getByRole('heading', { name: 'DSCF5438.RAF' })).toBeVisible()
  await expect(page.getByRole('img', { name: /DSCF5438.RAF \(after\)/ })).toBeVisible()
  await shot(page, '08-photo-view')
  await page.getByRole('button', { name: /Split/ }).click()
  await page.getByRole('button', { name: 'Crop', exact: true }).click()
  await shot(page, '09-photo-split-crop')

  await page.getByRole('link', { name: 'Styles' }).click()
  await expect(page.getByRole('link', { name: /Warm Film/ })).toBeVisible()
  await shot(page, '10-styles')
  await page.getByRole('link', { name: /Warm Film/ }).click()
  await expect(page.getByRole('heading', { name: 'Warm Film' })).toBeVisible()
  await shot(page, '11-style-detail')

  await page.getByRole('link', { name: 'Export presets' }).click()
  await page.getByRole('link', { name: /Print A3 fine art/ }).click()
  await expect(page.getByRole('heading', { name: /Print A3 fine art/ })).toBeVisible()
  await shot(page, '12-presets')

  await page.getByRole('link', { name: 'Library' }).click()
  await page.getByRole('listbox', { name: 'Photos' }).getByRole('option').first().click()
  await page.getByRole('button', { name: /Export…/ }).click()
  await expect(page.getByTestId('export-summary')).toContainText('1080×1350')
  await shot(page, '13-export-dialog')
})
