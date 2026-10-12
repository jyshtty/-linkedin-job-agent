import { useState } from 'react'
import type { BatchHistoryEntry, BatchInfo, BatchKind } from '../api'

interface Props {
  kind: BatchKind
  info: BatchInfo | undefined
  busy: boolean
  running: boolean
  onStart: (opts: { size: number; maxJobs: number; dryRun: boolean; skipCompanyContacts: boolean }) => void
  onStop: () => void
  onReset: (serial: number | null) => void
}

function describe(kind: BatchKind, h: BatchHistoryEntry) {
  const range = h.from_serial ? `#${h.from_serial}–#${h.to_serial}` : 'no jobs'
  const detail =
    kind === 'tailor'
      ? Object.entries(h.counts ?? {})
          .map(([k, v]) => `${v} ${k.replace('_', ' ')}`)
          .join(', ') || 'nothing processed'
      : `${h.sent ?? 0} ${h.dry_run ? 'typed (dry run)' : 'sent'} · ${h.jobs_checked ?? 0} jobs checked`
  const flag = h.error ? ' · error' : h.stopped ? ' · stopped' : ''
  return `${h.started.slice(5, 16)} · ${range} · ${detail}${flag}`
}

export function BatchPanel({ kind, info, busy, running, onStart, onStop, onReset }: Props) {
  const [size, setSize] = useState(10)
  const [maxJobs, setMaxJobs] = useState(25)
  const [dryRun, setDryRun] = useState(false)
  const [skipCompanyContacts, setSkipCompanyContacts] = useState(true)
  const [resetTo, setResetTo] = useState('')
  const isTailor = kind === 'tailor'
  const stoppedAt = info?.stopped_at_serial

  return (
    <section className="panel batch">
      <h2>{isTailor ? 'Batch run for tailor resume' : 'Batch run for referral job list'}</h2>
      <div className="batch-body">
        <div className="batch-status">
          <div className="big">
            Batch stopped at sl no <span>⇒ {stoppedAt ?? '— (not started)'}</span>
          </div>
          <div className="hint">{info?.pending ?? 0} jobs left after this point</div>
          <div className="row">
            <input
              className="input small"
              placeholder="sl no"
              value={resetTo}
              onChange={(e) => setResetTo(e.target.value.replace(/\D/g, ''))}
            />
            <button className="btn ghost" disabled={running} onClick={() => onReset(resetTo ? Number(resetTo) : null)}>
              {resetTo ? `Continue after #${resetTo}` : 'Restart from top'}
            </button>
          </div>
        </div>

        <div className="batch-controls">
          <label className="inline">
            {isTailor ? 'Jobs per batch' : 'Messages per batch'}
            <input className="input small" type="number" min={1} value={size} onChange={(e) => setSize(Number(e.target.value))} />
          </label>
          {!isTailor && (
            <>
              <label className="inline">
                Max jobs to check
                <input className="input small" type="number" min={1} value={maxJobs} onChange={(e) => setMaxJobs(Number(e.target.value))} />
              </label>
              <label className="check">
                <input type="checkbox" checked={skipCompanyContacts} onChange={(e) => setSkipCompanyContacts(e.target.checked)} />
                Skip people already asked at the same company (30 days)
              </label>
              <label className="check">
                <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
                Dry run
              </label>
            </>
          )}
          <div className="actions">
            {running ? (
              <button className="btn danger" onClick={onStop}>
                Stop batch
              </button>
            ) : (
              <button
                className="btn primary"
                disabled={busy || size < 1}
                onClick={() => onStart({ size, maxJobs, dryRun, skipCompanyContacts })}
              >
                Start batch
              </button>
            )}
          </div>
        </div>
      </div>
      {info && info.history.length > 0 && (
        <details className="history">
          <summary>Previous batches ({info.history.length})</summary>
          <ul>
            {info.history.map((h, i) => (
              <li key={i}>{describe(kind, h)}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}
