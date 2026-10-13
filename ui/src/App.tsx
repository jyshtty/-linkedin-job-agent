import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type AutoTailor, type BatchKind, type BatchStatus, type Job, type Meta, type Task } from './api'
import { BatchPanel } from './components/BatchPanel'
import { JobTable } from './components/JobTable'
import { ReferralPanel, TailorPanel } from './components/JobActions'
import { SearchPanel } from './components/SearchPanel'
import { TaskPanel } from './components/TaskPanel'

// Must match LANES in api/server.py: Chrome tasks never overlap; tailoring has its own lane.
const CHROME_KINDS = ['search', 'referral', 'batch_referral', 'flow']
const TAILOR_KINDS = ['tailor', 'batch_tailor', 'auto_tailor', 'flow']

export default function App() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [jobs, setJobs] = useState<Job[]>([])
  const [batch, setBatch] = useState<BatchStatus | null>(null)
  const [tasks, setTasks] = useState<Task[]>([])
  const [auto, setAuto] = useState<AutoTailor | null>(null)
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
        const [list, a] = await Promise.all([api.tasks(), api.autoTailor()])
        setTasks(list)
        setAuto(a)
        const nowRunning = new Set(list.filter((t) => t.status === 'running').map((t) => t.id))
        const finishedIds = [...runningIds.current].filter((id) => !nowRunning.has(id))
        const finished = finishedIds.length > 0
        runningIds.current = nowRunning
        // Surface failures: show the reason at the top and open that task's log
        for (const t of list.filter((t) => finishedIds.includes(t.id) && t.status === 'failed')) {
          const res = await api.taskLog(t.id, 0)
          const reason = [...res.log].reverse().find((l) => l.includes('❌') || /Error|Exception/.test(l))
          setError(`"${t.label}" failed${reason ? `: ${reason.replace('❌', '').trim()}` : ''} — see Activity below.`)
          setActiveTask(t.id)
        }
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
  const runningBatch = (kind: BatchKind) =>
    running.find((t) => t.kind === `batch_${kind}` || t.kind === 'flow' || (kind === 'tailor' && t.kind === 'auto_tailor'))
  const selectedJob = jobs.find((j) => j.serial === selected)

  const launch = async (start: () => Promise<Task>) => {
    setError(null)
    try {
      const task = await start()
      runningIds.current.add(task.id) // so even an instant failure is reported
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

  const toggleAuto = async () => {
    try {
      setAuto(await api.setAutoTailor(!auto?.enabled))
    } catch (e) {
      setError((e as Error).message)
    }
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
        <div className={`auto-tailor ${auto?.enabled ? `on ${auto.state}` : ''}`}>
          <button
            role="switch"
            aria-checked={!!auto?.enabled}
            className="switch"
            disabled={!auto}
            onClick={toggleAuto}
            title="Keep tailoring resumes in the background for every searched job, resuming where it stopped"
          >
            <span className="knob" />
          </button>
          <div>
            <div className="auto-title">
              Auto tailor {auto?.enabled ? (auto.state === 'running' ? '· busy' : '· on') : '· off'}
            </div>
            <div className="hint">
              {auto?.enabled
                ? `${auto.detail || 'Starting…'} · done up to #${batch?.tailor.stopped_at_serial ?? '—'}`
                : `Next job after #${batch?.tailor.stopped_at_serial ?? '—'} · ${batch?.tailor.pending ?? 0} left`}
            </div>
          </div>
        </div>
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
