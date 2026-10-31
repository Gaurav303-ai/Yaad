// TODO: Replace the placeholder routes as product flows are implemented.
import type { JSX } from 'react'
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/layout/Sidebar'
import { Toaster } from './components/ui/sonner'
import { Conflicts } from './pages/Conflicts'
import { Dashboard } from './pages/Dashboard'
import { Digest } from './pages/Digest'
import { MeetingRoom } from './pages/MeetingRoom'
import { Meetings } from './pages/Meetings'
import { Memory } from './pages/Memory'
import { Person } from './pages/Person'
import { Review } from './pages/Review'

function AppLayout(): JSX.Element {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  )
}

export default function App(): JSX.Element {
  return (
    <BrowserRouter>
      <Toaster />
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Dashboard />} />
          <Route path="meetings" element={<Meetings />} />
          <Route path="meetings/:meetingId" element={<MeetingRoom />} />
          <Route path="review" element={<Review />} />
          <Route path="conflicts" element={<Conflicts />} />
          <Route path="memory" element={<Memory />} />
          <Route path="people" element={<Person />} />
          <Route path="people/:personId" element={<Person />} />
          <Route path="digest" element={<Digest />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
