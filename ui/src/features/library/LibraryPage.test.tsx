import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
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
    expect(screen.getByText('DEMO DATA')).toBeInTheDocument()
    expect(await screen.findByText('backend v0.1.0')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Photo folder' })).toHaveValue('C:/Photos/Test')
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
