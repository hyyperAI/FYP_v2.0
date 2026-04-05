"""backend/scrape/engine.py

This module implements the `JobsScraper` class that aims to scrape Upwork job listings within certain parameters.
"""

import threading
import json
import time
import requests

from seleniumbase.common.exceptions import (
    NoSuchElementException as SBNoSuchElementException, WebDriverException as SBWebDriverException)
from seleniumbase.undetected import Chrome
from seleniumbase import Driver
from selenium.common.exceptions import NoSuchElementException, TimeoutException, WebDriverException
from bs4 import BeautifulSoup

from .parsers import parse_one_job, construct_url
from .utils import split_list_into_chunks, inhibit_sleep, time_print, sleep
from backend.integrations.selenium_setup import (
    create_driver, configure_driver, random_delay, adaptive_delay
)
from backend.database.operations import update_task_status


class JobsScraper:

    def __init__(
            self,
            search_query: str,
            jobs_per_page: int = 10,
            start_page: int = 1,
            pages_to_scrape: int | None = 3,
            save_path: str | None = None,
            retries: int = 3,
            headless: bool = False,
            workers: int = 1,
            fast: bool = False,
            task_id: str | None = None) -> None:
        """
        Scrapes the `jobs_per_page` * `pages_to_scrape` jobs resulting from searching for `search_query`.

        Notes
        -----
        Upwork won't load any job listings after a certain page number, this limit is any page after 101 when jobs per
        page are equal to 50, 251 when 20 and 501 when 10.

        Parameters
        ----------
        search_query: str
            The query to search for.
        jobs_per_page: int, optional
            How many jobs should be displayed per page. Allowed numbers are 10, 20 and 50. Default is 10.
            The higher the number, the fewer requests are made, the better.
        start_page: int, optional
            The page number to start searching from. Default is 1 (the first page). **Note** this can't be larger than a
            certain number, see the `Notes` section.
        pages_to_scrape: int, optional
            How many pages to scrape after (including) `start_page`. If None, scrape all the available pages. For
            example, if `start_page` is 1 and `pages_to_scrape` is 10, then pages 1 through 10 will be scraped.
            Default 10. **Note** this can't be larger than a certain number, see the `Notes` section.
        save_path: str, optional
            Where to save the scraped data.
        retries: int, optional
            How many times to retry scraping the jobs before giving up. The reasons why scraping might fail are because
            of CloudFlair's Captcha and network errors. Default is 3.
        headless: bool, optional
            Whether to use a headless browser. Default is False. An important **note**, if headless is set to True and
            the browser encountered a captcha the first time it tried to get a link, it means that the undetected
            headless browser didn't work for some reason (it usually works). In this case, a new browser instance is
            created with headless=False.
        workers: int, optional
            The number of worker threads to launch, the higher the number, the faster the execution and resource
            consumption. Default is 1 (sequential execution).
        fast: bool, optional
            Whether to use the fast scraping method. This method can be 10 to 50x times faster but leaves out all
            the information related to the client (location, total spent, etc) and number of proposals. Default False.
        task_id: str, optional
            Task ID for tracking scraping progress via API.
        """
        assert jobs_per_page in (10, 20, 50), "The allowed values for `jobs_per_page` are 10, 20 and 50."
        self.search_query = search_query
        self.jobs_per_page = jobs_per_page
        self.start_page = start_page
        self.save_path = save_path
        if self.save_path and not self.save_path.endswith('.json'):
            self.save_path += '.json'
        self.retries = retries
        self.headless = headless
        self.workers = workers
        self.fast = fast
        self.task_id = task_id

        # For monitoring mode - keep driver alive
        self.driver = None
        self.monitoring_mode = False

        # Upwork limits: 501 pages @10/page, 251 @20/page, 101 @50/page
        allowed_npages = {10: 501, 20: 251, 50: 101}[self.jobs_per_page]
        self.last_allowed_page = allowed_npages

        # Cap pages_to_scrape at allowed limit
        self.pages_to_scrape = min(pages_to_scrape or 3, self.last_allowed_page - self.start_page + 1)

        assert 0 < self.start_page <= self.last_allowed_page, f"`start_page` must be in [1, {self.last_allowed_page}]"

        self.pages_to_jobs: dict[str, dict[int, list[dict[str, str | int | float | None]]]] = {
            'scrape': {}, 'update': {}}
        self.failed_pages: set[int] = set()

        self.seen_descriptions: set[str] = set()
        self.seen_page = None

        estimated_number_of_jobs = self.pages_to_scrape * self.jobs_per_page
        print(
            f"Scraping Configuration\n----------------------\n"
            f"search query: {self.search_query}\n"
            f"pages to scrape: {self.pages_to_scrape}\n"
            f"estimated jobs: {estimated_number_of_jobs}\n"
            f"workers: {self.workers}\n"
            f"fast mode: {self.fast}\n"
            f"headless: {self.headless}\n"
            f"retries: {self.retries}\n"
            f"{f'saving to: {self.save_path}' if self.save_path else 'not saving'}")

    @property
    def scraped_jobs(self) -> list[dict]:
        """A list containing all the scraped jobs in the order they are presented with on Upwork."""
        jobs = []
        for action in ('update', 'scrape'):
            for _, jobs_list in sorted(self.pages_to_jobs[action].items(), key=lambda x: x[0]):
                jobs.extend(jobs_list)
        return jobs

    def save_job_to_api(self, job: dict) -> bool:
        """
        Save a job to the database directly.

        Parameters
        ----------
        job: dict
            The job data to save

        Returns
        -------
        success: bool
            True if saved successfully, False otherwise
        """
        from backend.database.operations import save_job
        try:
            save_job(job, task_id=self.task_id)
            return True
        except Exception as e:
            time_print(f"Failed to save job to database: {e}")
            return False

    def create_driver(self) -> Chrome:
        """Create selenium base undetected chrome driver instance with stealth settings."""
        driver = create_driver(
            headless=self.headless,
            undetected=True,
        )
        # Apply stealth settings to avoid detection
        configure_driver(driver, use_stealth=True)
        return driver

    def enable_monitoring_mode(self) -> None:
        """
        Enable monitoring mode - keeps driver alive for continuous monitoring.

        In monitoring mode, the driver is created once and reused for multiple scrapes.
        This is more efficient than creating and closing the driver each time.
        """
        self.monitoring_mode = True
        if self.driver is None:
            self.driver = self.create_driver()
            time_print("Driver created for monitoring mode")

            # Navigate to Upwork search page for monitoring
            try:
                success = self.get_url_retry(self.driver, self.start_page, f"Navigating to search page")
                if success:
                    time_print(f"Successfully navigated to search page for query: {self.search_query}")
                else:
                    time_print(f"Warning: Failed to navigate to search page after retries")
            except Exception as e:
                time_print(f"Warning: Could not navigate to search page: {e}")

    def disable_monitoring_mode(self) -> None:
        """Disable monitoring mode and close driver."""
        self.monitoring_mode = False
        if self.driver:
            try:
                self.driver.quit()
                time_print("Driver closed")
            except Exception as e:
                time_print(f"Error closing driver: {e}")
            finally:
                self.driver = None

    def refresh_driver(self) -> None:
        """
        Refresh the current page in the driver.

        This is used in monitoring mode to get fresh job listings without recreating the driver.
        """
        if self.driver:
            try:
                self.driver.refresh()
                # Wait for page to load after refresh
                sleep(3, 5)  # Longer wait for page to fully load
                time_print("Page refreshed")
            except Exception as e:
                time_print(f"Warning: Could not refresh page: {e}")
                # Try to re-navigate if refresh fails
                try:
                    self.get_url_retry(self.driver, self.start_page, "Re-navigating to search page")
                except Exception as e2:
                    time_print(f"Error: Could not re-navigate: {e2}")

    def get_url(self, driver: Chrome, page_number: int) -> None:
        """
        Loads the `page_number`th result page for the given `search_query` and `jobs_per_page`.

        Parameters
        ----------
        driver: Chrome
            The webdriver instance to use.
        page_number: int
            The page number to get.
        """
        driver.get(construct_url(self.search_query, self.jobs_per_page, page_number))

    def get_url_retry(self, driver: Chrome, page_number: int, msg: str | None = None) -> bool:
        """
        Same as `get_url` but retry the page if it fails whether because of a network error or a captcha.

        Returns
        -------
        success: bool
            True if the page loads successfully, False otherwise.
        """
        # The following code is to achieve retrying functionality, see https://stackoverflow.com/a/7663441/23524006
        for retry in range(self.retries):
            try:
                if msg:
                    time_print(f"{msg} (try {retry + 1}/{self.retries}).")
                self.get_url(driver, page_number)
                driver.find_element("css selector", "article")
            except NoSuchElementException:
                time_print(f"Encountered a Captcha scraping page {page_number}, trying again.")
                sleep(5, 15)
            except TimeoutException:
                time_print(f"Timed out waiting for page {page_number} to load. trying again.")
                sleep(15, 30)
            else:
                break
        else:
            return False
        return True

    def get_total_number_of_result_pages(self) -> int:
        """Gets the total number of result pages for a certain `search_query` and `jobs_per_page`."""
        driver = self.create_driver()
        t = time.time()
        success = self.get_url_retry(driver, 1, "Getting the total number of result pages.")
        self.link_get_took = time.time() - t
        page_source = driver.page_source if success else None
        driver.quit()
        if not success:
            raise TimeoutError(
                "Couldn't get the total number of result pages. If this was due to timeout, please check your"
                "connection and try again. If it was due to a captcha and `headless` is set to True, try setting it to"
                "False and try again.")
        soup = BeautifulSoup(page_source, "html.parser")
        n_pages = soup.select_one('li[data-test="pagination-mobile"].air3-pagination-mobile').text
        return int(n_pages.split()[-1].replace(",", ""))

    def _scrape_pages(self, page_numbers: list, action: str = 'scrape') -> None:
        """
        Scrapes all the page numbers contained in `page_number` for their job listings details.

        Notes
        -----
        - On Windows, this method prevents the computer from sleeping (but allows the screen to turn off) during
          the scraping process. The reason for this is that when Windows sleeps, the connection to the webdriver
          is severed, and it can't continue running when the PC wakes up resulting in an error.
        - The scraped data is available through `jobs_details` property.
        - `scrape_jobs` method should be used instead of this because it offers saving and multi-threading
          functionality. This method is intended for internal use, but can still be used by user code.

        Parameters
        ----------
        page_numbers: list
            A list containing the page numbers to scrape.
        action: str
            The action to perform, "scrape" the data or "update" existing data with any new data. Default "scrape".

        See Also
        --------
        scrape_jobs: The preferred method to call.
        """
        # Mark task as in progress
        if self.task_id:
            update_task_status(self.task_id, "in_progress")

        # Use existing driver if in monitoring mode, otherwise create new one
        if self.monitoring_mode and self.driver:
            driver = self.driver
        else:
            driver = self.create_driver()
        total_pages = self.start_page + self.pages_to_scrape - 1 if action == 'scrape' else self.last_allowed_page
        seen_jobs = []
        consecutive_seens = 0
        scraped_count = 0

        for page in page_numbers:
            if self.seen_page and page > self.seen_page:
                break
            inhibit_sleep(True)

            # Add random delay before navigation to mimic human behavior
            random_delay(3.0, 7.0)

            if not self.get_url_retry(
                    driver, page, f"Scraping page {page} of {total_pages}"):
                self.failed_pages.add(page)
                continue
            self.failed_pages.discard(page)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            jobs = soup.find_all('article')
            self.pages_to_jobs[action][page] = []
            for i, job in enumerate(jobs):

                job = parse_one_job(driver, job, i + 1, self.fast)
                job['search_query'] = self.search_query
                # print(f"Job {i + 1}: \n \n ======================================================= {job}")
                description = job['description']
                if description in self.seen_descriptions:
                    consecutive_seens += 1
                    seen_jobs.append(job)
                else:
                    consecutive_seens = 0
                    while seen_jobs:
                        self.pages_to_jobs[action][page].append(seen_jobs.pop(0))
                    self.pages_to_jobs[action][page].append(job)
                self.seen_descriptions.add(description)

                try:
                    self.save_job_to_api(job)
                except Exception as e:
                    time_print(f"Failed to save job to API: {e}")

                self.save_data()

                if consecutive_seens > 5:
                    self.seen_page = min(page, self.seen_page) if self.seen_page else page
                    break

            # Incremental save after each page
            self.save_data()

            # Update task progress
            if self.task_id:
                scraped_count += 1
                remaining = len(page_numbers) - scraped_count
                # Note: We can't get exact remaining jobs until scraping is done
                # But we can track page progress
                if remaining > 0:
                    update_task_status(self.task_id, "in_progress", remaining_jobs=remaining)

        inhibit_sleep(False)

        # Only quit driver if not in monitoring mode
        if not self.monitoring_mode:
            driver.quit()

    def distribute_work(self, page_numbers: list, action: str = 'scrape') -> None:
        """Distributes the number of pages to scrape across `self.workers` threads. This function is blocking."""
        workers = []
        for page_numbers_chunk in split_list_into_chunks(page_numbers, self.workers):
            worker = threading.Thread(target=self._scrape_pages, args=(page_numbers_chunk, action))
            worker.start()
            workers.append(worker)
            # Add delay between starting workers to reduce detection risk
            random_delay(5.0, 10.0)
        for worker in workers:
            worker.join()

    def retry_failed(self, action: str = 'scrape') -> None:
        """Retry to scrape any failed pages."""
        if self.failed_pages:
            time_print("Waiting 30 to 60 seconds before trying to scrape the failed pages...")
            sleep(30, 60)
            self.distribute_work(list(self.failed_pages), action)
            if self.failed_pages:  # Would be empty if all pages were scraped successfully.
                time_print(f"Failed to scrape the following pages: {self.failed_pages}.")

    def save_data(self) -> None:
        """Save the scraped data to `save_path` as json."""
        if self.save_path:
            time_print(f"Saving to {self.save_path}")
            with open(self.save_path, 'w') as save_file:
                json.dump(self.scraped_jobs, save_file)

    def scrape_jobs(self, page_numbers: list | None = None, action: str = 'scrape') -> list[dict]:
        """
        Scrapes `pages_to_scrape` number of pages for their job listings starting at `start_page`. The following
        information is collected about each job listing:
            - Job title
            - Job description
            - Job skills
            - Job post time as a UNIX timestamp
            - Job type (Hourly or Fixed)
            - Experience level (entry, intermediate, expert)
            - Time estimate (the estimated time the job is going to take, for example, 1-3 months for an hourly job
              or None for a fixed-price job)
            - Budget (The budget for a fixed-price job or the average hourly rate or None if it's not specified)
        And the following if the job listing is public (only proposals and location are guaranteed to exist):
            - Number of proposals
            - Client location
            - Client number of posted jobs
            - Client hire rate
            - Client average hourly rate
            - Client total spent

        Notes
        -----
        - On Windows, this method prevents the computer from sleeping (but allows the screen to turn off) during
          the scraping process. The reason for this is that when Windows sleeps, the connection to the webdriver
          is severed, and it can't continue running when the PC wakes up resulting in an error.

        Parameters
        ----------
        page_numbers: list, optional
            A list containing the page numbers to scrape. If None, scrape all the pages from `start_page` to
            `pages_to_scrape`. Default None
        action: str
            The action to perform, "scrape" the data or "update" existing data with any new data. Default "scrape".

        Returns
        -------
        jobs_details: list[dict]
            A list of dictionaries containing information about the jobs in the order they are presented with on Upwork.
        """
        if page_numbers is None:
            page_numbers = list(range(self.start_page, self.start_page + self.pages_to_scrape))
        self.distribute_work(page_numbers, action)
        self.retry_failed(action)
        if action == 'update':
            # list() to make a copy of the keys and avoid raising dict changed size during iteration runtime exception.
            for key in list(self.pages_to_jobs[action]):
                if self.seen_page and key > self.seen_page:
                    self.pages_to_jobs[action].pop(key)
        time_print(f"Scraped {sum(map(len, self.pages_to_jobs[action].values()))} jobs.")
        self.save_data()

        # Mark task as completed
        if self.task_id:
            job_count = len(self.scraped_jobs)
            update_task_status(self.task_id, "completed", job_count=job_count)

        return self.scraped_jobs

    def update_existing(self) -> list[dict]:
        """
        Update the existing data with any new job listings.

        This function can be called without calling `scrape_jobs` if the data has already been scraped before and is
        saved at `save_path.

        This function can be called repeatedly to keep updating the existing data, and it saves the data to `save_path`
        after each call.
        """
        if not self.pages_to_jobs['scrape']:
            if not self.save_path:
                raise FileNotFoundError(
                    "The scraped data isn't saved to a file or loaded in memory."
                    "If you want to scrape the data, use `scrape_jobs` instead.")
            with open(self.save_path, 'r') as save_file:
                loaded_jobs = json.load(save_file)
                self.seen_descriptions = {job['description'] for job in loaded_jobs}
                self.pages_to_jobs['scrape'][1] = loaded_jobs
        self.seen_page = None
        return self.scrape_jobs(list(range(1, self.last_allowed_page + 1)), 'update')


__all__ = ['JobsScraper']
