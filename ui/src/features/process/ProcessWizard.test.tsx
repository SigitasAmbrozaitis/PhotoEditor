import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { ApplyAndExportRequest, ApplyStyleRequest } from '../../api/types'
import { mockApi, renderApp } from '../../test/render'

async function openWizard(selection: string[]) {
  const calls = mockApi()
  const utils = renderApp('/library', { selection })
  await utils.user.click(await screen.findByRole('button', { name: /Apply style…/ }))
  const dialog = screen.getByRole('dialog', { name: `Apply style to ${selection.length} photos` })
  return { ...utils, calls, dialog: within(dialog) }
}

describe('Apply & export wizard (full use loop)', () => {
  it('goes style → export → review → job', async () => {
    const { user, calls, dialog } = await openWizard(['p001', 'p002', 'p003'])
    const next = dialog.getByRole('button', { name: 'Next' })
    expect(next).toBeDisabled() // no style chosen yet

    await user.click(await dialog.findByRole('radio', { name: /Moody Forest/ }))
    await user.click(next)

    // Export step: destination required.
    expect(await dialog.findByRole('combobox', { name: 'Export preset' })).toHaveValue('instagram-portrait')
    expect(dialog.getByRole('button', { name: 'Next' })).toBeDisabled()
    await user.type(dialog.getByRole('textbox', { name: 'Destination folder' }), 'C:/Exports/ig')
    await user.click(dialog.getByRole('button', { name: 'Next' }))

    // Review.
    expect(dialog.getByText('Moody Forest')).toBeInTheDocument()
    expect(dialog.getByText('Instagram portrait (4:5)')).toBeInTheDocument()
    expect(dialog.getByText(/→ C:\/Exports\/ig/)).toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: 'Apply & export' }))

    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    const body = calls.find((c) => c.method === 'POST')!.body as ApplyAndExportRequest
    expect(body).toMatchObject({
      kind: 'apply_and_export',
      photo_ids: ['p001', 'p002', 'p003'],
      style_id: 'moody-forest',
      preset_id: 'instagram-portrait',
      destination: 'C:/Exports/ig',
    })
    expect(body.settings.size?.width).toBe(1080)
    // Lands on the new job.
    expect(await screen.findByRole('heading', { name: 'New apply_and_export job' })).toBeInTheDocument()
  })

  it('can apply a style without exporting', async () => {
    const { user, calls, dialog } = await openWizard(['p001', 'p002'])
    await user.click(await dialog.findByRole('radio', { name: /Warm Film/ }))
    await user.click(dialog.getByRole('button', { name: 'Next' }))
    await user.click(dialog.getByRole('switch', { name: 'Export after applying the style' }))
    await user.click(dialog.getByRole('button', { name: 'Next' }))
    expect(dialog.getByText('No export (style is applied only)')).toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: 'Apply style' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    const body = calls.find((c) => c.method === 'POST')!.body as ApplyStyleRequest
    expect(body).toEqual({ kind: 'apply_style', photo_ids: ['p001', 'p002'], style_id: 'warm-film' })
  })

  it('back button returns to the previous step', async () => {
    const { user, dialog } = await openWizard(['p001', 'p002'])
    await user.click(await dialog.findByRole('radio', { name: /Warm Film/ }))
    await user.click(dialog.getByRole('button', { name: 'Next' }))
    await user.click(dialog.getByRole('button', { name: 'Back' }))
    expect(dialog.getByRole('radio', { name: /Warm Film/ })).toHaveAttribute('aria-checked', 'true')
  })
})
