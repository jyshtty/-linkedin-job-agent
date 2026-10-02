"""
LinkedIn Referral Agent
Finds employees at target company and generates personalized referral messages
"""
import os
import pandas as pd
from typing import List, Dict, Optional
from dotenv import load_dotenv
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException


class ReferralAgent:
    """Agent for finding company employees and generating referral requests"""

    def __init__(self):
        load_dotenv()

        self.searched_jobs_file = 'searched_job_list/searched_jobs.csv'
        self.referral_template_file = 'referral_template.txt'
        self.referral_config_file = 'referral_config.txt'
        self.referral_log_file = 'referral_log.csv'

        # Load LinkedIn credentials from .env
        self.linkedin_email = os.getenv('LINKEDIN_EMAIL')
        self.linkedin_password = os.getenv('LINKEDIN_PASSWORD')

        # Create default config if doesn't exist
        if not os.path.exists(self.referral_config_file):
            self._create_default_config()

        # Create default template if doesn't exist
        if not os.path.exists(self.referral_template_file):
            self._create_default_template()

    def _create_default_config(self):
        """Create default referral configuration"""
        with open(self.referral_config_file, 'w') as f:
            f.write("# Referral Agent Configuration\n")
            f.write("# Number of referral requests to send per job\n")
            f.write("referrals_per_job=2\n")
            f.write("\n")
            f.write("# Your professional summary (for template)\n")
            f.write("your_title=Senior Software Engineer\n")
            f.write("your_expertise=DSA and System Design\n")

    def _create_default_template(self):
        """Create default referral message template"""
        template = """Hi {name},

I'm a {your_title} with strong expertise in {your_expertise}.

I've been following {company} and would love to be part of the team — would you be open to referring me for the {job_title} position?

Job link: {job_link}

Even a referral submission makes a huge difference — really appreciate any help!

Best regards"""

        with open(self.referral_template_file, 'w') as f:
            f.write(template)

    def _load_config(self) -> Dict:
        """Load referral configuration"""
        config = {
            'referrals_per_job': 2,
            'your_title': 'Senior Software Engineer',
            'your_expertise': 'DSA and System Design'
        }

        if os.path.exists(self.referral_config_file):
            with open(self.referral_config_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if '=' in line:
                            key, value = line.split('=', 1)
                            if key == 'referrals_per_job':
                                config[key] = int(value)
                            else:
                                config[key] = value

        return config

    def _load_template(self) -> str:
        """Load referral message template"""
        with open(self.referral_template_file, 'r') as f:
            return f.read()

    def _get_job_by_serial(self, serial_number: int) -> Optional[Dict]:
        """Get job details by serial number from CSV"""
        if not os.path.exists(self.searched_jobs_file):
            print("❌ No searched jobs found. Run search command first.")
            return None

        df = pd.read_csv(self.searched_jobs_file)
        job_row = df[df['serial_number'] == serial_number]

        if job_row.empty:
            print(f"❌ No job found with serial number {serial_number}")
            return None

        return job_row.iloc[0].to_dict()

    def _auto_login(self, driver, wait) -> bool:
        """Auto-login to LinkedIn using credentials from .env"""
        try:
            if not self.linkedin_email or not self.linkedin_password:
                print("⚠️  No LinkedIn credentials in .env file")
                return False

            print("🔑 Auto-login enabled (using credentials from .env)")

            # Navigate to LinkedIn login page
            driver.get("https://www.linkedin.com/login")
            time.sleep(3)

            # Find email field by type (LinkedIn uses random IDs)
            try:
                email_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email']"))
                )
                email_field.clear()
                email_field.send_keys(self.linkedin_email)
                print("   ✓ Email entered")
            except:
                print("   ✗ Could not find email field")
                return False

            # Find password field by type (LinkedIn uses random IDs)
            try:
                password_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='password']"))
                )
                password_field.clear()
                password_field.send_keys(self.linkedin_password)
                print("   ✓ Password entered")
            except:
                print("   ✗ Could not find password field")
                return False

            # Find and click login button
            try:
                login_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
                )
                login_button.click()
                print("   ✓ Login button clicked")
            except:
                print("   ✗ Could not click login button")
                return False

            print("⏳ Logging in...")
            time.sleep(8)  # Wait longer for login to complete

            # Check if login successful - look for navigation bar or feed
            current_url = driver.current_url
            if "feed" in current_url or "mynetwork" in current_url or "linkedin.com/in/" in current_url:
                print("✅ Auto-login successful!\n")
                return True
            elif "checkpoint" in current_url or "challenge" in current_url:
                print("⚠️  LinkedIn security challenge detected - manual verification needed")
                print("   Please complete the security check in the browser...")
                time.sleep(30)  # Give user time to complete challenge
                return True  # Continue anyway
            else:
                print(f"⚠️  Unexpected page after login: {current_url}")
                return False

        except Exception as e:
            print(f"⚠️  Auto-login exception: {str(e)[:100]}")
            return False

    def find_company_employees(self, company: str, limit: int = 10) -> List[Dict]:
        """
        Find employees at target company on LinkedIn
        Returns list of employee profiles
        """
        print(f"\n🔍 Searching for employees at {company}...")
        print(f"   Fetching up to {limit} profiles...")

        # Initialize Selenium
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")

        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            wait = WebDriverWait(driver, 30)

            # Try auto-login first
            auto_login_success = self._auto_login(driver, wait)

            if not auto_login_success:
                # Fallback to manual login
                # Navigate to LinkedIn company search
                search_url = f"https://www.linkedin.com/search/results/people/?keywords={company.replace(' ', '%20')}&origin=SWITCH_SEARCH_VERTICAL"
                driver.get(search_url)

                print("\n" + "="*80)
                print("🔐 LINKEDIN LOGIN REQUIRED")
                print("="*80)
                print("\nPlease log in to LinkedIn in the browser window.")
                print("The script will continue automatically after login...")
                print("\nWaiting for login... (timeout: 120 seconds)")
                print("="*80 + "\n")

                # Wait for login
                try:
                    wait = WebDriverWait(driver, 120)
                    wait.until(
                        EC.presence_of_element_located((By.CLASS_NAME, "search-results-container"))
                    )
                    print("✅ Login successful!\n")
                except TimeoutException:
                    print("❌ Login timeout. Please try again.")
                    driver.quit()
                    return []
            else:
                # Navigate to search after successful auto-login
                search_url = f"https://www.linkedin.com/search/results/people/?keywords={company.replace(' ', '%20')}&origin=SWITCH_SEARCH_VERTICAL"
                driver.get(search_url)

            time.sleep(3)  # Let page load

            # Extract employee profiles
            employees = []
            try:
                # Find all profile cards
                profile_cards = driver.find_elements(By.CSS_SELECTOR, ".entity-result__item")

                for i, card in enumerate(profile_cards[:limit]):
                    try:
                        # Extract name
                        name_elem = card.find_element(By.CSS_SELECTOR, ".entity-result__title-text a")
                        name = name_elem.text.strip().split('\n')[0]

                        # Extract profile link
                        profile_link = name_elem.get_attribute('href')

                        # Extract title/position
                        try:
                            title_elem = card.find_element(By.CSS_SELECTOR, ".entity-result__primary-subtitle")
                            title = title_elem.text.strip()
                        except:
                            title = "N/A"

                        employees.append({
                            'name': name,
                            'title': title,
                            'profile_link': profile_link
                        })

                        print(f"   ✓ Found: {name} - {title}")

                    except Exception as e:
                        continue

                print(f"\n✅ Found {len(employees)} employees at {company}")

            except Exception as e:
                print(f"❌ Error extracting profiles: {e}")

            driver.quit()
            return employees

        except Exception as e:
            print(f"❌ Error initializing browser: {e}")
            return []

    def generate_referral_message(self, employee: Dict, job: Dict, config: Dict) -> str:
        """Generate personalized referral message"""
        template = self._load_template()

        # Get first name from full name
        first_name = employee['name'].split()[0]

        message = template.format(
            name=first_name,
            your_title=config['your_title'],
            your_expertise=config['your_expertise'],
            company=job['company'],
            job_title=job['job_title'],
            job_link=job['linkedin_link']
        )

        return message

    def log_referral(self, job: Dict, employee: Dict, sent: bool = False):
        """Log referral request to CSV"""
        import csv
        from datetime import datetime

        file_exists = os.path.exists(self.referral_log_file)

        with open(self.referral_log_file, 'a', newline='') as f:
            writer = csv.writer(f)

            if not file_exists:
                writer.writerow(['timestamp', 'job_serial', 'company', 'job_title',
                               'employee_name', 'employee_title', 'profile_link', 'sent'])

            writer.writerow([
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                job['serial_number'],
                job['company'],
                job['job_title'],
                employee['name'],
                employee['title'],
                employee['profile_link'],
                'Yes' if sent else 'No'
            ])

    def request_referrals(self, serial_number: int):
        """Main function to request referrals for a job"""
        print(f"\n{'='*80}")
        print(f"REFERRAL AGENT - JOB #{serial_number}")
        print(f"{'='*80}\n")

        # Load configuration
        config = self._load_config()
        num_referrals = config['referrals_per_job']

        # Get job details
        job = self._get_job_by_serial(serial_number)
        if not job:
            return

        print(f"Job: {job['job_title']}")
        print(f"Company: {job['company']}")
        print(f"Location: {job['location']}")
        print(f"LinkedIn Link: {job['linkedin_link']}")
        print(f"\nTarget: {num_referrals} referral request(s)\n")

        # Find employees at company
        employees = self.find_company_employees(job['company'], limit=num_referrals * 2)

        if not employees:
            print("❌ No employees found. Cannot send referral requests.")
            return

        # Generate and display referral messages
        print(f"\n{'='*80}")
        print(f"REFERRAL MESSAGES (Top {min(num_referrals, len(employees))} contacts)")
        print(f"{'='*80}\n")

        for i, employee in enumerate(employees[:num_referrals]):
            message = self.generate_referral_message(employee, job, config)

            print(f"\n{'─'*80}")
            print(f"REFERRAL #{i+1}")
            print(f"{'─'*80}")
            print(f"To: {employee['name']}")
            print(f"Title: {employee['title']}")
            print(f"Profile: {employee['profile_link']}")
            print(f"\nMessage:")
            print(f"{'─'*80}")
            print(message)
            print(f"{'─'*80}\n")

            # Log referral
            self.log_referral(job, employee, sent=False)

        # Display remaining contacts
        if len(employees) > num_referrals:
            print(f"\n{'='*80}")
            print(f"BACKUP CONTACTS ({len(employees) - num_referrals} additional)")
            print(f"{'='*80}\n")

            for i, employee in enumerate(employees[num_referrals:]):
                print(f"{i+1}. {employee['name']} - {employee['title']}")
                print(f"   {employee['profile_link']}")

        print(f"\n{'='*80}")
        print(f"✅ REFERRAL REQUESTS PREPARED!")
        print(f"{'='*80}")
        print(f"\n📋 Next Steps:")
        print(f"   1. Copy the messages above")
        print(f"   2. Visit each profile link")
        print(f"   3. Send connection request with the message")
        print(f"   4. Or message directly if already connected")
        print(f"\n💾 All referrals logged to: {self.referral_log_file}")
        print(f"{'='*80}\n")


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python referral_agent.py <serial_number>")
        print("\nExample:")
        print("  python referral_agent.py 1")
        print("\nConfiguration:")
        print("  - Edit 'referral_config.txt' to set number of referrals")
        print("  - Edit 'referral_template.txt' to customize message template")
        return

    serial_number = int(sys.argv[1])

    agent = ReferralAgent()
    agent.request_referrals(serial_number)


if __name__ == '__main__':
    main()
