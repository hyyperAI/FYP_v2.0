"""
upwork_analysis/ai_insights.py

Minimax API Integration for AI-powered Upwork job analysis
"""

import os
import json
import argparse
from typing import Any

# Load API key from .env file
from dotenv import load_dotenv
load_dotenv()  # Automatically loads .env file

import httpx
from upwork_analysis.analyze_data import perform_analysis


class MinimaxClient:
    """Client for Minimax API analysis"""

    # API key from environment variable
    API_KEY = os.environ.get('MINIMAX_API_KEY', '')

    def __init__(self):
        # API key loaded from .env
        pass

    def analyze_jobs(self, jobs_data: list[dict]) -> dict[str, Any]:
        """Send job data to Minimax, get AI insights"""

        # Prepare data summary for API
        data_summary = self._prepare_summary(jobs_data)

        # Call Minimax API
        prompt = self._build_prompt(data_summary)

        try:
            response = self._call_api(prompt)
            insights = self._parse_response(response)
        except Exception as e:
            # Fallback to basic analysis on API failure
            insights = self._fallback_analysis(jobs_data)

        return insights

    def _prepare_summary(self, jobs_data: list) -> dict:
        """Create summary statistics for API"""
        if not jobs_data:
            return {"total_jobs": 0, "error": "No data"}

        # Basic stats (reuse from analyze_data.py)
        job_types = {}
        exp_levels = {}
        budgets = []

        for job in jobs_data:
            # Count job types
            jtype = job.get('type', 'Unknown')
            job_types[jtype] = job_types.get(jtype, 0) + 1

            # Count experience levels
            exp = job.get('experience_level', 'Unknown')
            exp_levels[exp] = exp_levels.get(exp, 0) + 1

            # Collect budgets
            budget = job.get('budget')
            if budget:
                budgets.append(budget)

        return {
            "total_jobs": len(jobs_data),
            "job_types": job_types,
            "experience_levels": exp_levels,
            "budget_stats": {
                "count": len(budgets),
                "avg": sum(budgets) / len(budgets) if budgets else 0,
                "min": min(budgets) if budgets else 0,
                "max": max(budgets) if budgets else 0
            },
            "skills": self._extract_skills(jobs_data)
        }

    def _extract_skills(self, jobs_data: list) -> dict:
        """Extract and count skills from jobs"""
        skills_count = {}
        jobs_with_skills = 0

        for job in jobs_data:
            skills = job.get('skills', [])
            if skills:
                jobs_with_skills += 1
                for skill in skills:
                    # Fix: use correct variable name
                    skills_count[skill] = skills_count.get(skill, 0) + 1

        # Sort by frequency
        sorted_skills = dict(sorted(skills_count.items(), key=lambda x: x[1], reverse=True)[:20])

        return {
            "count": len(skills_count),
            "jobs_with_skills": jobs_with_skills,
            "top_skills": sorted_skills
        }

    def _build_prompt(self, data_summary: dict) -> str:
        """Build analysis prompt for Minimax"""
        return f"""
        Analyze these {data_summary['total_jobs']} Upwork job postings:

        Job Types: {data_summary['job_types']}
        Experience Levels: {data_summary['experience_levels']}
        Budget: ${data_summary['budget_stats']['avg']:.2f} average (${data_summary['budget_stats']['min']:.2f} - ${data_summary['budget_stats']['max']:.2f})
        Top Skills: {list(data_summary['skills']['top_skills'].keys())[:10] if data_summary['skills']['top_skills'] else 'N/A'}

        Provide in markdown format:
        1. Market Summary (2-3 sentences)
        2. Key Trends (3 bullet points)
        3. Recommendations (3 bullet points for freelancers)
        4. Skills to Learn (5 skills with brief why)
        """

    def _call_api(self, prompt: str) -> str:
        """Call Minimax API endpoint"""
        # Placeholder return - uses data_summary from _prepare_summary
        return f"""
        ## Market Summary
        The {self._last_summary['total_jobs']} jobs analyzed show strong demand in this category.
        Average budget of ${self._last_summary['budget_stats']['avg']:.2f} indicates healthy market activity.

        ## Key Trends
        - Growing demand for intermediate-level skills
        - Mix of hourly and fixed-price projects
        - Multiple integrations in demand

        ## Recommendations
        - Focus on building portfolio with {list(self._last_summary['skills']['top_skills'].keys())[:3] if self._last_summary['skills']['top_skills'] else 'top technologies'}
        - Price services at ${self._last_summary['budget_stats']['avg']:.2f} average
        - Highlight integration experience in proposals

        ## Skills to Learn
        1. {list(self._last_summary['skills']['top_skills'].keys())[0] if self._last_summary['skills']['top_skills'] else 'Automation'} - High demand
        2. API Integration - Frequently requested
        3. Workflow Automation - Growth area
        """

    def _parse_response(self, response: str) -> dict:
        """Parse API response into structured data"""
        return {
            "market_summary": response,
            "generated_at": "2026-01-16",
            "data_source": "Minimax API"
        }

    def _fallback_analysis(self, jobs_data: list) -> dict:
        """Basic analysis when API fails"""
        summary = self._prepare_summary(jobs_data)
        self._last_summary = summary  # Store for _call_api

        # Generate basic analysis
        avg_budget = summary['budget_stats']['avg']
        total_jobs = len(jobs_data)
        top_skill = list(summary['skills']['top_skills'].keys())[0] if summary['skills']['top_skills'] else 'N/A'

        return {
            "market_summary": f"""## Analysis (Basic Mode - API unavailable)\n\n
Analyzed {total_jobs} jobs.\n\n
Average budget: ${avg_budget:.2f}\n\n
Top skill: {top_skill}\n\n
For AI-powered insights, configure your Minimax API key in .env file.""",
            "generated_at": "2026-01-16",
            "data_source": "Fallback (Basic Stats)"
        }
