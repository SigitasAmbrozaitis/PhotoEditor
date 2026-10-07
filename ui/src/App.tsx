import { QueryClientProvider, type QueryClient } from '@tanstack/react-query'
import { Tooltip } from 'radix-ui'
import { useState, type ReactNode } from 'react'
import { Navigate, Route, Routes } from 'react-router'
import { Layout } from './components/Layout'
import { EmptyState } from './components/ui'
import { JobsPage } from './features/jobs/JobsPage'
import { LibraryPage } from './features/library/LibraryPage'
import { PhotoPage } from './features/photo/PhotoPage'
import { PresetsPage } from './features/presets/PresetsPage'
import { StyleDetailPage } from './features/styles/StyleDetailPage'
import { StylesPage } from './features/styles/StylesPage'
import { createQueryClient } from './queryClient'
import { SelectionProvider } from './state/SelectionProvider'

/** Data, selection and tooltip providers. The router is supplied by the caller (BrowserRouter or MemoryRouter). */
export function Providers({ children, client }: { children: ReactNode; client?: QueryClient }) {
  const [defaultClient] = useState(createQueryClient)
  return (
    <QueryClientProvider client={client ?? defaultClient}>
      <Tooltip.Provider>
        <SelectionProvider>{children}</SelectionProvider>
      </Tooltip.Provider>
    </QueryClientProvider>
  )
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Navigate to="/library" replace />} />
        <Route path="library" element={<LibraryPage />} />
        <Route path="library/:photoId" element={<PhotoPage />} />
        <Route path="styles" element={<StylesPage />} />
        <Route path="styles/:styleId" element={<StyleDetailPage />} />
        <Route path="presets" element={<PresetsPage />} />
        <Route path="presets/:presetId" element={<PresetsPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="jobs/:jobId" element={<JobsPage />} />
        <Route path="*" element={<EmptyState title="Page not found." />} />
      </Route>
    </Routes>
  )
}
