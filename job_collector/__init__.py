"""
Job Collection and Classification System
A modular system for collecting and classifying job postings.
"""

__version__ = "1.0.0"

from .models import JobPosting
from .pipeline.job_pipeline import JobClassificationPipeline

__all__ = ['JobPosting', 'JobClassificationPipeline']
