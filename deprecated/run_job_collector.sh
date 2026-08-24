#!/bin/bash
# Shell script to run job_collector.py with conda environment
# This script can be used with cron on Linux/Mac/WSL

# Change to the script directory
cd "$(dirname "$0")"

# Initialize conda (adjust path if needed)
# For Anaconda:
# source ~/anaconda3/etc/profile.d/conda.sh
# For Miniconda:
# source ~/miniconda3/etc/profile.d/conda.sh
# For conda installed via Homebrew (Mac):
# source /opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh

# Try to find conda automatically
if [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/anaconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
    source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "/opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh" ]; then
    source "/opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh"
else
    # Try to use conda from PATH
    eval "$(conda shell.bash hook)"
fi

# Activate conda environment and run the script
conda activate job-classifier
python job_collector.py --query "software engineer" --limit 50 --time-filter 30

# Optional: Log the output to a file (uncomment to enable)
# python job_collector.py --query "software engineer" --limit 50 --time-filter 30 >> job_collector.log 2>&1

