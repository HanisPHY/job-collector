"""
LinkedIn job collector using JobSpy.
"""

from typing import List, Optional

try:
    from jobspy import scrape_jobs
    JOBSPY_AVAILABLE = True
except ImportError:
    try:
        # Try alternative import path
        from jobspy.jobspy import scrape_jobs
        JOBSPY_AVAILABLE = True
    except ImportError:
        JOBSPY_AVAILABLE = False

import paths

from ..models import JobPosting
from ..utils import format_datetime_with_hour, get_current_datetime_formatted, generate_job_id


class LinkedInCollector:
    """Collects job postings from LinkedIn using JobSpy."""
    
    def __init__(self):
        """Initialize LinkedIn collector."""
        pass
    
    def collect_jobs(self, search_query: str = "software engineer", limit: int = 50, time_filter_minutes: Optional[int] = None) -> List[JobPosting]:
        """
        Collect jobs using python-jobspy library.
        
        Args:
            search_query: Search query for jobs
            limit: Maximum number of jobs to collect
            time_filter_minutes: Time filter in minutes (e.g., 1440 for 24 hours), or None (all time)
            
        Returns:
            List of JobPosting objects
        """
        jobs = []
        
        if not JOBSPY_AVAILABLE:
            raise ImportError("python-jobspy is required. Install with: pip install jobspy")
        
        try:
            print(f"Using python-jobspy to collect jobs for: {search_query}")
            
            # Convert time filter to hours_old format for jobspy
            hours_old = None
            if time_filter_minutes is not None and time_filter_minutes > 0:
                hours_old = max(1, time_filter_minutes // 60)  # Convert minutes to hours, minimum 1
            
            # Scrape jobs using jobspy
            # jobspy returns a pandas DataFrame
            jobs_df = scrape_jobs(
                site_name=["linkedin"],
                search_term=search_query,
                location="United States",
                results_wanted=limit,
                hours_old=hours_old,
                country_indeed="usa"
            )
            
            if jobs_df is not None and not jobs_df.empty:
                print(f"JobSpy found {len(jobs_df)} jobs")
                
                # save jobs_df to csv
                jobs_df.to_csv(str(paths.DATA_DIR / 'jobs_df.csv'), index=False)
                
                # Convert DataFrame rows to JobPosting objects
                for _, row in jobs_df.iterrows():
                    job_link = row.get('job_url', '') or row.get('url', '')
                    job_title = str(row.get('title', '')) or str(row.get('job_title', ''))
                    company_name = str(row.get('company', '')) or str(row.get('company_name', ''))
                    job_description = str(row.get('description', '')) or str(row.get('job_description', ''))
                    
                    # Extract date posted - try common field names and format with hours
                    date_posted = ''
                    # Try to get date_posted field (JobSpy uses this field name)
                    date_value = row.get('date_posted')
                    
                    # Format date_posted with hours if available
                    if date_value is not None:
                        date_posted = format_datetime_with_hour(date_value)
                    
                    # If still empty, try alternative field names
                    if not date_posted:
                        for alt_field in ['posted_date', 'date', 'posted', 'posted_at', 'created_at']:
                            alt_value = row.get(alt_field)
                            if alt_value is not None:
                                date_posted = format_datetime_with_hour(alt_value)
                                if date_posted:
                                    break
                    
                    # Note: If date_posted is still empty, it means JobSpy/LinkedIn didn't provide the date.
                    # This is a known limitation: LinkedIn often shows relative dates ("3 days ago") in HTML
                    # instead of exact posting dates. The actual date may exist in LinkedIn's internal API
                    # (originalListedAt field), but python-jobspy doesn't access it. The date_posted field
                    # will remain empty in these cases, which is expected behavior.
                    
                    # Get current datetime for date_recorded (when this job was collected)
                    date_recorded = get_current_datetime_formatted()
                    
                    # Generate unique ID
                    unique_id = generate_job_id(job_link)
                    
                    jobs.append(JobPosting(
                        job_title=job_title,
                        job_link=job_link,
                        company_name=company_name,
                        job_description=job_description,
                        unique_id=unique_id,
                        date_posted=date_posted,
                        date_recorded=date_recorded
                    ))
                
                print(f"Successfully collected {len(jobs)} jobs using JobSpy")
            else:
                print("JobSpy returned no jobs")
                
        except Exception as e:
            print(f"Error using JobSpy: {e}")
            raise
        
        return jobs
