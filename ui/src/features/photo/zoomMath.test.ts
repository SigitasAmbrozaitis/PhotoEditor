import { describe, expect, it } from 'vitest'
import { centeredOn, clampOffset, visibleTiles } from './zoomMath'

describe('zoom math', () => {
  it('lists the tiles covering the viewport, edge tiles smaller', () => {
    const image = { width: 1200, height: 700, tileSize: 512, scale: 1 }
    const tiles = visibleTiles(image, { x: 600, y: 300 }, { width: 500, height: 300 })
    expect(tiles.map((t) => [t.tx, t.ty])).toEqual([
      [1, 0],
      [2, 0],
      [1, 1],
      [2, 1],
    ])
    const corner = tiles.at(-1)!
    expect(corner).toEqual({ tx: 2, ty: 1, left: 424, top: 212, width: 176, height: 188 })
  })

  it('draws the 50 % tiles twice as large while 100 % loads', () => {
    const tiles = visibleTiles({ width: 600, height: 400, tileSize: 512, scale: 2 }, { x: 0, y: 0 }, { width: 1100, height: 500 })
    expect(tiles.map((t) => [t.tx, t.ty, t.width, t.height])).toEqual([
      [0, 0, 1024, 800],
      [1, 0, 176, 800],
    ])
  })

  it('keeps the image in view on whole pixels', () => {
    const size = { width: 1200, height: 700 }
    const view = { width: 500, height: 300 }
    expect(clampOffset({ x: -50, y: 900 }, size, view)).toEqual({ x: 0, y: 400 })
    expect(clampOffset({ x: 10.4, y: 20.6 }, size, view)).toEqual({ x: 10, y: 21 })
    // Smaller than the view: centered.
    expect(clampOffset({ x: 0, y: 0 }, { width: 300, height: 200 }, view)).toEqual({ x: -100, y: -50 })
  })

  it('centers on the focus point', () => {
    expect(centeredOn({ x: 0.5, y: 0.5 }, { width: 1200, height: 700 }, { width: 500, height: 300 })).toEqual({ x: 350, y: 200 })
    expect(centeredOn({ x: 0, y: 1 }, { width: 1200, height: 700 }, { width: 500, height: 300 })).toEqual({ x: 0, y: 400 })
  })
})
