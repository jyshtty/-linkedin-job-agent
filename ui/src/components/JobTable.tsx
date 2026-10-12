import { useMemo, useState } from 'react'
import type { Job } from '../api'

interface Props {
  jobs: Job[]
  selected: number | null
  onSelect: (serial: number) => void
  tailorStop: number | null
  referralStop: number | null
}

export function JobTable({ jobs, selected, onSelect, tailorStop, referralStop }: Props) {
  const [filter, setFilter] = useState('')
  const [onlyPending, setOnlyPending] = useState(false)

  const shown = useMemo(() => {
    const q = filter.toLowerCase()
    return jobs.filter(
      (j) =>
        (!q || `${j.serial} ${j.company} ${j.title} ${j.location} ${j.company_job_id}`.toLowerCase().includes(q)) &&
        (!onlyPending || j.referrals.length === 0),
    )
  }, [jobs, filter, onlyPending])

  return (
    <section className="panel table-panel">
      <div className="table-head">
        <h2>Searched jobs</h2>
        <span className="hint">
          {shown.length} of {jobs.length}
        </span>
        <input
          className="input grow"
          placeholder="Filter by company, title, location, job ID…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <label className="check">
          <input type="checkbox" checked={onlyPending} onChange={(e) => setOnlyPending(e.target.checked)} />
          No referrals yet
        </label>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Company</th>
              <th>Job title</th>
              <th>Location</th>
              <th>Company job ID</th>
              <th>Resume</th>
              <th>Referrals</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((j) => (
              <tr
                key={j.serial}
                className={j.serial === selected ? 'selected' : undefined}
                onClick={() => onSelect(j.serial)}
              >
                <td className="num">
                  {j.serial}
                  {j.serial === tailorStop && <span className="marker" title="Tailor batch stopped here">T</span>}
                  {j.serial === referralStop && <span className="marker alt" title="Referral batch stopped here">R</span>}
                </td>
                <td>{j.company}</td>
                <td>
                  <a href={j.company_url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>
                    {j.title}
                  </a>
                </td>
                <td className="muted">{j.location}</td>
                <td className="mono">{j.company_job_id}</td>
                <td>{j.resume ? <span className="pill ok" title={j.resume}>Tailored</span> : <span className="pill">Default</span>}</td>
                <td title={j.referrals.join(', ')}>
                  {j.referrals.length ? <span className="pill ok">{j.referrals.length} sent</span> : <span className="muted">—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {jobs.length === 0 && <div className="empty">No jobs yet. Run a search.</div>}
      </div>
    </section>
  )
}
