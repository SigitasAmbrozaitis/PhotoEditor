import { useRef, useState, type KeyboardEvent, type PointerEvent } from 'react'
import type { AdjustmentParams } from '../../api/types'
import { cn } from '../../lib/cn'
import { addPoint, clamp, movePoint, polyline, type Point } from './curveMath'
import { withValue, type EditSession } from './editSession'

type Channel = 'rgb' | 'red' | 'green' | 'blue'

const CHANNELS: { key: Channel; label: string; color: string }[] = [
  { key: 'rgb', label: 'RGB', color: '#d6d6d6' },
  { key: 'red', label: 'R', color: '#e05050' },
  { key: 'green', label: 'G', color: '#4fb453' },
  { key: 'blue', label: 'B', color: '#4a78d8' },
]
/** Point curves for RGB/R/G/B: drag points, click to add, double-click to remove; arrow keys nudge. */
export function ToneCurveEditor({ session }: { session: EditSession }) {
  const [channel, setChannel] = useState<Channel>('rgb')
  const [dragging, setDragging] = useState<number | null>(null)
  const svg = useRef<SVGSVGElement>(null)
  const params = session.params
  const points = params.tone_curve[channel] as Point[]
  const path = `tone_curve.${channel}`
  const color = CHANNELS.find((c) => c.key === channel)!.color

  const toCurve = (e: PointerEvent): Point => {
    const box = svg.current!.getBoundingClientRect()
    return { x: clamp((e.clientX - box.left) / box.width, 0, 1), y: clamp(1 - (e.clientY - box.top) / box.height, 0, 1) }
  }
  const commit = (next: Point[]) => session.commit(withValue(params, path, next) as AdjustmentParams)

  const onPointerDown = (e: PointerEvent, index: number) => {
    e.stopPropagation()
    if (e.detail >= 2) return // the second click of a double-click removes instead
    svg.current?.setPointerCapture(e.pointerId)
    setDragging(index)
  }
  const onPointerMove = (e: PointerEvent) => {
    if (dragging === null) return
    const p = toCurve(e)
    session.preview(path, movePoint(points, dragging, p.x, p.y))
  }
  const onPointerUp = (e: PointerEvent) => {
    if (dragging === null) return
    svg.current?.releasePointerCapture(e.pointerId)
    setDragging(null)
    commit(points)
  }
  const onBackgroundClick = (e: PointerEvent) => {
    if (dragging !== null) return
    const p = toCurve(e)
    const added = addPoint(points, p.x, p.y)
    if (added) commit(added)
  }
  const remove = (index: number) => {
    if (index === 0 || index === points.length - 1) return
    commit(points.filter((_, i) => i !== index))
  }
  const onKey = (e: KeyboardEvent, index: number) => {
    const step = e.shiftKey ? 0.05 : 0.01
    const moves: Record<string, [number, number]> = {
      ArrowUp: [0, step],
      ArrowDown: [0, -step],
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
    }
    const move = moves[e.key]
    if (move) {
      e.preventDefault()
      commit(movePoint(points, index, points[index]!.x + move[0], points[index]!.y + move[1]))
    } else if (e.key === 'Delete' || e.key === 'Backspace') {
      e.preventDefault()
      remove(index)
    }
  }

  return (
    <div className="mb-2">
      <div className="mb-1 flex gap-1" role="tablist" aria-label="Curve channel">
        {CHANNELS.map((c) => (
          <button
            key={c.key}
            type="button"
            role="tab"
            aria-selected={channel === c.key}
            onClick={() => setChannel(c.key)}
            className={cn(
              'rounded px-2 py-0.5 text-[11px]',
              channel === c.key ? 'bg-raised text-strong' : 'text-muted hover:text-fg',
            )}
          >
            {c.label}
          </button>
        ))}
      </div>
      <svg
        ref={svg}
        viewBox="0 0 100 100"
        className="aspect-square w-full cursor-crosshair touch-none rounded border border-line bg-bg select-none"
        aria-label={`Tone curve (${channel.toUpperCase()}): click to add a point`}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onClick={(e) => onBackgroundClick(e as unknown as PointerEvent)}
      >
        {[25, 50, 75].map((v) => (
          <g key={v} stroke="#333" strokeWidth="0.4">
            <line x1={v} y1="0" x2={v} y2="100" />
            <line x1="0" y1={v} x2="100" y2={v} />
          </g>
        ))}
        <line x1="0" y1="100" x2="100" y2="0" stroke="#444" strokeDasharray="2 2" strokeWidth="0.5" />
        {CHANNELS.filter((c) => c.key !== channel).map((c) => (
          <polyline
            key={c.key}
            fill="none"
            stroke={c.color}
            strokeOpacity="0.25"
            strokeWidth="0.6"
            points={polyline(params.tone_curve[c.key] as Point[])}
          />
        ))}
        <polyline fill="none" stroke={color} strokeWidth="1.2" points={polyline(points)} />
        {points.map((p, i) => (
          <circle
            key={i}
            cx={p.x * 100}
            cy={100 - p.y * 100}
            r={dragging === i ? 3 : 2.4}
            fill={color}
            stroke="#111"
            strokeWidth="0.6"
            tabIndex={0}
            role="slider"
            aria-label={`Point ${i + 1} of ${points.length}`}
            aria-valuetext={`input ${Math.round(p.x * 100)}%, output ${Math.round(p.y * 100)}%`}
            className="cursor-grab focus:outline-none focus-visible:stroke-accent"
            onPointerDown={(e) => onPointerDown(e, i)}
            onClick={(e) => e.stopPropagation()}
            onDoubleClick={(e) => {
              e.stopPropagation()
              remove(i)
            }}
            onKeyDown={(e) => onKey(e, i)}
          />
        ))}
      </svg>
    </div>
  )
}
