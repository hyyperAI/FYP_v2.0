"""
backend/cli.py

CLI entry points for backend commands.
"""

import argparse
import sys
import httpx
import time
import json

from .scrape.engine import JobsScraper
from .analysis.engine import perform_analysis


def scrape_cli_entry_point() -> None:
    """CLI entry point for scraping jobs."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Scrape Upwork job listings for a given search query.")
    parser.add_argument(
        "action", type=str, choices=("scrape", "update"), default="scrape",
        help="Scrape new jobs, or update existing scraped data with any new job postings")
    parser.add_argument(
        "-q", '--search-query', type=str, required=True,
        help='The query to search for.')
    parser.add_argument(
        "-j", "--jobs-per-page", type=int, choices=[10, 20, 50], default=10,
        help="How many jobs should be displayed per page.")
    parser.add_argument(
        "-s", "--start-page", type=int, default=1,
        help="The page number to start searching from.")
    parser.add_argument(
        "-p", "--pages-to-scrape", type=int,
        help="How many pages to scrape. If not passed, scrape all the pages*"
             "(there's a limit, see the docs for more info).")
    parser.add_argument(
        "-o", "--output", type=str, default='',
        help="Where to save the scraped data.")
    parser.add_argument(
        "-r", "--retries", type=int, default=3,
        help="Number of retries when encountering a Captcha before failing.")
    parser.add_argument(
        "--headless", action="store_true", default=False,
        help="Whether to enable headless mode (slower and more detectable).")
    parser.add_argument(
        "-w", "--workers", type=int, default=1,
        help="How many webdriver instances to spin up for scraping.")
    parser.add_argument(
        "-f", "--fast", action="store_true", default=False,
        help="Whether to use the fast scraping method. It can be 10 to 50x faster "
             "but leaves out all client information and number of proposals.")
    args = parser.parse_args()
    action = args.action
    search_query = args.search_query
    jobs_per_page = args.jobs_per_page
    start_page = args.start_page
    pages_to_scrape = args.pages_to_scrape
    save_path = args.output
    retries = args.retries
    headless = args.headless
    workers = args.workers
    fast = args.fast
    jobs_scraper = JobsScraper(
        search_query, jobs_per_page, start_page, pages_to_scrape, save_path, retries, headless, workers, fast)
    jobs_scraper.scrape_jobs() if action == "scrape" else jobs_scraper.update_existing()


def analyze_cli_entry_point() -> None:
    """CLI entry point for analyzing jobs."""
    import seaborn as sns
    sns.set(style='whitegrid', palette="deep", font_scale=1.1, rc={"figure.figsize": [10, 6]})
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="Perform data analysis on the data collected by scraping upwork and plot the data.")
    parser.add_argument(
        "dataset_path", type=str, help="The path to the scraped data.")
    parser.add_argument(
        "-o", "--save-dir", type=str, help="The directory to save the plots to. If not passed, don't save the plots.")
    parser.add_argument(
        "-s", "--show", action="store_true", help="Whether to show the plots. Off by default.")
    args = parser.parse_args()
    scraped_data_path = args.dataset_path
    save_directory = args.save_dir
    show = args.show
    perform_analysis(scraped_data_path, save_directory, show)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Upwork Analysis Backend CLI",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Scrape subcommand
    scrape_parser = subparsers.add_parser('scrape', help='Scrape jobs from Upwork')
    scrape_parser.add_argument(
        "-q", '--search-query', type=str, required=True,
        help='The query to search for.')
    scrape_parser.add_argument(
        "-j", "--jobs-per-page", type=int, choices=[10, 20, 50], default=10,
        help="How many jobs should be displayed per page.")
    scrape_parser.add_argument(
        "-p", "--pages-to-scrape", type=int, default=10,
        help="How many pages to scrape.")
    scrape_parser.add_argument(
        "-o", "--output", type=str, default='',
        help="Where to save the scraped data.")
    scrape_parser.add_argument(
        "--headless", action="store_true", default=False,
        help="Whether to enable headless mode.")
    scrape_parser.add_argument(
        "-f", "--fast", action="store_true", default=False,
        help="Whether to use the fast scraping method.")
    scrape_parser.add_argument(
        "--api-url", type=str, default="http://localhost:8000",
        help="API base URL for scraping service.")

    # Analyze subcommand
    analyze_parser = subparsers.add_parser('analyze', help='Analyze scraped job data')
    analyze_parser.add_argument(
        "dataset_path", type=str, help="The path to the scraped data.")
    analyze_parser.add_argument(
        "-o", "--save-dir", type=str, help="The directory to save the plots to.")
    analyze_parser.add_argument(
        "-s", "--show", action="store_true", help="Whether to show the plots.")

    # Database subcommand
    db_parser = subparsers.add_parser('db', help='Database operations')
    db_subparsers = db_parser.add_subparsers(dest='db_command', help='Database commands')

    db_stats_parser = db_subparsers.add_parser('stats', help='Show database statistics')
    db_query_parser = db_subparsers.add_parser('query', help='Query database')
    db_query_parser.add_argument(
        "--type", type=str, help="Filter by job type (Hourly/Fixed)")
    db_query_parser.add_argument(
        "--search-query", type=str, help="Filter by search query")
    db_query_parser.add_argument(
        "--limit", type=int, default=10, help="Number of jobs to return")

    args = parser.parse_args()

    if args.command == 'scrape':
        # Call API endpoint
        with httpx.Client() as client:
            response = client.post(f'{args.api_url}/api/upwork/start_scrape', json={
                'query': args.search_query,
                'page': 1,
                'jobs_per_page': args.jobs_per_page,
                'headless': args.headless,
                'workers': 1,
                'fast': args.fast
            })
            response.raise_for_status()
            result = response.json()
            task_id = result['task_id']

            print(f"Scraping started with task_id: {task_id}")
            print("Polling for completion...")

            # Poll for completion
            while True:
                status_response = client.get(f'{args.api_url}/api/upwork/scraping_status/{task_id}')
                status_response.raise_for_status()
                status = status_response.json()

                if status['status'] == 'completed':
                    print(f"Scraping completed! Found {status['job_count']} jobs")
                    break
                elif status['status'] == 'failed':
                    print(f"Scraping failed: {status['error_message']}")
                    return

                print(f"Status: {status['status']}...")
                time.sleep(5)

            # Get results
            results_response = client.get(f'{args.api_url}/api/upwork/get_scraping_results/{task_id}')
            results_response.raise_for_status()
            results = results_response.json()

            # Save to file if output specified
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(results['jobs'], f, indent=2)
                print(f"Results saved to {args.output}")
            else:
                print(f"Found {results['total_jobs']} jobs")
    elif args.command == 'analyze':
        perform_analysis(args.dataset_path, args.save_dir, args.show)
    elif args.command == 'db':
        from backend.database import operations
        if args.db_command == 'stats':
            stats = operations.get_stats()
            print("\n=== Database Statistics ===")
            print(f"Total Jobs: {stats['total_jobs']}")
            print(f"Jobs Today: {stats['jobs_today']}")
            print(f"Total Search Queries: {stats['total_search_queries']}")
            print(f"\nBy Type:")
            for job_type, count in stats['by_type'].items():
                print(f"  {job_type}: {count}")
            print(f"\nBy Experience Level:")
            for exp_level, count in stats['by_experience'].items():
                print(f"  {exp_level}: {count}")
        elif args.db_command == 'query':
            filters = {}
            if args.type:
                filters['type'] = args.type
            if args.search_query:
                filters['search_query'] = args.search_query
            filters['limit'] = args.limit
            jobs = operations.get_jobs(filters)
            print(f"\n=== Found {len(jobs)} jobs ===")
            for job in jobs[:args.limit]:
                print(f"\nJob ID: {job.get('job_id', 'N/A')}")
                print(f"Title: {job.get('title', 'N/A')}")
                print(f"Type: {job.get('type', 'N/A')}")
                print(f"Search Query: {job.get('search_query', 'N/A')}")
        else:
            db_parser.print_help()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
