"""
backend/ai/report_generator.py

Report generation with AI insights and dashboard creation.
"""

import os
import json
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import pandas as pd
import numpy as np

from .minimax_client import MinimaxClient


def create_dashboard_chart(jobs_data: list, output_dir: str):
    """Create a single dashboard with all 7 charts combined"""
    from backend.analysis.data_processing import read_dataset
    from backend.analysis.statistics import transform_to_binary_skills

    # Convert jobs_data to DataFrame
    df = pd.DataFrame(jobs_data)

    # Create figure with subplots
    fig = plt.figure(figsize=(20, 24))
    gs = gridspec.GridSpec(4, 2, height_ratios=[1, 1, 1, 1], hspace=0.3, wspace=0.3)

    # Chart 1: Job Types (Top Left)
    ax1 = fig.add_subplot(gs[0, 0])
    job_types = df['type'].value_counts()
    ax1.pie(job_types.values, labels=job_types.index, autopct='%1.1f%%', startangle=90)
    ax1.set_title('Job Types Distribution', fontsize=14, fontweight='bold')

    # Chart 2: Experience Levels (Top Right)
    ax2 = fig.add_subplot(gs[0, 1])
    exp_counts = df['experience_level'].value_counts()
    ax2.bar(exp_counts.index, exp_counts.values, color=['#2ecc71', '#3498db', '#e74c3c'])
    ax2.set_title('Experience Levels', fontsize=14, fontweight='bold')
    ax2.tick_params(axis='x', rotation=45)

    # Chart 3: Budget Distribution (Middle Left)
    ax3 = fig.add_subplot(gs[1, 0])
    budgets = df['budget'].dropna()
    if not budgets.empty:
        ax3.hist(budgets, bins=10, color='#9b59b6', alpha=0.7)
        ax3.set_title('Budget Distribution', fontsize=14, fontweight='bold')
        ax3.set_xlabel('Budget ($)')
        ax3.set_ylabel('Number of Jobs')

    # Chart 4: Top Skills (Middle Right)
    ax4 = fig.add_subplot(gs[1, 1])
    try:
        skills_df = transform_to_binary_skills(df)
        top_skills = skills_df.sum().sort_values(ascending=False).head(10)
        ax4.barh(range(len(top_skills)), top_skills.values, color='#f39c12')
        ax4.set_yticks(range(len(top_skills)))
        ax4.set_yticklabels(top_skills.index)
        ax4.set_title('Top 10 Skills', fontsize=14, fontweight='bold')
        ax4.set_xlabel('Frequency')
    except Exception as e:
        ax4.text(0.5, 0.5, 'Skills data not available', ha='center', va='center')
        ax4.set_title('Top 10 Skills', fontsize=14, fontweight='bold')

    # Chart 5: Time Estimates (Bottom Left)
    ax5 = fig.add_subplot(gs[2, 0])
    time_est = df['time_estimate'].value_counts()
    if not time_est.empty:
        ax5.barh(range(len(time_est)), time_est.values, color='#1abc9c')
        ax5.set_yticks(range(len(time_est)))
        ax5.set_yticklabels(time_est.index)
        ax5.set_title('Project Duration', fontsize=14, fontweight='bold')
        ax5.set_xlabel('Number of Jobs')

    # Chart 6: Budget by Job Type (Bottom Right)
    ax6 = fig.add_subplot(gs[2, 1])
    try:
        budget_by_type = df.groupby('type')['budget'].mean().dropna()
        if not budget_by_type.empty:
            ax6.bar(budget_by_type.index, budget_by_type.values, color=['#34495e', '#95a5a6'])
            ax6.set_title('Average Budget by Type', fontsize=14, fontweight='bold')
            ax6.set_ylabel('Average Budget ($)')
            ax6.tick_params(axis='x', rotation=45)
    except Exception as e:
        ax6.text(0.5, 0.5, 'Budget data not available', ha='center', va='center')
        ax6.set_title('Average Budget by Type', fontsize=14, fontweight='bold')

    # Chart 7: Client Locations (Bottom)
    ax7 = fig.add_subplot(gs[3, :])
    try:
        locations = df['client_location'].value_counts().head(10)
        if not locations.empty:
            ax7.bar(range(len(locations)), locations.values, color='#e67e22')
            ax7.set_xticks(range(len(locations)))
            ax7.set_xticklabels(locations.index, rotation=45, ha='right')
            ax7.set_title('Top 10 Client Locations', fontsize=14, fontweight='bold')
            ax7.set_ylabel('Number of Jobs')
    except Exception as e:
        ax7.text(0.5, 0.5, 'Location data not available', ha='center', va='center')
        ax7.set_title('Top 10 Client Locations', fontsize=14, fontweight='bold')

    # Add overall title
    query = jobs_data[0].get('title', 'Upwork Jobs')[:30] if jobs_data else 'Upwork Jobs'
    fig.suptitle(f'Upwork Job Analysis Dashboard - {len(jobs_data)} Jobs',
                 fontsize=18, fontweight='bold', y=0.98)

    # Save combined dashboard
    dashboard_path = os.path.join(output_dir, 'complete_analysis_dashboard.png')
    plt.savefig(dashboard_path, dpi=150, bbox_inches='tight')
    plt.close()

    print(f"Dashboard saved to: {dashboard_path}")
    return dashboard_path


class ReportGenerator:
    """Generate comprehensive markdown report with AI insights"""

    def __init__(self, insights: dict):
        self.insights = insights

    def generate_comprehensive_report(self, output_path: str, jobs_data: list):
        """Write comprehensive report in N8N style"""

        # Extract search query from job data
        query = "Upwork Jobs"
        if jobs_data and 'title' in jobs_data[0]:
            # Try to infer from titles
            titles = [job.get('title', '') for job in jobs_data[:5]]
            common_words = set(titles[0].lower().split())
            for title in titles[1:]:
                common_words &= set(title.lower().split())
            if common_words:
                query = ' '.join(sorted(common_words)[:3]).title()

        # Calculate comprehensive statistics
        total_jobs = len(jobs_data)
        job_types = {}
        exp_levels = {}
        budgets = []
        time_estimates = {}
        skills_count = {}
        client_locations = {}

        for job in jobs_data:
            # Job types
            jtype = job.get('type', 'Unknown')
            job_types[jtype] = job_types.get(jtype, 0) + 1

            # Experience levels
            exp = job.get('experience_level', 'Unknown')
            exp_levels[exp] = exp_levels.get(exp, 0) + 1

            # Budgets
            budget = job.get('budget')
            if budget:
                budgets.append(budget)

            # Time estimates
            time_est = job.get('time_estimate', 'Unknown')
            time_estimates[time_est] = time_estimates.get(time_est, 0) + 1

            # Skills
            skills = job.get('skills', [])
            for skill in skills:
                # Clean skill name
                skill = skill.strip()
                if skill and not skill.startswith('+'):
                    skills_count[skill] = skills_count.get(skill, 0) + 1

            # Client locations
            location = job.get('client_location', 'Unknown')
            if location and location != 'Unknown':
                client_locations[location] = client_locations.get(location, 0) + 1

        # Calculate statistics
        avg_budget = sum(budgets) / len(budgets) if budgets else 0
        min_budget = min(budgets) if budgets else 0
        max_budget = max(budgets) if budgets else 0

        # Build comprehensive report
        report = f"""# {query} - Analysis Report

**Scraped:** {self.insights.get('generated_at', '2026-01-16')}
**Total Jobs:** {total_jobs}
**Query:** "{query}"

---

## Executive Summary

{self.insights.get('market_summary', self._generate_summary(jobs_data, job_types, exp_levels, avg_budget, skills_count))}

---

## Job Types

| Type | Count | Percentage |
|------|-------|------------|
| Hourly | {job_types.get('Hourly', 0)} | {job_types.get('Hourly', 0)/total_jobs*100:.1f}% |
| Fixed Price | {job_types.get('Fixed', 0)} | {job_types.get('Fixed', 0)/total_jobs*100:.1f}% |

**Insight:** {"Hourly positions dominate" if job_types.get('Hourly', 0) > job_types.get('Fixed', 0) else "Fixed-price projects are more common"}, suggesting {"ongoing work opportunities" if job_types.get('Hourly', 0) > job_types.get('Fixed', 0) else "task-based projects"}.

---

## Experience Level Requirements

| Level | Count | Percentage |
|-------|-------|------------|
"""
        for level, count in sorted(exp_levels.items(), key=lambda x: x[1], reverse=True):
            report += f"| {level} | {count} | {count/total_jobs*100:.1f}% |\n"

        # Find most common experience level
        most_common_exp = max(exp_levels.items(), key=lambda x: x[1])[0] if exp_levels else "N/A"
        report += f"\n**Insight:** Focus on {most_common_exp} level - you need solid experience but don't need to be an expert.\n\n"

        # Budget Analysis
        report += f"""---

## Budget Analysis

| Metric | Value |
|--------|-------|
| Average | ${avg_budget:.2f} |
| Minimum | ${min_budget:.2f} |
| Maximum | ${max_budget:.2f} |
| Jobs with budgets | {len(budgets)} ({len(budgets)/total_jobs*100:.1f}%) |

"""

        if budgets:
            low_budget = sum(1 for b in budgets if b < 100)
            mid_budget = sum(1 for b in budgets if 100 <= b <= 500)
            high_budget = sum(1 for b in budgets if b > 500)

            report += f"""**Budget Distribution:**
- Low-budget (<$100): ~{low_budget} jobs
- Mid-range ($100-$500): ~{mid_budget} jobs
- High-value (>$500): ~{high_budget} jobs

**Insight:** Most {query.lower()} jobs are in the ${avg_budget/2:.0f}-${avg_budget*2:.0f} range for specific projects.

"""

        # Project Duration
        report += f"""---

## Project Duration

| Duration | Count |
|----------|-------|
"""
        for duration, count in sorted(time_estimates.items(), key=lambda x: x[1], reverse=True)[:5]:
            report += f"| {duration} | {count} |\n"

        # Calculate short-term percentage
        short_term = sum(count for dur, count in time_estimates.items()
                        if dur and any(term in dur.lower() for term in ['less than', '1 month', '1-3']))
        if short_term > 0:
            report += f"\n**Insight:** Short-term projects dominate ({short_term}/{total_jobs}), suggesting task-based work.\n\n"

        # Sample Jobs
        report += f"""---

## Sample Job Titles

"""
        for i, job in enumerate(jobs_data[:5], 1):
            title = job.get('title', 'N/A')[:80]
            report += f"{i}. **{title}**\n"
            if job.get('skills'):
                skills_str = ', '.join(job['skills'][:3])
                report += f"   - {skills_str}\n"
            report += "\n"

        # Skills Section
        if skills_count:
            report += f"""---

## Key Skills in Demand

**Top 15 Skills:**
"""
            sorted_skills = sorted(skills_count.items(), key=lambda x: x[1], reverse=True)[:15]
            for skill, count in sorted_skills:
                report += f"- **{skill}**: {count} jobs\n"

            # Identify trends
            top_3_skills = [skill for skill, _ in sorted_skills[:3]]
            report += f"\n**Insight:** {', '.join(top_3_skills)} are the most in-demand skills for {query.lower()} positions.\n\n"
        else:
            report += """---

## Key Skills in Demand

**Note:** Skills data extraction in progress. Based on job descriptions, these skills are likely required:
- Technical skills from job titles
- Platform-specific expertise
- Integration capabilities

"""

        # Recommendations
        report += f"""---

## Recommendations

### For {query} Developers:

"""

        # Generate data-driven recommendations
        if exp_levels:
            top_exp = max(exp_levels.items(), key=lambda x: x[1])[0]
            report += f"1. **Target {top_exp} Positions** - {exp_levels[top_exp]/total_jobs*100:.1f}% of jobs require this level\n"

        if skills_count:
            top_skill = max(skills_count.items(), key=lambda x: x[1])[0]
            report += f"2. **Master {top_skill}** - Most in-demand skill ({skills_count[top_skill]} jobs)\n"

        report += f"3. **Pricing Strategy** - Average budget is ${avg_budget:.0f}\n"

        if avg_budget < 500:
            report += f"4. **Start Small** - Focus on ${avg_budget/4:.0f}-${avg_budget/2:.0f} projects to build portfolio\n"

        report += "\n### Recommended Rates:\n\n"
        report += "| Project Type | Recommended Rate |\n"
        report += "|-------------|------------------|\n"
        report += f"| Simple tasks | ${avg_budget/4:.0f}-${avg_budget/2:.0f} |\n"
        report += f"| Medium complexity | ${avg_budget/2:.0f}-${avg_budget:.0f} |\n"
        report += f"| Advanced projects | ${avg_budget:.0f}-${max_budget:.0f} |\n"

        # Files Generated
        report += f"""---

## Files Generated

- `jobs_data.json` - Raw scraped data ({total_jobs} jobs)
- `complete_analysis_dashboard.png` - Combined visualization dashboard
- `{os.path.basename(output_path)}` - This analysis report

---

## Next Steps

1. **Build Portfolio** - Use top skills identified to create relevant projects
2. **Set Competitive Rates** - Price within the {avg_budget/2:.0f}-{avg_budget*1.5:.0f} range
3. **Apply Strategically** - Target {top_exp.lower() if exp_levels else 'entry'} level positions
4. **Monitor Trends** - Re-scrape monthly to track market changes

---

## Conclusion

**{query} market shows** {"strong" if avg_budget > 50 else "moderate"} demand with average budgets of ${avg_budget:.0f}.
Focus on mastering the top skills and targeting the most common experience level to maximize success.

**Action Item:** {"Build expertise in " + ", ".join([skill for skill, _ in sorted_skills[:3]]) + " to capture high-value opportunities." if skills_count else "Focus on building a strong portfolio with relevant projects."}

---

*Generated by Upwork Analysis Tool*
*Date: {self.insights.get('generated_at', '2026-01-16')}*
"""

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Write report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        print(f"Comprehensive report saved to: {output_path}")
        return output_path

    def _generate_summary(self, jobs_data: list, job_types: dict, exp_levels: dict, avg_budget: float, skills_count: dict) -> str:
        """Generate basic summary from data"""
        total = len(jobs_data)
        hourly_pct = job_types.get('Hourly', 0) / total * 100 if total > 0 else 0

        summary = f"Analysis of {total} {jobs_data[0].get('title', 'Upwork') if jobs_data else 'upwork'} jobs reveals:\n"
        summary += f"- **{hourly_pct:.0f}% Hourly rates** - Strong preference for ongoing work\n"
        summary += f"- **Average budget: ${avg_budget:.0f}** - Wide range from budget analysis\n"

        if exp_levels:
            top_exp = max(exp_levels.items(), key=lambda x: x[1])[0]
            summary += f"- **{exp_levels[top_exp]/total*100:.0f}% require {top_exp} level** - Good opportunity\n"

        if skills_count:
            top_skill = max(skills_count.items(), key=lambda x: x[1])[0]
            summary += f"- **{skills_count[top_skill]} jobs need {top_skill}** - Most in-demand skill\n"

        return summary

    def generate_report(self, output_path: str, jobs_data: list):
        """Legacy method - kept for compatibility"""
        return self.generate_comprehensive_report(output_path, jobs_data)


__all__ = ['ReportGenerator', 'create_dashboard_chart']
