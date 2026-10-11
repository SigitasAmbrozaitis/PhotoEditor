import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { makeJob, noOutput } from '../../test/fixtures'
import { mockApi, renderApp } from '../../test/render'

describe('Jobs', () => {
  it('lists jobs with progress', async () => {
    mockApi()
    renderApp('/jobs')
    const list = await screen.findByRole('list', { name: 'Jobs' })
    expect(within(list).getByText(/Apply Warm Film and export 2 photos/)).toBeInTheDocument()
    expect(within(list).getByRole('progressbar')).toHaveAttribute('aria-valuenow', '100')
    expect(screen.getByText('Select a job to see its details.')).toBeInTheDocument()
  })

  it('shows per-item status and outputs, with style and preset names', async () => {
    mockApi()
    renderApp('/jobs/j0001')
    expect(await screen.findByText('C:/Exports/ig/DSCF1001.jpg')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'DSCF1002.RAF' })).toHaveAttribute('href', '/library/p002')
    expect(await screen.findByRole('link', { name: 'Warm Film' })).toBeInTheDocument()
    expect(await screen.findByText('Instagram portrait (4:5)')).toBeInTheDocument()
  })

  it('shows failed items with their message', async () => {
    const failed = makeJob({
      failed: 1,
      items: [
        { photo_id: 'p001', filename: 'DSCF1001.RAF', status: 'failed', message: 'could not decode', output_path: null, ...noOutput },
      ],
    })
    mockApi({ 'GET /api/jobs': () => [failed], 'GET /api/jobs/:id': () => failed })
    renderApp('/jobs/j0001')
    expect(await screen.findByText('could not decode')).toBeInTheDocument()
    expect(screen.getAllByText(/1 failed/).length).toBeGreaterThan(0)
  })

  it('shows what each export wrote and reveals a file in its folder', async () => {
    const exported = makeJob({
      kind: 'export',
      items: [
        {
          photo_id: 'p001',
          filename: 'DSCF1001.RAF',
          status: 'done',
          message: 'overwritten',
          output_path: 'C:/Exports/ig/DSCF1001_ig.jpg',
          output_bytes: 412 * 1024,
          output_width: 1080,
          output_height: 1350,
          warnings: ['enlarged 1.20×'],
        },
      ],
    })
    const calls = mockApi({ 'GET /api/jobs': () => [exported], 'GET /api/jobs/:id': () => exported })
    const { user } = renderApp('/jobs/j0001')
    expect(await screen.findByText('DSCF1001_ig.jpg')).toHaveAttribute('title', 'C:/Exports/ig/DSCF1001_ig.jpg')
    expect(screen.getByText('1080×1350 · 412 KB')).toBeInTheDocument()
    expect(screen.getByText('enlarged 1.20×')).toBeInTheDocument()
    expect(screen.getByText('overwritten')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Show DSCF1001_ig.jpg in folder' }))
    await waitFor(() => expect(calls.find((c) => c.path === '/api/export/reveal')?.body).toEqual({ path: 'C:/Exports/ig/DSCF1001_ig.jpg' }))
  })

  it('cancels a running job', async () => {
    const running = makeJob({ status: 'running', progress: 0.5, completed: 1, finished_at: null })
    const calls = mockApi({ 'GET /api/jobs': () => [running], 'GET /api/jobs/:id': () => running })
    const { user } = renderApp('/jobs/j0001')
    await user.click(await screen.findByRole('button', { name: 'Cancel' }))
    await waitFor(() =>
      expect(calls.some((c) => c.method === 'POST' && c.path === '/api/jobs/j0001/cancel')).toBe(true),
    )
  })

  it('shows a running-jobs indicator in the top bar', async () => {
    const running = makeJob({ status: 'running', progress: 0.5, completed: 1, finished_at: null })
    mockApi({ 'GET /api/jobs': () => [running] })
    renderApp('/library')
    expect(await screen.findByRole('link', { name: '1 job running' })).toHaveTextContent('50%')
  })
})

describe('Export presets', () => {
  it('lists presets and shows the selected one read-only', async () => {
    mockApi()
    renderApp('/presets/web-full')
    const list = await screen.findByRole('list', { name: 'Export presets' })
    expect(within(list).getByRole('link', { name: /Instagram portrait/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Web full size/ })).toBeInTheDocument()
    expect(screen.getByDisplayValue('2048')).toBeDisabled()
    expect(screen.getByLabelText('built-in (read-only)')).toBeInTheDocument()
  })
})
