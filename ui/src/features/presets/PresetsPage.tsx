import { Copy, Lock, Save, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { useDeletePreset, useDuplicatePreset, usePresets, useUpdatePreset } from '../../api/queries'
import type { ExportPreset, ExportSettings, ExportTarget } from '../../api/types'
import {
  Button,
  Chip,
  Dialog,
  EmptyState,
  ErrorState,
  Field,
  Loading,
  PageHeader,
  TextArea,
  TextInput,
} from '../../components/ui'
import { cn } from '../../lib/cn'
import { ExportSettingsForm } from '../export/ExportSettingsForm'
import { exportSummary } from '../export/exportSummary'

const TARGET_LABELS: Record<ExportTarget, string> = {
  instagram: 'Instagram',
  print: 'Print',
  web: 'Web',
  custom: 'Custom',
}

export function PresetsPage() {
  const { presetId } = useParams()
  const presets = usePresets()
  const selected = presets.data?.find((p) => p.id === presetId) ?? presets.data?.[0]

  return (
    <>
      <PageHeader
        title="Export presets"
        subtitle="Reusable export settings. Built-in presets are read-only: duplicate one to make your own."
      />
      {presets.isError ? (
        <ErrorState error={presets.error} />
      ) : presets.isLoading ? (
        <Loading />
      ) : !presets.data?.length || !selected ? (
        <EmptyState title="No export presets." />
      ) : (
        <div className="flex min-h-0 flex-1">
          <ul aria-label="Export presets" className="w-80 shrink-0 overflow-y-auto border-r border-line bg-panel">
            {presets.data.map((p) => (
              <li key={p.id}>
                <Link
                  to={`/presets/${p.id}`}
                  aria-current={p.id === selected.id ? 'page' : undefined}
                  className={cn(
                    'flex flex-col gap-0.5 border-b border-line px-3 py-2',
                    p.id === selected.id ? 'bg-raised' : 'hover:bg-hover',
                  )}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-sm text-strong">
                      {p.builtin && <Lock className="size-3 text-muted" aria-label="built-in" />}
                      {p.name}
                    </span>
                    {p.error ? <Chip tone="err">Broken</Chip> : <Chip>{TARGET_LABELS[p.target]}</Chip>}
                  </span>
                  <span className="truncate font-mono text-[11px] text-muted">
                    {p.error ?? exportSummary(p.settings).split(' → ')[0]}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
          <div className="min-h-0 flex-1 overflow-y-auto p-4">
            {/* Keyed by version: a saved change (or another preset) starts a fresh, unmodified editor. */}
            <PresetEditor key={`${selected.id}@${selected.version}`} preset={selected} />
          </div>
        </div>
      )}
    </>
  )
}

function PresetEditor({ preset }: { preset: ExportPreset }) {
  const navigate = useNavigate()
  const duplicate = useDuplicatePreset()
  const update = useUpdatePreset(preset.id)
  const [name, setName] = useState(preset.name)
  const [description, setDescription] = useState(preset.description)
  const [settings, setSettings] = useState<ExportSettings>(preset.settings)
  const [deleting, setDeleting] = useState(false)
  const editable = !preset.builtin && !preset.error
  const changed =
    name !== preset.name || description !== preset.description || JSON.stringify(settings) !== JSON.stringify(preset.settings)

  const copy = () =>
    duplicate.mutate({ id: preset.id }, { onSuccess: (created) => void navigate(`/presets/${created.id}`) })
  const save = () =>
    update.mutate({ expected_version: preset.version, name: name.trim(), description, settings })

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          {editable ? (
            <div className="flex flex-col gap-2">
              <Field label="Name">
                <TextInput value={name} maxLength={80} onChange={(e) => setName(e.target.value)} aria-label="Preset name" />
              </Field>
              <Field label="Description">
                <TextArea
                  value={description}
                  rows={2}
                  onChange={(e) => setDescription(e.target.value)}
                  aria-label="Preset description"
                />
              </Field>
            </div>
          ) : (
            <>
              <h2 className="flex items-center gap-2 text-base font-semibold text-strong">
                {preset.name}
                {preset.builtin && <Lock className="size-3.5 text-muted" aria-label="built-in (read-only)" />}
              </h2>
              <p className="text-sm text-muted">{preset.description}</p>
            </>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          {editable && (
            <Button variant="primary" disabled={!changed || !name.trim() || update.isPending} onClick={save}>
              <Save className="size-4" aria-hidden /> Save
            </Button>
          )}
          {!preset.error && (
            <Button onClick={copy} disabled={duplicate.isPending}>
              <Copy className="size-4" aria-hidden /> {preset.builtin ? 'Duplicate to edit' : 'Duplicate'}
            </Button>
          )}
          {!preset.builtin && (
            <Button variant="danger" onClick={() => setDeleting(true)}>
              <Trash2 className="size-4" aria-hidden /> Delete
            </Button>
          )}
        </div>
      </div>
      {preset.error && (
        <p role="alert" className="rounded border border-err/40 bg-err/10 p-2 text-xs text-err">
          This preset's file can't be read: {preset.error}
        </p>
      )}
      {update.isError && <ErrorState error={update.error} />}
      {duplicate.isError && <ErrorState error={duplicate.error} />}
      {!preset.error && <ExportSettingsForm value={settings} onChange={setSettings} disabled={!editable} />}
      <DeletePresetDialog preset={preset} open={deleting} onOpenChange={setDeleting} />
    </div>
  )
}

function DeletePresetDialog({
  preset,
  open,
  onOpenChange,
}: {
  preset: ExportPreset
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const navigate = useNavigate()
  const remove = useDeletePreset()
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={`Delete "${preset.name}"?`}
      description="The preset file is removed from export-presets/. Exported files are not affected."
      width="max-w-md"
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(preset.id, {
                onSuccess: () => {
                  onOpenChange(false)
                  void navigate('/presets')
                },
              })
            }
          >
            Delete preset
          </Button>
        </>
      }
    >
      {remove.isError ? <ErrorState error={remove.error} /> : <p className="text-sm">This can't be undone.</p>}
    </Dialog>
  )
}
