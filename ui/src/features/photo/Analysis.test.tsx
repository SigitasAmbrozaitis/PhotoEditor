import { screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { resetDetailsForTests } from '../../hooks/useDetails'
import { mockApi, renderApp } from '../../test/render'

beforeEach(() => {
  localStorage.clear()
  resetDetailsForTests()
})

async function openTab(photoId: string) {
  const calls = mockApi()
  const utils = renderApp(`/library/${photoId}`)
  await utils.user.click(await screen.findByRole('tab', { name: 'AI Analysis' }))
  const panel = await screen.findByTestId('analysis-panel')
  return { ...utils, calls, panel }
}

describe('AI Analysis tab', () => {
  it('lists the subject and everything found with confidence, and draws them on the photo', async () => {
    const { user, panel } = await openTab('p001')
    expect(within(panel).getByTestId('analysis-subject')).toHaveTextContent('car 84 %')
    expect(within(panel).getByText('found by detection')).toBeInTheDocument()
    const found = within(panel).getByRole('region', { name: 'Found' })
    expect(within(found).getAllByRole('listitem').map((li) => li.textContent?.replace(/\s+/g, ' ').trim())).toEqual([
      'truck (car)subject84 %Use',
      'person20 %Use',
      'stands outguess12 %Use',
    ])
    // Drawn on the photo while the tab is open; Hide details (or D) hides them.
    const overlay = await screen.findByTestId('detection-overlay')
    expect(within(overlay).getByText('truck 84 %')).toBeInTheDocument()
    expect(within(overlay).getByTestId('focus-point')).toBeInTheDocument()
    await user.click(within(panel).getByRole('button', { name: /Hide details/ }))
    expect(screen.queryByTestId('detection-overlay')).not.toBeInTheDocument()
    await user.keyboard('d')
    expect(screen.getByTestId('detection-overlay')).toBeInTheDocument()
    // Not on the other tabs.
    await user.click(screen.getByRole('tab', { name: 'Info' }))
    expect(screen.queryByTestId('detection-overlay')).not.toBeInTheDocument()
  })

  it('Use makes another candidate the subject (saved by hand)', async () => {
    const { user, panel, calls } = await openTab('p001')
    await user.click(within(panel).getByRole('button', { name: 'Use person 20 % as the subject' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT' && c.path === '/api/photos/p001/subject')).toBe(true))
    const put = calls.find((c) => c.method === 'PUT' && c.path === '/api/photos/p001/subject')!
    // The upright box from the stored detection (the fake's person).
    expect(put.body).toEqual({ box: { left: 0.1, top: 0.6, right: 0.2, bottom: 0.9 } })
    expect(await within(panel).findByText('set by hand')).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: 'Use detected' })).toBeInTheDocument()
  })

  it('a photo not analysed yet offers Detect now', async () => {
    const { user, panel, calls } = await openTab('p003')
    expect(within(panel).getByText(/Not analysed yet/)).toBeInTheDocument()
    await user.click(within(panel).getByRole('button', { name: /Detect now/ }))
    expect(await within(panel).findByTestId('analysis-subject')).toHaveTextContent('car 84 %')
    expect(calls.some((c) => c.path === '/api/photos/p003/analysis' && c.query.get('detect') === 'true')).toBe(true)
  })

  it('Set subject opens the crop tool ready to draw', async () => {
    const { user, panel } = await openTab('p001')
    await user.click(within(panel).getByRole('button', { name: /Set subject/ }))
    expect(await screen.findByTestId('crop-tool')).toBeInTheDocument()
    expect(screen.getByTestId('subject-draw')).toBeInTheDocument()
  })
})
