"""
backend/scrape/parsers.py

HTML parsing functions for extracting job information from Upwork.
"""

from datetime import timedelta
from typing import Any

from bs4 import BeautifulSoup
from bs4.element import Tag

from .selectors import (
    job_title_selector,
    post_time_selector,
    job_skills_selector,
    description_selector,
    job_details_selector,
    job_type_selector,
    experience_level_selector,
    time_estimate_selector,
    budget_selector,
    budget_selector_fixed,
    proposals_selector,
    client_details_selector,
    client_location_selector,
    member_since_selector,
    other_jobs_count_selector,
    client_spent_all_selector,
    client_hires_all_selector,
    job_url_selector,
    job_back_arrow_selector,
    popup_title_selector,
)


def construct_url(query: str, jobs_per_page: int = 10, start_page: int = 1) -> str:
    """
    Constructs a search url based on the arguments and deals with spaces in
    `query` and choosing the correct `jobs_per_page`.

    Parameters
    ----------
    query: str
        The query to search for. It could be multiple words or single word.
    jobs_per_page: int
        How many jobs should be displayed per page. Allowed numbers are 10, 20 and 50. In case a different number is
        passed, the closest allowed number to it will be chosen. Default is 10.
    start_page: int
        The page number to start searching from. Default is 1 (the first page).

    Returns
    -------
    url: str
        The complete search url.
    """
    # Only 10, 20 and 50 are valid values to jobs_per_page; this expression takes care of getting the closest allowed
    # number to the input.
    jobs_per_page = min([10, 20, 50], key=lambda x: abs(x - jobs_per_page))
    query = query.replace(" ", "%20")
    return (f"https://www.upwork.com/nx/search/jobs/"
            f"?nbs=1"
            f"&page={start_page}"
            f"&per_page={jobs_per_page}"
            f"&q={query}"
            f"&sort=recency")


def parse_time(relative_time: str) -> float:
    """Upwork jobs post-dates are relative to the local time of the host, this function converts them as Unix time"""
    relative_time = relative_time.lower()
    if relative_time == "yesterday":
        time_delta = timedelta(days=1)
    elif "last week" in relative_time:
        time_delta = timedelta(weeks=1)
    elif "last month" in relative_time:
        time_delta = timedelta(days=30)
    else:
        number, unit = relative_time.split()[:2]
        unit += 's' if not unit.endswith('s') else ''  # Turn minute to minutes, for example.
        if "month" in unit:
            number = int(number) * 30
            unit = "days"
        time_delta = timedelta(**{unit: int(number)})
    absolute_time = datetime.now() - time_delta
    return int(absolute_time.timestamp())


def parse_budget(job_type: str, budget: str | None) -> int | None:
    """
    Takes the job type (hourly, fixed-price) budget, which might be the budget in $ for a fixed-price
    job or the estimated time of an hourly job.
    Returns the hourly rate for hourly jobs and the budget for fixed-price. Returns None if the hourly rate isn't
    specified.

    Formats handled:
    - Hourly: "$15.00 - $35.00" -> average = 25
    - Hourly: "$15.00-$35.00" -> average = 25
    - Fixed: "$500" -> 500
    - Fixed: "$5,000" -> 5000
    """
    import re

    job_type_lower = job_type.lower()

    # Handle hourly jobs - check budget text for rate range
    if "hourly" in job_type_lower:
        if budget:
            # Look for range format: "$15.00 - $35.00" or "$15.00-$35.00"
            match = re.search(r'\$?([\d.]+)\s*[-–]\s*\$?([\d.]+)', budget)
            if match:
                try:
                    min_rate = float(match.group(1))
                    max_rate = float(match.group(2))
                    return int((max_rate + min_rate) / 2)
                except ValueError:
                    pass

            # Look for single rate: "$25.00"
            match = re.search(r'\$?([\d.]+)', budget)
            if match:
                try:
                    return int(float(match.group(1)))
                except ValueError:
                    pass
        return None

    # Handle fixed-price jobs
    if not budget:
        return None

    # Remove $ sign and extract first number
    budget_clean = re.sub(r'[^\d.,]', '', budget.replace('$', ''))
    # Handle comma separators
    budget_clean = budget_clean.replace(',', '')

    try:
        return int(float(budget_clean))
    except ValueError:
        return None


def parse_total_spent(total_spent: str) -> int | None:
    """
    Parses the total spent texts and returns the dollar number as integer.
    Format examples: "$2.5K", "$2500", "$2.5Ktotal spent", "$5.6K total spent"

    Returns:
        int: The dollar amount (e.g., 5600 for "$5.6K")
        None: If parsing fails
    """
    if not total_spent:
        return None

    import re

    # Clean the text - remove $ prefix
    total_spent = total_spent.strip()
    total_spent = re.sub(r'^\$', '', total_spent)

    # Check for K or M suffix (e.g., "5.6K", "2.5M")
    # Handle both "5.6K" and "5.6 K" formats
    match = re.match(r'([\d.]+)\s*[KkMm]', total_spent)
    if match:
        num_str = match.group(1)
        suffix = re.search(r'[KkMm]', total_spent).group(0)
        try:
            value = float(num_str)
            if suffix.upper() == 'K':
                value = value * 1000
            elif suffix.upper() == 'M':
                value = value * 1_000_000
            return int(value)
        except ValueError:
            pass

    # Fallback: try to extract any number without suffix
    match = re.search(r'([\d.,]+)', total_spent)
    if match:
        num_str = match.group(1).replace(',', '')
        try:
            return int(float(num_str))
        except ValueError:
            pass

    return None


def parse_jobs_posted(open_jobs_text: str) -> int | None:
    """
    Parses the open jobs count from text.
    Format: "Other open jobs by this Client (3)" -> returns 3

    Also handles: "3 open jobs", "3 jobs", etc.
    """
    if not open_jobs_text:
        return None

    import re

    # Primary format: "(X)" at the end - "Other open jobs by this Client (3)"
    match = re.search(r'\((\d+)\)\s*$', open_jobs_text)
    if match:
        return int(match.group(1))

    # Fallback: look for number near "open jobs" or "jobs"
    match = re.search(r'(\d+)\s*(?:open\s+)?jobs?', open_jobs_text, re.IGNORECASE)
    if match:
        return int(match.group(1))

    return None


def parse_hires_info(hires_text: str) -> dict:
    """
    Parses hires text like "14 hires, 2 active" or "14 hires 2 active"
    Returns dict with 'total' and 'active' counts and calculated hire_rate.
    """
    if not hires_text:
        return {'total': None, 'active': None, 'hire_rate': None}

    import re

    # Match pattern: "X hires, Y active" or "X hires Y active"
    match = re.search(r'(\d+)\s*hires?,?\s*(\d+)\s*active', hires_text, re.IGNORECASE)
    if match:
        total = int(match.group(1))
        active = int(match.group(2))
        hire_rate = round(active / total, 2) if total > 0 else None
        return {'total': total, 'active': active, 'hire_rate': hire_rate}

    # Try just extracting total hires
    match = re.search(r'(\d+)\s*hires?', hires_text, re.IGNORECASE)
    if match:
        return {'total': int(match.group(1)), 'active': None, 'hire_rate': None}

    return {'total': None, 'active': None, 'hire_rate': None}


def parse_hours(hours_text: str) -> int | None:
    """
    Parses hours worked from text like "88 hours" or "88 hrs"
    Returns the number of hours.
    """
    if not hours_text:
        return None

    import re
    match = re.search(r'(\d+)', hours_text)
    if match:
        return int(match.group(1))
    return None


def parse_company_size(size_text: str) -> str | None:
    """
    Returns the company size text as-is.
    Format: "Small company (2-9 people)" -> returns "Small company (2-9 people)"
    """
    if not size_text:
        return None
    return size_text.strip()


def parse_hire_rate(hires_text: str) -> float | None:
    """
    Parses the hires text and returns hire rate as a decimal (e.g., 0.33 for 33%).
    Format: "3 hires, 1 active" -> hire_rate = 1/3 = 0.33
    Returns None if insufficient data.
    """
    if not hires_text:
        return None
    import re
    # Match pattern like "X hires, Y active"
    match = re.search(r'(\d+)\s*hires?,?\s*(\d+)\s*active', hires_text, re.IGNORECASE)
    if match:
        total = int(match.group(1))
        active = int(match.group(2))
        if total > 0:
            return round(active / total, 2)
    return None


def parse_member_since(date_text: str) -> str | None:
    """
    Parses member since date.
    Format: "Member since Aug 20, 2023" -> returns "Aug 20, 2023"
    """
    if not date_text:
        return None
    import re
    match = re.search(r'Member since\s+(.+)', date_text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def parse_one_job(driver: Any, job: Tag, index: int, fast: bool = False) -> dict[str, str | int | float | None]:
    """
    Parses one job listing (html) and returns a dictionary containing its information. The collected information is:
        - Job title
        - Job description
        - Job URL
        - Job skills
        - Job post time as a UNIX timestamp
        - Job type (Hourly or Fixed)
        - Experience level (entry, intermediate, expert)
        - Time estimate (the estimated time the job is going to take, for example, 1-3 months for an hourly job
          or None for a fixed-price job)
        - Budget (The budget for a fixed-price job or the average hourly rate or None if it's not specified)
    And the following if the listing is public and `fast=False` (only proposals and location are guaranteed to exist):
        - Number of proposals
        - Client location
        - Client total spent
        - Client hire rate
        - Client hours worked
        - Client company size
        - Client open jobs count

    Parameters
    ----------
    driver: Chrome
        The driver instance to use.
    job: Tag
        Beautiful soup tag containing the job html.
    index: int
        The index of the job with respect to the page.
    fast: bool, optional
        Whether to use the fast method. The fast method doesn't click on the job listing to scrape the information about
        the client and number of proposals making it much faster. Default False.

    Returns
    -------
    job_details: dict
        The job's details.
    """
    import re

    job_type = job.select_one(job_type_selector).text
    xp_level = job.select_one(experience_level_selector)
    time_est = job.select_one(time_estimate_selector)

    # Try fixed-price selector first, then fallback to generic
    budget = job.select_one(budget_selector_fixed)
    if not budget:
        budget = job.select_one(budget_selector)

    # Extract job URL from the listing
    title_link = job.select_one(job_url_selector)
    job_url = None
    if title_link and title_link.get('href'):
        href = title_link['href']
        # Convert relative URL to full URL
        if href.startswith('/'):
            job_url = f"https://www.upwork.com{href}"
        else:
            job_url = href

    # Get raw budget text for storage
    budget_text = budget.text if budget else None

    # Extract job_id from job_url
    job_id = None
    if job_url:
        # Extract ID from URL pattern like: /jobs/Title_~022012738270027427649/
        import re
        match = re.search(r'/jobs/[^~]+~([0-9]+)/', job_url)
        if match:
            job_id = match.group(1)
        else:
            # Fallback: generate from URL hash
            job_id = str(abs(hash(job_url)))

    job_details = {
        "job_id": job_id,
        "title": job.select_one(job_title_selector).text,
        "description": job.select_one(description_selector).text,
        "job_url": job_url,
        "time": parse_time(job.select_one(post_time_selector).text),
        "skills": [skill.text for skill in job.select(job_skills_selector)],
        "type": job_type.split(':')[0].split()[0],
        "experience_level": xp_level.text if xp_level else None,
        "time_estimate": time_est.text.split(',')[0] if time_est else None,
        "budget": budget_text  # Store raw text like "$10.00 - $20.00" or "$500"
    }
    if fast:
        return job_details

    # Initialize client fields with placeholders
    # String fields: "no value extracted" → "no data" if still empty
    # Int fields: 0
    string_keys = ("proposals", "client_location", "client_hire_rate", "client_company_size", "member_since")
    int_keys = ("client_total_spent", "client_hours", "client_jobs_posted")
    job_details.update({key: "no value extracted" for key in string_keys})
    job_details.update({key: 0 for key in int_keys})

    try:
        # 1. Click to open job panel
        driver.execute_script("arguments[0].click();", driver.find_element(f"article:nth-child({index})"))

        # 2. Wait for panel to load
        driver.wait_for_selector(client_location_selector, timeout=5)

        # 3. Wait for popup to load and check for private job
        is_private = False
        import time
        for _ in range(30):  # Max 3 seconds
            try:
                # print("find pop_uptitle")
                popup_title = driver.find_element(popup_title_selector).text.strip()
                # Check if private job (look for "the job is private" text)
                if "the job is private" in popup_title.lower():
                    is_private = True
                    job_details["proposals"] = "The job is private"
                    break
            except:
                pass
            time.sleep(0.1)

        # 4. If private job, skip extraction
        if is_private:
            print("job is private")
            pass  # Skip to back button
        else:
            # 5. Scrape data from POPUP ONLY (not full page source)
            print("Scrape data from popup...")
            try:
                # Find popup element and get only its HTML
                popup_element = driver.find_element("css selector", "div.air3-slider-content")
                popup_html = popup_element.get_attribute("outerHTML")
                job_soup = BeautifulSoup(popup_html, "html.parser")

                # Extract proposals count
                proposals_elem = job_soup.select_one(proposals_selector)
                if proposals_elem:
                    job_details["proposals"] = proposals_elem.text

                # Extract client location
                location_elem = job_soup.select_one(client_location_selector)
                if location_elem:
                    job_details["client_location"] = location_elem.text

                # Extract member since date
                member_since_elem = job_soup.select_one(member_since_selector)
                if member_since_elem:
                    job_details["member_since"] = member_since_elem.get_text(strip=True)

                # Extract client total spent
                for strong in job_soup.select(client_spent_all_selector):
                    text = strong.get_text(strip=True)
                    if re.search(r'\$[\d.,]+K?', text):
                        job_details["client_total_spent"] = parse_total_spent(text)
                        break

                # Extract client hire rate
                for div in job_soup.select(client_hires_all_selector):
                    text = div.get_text(strip=True)
                    if 'hires' in text.lower() and 'active' in text.lower():
                        job_details["client_hire_rate"] = text
                        break

                # Extract client hours and company size
                client_panel = job_soup.select_one(client_details_selector)
                if client_panel:
                    panel_text = client_panel.get_text(strip=True)
                    hours_match = re.search(r'(\d+)\s*hours?', panel_text, re.IGNORECASE)
                    if hours_match:
                        job_details["client_hours"] = int(hours_match.group(1))
                    company_match = re.search(r'(Small|Medium|Large)\s*company\s*\([^)]+\)', panel_text)
                    if company_match:
                        job_details["client_company_size"] = company_match.group(0)

                # Extract other open jobs count
                other_jobs_elem = job_soup.select_one(other_jobs_count_selector)
                if other_jobs_elem:
                    job_details["client_jobs_posted"] = parse_jobs_posted(other_jobs_elem.get_text(strip=True))

                print(f"Extracted: location={job_details['client_location']}, spent={job_details['client_total_spent']}")
            except Exception as e:
                print(f"Extraction error: {e}")
                pass

    except Exception:  # In case of a timeout or private job listing.
        pass

    # Clean up: convert "no value extracted" to "no data" for empty string fields
    for key in string_keys:
        if job_details[key] == "no value extracted":
            job_details[key] = "no data"

    try:
        driver.wait_for_selector(job_back_arrow_selector, timeout=1.5)
        print(f"Job proposal is :{job[proposal]}")
        print("Clicking back arrow...")
        driver.find_element(job_back_arrow_selector).click()
    except Exception:
        pass

    from .utils import sleep
    sleep(2, 3)  # Wait for panel to fully close/reset before next job
    # print(f"the job_Details that are extracted for a single value is \n\n  {job_details}")
    return job_details


def parse_first_job_only(driver: Any, soup: BeautifulSoup, fast: bool = False) -> dict[str, str | int | float | None]:
    """
    MONITORING MODE: Extract ONLY the first job from the page.

    This function is specifically designed for continuous monitoring where we only
    care about the first job position. When a new job is posted, it appears at
    position 1, pushing the old job down.

    Parameters
    ----------
    driver: Chrome
        The driver instance to use.
    soup: BeautifulSoup
        BeautifulSoup object containing the page HTML.
    fast: bool, optional
        Whether to use the fast method. Default False.

    Returns
    -------
    job_details: dict or None
        The first job's details, or None if no job found.
    """
    import re

    # Find the FIRST job only (position 1)
    jobs = soup.find_all('article')

    if not jobs:
        print("[MONITOR] No jobs found on page")
        return None

    first_job = jobs[0]  # Only the first job!

    print(f"[MONITOR] Extracting first job only (position 1)")

    # Parse the first job using the same logic as parse_one_job
    job_type = first_job.select_one(job_type_selector).text
    xp_level = first_job.select_one(experience_level_selector)
    time_est = first_job.select_one(time_estimate_selector)

    # Try fixed-price selector first, then fallback to generic
    budget = first_job.select_one(budget_selector_fixed)
    if not budget:
        budget = first_job.select_one(budget_selector)

    # Extract job URL from the listing
    title_link = first_job.select_one(job_url_selector)
    job_url = None
    if title_link and title_link.get('href'):
        href = title_link['href']
        # Convert relative URL to full URL
        if href.startswith('/'):
            job_url = f"https://www.upwork.com{href}"
        else:
            job_url = href

    # Get raw budget text for storage
    budget_text = budget.text if budget else None

    # Extract job_id from job_url
    job_id = None
    if job_url:
        # Extract ID from URL pattern
        match = re.search(r'/jobs/[^~]+~([0-9]+)/', job_url)
        if match:
            job_id = match.group(1)
        else:
            # Fallback: generate from URL hash
            job_id = str(abs(hash(job_url)))

    job_details = {
        "job_id": job_id,
        "title": first_job.select_one(job_title_selector).text,
        "description": first_job.select_one(description_selector).text,
        "job_url": job_url,
        "time": parse_time(first_job.select_one(post_time_selector).text),
        "skills": [skill.text for skill in first_job.select(job_skills_selector)],
        "type": job_type.split(':')[0].split()[0],
        "experience_level": xp_level.text if xp_level else None,
        "time_estimate": time_est.text.split(',')[0] if time_est else None,
        "budget": budget_text  # Store raw text
    }

    if fast:
        print(f"[MONITOR] Fast mode: extracted basic info only")
        return job_details

    # Initialize client fields
    string_keys = ("proposals", "client_location", "client_hire_rate", "client_company_size", "member_since")
    int_keys = ("client_total_spent", "client_hours", "client_jobs_posted")
    job_details.update({key: "no value extracted" for key in string_keys})
    job_details.update({key: 0 for key in int_keys})

    try:
        # Click to open job panel (first job only)
        driver.execute_script("arguments[0].click();", driver.find_element("article:nth-child(1)"))

        # Wait for panel to load
        driver.wait_for_selector(client_location_selector, timeout=5)

        # Check for private job
        is_private = False
        import time
        for _ in range(30):
            try:
                popup_title = driver.find_element(popup_title_selector).text.strip()
                if "the job is private" in popup_title.lower():
                    is_private = True
                    job_details["proposals"] = "The job is private"
                    break
            except:
                pass
            time.sleep(0.1)

        # If not private, scrape from popup
        if not is_private:
            print(f"[MONITOR] Scraping first job details from popup...")
            try:
                popup_element = driver.find_element("css selector", "div.air3-slider-content")
                popup_html = popup_element.get_attribute("outerHTML")
                job_soup = BeautifulSoup(popup_html, "html.parser")

                # Extract proposals
                proposals_elem = job_soup.select_one(proposals_selector)
                if proposals_elem:
                    job_details["proposals"] = proposals_elem.text

                # Extract client location
                location_elem = job_soup.select_one(client_location_selector)
                if location_elem:
                    job_details["client_location"] = location_elem.text

                # Extract member since
                member_since_elem = job_soup.select_one(member_since_selector)
                if member_since_elem:
                    job_details["member_since"] = member_since_elem.get_text(strip=True)

                # Extract total spent
                total_spent_elem = job_soup.select_one(client_spent_all_selector)
                if total_spent_elem:
                    total_spent_text = total_spent_elem.get_text(strip=True)
                    job_details["client_total_spent"] = parse_total_spent(total_spent_text)

                # Extract hire rate
                hire_rate_elem = job_soup.select_one(client_hires_all_selector)
                if hire_rate_elem:
                    hire_rate_text = hire_rate_elem.get_text(strip=True)
                    job_details["client_hire_rate"] = parse_hire_rate(hire_rate_text)

                # Extract hours worked
                hours_elem = job_soup.select_one("li:contains('hours')")
                if hours_elem:
                    hours_text = hours_elem.get_text(strip=True)
                    job_details["client_hours"] = parse_hours(hours_text)

                # Extract company size
                company_size_elem = job_soup.select_one("li:contains('employees')")
                if company_size_elem:
                    company_size_text = company_size_elem.get_text(strip=True)
                    job_details["client_company_size"] = parse_company_size(company_size_text)

                # Extract open jobs count
                open_jobs_elem = job_soup.select_one(other_jobs_count_selector)
                if open_jobs_elem:
                    open_jobs_text = open_jobs_elem.get_text(strip=True)
                    job_details["client_jobs_posted"] = parse_jobs_posted(open_jobs_text)

                print(f"[MONITOR] Extracted: location={job_details['client_location']}, spent={job_details['client_total_spent']}")
            except Exception as e:
                print(f"[MONITOR] Extraction error: {e}")
                pass
    except Exception:
        pass

    # Clean up
    for key in string_keys:
        if job_details[key] == "no value extracted":
            job_details[key] = "no data"

    try:
        driver.wait_for_selector(job_back_arrow_selector, timeout=1.5)
        driver.find_element(job_back_arrow_selector).click()
    except Exception:
        pass

    from .utils import sleep
    sleep(2, 3)

    print(f"[MONITOR] First job extracted successfully")
    print(f"  Job ID: {job_details['job_id']}")
    print(f"  Title: {job_details['title'][:60]}...")

    return job_details


# For backward compatibility - import datetime for local use
from datetime import datetime

__all__ = [
    'construct_url',
    'parse_time',
    'parse_budget',
    'parse_total_spent',
    'parse_jobs_posted',
    'parse_hires_info',
    'parse_hours',
    'parse_company_size',
    'parse_hire_rate',
    'parse_member_since',
    'parse_one_job',
    'parse_first_job_only',
]
