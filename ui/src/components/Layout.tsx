import { Download, FolderOpen, Images, ListChecks, LoaderCircle, Palette } from 'lucide-react'
import { NavLink, Outlet } from 'react-router'
import { useJobs, useLibrary } from '../api/queries'
import { useBackendHealth, type BackendState } from '../hooks/useBackendHealth'
import { Tooltip } from './ui'
import { cn } from '../lib/cn'

const NAV = [
  { to: '/library', label: 'Library', icon: Images },
  { to: '/styles', label: 'Styles', icon: Palette },
  { to: '/presets', label: 'Export presets', icon: Download },
  { to: '/jobs', label: 'Jobs', icon: ListChecks },
] as const

export function BackendBadge({ state }: { state: BackendState }) {
  switch (state.kind) {
    case 'checking':
      return <span className="rounded-full border border-warn px-2 py-0.5 font-mono text-[11px] text-warn">connecting…</span>
    case 'online':
      return (
        <span className="rounded-full border border-ok px-2 py-0.5 font-mono text-[11px] text-ok">
          backend v{state.version}
        </span>
      )
    case 'offline':
      return (
        <span role="alert" className="rounded-full bg-err px-2 py-0.5 font-mono text-[11px] text-white">
          backend offline
        </span>
      )
  }
}

function JobIndicator() {
  const { data: jobs } = useJobs()
  const running = jobs?.filter((j) => j.status === 'running' || j.status === 'queued') ?? []
  if (running.length === 0) return null
  const progress = running.reduce((sum, j) => sum + j.progress, 0) / running.length
  return (
    <NavLink
      to="/jobs"
      className="flex items-center gap-2 rounded px-2 py-1 text-xs text-fg hover:bg-hover"
      aria-label={`${running.length} job${running.length === 1 ? '' : 's'} running`}
    >
      <LoaderCircle className="size-3.5 animate-spin text-accent" aria-hidden />
      <span>
        {running.length} running · {Math.round(progress * 100)}%
      </span>
    </NavLink>
  )
}

function TopBar() {
  const backend = useBackendHealth()
  const { data: library } = useLibrary()
  return (
    <header className="flex h-10 shrink-0 items-center gap-4 border-b border-line bg-panel px-3">
      <span className="text-sm font-semibold tracking-wide text-strong">PhotoEditor</span>
      <Tooltip content="Mock data: Phase 1 UI skeleton. Real photos arrive in Phase 2.">
        <span className="rounded bg-warn/15 px-1.5 py-0.5 text-[11px] font-medium text-warn">DEMO DATA</span>
      </Tooltip>
      {library?.folder && (
        <span className="flex min-w-0 items-center gap-1.5 text-xs text-muted" title={library.folder}>
          <FolderOpen className="size-3.5 shrink-0" aria-hidden />
          <span className="truncate">{library.folder}</span>
        </span>
      )}
      <div className="flex-1" />
      <JobIndicator />
      <BackendBadge state={backend} />
    </header>
  )
}

function NavRail() {
  return (
    <nav aria-label="Main" className="flex w-[76px] shrink-0 flex-col gap-1 border-r border-line bg-panel py-2">
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            cn(
              'mx-1.5 flex flex-col items-center gap-1 rounded px-1 py-2 text-center text-[11px] leading-tight',
              isActive ? 'bg-raised text-strong' : 'text-muted hover:bg-hover hover:text-fg',
            )
          }
        >
          <Icon className="size-5" aria-hidden />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

export function Layout() {
  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <NavRail />
        <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
