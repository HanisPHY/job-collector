# Job Collection and Classification System

A Python-based system for collecting job postings from LinkedIn and classifying them based on visa sponsorship likelihood and company type.

## Features

- **Data Collection**: Attempts LinkedIn Jobs API first, falls back to web scraping
- **Visa Sponsorship Classification**: Analyzes job descriptions for sponsorship-related keywords
- **Company Type Classification**: Dynamic database approach loading from multiple sources (GitHub, Fortune 500, unicorn lists) with optional LLM classification
- **CSV Output**: Generates structured CSV with all required columns and category grouping

## Setup

### 1. Create Conda Environment

```bash
conda env create -f environment.yml
conda activate job-classifier
```

Alternatively, create environment manually:

```bash
conda create -n job-classifier python=3.10
conda activate job-classifier
pip install -r requirements.txt
```

### 2. Install ChromeDriver (for web scraping)

The scraping method requires ChromeDriver. Install it based on your system:

**Windows:**
- Download from https://chromedriver.chromium.org/
- Add to PATH or place in project directory

**Using conda:**
```bash
conda install -c conda-forge chromedriver
```

**Using Homebrew (Mac):**
```bash
brew install chromedriver
```

### 3. Optional: Configure API Keys

For enhanced functionality, configure API keys using a `.env` file:

1. Copy the example environment file:
   ```bash
   # Windows (PowerShell)
   Copy-Item .env.example .env
   
   # Mac/Linux
   cp .env.example .env
   ```

2. Edit the `.env` file and add your API keys:
   ```
   LINKEDIN_API_KEY=your_linkedin_api_key
   OPENAI_API_KEY=your_openai_api_key
   ```

**Note:** The `.env` file is automatically loaded by the script (using `python-dotenv`). You don't need to manually export environment variables.

Alternatively, you can set environment variables directly:
```bash
# Windows (PowerShell)
$env:LINKEDIN_API_KEY="your_linkedin_api_key"
$env:OPENAI_API_KEY="your_openai_api_key"

# Mac/Linux
export LINKEDIN_API_KEY="your_linkedin_api_key"
export OPENAI_API_KEY="your_openai_api_key"
```

## Usage

### Basic Usage

```bash
python job_collector.py --query "software engineer" --limit 50
```

### Command Line Options

- `--query`: Job search query (default: "software engineer")
- `--limit`: Maximum number of jobs to collect (default: 50)
- `--output`: Output CSV file path (default: "job_classifications.csv")
- `--time-filter`: Filter jobs by posting time in minutes (e.g., `180` for 3 hours, `1440` for 24 hours). If not specified, all jobs are included.
- `--use-api`: Attempt to use LinkedIn API (requires API key)
- `--no-llm`: Disable LLM-based company classification

### Examples

```bash
# Collect 100 data scientist jobs
python job_collector.py --query "data scientist" --limit 100

# Use custom output file
python job_collector.py --output "my_jobs.csv"

# Filter jobs posted in the last 24 hours (1440 minutes)
python job_collector.py --query "software engineer" --time-filter 1440

# Filter jobs posted in the last 3 hours (180 minutes)
python job_collector.py --query "data scientist" --time-filter 180 --limit 30

# Filter jobs posted in the last 1 hour (60 minutes)
python job_collector.py --query "software engineer" --time-filter 60

# Disable LLM classification (faster, less accurate)
python job_collector.py --no-llm
```

## Scheduled Runs & Daily Report

Collectors are scheduled through `run_logged.bat`, which captures each run's output to
`logs/<script>/<timestamp>.log` and records the run in `logs/runs.jsonl`:

```
run_logged.bat run_ats_collector
```

`daily_report.py` then turns that into `logs/daily/YYYY-MM-DD.md` — what to apply to
today (grouped by company, unapplied only), any health alerts, and a per-run summary:

```
python daily_report.py
```

See [SCHEDULING.md](SCHEDULING.md) for Task Scheduler setup and troubleshooting.

## Output Format

The CSV file contains the following columns:

1. `job_title`: Job title
2. `job_link`: LinkedIn job post URL
3. `sponsorship_status`: `Sponsor` or `Not (Maybe Not) Sponsor`
4. `company_type`: `独角兽/上市公司/Big Tech` or `Others`
5. `category`: Combined category for easy grouping

### Category Groups

Jobs are automatically grouped into four categories:
1. **Sponsor & 独角兽/上市公司/Big Tech**
2. **Not (Maybe Not) Sponsor & 独角兽/上市公司/Big Tech**
3. **Sponsor & Others**
4. **Not (Maybe Not) Sponsor & Others**

The CSV is sorted by these categories for easy filtering.

## Classification Rules

### Visa Sponsorship

The system searches for these keywords in job descriptions:
- `visa`, `sponsor`, `sponsorship`
- `H-1B`, `H1B`, `H1-B`
- `OPT`, `CPT`, `STEM OPT`
- `work authorization`, `work visa`
- `immigration`, `green card`, `permanent residency`

If **at least one** keyword is found → classified as **Sponsor**

### Company Type Classification

The system uses a **dynamic company database** that loads from multiple sources:

1. **Built-in Big Tech List**: Includes major tech companies (Google, Microsoft, Apple, Amazon, Meta, etc.)
2. **GitHub Tech Companies**: Automatically fetches from public GitHub repository
3. **Fortune 500 Companies**: Loads from local `fortune_500_companies.csv` file (if available)
4. **Unicorn Companies**: Loads from local `unicorn_companies.csv` file (if available)
5. **SEC EDGAR API**: Can optionally fetch publicly traded companies (commented out by default due to size)

The database is cached locally in `company_database_cache.json` and refreshes every 30 days automatically.

#### Adding Company Lists

To enhance the database, you can download and add CSV files:

**Fortune 500 Companies:**
- Download from: https://www.gigasheet.com/sample-data/fortune-500-companies
- Save as `fortune_500_companies.csv` in the project directory
- CSV should have a column named `company`, `name`, `Company`, or `Name`

**Unicorn Companies:**
- Download from: https://www.kaggle.com/datasets/ritwikb3/unicorn-companies
- Save as `unicorn_companies.csv` in the project directory
- CSV should have a column named `company`, `name`, `Company`, or `Name`

The system will automatically load these files on the next run.

If a company is not found in the database, the system can optionally use LLM classification (if enabled and API key provided).
Otherwise → classified as **Not (Maybe Not) Sponsor**

### Company Type

Companies are classified as **独角兽/上市公司/Big Tech** if they are:
- Known Big Tech companies (Google, Microsoft, Apple, Amazon, Meta, etc.)
- Unicorn startups (private valuation ≥ $1B)
- Publicly listed companies
- Large, established, and prestigious companies or institutions

Otherwise → classified as **Others**

The system uses a dynamic database that loads from multiple sources (see Company Type Classification section above).

## Limitations and Notes

1. **LinkedIn API**: The official LinkedIn Jobs API requires partnership access. The system will automatically fall back to web scraping.

2. **Web Scraping**: 
   - Requires ChromeDriver installation
   - May be rate-limited by LinkedIn
   - Requires stable internet connection
   - May need manual intervention if LinkedIn changes their HTML structure

3. **LLM Classification**: 
   - Requires OpenAI API key
   - Incurs API costs
   - Can be disabled with `--no-llm` flag

4. **Job Descriptions**: If job descriptions are missing or incomplete, sponsorship classification may be less accurate.

## Troubleshooting

### ChromeDriver Issues

If you encounter ChromeDriver errors:
1. Ensure Chrome/Chromium is installed
2. Check ChromeDriver version matches your Chrome version
3. Try updating: `conda update chromedriver`

### Selenium Issues

If scraping fails:
1. Check internet connection
2. Verify LinkedIn is accessible
3. Try running without `--headless` mode (modify code)
4. Check for LinkedIn login requirements

### API Key Issues

If LLM classification fails:
1. Verify OpenAI API key is set correctly
2. Check API key has sufficient credits
3. Use `--no-llm` to disable LLM features

## Development

### Project Structure

```
.
├── job_collector.py      # Main script
├── requirements.txt      # Pip dependencies
├── environment.yml       # Conda environment
├── README.md            # This file
└── job_classifications.csv  # Output file (generated)
```

### Extending the System

To add new data sources or classification methods:

1. **New Data Source**: Extend `LinkedInCollector` class or create new collector
2. **New Classification**: Add methods to `SponsorshipClassifier` or `CompanyTypeClassifier`
3. **External APIs**: Integrate Crunchbase, SEC filings, etc. in `CompanyTypeClassifier`

## License

This project is for educational purposes. Please respect LinkedIn's Terms of Service when scraping.

