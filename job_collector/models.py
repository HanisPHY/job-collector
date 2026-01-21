"""
Data models for job postings.
"""

from dataclasses import dataclass


@dataclass
class JobPosting:
    """Data class for job posting information."""
    job_title: str
    job_link: str
    company_name: str
    job_description: str = ""
    sponsorship_status: str = ""
    company_type: str = ""
    unique_id: str = ""
    date_posted: str = ""
    date_recorded: str = ""
