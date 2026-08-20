"""
Main pipeline for collecting and classifying jobs.
"""

import time
from typing import List, Optional

from ..collectors.linkedin import LinkedInCollector
from ..classifiers.sponsorship import SponsorshipClassifier
from ..classifiers.company_type import CompanyTypeClassifier
from ..classifiers.seniority import SeniorityFilter
from ..tracking.cost_tracker import LLMCostTracker
from ..io.csv_handler import CSVHandler
from ..models import JobPosting
from ..utils import generate_job_id


class JobClassificationPipeline:
    """Main pipeline for collecting and classifying jobs."""
    
    def __init__(self, 
                 use_llm: bool = True,
                 openai_key: Optional[str] = None,
                 exclude_senior: bool = False):
        """
        Initialize the pipeline.
        
        Args:
            use_llm: Whether to use LLM for company classification
            openai_key: OpenAI API key
            exclude_senior: Whether to drop senior/lead/staff titles before classification
        """
        self.collector = LinkedInCollector()
        self.exclude_senior = exclude_senior
        self.sponsorship_classifier = SponsorshipClassifier()
        # Initialize cost tracker for LLM usage
        self.cost_tracker = LLMCostTracker() if use_llm else None
        self.company_classifier = CompanyTypeClassifier(use_llm, openai_key, self.cost_tracker)
        self.csv_handler = CSVHandler()
        # Filled in by process() on every exit path, including the early ones.
        # main.py folds this into the run summary in logs/runs.jsonl so that
        # "collected nothing" is distinguishable from "never ran".
        self.last_run_stats = {'collected': 0, 'already_existing': 0,
                               'needed_classification': 0, 'reason': None}
    
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
            self.last_run_stats['reason'] = 'no_jobs_collected'
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
        
        # Filter out senior/experienced titles before any classification work.
        # Done before dedup so excluded jobs never reach the LLM.
        if self.exclude_senior:
            jobs, excluded_jobs = SeniorityFilter.filter_jobs(jobs)
            if excluded_jobs:
                print(f"\nSeniority filter: excluded {len(excluded_jobs)} non-entry-level jobs")
                for job in excluded_jobs[:10]:
                    _, reason = SeniorityFilter.is_excluded(job.job_title)
                    try:
                        print(f"  - [{reason}] {job.job_title}")
                    except UnicodeEncodeError:
                        safe_title = job.job_title.encode('ascii', 'ignore').decode('ascii')
                        print(f"  - [{reason}] {safe_title}")
                if len(excluded_jobs) > 10:
                    print(f"  ... and {len(excluded_jobs) - 10} more")
                print()

            if not jobs:
                self.last_run_stats['reason'] = 'all_filtered_senior'
                print("All collected jobs were filtered out as too senior.")
                return []

        # Ensure all jobs have unique_id before checking for duplicates
        for job in jobs:
            if not job.unique_id:
                job.unique_id = generate_job_id(job.job_link)
        
        # Load existing jobs from output file to avoid re-classifying
        existing_jobs_dict, existing_ids = self.csv_handler.load_existing_jobs(output_file)
        
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
        
        self.last_run_stats.update({
            'collected': len(jobs),
            'already_existing': len(existing_jobs_found),
            'needed_classification': len(new_jobs),
        })

        print(f"\nCollected {len(jobs)} jobs.")
        print(f"  - {len(existing_jobs_found)} jobs already exist in output file (skipping classification)")
        print(f"  - {len(new_jobs)} new jobs need classification\n")
        
        # Only classify new jobs
        if new_jobs:
            print("Starting classification for new jobs...\n")
            
            # Step 1: Classify sponsorship and check database for company types
            companies_needing_llm = []  # List of (job_index, company_name, job_description)
            
            for i, job in enumerate(new_jobs):
                print(f"Classifying job {i+1}/{len(new_jobs)}: {job.job_title}")
                
                # Classify sponsorship (always done individually)
                job.sponsorship_status = self.sponsorship_classifier.classify(job.job_description)
                
                # Check company type in database first (without LLM)
                job.company_type = self.company_classifier.classify(
                    job.company_name, 
                    job.job_description, 
                    use_llm_immediately=False
                )
                
                # If company not found in database and LLM is enabled, collect for batch processing
                if (job.company_type == "Others" and 
                    self.company_classifier.use_llm and 
                    self.company_classifier.openai_key):
                    companies_needing_llm.append((i, job.company_name, job.job_description))
                
                print(f"  -> Sponsorship: {job.sponsorship_status}")
                # Handle Unicode encoding for Windows console
                try:
                    print(f"  -> Company Type: {job.company_type}")
                    if (i, job.company_name, job.job_description) in companies_needing_llm:
                        print(f"     (Will be classified with LLM in batch)")
                except UnicodeEncodeError:
                    safe_company_type = job.company_type.encode('ascii', 'ignore').decode('ascii')
                    print(f"  -> Company Type: {safe_company_type}")
                print()
            
            # Step 2: Batch classify companies that need LLM
            if companies_needing_llm:
                print(f"\n{'='*60}")
                print(f"Batch LLM Classification: {len(companies_needing_llm)} companies")
                print(f"{'='*60}\n")
                
                # Prepare list for batch classification
                batch_companies = [(company_name, job_description) 
                                  for _, company_name, job_description in companies_needing_llm]
                
                # Perform batch classification
                batch_results = self.company_classifier.batch_classify_with_llm(batch_companies)
                
                # Map results back to jobs
                for job_idx, company_name, _ in companies_needing_llm:
                    if company_name in batch_results:
                        new_jobs[job_idx].company_type = batch_results[company_name]
                        print(f"LLM classification for {company_name}: {batch_results[company_name]}")
                    else:
                        # Fallback if company not in results
                        new_jobs[job_idx].company_type = "Others"
                
                print(f"\n{'='*60}")
                print("Batch LLM Classification Complete")
                print(f"{'='*60}\n")
        
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
            if cost_summary['cost_usd'] is None:
                print(f"Estimated cost: unpriced - no entry for '{cost_summary['model']}' "
                      f"in LLMCostTracker.MODEL_PRICING")
            else:
                print(f"Estimated cost: ${cost_summary['cost_usd']:.6f} USD")
            print(f"{'='*60}\n")
        
        print(f"{'='*60}\n")
        
        return all_jobs
    
    def save_to_csv(self, jobs: List[JobPosting], output_file: str = "job_classifications.csv"):
        """
        Save jobs to CSV file.

        Args:
            jobs: List of JobPosting objects
            output_file: Output CSV file path

        Returns:
            {'new_jobs': int, 'total_jobs': int} from the CSV handler.
        """
        return self.csv_handler.save_to_csv(jobs, output_file)
