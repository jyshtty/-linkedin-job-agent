# Release Notes

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
