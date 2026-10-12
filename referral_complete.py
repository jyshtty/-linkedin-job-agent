"""
Complete referral agent - from opening Chrome to sending messages.

Drives your already-running, logged-in Chrome through AppleScript (no new
browser session). One-time setup in Chrome:
    View > Developer > Allow JavaScript from Apple Events

Usage:
    python referral_complete.py <job_serial>             # send messages
    python referral_complete.py <job_serial> --dry-run   # type messages but don't send
"""
import base64
import csv
import glob
import json
import os
import random
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from urllib.parse import quote

import pandas as pd

from apply_link_resolver import SKIP_REASONS, numeric_job_id, resolved_job

LOG_FILE = 'referral_log.csv'
LOG_COLUMNS = ['timestamp', 'job_serial', 'company', 'job_title', 'employee_name', 'employee_title',
               'profile_link', 'sent', 'linkedin_job_id']
COMPANY_COOLDOWN_DAYS = 30
TAILORED_RESUME_DIR = 'tailored_resume'
ORIGINAL_RESUME_DIR = 'original_resume'
MAX_PAGES = 5

# Runs JavaScript in a specific tab (found by id, so switching tabs doesn't break it).
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

OPEN_TAB_SCRIPT = '''
on run argv
    tell application "Google Chrome"
        activate
        if (count of windows) is 0 then make new window
        tell front window
            set t to make new tab with properties {URL:(item 1 of argv)}
            return id of t
        end tell
    end tell
end run
'''

CLOSE_TAB_SCRIPT = '''
on run argv
    set tid to (item 1 of argv)
    tell application "Google Chrome"
        repeat with w in windows
            repeat with t in tabs of w
                if ((id of t) as text) is tid then
                    close t
                    return "ok"
                end if
            end repeat
        end repeat
    end tell
    return "__NO_TAB__"
end run
'''

FOCUS_TAB_SCRIPT = '''
on run argv
    set tid to (item 1 of argv)
    tell application "Google Chrome"
        repeat with w in windows
            set i to 0
            repeat with t in tabs of w
                set i to i + 1
                if ((id of t) as text) is tid then
                    set active tab index of w to i
                    set index of w to 1
                    activate
                    return "ok"
                end if
            end repeat
        end repeat
    end tell
    return "__NO_TAB__"
end run
'''

# Shared helpers prepended to every snippet. Everything runs inside an IIFE so
# repeated calls don't collide on `const` declarations in the page's scope.
JS_LIB = r'''
const BOX_SEL = '.msg-form__contenteditable[contenteditable="true"], form.msg-form [contenteditable="true"], ' +
    '[class*="msg-"] [contenteditable="true"], [role="dialog"] [contenteditable="true"][role="textbox"]';
const BUBBLE_SEL = '.msg-overlay-conversation-bubble, [class*="msg-overlay-conversation-bubble"], .msg-convo-wrapper, .scaffold-layout__detail';
// LinkedIn renders the chat overlay inside a shadow root, so plain
// document.querySelectorAll can't see it. Search shadow roots and iframes too.
const allRoots = () => {
    const out = [document];
    const walk = root => {
        for (const el of root.querySelectorAll('*')) {
            if (el.shadowRoot) { out.push(el.shadowRoot); walk(el.shadowRoot); }
            if (el.tagName === 'IFRAME') {
                try { const d = el.contentDocument; if (d) { out.push(d); walk(d); } } catch (e) {}
            }
        }
    };
    walk(document);
    return out;
};
const qsa = sel => allRoots().flatMap(r => [...r.querySelectorAll(sel)]);
const textOf = n => !n ? '' : (n.innerText ?? [...n.children].map(c => c.innerText || '').join('\n'));
const visible = el => !!el && el.getClientRects().length > 0;
const findBox = () => qsa(BOX_SEL).find(visible);
const scopeOf = el => (el && (el.closest(BUBBLE_SEL) || el.getRootNode())) || document;
const threadOf = el => { const s = scopeOf(el); return s.querySelector('.msg-s-message-list, .msg-s-message-list-content') || s; };
const sendBtnOf = box => (box.closest('form') || scopeOf(box)).querySelector('button.msg-form__send-button, button[type="submit"]');
const clearBox = box => {
    const doc = box.ownerDocument;
    box.focus();
    const r = doc.createRange();
    r.selectNodeContents(box);
    const sel = doc.defaultView.getSelection();
    sel.removeAllRanges();
    sel.addRange(r);
    doc.execCommand('delete');
};
'''

JS_PAGE_STATE = '''
return {
    ready: document.readyState === 'complete' && !!document.querySelector('main'),
    url: location.href,
    results: document.querySelectorAll('main a[href*="/in/"]').length,
};
'''

JS_SCROLL_RESULTS = '''
window.scrollTo(0, document.body.scrollHeight);
return true;
'''

# Exact "Message" buttons/links on result cards only - skips the top-nav
# "Messaging" item and anything inside the chat overlay.
JS_LIST_CANDIDATES = r'''
const out = [];
const seen = new Set();
for (const el of document.querySelectorAll('main button, main a')) {
    if (!visible(el) || el.closest('header, #global-nav, .msg-overlay-container, aside')) continue;
    const text = (el.innerText || '').trim();
    const aria = (el.getAttribute('aria-label') || '').trim();
    if (text !== 'Message' && !/^(send a )?message\b/i.test(aria)) continue;
    const card = el.closest('li') || el.parentElement?.parentElement;
    const link = card && card.querySelector('a[href*="/in/"]');
    const profile = link ? link.href.split('?')[0] : '';
    let name = aria.replace(/^(send a )?message( to)?\s*/i, '').trim();
    if (!name && link) name = (link.innerText || '').split('\n')[0].trim();
    const key = profile || name;
    if (!key || seen.has(key)) continue;
    seen.add(key);
    el.setAttribute('data-ra-key', key);
    out.push({name, profile, key});
}
return out;
'''

JS_CLICK_CANDIDATE = '''
const el = document.querySelector('[data-ra-key="' + CSS.escape(__KEY__) + '"]');
if (!el) return false;
el.scrollIntoView({block: 'center'});
el.click();
return true;
'''

JS_CLOSE_BUBBLES = r'''
let closed = 0;
for (const b of qsa('[class*="msg-overlay-conversation-bubble"]')) {
    const btn = [...b.querySelectorAll('button')].find(x =>
        /close your|close conversation|close.*(draft|message)|^close$|^dismiss$/i.test(((x.getAttribute('aria-label') || '') + ' ' + (x.innerText || '')).trim()) ||
        x.querySelector('[data-test-icon="close-small"], use[href*="close-small"]'));
    if (btn) { btn.click(); closed++; }
}
const discard = qsa('.artdeco-modal button').find(x => /discard/i.test(x.innerText || ''));
if (discard) discard.click();
return closed;
'''

JS_IS_INMAIL = '''
const box = findBox();
const scope = box ? scopeOf(box) : qsa('[class*="msg-overlay-conversation-bubble"]').find(visible);
return !!scope && /InMail credit/i.test(textOf(scope));
'''

# Snapshot of the chat overlay, written to a file when a step fails so
# selectors can be fixed against LinkedIn's real markup.
JS_DEBUG = '''
const describe = el => ({tag: el.tagName, cls: String(el.className).slice(0, 200),
    role: el.getAttribute('role'), aria: el.getAttribute('aria-label'), ce: el.getAttribute('contenteditable')});
return {
    url: location.href,
    roots: allRoots().length,
    shadow_hosts: allRoots().filter(r => r.host).map(r => describe(r.host)),
    editables: qsa('[contenteditable], textarea').filter(visible).map(describe),
    overlays: qsa('[class*="msg-overlay"], [role="dialog"]').filter(visible).slice(0, 15).map(describe),
    buttons: qsa('[class*="msg-overlay"] button, [role="dialog"] button').filter(visible).slice(0, 30).map(describe),
};
'''

JS_THREAD_HAS_JOB = '''
const box = findBox();
if (!box) return null;
const text = textOf(threadOf(box));
return __MARKERS__.some(m => text.includes(m));
'''

# execCommand goes through the browser's editing pipeline, so LinkedIn's
# editor state updates and the Send button enables (setting textContent doesn't).
JS_TYPE_MESSAGE = '''
const box = findBox();
if (!box) return -1;
clearBox(box);
const doc = box.ownerDocument;
__MSG__.split('\\n').forEach((line, i) => {
    if (i) doc.execCommand('insertParagraph');
    if (line) doc.execCommand('insertText', false, line);
});
box.dispatchEvent(new Event('input', {bubbles: true}));
return box.innerText.replace(/\\s+/g, '').length;
'''

# Loads the PDF into the chat's "Attach a file" input (the one that accepts .pdf).
JS_ATTACH_FILE = '''
const box = findBox();
if (!box) return 'no_box';
const form = box.closest('form') || scopeOf(box);
const input = [...form.querySelectorAll('input[type="file"]')].find(i => /\\.pdf/.test(i.accept));
if (!input) return 'no_input';
const bin = atob(__DATA__);
const bytes = new Uint8Array(bin.length);
for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
const dt = new DataTransfer();
dt.items.add(new File([bytes], __NAME__, {type: 'application/pdf'}));
input.files = dt.files;
input.dispatchEvent(new Event('change', {bubbles: true}));
return 'attached';
'''

# LinkedIn shows "<name> <size> Attached" once the upload finishes.
JS_ATTACHMENT_READY = '''
const box = findBox();
const scope = scopeOf(box);
const preview = [...scope.querySelectorAll('.msg-form__attachment-preview')].find(visible);
return !!preview && textOf(preview).includes(__NAME__) && /Attached/.test(textOf(preview));
'''

JS_REMOVE_ATTACHMENTS = '''
const btns = qsa('.msg-attachment-preview__remove-attachment').filter(visible);
btns.forEach(b => b.click());
return btns.length;
'''

JS_CLEAR_BOX = '''
const box = findBox();
if (box) clearBox(box);
return !!box;
'''

JS_CLICK_SEND = '''
const box = findBox();
if (!box) return 'no_box';
const btn = sendBtnOf(box);
if (!btn) return 'no_button';
if (btn.disabled) return 'disabled';
btn.click();
return 'clicked';
'''

JS_SEND_STATE = '''
const box = findBox();
return {
    empty: !box || box.innerText.trim() === '',
    in_thread: __MARKERS__.some(m => textOf(threadOf(box)).includes(m)),
};
'''


class Chrome:
    """Thin AppleScript bridge to one Chrome tab."""

    def __init__(self, url):
        result = self._osascript(OPEN_TAB_SCRIPT, url)
        self.tab_id = result.strip()

    @staticmethod
    def _osascript(script, *args):
        r = subprocess.run(['osascript', '-e', script, *args], capture_output=True, text=True)
        if 'JavaScript through AppleScript' in r.stderr:
            sys.exit("\n❌ Chrome is blocking scripted JavaScript.\n"
                     "   Enable: Chrome menu > View > Developer > Allow JavaScript from Apple Events\n")
        if r.returncode != 0:
            raise RuntimeError(r.stderr.strip())
        return r.stdout

    def js(self, body, **params):
        for k, v in params.items():
            body = body.replace(f'__{k.upper()}__', json.dumps(v))
        code = f'JSON.stringify((() => {{ {JS_LIB}\n{body} }})())'
        out = self._osascript(RUN_JS_SCRIPT, self.tab_id, code).strip()
        if out == '__NO_TAB__':
            sys.exit("\n❌ The LinkedIn tab was closed. Stopping.\n")
        if out in ('', 'missing value'):
            return None
        return json.loads(out)

    def navigate(self, url):
        self.js('location.href = __URL__; return true;', url=url)
        time.sleep(2)

    def focus(self):
        self._osascript(FOCUS_TAB_SCRIPT, self.tab_id)

    def close(self):
        self._osascript(CLOSE_TAB_SCRIPT, self.tab_id)


def wait_for(check, timeout, interval=1.0):
    """Poll check() until it returns something truthy or timeout expires."""
    end = time.time() + timeout
    while time.time() < end:
        value = check()
        if value:
            return value
        time.sleep(interval)
    return None


def search_url(company, page):
    return (f"https://www.linkedin.com/search/results/people/?keywords={quote(company)}"
            f"&network=%5B%22F%22%5D&origin=FACETED_SEARCH&page={page}")


def load_results(chrome):
    """Wait for the search page to render; returns False if there are no results."""
    state = wait_for(lambda: (s := chrome.js(JS_PAGE_STATE)) and s['ready'] and s, timeout=30)
    if not state:
        print("   ⚠️  Page did not finish loading")
        return False
    if '/login' in state['url'] or '/authwall' in state['url']:
        sys.exit("\n❌ LinkedIn is asking you to log in. Log in in Chrome, then rerun.\n")
    time.sleep(3)
    chrome.js(JS_SCROLL_RESULTS)
    time.sleep(2)
    return chrome.js(JS_PAGE_STATE)['results'] > 0


def first_name(name):
    cleaned = re.split(r'[•,|(]', name)[0].strip()
    parts = [p for p in cleaned.split() if p.rstrip('.').lower() not in ('dr', 'mr', 'ms', 'mrs')]
    return parts[0].capitalize() if parts else ''


def build_message(template, config, job, name):
    fname = first_name(name)
    if not fname:
        template = template.replace('Hi {name},', 'Hi,')
    return template.format(
        name=fname,
        your_title=config['your_title'],
        your_expertise=config['your_expertise'],
        company=job['company'],
        job_title=job['job_title'],
        job_link=job['company_career_url'],
        company_job_id=job['company_job_id'],
    )


def find_resume(job):
    """Tailored resume for this job if one exists, else the original resume."""
    # resume_tailor names files <Company>_<serial>_<company job ID>.pdf. Match on company +
    # job ID (serials change between searches); older files carry the LinkedIn job ID instead.
    company = re.sub(r'[^A-Za-z0-9._-]', '_', job['company'])
    company_job_id = re.sub(r'[^A-Za-z0-9._-]', '_', str(job['company_job_id']))
    linkedin_id = numeric_job_id(job['linkedin_job_id'])
    for path in sorted(glob.glob(os.path.join(TAILORED_RESUME_DIR, '*.pdf'))):
        name = os.path.basename(path)
        if (name.startswith(company + '_') and name.endswith(f'_{company_job_id}.pdf')) \
                or re.search(rf'[-_]{linkedin_id}_', name):
            return path, True
    originals = sorted(glob.glob(os.path.join(ORIGINAL_RESUME_DIR, '*.pdf')))
    return (originals[0], False) if originals else (None, False)


def attach_resume(chrome, resume):
    """Attach the PDF and wait for LinkedIn to finish uploading it."""
    with open(resume['path'], 'rb') as f:
        data = base64.b64encode(f.read()).decode()
    if chrome.js(JS_ATTACH_FILE, data=data, name=resume['name']) != 'attached':
        return False
    return bool(wait_for(lambda: chrome.js(JS_ATTACHMENT_READY, name=resume['name']), timeout=30))


def close_conversation(chrome):
    chrome.js(JS_CLOSE_BUBBLES)
    time.sleep(1)
    chrome.js(JS_CLOSE_BUBBLES)  # second pass handles a "Discard draft?" modal
    time.sleep(1)


def paste_message(chrome, message):
    """Fallback when execCommand typing doesn't take: real clipboard paste."""
    chrome.js(JS_CLEAR_BOX)
    subprocess.run(['pbcopy'], input=message, text=True)
    chrome.focus()
    time.sleep(1)
    subprocess.run(['osascript', '-e',
                    'tell application "System Events" to keystroke "v" using command down'],
                   capture_output=True)
    time.sleep(1)


def dump_debug(chrome, step):
    with open('referral_debug.json', 'w') as f:
        json.dump({'step': step, **(chrome.js(JS_DEBUG) or {})}, f, indent=2)
    print(f"   🔍 Saved page details to referral_debug.json")


def message_person(chrome, candidate, message, resume, job_markers, dry_run):
    """Open the chat, type, send and verify. Returns a status string."""
    close_conversation(chrome)

    if not chrome.js(JS_CLICK_CANDIDATE, key=candidate['key']):
        return 'failed:button_gone'

    opened = wait_for(lambda: chrome.js('return !!findBox();') or chrome.js(JS_IS_INMAIL), timeout=15)
    if chrome.js(JS_IS_INMAIL):
        close_conversation(chrome)
        return 'skipped_inmail'
    if not opened:
        dump_debug(chrome, 'no_message_box')
        close_conversation(chrome)
        return 'failed:no_message_box'
    time.sleep(2)  # let the conversation history load

    if chrome.js(JS_THREAD_HAS_JOB, markers=job_markers):
        close_conversation(chrome)
        return 'already_messaged'

    expected = len(re.sub(r'\s+', '', message))
    typed = chrome.js(JS_TYPE_MESSAGE, msg=message)
    if typed < expected * 0.9:
        print("   ↪️  Typing didn't register, retrying with paste...")
        paste_message(chrome, message)
        typed = chrome.js('const b = findBox(); return b ? b.innerText.replace(/\\s+/g, "").length : -1;')
        if typed < expected * 0.9:
            dump_debug(chrome, 'could_not_type')
            close_conversation(chrome)
            return 'failed:could_not_type'

    if not attach_resume(chrome, resume):
        dump_debug(chrome, 'attach_resume')
        chrome.js(JS_REMOVE_ATTACHMENTS)
        chrome.js(JS_CLEAR_BOX)
        close_conversation(chrome)
        return 'failed:could_not_attach_resume'

    if dry_run:
        time.sleep(2)
        chrome.js(JS_REMOVE_ATTACHMENTS)
        chrome.js(JS_CLEAR_BOX)
        close_conversation(chrome)
        return 'dry_run'

    clicked = wait_for(lambda: chrome.js(JS_CLICK_SEND) == 'clicked', timeout=8)
    if not clicked:
        dump_debug(chrome, 'send_button')
        chrome.js(JS_REMOVE_ATTACHMENTS)
        close_conversation(chrome)
        return 'failed:send_button'

    state = wait_for(lambda: (s := chrome.js(JS_SEND_STATE, markers=job_markers)) and s['in_thread'] and s, timeout=10)
    if not state:
        state = chrome.js(JS_SEND_STATE, markers=job_markers)
        if not (state and state['empty']):
            close_conversation(chrome)
            return 'failed:not_confirmed'

    time.sleep(2)
    close_conversation(chrome)
    return 'sent'


def _read_log():
    if not os.path.exists(LOG_FILE):
        return pd.DataFrame(columns=LOG_COLUMNS)
    df = pd.read_csv(LOG_FILE, dtype=str).fillna('')
    for col in LOG_COLUMNS:
        if col not in df.columns:
            df[col] = ''
    return df


def already_sent_count(job):
    """How many people have already been messaged about this job."""
    df = _read_log()
    return int(((df['linkedin_job_id'] == numeric_job_id(job['linkedin_job_id'])) & (df['sent'] == 'Yes')).sum())


def load_log(job):
    """Profiles/names already handled for this job, so reruns don't double-message."""
    df = _read_log()
    linkedin_id = numeric_job_id(job['linkedin_job_id'])
    # Older rows have no LinkedIn job ID; fall back to the serial number for those
    same_job = (df['linkedin_job_id'] == linkedin_id) | \
               ((df['linkedin_job_id'] == '') & (df['job_serial'] == str(job['serial_number'])))
    done = df[same_job & df['sent'].isin(['Yes', 'Already'])]
    return (set(done['profile_link']) | set(done['employee_name'])) - {''}


def recent_company_contacts(company):
    """People already asked about any job at this company in the last COMPANY_COOLDOWN_DAYS days."""
    df = _read_log()
    cutoff = (datetime.now() - timedelta(days=COMPANY_COOLDOWN_DAYS)).strftime('%Y-%m-%d %H:%M:%S')
    done = df[(df['company'] == company) & (df['sent'] == 'Yes') & (df['timestamp'] >= cutoff)]
    return (set(done['profile_link']) | set(done['employee_name'])) - {''}


def log_referral(job, candidate, status):
    sent = {'sent': 'Yes', 'already_messaged': 'Already', 'dry_run': 'DryRun'}.get(status, 'No')
    df = _read_log()
    if os.path.exists(LOG_FILE) and list(pd.read_csv(LOG_FILE, nrows=0).columns) != LOG_COLUMNS:
        df[LOG_COLUMNS].to_csv(LOG_FILE, index=False)  # upgrade an older log's header in place
    file_exists = os.path.exists(LOG_FILE)
    with open(LOG_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(LOG_COLUMNS)
        writer.writerow([datetime.now().strftime('%Y-%m-%d %H:%M:%S'), job['serial_number'],
                         job['company'], job['job_title'], candidate['name'], '',
                         candidate['profile'], sent, numeric_job_id(job['linkedin_job_id'])])


def run(serial_number, dry_run=False, max_messages=None, skip_company_contacts=False, should_stop=None,
        close_tab=False):
    """
    Message connections about one job. Returns {'status', 'sent'} where status is
    'done', 'skipped' (job not usable), 'capped' (stopped at max_messages),
    'stopped' (should_stop() said so) or 'error'.
    """
    # Load job, with its company careers link
    job = resolved_job(serial_number)
    if job is None:
        print(f"❌ No job found with serial number {serial_number}")
        return {'status': 'error', 'sent': 0}
    if job['apply_status'] != 'OK':
        print(f"\n⏭️  Skipping job #{serial_number} ({job['company']} - {job['job_title']}):")
        print(f"   {SKIP_REASONS.get(job['apply_status'], job['apply_status'])}. No messages sent.\n")
        return {'status': 'skipped', 'sent': 0}
    job_markers = [job['company_career_url'], numeric_job_id(job['linkedin_job_id'])]

    resume_path, tailored = find_resume(job)
    if not resume_path:
        print(f"❌ No resume PDF found in {TAILORED_RESUME_DIR}/ or {ORIGINAL_RESUME_DIR}/")
        return {'status': 'error', 'sent': 0}
    # Always attach under the original resume's clean file name
    originals = sorted(glob.glob(os.path.join(ORIGINAL_RESUME_DIR, '*.pdf')))
    resume = {'path': resume_path,
              'name': os.path.basename(originals[0]) if originals else os.path.basename(resume_path)}

    # Load config
    config = {'referrals_per_job': 2, 'your_title': 'Senior Software Engineer', 'your_expertise': 'DSA and System Design'}
    if os.path.exists('referral_config.txt'):
        with open('referral_config.txt', 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key] = int(value) if key == 'referrals_per_job' else value

    # Load template
    with open('referral_template.txt', 'r') as f:
        template = f.read()

    # People already messaged about this job count toward referrals_per_job
    previously_sent = already_sent_count(job)
    wanted = max(config['referrals_per_job'] - previously_sent, 0)
    target = wanted if max_messages is None else min(wanted, max_messages)
    capped = target < wanted
    if wanted == 0:
        print(f"\n✅ Job #{serial_number} ({job['company']}) already has {previously_sent} referral requests. Nothing to send.\n")
        return {'status': 'done', 'sent': 0}
    done = load_log(job)
    company_contacts = recent_company_contacts(job['company']) if skip_company_contacts else set()

    print(f"\n{'='*80}")
    print(f"🤖 REFERRAL AGENT - JOB #{serial_number}{'  (DRY RUN - nothing will be sent)' if dry_run else ''}")
    print(f"{'='*80}")
    print(f"Company: {job['company']}")
    print(f"Job: {job['job_title']}")
    print(f"Company link: {job['company_career_url']}")
    print(f"Company job ID: {job['company_job_id']}")
    print(f"Resume: {resume_path} ({'tailored for this job' if tailored else 'default'})")
    print(f"Target: {target} referrals" + (f" ({previously_sent} already sent earlier)" if previously_sent else ""))
    if done:
        print(f"Skipping people already messaged for this job (see {LOG_FILE})")
    if company_contacts:
        print(f"Skipping {len(company_contacts)} people asked about {job['company']} in the last {COMPANY_COOLDOWN_DAYS} days")
    print(f"{'='*80}\n")

    # Step 1: Open LinkedIn search in a new tab of your existing Chrome
    print("🌐 Opening LinkedIn search in Chrome...")
    chrome = Chrome(search_url(job['company'], 1))

    # Step 2: Walk result pages, messaging people who have a Message button
    sent = 0
    tried = set()
    for page in range(1, MAX_PAGES + 1):
        if page > 1:
            print(f"📄 Moving to results page {page}...")
            chrome.navigate(search_url(job['company'], page))
        if not load_results(chrome):
            print("   No more results.")
            break

        while sent < target:
            if should_stop and should_stop():
                print("⏹️  Stop requested, finishing here.")
                if close_tab:
                    chrome.close()
                return {'status': 'stopped', 'sent': sent}
            candidates = [c for c in chrome.js(JS_LIST_CANDIDATES) or []
                          if c['key'] not in tried and not ({c['profile'], c['name']} & (done | company_contacts))]
            if not candidates:
                break
            candidate = candidates[0]
            tried.add(candidate['key'])

            print(f"[{sent + 1}/{target}] {candidate['name'] or candidate['profile']}")
            message = build_message(template, config, job, candidate['name'])
            status = message_person(chrome, candidate, message, resume, job_markers, dry_run)
            log_referral(job, candidate, status)

            icons = {'sent': '✅ Sent!', 'dry_run': '🧪 Typed (dry run, not sent)',
                     'already_messaged': '⏭️  Already asked about this job, skipping',
                     'skipped_inmail': '⏭️  Not a free message (InMail), skipping'}
            print(f"   {icons.get(status, '❌ ' + status)}\n")
            if status in ('sent', 'dry_run'):
                sent += 1

            # Some Message buttons open the full messaging page; come back to the results
            if '/search/results/people' not in chrome.js('return location.href;'):
                chrome.navigate(search_url(job['company'], page))
                load_results(chrome)

            if sent < target:
                time.sleep(random.uniform(3, 6))

        if sent >= target:
            break

    print(f"{'='*80}")
    print(f"✅ FINISHED! {'Typed' if dry_run else 'Sent'} {sent}/{target} messages  (log: {LOG_FILE})")
    if sent < target:
        print("   Not enough 1st-degree connections with a Message button at this company.")
    print(f"{'='*80}\n")
    if close_tab:
        chrome.close()
    return {'status': 'capped' if capped and sent >= target else 'done', 'sent': sent}


if __name__ == '__main__':
    sys.stdout.reconfigure(line_buffering=True)
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print("Usage: python referral_complete.py <job_serial> [--dry-run]")
        print("Example: python referral_complete.py 1 --dry-run")
    else:
        run(int(args[0]), dry_run='--dry-run' in sys.argv)
