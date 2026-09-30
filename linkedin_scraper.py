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

    def _get_company_apply_url(self, job_id: str) -> str:
        """
        Get the company career page URL for a job.
        Returns 'EASY_APPLY' if it's an Easy Apply job.
        Returns 'N/A' if no external apply link found.
        """
        try:
            job_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
            response = self.session.get(job_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Check if it's Easy Apply
            easy_apply_button = soup.find('button', string=lambda text: text and 'easy apply' in text.lower())
            if easy_apply_button:
                return 'EASY_APPLY'

            # Look for external apply button/link
            apply_button = soup.find('a', class_='apply-button')
            if not apply_button:
                apply_button = soup.find('a', {'data-tracking-control-name': 'public_jobs_apply-link-offsite'})
            if not apply_button:
                # Look for any link with "apply" text
                apply_button = soup.find('a', string=lambda text: text and 'apply' in text.lower() and 'easy' not in text.lower())

            if apply_button:
                company_url = apply_button.get('href', 'N/A')
                # Filter out LinkedIn Easy Apply URLs
                if 'linkedin.com/job-apply' in company_url or 'linkedin.com/jobs/apply' in company_url:
                    return 'EASY_APPLY'
                return company_url

            return 'N/A'

        except Exception as e:
            print(f"   Error checking apply type for job {job_id}: {str(e)}")
            return 'N/A'

    def fetch_job_details(self, job_id: str) -> dict:
        """
        Fetch full job details including company apply link and job description.
        This is a public method to be called on-demand (e.g., by tailor_resume).
        """
        try:
            # Extract numeric job ID from slug format (e.g., "lead-engineer-at-target-4469431197" -> "4469431197")
            import re
            numeric_id_match = re.search(r'(\d+)$', job_id)
            numeric_job_id = numeric_id_match.group(1) if numeric_id_match else job_id

            job_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{numeric_job_id}"
            response = self.session.get(job_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract company apply link (external career page URL)
            apply_link_tag = soup.find('a', class_='apply-button')
            if not apply_link_tag:
                apply_link_tag = soup.find('a', {'data-tracking-control-name': 'public_jobs_apply-link-offsite'})
            if not apply_link_tag:
                # Look for any external apply link
                apply_link_tag = soup.find('a', string=lambda text: text and 'apply' in text.lower() and 'easy' not in text.lower())

            company_apply_link = apply_link_tag.get('href', 'N/A') if apply_link_tag else 'N/A'

            # Skip if it's an Easy Apply link
            if company_apply_link != 'N/A' and ('linkedin.com/job-apply' in company_apply_link or 'linkedin.com/jobs/apply' in company_apply_link):
                company_apply_link = 'EASY_APPLY'

            # Extract company job ID from apply link if available
            company_job_id = 'N/A'
            if company_apply_link != 'N/A':
                # Try to extract job ID from URL patterns
                import re
                # Common patterns: /jobs/12345, jobId=12345, job-12345, etc.
                patterns = [
                    r'/jobs?[/-](\w+)',
                    r'jobId[=:](\w+)',
                    r'job[_-]id[=:](\w+)',
                    r'posting[_-]?id[=:](\w+)',
                    r'requisition[_-]?id[=:](\w+)'
                ]
                for pattern in patterns:
                    match = re.search(pattern, company_apply_link, re.IGNORECASE)
                    if match:
                        company_job_id = match.group(1)
                        break

            # Extract job description
            desc_tag = soup.find('div', class_='description')
            if not desc_tag:
                desc_tag = soup.find('div', class_='show-more-less-html__markup')

            job_description = desc_tag.get_text(strip=True) if desc_tag else 'N/A'

            return {
                'company_apply_link': company_apply_link,
                'company_job_id': company_job_id,
                'job_description': job_description
            }

        except Exception as e:
            print(f"Warning: Could not fetch full job details for {job_id}: {str(e)}")
            print("Proceeding with basic job information...")
            return {
                'company_apply_link': 'N/A',
                'company_job_id': 'N/A',
                'job_description': 'N/A'
            }

    def search_jobs(self, job_role: Optional[str] = None, company: Optional[str] = None) -> pd.DataFrame:
        """Search for jobs on LinkedIn filtered by past week and location India."""
        all_jobs = []
        job_roles = [job_role] if job_role else self._read_job_roles()

        # Calculate seconds since epoch for past week
        past_week_seconds = int((datetime.now() - timedelta(days=7)).timestamp())

        for role in job_roles:
            print(f"\nSearching: {role} in India" + (f" at {company}" if company else ""))

            try:
                # When company is specified, include it in keywords instead of using f_C filter
                # LinkedIn's f_C requires company ID which we don't have
                search_keywords = f"{role} {company}" if company else role

                params = {
                    'keywords': search_keywords,
                    'location': 'India',
                    'f_TPR': f'r{past_week_seconds}',  # Past week filter
                    'f_AL': 'true',  # Filter: Show only jobs with external apply (not Easy Apply)
                    'start': 0
                }

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
                        # Extract numeric job ID from URL (e.g., from /jobs/view/4331060877)
                        import re
                        job_id_match = re.search(r'/(\d+)', job_url)
                        job_id = job_id_match.group(1) if job_id_match else job_url.split('/')[-1].split('?')[0]

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

                        # Store company_career_url and company_job_id as placeholders - will be fetched on-demand
                        all_jobs.append({
                            'linkedin_job_id': job_id,
                            'linkedin_link': f"https://www.linkedin.com/jobs/view/{job_id}",
                            'company_career_url': 'TBD',  # To be determined when tailoring resume
                            'company_job_id': 'TBD',  # To be determined when tailoring resume
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
