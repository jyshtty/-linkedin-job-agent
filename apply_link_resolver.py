"""
Resolve a LinkedIn job to its company careers-portal URL and company job ID.

A job is usable for referrals/tailoring only when BOTH are found:
    apply_status == 'OK'  ->  company_career_url + company_job_id are set
Otherwise apply_status says why it is skipped:
    EASY_APPLY      - applies on LinkedIn, no company portal
    AGGREGATOR      - apply link goes to a job board (Naukri, Indeed, ...)
    NO_COMPANY_URL  - external apply, but LinkedIn returned no URL
    NO_JOB_ID       - company portal found, but no job ID in URL/description/page
    UNRESOLVED      - couldn't check (Chrome not running / not logged in); retried next run

LinkedIn only exposes the company apply URL to logged-in users, so this reads it
through your already-open, logged-in Chrome (same AppleScript bridge as the
referral agent). Requires Chrome > View > Developer > Allow JavaScript from Apple Events.

Usage (backfill searched_jobs.csv):
    python apply_link_resolver.py            # resolve rows not yet checked
    python apply_link_resolver.py --force    # re-check every row
"""
import json
import re
import subprocess
import sys
import time
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse

import pandas as pd
import requests

JOBS_FILE = 'searched_job_list/searched_jobs.csv'

AGGREGATOR_DOMAINS = (
    'naukri.com', 'indeed.', 'glassdoor.', 'foundit.', 'monster.', 'monsterindia.',
    'instahyre.com', 'iimjobs.com', 'hirist.', 'cutshort.io', 'wellfound.com', 'angel.co',
    'shine.com', 'timesjobs.com', 'sourcingxpress.com', 'ziprecruiter.', 'dice.com',
    'simplyhired.', 'talent.com', 'jooble.', 'careerbuilder.', 'apna.co', 'workindia.',
    'freshersworld.', 'jobstreet.', 'seek.com', 'adzuna.', 'linkedin.com', 'lnkd.in',
)

# Query params that only track where the click came from
TRACKING_PARAMS = {'source', 'src', 'sourceid', 'ref', 'refid', 'trid', 'lever-source',
                   'gh_src', 'board_id', 'trk', 'trackingid', 'codes', 'iis', 'iisn'}

UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'

# Query params that carry the job ID on common ATSs (SuccessFactors, Taleo, Greenhouse, Infosys, ...)
ID_PARAMS = ('career_job_req_id', 'jobreferencecode', 'gh_jid', 'jobid', 'job_id', 'reqid', 'req_id',
             'requisitionid', 'requisition_id', 'postingid', 'jobreqid', 'jobopeningid', 'jobcode', 'job')

PAGE_ID_KEYS = ('reqId', 'requisitionId', 'requisition_id', 'jobReqId', 'jobRequisitionId', 'reqNumber')

DESCRIPTION_ID = re.compile(
    r'\b(?:job|req(?:uisition)?|position|posting|reference|vacancy)\s*'
    r'(?:id|#|no\.?|number|code|ref(?:erence)?)\s*[:#\-]?\s*([A-Z0-9][A-Z0-9_\-/]{2,30})',
    re.IGNORECASE)

UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/129 Safari/537.36'}

# ---------------------------------------------------------------- Chrome bridge

RUN_JS_SCRIPT = '''
on run argv
    set tid to (item 1 of argv)
    set code to item 2 of argv
    tell application "Google Chrome"
        repeat with w in windows
            repeat with t in tabs of w
                if ((id of t) as text) is tid then return execute t javascript code
            end repeat
        end repeat
    end tell
    return "__NO_TAB__"
end run
'''

FIND_OR_OPEN_TAB_SCRIPT = '''
tell application "Google Chrome"
    repeat with w in windows
        repeat with t in tabs of w
            if URL of t contains "linkedin.com" then return (id of t) as text
        end repeat
    end repeat
    if (count of windows) is 0 then make new window
    tell front window
        set t to make new tab with properties {URL:"https://www.linkedin.com/feed/"}
        return "NEW:" & ((id of t) as text)
    end tell
end tell
'''

# Synchronous XHR so AppleScript gets the result back; uses the page's own session.
JS_JOB_POSTING = r'''
const csrf = (document.cookie.match(/JSESSIONID="?([^";]+)/) || [])[1];
if (!csrf) return {status: 401};
const x = new XMLHttpRequest();
x.open('GET', '/voyager/api/jobs/jobPostings/' + __ID__ +
    '?decorationId=com.linkedin.voyager.deco.jobs.web.shared.WebFullJobPosting-65', false);
x.setRequestHeader('csrf-token', csrf);
x.setRequestHeader('x-restli-protocol-version', '2.0.0');
x.send();
if (x.status !== 200) return {status: x.status};
const d = JSON.parse(x.responseText);
const company = (JSON.stringify(d.companyDetails || {}).match(/fs_normalized_company:(\d+)/) || [])[1] || '';
return {status: 200, apply: d.applyMethod || {}, description: (d.description && d.description.text) || '', company_id: company};
'''


class LinkedInSession:
    """Runs LinkedIn API calls inside a logged-in Chrome tab."""

    def __init__(self):
        self.tab_id = None
        running = subprocess.run(['osascript', '-e', 'application "Google Chrome" is running'],
                                 capture_output=True, text=True).stdout.strip()
        if running != 'true':
            return
        out = subprocess.run(['osascript', '-e', FIND_OR_OPEN_TAB_SCRIPT],
                             capture_output=True, text=True).stdout.strip()
        if out.startswith('NEW:'):
            out = out[4:]
            time.sleep(6)  # let the new LinkedIn tab load so it has session cookies
        self.tab_id = out or None

    @property
    def available(self):
        return self.tab_id is not None

    def job_posting(self, numeric_id):
        code = f'JSON.stringify((() => {{ {JS_JOB_POSTING.replace("__ID__", json.dumps(numeric_id))} }})())'
        r = subprocess.run(['osascript', '-e', RUN_JS_SCRIPT, self.tab_id, code],
                           capture_output=True, text=True)
        if 'JavaScript through AppleScript' in r.stderr:
            print("   ⚠️  Enable Chrome > View > Developer > Allow JavaScript from Apple Events")
            self.tab_id = None
            return None
        try:
            return json.loads(r.stdout)
        except ValueError:
            return None

# ---------------------------------------------------------------- URL handling


def clean_url(url):
    """Drop tracking params (also inside #fragments) and trailing /apply pages."""
    p = urlparse(url.strip())
    query = urlencode([(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
                       if k.lower() not in TRACKING_PARAMS and not k.lower().startswith('utm_')])
    fragment = p.fragment
    if '?' in fragment:  # SPA routes like #/Career Portal/83656?utm_source=LinkedIn
        route, fquery = fragment.split('?', 1)
        fquery = urlencode([(k, v) for k, v in parse_qsl(fquery, keep_blank_values=True)
                            if k.lower() not in TRACKING_PARAMS and not k.lower().startswith('utm_')])
        fragment = route + ('?' + fquery if fquery else '')
    path = re.sub(r'/(apply|application)/?$', '', p.path)
    return urlunparse((p.scheme, p.netloc, path, p.params, query, fragment))


def is_aggregator(url):
    host = urlparse(url).netloc.lower()
    return any(d in host for d in AGGREGATOR_DOMAINS)


def plausible_id(value):
    """A real requisition number, not an internal tracking hash like Phenom's 80-char codes."""
    value = (value or '').strip()
    if not 3 <= len(value) <= 30 or not re.search(r'\d', value):
        return False
    return not re.fullmatch(r'[0-9a-fA-F]{20,}', value)


def job_id_from_url(url):
    p = urlparse(url)
    host = p.netloc.lower()
    route = p.path + ('/' + p.fragment if p.fragment else '')
    segments = [s for s in re.split(r'[/#]', route) if s]

    for k, v in parse_qsl(p.query + '&' + (p.fragment.split('?', 1)[1] if '?' in p.fragment else '')):
        if k.lower() in ID_PARAMS and plausible_id(v):
            return v

    if 'myworkdayjobs.com' in host and segments:
        # .../job/Mumbai-India/Senior-DevOps-Engineer_R15145  ->  R15145
        last = segments[-1]
        if '_' in last and plausible_id(last.rsplit('_', 1)[1]):
            return last.rsplit('_', 1)[1]

    # Phenom portals (Cisco, Mastercard, ...): /job/MASRUSR292939EXTERNALENUS/...  ->  R292939
    for seg in segments:
        m = re.search(r'(R?\d{4,})EXTERNAL', seg)
        if m:
            return m.group(1)

    # Lever / Ashby / other UUID-based postings
    m = re.search(UUID, route, re.IGNORECASE)
    if m:
        return m.group(0)

    if 'epam' in host and 'vacancy' in segments:
        i = segments.index('vacancy')
        if i + 1 < len(segments):
            return segments[i + 1]

    # Generic: last path/fragment segment with a 4+ digit token
    # (SmartRecruiters 744000151583482-title, Keka /jobdetails/141668, iCIMS /jobs/9876/..., Oracle /job/123456)
    for seg in reversed(segments):
        for token in re.split(r'[-_]', seg):
            if re.search(r'\d{4,}', token) and plausible_id(token):
                return token
    return None


def job_id_from_text(text):
    for m in DESCRIPTION_ID.finditer(text or ''):
        candidate = m.group(1).strip('-/')
        if plausible_id(candidate):
            return candidate
    return None


def job_id_from_page(url):
    """Last resort: the careers page itself (JSON-LD JobPosting identifier or 'Job ID: ...' text)."""
    try:
        html = requests.get(url, headers=UA, timeout=10).text
    except requests.RequestException:
        return None
    # Requisition fields in the page's embedded data (e.g. Phenom portals: "reqId":"REQ20652")
    for key in PAGE_ID_KEYS:
        for m in re.finditer(r'"%s"\s*:\s*"([^"]+)"' % key, html, re.IGNORECASE):
            if plausible_id(m.group(1)) and not re.fullmatch(UUID, m.group(1), re.IGNORECASE):
                return m.group(1)
    m = re.search(r'"identifier"\s*:\s*\{[^}]*?"value"\s*:\s*"([^"]+)"', html)
    if m and plausible_id(m.group(1)) and not re.fullmatch(UUID, m.group(1), re.IGNORECASE):
        return m.group(1)
    return job_id_from_text(re.sub(r'<[^>]+>', ' ', html))

# ---------------------------------------------------------------- resolve


def numeric_job_id(linkedin_job_id):
    m = re.search(r'(\d+)$', str(linkedin_job_id))
    return m.group(1) if m else str(linkedin_job_id)


def resolve(linkedin_job_id, session):
    """Returns {apply_status, company_career_url, company_job_id, description, linkedin_company_id}."""
    result = {'apply_status': 'UNRESOLVED', 'company_career_url': 'TBD', 'company_job_id': 'N/A',
              'description': '', 'linkedin_company_id': ''}
    if not session.available:
        return result
    data = session.job_posting(numeric_job_id(linkedin_job_id))
    if not data or data.get('status') != 200:
        return result

    result['description'] = data.get('description', '')
    result['linkedin_company_id'] = data.get('company_id', '')
    apply_type, details = next(iter(data['apply'].items()), ('', {}))
    if 'OnsiteApply' in apply_type:
        return {**result, 'apply_status': 'EASY_APPLY', 'company_career_url': 'EASY_APPLY'}

    raw_url = (details or {}).get('companyApplyUrl')
    if not raw_url:
        return {**result, 'apply_status': 'NO_COMPANY_URL', 'company_career_url': 'NO_COMPANY_URL'}

    url = clean_url(raw_url)
    if is_aggregator(url):
        return {**result, 'apply_status': 'AGGREGATOR', 'company_career_url': url}

    job_id = job_id_from_url(url) or job_id_from_text(result['description']) or job_id_from_page(url)
    if not job_id:
        return {**result, 'apply_status': 'NO_JOB_ID', 'company_career_url': url}
    return {**result, 'apply_status': 'OK', 'company_career_url': url, 'company_job_id': job_id}


SKIP_REASONS = {
    'EASY_APPLY': "it's an Easy Apply job (no company careers portal)",
    'AGGREGATOR': "its apply link goes to a job board, not the company's portal",
    'NO_COMPANY_URL': "LinkedIn has no company apply URL for it",
    'NO_JOB_ID': "no company job ID could be found for it",
    'NOT_INTERESTED': "it's posted by a company that isn't in interested_companies/",
    'UNRESOLVED': "its company link couldn't be checked (open Chrome logged in to LinkedIn and retry)",
}


def resolved_job(serial_number):
    """
    Job row for a serial number, with its company link resolved.
    Resolves (and saves to the CSV) on first use, so old rows work without a backfill.
    """
    df = pd.read_csv(JOBS_FILE, dtype=str)
    if 'apply_status' not in df.columns:
        df['apply_status'] = 'UNRESOLVED'
    df['apply_status'] = df['apply_status'].fillna('UNRESOLVED')
    match = df.index[df['serial_number'] == str(serial_number)]
    if len(match) == 0:
        return None
    i = match[0]
    if df.at[i, 'apply_status'] == 'UNRESOLVED':
        print("🔗 Looking up the company careers link...")
        r = resolve(df.at[i, 'linkedin_job_id'], LinkedInSession())
        for col in ('apply_status', 'company_career_url', 'company_job_id', 'linkedin_company_id'):
            df.at[i, col] = r[col]
        df.to_csv(JOBS_FILE, index=False)
    return df.loc[i].to_dict()


def backfill(force=False):
    df = pd.read_csv(JOBS_FILE, dtype=str)
    if 'apply_status' not in df.columns:
        df['apply_status'] = 'UNRESOLVED'
    df['apply_status'] = df['apply_status'].fillna('UNRESOLVED')

    todo = df.index if force else df.index[df['apply_status'] == 'UNRESOLVED']
    if len(todo) == 0:
        print("All jobs already resolved (use --force to re-check).")
        return df

    session = LinkedInSession()
    if not session.available:
        sys.exit("❌ Chrome isn't running with LinkedIn. Open Chrome (logged in to LinkedIn) and rerun.")

    print(f"Resolving {len(todo)} jobs...\n")
    for i in todo:
        r = resolve(df.at[i, 'linkedin_job_id'], session)
        for col in ('apply_status', 'company_career_url', 'company_job_id', 'linkedin_company_id'):
            df.at[i, col] = r[col]
        print(f"#{df.at[i, 'serial_number']:>3} {df.at[i, 'company'][:28]:<28} {r['apply_status']:<14} "
              f"{r['company_job_id'] if r['apply_status'] == 'OK' else ''}")
        time.sleep(0.4)

    df.to_csv(JOBS_FILE, index=False)
    print(f"\n{df['apply_status'].value_counts().to_string()}")
    print(f"\nSaved to {JOBS_FILE}")
    return df


if __name__ == '__main__':
    backfill(force='--force' in sys.argv)
