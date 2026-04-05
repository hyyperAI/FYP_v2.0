"""
backend/scrape/selectors.py

CSS selectors for Upwork job listing elements.
These selectors are used to locate and extract job information from the Upwork website.

Note: Upwork may change their website structure periodically.
If selectors stop working, check the Upwork website and update accordingly.
"""

# Job listing selectors
job_title_selector = ".air3-line-clamp > h2 > a"
post_time_selector = ".job-tile-header div small span:nth-child(2)"
job_skills_selector = '.air3-token'
description_selector = "div.air3-line-clamp.is-clamped > p.mb-0"

# Job details section selectors
job_details_selector = "ul.job-tile-info-list.text-base-sm.mb-4"
job_type_selector = job_details_selector + " > li:nth-child(1) > strong"
experience_level_selector = job_details_selector + ' > li[data-test="experience-level"] > strong'
time_estimate_selector = job_details_selector + ' > li[data-test="duration-label"] > strong:nth-child(2)'
# Budget selector - try fixed-price first, fallback to any li with $ amount
budget_selector_fixed = job_details_selector + ' > li[data-test="is-fixed-price"] > strong:nth-child(2)'
budget_selector = job_details_selector + ' > li > strong'

# Individual job page selectors (opened when clicking a job)
proposals_selector = 'ul.client-activity-items > li.ca-item > span.value'
client_details_selector = "ul.ac-items"
client_location_selector = client_details_selector + ' > li:nth-child(1) > strong'
# Member since: "Member since Aug 20, 2023" in <small> tag inside div[data-qa="client-contract-date"]
member_since_selector = 'div[data-qa="client-contract-date"] small'
# Other open jobs count: "Other open jobs by this Client (1)" in h5 inside div[data-test="OtherJobs"]
other_jobs_count_selector = 'div[data-test="OtherJobs"] h5'

# These selectors use regex-based finding in parser since structure varies
# We'll use the same base selectors and filter in the parser
client_spent_all_selector = client_details_selector + ' strong'
client_hires_all_selector = client_details_selector + ' div'

# Job listing selectors
job_url_selector = ".air3-line-clamp > h2 > a"

# Navigation selectors
job_back_arrow_selector = 'div.air3-slider-header button.air3-slider-prev-btn'
back_button = 'a.back-to-results[data-qa="back-to-search-results"]'

# Popup title selector (to verify correct panel opened)
popup_title_selector = 'div.air3-slider-content h2, div.air3-slider-header h4'

# Pagination selectors
pagination_selector = 'li[data-test="pagination-mobile"].air3-pagination-mobile'

__all__ = [
    'job_title_selector',
    'post_time_selector',
    'job_skills_selector',
    'description_selector',
    'job_details_selector',
    'job_type_selector',
    'experience_level_selector',
    'time_estimate_selector',
    'budget_selector',
    'budget_selector_fixed',
    'proposals_selector',
    'client_details_selector',
    'client_location_selector',
    'member_since_selector',
    'other_jobs_count_selector',
    'client_spent_all_selector',
    'client_hires_all_selector',
    'job_url_selector',
    'job_back_arrow_selector',
    'back_button',
    'popup_title_selector',
    'pagination_selector',
]
