/** Layout math for the zoom view: which tiles cover the viewport, and how far it may pan. */

export interface Point {
  x: number
  y: number
}

export interface Size {
  width: number
  height: number
}

export interface Tile {
  tx: number
  ty: number
  left: number
  top: number
  width: number
  height: number
}

/** Tiles of an image (width × height at the shown level, drawn `scale`× larger) that cover the viewport. */
export function visibleTiles(
  image: { width: number; height: number; tileSize: number; scale: number },
  offset: Point,
  viewport: Size,
): Tile[] {
  const step = image.tileSize * image.scale
  const tiles: Tile[] = []
  const firstX = Math.max(0, Math.floor(offset.x / step))
  const firstY = Math.max(0, Math.floor(offset.y / step))
  const lastX = Math.min(Math.ceil(image.width / image.tileSize) - 1, Math.floor((offset.x + viewport.width) / step))
  const lastY = Math.min(Math.ceil(image.height / image.tileSize) - 1, Math.floor((offset.y + viewport.height) / step))
  for (let ty = firstY; ty <= lastY; ty++) {
    for (let tx = firstX; tx <= lastX; tx++) {
      tiles.push({
        tx,
        ty,
        left: tx * step - offset.x,
        top: ty * step - offset.y,
        width: Math.min(image.tileSize, image.width - tx * image.tileSize) * image.scale,
        height: Math.min(image.tileSize, image.height - ty * image.tileSize) * image.scale,
      })
    }
  }
  return tiles
}

/** Keep the image covering the viewport (or centered when it is smaller), on whole pixels so tiles meet
 * without hairline seams. */
export function clampOffset(offset: Point, size: Size, viewport: Size): Point {
  const axis = (value: number, image: number, view: number) =>
    Math.round(image <= view ? -(view - image) / 2 : Math.min(Math.max(value, 0), image - view))
  return { x: axis(offset.x, size.width, viewport.width), y: axis(offset.y, size.height, viewport.height) }
}

/** The offset that puts `focus` (0..1 of the image) in the middle of the viewport, as far as the image allows. */
export function centeredOn(focus: Point, size: Size, viewport: Size): Point {
  return clampOffset(
    { x: focus.x * size.width - viewport.width / 2, y: focus.y * size.height - viewport.height / 2 },
    size,
    viewport,
  )
}
