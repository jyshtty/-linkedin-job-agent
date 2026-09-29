import os
import pickle
import pandas as pd
from linkedin_api import Linkedin
from datetime import datetime, timedelta
from typing import List, Optional
from dotenv import load_dotenv


class LinkedInJobAgent:
    """Agent for searching LinkedIn jobs and managing job listings."""

    def __init__(self):
        load_dotenv()
        self.email = os.getenv('LINKEDIN_EMAIL')
        self.password = os.getenv('LINKEDIN_PASSWORD')
        self.cookies_path = '.linkedin_cookies'

        if not self.email or not self.password:
            raise ValueError("LinkedIn credentials not found. Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env file")

        # Try to use saved cookies first
        if os.path.exists(self.cookies_path):
            print("Using saved LinkedIn session...")
            with open(self.cookies_path, 'rb') as f:
                cookies = pickle.load(f)
            self.api = Linkedin('', '', cookies=cookies)
        else:
            print("Authenticating with LinkedIn (this may trigger security checks)...")
            print("If authentication fails, you may need to:")
            print("1. Log in to LinkedIn in a browser")
            print("2. Export cookies manually")
            try:
                self.api = Linkedin(self.email, self.password)
                # Save cookies for future use
                with open(self.cookies_path, 'wb') as f:
                    pickle.dump(self.api.client.session.cookies, f)
                print("Session saved successfully!")
            except Exception as e:
                raise Exception(f"LinkedIn authentication failed: {str(e)}")

        self.searched_jobs_file = 'searched_job_list/searched_jobs.csv'
        os.makedirs('searched_job_list', exist_ok=True)

    def _read_job_roles(self) -> List[str]:
        """Read job roles from the interested_job_role file."""
        with open('interested_job_role/job_role.txt', 'r') as f:
            return [line.strip() for line in f if line.strip()]

    def search_jobs(self, job_role: Optional[str] = None, company: Optional[str] = None) -> pd.DataFrame:
        """Search for jobs on LinkedIn filtered by past week."""
        all_jobs = []
        job_roles = [job_role] if job_role else self._read_job_roles()

        # Past week timestamp
        past_week_timestamp = int((datetime.now() - timedelta(days=7)).timestamp() * 1000)

        for role in job_roles:
            print(f"\nSearching: {role}" + (f" at {company}" if company else ""))

            try:
                search_params = {
                    'keywords': role,
                    'listed_at': past_week_timestamp,
                    'limit': 50
                }
                if company:
                    search_params['companies'] = [company]

                jobs = self.api.search_jobs(**search_params)

                for job in jobs:
                    job_id = job.get('dashEntityUrn', '').split(':')[-1]
                    all_jobs.append({
                        'linkedin_job_id': job_id,
                        'linkedin_link': f"https://www.linkedin.com/jobs/view/{job_id}",
                        'company_website_link': job.get('applyUrl', 'N/A'),
                        'job_title': job.get('title', 'N/A'),
                        'company': job.get('companyName', 'N/A'),
                        'location': job.get('location', 'N/A'),
                        'posted_date': job.get('listedAt', 'N/A'),
                        'search_role': role
                    })

                print(f"Found {len(jobs)} jobs")
            except Exception as e:
                print(f"Error: {str(e)}")

        if not all_jobs:
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
