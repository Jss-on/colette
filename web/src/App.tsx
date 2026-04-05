import { Route, Routes } from 'react-router'
import { ProjectList } from './pages/ProjectList'
import { ProjectDashboard } from './pages/ProjectDashboard'

export function App() {
  return (
    <Routes>
      <Route path="/" element={<ProjectList />} />
      <Route path="/projects/:id" element={<ProjectDashboard />} />
    </Routes>
  )
}
