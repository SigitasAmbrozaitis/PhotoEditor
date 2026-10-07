import { useBackendHealth, type BackendState } from './hooks/useBackendHealth'

function BackendBadge({ state }: { state: BackendState }) {
  switch (state.kind) {
    case 'checking':
      return <span className="badge badge--checking">connecting…</span>
    case 'online':
      return <span className="badge badge--online">backend v{state.version}</span>
    case 'offline':
      return (
        <span className="badge badge--offline" role="alert">
          backend offline
        </span>
      )
  }
}

export default function App() {
  const backend = useBackendHealth()

  return (
    <div className="app">
      <header className="topbar">
        <h1 className="brand">PhotoEditor</h1>
        <BackendBadge state={backend} />
      </header>
      <main className="content">
        <p className="placeholder">
          Project scaffold is running. Screens arrive in Phase 1 (UI skeleton).
        </p>
      </main>
    </div>
  )
}
