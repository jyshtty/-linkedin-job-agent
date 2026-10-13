"""
Company portal search: finds jobs straight on a company's own careers site with
Firecrawl's AI agent (https://docs.firecrawl.dev/features/agent), for companies whose
jobs don't show up (or show up badly) in the LinkedIn search.

    python portal_search.py --company Databricks --company Stripe [--role R ...] [--max-credits 150]

One agent run per company, covering every role. Jobs land in searched_jobs.csv with
apply_status OK, so tailor batches / auto tailor pick them up like LinkedIn jobs.
Portal jobs have no LinkedIn posting, so their linkedin_job_id is "portal-<company>-<job id>"
and the tailor reads their description from the portal page instead of LinkedIn.

Needs FIRECRAWL_API_KEY in .env. Agent runs can cost a few hundred credits, so each
run is capped by --max-credits (a run that hits the cap still returns what it found).
"""
import argparse
import os
import re
import time
from datetime import datetime, timedelta

import pandas as pd
import requests
from dotenv import load_dotenv

import company_directory
from apply_link_resolver import clean_url, is_aggregator, job_id_from_url, normalize_job_id, plausible_id

API_URL = 'https://api.firecrawl.dev/v2'
PORTAL_PREFIX = 'portal-'
DEFAULT_MAX_CREDITS = 150
POLL_SECS = 5
TIMEOUT_SECS = 15 * 60

JOBS_SCHEMA = {
    'type': 'object',
    'properties': {
        'careers_site': {'type': 'string', 'description': "URL of the company's own careers/jobs portal"},
        'jobs': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'job_title': {'type': 'string'},
                    'job_url': {'type': 'string', 'description': "Direct link to this job's page on the company's own careers site"},
                    'company_job_id': {'type': 'string', 'description': 'Requisition / job ID shown on the job page or in its URL'},
                    'location': {'type': 'string'},
                    'posted_date': {'type': 'string', 'description': 'Date posted as YYYY-MM-DD, empty if not shown'},
                },
                'required': ['job_title', 'job_url'],
            },
        },
    },
    'required': ['jobs'],
}


def is_portal_job(job):
    return str(job.get('linkedin_job_id', '')).startswith(PORTAL_PREFIX)


def _slug(value):
    return re.sub(r'[^a-z0-9]+', '-', str(value).lower()).strip('-')


def _headers():
    load_dotenv()
    key = os.getenv('FIRECRAWL_API_KEY')
    if not key:
        raise RuntimeError('FIRECRAWL_API_KEY not found in .env')
    return {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}


def _prompt(company, roles):
    since = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    return (
        f"Go to {company}'s own official careers / jobs portal (not LinkedIn, Naukri, Indeed, Glassdoor "
        f"or any other job board). Use the portal's search and location filters to find open jobs "
        f"located in India (any city, or remote India) that match any of these roles: {'; '.join(roles)}. "
        f"Include close title variants (e.g. Senior / Staff / Lead versions). Skip jobs posted before {since} "
        f"when the posting date is shown. For each job give its title, the direct link to the job's page "
        f"on the company's careers site, the requisition / job ID, location and posting date. "
        f"Return an empty jobs list if there are none - don't invent jobs."
    )


def run_agent(company, roles, max_credits=DEFAULT_MAX_CREDITS):
    """Start an agent run for one company and wait for it. Returns (jobs, credits used)."""
    resp = requests.post(f'{API_URL}/agent', headers=_headers(), timeout=60, json={
        'prompt': _prompt(company, roles), 'schema': JOBS_SCHEMA,
        'maxCredits': max_credits, 'effort': 'low',
    })
    resp.raise_for_status()
    job_id = resp.json()['id']

    deadline = time.time() + TIMEOUT_SECS
    while time.time() < deadline:
        time.sleep(POLL_SECS)
        resp = requests.get(f'{API_URL}/agent/{job_id}', headers=_headers(), timeout=60)
        resp.raise_for_status()
        result = resp.json()
        if result.get('status') == 'completed':
            return (result.get('data') or {}).get('jobs', []), result.get('creditsUsed', 0)
        if result.get('status') == 'failed':
            partial = result.get('partial') or {}
            if result.get('stopReason') == 'credit_limit_reached' and isinstance(partial, dict):
                print(f"   ⚠️  Hit the {max_credits}-credit cap; keeping the jobs found so far")
                return partial.get('jobs', []), result.get('creditsUsed', 0)
            raise RuntimeError(result.get('error') or result.get('message') or 'agent run failed')
    raise RuntimeError(f'agent run {job_id} still running after {TIMEOUT_SECS // 60} min')


def _to_rows(company, raw_jobs, role_label):
    """Agent output -> searched_jobs.csv rows. Drops job-board links and jobs without a job ID."""
    company_id = company_directory.id_for(company) or ''
    rows, skipped = [], 0
    for j in raw_jobs:
        url = clean_url(j.get('job_url') or '')
        if not url.startswith('http') or is_aggregator(url) or 'linkedin.com' in url:
            skipped += 1
            continue
        job_id = normalize_job_id(j.get('company_job_id') or '')
        if not plausible_id(job_id):
            job_id = job_id_from_url(url) or ''
        if not plausible_id(job_id):
            skipped += 1
            continue
        rows.append({
            'linkedin_job_id': f'{PORTAL_PREFIX}{_slug(company)}-{_slug(job_id)}',
            'linkedin_link': '',
            'company_career_url': url,
            'company_job_id': job_id,
            'job_title': (j.get('job_title') or 'N/A').strip(),
            'company': company,
            'location': (j.get('location') or 'India').strip(),
            'posted_date': (j.get('posted_date') or 'N/A').strip(),
            'search_role': role_label,
            'apply_status': 'OK',
            'linkedin_company_id': company_id,
        })
    if skipped:
        print(f"   Skipped {skipped} jobs (job-board link or no job ID)")
    return rows


def search_portals(companies, roles=None, max_credits=DEFAULT_MAX_CREDITS, should_stop=lambda: False):
    """Search each company's careers portal and save new jobs to searched_jobs.csv."""
    from linkedin_scraper import LinkedInJobScraper
    scraper = LinkedInJobScraper()
    roles = roles or scraper._read_job_roles()
    role_label = roles[0] if len(roles) == 1 else ', '.join(roles)
    total_credits, all_rows = 0, []
    for company in companies:
        if should_stop():
            print("⏹️  Stop requested.")
            break
        print(f"\n🌐 Searching {company}'s careers portal for: {'; '.join(roles)} (cap {max_credits} credits)")
        try:
            raw, credits = run_agent(company, roles, max_credits)
        except (requests.RequestException, RuntimeError) as e:
            print(f"   ❌ {company}: {e}")
            continue
        total_credits += credits
        rows = _to_rows(company, raw, role_label)
        print(f"   Found {len(rows)} jobs ({credits} credits)")
        for r in rows:
            print(f"   • {r['job_title']} — {r['location']} [{r['company_job_id']}]")
        all_rows.extend(rows)

    print(f"\n💳 Firecrawl credits used: {total_credits}")
    if not all_rows:
        print("No portal jobs found")
        return pd.DataFrame()
    df = pd.DataFrame(all_rows).drop_duplicates('linkedin_job_id').reset_index(drop=True)
    df.insert(0, 'serial_number', range(1, len(df) + 1))
    scraper._save_jobs(df)
    return df


def fetch_description(url):
    """Job description from the portal page (1 Firecrawl scrape credit). 'N/A' if it can't be read."""
    try:
        resp = requests.post(f'{API_URL}/scrape', headers=_headers(), timeout=120,
                             json={'url': url, 'formats': ['markdown'], 'onlyMainContent': True})
        resp.raise_for_status()
        return (resp.json().get('data') or {}).get('markdown') or 'N/A'
    except (requests.RequestException, RuntimeError) as e:
        print(f"Warning: Could not fetch job description from {url}: {e}")
        return 'N/A'


if __name__ == '__main__':
    p = argparse.ArgumentParser(description="Search companies' own careers portals with Firecrawl's AI agent")
    p.add_argument('--company', action='append', required=True)
    p.add_argument('--role', action='append')
    p.add_argument('--max-credits', type=int, default=DEFAULT_MAX_CREDITS)
    a = p.parse_args()
    search_portals(a.company, a.role, a.max_credits)
