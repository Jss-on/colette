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

// --- Operator Intervention ---

export function pausePipeline(projectId: string, reason?: string) {
  return apiFetch<Record<string, unknown>>(`/projects/${projectId}/pause`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: reason ?? '' }),
  })
}

export function resumePipeline(projectId: string) {
  return apiFetch<Record<string, unknown>>(`/projects/${projectId}/resume`, {
    method: 'POST',
  })
}

export function injectFeedback(projectId: string, message: string, targetStage?: string, targetAgent?: string) {
  return apiFetch<Record<string, unknown>>(`/projects/${projectId}/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, target_stage: targetStage, target_agent: targetAgent }),
  })
}

export function sendAgentMessage(projectId: string, agentId: string, message: string) {
  return apiFetch<Record<string, unknown>>(`/projects/${projectId}/agents/${agentId}/message`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message }),
  })
}

export function restartStage(projectId: string, stageName: string, reason?: string) {
  return apiFetch<Record<string, unknown>>(`/projects/${projectId}/stages/${stageName}/restart`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: reason ?? '' }),
  })
}

export function skipStage(projectId: string, stageName: string, reason?: string, syntheticHandoff?: Record<string, unknown>) {
  return apiFetch<Record<string, unknown>>(`/projects/${projectId}/stages/${stageName}/skip`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: reason ?? '', synthetic_handoff: syntheticHandoff ?? {} }),
  })
}

export function editHandoff(projectId: string, stageName: string, patch: Record<string, unknown>, mode: 'merge' | 'replace' = 'merge') {
  return apiFetch<Record<string, unknown>>(`/projects/${projectId}/handoffs/${stageName}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ patch, mode }),
  })
}
