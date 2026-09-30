import argparse
from linkedin_scraper import LinkedInJobScraper
from resume_tailor import ResumeTailor


def main():
    parser = argparse.ArgumentParser(description='LinkedIn Job Search Agent')
    parser.add_argument('command', choices=['search', 'tailor_resume'], help='Command to execute')
    parser.add_argument('serial_number', type=int, nargs='?', help='Serial number from searched jobs CSV (for tailor_resume)')
    parser.add_argument('--job_role', type=str, help='Job role to search for')
    parser.add_argument('--company', type=str, help='Company name to filter')

    args = parser.parse_args()

    if args.command == 'search':
        agent = LinkedInJobScraper()
        df = agent.search_jobs(job_role=args.job_role, company=args.company)
        if not df.empty:
            print(f"\n{'='*120}")
            print(f"{'SEARCH RESULTS (External Apply Only)':^120}")
            print(f"{'='*120}")
            # Show job details with company URL truncated for display
            display_df = df[['serial_number', 'job_title', 'company', 'location']].copy()
            print(display_df.to_string(index=False))
            print(f"{'='*120}")
            print(f"Total jobs found: {len(df)}")
            print(f"Note: Easy Apply jobs excluded. Company career URLs will be fetched when you run tailor_resume.")
            print(f"{'='*120}\n")

    elif args.command == 'tailor_resume':
        if not args.serial_number:
            print("Error: serial_number is required for tailor_resume command")
            print("Usage: python main.py tailor_resume <serial_number>")
            return

        tailor = ResumeTailor()
        tailor.tailor_resume(args.serial_number)


if __name__ == '__main__':
    main()
