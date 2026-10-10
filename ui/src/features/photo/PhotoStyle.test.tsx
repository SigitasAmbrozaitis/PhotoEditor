import { screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import * as fx from '../../test/fixtures'
import { mockApi, renderApp } from '../../test/render'
import { changedPerGroup, differingPaths } from './photoStyleGroups'

function panel() {
  return screen.findByRole('complementary', { name: 'Photo details' })
}

describe('Photo view: style', () => {
  it("shows the photo's style, what its rules did and which sliders come from it", async () => {
    mockApi()
    renderApp('/library/p002')
    const details = await panel()
    expect(await within(details).findByRole('combobox', { name: 'Style' })).toHaveValue('warm-film')
    const rules = within(details).getByRole('list', { name: "What the style's rules did" })
    expect(rules).toHaveTextContent('White balance: fixed: 6200 K, tint +0.0')
    expect(within(details).getAllByLabelText('from the style').length).toBeGreaterThan(0)
    expect(within(details).getByText('The style only')).toBeInTheDocument()
    expect(within(details).getByRole('button', { name: 'Reset all' })).toHaveAttribute(
      'title',
      "Drop this photo's own changes (the style stays)",
    )
  })

  it('applies or removes a style right away', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library/p001')
    const details = await panel()
    const picker = await within(details).findByRole('combobox', { name: 'Style' })
    await within(picker).findByRole('option', { name: 'Warm Film' })
    await user.selectOptions(picker, 'warm-film')
    await waitFor(() => expect(calls.some((c) => c.path === '/api/photos/p001/style')).toBe(true))
    expect(calls.find((c) => c.path === '/api/photos/p001/style')!.body).toEqual({ style_id: 'warm-film' })
    expect(await within(details).findByRole('combobox', { name: 'Style' })).toHaveValue('warm-film')
    await user.selectOptions(within(details).getByRole('combobox', { name: 'Style' }), '')
    await waitFor(() => expect(calls.filter((c) => c.path === '/api/photos/p001/style')).toHaveLength(2))
    expect(calls.filter((c) => c.path === '/api/photos/p001/style').at(-1)!.body).toEqual({ style_id: null })
  })

  it("saves the photo's look as a new style and uses it for the photo", async () => {
    const calls = mockApi()
    const { user } = renderApp('/library/p002')
    const details = await panel()
    await user.click(await within(details).findByRole('button', { name: /Save as style…/ }))
    const dialog = within(screen.getByRole('dialog', { name: 'Save as style' }))
    // Only groups the photo changed are preselected, with their counts.
    expect(dialog.getByRole('checkbox', { name: /Tone 1 changed/ })).toBeChecked()
    expect(dialog.getByRole('checkbox', { name: /HSL \/ color mixer unchanged/ })).not.toBeChecked()
    expect(dialog.getByRole('button', { name: 'Create style' })).toBeDisabled() // needs a name
    await user.type(dialog.getByRole('textbox', { name: 'Name' }), 'Golden cats')
    expect(dialog.getByText(/brings other photos to this photo's brightness/)).toBeInTheDocument()
    await user.click(dialog.getByRole('button', { name: 'Create style' }))
    await waitFor(() => expect(calls.some((c) => c.path === '/api/photos/p002/style')).toBe(true))
    expect(calls.find((c) => c.path === '/api/styles/from-photo')!.body).toEqual({
      photo_id: 'p002',
      name: 'Golden cats',
      description: '',
      groups: ['tone'],
      exposure: 'match',
      white_balance: 'offset',
    })
    expect(calls.find((c) => c.path === '/api/photos/p002/style')!.body).toEqual({ style_id: 'new-look' })
  })

  it('updates the style from the photo, saying how many photos change', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library/p002')
    const details = await panel()
    await user.click(await within(details).findByRole('button', { name: /Update style…/ }))
    const dialog = within(await screen.findByRole('dialog', { name: /Update "Warm Film" from this photo/ }))
    const submit = await dialog.findByRole('button', { name: 'Update style (3 photos change)' })
    await user.type(dialog.getByRole('textbox', { name: 'Change note' }), 'brighter')
    await user.click(submit)
    await waitFor(() => expect(calls.some((c) => c.path === '/api/styles/warm-film/from-photo')).toBe(true))
    expect(calls.find((c) => c.path === '/api/styles/warm-film/from-photo')!.body).toEqual({
      photo_id: 'p002',
      groups: ['tone'],
      expected_version: 2,
      change_note: 'brighter',
    })
  })

  it('has no "Update style" without a style', async () => {
    mockApi()
    renderApp('/library/p001')
    const details = await panel()
    await within(details).findByRole('button', { name: /Save as style…/ })
    expect(within(details).queryByRole('button', { name: /Update style…/ })).not.toBeInTheDocument()
  })
})

describe('changed values per group', () => {
  it('compares leaves, with curves as a whole', () => {
    const a = fx.neutralAdjustments()
    const b = fx.neutralAdjustments()
    b.tone.contrast = 10
    b.tone.exposure = 0.5 // exposure is a separate choice, not counted
    b.tone_curve.rgb = [
      { x: 0, y: 0.05 },
      { x: 1, y: 1 },
    ]
    b.hsl.green.saturation = -20
    expect(differingPaths(a, b)).toEqual(['tone.exposure', 'tone.contrast', 'tone_curve.rgb', 'hsl.green.saturation'])
    expect(changedPerGroup(b, a)).toEqual({ tone: 1, tone_curve: 1, hsl: 1 })
  })
})
