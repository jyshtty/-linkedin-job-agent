import argparse
from linkedin_scraper import LinkedInJobScraper


def main():
    parser = argparse.ArgumentParser(description='LinkedIn Job Search Agent')
    parser.add_argument('command', choices=['search'], help='Command to execute')
    parser.add_argument('--job_role', type=str, help='Job role to search for')
    parser.add_argument('--company', type=str, help='Company name to filter')

    args = parser.parse_args()

    agent = LinkedInJobScraper()

    if args.command == 'search':
        df = agent.search_jobs(job_role=args.job_role, company=args.company)
        if not df.empty:
            print(f"\n{'='*100}")
            print(f"{'SEARCH RESULTS':^100}")
            print(f"{'='*100}")
            print(df[['serial_number', 'linkedin_job_id', 'company_website_link']].to_string(index=False))
            print(f"{'='*100}\n")


if __name__ == '__main__':
    main()
