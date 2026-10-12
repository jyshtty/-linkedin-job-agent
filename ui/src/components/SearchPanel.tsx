import { useMemo, useState } from 'react'
import type { Meta } from '../api'

interface Props {
  meta: Meta | null
  busy: boolean
  onSearch: (roles: string[], companies: string[]) => void
  onStartFlow: (roles: string[], companies: string[]) => void
}

export function SearchPanel({ meta, busy, onSearch, onStartFlow }: Props) {
  const [allCompanies, setAllCompanies] = useState(true)
  const [companies, setCompanies] = useState<string[]>([])
  const [companyFilter, setCompanyFilter] = useState('')
  const [roles, setRoles] = useState<string[]>([])
  const [extraRoles, setExtraRoles] = useState<string[]>([])
  const [newRole, setNewRole] = useState('')

  const shownCompanies = useMemo(
    () => (meta?.companies ?? []).filter((c) => c.toLowerCase().includes(companyFilter.toLowerCase())),
    [meta, companyFilter],
  )
  const roleOptions = [...(meta?.roles ?? []), ...extraRoles]
  const chosenCompanies = allCompanies ? [] : companies
  const canRun = !busy && (allCompanies || companies.length > 0)

  const toggle = (list: string[], value: string) =>
    list.includes(value) ? list.filter((v) => v !== value) : [...list, value]

  const addRole = () => {
    const role = newRole.trim()
    if (role && !roleOptions.includes(role)) setExtraRoles([...extraRoles, role])
    if (role && !roles.includes(role)) setRoles([...roles, role])
    setNewRole('')
  }

  return (
    <section className="panel">
      <h2>Search Agent</h2>

      <label className="field-label">Companies</label>
      <label className="check">
        <input type="checkbox" checked={allCompanies} onChange={(e) => setAllCompanies(e.target.checked)} />
        All interested companies ({meta?.companies.length ?? 0})
      </label>
      {!allCompanies && (
        <div className="picker">
          <input
            className="input"
            placeholder="Filter companies…"
            value={companyFilter}
            onChange={(e) => setCompanyFilter(e.target.value)}
          />
          <div className="picker-list">
            {shownCompanies.map((c) => (
              <label key={c} className="check">
                <input type="checkbox" checked={companies.includes(c)} onChange={() => setCompanies(toggle(companies, c))} />
                {c}
              </label>
            ))}
          </div>
          <div className="hint">{companies.length} selected</div>
        </div>
      )}

      <label className="field-label">Job roles</label>
      <div className="picker-list short">
        {roleOptions.map((r) => (
          <label key={r} className="check">
            <input type="checkbox" checked={roles.includes(r)} onChange={() => setRoles(toggle(roles, r))} />
            {r}
          </label>
        ))}
      </div>
      <div className="row">
        <input
          className="input"
          placeholder="Add a role…"
          value={newRole}
          onChange={(e) => setNewRole(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && addRole()}
        />
        <button className="btn ghost" onClick={addRole} disabled={!newRole.trim()}>
          Add
        </button>
      </div>
      <div className="hint">{roles.length ? `${roles.length} selected` : 'None selected = all roles in job_role.txt'}</div>

      <div className="actions">
        <button className="btn primary" disabled={!canRun} onClick={() => onSearch(roles, chosenCompanies)}>
          Search
        </button>
        <button className="btn" disabled={!canRun} onClick={() => onStartFlow(roles, chosenCompanies)}>
          Start flow
        </button>
      </div>
      <div className="hint">Start flow = search → tailor batch → referral batch.</div>
    </section>
  )
}
