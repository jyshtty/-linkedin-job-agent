# Job Agent UI

React + TypeScript (Vite) front end for the job agent. It talks to the local
FastAPI server in `../api/server.py`, which runs every action through `../batch.py`.

From the repo root:

```bash
./run_ui.sh        # build (if needed) and serve everything at http://localhost:8000
./run_ui.sh dev    # hot reload: API on :8000, Vite dev server on :5173 (proxies /api)
```

- `src/api.ts` — typed client for the API
- `src/App.tsx` — page layout, polling, task launching
- `src/components/` — Search / Tailor / Referral panels, job table, batch panels, activity log
