import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { AdjustmentParams } from '../../api/types'
import { mockApi, renderApp, type ApiCall } from '../../test/render'

function panel() {
  return screen.findByRole('complementary', { name: 'Photo details' })
}

function lastSaved(calls: ApiCall[]): AdjustmentParams | undefined {
  return calls.filter((c) => c.method === 'PUT' && c.path.endsWith('/edit')).at(-1)?.body as AdjustmentParams | undefined
}

describe('Photo view', () => {
  it('shows the photo, its style and adjustment values', async () => {
    mockApi()
    renderApp('/library/p002')
    expect(await screen.findByRole('heading', { name: 'DSCF1002.RAF' })).toBeInTheDocument()
    const details = await panel()
    expect(await within(details).findByText('Warm Film')).toBeInTheDocument()
    expect(within(details).getByText('+0.15 EV')).toBeInTheDocument()
    expect(within(details).getByText('6200 K')).toBeInTheDocument()
    expect(within(details).getByText(/Double-click a slider to reset it/)).toBeInTheDocument()
  })

  it('shows the as-shot white balance when it is not changed', async () => {
    mockApi()
    renderApp('/library/p001')
    const details = await panel()
    expect(within(details).getByText('As shot 5200 K')).toBeInTheDocument()
    expect(within(details).getByText('As shot +8')).toBeInTheDocument()
  })

  it('marks per-photo changes', async () => {
    mockApi()
    renderApp('/library/p004')
    expect(await screen.findByText(/1 change for this photo · saved/)).toBeInTheDocument()
    expect(screen.getByLabelText('changed for this photo')).toBeInTheDocument()
  })

  it('saves a slider change after a short pause', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library/p001')
    const details = await panel()
    within(details).getByRole('slider', { name: 'Exposure' }).focus()
    await user.keyboard('{ArrowRight}{ArrowRight}')
    // Arrow keys on a slider move the slider, not to the next photo.
    expect(screen.getByRole('heading', { name: 'DSCF1001.RAF' })).toBeInTheDocument()
    await waitFor(() => expect(lastSaved(calls)?.tone.exposure).toBeCloseTo(0.1))
    expect(within(details).getByText('+0.1 EV')).toBeInTheDocument()
  })

  it('double-click resets a slider and undo/redo walk the history', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library/p004')
    const details = await panel()
    const exposure = details.querySelector('[data-path="tone.exposure"]')!
    expect(within(details).getByText('+0.3 EV')).toBeInTheDocument()
    await user.dblClick(exposure)
    await waitFor(() => expect(lastSaved(calls)?.tone.exposure).toBe(0))

    await user.click(within(details).getByRole('button', { name: 'Undo' }))
    await waitFor(() => expect(lastSaved(calls)?.tone.exposure).toBe(0.3))
    await user.keyboard('{Control>}{Shift>}z{/Shift}{/Control}')
    await waitFor(() => expect(lastSaved(calls)?.tone.exposure).toBe(0))
  })

  it('accepts a typed value and rejects one out of range', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library/p002')
    const details = await panel()
    await user.click(within(details).getByRole('button', { name: '+0.15 EV' }))
    const input = within(details).getByRole('textbox', { name: 'Exposure value' })
    await user.clear(input)
    await user.type(input, '9')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    await user.clear(input)
    await user.type(input, '1.5{Enter}')
    await waitFor(() => expect(lastSaved(calls)?.tone.exposure).toBe(1.5))
  })

  it('reset all goes back to the unedited photo', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library/p004')
    const details = await panel()
    await user.click(within(details).getByRole('button', { name: 'Reset all' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.path === '/api/photos/p004/edit')).toBe(true))
    expect(await within(details).findByText('0 EV')).toBeInTheDocument()
  })

  it('keeps later-phase parameters disabled and labeled', async () => {
    mockApi()
    const { user } = renderApp('/library/p001')
    const details = await panel()
    await user.click(within(details).getByRole('button', { name: 'Crop & geometry' }))
    expect(await within(details).findByText('Phase 6')).toBeInTheDocument()
    const clarity = details.querySelector('[data-path="presence.clarity"]')!
    expect(within(clarity as HTMLElement).getByText('Phase 9')).toBeInTheDocument()
    expect(within(clarity as HTMLElement).getByRole('slider')).toHaveAttribute('data-disabled')
  })

  it('switches between after, before, split and camera JPEG views', async () => {
    mockApi()
    const { user } = renderApp('/library/p002')
    const after = await screen.findByRole('img', { name: 'DSCF1002.RAF (after)' })
    expect(after.getAttribute('src')).toContain('v=v2')
    expect(after.getAttribute('src')).not.toContain('before=true')

    await user.click(screen.getByRole('button', { name: /Before/ }))
    expect(screen.getByRole('img', { name: 'DSCF1002.RAF (before)' }).getAttribute('src')).toContain('before=true')

    await user.click(screen.getByRole('button', { name: /Split/ }))
    expect(screen.getByRole('slider', { name: 'Before/after split position' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Camera JPEG/ }))
    expect(screen.getByRole('img', { name: 'DSCF1002.RAF (camera JPEG)' }).getAttribute('src')).toContain('/sidecar')
  })

  it('edits the tone curve with the keyboard', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library/p001')
    const details = await panel()
    await user.click(within(details).getByRole('button', { name: 'Tone curve (parametric)' }))
    const end = await within(details).findByRole('slider', { name: 'Point 2 of 2' })
    end.focus()
    fireEvent.keyDown(end, { key: 'ArrowDown', shiftKey: true })
    await waitFor(() => expect(lastSaved(calls)?.tone_curve.rgb.at(-1)).toEqual({ x: 1, y: 0.95 }))
  })

  it('toggles the crop overlay', async () => {
    mockApi()
    const { user } = renderApp('/library/p004')
    await screen.findByRole('heading', { name: 'DSCF1004.RAF' })
    expect(screen.queryByTestId('crop-overlay')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Crop' }))
    expect(screen.getByTestId('crop-overlay')).toBeInTheDocument()
  })

  it('shows EXIF info in the Info tab', async () => {
    mockApi()
    const { user } = renderApp('/library/p001')
    await screen.findByRole('heading', { name: 'DSCF1001.RAF' })
    await user.click(screen.getByRole('tab', { name: 'Info' }))
    expect(screen.getByText('FUJIFILM X-T3')).toBeInTheDocument()
    expect(screen.getByText('f/2.8')).toBeInTheDocument()
    expect(screen.getByText('6240 × 4160')).toBeInTheDocument()
  })

  it('navigates with next/previous and the filmstrip', async () => {
    mockApi()
    const { user } = renderApp('/library/p002')
    await screen.findByRole('heading', { name: 'DSCF1002.RAF' })
    await user.click(screen.getByRole('button', { name: 'Next photo' }))
    expect(await screen.findByRole('heading', { name: 'DSCF1003.RAF' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Previous photo' }))
    expect(await screen.findByRole('heading', { name: 'DSCF1002.RAF' })).toBeInTheDocument()
    const strip = screen.getByRole('navigation', { name: 'Filmstrip' })
    await user.click(within(strip).getByRole('link', { name: 'DSCF1005.RAF' }))
    expect(await screen.findByRole('heading', { name: 'DSCF1005.RAF' })).toBeInTheDocument()
  })
})
