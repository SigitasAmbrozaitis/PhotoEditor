import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { resetDetailsForTests } from '../../hooks/useDetails'
import * as fx from '../../test/fixtures'
import { mockApi, renderApp, type ApiCall } from '../../test/render'

const REVIEW = '/reviews/abcdef123456'

beforeEach(() => {
  localStorage.clear()
  resetDetailsForTests()
})

const sent = (calls: ApiCall[], method: string, path: string) =>
  calls.filter((c) => c.method === method && c.path.startsWith(path)).map((c) => c.body)

async function openPhoto(name: string) {
  const { user } = renderApp(REVIEW)
  await user.click(await screen.findByRole('button', { name }))
  const panel = await screen.findByRole('region', { name: `Review of ${name}` })
  return { user, panel }
}

describe('Prepare export dialog', () => {
  it('sends a prepare job with the style, preset and destination, then opens the review', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library', { selection: ['p001', 'p002'] })
    await user.click(await screen.findByRole('button', { name: /Prepare export…/ }))
    const dialog = screen.getByRole('dialog', { name: 'Prepare 2 photos for export' })
    await user.selectOptions(within(dialog).getByRole('combobox', { name: 'Style' }), 'warm-film')
    await user.click(within(dialog).getByRole('switch', { name: 'Even out these photos' }))
    await user.type(within(dialog).getByRole('textbox', { name: /Destination/ }), 'C:/Exports/ig')
    const prepare = within(dialog).getByRole('button', { name: 'Prepare' })
    await waitFor(() => expect(prepare).toBeEnabled())
    await user.click(prepare)

    await screen.findByRole('heading', { name: 'Review · instagram-portrait' })
    const [body] = sent(calls, 'POST', '/api/jobs') as Record<string, unknown>[]
    expect(body).toMatchObject({
      kind: 'prepare_export',
      photo_ids: ['p001', 'p002'],
      style_id: 'warm-film',
      even_out: true,
      preset_id: 'instagram-portrait',
      destination: 'C:/Exports/ig',
    })
  })
})

describe('Review screen', () => {
  it('lists Check first with reasons, then Ready, then what cannot be exported', async () => {
    mockApi()
    renderApp(REVIEW)
    const check = await screen.findByRole('region', { name: 'Check' })
    expect(within(check).getAllByRole('button').map((b) => b.getAttribute('aria-label'))).toEqual([
      'DSCF1002.RAF',
      'DSCF1003.RAF',
      'DSCF1005.RAF',
    ])
    expect(within(check).getByText('Two candidates')).toBeInTheDocument()
    expect(within(check).getByText('No subject')).toBeInTheDocument()
    expect(within(check).getByText('Zoom limit')).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Ready' })).getByRole('button', { name: 'DSCF1001.RAF' })).toBeVisible()
    expect(within(screen.getByRole('region', { name: "Can't be exported" })).getByText("Can't export")).toBeVisible()
    expect(screen.getByText(/1 ready · 3 to check · 0 approved · 1 can't be exported/)).toBeInTheDocument()
    // The first Check photo is open, with its reason in words.
    const panel = screen.getByRole('region', { name: 'Review of DSCF1002.RAF' })
    expect(within(panel).getByText('another car scores 0.80 (the car: 0.84)')).toBeInTheDocument()
  })

  it('choosing the other candidate frames it and approves the photo', async () => {
    const calls = mockApi()
    const { panel, user } = await openPhoto('DSCF1002.RAF')
    await user.click(within(panel).getByRole('button', { name: 'Use the truck (80 %)' }))
    await waitFor(() => expect(within(panel).getByText('approved')).toBeInTheDocument())
    expect(sent(calls, 'PUT', '/api/reviews/abcdef123456/items/p002/subject')).toEqual([{ candidate: 1 }])
    expect(within(panel).getByRole('button', { name: 'Use the truck (80 %)' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText(/2 ready · 2 to check/)).toBeInTheDocument()
  })

  it('a box drawn on the photo sets the subject', async () => {
    const calls = mockApi()
    const { panel, user } = await openPhoto('DSCF1003.RAF')
    await user.click(within(panel).getByRole('button', { name: /Set subject/ }))
    const photo = within(panel).getByTestId('review-photo')
    photo.getBoundingClientRect = () => ({ left: 0, top: 0, width: 200, height: 100, right: 200, bottom: 100, x: 0, y: 0, toJSON: () => ({}) })
    const draw = within(panel).getByTestId('review-draw')
    fireEvent.mouseDown(draw, { clientX: 20, clientY: 10 })
    fireEvent.mouseMove(window, { clientX: 100, clientY: 60 })
    fireEvent.mouseUp(window, { clientX: 100, clientY: 60 })
    await waitFor(() => expect(within(panel).getByRole('button', { name: 'Use detected' })).toBeInTheDocument())
    expect(sent(calls, 'PUT', '/api/reviews/abcdef123456/items/p003/subject')).toEqual([
      { box: { left: 0.1, top: 0.1, right: 0.5, bottom: 0.6 } },
    ])
    await user.click(within(panel).getByRole('button', { name: 'Use detected' }))
    await waitFor(() => expect(sent(calls, 'PUT', '/api/reviews/abcdef123456/items/p003/subject')).toHaveLength(2))
    expect(sent(calls, 'PUT', '/api/reviews/abcdef123456/items/p003/subject')[1]).toEqual({ box: null })
  })

  it('the zoom goes from 1 to the quality limit, marks the fast one, and Auto goes back', async () => {
    const calls = mockApi()
    const { panel, user } = await openPhoto('DSCF1005.RAF')
    const zoom = within(panel).getByRole('spinbutton', { name: 'Zoom' })
    expect(zoom).toHaveValue(1.54)
    expect(within(panel).getByRole('slider', { name: 'Zoom slider' })).toHaveAttribute('max', '3.08')
    expect(within(panel).getByText('│ fast 1.54×')).toBeInTheDocument()
    expect(within(panel).getByText('max 3.08× │')).toBeInTheDocument()
    expect(within(panel).getByRole('button', { name: 'Auto (1.54×)' })).toBeDisabled()

    await user.clear(zoom)
    await user.type(zoom, '2.4{Enter}')
    await waitFor(() => expect(within(panel).getByText(/needs the full decode/)).toBeInTheDocument())
    expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p005')).toEqual([{ zoom: 2.4 }])
    expect(within(panel).getByText('approved')).toBeInTheDocument()

    // Typed past the limit: it stops at the limit.
    await user.clear(zoom)
    await user.type(zoom, '9{Enter}')
    await waitFor(() => expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p005')).toHaveLength(2))
    expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p005')[1]).toEqual({ zoom: 3.08 })

    await user.click(within(panel).getByRole('button', { name: 'Auto (1.54×)' }))
    await waitFor(() => expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p005')).toHaveLength(3))
    expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p005')[2]).toEqual({ zoom: null })
  })

  it('A approves, the arrow keys move between photos', async () => {
    const calls = mockApi()
    const { user } = renderApp(REVIEW)
    await screen.findByRole('region', { name: 'Review of DSCF1002.RAF' })
    await user.keyboard('{ArrowRight}')
    const panel = await screen.findByRole('region', { name: 'Review of DSCF1003.RAF' })
    await user.keyboard('a')
    await waitFor(() => expect(within(panel).getByRole('button', { name: 'Unapprove' })).toBeInTheDocument())
    expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p003')).toEqual([{ approved: true }])
    await user.keyboard('{ArrowLeft}')
    expect(await screen.findByRole('region', { name: 'Review of DSCF1002.RAF' })).toBeInTheDocument()
  })

  it('the rules dialog saves the review settings', async () => {
    const calls = mockApi()
    const { user } = renderApp(REVIEW)
    await user.click(await screen.findByRole('button', { name: 'Rules…' }))
    const dialog = screen.getByRole('dialog', { name: 'Review rules' })
    const score = await within(dialog).findByRole('spinbutton', { name: /Minimum score/ })
    await user.clear(score)
    await user.type(score, '0.4')
    await user.click(within(dialog).getByRole('switch', { name: 'Two candidates' }))
    await user.click(within(dialog).getByRole('button', { name: 'Save rules' }))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'Review rules' })).not.toBeInTheDocument())
    expect(sent(calls, 'PUT', '/api/review-settings')).toEqual([
      expect.objectContaining({ min_score: 0.4, ambiguous: false, uncertain: true }),
    ])
  })
})

describe('Review export buttons', () => {
  it('Export Approved sends the approved ones and opens the job', async () => {
    const calls = mockApi()
    const { user } = renderApp(REVIEW)
    const button = await screen.findByRole('button', { name: 'Export Approved (1)' })
    expect(screen.getByRole('button', { name: 'Force Export All (4)' })).toBeEnabled()
    await user.click(button)
    expect(await screen.findByRole('heading', { name: 'Jobs' })).toBeInTheDocument()
    expect(sent(calls, 'POST', '/api/reviews/abcdef123456/export')).toEqual([{ scope: 'approved' }])
  })

  it('Force Export All asks first, naming the photos not approved', async () => {
    const calls = mockApi()
    const { user } = renderApp(REVIEW)
    await user.click(await screen.findByRole('button', { name: 'Force Export All (4)' }))
    const dialog = screen.getByRole('dialog', { name: 'Export 3 photos without a look?' })
    const names = within(within(dialog).getByRole('list', { name: 'Not approved' })).getAllByRole('listitem')
    expect(names.map((n) => n.textContent?.split(' · ')[0])).toEqual(['DSCF1002.RAF', 'DSCF1003.RAF', 'DSCF1005.RAF'])
    await user.click(within(dialog).getByRole('button', { name: 'Force Export All (4)' }))
    await waitFor(() => expect(sent(calls, 'POST', '/api/reviews/abcdef123456/export')).toEqual([{ scope: 'all' }]))
  })

  it('one Export All once nothing is left to approve', async () => {
    mockApi()
    const { user } = renderApp(REVIEW)
    for (const name of ['DSCF1002.RAF', 'DSCF1003.RAF', 'DSCF1005.RAF']) {
      await user.click(await screen.findByRole('button', { name }))
      const panel = await screen.findByRole('region', { name: `Review of ${name}` })
      await user.click(within(panel).getByRole('button', { name: /Approve \(A\)/ }))
      await waitFor(() => expect(within(panel).getByRole('button', { name: 'Unapprove' })).toBeInTheDocument())
    }
    expect(await screen.findByRole('button', { name: 'Export All (4)' })).toBeEnabled()
    expect(screen.queryByRole('button', { name: /Force Export All/ })).not.toBeInTheDocument()
  })
})

describe('Reviews list', () => {
  it('lists open reviews with what is left to check, and the nav shows the count', async () => {
    mockApi()
    const { user } = renderApp('/reviews')
    const list = await screen.findByRole('list', { name: 'Open reviews' })
    expect(within(list).getByText('3 to check')).toBeInTheDocument()
    expect(within(list).getByText('5 photos · instagram-portrait')).toBeInTheDocument()
    expect(screen.getByLabelText('3 to check')).toBeInTheDocument()
    await user.click(within(list).getByRole('button', { name: 'Discard review abcdef123456' }))
    expect(await screen.findByText('No open reviews.')).toBeInTheDocument()
  })

  it('a finished or discarded review says so', async () => {
    mockApi({ 'GET /api/reviews/:id': () => Response.json({ detail: 'not found' }, { status: 404 }) })
    renderApp(REVIEW)
    expect(await screen.findByText('This review is done or was discarded.')).toBeInTheDocument()
  })
})

describe('Review details, frame and live zoom (feedback)', () => {
  const rect = { left: 0, top: 0, width: 200, height: 100, right: 200, bottom: 100, x: 0, y: 0, toJSON: () => ({}) }

  it('shows what detection found with confidence by default; Hide details and D hide it', async () => {
    mockApi()
    const { user } = renderApp(REVIEW)
    const panel = await screen.findByRole('region', { name: 'Review of DSCF1002.RAF' })
    expect(within(panel).getByText('car 84 %', { selector: 'span.rounded-full' })).toBeInTheDocument() // by the tag
    const overlay = within(panel).getByTestId('detection-overlay')
    expect(within(overlay).getByText('truck 80 %')).toBeInTheDocument()
    expect(within(overlay).getByText('stands out 31 %')).toBeInTheDocument()
    expect(within(overlay).getByTestId('focus-point')).toBeInTheDocument()
    // The cards show the confidence too.
    expect(within(screen.getByRole('region', { name: 'Check' })).getAllByText('car 84 %').length).toBeGreaterThan(0)

    await user.click(within(panel).getByRole('button', { name: /Hide details/ }))
    expect(within(panel).queryByTestId('detection-overlay')).not.toBeInTheDocument()
    await user.keyboard('d')
    expect(within(panel).getByTestId('detection-overlay')).toBeInTheDocument()
  })

  it('dragging the frame saves its position; Re-center goes back to the subject', async () => {
    const calls = mockApi()
    const { user } = renderApp(REVIEW)
    const panel = await screen.findByRole('region', { name: 'Review of DSCF1002.RAF' })
    within(panel).getByTestId('review-photo').getBoundingClientRect = () => rect
    const frame = within(panel).getByTestId('review-frame')
    fireEvent.mouseDown(frame, { clientX: 140, clientY: 50 })
    fireEvent.mouseMove(window, { clientX: 100, clientY: 50 })
    // Moves while dragging (display only), saved on release.
    expect(parseFloat(frame.style.left)).toBeCloseTo(25)
    expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p002')).toEqual([])
    fireEvent.mouseUp(window, { clientX: 100, clientY: 50 })
    await waitFor(() => expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p002')).toHaveLength(1))
    expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p002')[0]).toEqual({ position: { x: 0.5, y: 0.5 } })
    await user.click(await within(panel).findByRole('button', { name: /Re-center on subject/ }))
    await waitFor(() => expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p002')).toHaveLength(2))
    expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p002')[1]).toEqual({ position: null })
  })

  it('the frame follows the zoom slider live and the zoom is saved on release', async () => {
    const calls = mockApi()
    const { panel } = await openPhoto('DSCF1005.RAF')
    await waitFor(() => expect(calls.some((c) => c.path.endsWith('/items/p005/frames'))).toBe(true))
    const frame = within(panel).getByTestId('review-frame')
    const slider = within(panel).getByRole('slider', { name: 'Zoom slider' })
    await waitFor(() => {
      fireEvent.change(slider, { target: { value: '2' } })
      // The fake's frame at 2×: a quarter of the photo wide around the crop's center (0.7).
      expect(frame.style.width).toBe('25%')
    })
    expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p005')).toEqual([])
    fireEvent.mouseUp(slider)
    await waitFor(() => expect(sent(calls, 'PATCH', '/api/reviews/abcdef123456/items/p005')).toEqual([{ zoom: 2 }]))
  })

  it('a review framed on the center has no subject tools', async () => {
    mockApi({
      'GET /api/reviews/:id': () => {
        const review = fx.makeReview()
        return { ...review, settings: { ...review.settings, aspect: { ...review.settings.aspect, anchor: 'center', zoom: 'off' } } }
      },
    })
    renderApp(REVIEW)
    const panel = await screen.findByRole('region', { name: 'Review of DSCF1002.RAF' })
    expect(within(panel).queryByRole('button', { name: /Set subject/ })).not.toBeInTheDocument()
    expect(within(panel).queryByRole('button', { name: /Use the truck/ })).not.toBeInTheDocument()
    expect(within(panel).queryByTestId('detection-overlay')).not.toBeInTheDocument()
  })

  it('the review opened straight from Prepare shows the job until it is ready', async () => {
    mockApi({
      'GET /api/reviews/:id': () => Response.json({ detail: 'not found' }, { status: 404 }),
      'GET /api/jobs': () => [
        fx.makeJob({ id: 'j0042', kind: 'prepare_export', status: 'running', progress: 0.5, completed: 3, total: 6, review_id: 'abcdef123456' }),
      ],
    })
    renderApp(REVIEW)
    expect(await screen.findByRole('heading', { name: 'Preparing the review…' })).toBeInTheDocument()
    expect(screen.getByText(/3 of 6/)).toBeInTheDocument()
  })

  it('the Prepare dialog frames on the subject unless switched off', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library', { selection: ['p001'] })
    await user.click(await screen.findByRole('button', { name: /Prepare export…/ }))
    const dialog = screen.getByRole('dialog', { name: 'Prepare 1 photo for export' })
    const frameOnSubject = await within(dialog).findByRole('switch', { name: 'Frame the crop on the subject' })
    expect(frameOnSubject).toBeChecked()
    await user.click(frameOnSubject)
    await user.type(within(dialog).getByRole('textbox', { name: /Destination/ }), 'C:/Exports/print')
    const prepare = within(dialog).getByRole('button', { name: 'Prepare' })
    await waitFor(() => expect(prepare).toBeEnabled())
    await user.click(prepare)
    await screen.findByRole('heading', { name: 'Review · instagram-portrait' })
    const [body] = sent(calls, 'POST', '/api/jobs') as { settings: { aspect: Record<string, unknown> } }[]
    expect(body!.settings.aspect).toMatchObject({ anchor: 'center', zoom: 'off' })
  })
})
