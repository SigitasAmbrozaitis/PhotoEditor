import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { ExportRequest } from '../../api/types'
import { presets } from '../../test/fixtures'
import { mockApi, renderApp } from '../../test/render'
import { exportSummary } from './exportSummary'

describe('exportSummary', () => {
  it('summarizes size, crop, file, color space and destination', () => {
    const ig = presets[0]!.settings
    expect(exportSummary(ig, 'C:/Exports')).toBe('1080×1350 · 4:5 crop · JPEG q92 · sRGB → C:/Exports')
    expect(exportSummary(ig, '  ')).toBe('1080×1350 · 4:5 crop · JPEG q92 · sRGB → (choose a folder)')
    const web = presets[1]!.settings
    expect(exportSummary(web)).toBe('long edge 2048 px · JPEG q85 · sRGB → (choose a folder)')
    const tiff = { ...web, file: { ...web.file, format: 'tiff' as const, bit_depth: 16 }, color_space: 'adobe_rgb' as const }
    expect(exportSummary(tiff, 'D:/Print')).toBe('long edge 2048 px · TIFF 16-bit · Adobe RGB → D:/Print')
  })
})

describe('Export dialog', () => {
  it('updates the summary when the preset or settings change', async () => {
    mockApi()
    const { user } = renderApp('/library', { selection: ['p001', 'p002'] })
    await user.click(await screen.findByRole('button', { name: /Export…/ }))
    const dialog = screen.getByRole('dialog', { name: 'Export 2 photos' })
    const summary = await within(dialog).findByTestId('export-summary')
    expect(summary).toHaveTextContent('1080×1350 · 4:5 crop · JPEG q92 · sRGB → (choose a folder)')

    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Export preset' }), 'web-full')
    expect(summary).toHaveTextContent('long edge 2048 px · JPEG q85 · sRGB')

    await user.selectOptions(within(dialog).getByDisplayValue('sRGB'), 'display_p3')
    expect(summary).toHaveTextContent('Display P3')
    expect(within(dialog).getByText('Export preset (modified)')).toBeInTheDocument()
  })

  it('requires a destination, then creates an export job and opens it', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library', { selection: ['p001', 'p002'] })
    await user.click(await screen.findByRole('button', { name: /Export…/ }))
    const dialog = screen.getByRole('dialog', { name: 'Export 2 photos' })
    const exportButton = await within(dialog).findByRole('button', { name: 'Export' })
    expect(exportButton).toBeDisabled()

    await user.type(within(dialog).getByRole('textbox', { name: 'Destination folder' }), 'D:/Out')
    expect(within(dialog).getByTestId('export-summary')).toHaveTextContent('→ D:/Out')
    await user.click(exportButton)

    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/api/jobs')).toBe(true))
    const body = calls.find((c) => c.method === 'POST')!.body as ExportRequest
    expect(body.kind).toBe('export')
    expect(body.photo_ids).toEqual(['p001', 'p002'])
    expect(body.destination).toBe('D:/Out')
    expect(body.preset_id).toBe('instagram-portrait')
    expect(await screen.findByRole('heading', { name: 'New export job' })).toBeInTheDocument()
  })
})
