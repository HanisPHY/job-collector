"""
Job Collection and Classification System
Collects job postings from LinkedIn and classifies them by visa sponsorship and company type.
"""

import os
import re
import csv
import time
import hashlib
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, continue without it
    pass

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

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


def format_datetime_with_hour(dt_value) -> str:
    """
    Format datetime to 'YYYY-MM-DD HH:MM' format (more readable with dashes and minutes).
    
    Args:
        dt_value: datetime object, date object, or string
        
    Returns:
        Formatted string in 'YYYY-MM-DD HH:MM' format, or empty string if invalid
    """
    if dt_value is None:
        return ''
    
    try:
        # Handle pandas datetime
        if pd is not None and pd.notna(dt_value):
            if hasattr(dt_value, 'strftime'):
                # datetime object - use hour and minute
                return dt_value.strftime('%Y-%m-%d %H:%M')
            elif hasattr(dt_value, 'date'):
                # datetime with date() method - if it's a date object, use 00:00
                if hasattr(dt_value, 'hour'):
                    return dt_value.strftime('%Y-%m-%d %H:%M')
                else:
                    return dt_value.date().strftime('%Y-%m-%d') + ' 00:00'
        else:
            # Check if it's a datetime object
            if hasattr(dt_value, 'strftime'):
                if hasattr(dt_value, 'hour'):
                    return dt_value.strftime('%Y-%m-%d %H:%M')
                else:
                    return dt_value.strftime('%Y-%m-%d') + ' 00:00'
            elif hasattr(dt_value, 'date'):
                return dt_value.date().strftime('%Y-%m-%d') + ' 00:00'
            elif isinstance(dt_value, str):
                # Try to parse string date
                dt_value = dt_value.strip()
                if dt_value and dt_value.lower() not in ['none', 'nan', 'nat', '']:
                    # Try common date formats
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y.%m.%d %H:%M', '%Y.%m.%d %H', '%Y.%m.%d']:
                        try:
                            parsed = datetime.strptime(dt_value, fmt)
                            return parsed.strftime('%Y-%m-%d %H:%M')
                        except ValueError:
                            continue
    except Exception:
        pass
    
    return ''


def get_current_datetime_formatted() -> str:
    """
    Get current datetime formatted as 'YYYY-MM-DD HH:MM' (more readable format).
    
    Returns:
        Current datetime in 'YYYY-MM-DD HH:MM' format
    """
    return datetime.now().strftime('%Y-%m-%d %H:%M')


def generate_job_id(job_link: str) -> str:
    """
    Generate a unique ID for a job posting based on its LinkedIn URL.
    
    Args:
        job_link: LinkedIn job URL
        
    Returns:
        Unique job ID (extracted from URL or hash-based)
    """
    if not job_link:
        # Generate hash-based ID if no link
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:12]
    
    # Remove query parameters first to get base URL
    base_url = job_link.split('?')[0]
    
    # Try to extract job ID from LinkedIn URL
    # LinkedIn URLs can be:
    # - https://www.linkedin.com/jobs/view/1234567890/
    # - https://www.linkedin.com/jobs/view/job-title-at-company-1234567890
    # The job ID is the numeric part at the end (before any query params)
    
    # Pattern 1: /jobs/view/...-1234567890 (most common format)
    match = re.search(r'/jobs/view/[^/]+-(\d+)/?$', base_url)
    if match:
        return match.group(1)
    
    # Pattern 2: /jobs/view/1234567890 (direct numeric ID)
    match = re.search(r'/jobs/view/(\d+)/?$', base_url)
    if match:
        return match.group(1)
    
    # Fallback: use hash of the base URL (without query parameters)
    # This ensures same job gets same ID even if tracking params change
    return hashlib.md5(base_url.encode()).hexdigest()[:16]


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


class SponsorshipClassifier:
    """Classifies jobs based on visa sponsorship keywords."""
    
    # Keywords that indicate visa sponsorship
    SPONSORSHIP_KEYWORDS = [
        'visa',
        'sponsor',
        'sponsorship',
        'h-1b',
        'h1b',
        'h1-b',
        'opt',
        'cpt',
        'stem opt',
        'work authorization',
        'work visa',
        'immigration',
        'green card',
        'permanent residency'
    ]
    
    @classmethod
    def classify(cls, job_description: str) -> str:
        """
        Classify sponsorship status based on keywords.
        
        Args:
            job_description: Job description text
            
        Returns:
            'Sponsor' if keywords found, 'Not (Maybe Not) Sponsor' otherwise
        """
        if not job_description:
            return "Not (Maybe Not) Sponsor"
        
        description_lower = job_description.lower()
        
        for keyword in cls.SPONSORSHIP_KEYWORDS:
            if keyword in description_lower:
                return "Sponsor"
        
        return "Not (Maybe Not) Sponsor"


class LLMCostTracker:
    """Tracks LLM API usage and calculates costs."""
    
    # Pricing per 1K tokens (as of 2024, update as needed)
    # Prices in USD
    MODEL_PRICING = {
        "gpt-3.5-turbo": {
            "input": 0.0005,   # $0.50 per 1M tokens
            "output": 0.0015   # $1.50 per 1M tokens
        },
        "gpt-4": {
            "input": 0.03,      # $30 per 1M tokens
            "output": 0.06      # $60 per 1M tokens
        },
        "gpt-4-turbo": {
            "input": 0.01,      # $10 per 1M tokens
            "output": 0.03      # $30 per 1M tokens
        },
        "gpt-4o": {
            "input": 0.0025,    # $2.50 per 1M tokens
            "output": 0.01      # $10 per 1M tokens
        }
    }
    
    def __init__(self):
        """Initialize cost tracker."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = 0
        self.model_used = None
    
    def record_usage(self, model: str, input_tokens: int, output_tokens: int):
        """
        Record API usage.
        
        Args:
            model: Model name used
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
        """
        if self.model_used is None:
            self.model_used = model
        elif self.model_used != model:
            # If different models used, use the first one for cost calculation
            pass
        
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.api_calls += 1
    
    def calculate_cost(self) -> float:
        """
        Calculate total cost based on token usage.
        
        Returns:
            Total cost in USD
        """
        if not self.model_used or self.model_used not in self.MODEL_PRICING:
            # Default to gpt-3.5-turbo if model not found
            self.model_used = "gpt-3.5-turbo"
        
        pricing = self.MODEL_PRICING[self.model_used]
        input_cost = (self.total_input_tokens / 1000) * pricing["input"]
        output_cost = (self.total_output_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    def get_summary(self) -> Dict[str, any]:
        """
        Get summary of API usage and costs.
        
        Returns:
            Dictionary with usage statistics
        """
        return {
            "model": self.model_used or "N/A",
            "api_calls": self.api_calls,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "cost_usd": self.calculate_cost()
        }
    
    def reset(self):
        """Reset tracking counters."""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_calls = 0
        self.model_used = None


class CompanyTypeClassifier:
    """Classifies companies into categories using extensible approach."""
    
    # Well-known Big Tech companies
    BIG_TECH_COMPANIES = {
        'google', 'alphabet', 'microsoft', 'apple', 'amazon', 'meta', 'facebook',
        'netflix', 'nvidia', 'oracle', 'salesforce', 'adobe', 'intel', 'ibm',
        'cisco', 'qualcomm', 'paypal', 'uber', 'lyft', 'airbnb', 'tesla',
        'twitter', 'x.com', 'snapchat', 'spotify', 'zoom', 'slack', 'dropbox'
    }
    
    def __init__(self, use_llm: bool = True, openai_key: Optional[str] = None, cost_tracker: Optional[LLMCostTracker] = None):
        """
        Initialize company type classifier.
        
        Args:
            use_llm: Whether to use LLM for classification when needed
            openai_key: OpenAI API key for LLM classification
            cost_tracker: Optional cost tracker for API usage
        """
        self.use_llm = use_llm and OPENAI_AVAILABLE
        self.openai_key = openai_key or os.getenv('OPENAI_API_KEY')
        self.cost_tracker = cost_tracker
        if self.use_llm and self.openai_key:
            openai.api_key = self.openai_key
    
    def classify(self, company_name: str, job_description: str = "") -> str:
        """
        Classify company type.
        
        Args:
            company_name: Name of the company
            job_description: Optional job description for context
            
        Returns:
            '独角兽/上市公司/Big Tech' or 'Others'
        """
        company_lower = company_name.lower().strip()
        
        # Check if it's a known Big Tech company
        for big_tech in self.BIG_TECH_COMPANIES:
            if big_tech in company_lower:
                return "独角兽/上市公司/Big Tech"
        
        # Try to determine if it's a unicorn or public company using LLM
        if self.use_llm and self.openai_key:
            try:
                result = self._classify_with_llm(company_name, job_description)
                print(f"classification result for {company_name}: {result}")
                if result:
                    return result
            except Exception as e:
                print(f"LLM classification failed for {company_name}: {e}")
        
        # Try to check via web search/API (placeholder for external data sources)
        # This could integrate with Crunchbase API, SEC filings, etc.
        
        # Default to Others if cannot determine
        return "Others"
    
    def _classify_with_llm(self, company_name: str, job_description: str) -> Optional[str]:
        """
        Use LLM to classify company type.
        
        Args:
            company_name: Name of the company
            job_description: Job description for context
            
        Returns:
            Classification result or None
        """
        if not OPENAI_AVAILABLE:
            return None
        
        prompt = f"""Classify the following company into one of these categories:

1. "独角兽/上市公司/Big Tech" - if the company is ANY of the following:
   - A unicorn startup (private valuation ≥ $1B)
   - A publicly listed company
   - A well-known Big Tech company
   - A large, established, and prestigious company or institution,
     even if privately held
     (e.g., quantitative trading firms, hedge funds, major consulting firms,
      global financial institutions, or core tech infrastructure companies)

2. "Others" - small startups, early-stage companies, unknown firms, or local businesses

When in doubt, prefer classifying well-known large companies as
"独角兽/上市公司/Big Tech".

Company name: {company_name}
Job description context: {job_description[:500] if job_description else "N/A"}

Respond with ONLY one of: "独角兽/上市公司/Big Tech" or "Others"

"""
        
        model_name = "gpt-3.5-turbo"
        try:
            # Try new API format (openai >= 1.0.0)
            try:
                from openai import OpenAI
                client = OpenAI(api_key=self.openai_key)
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a company classification assistant. Respond with only the category name."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=20,
                    temperature=0
                )
                result = response.choices[0].message.content.strip()
                
                # Track token usage if cost tracker is available
                if self.cost_tracker:
                    usage = response.usage
                    input_tokens = usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0
                    output_tokens = usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0
                    self.cost_tracker.record_usage(model_name, input_tokens, output_tokens)
            except (ImportError, AttributeError):
                # Fallback to old API format (openai < 1.0.0)
                response = openai.ChatCompletion.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a company classification assistant. Respond with only the category name."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=20,
                    temperature=0
                )
                result = response.choices[0].message.content.strip()
                
                # Track token usage if cost tracker is available
                if self.cost_tracker:
                    usage = response.usage
                    input_tokens = usage.get('prompt_tokens', 0) if isinstance(usage, dict) else (usage.prompt_tokens if hasattr(usage, 'prompt_tokens') else 0)
                    output_tokens = usage.get('completion_tokens', 0) if isinstance(usage, dict) else (usage.completion_tokens if hasattr(usage, 'completion_tokens') else 0)
                    self.cost_tracker.record_usage(model_name, input_tokens, output_tokens)
            
            if result in ["独角兽/上市公司/Big Tech", "Others"]:
                return result
        except Exception as e:
            print(f"OpenAI API error: {e}")
        
        return None


class JobClassificationPipeline:
    """Main pipeline for collecting and classifying jobs."""
    
    def __init__(self, 
                 use_llm: bool = True,
                 openai_key: Optional[str] = None):
        """
        Initialize the pipeline.
        
        Args:
            use_llm: Whether to use LLM for company classification
            openai_key: OpenAI API key
        """
        self.collector = LinkedInCollector()
        self.sponsorship_classifier = SponsorshipClassifier()
        # Initialize cost tracker for LLM usage
        self.cost_tracker = LLMCostTracker() if use_llm else None
        self.company_classifier = CompanyTypeClassifier(use_llm, openai_key, self.cost_tracker)
    
    def process(self, search_query: str = "software engineer", limit: int = 50, time_filter_minutes: Optional[int] = None, output_file: str = "job_classifications.csv") -> List[JobPosting]:
        """
        Collect and classify jobs.
        
        Args:
            search_query: Job search query
            limit: Maximum number of jobs to process
            time_filter_minutes: Time filter in minutes for job postings (e.g., 180 for 3 hours, 1440 for 24 hours), or None (all time)
            output_file: Output CSV file path (used to check for existing jobs)
            
        Returns:
            List of classified JobPosting objects
        """
        # Record start time
        start_time = time.time()
        
        print(f"\n{'='*60}")
        print("Starting Job Collection and Classification")
        if time_filter_minutes is not None and time_filter_minutes > 0:
            if time_filter_minutes < 60:
                print(f"Time Filter: Last {time_filter_minutes} minutes")
            elif time_filter_minutes < 1440:
                hours = time_filter_minutes / 60
                print(f"Time Filter: Last {hours:.1f} hours ({time_filter_minutes} minutes)")
            else:
                days = time_filter_minutes / 1440
                print(f"Time Filter: Last {days:.1f} days ({time_filter_minutes} minutes)")
        print(f"{'='*60}\n")
        
        # Collect jobs using JobSpy
        jobs = self.collector.collect_jobs(search_query, limit, time_filter_minutes)
        
        if not jobs:
            print("No jobs collected. Please check your setup.")
            # Calculate elapsed time even if no jobs collected
            elapsed_time = time.time() - start_time
            minutes = int(elapsed_time // 60)
            seconds = elapsed_time % 60
            if minutes > 0:
                print(f"\nTotal process time: {minutes} minute(s) and {seconds:.2f} second(s)")
            else:
                print(f"\nTotal process time: {seconds:.2f} second(s)")
            return []
        
        # Ensure all jobs have unique_id before checking for duplicates
        for job in jobs:
            if not job.unique_id:
                job.unique_id = generate_job_id(job.job_link)
        
        # Load existing jobs from output file to avoid re-classifying
        existing_jobs_dict, existing_ids = self._load_existing_jobs(output_file)
        
        # Separate new jobs from existing ones
        new_jobs = []
        existing_jobs_found = []
        
        for job in jobs:
            if job.unique_id in existing_ids:
                # Job already exists, use the existing classification
                if job.unique_id in existing_jobs_dict:
                    existing_jobs_found.append(existing_jobs_dict[job.unique_id])
            else:
                # New job, needs classification
                new_jobs.append(job)
        
        print(f"\nCollected {len(jobs)} jobs.")
        print(f"  - {len(existing_jobs_found)} jobs already exist in output file (skipping classification)")
        print(f"  - {len(new_jobs)} new jobs need classification\n")
        
        # Only classify new jobs
        if new_jobs:
            print("Starting classification for new jobs...\n")
            for i, job in enumerate(new_jobs):
                print(f"Classifying job {i+1}/{len(new_jobs)}: {job.job_title}")
                
                # Classify sponsorship
                job.sponsorship_status = self.sponsorship_classifier.classify(job.job_description)
                
                # Classify company type
                job.company_type = self.company_classifier.classify(job.company_name, job.job_description)
                
                print(f"  -> Sponsorship: {job.sponsorship_status}")
                # Handle Unicode encoding for Windows console
                try:
                    print(f"  -> Company Type: {job.company_type}\n")
                except UnicodeEncodeError:
                    safe_company_type = job.company_type.encode('ascii', 'ignore').decode('ascii')
                    print(f"  -> Company Type: {safe_company_type}\n")
        
        # Combine existing and new jobs
        all_jobs = existing_jobs_found + new_jobs
        
        # Calculate and display elapsed time
        elapsed_time = time.time() - start_time
        minutes = int(elapsed_time // 60)
        seconds = elapsed_time % 60
        print(f"\n{'='*60}")
        print("Process Completed")
        if minutes > 0:
            print(f"Total process time: {minutes} minute(s) and {seconds:.2f} second(s)")
        else:
            print(f"Total process time: {seconds:.2f} second(s)")
        
        # Display LLM API cost if LLM was used
        if self.cost_tracker and self.cost_tracker.api_calls > 0:
            cost_summary = self.cost_tracker.get_summary()
            print(f"\n{'='*60}")
            print("LLM API Usage & Cost Summary")
            print(f"{'='*60}")
            print(f"Model used: {cost_summary['model']}")
            print(f"API calls: {cost_summary['api_calls']}")
            print(f"Input tokens: {cost_summary['input_tokens']:,}")
            print(f"Output tokens: {cost_summary['output_tokens']:,}")
            print(f"Total tokens: {cost_summary['total_tokens']:,}")
            print(f"Estimated cost: ${cost_summary['cost_usd']:.6f} USD")
            print(f"{'='*60}\n")
        
        print(f"{'='*60}\n")
        
        return all_jobs
    
    def _load_existing_jobs(self, output_file: str = "job_classifications.csv") -> Tuple[Dict[str, JobPosting], set]:
        """
        Load existing jobs from CSV file.
        
        Args:
            output_file: Path to CSV file
            
        Returns:
            Tuple of (dictionary mapping unique_id to JobPosting, set of existing unique_ids)
        """
        existing_jobs_dict = {}
        existing_ids = set()
        file_exists = os.path.exists(output_file)
        
        if file_exists:
            try:
                if pd is not None:
                    # Use pandas to read existing file
                    existing_df = pd.read_csv(output_file, encoding='utf-8-sig')
                    if 'unique_id' in existing_df.columns:
                        existing_ids = set(existing_df['unique_id'].astype(str))
                        # Convert existing rows back to JobPosting objects
                        for _, row in existing_df.iterrows():
                            unique_id = str(row.get('unique_id', ''))
                            existing_jobs_dict[unique_id] = JobPosting(
                                job_title=row.get('job_title', ''),
                                job_link=row.get('job_link', ''),
                                company_name=row.get('company_name', ''),
                                job_description=row.get('job_description', ''),
                                sponsorship_status=row.get('sponsorship_status', ''),
                                company_type=row.get('company_type', ''),
                                unique_id=unique_id,
                                date_posted=str(row.get('date_posted', '')) if pd.notna(row.get('date_posted', '')) else '',
                                date_recorded=str(row.get('date_recorded', '')) if pd.notna(row.get('date_recorded', '')) else ''
                            )
                else:
                    # Use standard CSV reader
                    with open(output_file, 'r', newline='', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if 'unique_id' in row and row['unique_id']:
                                unique_id = row['unique_id']
                                existing_ids.add(unique_id)
                                existing_jobs_dict[unique_id] = JobPosting(
                                    job_title=row.get('job_title', ''),
                                    job_link=row.get('job_link', ''),
                                    company_name=row.get('company_name', ''),
                                    job_description=row.get('job_description', ''),
                                    sponsorship_status=row.get('sponsorship_status', ''),
                                    company_type=row.get('company_type', ''),
                                    unique_id=unique_id,
                                    date_posted=row.get('date_posted', ''),
                                    date_recorded=row.get('date_recorded', '')
                                )
            except Exception as e:
                print(f"Warning: Could not read existing file {output_file}: {e}")
                print("Will treat all jobs as new.")
        
        return existing_jobs_dict, existing_ids
    
    def save_to_csv(self, jobs: List[JobPosting], output_file: str = "job_classifications.csv"):
        """
        Save jobs to CSV file. If file exists, only append new jobs (deduplicated by unique_id).
        
        Args:
            jobs: List of JobPosting objects
            output_file: Output CSV file path
        """
        # Ensure all jobs have unique_id
        for job in jobs:
            if not job.unique_id:
                job.unique_id = generate_job_id(job.job_link)
        
        # Read existing jobs if file exists
        existing_ids = set()
        existing_jobs = []
        file_exists = os.path.exists(output_file)
        
        if file_exists:
            try:
                if pd is not None:
                    # Use pandas to read existing file
                    existing_df = pd.read_csv(output_file, encoding='utf-8-sig')
                    if 'unique_id' in existing_df.columns:
                        existing_ids = set(existing_df['unique_id'].astype(str))
                        # Convert existing rows back to JobPosting objects for merging
                        for _, row in existing_df.iterrows():
                            existing_jobs.append(JobPosting(
                                job_title=row.get('job_title', ''),
                                job_link=row.get('job_link', ''),
                                company_name=row.get('company_name', ''),
                                job_description=row.get('job_description', ''),
                                sponsorship_status=row.get('sponsorship_status', ''),
                                company_type=row.get('company_type', ''),
                                unique_id=str(row.get('unique_id', '')),
                                date_posted=str(row.get('date_posted', '')) if pd.notna(row.get('date_posted', '')) else '',
                                date_recorded=str(row.get('date_recorded', '')) if pd.notna(row.get('date_recorded', '')) else ''
                            ))
                else:
                    # Use standard CSV reader
                    with open(output_file, 'r', newline='', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if 'unique_id' in row and row['unique_id']:
                                existing_ids.add(row['unique_id'])
                                existing_jobs.append(JobPosting(
                                    job_title=row.get('job_title', ''),
                                    job_link=row.get('job_link', ''),
                                    company_name=row.get('company_name', ''),
                                    job_description=row.get('job_description', ''),
                                    sponsorship_status=row.get('sponsorship_status', ''),
                                    company_type=row.get('company_type', ''),
                                    unique_id=row['unique_id'],
                                    date_posted=row.get('date_posted', ''),
                                    date_recorded=row.get('date_recorded', '')
                                ))
            except Exception as e:
                print(f"Warning: Could not read existing file {output_file}: {e}")
                print("Creating new file...")
                existing_ids = set()
                existing_jobs = []
        
        # Filter out jobs that already exist
        new_jobs = [job for job in jobs if job.unique_id not in existing_ids]
        
        if not new_jobs:
            print(f"\nNo new jobs to add. All {len(jobs)} jobs already exist in {output_file}")
            print(f"Total jobs in file: {len(existing_jobs)}")
            return
        
        # Combine new jobs at the beginning, then existing jobs
        all_jobs = new_jobs + existing_jobs
        
        # Prepare data for CSV
        fieldnames = ['unique_id', 'job_title', 'job_link', 'company_name', 
                     'sponsorship_status', 'company_type', 'date_posted', 'date_recorded', 'category']
        
        if pd is not None:
            # Use pandas for cleaner CSV writing
            data = []
            for job in all_jobs:
                data.append({
                    'unique_id': job.unique_id,
                    'job_title': job.job_title,
                    'job_link': job.job_link,
                    'company_name': job.company_name,
                    'sponsorship_status': job.sponsorship_status,
                    'company_type': job.company_type,
                    'date_posted': job.date_posted,
                    'date_recorded': job.date_recorded,
                    'category': f"{job.sponsorship_status} & {job.company_type}"
                })
            
            df = pd.DataFrame(data)
            # Keep existing jobs in their original order, append new jobs at the end
            df.to_csv(output_file, index=False, encoding='utf-8-sig')
        else:
            # Fallback to standard CSV writer
            with open(output_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                # Keep existing jobs in their original order, append new jobs at the end
                for job in all_jobs:
                    writer.writerow({
                        'unique_id': job.unique_id,
                        'job_title': job.job_title,
                        'job_link': job.job_link,
                        'company_name': job.company_name,
                        'sponsorship_status': job.sponsorship_status,
                        'company_type': job.company_type,
                        'date_posted': job.date_posted,
                        'date_recorded': job.date_recorded,
                        'category': f"{job.sponsorship_status} & {job.company_type}"
                    })
        
        print(f"\nResults saved to {output_file}")
        print(f"New jobs added: {len(new_jobs)}")
        print(f"Total jobs in file: {len(all_jobs)}")
        
        # Print summary by category
        categories = {}
        for job in all_jobs:
            cat = f"{job.sponsorship_status} & {job.company_type}"
            categories[cat] = categories.get(cat, 0) + 1
        
        print("\nSummary by category:")
        for cat, count in sorted(categories.items()):
            try:
                print(f"  {cat}: {count}")
            except UnicodeEncodeError:
                # Fallback for encoding issues
                safe_cat = cat.encode('ascii', 'ignore').decode('ascii')
                print(f"  {safe_cat}: {count}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect and classify LinkedIn jobs')
    parser.add_argument('--query', type=str, default='software engineer',
                       help='Job search query (default: software engineer)')
    parser.add_argument('--limit', type=int, default=50,
                       help='Maximum number of jobs to collect (default: 50)')
    parser.add_argument('--output', type=str, default='job_classifications.csv',
                       help='Output CSV file (default: job_classifications.csv)')
    parser.add_argument('--no-llm', action='store_true',
                       help='Disable LLM-based company classification')
    parser.add_argument('--time-filter', type=int, default=None, metavar='MINUTES',
                       help='Filter jobs by posting time in minutes (e.g., 180 for 3 hours, 1440 for 24 hours)')
    
    args = parser.parse_args()
    
    # Validate time filter if provided
    if args.time_filter is not None and args.time_filter <= 0:
        parser.error("--time-filter must be a positive integer (minutes)")
    
    # Record overall start time
    overall_start_time = time.time()
    
    # Initialize pipeline
    pipeline = JobClassificationPipeline(
        use_llm=not args.no_llm,
        openai_key=os.getenv('OPENAI_API_KEY')
    )
    
    # Process jobs (pass output file to check for existing jobs)
    jobs = pipeline.process(args.query, args.limit, args.time_filter, output_file=args.output)
    
    if jobs:
        # Save to CSV
        pipeline.save_to_csv(jobs, args.output)
        
        # Calculate and display overall elapsed time (including CSV saving)
        overall_elapsed_time = time.time() - overall_start_time
        overall_minutes = int(overall_elapsed_time // 60)
        overall_seconds = overall_elapsed_time % 60
        print(f"\n{'='*60}")
        print("Complete Process Summary")
        if overall_minutes > 0:
            print(f"Total time (including CSV save): {overall_minutes} minute(s) and {overall_seconds:.2f} second(s)")
        else:
            print(f"Total time (including CSV save): {overall_seconds:.2f} second(s)")
        
        # Display LLM cost in final summary if available
        if jobs and hasattr(pipeline, 'cost_tracker') and pipeline.cost_tracker and pipeline.cost_tracker.api_calls > 0:
            cost_summary = pipeline.cost_tracker.get_summary()
            print(f"LLM API cost: ${cost_summary['cost_usd']:.6f} USD ({cost_summary['total_tokens']:,} tokens)")
        
        print(f"{'='*60}\n")
    else:
        print("No jobs were collected. Please check your configuration.")
        # Still show timing even if no jobs
        overall_elapsed_time = time.time() - overall_start_time
        overall_minutes = int(overall_elapsed_time // 60)
        overall_seconds = overall_elapsed_time % 60
        if overall_minutes > 0:
            print(f"Total time: {overall_minutes} minute(s) and {overall_seconds:.2f} second(s)")
        else:
            print(f"Total time: {overall_seconds:.2f} second(s)")


if __name__ == "__main__":
    main()

