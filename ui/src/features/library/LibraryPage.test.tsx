import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import * as fx from '../../test/fixtures'
import { mockApi, renderApp } from '../../test/render'

async function grid() {
  return within(await screen.findByRole('listbox', { name: 'Photos' }))
}

describe('Library', () => {
  it('shows the app shell and the photo grid', async () => {
    mockApi()
    renderApp('/library')
    const photos = await grid()
    expect(photos.getAllByRole('option')).toHaveLength(6)
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    expect(screen.queryByText('DEMO DATA')).not.toBeInTheDocument() // the Library shows real photos
    expect(await screen.findByText('backend v0.1.0')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Photo folder' })).toHaveValue('C:/Photos/Test')
  })

  it('shows an empty state with the suggested folder when nothing is open', async () => {
    mockApi({
      'GET /api/library': () => fx.emptyLibrary,
      'GET /api/library/folders': () => [],
      'GET /api/photos': () => ({ items: [], total: 0, offset: 0, limit: 500 }),
      'GET /api/jobs': () => [],
    })
    renderApp('/library')
    expect(await screen.findByText('Open a folder')).toBeInTheDocument()
    expect(screen.getByText('No folder open')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Photo folder' })).toHaveValue('C:/Users/me/Pictures/2026-08-11')
    expect(screen.queryByRole('combobox', { name: 'Recent folders' })).not.toBeInTheDocument()
  })

  it('browses folders and picks one', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library')
    await grid()
    await user.click(screen.getByRole('button', { name: /browse/i }))
    const dialog = within(await screen.findByRole('dialog', { name: 'Choose a photo folder' }))
    await user.click(await dialog.findByRole('button', { name: /day1/ }))
    expect(await dialog.findByText('12 photos in this folder')).toBeInTheDocument()
    expect(calls.filter((c) => c.path === '/api/fs/dirs').map((c) => c.query.get('path'))).toEqual([
      'C:/Photos/Test',
      'C:/Photos/Test/day1',
    ])
    await user.click(dialog.getByRole('button', { name: 'Up one level' }))
    await user.click(await dialog.findByRole('button', { name: /day1/ }))
    await user.click(await dialog.findByRole('button', { name: 'Choose this folder' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(screen.getByRole('textbox', { name: 'Photo folder' })).toHaveValue('C:/Photos/Test/day1')
  })

  it('imports a folder and shows progress', async () => {
    const calls = mockApi({ 'GET /api/jobs': () => [fx.makeImportJob({ status: 'running', completed: 3, progress: 3 / 67, finished_at: null, summary: null })] })
    const { user } = renderApp('/library')
    await grid()
    const field = screen.getByRole('textbox', { name: 'Photo folder' })
    await user.clear(field)
    await user.type(field, 'D:/Shoots/2026')
    await user.click(screen.getByRole('switch', { name: 'Include subfolders' }))
    await user.click(screen.getByRole('button', { name: 'Open' }))
    await waitFor(() => {
      const post = calls.find((c) => c.method === 'POST' && c.path === '/api/library/import')
      expect(post?.body).toEqual({ folder: 'D:/Shoots/2026', include_subfolders: true })
    })
    expect(await screen.findByText(/Importing… 3 \/ 67/)).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Import progress' })).toHaveAttribute('aria-valuenow', '4')
  })

  it('shows the last import result above the grid', async () => {
    mockApi({ 'GET /api/jobs': () => [fx.makeImportJob()] })
    renderApp('/library')
    await grid()
    expect(await screen.findByText('Last import: 67 photos: 67 new; 1 other file skipped')).toBeInTheDocument()
  })

  it('switches to a recently imported folder', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library')
    await grid()
    await user.selectOptions(await screen.findByRole('combobox', { name: 'Recent folders' }), 'C:/Photos/Older')
    await waitFor(() => {
      const put = calls.find((c) => c.method === 'PUT' && c.path === '/api/library/current')
      expect(put?.body).toEqual({ folder: 'C:/Photos/Older' })
    })
  })

  it('shows style badges on styled photos', async () => {
    mockApi()
    renderApp('/library')
    const photos = await grid()
    const styled = photos.getByRole('option', { name: 'DSCF1002.RAF' })
    expect(await within(styled).findByText('Warm Film')).toBeInTheDocument()
  })

  it('supports click, ctrl+click, shift+click, select all and clear', async () => {
    mockApi()
    const { user } = renderApp('/library')
    const photos = await grid()
    const tile = (n: number) => photos.getByRole('option', { name: `DSCF${1000 + n}.RAF` })
    const apply = screen.getByRole('button', { name: /apply style/i })
    expect(apply).toBeDisabled()

    await user.click(tile(2))
    expect(tile(2)).toHaveAttribute('aria-selected', 'true')
    expect(apply).toBeEnabled()

    await user.keyboard('{Shift>}')
    await user.click(tile(4))
    await user.keyboard('{/Shift}')
    expect([2, 3, 4].every((n) => tile(n).getAttribute('aria-selected') === 'true')).toBe(true)
    expect(screen.getByText(/3 selected/)).toBeInTheDocument()

    await user.keyboard('{Control>}')
    await user.click(tile(3))
    await user.keyboard('{/Control}')
    expect(tile(3)).toHaveAttribute('aria-selected', 'false')
    expect(screen.getByText(/2 selected/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Select all' }))
    expect(screen.getByText(/6 selected/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Clear' }))
    expect(screen.getByText(/0 selected/)).toBeInTheDocument()
    expect(apply).toBeDisabled()
  })

  it('passes sort and filter choices to the API', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library')
    await grid()
    await user.selectOptions(screen.getByRole('combobox', { name: 'Sort by' }), 'name')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Filter by style' }), 'warm-film')
    await waitFor(() => {
      const last = calls.filter((c) => c.path === '/api/photos').at(-1)
      expect(last?.query.get('sort')).toBe('name')
      expect(last?.query.get('style_id')).toBe('warm-film')
    })
    expect((await grid()).getAllByRole('option')).toHaveLength(1)
  })

  it('opens a photo with double-click', async () => {
    mockApi()
    const { user } = renderApp('/library')
    const photos = await grid()
    await user.dblClick(photos.getByRole('option', { name: 'DSCF1003.RAF' }))
    expect(await screen.findByRole('heading', { name: 'DSCF1003.RAF' })).toBeInTheDocument()
  })

  it('shows a red offline badge when the backend is unreachable', async () => {
    mockApi({
      'GET /api/health': () => {
        throw new TypeError('Failed to fetch')
      },
    })
    renderApp('/library')
    expect(await screen.findByRole('alert')).toHaveTextContent('backend offline')
  })

  it('shows an error when the API fails', async () => {
    mockApi({ 'GET /api/photos': () => new Response('{"detail":"boom"}', { status: 500 }) })
    renderApp('/library')
    expect(await screen.findByText('Could not load data')).toBeInTheDocument()
  })
})
