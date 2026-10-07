import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockApi, renderApp } from '../../test/render'
import { parameterLabel, parameterValue } from './parameterFormat'

describe('Styles library', () => {
  it('lists style cards linking to the detail page', async () => {
    mockApi()
    renderApp('/styles')
    const link = await screen.findByRole('link', { name: /Warm Film/ })
    expect(link).toHaveAttribute('href', '/styles/warm-film')
    expect(screen.getByRole('link', { name: /Moody Forest/ })).toBeInTheDocument()
  })

  it('explains that style creation comes in Phase 8', async () => {
    mockApi()
    const { user } = renderApp('/styles')
    await user.click(await screen.findByRole('button', { name: /Create style/ }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/arrives in Phase 8/)).toBeInTheDocument()
  })
})

describe('Style detail', () => {
  it('shows description, best for / avoid on, samples and changed parameters', async () => {
    mockApi()
    renderApp('/styles/warm-film')
    expect(await screen.findByRole('heading', { name: 'Warm Film' })).toBeInTheDocument()
    expect(screen.getByText('Soft warm analog look.')).toBeInTheDocument()
    expect(screen.getByText('portraits')).toBeInTheDocument()
    expect(screen.getByText('night scenes')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Sample 1 before' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Sample 1 after' })).toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getByText('Tone › Exposure')).toBeInTheDocument()
    expect(within(table).getByText('+0.15 EV')).toBeInTheDocument()
    expect(within(table).getByText('6200 K')).toBeInTheDocument()
  })

  it('applies to the selection only when photos are selected', async () => {
    mockApi()
    renderApp('/styles/warm-film')
    expect(await screen.findByRole('button', { name: /Apply to 0 selected/ })).toBeDisabled()
  })

  it('opens the apply wizard with the style preselected', async () => {
    mockApi()
    const { user } = renderApp('/styles/warm-film', { selection: ['p001', 'p002'] })
    await user.click(await screen.findByRole('button', { name: /Apply to 2 selected/ }))
    const dialog = screen.getByRole('dialog', { name: /Apply style to 2 photos/ })
    expect(await within(dialog).findByRole('radio', { name: /Warm Film/ })).toHaveAttribute('aria-checked', 'true')
  })
})

describe('parameter formatting', () => {
  it('labels dotted parameter paths', () => {
    expect(parameterLabel('color_grading.shadows.hue')).toBe('Color grading › Shadows › Hue')
  })

  it('formats values using the slider metadata', () => {
    expect(parameterValue('tone.exposure', -0.4)).toBe('-0.4 EV')
    expect(parameterValue('tone.contrast', 25)).toBe('+25')
    expect(parameterValue('white_balance.temperature', 6200)).toBe('6200 K')
    expect(parameterValue('tone_curve.rgb', [])).toBe('custom curve')
    expect(parameterValue('lens.profile_corrections', true)).toBe('On')
  })
})
