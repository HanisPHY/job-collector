# Quick Start Guide

## 1. Setup Environment (5 minutes)

### Option A: Using Conda (Recommended)

```bash
# Create environment
conda env create -f environment.yml

# Activate environment
conda activate job-classifier
```

### Option B: Using pip

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## 2. Install ChromeDriver

The web scraping feature requires ChromeDriver.

**Windows:**
```bash
# Using conda
conda install -c conda-forge chromedriver

# Or download manually from https://chromedriver.chromium.org/
```

**Mac:**
```bash
brew install chromedriver
```

**Linux:**
```bash
sudo apt-get install chromium-chromedriver
# or
conda install -c conda-forge chromedriver
```

## 3. Run the System

### Basic Usage

```bash
python job_collector.py --query "software engineer" --limit 20
```

### Filter by Time (Last 24 Hours)

```bash
python job_collector.py --query "software engineer" --time-filter 1440 --limit 50
```

### Filter by Time (Last 3 Hours)

```bash
python job_collector.py --query "data scientist" --time-filter 180 --limit 30
```

### Filter by Time (Any Duration in Minutes)

```bash
# Last 1 hour (60 minutes)
python job_collector.py --query "software engineer" --time-filter 60

# Last 12 hours (720 minutes)
python job_collector.py --query "data scientist" --time-filter 720
```

### With Custom Output

```bash
python job_collector.py --query "data scientist" --limit 50 --output "my_jobs.csv"
```

### Without LLM (Faster)

```bash
python job_collector.py --query "product manager" --no-llm
```

## 4. Test the System

Before scraping real data, test the classification logic:

```bash
python test_sample.py
```

This will create `test_output.csv` with sample data.

## 5. Optional: Configure API Keys

For enhanced company classification, configure API keys using a `.env` file:

**Recommended: Use .env file**

1. Copy the example file:
   ```bash
   # Windows (PowerShell)
   Copy-Item .env.example .env
   
   # Mac/Linux
   cp .env.example .env
   ```

2. Edit `.env` and add your keys:
   ```
   LINKEDIN_API_KEY=your_linkedin_api_key
   OPENAI_API_KEY=your_openai_api_key
   ```

The script will automatically load these from the `.env` file.

**Alternative: Set environment variables directly**

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY="your-key-here"
```

**Windows (CMD):**
```cmd
set OPENAI_API_KEY=your-key-here
```

**Mac/Linux:**
```bash
export OPENAI_API_KEY="your-key-here"
```
```
OPENAI_API_KEY=your-key-here
```

## 6. View Results

Open the generated CSV file (e.g., `job_classifications.csv`) in Excel or any spreadsheet application.

The CSV contains:
- `job_title`: Job title
- `job_link`: LinkedIn URL
- `sponsorship_status`: Sponsor or Not (Maybe Not) Sponsor
- `company_type`: 独角兽/上市公司/Big Tech or Others
- `category`: Combined category for easy filtering

## Troubleshooting

### ChromeDriver Not Found
- Ensure Chrome/Chromium is installed
- Check ChromeDriver version matches Chrome version
- Add ChromeDriver to PATH

### Scraping Fails
- Check internet connection
- Verify LinkedIn is accessible
- LinkedIn may require login (modify code to add login)

### LLM Classification Fails
- Verify OpenAI API key is set
- Check API key has credits
- Use `--no-llm` flag to disable

## Next Steps

- Read `README.md` for detailed documentation
- Check `example_usage.py` for programmatic usage examples
- Customize classification rules in `job_collector.py`

