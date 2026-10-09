import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import * as fx from '../../test/fixtures'
import { mockApi, renderApp } from '../../test/render'
import { parameterLabel, parameterValue } from './parameterFormat'
import { describeRule } from './styleWords'

describe('Styles library', () => {
  it('lists style cards with their photo counts, linking to the detail page', async () => {
    mockApi()
    renderApp('/styles')
    const link = await screen.findByRole('link', { name: /Warm Film/ })
    expect(link).toHaveAttribute('href', '/styles/warm-film')
    expect(within(link).getByText(/3 photos · v2/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Moody Forest/ })).toBeInTheDocument()
    expect(screen.queryByText('DEMO DATA')).not.toBeInTheDocument() // real styles now
  })

  it('shows why a broken style file cannot be used', async () => {
    mockApi({
      'GET /api/styles': () => [{ ...fx.styleSummaries[0]!, error: 'style.json is not valid JSON' }],
    })
    renderApp('/styles')
    expect(await screen.findByText(/Can't be used: style.json is not valid JSON/)).toBeInTheDocument()
  })

  it('explains how to make a style by hand now, and AI creation in Phase 8', async () => {
    mockApi()
    const { user } = renderApp('/styles')
    await user.click(await screen.findByRole('button', { name: /Create style/ }))
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText(/Save as style…/)).toBeInTheDocument()
    expect(within(dialog).getByText(/arrives in Phase 8/)).toBeInTheDocument()
  })
})

describe('Style detail', () => {
  it('shows text, rules, parameters, samples and history', async () => {
    mockApi()
    renderApp('/styles/warm-film')
    expect(await screen.findByRole('heading', { name: 'Warm Film' })).toBeInTheDocument()
    expect(screen.getByText(/Version 2 · updated .* · 3 photos/)).toBeInTheDocument()
    expect(screen.getByText('Soft warm analog look.')).toBeInTheDocument()
    expect(screen.getByText('portraits')).toBeInTheDocument()
    expect(screen.getByText('White balance: fixed 6200 K, tint 0')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Sample 1 after' })).toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getByText('Tone › Exposure')).toBeInTheDocument()
    expect(within(table).getByText('+0.15 EV')).toBeInTheDocument()
    const versions = await screen.findByRole('list', { name: 'Versions' })
    expect(within(versions).getByText('warmer highlights')).toBeInTheDocument()
  })

  it('edits the name and description and saves them with a change note', async () => {
    const calls = mockApi()
    const { user } = renderApp('/styles/warm-film')
    await user.click(await screen.findByRole('button', { name: 'Edit name and description' }))
    const name = screen.getByLabelText('Name')
    await user.clear(name)
    await user.type(name, 'Warm Film II')
    await user.type(screen.getByLabelText('Change note'), 'renamed')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('heading', { name: 'Warm Film II' })).toBeInTheDocument()
    const put = calls.find((c) => c.method === 'PUT' && c.path === '/api/styles/warm-film')
    expect(put?.body).toMatchObject({ expected_version: 2, change_note: 'renamed', name: 'Warm Film II' })
  })

  it('says when another change came first and offers a reload', async () => {
    mockApi({ 'PUT /api/styles/:id': () => Response.json({ detail: 'at version 3' }, { status: 409 }) })
    const { user } = renderApp('/styles/warm-film')
    await user.click(await screen.findByRole('button', { name: 'Edit name and description' }))
    await user.click(screen.getByRole('button', { name: 'Save' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(/changed somewhere else/)
    expect(within(alert).getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  })

  it('edits the adaptive rules, with a hint per metering mode', async () => {
    const calls = mockApi()
    const { user } = renderApp('/styles/warm-film')
    await user.click(await screen.findByRole('button', { name: 'Edit rules' }))
    await user.click(screen.getByRole('switch', { name: 'Auto exposure' }))
    await user.selectOptions(screen.getByRole('combobox', { name: /^Metering/ }), 'highlights')
    expect(screen.getByText(/dark subjects stay dark \(a black cat/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    const body = calls.find((c) => c.method === 'PUT')!.body as { rules: { type: string; metering?: string }[] }
    expect(body.rules.map((r) => r.type)).toEqual(['exposure', 'white_balance'])
    expect(body.rules[0]!.metering).toBe('highlights')
    expect(await screen.findByText(/Auto exposure: highlights, default target/)).toBeInTheDocument()
  })

  it('removes a parameter from the style', async () => {
    const calls = mockApi()
    const { user } = renderApp('/styles/warm-film')
    await user.click(await screen.findByRole('button', { name: 'Remove Tone › Highlights from the style' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(calls.find((c) => c.method === 'PUT')!.body).toMatchObject({ values: { 'tone.exposure': 0.15 } })
  })

  it('adds selected photos to the test set', async () => {
    const calls = mockApi()
    const { user } = renderApp('/styles/warm-film', { selection: ['p001', 'p003'] })
    await user.click(await screen.findByRole('button', { name: 'Add 2 selected' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(calls.find((c) => c.method === 'PUT')!.body).toMatchObject({ test_photo_ids: ['p001', 'p003'] })
    expect(await screen.findByRole('img', { name: 'Test photo p001 with the style' })).toBeInTheDocument()
  })

  it('measures consistency and flags photos far from the rest', async () => {
    mockApi()
    const { user } = renderApp('/styles/warm-film')
    await user.click(await screen.findByRole('button', { name: /Measure on the photos using it \(3\)/ }))
    const photos = await screen.findByRole('table', { name: 'Photos in the report' })
    const rows = within(photos).getAllByRole('row')
    expect(rows[1]).toHaveTextContent(/DSCF5402.RAF\s*needs attention/) // sorted by distance from the median
    expect(rows[1]).toHaveTextContent(/limited to 1.5 EV/)
    const spread = screen.getByRole('table', { name: 'Spread before and after' })
    expect(within(spread).getByText('Middle brightness')).toBeInTheDocument()
  })

  it('renders samples from the selection', async () => {
    const calls = mockApi()
    const { user } = renderApp('/styles/warm-film', { selection: ['p001', 'p002'] })
    await user.click(await screen.findByRole('button', { name: /Render from 2 selected/ }))
    await waitFor(() => expect(calls.some((c) => c.path === '/api/styles/warm-film/samples')).toBe(true))
    expect(calls.find((c) => c.path === '/api/styles/warm-film/samples')!.body).toEqual({ photo_ids: ['p001', 'p002'] })
  })

  it('compares with an older version and brings it back', async () => {
    const calls = mockApi()
    const { user } = renderApp('/styles/warm-film')
    const versions = await screen.findByRole('list', { name: 'Versions' })
    expect(await screen.findByText('v1 → v2')).toBeInTheDocument() // the previous version by default
    expect(screen.getByText(/Tone › Highlights:/)).toHaveTextContent('-10 → -30')
    await user.click(within(versions).getByRole('button', { name: /Bring back/ }))
    await waitFor(() => expect(calls.some((c) => c.path === '/api/styles/warm-film/revert')).toBe(true))
    expect(calls.find((c) => c.path === '/api/styles/warm-film/revert')!.body).toEqual({
      version: 1,
      expected_version: 2,
    })
  })

  it('deletes after confirming how many photos are affected', async () => {
    const calls = mockApi()
    const { user } = renderApp('/styles/warm-film')
    await user.click(await screen.findByRole('button', { name: /Delete/ }))
    const dialog = screen.getByRole('dialog', { name: /Delete "Warm Film"/ })
    expect(within(dialog).getByText(/3 photos use this style\. They will drop back to no style/)).toBeInTheDocument()
    await user.click(within(dialog).getByRole('button', { name: 'Delete style' }))
    expect(await screen.findByRole('heading', { name: 'Styles' })).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'DELETE' && c.path === '/api/styles/warm-film')).toBe(true)
  })

  it('duplicates and opens the copy', async () => {
    mockApi()
    const { user } = renderApp('/styles/warm-film')
    await user.click(await screen.findByRole('button', { name: /Duplicate/ }))
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Warm Film (copy)' })).toBeInTheDocument())
  })

  it('shows its photos in the Library', async () => {
    const calls = mockApi()
    const { user } = renderApp('/styles/warm-film')
    await user.click(await screen.findByRole('button', { name: /Show photos/ }))
    expect(await screen.findByLabelText('Filter by style')).toHaveValue('warm-film')
    await waitFor(() => expect(calls.some((c) => c.path === '/api/photos' && c.query.get('style_id') === 'warm-film')).toBe(true))
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

  it('describes rules in words', () => {
    expect(
      describeRule({
        type: 'white_balance',
        rule_version: 1,
        mode: 'as_shot',
        temperature_offset: 400,
        tint_offset: -3,
        temperature: null,
        tint: null,
      }),
    ).toBe('White balance: as shot +400 K, tint -3')
    expect(
      describeRule({
        type: 'exposure',
        rule_version: 1,
        metering: 'camera_settings',
        target: -2,
        use_group: true,
        strength: 50,
        max_change: 1,
      }),
    ).toBe('Auto exposure: camera settings, target -2 stops, 50 %, max ±1 EV, uses the group when evened out')
  })
})
