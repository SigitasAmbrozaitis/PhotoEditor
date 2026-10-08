/**
 * Editing state of the open photo: the parameters shown by the sliders, auto-save to the backend, undo/redo.
 *
 * Slider moves update the local parameters at once (so the UI keeps up) and save after a short pause. Saves
 * never overlap: while one is in flight, only the newest parameters wait for the next one, so responses (and
 * the preview versions they carry) can't arrive out of order.
 */
import { useCallback, useEffect, useReducer, useRef, useState } from 'react'
import { useResetEdit, useSaveEdit } from '../../api/queries'
import type { AdjustmentParams, PhotoDetail } from '../../api/types'

export const SAVE_DELAY_MS = 200

/** Return a copy of `params` with the dotted `path` set to `value`. */
export function withValue(params: AdjustmentParams, path: string, value: unknown): AdjustmentParams {
  const copy = structuredClone(params) as unknown as Record<string, unknown>
  const keys = path.split('.')
  let node = copy
  for (const key of keys.slice(0, -1)) node = node[key] as Record<string, unknown>
  node[keys.at(-1)!] = value
  return copy as unknown as AdjustmentParams
}

interface State {
  params: AdjustmentParams
  past: AdjustmentParams[]
  future: AdjustmentParams[]
  /** Parameters before the gesture in progress (a drag is one undo step). */
  gestureStart: AdjustmentParams | null
  /** How soon to save the current params: right away for undo/redo, after a pause while dragging. */
  saveDelay: number
}

type Action =
  | { type: 'preview'; path: string; value: unknown }
  | { type: 'commit'; params: AdjustmentParams }
  | { type: 'set'; path: string; value: unknown }
  | { type: 'undo' }
  | { type: 'redo' }
  | { type: 'loaded'; params: AdjustmentParams }

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'preview':
      return {
        ...state,
        params: withValue(state.params, action.path, action.value),
        gestureStart: state.gestureStart ?? state.params,
        saveDelay: SAVE_DELAY_MS,
      }
    case 'set':
      // Applied to the current parameters (not a copy captured at render time), so quick successive changes
      // (key repeat, fast clicks) all count.
      return reducer(state, { type: 'commit', params: withValue(state.params, action.path, action.value) })
    case 'commit':
      return {
        params: action.params,
        past: [...state.past, state.gestureStart ?? state.params],
        future: [],
        gestureStart: null,
        saveDelay: SAVE_DELAY_MS,
      }
    case 'undo': {
      const previous = state.past.at(-1)
      if (!previous) return state
      return {
        params: previous,
        past: state.past.slice(0, -1),
        future: [state.params, ...state.future],
        gestureStart: null,
        saveDelay: 0,
      }
    }
    case 'redo': {
      const [next, ...rest] = state.future
      if (!next) return state
      return { params: next, past: [...state.past, state.params], future: rest, gestureStart: null, saveDelay: 0 }
    }
    case 'loaded':
      // The backend already has these (after a reset): an undo step, but nothing to save.
      return { ...state, params: action.params, past: [...state.past, state.params], future: [], gestureStart: null }
  }
}

export interface EditSession {
  params: AdjustmentParams
  /** Live change during a gesture (drag): no undo step yet. */
  preview: (path: string, value: unknown) => void
  /** Finish a gesture or make a one-off change: one undo step. */
  commit: (next: AdjustmentParams) => void
  /** Set one value (from the current parameters): one undo step. */
  set: (path: string, value: unknown) => void
  resetAll: () => void
  undo: () => void
  redo: () => void
  canUndo: boolean
  canRedo: boolean
  saving: boolean
  error: string | null
}

export function useEditSession(detail: PhotoDetail): EditSession {
  const save = useSaveEdit(detail.photo.id)
  const reset = useResetEdit(detail.photo.id)
  const [state, dispatch] = useReducer(reducer, {
    params: detail.edit.adjustments,
    past: [],
    future: [],
    gestureStart: null,
    saveDelay: SAVE_DELAY_MS,
  })
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  const onServer = useRef(detail.edit.adjustments) // what the backend has (no need to save it again)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const inFlight = useRef(false)
  const queued = useRef<AdjustmentParams | null>(null)
  const mutate = useRef(save.mutateAsync)
  useEffect(() => {
    mutate.current = save.mutateAsync
  })

  const send = useCallback(async (params: AdjustmentParams) => {
    if (inFlight.current) {
      queued.current = params
      return
    }
    inFlight.current = true
    setSaving(true)
    let next: AdjustmentParams | null = params
    while (next) {
      queued.current = null
      try {
        await mutate.current(next)
        onServer.current = next
        setError(null)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Could not save the edit')
      }
      next = queued.current
    }
    inFlight.current = false
    setSaving(false)
  }, [])

  const pending = useRef<AdjustmentParams | null>(null)
  useEffect(() => {
    if (state.params === onServer.current) return
    pending.current = state.params
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      timer.current = null
      pending.current = null
      void send(state.params)
    }, state.saveDelay)
  }, [state.params, state.saveDelay, send])

  // Leaving the photo with a change still waiting: save it rather than drop it.
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current)
      if (pending.current) void send(pending.current)
    },
    [send],
  )

  const resetAll = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    pending.current = null
    reset.mutate(undefined, {
      onSuccess: (updated) => {
        onServer.current = updated.edit.adjustments
        dispatch({ type: 'loaded', params: updated.edit.adjustments })
      },
      onError: (e) => setError(e.message),
    })
  }, [reset])

  return {
    params: state.params,
    preview: useCallback((path: string, value: unknown) => dispatch({ type: 'preview', path, value }), []),
    commit: useCallback((params: AdjustmentParams) => dispatch({ type: 'commit', params }), []),
    set: useCallback((path: string, value: unknown) => dispatch({ type: 'set', path, value }), []),
    resetAll,
    undo: useCallback(() => dispatch({ type: 'undo' }), []),
    redo: useCallback(() => dispatch({ type: 'redo' }), []),
    canUndo: state.past.length > 0,
    canRedo: state.future.length > 0,
    saving: saving || reset.isPending,
    error,
  }
}
