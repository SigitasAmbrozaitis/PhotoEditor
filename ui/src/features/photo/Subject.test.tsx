import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { CropSuggestionRequest, JobRequest } from '../../api/types'
import { resetGridForTests } from '../../hooks/useGrid'
import { mockApi, renderApp, type ApiCall } from '../../test/render'

// jsdom lays nothing out: give every element a size so the crop frame has one.
const sizes = { clientWidth: 800, clientHeight: 600 }
const saved: Record<string, PropertyDescriptor | undefined> = {}
beforeEach(() => {
  localStorage.clear()
  resetGridForTests()
  for (const [name, value] of Object.entries(sizes)) {
    saved[name] = Object.getOwnPropertyDescriptor(HTMLElement.prototype, name)
    Object.defineProperty(HTMLElement.prototype, name, { configurable: true, get: () => value })
  }
})
afterEach(() => {
  for (const name of Object.keys(sizes)) {
    if (saved[name]) Object.defineProperty(HTMLElement.prototype, name, saved[name])
  }
})

const suggestions = (calls: ApiCall[]) =>
  calls.filter((c) => c.path.endsWith('/suggest-crop')).map((c) => c.body as CropSuggestionRequest)
const subjectPuts = (calls: ApiCall[]) => calls.filter((c) => c.method === 'PUT' && c.path.endsWith('/subject'))

async function openCrop(calls = mockApi()) {
  const { user } = renderApp('/library/p001')
  await screen.findByRole('heading', { name: 'DSCF1001.RAF' })
  await user.keyboard('r')
  const tool = await screen.findByTestId('crop-tool')
  return { calls, user, tool }
}

describe('Suggest crop', () => {
  it('frames the subject in the draft, with placement and zoom', async () => {
    const { calls, user, tool } = await openCrop()
    await user.click(within(tool).getByRole('button', { name: /Suggest crop/ }))
    await waitFor(() => expect(suggestions(calls)).toHaveLength(1))
    // No aspect lock yet: the photo's own ratio, and the draft geometry (flips, turn, angle) goes along.
    expect(suggestions(calls)[0]).toMatchObject({ aspect: '6240:4160', placement: 'centered', zoom: 1 })
    expect(suggestions(calls)[0]!.geometry).toMatchObject({ rotate: 0, angle: 0 })
    const rect = screen.getByTestId('crop-rect')
    await waitFor(() => expect(parseFloat(rect.style.left)).toBeCloseTo(45)) // half the frame wide, on the car at x 0.7
    expect(screen.getByTestId('suggestion')).toHaveTextContent('framed on: car (detected)')
    expect(within(tool).getByRole('combobox', { name: 'Aspect ratio' })).toHaveValue('original')

    await user.selectOptions(within(tool).getByRole('combobox', { name: 'Placement' }), 'thirds')
    await waitFor(() => expect(suggestions(calls).at(-1)).toMatchObject({ placement: 'thirds' }))

    fireEvent.change(within(tool).getByRole('slider', { name: 'Zoom' }), { target: { value: '2' } })
    await waitFor(() => expect(suggestions(calls).at(-1)).toMatchObject({ zoom: 2 }))
    await waitFor(() => expect(parseFloat(rect.style.width)).toBeCloseTo(25))
    fireEvent.change(within(tool).getByRole('slider', { name: 'Zoom' }), { target: { value: '4' } })
    await waitFor(() => expect(screen.getByTestId('suggestion')).toHaveTextContent('zoom stopped at 2.50×'))
    expect(within(tool).getByText('2.50×')).toBeInTheDocument()

    // Done saves the suggested crop like any other.
    await user.click(within(tool).getByRole('button', { name: /Done/ }))
    await waitFor(() => expect(screen.queryByTestId('crop-tool')).not.toBeInTheDocument())
  })
})

describe('Subject overlay', () => {
  it('shows the subject with its kind and the other candidates faintly', async () => {
    const { calls, user, tool } = await openCrop()
    expect(calls.some((c) => c.path.endsWith('/subject'))).toBe(false) // only asked for when shown
    await user.click(within(tool).getByRole('button', { name: /Show subject/ }))
    const main = await screen.findByTestId('subject-box')
    expect(main).toHaveTextContent('car (detected)')
    expect(main.style.left).toBe('60%')
    expect(screen.getAllByTestId('subject-candidate')).toHaveLength(1) // the person; the car is the main box
    expect(screen.getByTestId('subject-summary')).toHaveTextContent('Subject: car (detected) · 84 %')
  })

  it('sets a subject by hand and goes back to the detected one', async () => {
    const { calls, user, tool } = await openCrop()
    const useDetected = within(tool).getByRole('button', { name: 'Use detected' })
    await user.click(within(tool).getByRole('button', { name: /Set subject/ }))
    const draw = screen.getByTestId('subject-draw')
    fireEvent.mouseDown(draw, { clientX: -200, clientY: -100 })
    fireEvent.mouseMove(window, { clientX: -50, clientY: 50 })
    fireEvent.mouseUp(window, { clientX: -50, clientY: 50 })
    await waitFor(() => expect(subjectPuts(calls)).toHaveLength(1))
    const box = (subjectPuts(calls)[0]!.body as { box: { left: number; right: number; top: number; bottom: number } }).box
    expect(box.left).toBeLessThan(box.right)
    expect(box.top).toBeLessThan(box.bottom)
    expect(await screen.findByTestId('subject-box')).toHaveTextContent('set by hand')
    expect(screen.queryByTestId('subject-draw')).not.toBeInTheDocument()

    await waitFor(() => expect(useDetected).toBeEnabled())
    await user.click(useDetected)
    await waitFor(() => expect(subjectPuts(calls).at(-1)?.body).toEqual({ box: null }))
    expect(await screen.findByText('car (detected)', { selector: 'span' })).toBeInTheDocument()
  })

  it('ignores a click that draws no box, and Esc stops drawing without leaving the tool', async () => {
    const { calls, user, tool } = await openCrop()
    await user.click(within(tool).getByRole('button', { name: /Set subject/ }))
    const draw = screen.getByTestId('subject-draw')
    fireEvent.mouseDown(draw, { clientX: 10, clientY: 10 })
    fireEvent.mouseUp(window, { clientX: 11, clientY: 10 })
    expect(subjectPuts(calls)).toHaveLength(0)
    await user.keyboard('{Escape}')
    expect(screen.queryByTestId('subject-draw')).not.toBeInTheDocument()
    expect(screen.getByTestId('crop-tool')).toBeInTheDocument()
  })
})

describe('Grid', () => {
  it('toggles with the button and G in the crop tool, and is remembered', async () => {
    const { user, tool } = await openCrop()
    const rect = screen.getByTestId('crop-rect')
    expect(within(rect).queryByTestId('thirds-grid')).not.toBeInTheDocument()
    await user.click(within(tool).getByRole('button', { name: /Grid/ }))
    expect(within(rect).getByTestId('thirds-grid')).toBeInTheDocument()
    expect(localStorage.getItem('photoedit.grid')).toBe('on')
    await user.keyboard('g')
    expect(within(rect).queryByTestId('thirds-grid')).not.toBeInTheDocument()
    expect(localStorage.getItem('photoedit.grid')).toBe('off')
  })

  it('shows over the photo view and starts as remembered', async () => {
    localStorage.setItem('photoedit.grid', 'on')
    resetGridForTests()
    mockApi()
    const { user } = renderApp('/library/p001')
    await screen.findByRole('heading', { name: 'DSCF1001.RAF' })
    expect(screen.getByTestId('thirds-grid')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Grid/ })).toHaveAttribute('aria-pressed', 'true')
    await user.keyboard('g')
    expect(screen.queryByTestId('thirds-grid')).not.toBeInTheDocument()
  })
})

describe('Subjects in the Library and the export', () => {
  it('detects the selection’s subjects in the background', async () => {
    const calls = mockApi()
    const { user } = renderApp('/library', { selection: ['p001', 'p002'] })
    await user.click(await screen.findByRole('button', { name: /Detect subjects/ }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/api/jobs')).toBe(true))
    const request = calls.find((c) => c.method === 'POST' && c.path === '/api/jobs')!.body as JobRequest
    expect(request).toEqual({ kind: 'detect_subjects', photo_ids: ['p001', 'p002'] })
  })

  it('frames on the subject and shows each photo’s subject in the plan', async () => {
    mockApi()
    const { user } = renderApp('/library', { selection: ['p001', 'p002'] })
    await user.click(await screen.findByRole('button', { name: /Export…/ }))
    const dialog = screen.getByRole('dialog', { name: 'Export 2 photos' })
    const anchor = await within(dialog).findByRole('combobox', { name: 'Frame the crop on' })
    await user.selectOptions(anchor, 'subject')
    await user.type(within(dialog).getByRole('textbox', { name: 'Destination folder' }), 'D:/Out')
    const plan = await within(dialog).findByRole('table', { name: 'Export plan' })
    await waitFor(() => expect(within(plan).getAllByTestId('plan-subject')).toHaveLength(2))
    const cells = within(plan).getAllByTestId('plan-subject')
    expect(cells[0]).toHaveTextContent('car (detected) · 84 %')
    expect(cells[1]).toHaveTextContent('none → centered')
    // The column already says it: no duplicate warning chip.
    expect(within(plan).queryByText('no subject found: centered')).not.toBeInTheDocument()
  })
})
