import { useQueryClient, type QueryClient } from '@tanstack/react-query'
import { Sparkles, X } from 'lucide-react'
import { Toast } from 'radix-ui'
import { useState } from 'react'
import { Link } from 'react-router'
import type { ExportPreset, PhotoDetail, PhotoPage, StyleSummary } from '../api/types'
import { describeActivity, type Activity } from '../hooks/liveUpdates'

export const TOAST_MS = 6000

/** Names already in the query cache (nothing is fetched just for a toast). */
function cachedName(client: QueryClient, kind: 'photo' | 'style' | 'preset', id: string): string | undefined {
  switch (kind) {
    case 'photo': {
      const detail = client.getQueryData<PhotoDetail>(['photo', id])
      if (detail) return detail.photo.filename
      for (const [, page] of client.getQueriesData<PhotoPage>({ queryKey: ['photos'] })) {
        const found = page?.items.find((p) => p.id === id)
        if (found) return found.filename
      }
      return undefined
    }
    case 'style':
      return client.getQueryData<StyleSummary[]>(['styles'])?.find((s) => s.id === id)?.name
    case 'preset':
      return client.getQueryData<ExportPreset[]>(['presets'])?.find((p) => p.id === id)?.name
  }
}

/** "Claude edited 24 photos": shown while Claude changes things, so the user sees what moved and where. */
export function ActivityToast({ activity }: { activity: Activity | null }) {
  const client = useQueryClient()
  // Closed for this moment of the burst; the next change (a new lastAt) shows it again.
  const [dismissed, setDismissed] = useState<number | null>(null)
  const message = activity && describeActivity(activity, (kind, id) => cachedName(client, kind, id))
  const close = () => setDismissed(activity?.lastAt ?? null)
  return (
    <Toast.Provider duration={TOAST_MS} label="Claude's changes">
      {activity && message && (
        <Toast.Root
          key={activity.id}
          open={dismissed !== activity.lastAt}
          onOpenChange={(open) => !open && close()}
          className="flex items-center gap-3 rounded-lg border border-line bg-panel px-3 py-2.5 text-sm text-fg shadow-2xl"
        >
          <Sparkles className="size-4 shrink-0 text-accent" aria-hidden />
          <Toast.Title className="min-w-0 flex-1">{message.text}</Toast.Title>
          {message.link && (
            <Toast.Action altText={`Show: ${message.text}`} asChild>
              <Link to={message.link} onClick={close} className="shrink-0 text-xs font-medium text-accent hover:underline">
                Show
              </Link>
            </Toast.Action>
          )}
          <Toast.Close aria-label="Close" className="shrink-0 rounded p-0.5 text-muted hover:bg-hover hover:text-fg">
            <X className="size-3.5" />
          </Toast.Close>
        </Toast.Root>
      )}
      <Toast.Viewport className="fixed right-4 bottom-4 z-50 flex w-[380px] max-w-[calc(100vw-2rem)] flex-col gap-2 outline-none" />
    </Toast.Provider>
  )
}
