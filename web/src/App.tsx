import { Route, Routes } from 'react-router'
import { ProjectList } from './pages/ProjectList'
import { ProjectDashboard } from './pages/ProjectDashboard'
import { RunHistory } from './pages/RunHistory'
import { RunReplay } from './pages/RunReplay'
import { Analytics } from './pages/Analytics'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<ProjectList />} />
      <Route path="/projects/:id" element={<ProjectDashboard />} />
      <Route path="/projects/:id/history" element={<RunHistory />} />
      <Route path="/projects/:id/runs/:runId" element={<RunReplay />} />
      <Route path="/analytics" element={<Analytics />} />
    </Routes>
  )
}
