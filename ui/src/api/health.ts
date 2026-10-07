export interface Health {
  status: string
  version: string
}

/** Fetch backend health. Throws if the backend is unreachable or unhealthy. */
export async function fetchHealth(signal?: AbortSignal): Promise<Health> {
  const response = await fetch('/api/health', { signal })
  if (!response.ok) {
    throw new Error(`Health check failed: HTTP ${response.status}`)
  }
  return (await response.json()) as Health
}
