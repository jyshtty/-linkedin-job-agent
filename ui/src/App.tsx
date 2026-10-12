import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type BatchKind, type BatchStatus, type Job, type Meta, type Task } from './api'
import { BatchPanel } from './components/BatchPanel'
import { JobTable } from './components/JobTable'
import { ReferralPanel, TailorPanel } from './components/JobActions'
import { SearchPanel } from './components/SearchPanel'
import { TaskPanel } from './components/TaskPanel'

// Must match LANES in api/server.py: Chrome tasks never overlap; tailoring has its own lane.
const CHROME_KINDS = ['search', 'referral', 'batch_referral', 'flow']
const TAILOR_KINDS = ['tailor', 'batch_tailor', 'flow']

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [batch, setBatch] = useState<BatchStatus | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [activeTask, setActiveTask] = useState<number | null>(null)
  const [selected, setSelected] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const runningIds = useRef<Set<number>>(new Set())

  const refreshData = useCallback(async () => {
    try {
      const [j, b] = await Promise.all([api.jobs(), api.batch()])
      setJobs(j)
      setBatch(b)
    } catch (e) {
      setError(`Can't reach the API: ${(e as Error).message}`)
    }
  }, [])

  useEffect(() => {
    api.meta().then(setMeta).catch((e) => setError(`Can't reach the API: ${e.message}`))
    refreshData()
  }, [refreshData])

  // Poll tasks; reload jobs + batch state whenever a task finishes (and periodically while busy)
  useEffect(() => {
    let tick = 0
    const timer = setInterval(async () => {
      try {
        const list = await api.tasks()
        setTasks(list)
        const nowRunning = new Set(list.filter((t) => t.status === 'running').map((t) => t.id))
        const finished = [...runningIds.current].some((id) => !nowRunning.has(id))
        runningIds.current = nowRunning
        tick++
        if (finished || (nowRunning.size > 0 && tick % 5 === 0)) refreshData()
      } catch {
        // API restarting; keep polling
      }
    }, 1500)
    return () => clearInterval(timer)
  }, [refreshData])

  const running = tasks.filter((t) => t.status === 'running')
  const chromeBusy = running.some((t) => CHROME_KINDS.includes(t.kind))
  const tailorBusy = running.some((t) => TAILOR_KINDS.includes(t.kind))
  const runningBatch = (kind: BatchKind) => running.find((t) => t.kind === `batch_${kind}` || t.kind === 'flow')
  const selectedJob = jobs.find((j) => j.serial === selected)

  const launch = async (start: () => Promise<Task>) => {
    setError(null)
    try {
      const task = await start()
      setTasks((prev) => [task, ...prev])
      setActiveTask(task.id)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const stop = async (id: number, force: boolean) => {
    try {
      await api.stopTask(id, force)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const startFlow = (roles: string[], companies: string[]) => {
    const ok = window.confirm(
      'Start flow will:\n\n1. Search jobs\n2. Tailor resumes for the next 10 jobs\n3. Send up to 10 referral messages\n\nContinue?',
    )
    if (ok) launch(() => api.flow(roles, companies, 10, 10))
  }

  const resetBatch = async (kind: BatchKind, serial: number | null) => {
    try {
      await api.resetBatch(kind, serial)
      refreshData()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <div className="app">
      <header>
        <h1>Job Agent</h1>
        <span className="hint">
          {jobs.length} jobs · {jobs.filter((j) => j.resume).length} tailored ·{' '}
          {jobs.reduce((n, j) => n + j.referrals.length, 0)} referrals sent
        </span>
      </header>

      {error && (
        <div className="error" onClick={() => setError(null)}>
          {error} <span className="muted">(click to dismiss)</span>
        </div>
      )}

      <div className="agents">
        <SearchPanel
          meta={meta}
          busy={chromeBusy}
          onSearch={(roles, companies) => launch(() => api.search(roles, companies))}
          onStartFlow={startFlow}
        />
        <TailorPanel job={selectedJob} busy={tailorBusy} onTailor={(s) => launch(() => api.tailor(s))} />
        <ReferralPanel job={selectedJob} busy={chromeBusy} onSend={(s, dry) => launch(() => api.referral(s, dry))} />
      </div>

      <JobTable
        jobs={jobs}
        selected={selected}
        onSelect={setSelected}
        tailorStop={batch?.tailor.stopped_at_serial ?? null}
        referralStop={batch?.referral.stopped_at_serial ?? null}
      />

      <BatchPanel
        kind="tailor"
        info={batch?.tailor}
        busy={tailorBusy}
        running={!!runningBatch('tailor')}
        onStart={({ size }) => launch(() => api.startTailorBatch(size))}
        onStop={() => {
          const t = runningBatch('tailor')
          if (t) stop(t.id, false)
        }}
        onReset={(serial) => resetBatch('tailor', serial)}
      />
      <BatchPanel
        kind="referral"
        info={batch?.referral}
        busy={chromeBusy}
        running={!!runningBatch('referral')}
        onStart={({ size, maxJobs, dryRun, skipCompanyContacts }) =>
          launch(() => api.startReferralBatch(size, maxJobs, dryRun, skipCompanyContacts))
        }
        onStop={() => {
          const t = runningBatch('referral')
          if (t) stop(t.id, false)
        }}
        onReset={(serial) => resetBatch('referral', serial)}
      />

      <TaskPanel tasks={tasks} activeId={activeTask} onSelect={setActiveTask} onStop={stop} />
    </div>
  )
}
