import { useState } from 'react'
import type { Job } from '../api'

function SelectedJob({ job }: { job: Job | undefined }) {
  if (!job) return <div className="selected-job empty-sel">Select a row in the job list.</div>
  return (
    <div className="selected-job">
      <div className="sel-title">
        #{job.serial} · {job.company}
      </div>
      <div>{job.title}</div>
      <div className="muted mono">Job ID {job.company_job_id}</div>
    </div>
  )
}

interface TailorProps {
  job: Job | undefined
  busy: boolean
  onTailor: (serial: number) => void
}

export function TailorPanel({ job, busy, onTailor }: TailorProps) {
  return (
    <section className="panel">
      <h2>Tailor Resume Agent</h2>
      <SelectedJob job={job} />
      {job && (
        <div className="hint">
          {job.resume ? `Tailored resume exists: ${job.resume}` : 'No tailored resume yet — the default is used.'}
        </div>
      )}
      <div className="actions">
        <button className="btn primary" disabled={!job || busy} onClick={() => job && onTailor(job.serial)}>
          Tailor resume
        </button>
      </div>
    </section>
  )
}

interface ReferralProps {
  job: Job | undefined
  busy: boolean
  onSend: (serial: number, dryRun: boolean) => void
}

export function ReferralPanel({ job, busy, onSend }: ReferralProps) {
  const [dryRun, setDryRun] = useState(false)
  return (
    <section className="panel">
      <h2>Send Referral Agent</h2>
      <SelectedJob job={job} />
      {job && (
        <div className="hint">
          {job.referrals.length ? `Already sent to: ${job.referrals.join(', ')}` : 'No referrals sent for this job yet.'}
          <br />
          Resume attached: {job.resume ? 'tailored' : 'default'}
        </div>
      )}
      <label className="check">
        <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
        Dry run (type the message but don't send)
      </label>
      <div className="actions">
        <button className="btn primary" disabled={!job || busy} onClick={() => job && onSend(job.serial, dryRun)}>
          {dryRun ? 'Dry-run referral' : 'Send referral'}
        </button>
      </div>
    </section>
  )
}
