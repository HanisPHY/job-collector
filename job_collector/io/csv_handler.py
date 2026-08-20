"""
CSV file I/O operations for job postings.
"""

import os
import csv
from typing import List, Dict, Tuple, Set

try:
    import pandas as pd
except ImportError:
    pd = None

from ..models import JobPosting
from ..utils import generate_job_id


class CSVHandler:
    """Handles reading and writing job postings to/from CSV files."""
    
    @staticmethod
    def load_existing_jobs(output_file: str = "job_classifications.csv") -> Tuple[Dict[str, JobPosting], Set[str]]:
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
                # Do NOT swallow this. Continuing with an empty set makes every
                # job look new, which downstream means re-classifying everything
                # and (in save_to_csv) rewriting the file from scratch - losing
                # the history, the manual 'applied' column, and the original
                # date_recorded timestamps the daily report is built on.
                raise RuntimeError(
                    f"Could not read existing file {output_file}: {e}. "
                    f"Refusing to continue - fix or move the file first."
                ) from e

        return existing_jobs_dict, existing_ids
    
    @staticmethod
    def save_to_csv(jobs: List[JobPosting], output_file: str = "job_classifications.csv") -> Dict[str, int]:
        """
        Save jobs to CSV file. If file exists, only append new jobs (deduplicated by unique_id).

        Args:
            jobs: List of JobPosting objects
            output_file: Output CSV file path

        Returns:
            {'new_jobs': int, 'total_jobs': int} - reported by main.py into
            logs/runs.jsonl so the daily report can tell "nothing new today"
            apart from "the collector never ran".
        """
        # Ensure all jobs have unique_id
        for job in jobs:
            if not job.unique_id:
                job.unique_id = generate_job_id(job.job_link)
        
        # Read existing jobs if file exists
        existing_ids = set()
        existing_jobs = []
        applied_values = {}  # Dictionary to store 'applied' values by unique_id
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
                            unique_id = str(row.get('unique_id', ''))
                            existing_jobs.append(JobPosting(
                                job_title=row.get('job_title', ''),
                                job_link=row.get('job_link', ''),
                                company_name=row.get('company_name', ''),
                                job_description=row.get('job_description', ''),
                                sponsorship_status=row.get('sponsorship_status', ''),
                                company_type=row.get('company_type', ''),
                                unique_id=unique_id,
                                date_posted=str(row.get('date_posted', '')) if pd.notna(row.get('date_posted', '')) else '',
                                date_recorded=str(row.get('date_recorded', '')) if pd.notna(row.get('date_recorded', '')) else ''
                            ))
                            # Store 'applied' value if it exists
                            if 'applied' in existing_df.columns:
                                applied_val = row.get('applied', '')
                                if pd.notna(applied_val):
                                    applied_values[unique_id] = str(applied_val)
                                else:
                                    applied_values[unique_id] = ''
                else:
                    # Use standard CSV reader
                    with open(output_file, 'r', newline='', encoding='utf-8-sig') as f:
                        reader = csv.DictReader(f)
                        for row in reader:
                            if 'unique_id' in row and row['unique_id']:
                                unique_id = row['unique_id']
                                existing_ids.add(unique_id)
                                existing_jobs.append(JobPosting(
                                    job_title=row.get('job_title', ''),
                                    job_link=row.get('job_link', ''),
                                    company_name=row.get('company_name', ''),
                                    job_description=row.get('job_description', ''),
                                    sponsorship_status=row.get('sponsorship_status', ''),
                                    company_type=row.get('company_type', ''),
                                    unique_id=unique_id,
                                    date_posted=row.get('date_posted', ''),
                                    date_recorded=row.get('date_recorded', '')
                                ))
                                # Store 'applied' value if it exists
                                applied_values[unique_id] = row.get('applied', '')
            except Exception as e:
                # Clearing these would make every job look new and rewrite the
                # whole file from this batch alone - wiping the history, the
                # manual 'applied' column, and every original date_recorded.
                # Fail loudly instead; the file on disk stays untouched.
                raise RuntimeError(
                    f"Could not read existing file {output_file}: {e}. "
                    f"Refusing to overwrite it - fix or move the file first."
                ) from e

        # Filter out jobs that already exist
        new_jobs = [job for job in jobs if job.unique_id not in existing_ids]

        if not new_jobs:
            print(f"\nNo new jobs to add. All {len(jobs)} jobs already exist in {output_file}")
            print(f"Total jobs in file: {len(existing_jobs)}")
            # Most common path on the hourly new-grad schedule - must still
            # return counts, not None.
            return {'new_jobs': 0, 'total_jobs': len(existing_jobs)}

        # Combine new jobs at the beginning, then existing jobs
        all_jobs = new_jobs + existing_jobs
        
        # Prepare data for CSV
        fieldnames = ['unique_id', 'job_title', 'job_link', 'company_name', 
                     'sponsorship_status', 'company_type', 'date_posted', 'date_recorded', 'category', 'applied']
        
        if pd is not None:
            # Use pandas for cleaner CSV writing
            data = []
            for job in all_jobs:
                # Get 'applied' value from stored values or use empty string for new jobs
                applied_value = applied_values.get(job.unique_id, '')
                data.append({
                    'unique_id': job.unique_id,
                    'job_title': job.job_title,
                    'job_link': job.job_link,
                    'company_name': job.company_name,
                    'sponsorship_status': job.sponsorship_status,
                    'company_type': job.company_type,
                    'date_posted': job.date_posted,
                    'date_recorded': job.date_recorded,
                    'category': f"{job.sponsorship_status} & {job.company_type}",
                    'applied': applied_value
                })
            
            df = pd.DataFrame(data)
            # New jobs are written first so they appear at the top of the file.
            # Write to a temp file then atomically replace, so an interrupted run
            # cannot truncate the existing file (including the manual 'applied' column).
            tmp_file = output_file + '.tmp'
            df.to_csv(tmp_file, index=False, encoding='utf-8-sig')
            os.replace(tmp_file, output_file)
        else:
            # Fallback to standard CSV writer
            tmp_file = output_file + '.tmp'
            with open(tmp_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                # New jobs are written first so they appear at the top of the file.
                for job in all_jobs:
                    # Get 'applied' value from stored values or use empty string for new jobs
                    applied_value = applied_values.get(job.unique_id, '')
                    writer.writerow({
                        'unique_id': job.unique_id,
                        'job_title': job.job_title,
                        'job_link': job.job_link,
                        'company_name': job.company_name,
                        'sponsorship_status': job.sponsorship_status,
                        'company_type': job.company_type,
                        'date_posted': job.date_posted,
                        'date_recorded': job.date_recorded,
                        'category': f"{job.sponsorship_status} & {job.company_type}",
                        'applied': applied_value
                    })
            os.replace(tmp_file, output_file)
        
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

        return {'new_jobs': len(new_jobs), 'total_jobs': len(all_jobs)}
