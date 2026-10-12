"""
Local API for the job-agent UI.

    .venv/bin/python -m uvicorn api.server:app --port 8000     (from the repo root)

Every action (search, tailor, referral, batches, flow) runs `batch.py` as a
background process; the UI polls its log. Actions that drive Chrome share one
lane and tailoring has its own, so a tailor batch can run alongside a referral
batch but two Chrome jobs never overlap.
"""
import itertools
import os
import subprocess
import sys
import threading
import time
from typing import List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import batch  # noqa: E402
import company_directory  # noqa: E402
from apply_link_resolver import numeric_job_id  # noqa: E402
from referral_complete import LOG_FILE, find_resume  # noqa: E402

UI_DIST = os.path.join(ROOT, 'ui', 'dist')

# Which lanes each task occupies, and which batch stop-flag stops it gracefully
LANES = {
    'search': {'chrome'}, 'referral': {'chrome'}, 'batch_referral': {'chrome'},
    'tailor': {'tailor'}, 'batch_tailor': {'tailor'}, 'flow': {'chrome', 'tailor'},
}
GRACEFUL_STOP = {'tailor': ['tailor'], 'batch_tailor': ['tailor'], 'referral': ['referral'],
                 'batch_referral': ['referral'], 'flow': ['tailor', 'referral']}

app = FastAPI(title='LinkedIn Job Agent')


class Task:
    _ids = itertools.count(1)

    def __init__(self, kind, label, args):
        self.id = next(self._ids)
        self.kind, self.label, self.args = kind, label, args
        self.lines: List[str] = []
        self.status = 'running'
        self.stop_requested = False
        self.started = time.strftime('%H:%M:%S')
        self.ended = None
        self.proc = subprocess.Popen([sys.executable, '-u', 'batch.py', *args], cwd=ROOT,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        for line in self.proc.stdout:
            if 'NotOpenSSLWarning' in line or 'warnings.warn(' in line:
                continue
            self.lines.append(line.rstrip('\n'))
        code = self.proc.wait()
        if self.status == 'running':
            self.status = 'stopped' if self.stop_requested else ('done' if code == 0 else 'failed')
        self.ended = time.strftime('%H:%M:%S')

    @property
    def running(self):
        return self.proc.poll() is None

    def summary(self):
        return {'id': self.id, 'kind': self.kind, 'label': self.label, 'status': self.status,
                'started': self.started, 'ended': self.ended, 'lines': len(self.lines)}


TASKS: List[Task] = []
LOCK = threading.Lock()


def start_task(kind, label, args):
    with LOCK:
        busy = [t for t in TASKS if t.running and LANES[t.kind] & LANES[kind]]
        if busy:
            raise HTTPException(409, f"'{busy[0].label}' is still running. Wait for it or stop it first.")
        for flag in GRACEFUL_STOP.get(kind, []):
            batch.clear_stop(flag)
        task = Task(kind, label, args)
        TASKS.append(task)
        del TASKS[:-30]
        return task.summary()

# ---------------------------------------------------------------- data


def _read_job_roles():
    path = os.path.join('interested_job_role', 'job_role.txt')
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


@app.get('/api/meta')
def meta():
    return {'companies': company_directory.load_interested(), 'roles': _read_job_roles()}


@app.get('/api/jobs')
def jobs():
    df = batch.load_jobs()
    if df.empty:
        return []
    sent = {}
    if os.path.exists(LOG_FILE):
        log = pd.read_csv(LOG_FILE, dtype=str).fillna('')
        if 'linkedin_job_id' not in log.columns:
            log['linkedin_job_id'] = ''
        log = log[log['sent'] == 'Yes']
        for key, group in log.groupby('linkedin_job_id'):
            if key:
                sent[key] = list(group['employee_name'])
    out = []
    for job in df.to_dict('records'):
        resume_path, tailored = find_resume(job)
        out.append({
            'serial': job['_serial'],
            'company': job['company'],
            'title': job['job_title'],
            'location': job['location'],
            'posted': job['posted_date'],
            'role': job['search_role'],
            'status': job.get('apply_status', ''),
            'company_url': job['company_career_url'],
            'company_job_id': job['company_job_id'],
            'linkedin_url': job['linkedin_link'],
            'resume': os.path.basename(resume_path) if tailored else None,
            'referrals': sent.get(numeric_job_id(job['linkedin_job_id']), []),
        })
    return out


@app.get('/api/batch')
def batch_status():
    return batch.status()


class ResetBody(BaseModel):
    serial: Optional[int] = None


@app.post('/api/batch/{kind}/reset')
def batch_reset(kind: str, body: ResetBody):
    if kind not in batch.KINDS:
        raise HTTPException(404)
    if any(t.running and LANES[t.kind] & LANES[f'batch_{kind}'] for t in TASKS):
        raise HTTPException(409, 'Stop the running batch first.')
    batch.reset(kind, body.serial)
    return batch.status()[kind]

# ---------------------------------------------------------------- actions


class SearchBody(BaseModel):
    roles: List[str] = []
    companies: List[str] = []  # empty = all interested companies


class FlowBody(SearchBody):
    size: int = 10
    messages: int = 10
    dry_run: bool = False


class JobBody(BaseModel):
    serial: int
    dry_run: bool = False


class TailorBatchBody(BaseModel):
    size: int = 10


class ReferralBatchBody(BaseModel):
    messages: int = 10
    max_jobs: int = 25
    dry_run: bool = False
    skip_company_contacts: bool = True


def _search_args(body: SearchBody):
    args = []
    for r in body.roles:
        args += ['--role', r]
    for c in body.companies:
        args += ['--company', c]
    return args


@app.post('/api/search')
def search(body: SearchBody):
    label = f"Search {', '.join(body.roles) or 'all roles'}"
    return start_task('search', label, ['search', *_search_args(body)])


@app.post('/api/flow')
def flow(body: FlowBody):
    args = ['flow', *_search_args(body), '--size', str(body.size), '--messages', str(body.messages)]
    if body.dry_run:
        args.append('--dry-run')
    return start_task('flow', 'Start flow', args)


@app.post('/api/tailor')
def tailor(body: JobBody):
    return start_task('tailor', f'Tailor resume #{body.serial}', ['tailor-job', str(body.serial)])


@app.post('/api/referral')
def referral(body: JobBody):
    args = ['referral-job', str(body.serial)] + (['--dry-run'] if body.dry_run else [])
    return start_task('referral', f"Referral #{body.serial}{' (dry run)' if body.dry_run else ''}", args)


@app.post('/api/batch/tailor/start')
def start_tailor_batch(body: TailorBatchBody):
    return start_task('batch_tailor', f'Tailor batch ({body.size} jobs)', ['tailor', '--size', str(body.size)])


@app.post('/api/batch/referral/start')
def start_referral_batch(body: ReferralBatchBody):
    args = ['referral', '--messages', str(body.messages), '--max-jobs', str(body.max_jobs)]
    if body.dry_run:
        args.append('--dry-run')
    if not body.skip_company_contacts:
        args.append('--allow-company-repeats')
    label = f"Referral batch ({body.messages} messages{', dry run' if body.dry_run else ''})"
    return start_task('batch_referral', label, args)

# ---------------------------------------------------------------- tasks


def _task(task_id):
    task = next((t for t in TASKS if t.id == task_id), None)
    if task is None:
        raise HTTPException(404, 'Unknown task')
    return task


@app.get('/api/tasks')
def tasks():
    return [t.summary() for t in reversed(TASKS)]


@app.get('/api/tasks/{task_id}')
def task_log(task_id: int, since: int = 0):
    task = _task(task_id)
    return {**task.summary(), 'since': since, 'log': task.lines[since:]}


@app.post('/api/tasks/{task_id}/stop')
def stop_task(task_id: int, force: bool = False):
    """Graceful stop finishes the current person/job first; force kills the process."""
    task = _task(task_id)
    if not task.running:
        return task.summary()
    flags = GRACEFUL_STOP.get(task.kind)
    if flags and not force:
        for flag in flags:
            batch.request_stop(flag)
        task.stop_requested = True
        task.lines.append('⏹️  Stop requested — finishing the current step...')
    else:
        task.status = 'stopped'
        task.proc.terminate()
    return task.summary()

# ---------------------------------------------------------------- UI


if os.path.isdir(UI_DIST):
    app.mount('/assets', StaticFiles(directory=os.path.join(UI_DIST, 'assets')), name='assets')

    @app.get('/{path:path}')
    def ui(path: str):
        return FileResponse(os.path.join(UI_DIST, 'index.html'))
