"""
Utility functions for date formatting and ID generation.
"""

import re
import time
import hashlib
from datetime import datetime
from typing import Optional

try:
    import pandas as pd
except ImportError:
    pd = None


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
