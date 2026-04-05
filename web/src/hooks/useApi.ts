const BASE = '/api/v1'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init)
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

export function fetchProjects() {
  return apiFetch<{ data: Record<string, unknown>[]; total: number }>('/projects')
}

export function fetchAgents(projectId: string) {
  return apiFetch<{ agents: Record<string, unknown>[] }>(`/projects/${projectId}/agents`)
}

export function fetchConversation(projectId: string) {
  return apiFetch<{ entries: Record<string, unknown>[] }>(`/projects/${projectId}/conversation`)
}

export function approveGate(gateId: string) {
  return apiFetch<void>(`/approvals/${gateId}/approve`, { method: 'POST' })
}

export function rejectGate(gateId: string) {
  return apiFetch<void>(`/approvals/${gateId}/reject`, { method: 'POST' })
}

export function fetchArtifacts(projectId: string) {
  return apiFetch<{ artifacts: Record<string, unknown>[] }>(`/projects/${projectId}/artifacts`)
}

export function downloadArtifactZip(projectId: string, stage: string) {
  window.open(`${BASE}/projects/${projectId}/artifacts/zip?stage=${stage}`, '_blank')
}
