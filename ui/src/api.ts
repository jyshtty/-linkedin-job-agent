// Thin client for api/server.py

export interface Job {
  serial: number
  company: string
  title: string
  location: string
  posted: string
  role: string
  status: string
  company_url: string
  company_job_id: string
  linkedin_url: string
  resume: string | null // tailored resume file name, null = default resume
  referrals: string[] // names of people messaged about this job
}

export interface BatchHistoryEntry {
  started: string
  finished?: string
  from_serial: number | null
  to_serial: number | null
  processed?: number
  counts?: Record<string, number>
  jobs_checked?: number
  sent?: number
  dry_run?: boolean
  stopped: boolean
  error?: string
}

export interface BatchInfo {
  stopped_at_serial: number | null
  pending: number
  running_stop_requested: boolean
  history: BatchHistoryEntry[]
}

export type BatchKind = 'tailor' | 'referral'
export type BatchStatus = Record<BatchKind, BatchInfo>

export interface Task {
  id: number
  kind: string
  label: string
  status: 'running' | 'done' | 'failed' | 'stopped'
  started: string
  ended: string | null
  lines: number
}

export interface TaskLog extends Task {
  since: number
  log: string[]
}

export interface Meta {
  companies: string[]
  roles: string[]
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      // not JSON
    }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

export const api = {
  meta: () => request<Meta>('/meta'),
  jobs: () => request<Job[]>('/jobs'),
  batch: () => request<BatchStatus>('/batch'),
  tasks: () => request<Task[]>('/tasks'),
  taskLog: (id: number, since: number) => request<TaskLog>(`/tasks/${id}?since=${since}`),
  stopTask: (id: number, force = false) => request<Task>(`/tasks/${id}/stop?force=${force}`, {}),

  search: (roles: string[], companies: string[]) => request<Task>('/search', { roles, companies }),
  flow: (roles: string[], companies: string[], size: number, messages: number) =>
    request<Task>('/flow', { roles, companies, size, messages }),
  tailor: (serial: number) => request<Task>('/tailor', { serial }),
  referral: (serial: number, dry_run: boolean) => request<Task>('/referral', { serial, dry_run }),

  startTailorBatch: (size: number) => request<Task>('/batch/tailor/start', { size }),
  startReferralBatch: (messages: number, max_jobs: number, dry_run: boolean, skip_company_contacts: boolean) =>
    request<Task>('/batch/referral/start', { messages, max_jobs, dry_run, skip_company_contacts }),
  resetBatch: (kind: BatchKind, serial: number | null) => request<BatchInfo>(`/batch/${kind}/reset`, { serial }),
}
