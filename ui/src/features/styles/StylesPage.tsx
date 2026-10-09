import { Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { useStyles } from '../../api/queries'
import { Button, Dialog, EmptyState, ErrorState, Loading, PageHeader } from '../../components/ui'

function CreateStyleDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Create style"
      description="Coming in Phase 8: AI style creation"
      width="max-w-lg"
      footer={
        <Button variant="primary" onClick={() => onOpenChange(false)}>
          OK
        </Button>
      }
    >
      <div className="flex flex-col gap-2 text-sm">
        <p>Creating a style from sample photos arrives in Phase 8. The flow will be:</p>
        <ol className="list-decimal space-y-1 pl-5 text-muted">
          <li>You provide sample photos: finished photos, and/or RAWs with your edited versions.</li>
          <li>The AI analyzes them and proposes style parameters.</li>
          <li>It renders before/after previews and refines them with you.</li>
          <li>The style is saved with a description and sample images.</li>
        </ol>
      </div>
    </Dialog>
  )
}

export function StylesPage() {
  const styles = useStyles()
  const [creating, setCreating] = useState(false)

  return (
    <>
      <PageHeader
        title="Styles"
        subtitle={styles.data ? `${styles.data.length} styles` : undefined}
        actions={
          <Button variant="primary" onClick={() => setCreating(true)}>
            <Plus className="size-4" aria-hidden /> Create style…
          </Button>
        }
      />
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {styles.isError ? (
          <ErrorState error={styles.error} />
        ) : styles.isLoading ? (
          <Loading label="Loading styles…" />
        ) : !styles.data?.length ? (
          <EmptyState title="No styles yet." />
        ) : (
          <ul className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
            {styles.data.map((s) => (
              <li key={s.id}>
                <Link
                  to={`/styles/${s.id}`}
                  className="flex h-full flex-col overflow-hidden rounded-lg border border-line bg-panel transition-colors hover:border-muted"
                >
                  {s.cover_url ? (
                    <img src={s.cover_url} alt={`${s.name} sample`} className="aspect-[3/2] w-full object-cover" />
                  ) : (
                    <div className="checker aspect-[3/2] w-full" />
                  )}
                  <div className="flex flex-1 flex-col gap-1 p-3">
                    <h2 className="text-sm font-semibold text-strong">{s.name}</h2>
                    <p className="line-clamp-3 text-xs text-muted">{s.description}</p>
                    {s.updated_at && (
                      <p className="mt-auto pt-2 text-[11px] text-muted">
                        Updated {new Date(s.updated_at).toLocaleDateString()}
                      </p>
                    )}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
      <CreateStyleDialog open={creating} onOpenChange={setCreating} />
    </>
  )
}
