import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { PresetUpdate } from '../../api/types'
import { presets } from '../../test/fixtures'
import { mockApi, renderApp } from '../../test/render'

const custom = { ...presets[1]!, id: 'my-web', name: 'My web', builtin: false, version: 3 }

describe('Presets screen', () => {
  it('duplicates a built-in preset into an editable copy', async () => {
    const calls = mockApi()
    const { user } = renderApp('/presets/web-full')
    await user.click(await screen.findByRole('button', { name: 'Duplicate to edit' }))
    expect(await screen.findByRole('textbox', { name: 'Preset name' })).toHaveValue('Web full size copy')
    expect(calls.some((c) => c.method === 'POST' && c.path === '/api/export-presets/web-full/duplicate')).toBe(true)
    expect(screen.getByDisplayValue('2048')).toBeEnabled()
    const list = screen.getByRole('list', { name: 'Export presets' })
    expect(within(list).getByRole('link', { name: /Web full size copy/ })).toHaveAttribute('aria-current', 'page')
  })

  it('saves edits with the version they were made on', async () => {
    const calls = mockApi({ 'GET /api/export-presets': () => [...presets, custom] })
    const { user } = renderApp('/presets/my-web')
    const save = await screen.findByRole('button', { name: 'Save' })
    expect(save).toBeDisabled()
    const quality = screen.getByDisplayValue('85')
    await user.clear(quality)
    await user.type(quality, '95')
    await user.clear(screen.getByRole('textbox', { name: 'Preset name' }))
    await user.type(screen.getByRole('textbox', { name: 'Preset name' }), 'Web 95')
    await user.click(save)
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    const body = calls.find((c) => c.method === 'PUT')!.body as PresetUpdate
    expect(body).toMatchObject({ expected_version: 3, name: 'Web 95', settings: { file: { jpeg_quality: 95 } } })
  })

  it('deletes a custom preset after confirming', async () => {
    const calls = mockApi({ 'GET /api/export-presets': () => [...presets, custom] })
    const { user } = renderApp('/presets/my-web')
    await user.click(await screen.findByRole('button', { name: 'Delete' }))
    const dialog = screen.getByRole('dialog', { name: 'Delete "My web"?' })
    await user.click(within(dialog).getByRole('button', { name: 'Delete preset' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.path === '/api/export-presets/my-web')).toBe(true))
  })

  it('shows a broken preset with its error, and only allows deleting it', async () => {
    const broken = { ...custom, id: 'bad', name: 'bad', error: 'settings.file.jpeg_quality: too large' }
    mockApi({ 'GET /api/export-presets': () => [...presets, broken] })
    renderApp('/presets/bad')
    expect(await screen.findByRole('alert')).toHaveTextContent("can't be read: settings.file.jpeg_quality")
    expect(screen.queryByRole('button', { name: /Duplicate/ })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument()
    expect(screen.getByText('Broken')).toBeInTheDocument()
  })
})
