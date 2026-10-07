import { act, renderHook } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'
import { fitInside } from '../hooks/useElementSize'
import { useSelection } from './selection'
import { SelectionProvider } from './SelectionProvider'

const ORDER = ['a', 'b', 'c', 'd', 'e']

function setup(initial?: string[]) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <SelectionProvider initial={initial}>{children}</SelectionProvider>
  )
  return renderHook(() => useSelection(), { wrapper })
}

describe('selection', () => {
  it('selectOnly, toggle and clear', () => {
    const { result } = setup()
    act(() => result.current.selectOnly('b'))
    expect(result.current.ids).toEqual(['b'])
    act(() => result.current.toggle('d'))
    expect(result.current.ids).toEqual(['b', 'd'])
    act(() => result.current.toggle('b'))
    expect(result.current.ids).toEqual(['d'])
    act(() => result.current.clear())
    expect(result.current.ids).toEqual([])
  })

  it('selects ranges in both directions from the anchor', () => {
    const { result } = setup()
    act(() => result.current.selectOnly('b'))
    act(() => result.current.selectRange(ORDER, 'd'))
    expect(result.current.ids).toEqual(['b', 'c', 'd'])
    act(() => result.current.selectRange(ORDER, 'a'))
    expect(result.current.ids).toEqual(['a', 'b'])
  })

  it('range without an anchor selects just that item', () => {
    const { result } = setup()
    act(() => result.current.selectRange(ORDER, 'c'))
    expect(result.current.ids).toEqual(['c'])
  })

  it('persists across reloads in sessionStorage', () => {
    const first = setup()
    act(() => first.result.current.selectAll(ORDER))
    first.unmount()
    const second = setup()
    expect(second.result.current.ids).toEqual(ORDER)
  })

  it('ignores corrupt stored data', () => {
    sessionStorage.setItem('photoedit.selection', '{not json')
    expect(setup().result.current.ids).toEqual([])
  })

  it('throws outside the provider', () => {
    expect(() => renderHook(() => useSelection())).toThrow(/SelectionProvider/)
  })
})

describe('fitInside', () => {
  it('fits by width or height', () => {
    expect(fitInside({ width: 1000, height: 1000 }, 1.5)).toEqual({ width: 1000, height: 666 })
    expect(fitInside({ width: 1000, height: 400 }, 1.5)).toEqual({ width: 600, height: 400 })
    expect(fitInside({ width: 0, height: 400 }, 1.5)).toEqual({ width: 0, height: 0 })
  })
})
