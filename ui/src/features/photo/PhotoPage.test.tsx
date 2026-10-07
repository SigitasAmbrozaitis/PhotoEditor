import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockApi, renderApp } from '../../test/render'

describe('Photo view', () => {
  it('shows the photo, its style and adjustment values', async () => {
    mockApi()
    renderApp('/library/p002')
    expect(await screen.findByRole('heading', { name: 'DSCF1002.RAF' })).toBeInTheDocument()
    const panel = screen.getByRole('complementary', { name: 'Photo details' })
    expect(await within(panel).findByText('Warm Film')).toBeInTheDocument()
    expect(within(panel).getByText('+0.15 EV')).toBeInTheDocument()
    expect(within(panel).getByText('6200 K')).toBeInTheDocument()
    expect(within(panel).getByText(/Editing arrives in Phase 3/)).toBeInTheDocument()
  })

  it('shows "As shot" for unset white balance', async () => {
    mockApi()
    renderApp('/library/p001')
    const panel = await screen.findByRole('complementary', { name: 'Photo details' })
    expect(within(panel).getAllByText('As shot')).toHaveLength(2)
  })

  it('marks per-photo overrides', async () => {
    mockApi()
    renderApp('/library/p004')
    expect(await screen.findByText(/1 per-photo override/)).toBeInTheDocument()
    expect(screen.getByLabelText('overridden for this photo')).toBeInTheDocument()
  })

  it('switches between after, before and split views', async () => {
    mockApi()
    const { user } = renderApp('/library/p002')
    const after = await screen.findByRole('img', { name: 'DSCF1002.RAF (after)' })
    expect(after.getAttribute('src')).not.toContain('before=true')

    await user.click(screen.getByRole('button', { name: /Before/ }))
    expect(screen.getByRole('img', { name: 'DSCF1002.RAF (before)' }).getAttribute('src')).toContain('before=true')

    await user.click(screen.getByRole('button', { name: /Split/ }))
    expect(screen.getByRole('slider', { name: 'Before/after split position' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'DSCF1002.RAF (after)' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'DSCF1002.RAF (before)' })).toBeInTheDocument()
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
