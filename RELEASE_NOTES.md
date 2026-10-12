# Release Notes

## v0.2.0 — 2026-10-12

Adds a web UI and resumable batch runs. Tailoring and referrals can now be worked
through the job list a batch at a time, each batch picking up where the last one
stopped.

### Commands

```bash
./run_ui.sh          # open the UI at http://localhost:8000
./run_ui.sh dev      # hot reload while editing the UI (http://localhost:5173)

python batch.py tailor   [--size 10]
python batch.py referral [--messages 10] [--max-jobs 25] [--dry-run] [--allow-company-repeats]
python batch.py status | reset <tailor|referral> [--serial N] | stop <tailor|referral>
```

The existing `main.py` commands work as before.

### New

- **Web UI** (`ui/`, React + TypeScript), served by a local API (`api/server.py`, FastAPI)
  - **Search Agent:** search all interested companies or only the ones you tick;
    pick roles from `job_role.txt` or add new ones. **Start flow** runs a search,
    then a tailor batch, then a referral batch, after asking you to confirm.
  - **Tailor Resume Agent** and **Send Referral Agent:** act on the row selected
    in the job table. Referrals can be sent as a dry run.
  - **Job table:** filter by company, title, location or job ID. Each row shows
    whether the job has a tailored resume, who has been messaged about it, and
    where each batch stopped.
  - **Activity log:** live output of every run, with **Stop** (finishes the current
    person or job first) and **Force stop**.
  - Tasks that control Chrome never run at the same time. Tailoring doesn't use
    Chrome, so a tailor batch can run alongside a referral batch.
- **Batch runs** (`batch.py`)
  - **Tailor batch:** tailors resumes for the next N jobs (default 10), one after
    another with no waits. It skips jobs that already have a tailored resume.
  - **Referral batch:** sends up to 10 messages per batch, checking at most 25 jobs.
    If the message limit is reached partway through a job, the next batch finishes
    that job first.
  - Each batch shows **"Batch stopped at sl no ⇒ N"** and continues from there next
    time. The position is saved after every job in `batch_state.json`, by LinkedIn
    job ID, so it survives the job list being renumbered. You can restart from the
    top or continue after any serial number.
  - If a job fails (for example the AI service is down), the batch stops and retries
    that job next time instead of skipping it.
  - `batch.tailor_job(serial)` tailors a single job on its own, ready to be called
    from a queue worker (e.g. Kafka) later.

### Changed

- **Referrals**
  - People already messaged about a job now count toward `referrals_per_job`, so
    rerunning a job doesn't message extra people.
  - Option to skip people asked about **any job at the same company** in the last
    30 days. It's on by default for referral batches.
  - `referral_log.csv` now records each job's LinkedIn job ID, so the log no longer
    depends on serial numbers. Older logs are upgraded automatically.
- **Resume tailoring** uses the company link and job ID already saved in
  `searched_jobs.csv`, so it no longer needs Chrome. Batches skip the slow
  browser-based Overleaf fallback.
- **Job search** accepts a list of companies, not only "all" or one.
- **New dependencies:** `fastapi` and `uvicorn`. The UI also needs Node.js;
  `run_ui.sh` installs its packages the first time.

### Fixed

- These known limitations from v0.1.0 are resolved:
  - the same person being asked about several jobs at one company
  - the referral log being keyed by serial number

### Known limitations

- **Tailoring needs the AI service.** It uses the endpoint in `.env`
  (`ai-proxy.lab.epam.com`), which needs the EPAM VPN. Without it, tailoring stops
  at the match-analysis step, and tailoring from the UI hasn't yet produced a
  resume end to end.
- **Wrong people can be messaged.** The people search still matches the company by
  keyword, so it can pick someone who mentions the company but doesn't work there now.
- **Not tested end to end yet:** sending referrals from the UI, a full referral
  batch, and Start flow.

## v0.1.0 — 2026-10-12

First tagged release. Searches jobs at your interested companies, tailors your
resume, and asks your LinkedIn connections for referrals, using only jobs that
have a company careers page and a company job ID.

### Commands

```bash
python main.py search [--job_role "<role>"] [--company "<name>"]
python main.py tailor_resume <serial>
python main.py request_referral <serial> [--dry-run]

python apply_link_resolver.py [--force]   # re-check company links in searched_jobs.csv
python company_directory.py [--refresh]   # map interested companies to LinkedIn IDs
```

### New

- **Referral agent** (`referral_complete.py`, also `main.py request_referral`)
  - Works in your existing, logged-in Chrome through AppleScript. It never opens a
    new browser session, so it can't log you out.
  - Messages up to `referrals_per_job` 1st-degree connections at the job's company.
  - Greets each person by first name.
  - Attaches the tailored resume for the job if one exists in `tailored_resume/`,
    otherwise `original_resume/Ajay_resume.pdf`.
  - Confirms each message appears in the chat before closing it.
  - Skips anyone already asked about the same job, and skips paid InMail windows.
  - Records every attempt in `referral_log.csv`. `--dry-run` types the message and
    attaches the resume, then clears both without sending.
- **Company careers links** (`apply_link_resolver.py`)
  - Finds each job's company careers URL and company job ID. It has specific rules
    for Workday, Greenhouse, Lever, Ashby, SmartRecruiters, Phenom, SuccessFactors,
    Taleo, iCIMS, Keka, Infosys, Apple, EPAM and RippleHire.
  - If the link doesn't contain the ID, it falls back to the job description, then
    to the careers page itself.
  - A job is used only if both the link and the ID are found. Otherwise it is
    marked `EASY_APPLY`, `AGGREGATOR`, `NO_COMPANY_URL`, `NO_JOB_ID`,
    `NOT_INTERESTED` or `UNRESOLVED`.
- **Interested companies** (`company_directory.py`)
  - Reads every list in `interested_companies/` and maps each company to its
    LinkedIn company ID. The mapping is cached in `company_ids.json`, so lookups
    happen once.
- **Referral template**: now includes the company job link, the company job ID and
  a note that the resume is attached.

### Changed

- **Job search**
  - Searches only the interested companies, many companies per search.
  - Fetches up to 4 pages of results per search, not just the first 10 jobs.
  - Checks each job's hiring company against the list.
- **Resume tailoring**
  - Skips jobs that have no company careers link and job ID.
  - Names tailored resumes `<Company>_<serial>_<company job ID>.pdf`.

### Fixed

- **Search returned only Easy Apply jobs.** The `f_AL=true` filter selected Easy
  Apply jobs, the opposite of what was intended. It has been removed.
- **Past-week filter did nothing.** It now really limits results to the last 7 days.
- **Long internal codes saved as job IDs.** Some careers sites (e.g. Snowflake) put
  an internal code in the link. These are now rejected, and the real requisition
  number is used instead (e.g. `REQ20652`).
- **Messages not typed or sent.** LinkedIn now draws the chat window inside a
  shadow DOM. Typing, sending and closing now work there.

### Removed

- Selenium-based `referral_agent.py`. It opened a separate browser and did not
  attach resumes. `main.py request_referral` now uses `referral_complete.py`.
- `linkedin_agent.py`, the unused standalone PDF compilers, outdated status
  reports, and the unused `linkedin-api` and `reportlab` dependencies.

### Setup

- **macOS with Google Chrome**, logged in to LinkedIn.
- **Allow scripted JavaScript in Chrome:** View → Developer → Allow JavaScript from
  Apple Events.
- **Optional:** Accessibility permission for your terminal. It's only used if typing
  falls back to pasting.

### Known limitations

- **Wrong people can be messaged.** The people search matches the company by
  keyword, so it can pick someone who mentions the company but doesn't work there
  now. Planned fix: LinkedIn's current-company filter, using the IDs already saved.
- **The same person can be asked several times.** Duplicates are only avoided per
  job, so someone at a company with several jobs may get one message per job.
- **The log is keyed by serial number.** `referral_log.csv` tracks jobs by serial
  number, which changes when the job list is rebuilt from scratch.
- **Some company IDs need checking.** Moj and Da Vinci Derivatives have no usable
  LinkedIn page. Samsung Research maps to Samsung Research America.
