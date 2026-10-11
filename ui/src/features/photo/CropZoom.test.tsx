import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { AdjustmentParams, Geometry } from '../../api/types'
import { mockApi, renderApp, type ApiCall } from '../../test/render'

// jsdom lays nothing out: give every element a size so the crop frame and the zoom viewport have one.
const sizes = { clientWidth: 800, clientHeight: 600 }
const saved: Record<string, PropertyDescriptor | undefined> = {}
beforeEach(() => {
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

const previews = (calls: ApiCall[]) => calls.filter((c) => c.path.endsWith('/geometry/preview'))
const saves = (calls: ApiCall[]) =>
  calls.filter((c) => c.method === 'PUT' && c.path.endsWith('/edit')).map((c) => (c.body as AdjustmentParams).geometry)

async function openCrop(calls = mockApi()) {
  const { user } = renderApp('/library/p001')
  await screen.findByRole('heading', { name: 'DSCF1001.RAF' })
  await user.keyboard('r')
  const tool = await screen.findByTestId('crop-tool')
  return { calls, user, tool }
}

describe('Crop tool', () => {
  it('sends straighten, aspect and turns to core and saves on Done', async () => {
    const { calls, user, tool } = await openCrop()
    const angle = within(tool).getByRole('spinbutton', { name: 'Straighten angle' })
    fireEvent.change(angle, { target: { value: '5' } })
    await waitFor(() => expect(previews(calls).at(-1)?.body).toMatchObject({ change: { angle: 5 } }))
    // Core shrank the crop: the rectangle shows it.
    await waitFor(() => expect(screen.getByTestId('crop-rect').style.left).toBe('10%'))
    await user.selectOptions(within(tool).getByRole('combobox', { name: 'Aspect ratio' }), '4:5')
    await waitFor(() => expect(previews(calls).at(-1)?.body).toMatchObject({ change: { aspect: '4:5' } }))
    await user.click(within(tool).getByRole('button', { name: 'Rotate right' }))
    await waitFor(() => expect(previews(calls).at(-1)?.body).toMatchObject({ change: { rotate: 90 } }))
    await user.click(within(tool).getByRole('button', { name: /Done/ }))
    await waitFor(() => expect(screen.queryByTestId('crop-tool')).not.toBeInTheDocument())
    await waitFor(() => expect(saves(calls).at(-1)).toMatchObject({ angle: 5, aspect: '4:5', rotate: 90 }))
  })

  it('drags a corner within the photo', async () => {
    const { tool } = await openCrop()
    const rect = screen.getByTestId('crop-rect')
    expect(rect.style.width).toBe('100%')
    fireEvent.mouseDown(within(tool).getByLabelText('Crop handle se'), { clientX: 700, clientY: 500 })
    fireEvent.mouseMove(window, { clientX: 500, clientY: 400 })
    fireEvent.mouseUp(window)
    expect(parseFloat(rect.style.width)).toBeLessThan(100)
    expect(rect.style.left).toBe('0%')
  })

  it('keeps the tool open with the message when core refuses the crop', async () => {
    const calls = mockApi({
      'POST /api/photos/:id/geometry/preview': ({ body }) => {
        const { change, geometry } = body as { change: Partial<Geometry>; geometry: Geometry }
        if (change.crop) return Response.json({ detail: 'the crop reaches outside the photo' }, { status: 400 })
        return { ...geometry, ...change }
      },
    })
    const { user, tool } = await openCrop(calls)
    await user.click(within(tool).getByRole('button', { name: /Done/ }))
    expect(await within(tool).findByRole('alert')).toHaveTextContent('the crop reaches outside the photo')
    expect(screen.getByTestId('crop-tool')).toBeInTheDocument()
    expect(saves(calls)).toEqual([])
  })

  it('cancels with Escape without saving, and undo walks back a crop', async () => {
    const { calls, user, tool } = await openCrop()
    fireEvent.change(within(tool).getByRole('spinbutton', { name: 'Straighten angle' }), { target: { value: '3' } })
    await waitFor(() => expect(previews(calls)).toHaveLength(1))
    await user.keyboard('{Escape}')
    expect(screen.queryByTestId('crop-tool')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'DSCF1001.RAF' })).toBeInTheDocument() // still on the photo
    expect(saves(calls)).toEqual([])

    await user.keyboard('r')
    const again = await screen.findByTestId('crop-tool')
    await user.click(within(again).getByRole('button', { name: 'Flip horizontal' }))
    await waitFor(() => expect(previews(calls).at(-1)?.body).toMatchObject({ change: { flip_horizontal: true } }))
    await user.keyboard('{Enter}')
    await waitFor(() => expect(saves(calls).at(-1)?.flip_horizontal).toBe(true))
    await user.click(screen.getByRole('button', { name: 'Undo' }))
    await waitFor(() => expect(saves(calls).at(-1)?.flip_horizontal).toBe(false))
  })
})

describe('Zoom view', () => {
  it('shows 100 % tiles for the viewport and goes back to fit', async () => {
    mockApi()
    const { user } = renderApp('/library/p001')
    await screen.findByRole('heading', { name: 'DSCF1001.RAF' })
    await user.click(screen.getByRole('button', { name: '100%' }))
    const view = await screen.findByTestId('zoom-view')
    // 1200 × 800 at 100 %, centered in an 800 × 600 view: the four tiles around the middle.
    await waitFor(() => expect(view.querySelectorAll('img[src*="/tiles/"]')).toHaveLength(4))
    const sources = [...view.querySelectorAll('img[src*="/tiles/"]')].map((i) => i.getAttribute('src'))
    expect(sources[0]).toContain('/zoom/100/tiles/0/0')
    expect(screen.getByTestId('zoom-navigator')).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByTestId('zoom-view')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'DSCF1001.RAF' })).toBeInTheDocument()
  })

  it('shows the 50 % tiles enlarged while the full decode runs', async () => {
    mockApi({
      'GET /api/photos/:id/zoom/:level': ({ path }) =>
        path.endsWith('/100')
          ? { level: 100, state: 'decoding', width: null, height: null, tile_size: 512 }
          : { level: 50, state: 'ready', width: 600, height: 400, tile_size: 512 },
    })
    const { user } = renderApp('/library/p001')
    await screen.findByRole('heading', { name: 'DSCF1001.RAF' })
    await user.keyboard('z')
    const view = await screen.findByTestId('zoom-view')
    expect(await within(view).findByText(/Loading full size/)).toBeInTheDocument()
    await waitFor(() => expect(view.querySelector('img[src*="/zoom/50/tiles/"]')).not.toBeNull())
    const tile = view.querySelector<HTMLImageElement>('img[src*="/zoom/50/tiles/0/0"]')!
    expect(tile.style.width).toBe('1024px')
  })

  it('shows before tiles in Before mode', async () => {
    mockApi()
    const { user } = renderApp('/library/p001')
    await screen.findByRole('heading', { name: 'DSCF1001.RAF' })
    await user.click(screen.getByRole('button', { name: 'Before' }))
    await user.click(screen.getByRole('button', { name: '50%' }))
    const view = await screen.findByTestId('zoom-view')
    await waitFor(() => expect(view.querySelector('img[src*="/tiles/"]')).not.toBeNull())
    expect(view.querySelector('img[src*="/tiles/"]')!.getAttribute('src')).toContain('before=true')
  })
})
