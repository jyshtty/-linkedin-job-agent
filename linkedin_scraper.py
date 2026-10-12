import os
import pandas as pd
import requests
from typing import List, Optional
from bs4 import BeautifulSoup
import time

import company_directory
from apply_link_resolver import LinkedInSession, numeric_job_id, resolve


class LinkedInJobScraper:
    """Scraper for LinkedIn public job search (no authentication needed)."""

    COMPANIES_PER_SEARCH = 25  # company IDs per f_C filter
    MAX_PAGES = 4  # 10 jobs per page

    def __init__(self):
        self.base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        self.searched_jobs_file = 'searched_job_list/searched_jobs.csv'
        os.makedirs('searched_job_list', exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def _read_job_roles(self) -> List[str]:
        """Read job roles from the interested_job_role file."""
        with open('interested_job_role/job_role.txt', 'r') as f:
            return [line.strip() for line in f if line.strip()]

    def fetch_job_details(self, job_id: str) -> dict:
        """
        Fetch full job details including company apply link and job description.
        This is a public method to be called on-demand (e.g., by tailor_resume).
        """
        link = resolve(job_id, LinkedInSession())

        job_description = 'N/A'
        try:
            job_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{numeric_job_id(job_id)}"
            response = self.session.get(job_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            desc_tag = soup.find('div', class_='description')
            if not desc_tag:
                desc_tag = soup.find('div', class_='show-more-less-html__markup')
            if desc_tag:
                job_description = desc_tag.get_text(strip=True)
        except Exception as e:
            print(f"Warning: Could not fetch job description for {job_id}: {str(e)}")

        if job_description == 'N/A' and link['description']:
            job_description = link['description']

        return {
            'apply_status': link['apply_status'],
            'company_apply_link': link['company_career_url'],
            'company_job_id': link['company_job_id'],
            'job_description': job_description
        }

    def _parse_job_cards(self, html: str, role: str) -> List[dict]:
        jobs = []
        soup = BeautifulSoup(html, 'html.parser')
        for card in soup.find_all('li'):
            try:
                job_link_tag = card.find('a', class_='base-card__full-link')
                if not job_link_tag:
                    continue

                job_url = job_link_tag.get('href', '')
                # Slug like "senior-engineer-at-atlassian-4469431197" (numeric ID at the end)
                job_id = job_url.split('?')[0].rstrip('/').split('/')[-1]

                title_tag = card.find('h3', class_='base-search-card__title')
                company_tag = card.find('h4', class_='base-search-card__subtitle')
                location_tag = card.find('span', class_='job-search-card__location')
                time_tag = card.find('time')

                jobs.append({
                    'linkedin_job_id': job_id,
                    'linkedin_link': f"https://www.linkedin.com/jobs/view/{job_id}",
                    'company_career_url': 'TBD',  # Filled in by _keep_company_portal_jobs
                    'company_job_id': 'TBD',
                    'job_title': title_tag.text.strip() if title_tag else 'N/A',
                    'company': company_tag.text.strip() if company_tag else 'N/A',
                    'location': location_tag.text.strip() if location_tag else 'N/A',
                    'posted_date': time_tag.get('datetime', 'N/A') if time_tag else 'N/A',
                    'search_role': role
                })
            except Exception as e:
                print(f"Error parsing job card: {str(e)}")
        return jobs

    def search_jobs(self, job_role: Optional[str] = None, company: Optional[str] = None) -> pd.DataFrame:
        """
        Search past-week jobs in India posted by the interested companies
        (every list in interested_companies/), or by one company with --company.
        """
        all_jobs = []
        job_roles = [job_role] if job_role else self._read_job_roles()

        if company:
            cid = company_directory.id_for(company)
            if not cid:
                print(f"❌ Couldn't find a LinkedIn company page for {company!r}")
                return pd.DataFrame()
            company_ids = [cid]
        else:
            company_ids = list(dict.fromkeys(company_directory.company_ids().values()))
        batches = [company_ids[i:i + self.COMPANIES_PER_SEARCH]
                   for i in range(0, len(company_ids), self.COMPANIES_PER_SEARCH)]

        for role in job_roles:
            print(f"\nSearching: {role} in India at " +
                  (company if company else f"{len(company_ids)} interested companies"))
            role_jobs = 0
            for batch in batches:
                for page in range(self.MAX_PAGES):
                    params = {
                        'keywords': role,
                        'location': 'India',
                        'f_TPR': 'r604800',  # Posted in the past week (seconds)
                        'f_C': ','.join(batch),  # Only these companies
                        'start': page * 10
                    }
                    try:
                        response = self.session.get(self.base_url, params=params)
                        if response.status_code == 429:
                            print("   Rate limited by LinkedIn, waiting 30s...")
                            time.sleep(30)
                            response = self.session.get(self.base_url, params=params)
                        response.raise_for_status()
                    except Exception as e:
                        print(f"   Error searching {role}: {str(e)}")
                        break

                    jobs = self._parse_job_cards(response.text, role)
                    all_jobs.extend(jobs)
                    role_jobs += len(jobs)
                    time.sleep(2)  # Be respectful with requests
                    if len(jobs) < 10:  # last page
                        break
            print(f"Found {role_jobs} jobs")

        if not all_jobs:
            print("No jobs found")
            return pd.DataFrame()

        df = self._keep_company_portal_jobs(pd.DataFrame(all_jobs), set(company_ids))
        if df.empty:
            print("No jobs with a company careers portal and job ID")
            return df
        df.insert(0, 'serial_number', range(1, len(df) + 1))
        self._save_jobs(df)
        return df

    def _keep_company_portal_jobs(self, df: pd.DataFrame, company_ids: set) -> pd.DataFrame:
        """
        Resolve each job's company careers URL + job ID and drop jobs that can't be
        used (Easy Apply, job boards, no company job ID, or posted by a company that
        isn't one we searched for). Jobs that couldn't be checked (Chrome not
        available) are kept as UNRESOLVED and checked again later.
        """
        df = df.drop_duplicates('linkedin_job_id').reset_index(drop=True)
        session = LinkedInSession()
        if not session.available:
            print("\n⚠️  Chrome with LinkedIn isn't open - company links not checked yet.")
            print("   Run `python apply_link_resolver.py` later to fill them in.")
            df['apply_status'] = 'UNRESOLVED'
            return df

        print(f"\n🔗 Checking company careers links for {len(df)} jobs...")
        for i, row in df.iterrows():
            r = resolve(row['linkedin_job_id'], session)
            for col in ('apply_status', 'company_career_url', 'company_job_id', 'linkedin_company_id'):
                df.at[i, col] = r[col]
            if r['linkedin_company_id'] and r['linkedin_company_id'] not in company_ids:
                df.at[i, 'apply_status'] = 'NOT_INTERESTED'
            time.sleep(0.4)

        counts = df['apply_status'].value_counts()
        skipped = counts.drop(['OK', 'UNRESOLVED'], errors='ignore')
        if not skipped.empty:
            print("   Skipped: " + ", ".join(f"{n} {status}" for status, n in skipped.items()))
        return df[df['apply_status'].isin(['OK', 'UNRESOLVED'])].reset_index(drop=True)

    def _save_jobs(self, df: pd.DataFrame):
        """Save jobs to CSV, avoiding duplicates."""
        if os.path.exists(self.searched_jobs_file):
            existing_df = pd.read_csv(self.searched_jobs_file)
            new_jobs = df[~df['linkedin_job_id'].isin(existing_df['linkedin_job_id'])]
            if not new_jobs.empty:
                combined_df = pd.concat([existing_df, new_jobs], ignore_index=True)
                combined_df['serial_number'] = range(1, len(combined_df) + 1)
                combined_df.to_csv(self.searched_jobs_file, index=False)
                print(f"\nAdded {len(new_jobs)} new jobs")
            else:
                print("\nNo new jobs (all already exist)")
        else:
            df.to_csv(self.searched_jobs_file, index=False)
            print(f"\nSaved {len(df)} jobs to CSV")
