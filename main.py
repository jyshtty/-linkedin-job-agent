import argparse
from linkedin_scraper import LinkedInJobScraper
from resume_tailor import ResumeTailor
import referral_complete


def main():
    parser = argparse.ArgumentParser(description='LinkedIn Job Search Agent')
    parser.add_argument('command', choices=['search', 'tailor_resume', 'request_referral'], help='Command to execute')
    parser.add_argument('serial_number', type=int, nargs='?', help='Serial number from searched jobs CSV (for tailor_resume and request_referral)')
    parser.add_argument('--job_role', type=str, help='Job role to search for')
    parser.add_argument('--company', type=str, help='Company name to filter')
    parser.add_argument('--dry-run', action='store_true', help='request_referral: type messages but do not send')

    args = parser.parse_args()

    if args.command == 'search':
        agent = LinkedInJobScraper()
        df = agent.search_jobs(job_role=args.job_role, company=args.company)
        if not df.empty:
            print(f"\n{'='*120}")
            print(f"{'SEARCH RESULTS (Company Portal Jobs Only)':^120}")
            print(f"{'='*120}")
            # Show job details with company URL truncated for display
            display_df = df[['serial_number', 'job_title', 'company', 'location']].copy()
            print(display_df.to_string(index=False))
            print(f"{'='*120}")
            print(f"Total jobs found: {len(df)}")
            print(f"Note: Easy Apply, job-board and no-job-ID jobs excluded.")
            print(f"{'='*120}\n")

    elif args.command == 'tailor_resume':
        if not args.serial_number:
            print("Error: serial_number is required for tailor_resume command")
            print("Usage: python main.py tailor_resume <serial_number>")
            return

        tailor = ResumeTailor()
        tailor.tailor_resume(args.serial_number)

    elif args.command == 'request_referral':
        if not args.serial_number:
            print("Error: serial_number is required for request_referral command")
            print("Usage: python main.py request_referral <serial_number>")
            return

        referral_complete.run(args.serial_number, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
