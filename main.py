"""
Main entry point for job collection and classification.
"""

import os
import time

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, continue without it
    pass

from job_collector import JobClassificationPipeline


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
