import { useEffect, useRef, useState } from 'react'
import { api, type Task } from '../api'

interface Props {
  tasks: Task[]
  activeId: number | null
  onSelect: (id: number) => void
  onStop: (id: number, force: boolean) => void
}

export function TaskPanel({ tasks, activeId, onSelect, onStop }: Props) {
  const [lines, setLines] = useState<string[]>([])
  const logRef = useRef<HTMLPreElement>(null)
  const active = tasks.find((t) => t.id === activeId)

  // Stream the selected task's log by polling for new lines
  useEffect(() => {
    if (activeId === null) return
    let since = 0
    let cancelled = false
    setLines([])
    const poll = async () => {
      try {
        const res = await api.taskLog(activeId, since)
        if (cancelled) return
        if (res.log.length) {
          since += res.log.length
          setLines((prev) => [...prev, ...res.log])
        }
        if (res.status === 'running') setTimeout(poll, 1000)
      } catch {
        if (!cancelled) setTimeout(poll, 3000)
      }
    }
    poll()
    return () => {
      cancelled = true
    }
  }, [activeId])

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight })
  }, [lines])

  return (
    <section className="panel log-panel">
      <div className="table-head">
        <h2>Activity</h2>
        {active?.status === 'running' && (
          <>
            <button className="btn danger small" onClick={() => onStop(active.id, false)}>
              Stop
            </button>
            <button className="btn ghost small" onClick={() => onStop(active.id, true)} title="Kill immediately">
              Force stop
            </button>
          </>
        )}
      </div>
      <div className="tasks">
        {tasks.length === 0 && <div className="hint">Nothing has run yet.</div>}
        {tasks.map((t) => (
          <button key={t.id} className={`task ${t.id === activeId ? 'active' : ''}`} onClick={() => onSelect(t.id)}>
            <span className={`dot ${t.status}`} />
            {t.label}
            <span className="muted"> · {t.started}</span>
          </button>
        ))}
      </div>
      <pre className="log" ref={logRef}>
        {active ? lines.join('\n') || 'Starting…' : 'Select an activity to see its log.'}
      </pre>
    </section>
  )
}
