"""
Batch runs over searched_jobs.csv that pick up where the previous batch stopped.

    python batch.py tailor   [--size 10]                    # tailor resumes for the next N jobs, no waits
    python batch.py referral [--messages 10] [--max-jobs 25] [--dry-run] [--allow-company-repeats]
    python batch.py status                                   # where each batch stopped
    python batch.py reset tailor|referral [--serial N]       # restart from the top, or after job #N
    python batch.py stop tailor|referral                     # finish the current item, then stop

Single jobs and searches (used by the UI so they can be stopped the same way):
    python batch.py tailor-job <serial>
    python batch.py referral-job <serial> [--dry-run]
    python batch.py search [--role R ...] [--company C ...]
    python batch.py flow [--role R ...] [--company C ...] [--size 10] [--messages 10]

Progress is saved after every job in batch_state.json. Each job is remembered by its
LinkedIn job ID, so a rebuilt job list (new serial numbers) doesn't resume at the wrong job.
"""
import argparse
import json
import os
import random
import sys
import time
from datetime import datetime

import pandas as pd

from apply_link_resolver import JOBS_FILE, numeric_job_id

STATE_FILE = 'batch_state.json'
KINDS = ('tailor', 'referral')
HISTORY_LIMIT = 50


def _now():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def stop_file(kind):
    return f'.stop_{kind}'


def stop_requested(kind):
    return os.path.exists(stop_file(kind))


def request_stop(kind):
    open(stop_file(kind), 'w').close()


def clear_stop(kind):
    if os.path.exists(stop_file(kind)):
        os.remove(stop_file(kind))

# ---------------------------------------------------------------- state


def load_state():
    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            state = json.load(f)
    for kind in KINDS:
        state.setdefault(kind, {'last_job_id': '', 'last_serial': None, 'history': []})
    return state


# Auto-tailor toggle lives in its own flag file (not batch_state.json) so it can't race
# with a running batch writing its checkpoint.
AUTO_TAILOR_FILE = '.auto_tailor_on'


def auto_tailor_enabled():
    return os.path.exists(AUTO_TAILOR_FILE)


def set_auto_tailor(enabled):
    if enabled:
        open(AUTO_TAILOR_FILE, 'w').close()
    elif os.path.exists(AUTO_TAILOR_FILE):
        os.remove(AUTO_TAILOR_FILE)


def ai_service_up(timeout=5):
    """Cheap reachability check of the AI endpoint (no tokens spent): any non-5xx reply counts as up."""
    import requests
    from dotenv import load_dotenv
    load_dotenv()
    endpoint = os.getenv('AZURE_ENDPOINT')
    if not endpoint:
        return False
    try:
        return requests.get(endpoint, timeout=timeout).status_code < 500
    except requests.RequestException:
        return False


def save_state(state):
    tmp = STATE_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def _set_checkpoint(kind, job):
    state = load_state()
    state[kind]['last_job_id'] = numeric_job_id(job['linkedin_job_id'])
    state[kind]['last_serial'] = int(job['serial_number'])
    save_state(state)


def _add_history(kind, entry):
    state = load_state()
    state[kind]['history'] = ([entry] + state[kind]['history'])[:HISTORY_LIMIT]
    save_state(state)


def load_jobs():
    if not os.path.exists(JOBS_FILE):
        return pd.DataFrame()
    df = pd.read_csv(JOBS_FILE, dtype=str).fillna('')
    df['_serial'] = df['serial_number'].astype(int)
    return df.sort_values('_serial')


def pending_jobs(kind):
    """Usable jobs after the checkpoint, in serial order."""
    df = load_jobs()
    if df.empty:
        return []
    if 'apply_status' not in df.columns:
        return []
    df = df[df['apply_status'] == 'OK']
    cp = load_state()[kind]
    ids = [numeric_job_id(j) for j in df['linkedin_job_id']]
    if cp['last_job_id'] and cp['last_job_id'] in ids:
        df = df.iloc[ids.index(cp['last_job_id']) + 1:]
    elif cp['last_serial'] is not None:
        # Checkpoint job no longer in the list (list rebuilt): continue by serial number
        df = df[df['_serial'] > cp['last_serial']]
    return [row.to_dict() for _, row in df.iterrows()]


def status():
    state = load_state()
    out = {}
    for kind in KINDS:
        out[kind] = {
            'stopped_at_serial': state[kind]['last_serial'],
            'pending': len(pending_jobs(kind)),
            'running_stop_requested': stop_requested(kind),
            'history': state[kind]['history'][:10],
        }
    return out


def reset(kind, serial=None):
    state = load_state()
    if serial is None:
        state[kind].update(last_job_id='', last_serial=None)
    else:
        df = load_jobs()
        row = df[df['_serial'] == int(serial)]
        state[kind]['last_serial'] = int(serial)
        state[kind]['last_job_id'] = numeric_job_id(row.iloc[0]['linkedin_job_id']) if len(row) else ''
    save_state(state)

# ---------------------------------------------------------------- tailor


def tailor_job(serial, tailor=None, allow_overleaf=True):
    """
    Tailor the resume for one job. Self-contained so a queue consumer (e.g. Kafka)
    can call it per job later. Returns 'exists', 'tailored', 'not_needed', 'skipped',
    'tex_only' or 'error'.
    """
    from referral_complete import find_resume
    from resume_tailor import ResumeTailor

    job = next((j for j in load_jobs().to_dict('records') if j['_serial'] == int(serial)), None)
    if job is None:
        print(f"❌ No job #{serial}")
        return 'error'
    if find_resume(job)[1]:
        print(f"#{serial} {job['company']}: tailored resume already exists")
        return 'exists'
    tailor = tailor or ResumeTailor()
    tailor.tailor_resume(int(serial), allow_overleaf=allow_overleaf)
    return tailor.last_status


def run_tailor_batch(size=10):
    from resume_tailor import ResumeTailor

    clear_stop('tailor')
    jobs = pending_jobs('tailor')[:size]
    entry = {'started': _now(), 'from_serial': None, 'to_serial': None, 'processed': 0,
             'counts': {}, 'stopped': False}
    print(f"\n📦 TAILOR BATCH: {len(jobs)} jobs (size {size})\n")
    tailor = ResumeTailor()
    for job in jobs:
        if stop_requested('tailor'):
            entry['stopped'] = True
            print("⏹️  Stop requested.")
            break
        try:
            result = tailor_job(job['serial_number'], tailor=tailor, allow_overleaf=False)
        except Exception as e:  # e.g. AI service down: stop without skipping this job
            print(f"❌ #{job['serial_number']} failed: {e}. Stopping batch; it will retry this job next time.")
            entry['error'] = str(e)
            break
        _set_checkpoint('tailor', job)
        entry['from_serial'] = entry['from_serial'] or int(job['serial_number'])
        entry['to_serial'] = int(job['serial_number'])
        entry['processed'] += 1
        entry['counts'][result] = entry['counts'].get(result, 0) + 1
        print(f"   → #{job['serial_number']} {job['company']}: {result}\n")
    entry['finished'] = _now()
    _add_history('tailor', entry)
    clear_stop('tailor')
    print(f"\n✅ Tailor batch done: {entry['processed']} jobs {entry['counts']}. "
          f"Stopped at #{load_state()['tailor']['last_serial']}")
    return entry

# ---------------------------------------------------------------- referral


def referral_job(serial, dry_run=False):
    import referral_complete
    clear_stop('referral')
    result = referral_complete.run(int(serial), dry_run=dry_run, should_stop=lambda: stop_requested('referral'))
    clear_stop('referral')
    return result


def run_referral_batch(messages=10, max_jobs=25, dry_run=False, skip_company_contacts=True):
    import referral_complete

    clear_stop('referral')
    jobs = pending_jobs('referral')[:max_jobs]
    entry = {'started': _now(), 'from_serial': None, 'to_serial': None, 'jobs_checked': 0,
             'sent': 0, 'dry_run': dry_run, 'stopped': False}
    print(f"\n📦 REFERRAL BATCH: up to {messages} messages across up to {len(jobs)} jobs"
          f"{' (DRY RUN)' if dry_run else ''}\n")
    for job in jobs:
        remaining = messages - entry['sent']
        if remaining <= 0:
            break
        if stop_requested('referral'):
            entry['stopped'] = True
            print("⏹️  Stop requested.")
            break
        try:
            r = referral_complete.run(int(job['serial_number']), dry_run=dry_run, max_messages=remaining,
                                      skip_company_contacts=skip_company_contacts,
                                      should_stop=lambda: stop_requested('referral'), close_tab=True)
        except Exception as e:
            print(f"❌ #{job['serial_number']} failed: {e}. Stopping batch; it will retry this job next time.")
            entry['error'] = str(e)
            break
        entry['sent'] += r['sent']
        entry['jobs_checked'] += 1
        entry['from_serial'] = entry['from_serial'] or int(job['serial_number'])
        entry['to_serial'] = int(job['serial_number'])
        if r['status'] in ('capped', 'stopped'):
            # Job not finished (message cap hit / stopped mid-job): next batch resumes here
            entry['stopped'] = r['status'] == 'stopped'
            break
        if r['status'] == 'error':
            break
        _set_checkpoint('referral', job)
        time.sleep(random.uniform(3, 6))
    entry['finished'] = _now()
    _add_history('referral', entry)
    clear_stop('referral')
    print(f"\n✅ Referral batch done: {entry['sent']} messages {'typed (dry run)' if dry_run else 'sent'}, "
          f"{entry['jobs_checked']} jobs checked. Stopped at #{load_state()['referral']['last_serial']}")
    return entry

# ---------------------------------------------------------------- search / flow


def run_search(roles=None, companies=None):
    from linkedin_scraper import LinkedInJobScraper
    scraper = LinkedInJobScraper()
    for role in (roles or [None]):
        scraper.search_jobs(job_role=role, companies=companies or None)


def run_flow(roles=None, companies=None, size=10, messages=10, dry_run=False):
    print("▶️  FLOW: search → tailor batch → referral batch\n")
    run_search(roles, companies)
    if stop_requested('tailor') or stop_requested('referral'):
        return
    run_tailor_batch(size)
    if stop_requested('referral'):
        return
    run_referral_batch(messages=messages, dry_run=dry_run)


def main():
    p = argparse.ArgumentParser(description='Batch runs for tailoring and referrals')
    sub = p.add_subparsers(dest='cmd', required=True)
    t = sub.add_parser('tailor'); t.add_argument('--size', type=int, default=10)
    r = sub.add_parser('referral')
    r.add_argument('--messages', type=int, default=10)
    r.add_argument('--max-jobs', type=int, default=25)
    r.add_argument('--dry-run', action='store_true')
    r.add_argument('--allow-company-repeats', action='store_true',
                   help='also message people already asked about this company in the last 30 days')
    sub.add_parser('status')
    rs = sub.add_parser('reset'); rs.add_argument('kind', choices=KINDS); rs.add_argument('--serial', type=int)
    st = sub.add_parser('stop'); st.add_argument('kind', choices=KINDS)
    tj = sub.add_parser('tailor-job'); tj.add_argument('serial', type=int)
    rj = sub.add_parser('referral-job'); rj.add_argument('serial', type=int); rj.add_argument('--dry-run', action='store_true')
    for name in ('search', 'flow'):
        sp = sub.add_parser(name)
        sp.add_argument('--role', action='append')
        sp.add_argument('--company', action='append')
        if name == 'flow':
            sp.add_argument('--size', type=int, default=10)
            sp.add_argument('--messages', type=int, default=10)
            sp.add_argument('--dry-run', action='store_true')
    a = p.parse_args()

    if a.cmd == 'tailor':
        run_tailor_batch(a.size)
    elif a.cmd == 'referral':
        run_referral_batch(a.messages, a.max_jobs, a.dry_run, not a.allow_company_repeats)
    elif a.cmd == 'status':
        print(json.dumps(status(), indent=2))
    elif a.cmd == 'reset':
        reset(a.kind, a.serial)
        print(f"{a.kind} batch will start {'from the top' if a.serial is None else f'after job #{a.serial}'}")
    elif a.cmd == 'stop':
        request_stop(a.kind)
        print(f"Stop requested for {a.kind} batch")
    elif a.cmd == 'tailor-job':
        print(f"Result: {tailor_job(a.serial)}")
    elif a.cmd == 'referral-job':
        referral_job(a.serial, a.dry_run)
    elif a.cmd == 'search':
        run_search(a.role, a.company)
    elif a.cmd == 'flow':
        run_flow(a.role, a.company, a.size, a.messages, a.dry_run)


if __name__ == '__main__':
    sys.stdout.reconfigure(line_buffering=True)
    main()
