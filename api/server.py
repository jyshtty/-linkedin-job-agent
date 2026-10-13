"""
Local API for the job-agent UI.

    .venv/bin/python -m uvicorn api.server:app --port 8000     (from the repo root)

Every action (search, tailor, referral, batches, flow) runs `batch.py` as a
background process; the UI polls its log. Actions that drive Chrome share one
lane and tailoring has its own, so a tailor batch can run alongside a referral
batch but two Chrome jobs never overlap.

Auto tailor: while its toggle is on (survives restarts), a watcher thread keeps starting
tailor batches from the saved checkpoint whenever the tailor lane is free and the AI
service is reachable, so tailoring resumes on its own after a restart or an outage.
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
    'tailor': {'tailor'}, 'batch_tailor': {'tailor'}, 'auto_tailor': {'tailor'}, 'flow': {'chrome', 'tailor'},
}
GRACEFUL_STOP = {'tailor': ['tailor'], 'batch_tailor': ['tailor'], 'auto_tailor': ['tailor'], 'referral': ['referral'],
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

# ---------------------------------------------------------------- auto tailor


AUTO_BATCH_SIZE = 5      # jobs per auto batch; small so the tailor lane frees up often
AUTO_POLL_SECS = 5
AUTO_RETRY_SECS = 120    # wait after the AI service is down or a batch failed
AUTO_MAX_FAILS = 3       # skip a job that keeps failing while the service is up
AUTO = {'state': 'off', 'detail': '', 'task_id': None}


def _auto_set(state, detail=''):
    AUTO.update(state=state, detail=detail)


def _auto_after_batch(task, fails):
    """Back off after a failed auto batch; skip a job that fails repeatedly while the service is up."""
    history = batch.load_state()['tailor']['history']
    if task.status == 'done' and not (history and history[0].get('error')):
        return 0
    pending = batch.pending_jobs('tailor')
    if pending and batch.ai_service_up():
        serial = int(pending[0]['serial_number'])
        fails[serial] = fails.get(serial, 0) + 1
        if fails[serial] >= AUTO_MAX_FAILS:
            batch.reset('tailor', serial)
            task.lines.append(f'⏭️  Auto tailor: job #{serial} failed {AUTO_MAX_FAILS} times, skipping it.')
            fails.pop(serial)
            return 0
    return time.time() + AUTO_RETRY_SECS


def _auto_tailor_loop():
    """While the toggle is on, keep running tailor batches from the saved checkpoint."""
    retry_at, retry_why, fails = 0, '', {}
    while True:
        time.sleep(AUTO_POLL_SECS)
        try:
            ours = next((t for t in TASKS if t.id == AUTO['task_id']), None)
            if ours and not ours.running:
                AUTO['task_id'] = None
                if not ours.stop_requested:
                    retry_at, retry_why = _auto_after_batch(ours, fails), 'Last batch failed'
            if not batch.auto_tailor_enabled():
                _auto_set('off')
                continue
            if ours and ours.running:
                _auto_set('running', ours.label)
                continue
            other = next((t for t in TASKS if t.running and 'tailor' in LANES[t.kind]), None)
            if other:
                _auto_set('waiting', f"Waiting for '{other.label}' to finish")
                continue
            if time.time() < retry_at:
                _auto_set('waiting', f"{retry_why} — retrying at {time.strftime('%H:%M', time.localtime(retry_at))}")
                continue
            pending = batch.pending_jobs('tailor')
            if not pending:
                _auto_set('idle', 'All searched jobs are tailored — waiting for new jobs')
                continue
            if not batch.ai_service_up():
                retry_at, retry_why = time.time() + AUTO_RETRY_SECS, 'AI service unreachable'
                continue
            label = f"Auto tailor (from #{pending[0]['serial_number']}, {len(pending)} left)"
            AUTO['task_id'] = start_task('auto_tailor', label, ['tailor', '--size', str(AUTO_BATCH_SIZE)])['id']
            _auto_set('running', label)
        except HTTPException:
            pass  # lane got taken between the check and the start; try again next tick
        except Exception as e:
            _auto_set('waiting', f'Auto tailor error: {e}')


@app.on_event('startup')
def _start_auto_tailor():
    threading.Thread(target=_auto_tailor_loop, daemon=True).start()


class AutoTailorBody(BaseModel):
    enabled: bool


@app.get('/api/auto-tailor')
def auto_tailor_status():
    return {'enabled': batch.auto_tailor_enabled(), **AUTO}


@app.post('/api/auto-tailor')
def auto_tailor_toggle(body: AutoTailorBody):
    batch.set_auto_tailor(body.enabled)
    ours = next((t for t in TASKS if t.id == AUTO['task_id'] and t.running), None)
    if not body.enabled and ours:
        batch.request_stop('tailor')  # finish the current job, then stop
        ours.stop_requested = True
        ours.lines.append('⏹️  Auto tailor turned off — finishing the current job...')
    elif not body.enabled:
        _auto_set('off')
    return auto_tailor_status()

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
    if task.kind == 'auto_tailor':  # otherwise the watcher would just start the next batch
        batch.set_auto_tailor(False)
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
