import os
import pandas as pd
import requests
from datetime import datetime, timedelta
from typing import List, Optional
from bs4 import BeautifulSoup
import time


class LinkedInJobScraper:
    """Scraper for LinkedIn public job search (no authentication needed)."""

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

    def search_jobs(self, job_role: Optional[str] = None, company: Optional[str] = None) -> pd.DataFrame:
        """Search for jobs on LinkedIn filtered by past week and location India."""
        all_jobs = []
        job_roles = [job_role] if job_role else self._read_job_roles()

        # Calculate seconds since epoch for past week
        past_week_seconds = int((datetime.now() - timedelta(days=7)).timestamp())

        for role in job_roles:
            print(f"\nSearching: {role} in India" + (f" at {company}" if company else ""))

            try:
                params = {
                    'keywords': role,
                    'location': 'India',
                    'f_TPR': f'r{past_week_seconds}',  # Past week filter
                    'start': 0
                }

                if company:
                    params['f_C'] = company

                response = self.session.get(self.base_url, params=params)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, 'html.parser')
                job_cards = soup.find_all('li')

                for card in job_cards:
                    try:
                        # Extract job ID from data attribute or link
                        job_link_tag = card.find('a', class_='base-card__full-link')
                        if not job_link_tag:
                            continue

                        job_url = job_link_tag.get('href', '')
                        job_id = job_url.split('/')[-1].split('?')[0] if job_url else 'N/A'

                        # Extract job details
                        title_tag = card.find('h3', class_='base-search-card__title')
                        job_title = title_tag.text.strip() if title_tag else 'N/A'

                        company_tag = card.find('h4', class_='base-search-card__subtitle')
                        company_name = company_tag.text.strip() if company_tag else 'N/A'

                        location_tag = card.find('span', class_='job-search-card__location')
                        location = location_tag.text.strip() if location_tag else 'N/A'

                        # Extract posted date
                        time_tag = card.find('time')
                        posted_date = time_tag.get('datetime', 'N/A') if time_tag else 'N/A'

                        all_jobs.append({
                            'linkedin_job_id': job_id,
                            'linkedin_link': f"https://www.linkedin.com/jobs/view/{job_id}",
                            'company_website_link': 'N/A',  # Not available in public search
                            'job_title': job_title,
                            'company': company_name,
                            'location': location,
                            'posted_date': posted_date,
                            'search_role': role
                        })

                    except Exception as e:
                        print(f"Error parsing job card: {str(e)}")
                        continue

                print(f"Found {len(job_cards)} jobs")
                time.sleep(2)  # Be respectful with requests

            except Exception as e:
                print(f"Error searching for {role}: {str(e)}")
                continue

        if not all_jobs:
            print("No jobs found")
            return pd.DataFrame()

        df = pd.DataFrame(all_jobs)
        df.insert(0, 'serial_number', range(1, len(df) + 1))
        self._save_jobs(df)
        return df

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
