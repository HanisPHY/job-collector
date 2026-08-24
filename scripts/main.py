"""
Main entry point for job collection and classification.
"""

import os
import time
import traceback

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available, continue without it
    pass

import sys

import paths
import run_log

_this_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.remove(_this_dir)
try:
    from job_collector import JobClassificationPipeline
finally:
    sys.path.insert(0, _this_dir)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Collect and classify LinkedIn jobs')
    parser.add_argument('--query', type=str, default='software engineer',
                       help='Job search query (default: software engineer)')
    parser.add_argument('--limit', type=int, default=50,
                       help='Maximum number of jobs to collect (default: 50)')
    parser.add_argument('--output', type=str, default=str(paths.DATA_DIR / 'job_classifications.csv'),
                       help='Output CSV file (default: data/job_classifications.csv)')
    parser.add_argument('--no-llm', action='store_true',
                       help='Disable LLM-based company classification')
    parser.add_argument('--time-filter', type=int, default=None, metavar='MINUTES',
                       help='Filter jobs by posting time in minutes (e.g., 180 for 3 hours, 1440 for 24 hours)')
    parser.add_argument('--exclude-senior', action='store_true',
                       help='Drop senior/staff/principal/lead/manager titles (recommended for new grad searches)')
    
    args = parser.parse_args()
    
    # Validate time filter if provided
    if args.time_filter is not None and args.time_filter <= 0:
        parser.error("--time-filter must be a positive integer (minutes)")
    
    # Record overall start time
    overall_start_time = time.time()

    # Emitted exactly once in `finally`, so every path leaves a record in
    # logs/runs.jsonl - including "collected nothing", which is the silent
    # failure mode the daily report exists to catch. The new-grad batch calls
    # this script 9 times per run; all 9 records share one JOB_RUN_ID.
    metrics = {
        'exit_code': 0,
        'query': args.query,
        'time_filter': args.time_filter,
        'output': args.output,
        'new_jobs': 0,
    }
    pipeline = None
    try:
        # Initialize pipeline
        pipeline = JobClassificationPipeline(
            use_llm=not args.no_llm,
            openai_key=os.getenv('OPENAI_API_KEY'),
            exclude_senior=args.exclude_senior
        )

        # Process jobs (pass output file to check for existing jobs)
        jobs = pipeline.process(args.query, args.limit, args.time_filter, output_file=args.output)

        if jobs:
            # Save to CSV
            save_stats = pipeline.save_to_csv(jobs, args.output)
            metrics.update(save_stats or {})

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
                if cost_summary['cost_usd'] is None:
                    print(f"LLM API cost: unpriced model '{cost_summary['model']}' "
                          f"({cost_summary['total_tokens']:,} tokens)")
                else:
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
    except BaseException as e:
        metrics['exit_code'] = 1
        metrics['error'] = type(e).__name__
        metrics['error_message'] = str(e)[:500]
        metrics['traceback'] = ''.join(traceback.format_exc()).strip()[-2000:]
        raise
    finally:
        if pipeline is not None:
            metrics.update(pipeline.last_run_stats)
            if pipeline.cost_tracker and pipeline.cost_tracker.api_calls:
                cost = pipeline.cost_tracker.get_summary()
                metrics['llm_cost_usd'] = cost['cost_usd']
                metrics['llm_api_calls'] = cost['api_calls']
                metrics['llm_tokens'] = cost['total_tokens']
                metrics['llm_model'] = cost['model']
        metrics['elapsed_s'] = round(time.time() - overall_start_time, 1)
        run_log.run_summary('newgrad_linkedin', **metrics)


if __name__ == "__main__":
    main()
