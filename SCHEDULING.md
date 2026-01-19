# Scheduling the Job Collector

This guide explains how to set up automated scheduling for the job collector to run every 30 minutes.

## Windows Task Scheduler (Recommended for Windows)

Since you're on Windows, use Task Scheduler instead of cron.

### Step 1: Create a Batch Script

A batch script `run_job_collector.bat` has been created for you. You can customize it by editing the command line arguments:

- `--query`: Job search query (default: "software engineer")
- `--limit`: Maximum number of jobs to collect (default: 50)
- `--time-filter`: Filter jobs by posting time in minutes (30 = last 30 minutes)
- `--output`: Output CSV file path (default: "job_classifications.csv")
- `--no-llm`: Disable LLM-based company classification (optional)

### Step 2: Set Up Windows Task Scheduler

#### Method A: Using GUI (Easiest)

1. **Open Task Scheduler**:
   - Press `Win + R`, type `taskschd.msc`, and press Enter
   - Or search for "Task Scheduler" in the Start menu

2. **Create Basic Task**:
   - Click "Create Basic Task..." in the right panel
   - Name: `Job Collector - Every 30 Minutes`
   - Description: `Runs job collector script every 30 minutes`
   - Click Next

3. **Set Trigger**:
   - Trigger: `Daily`
   - Start date: Today's date
   - Start time: Current time or desired start time
   - Recur every: `1 days`
   - Click Next

4. **Set Action**:
   - Action: `Start a program`
   - Program/script: Browse and select `run_job_collector.bat`
   - Start in: Browse and select your project directory (e.g., `D:\OneDrive\work\school\project\Job`)
   - Click Next

5. **Finish**:
   - Check "Open the Properties dialog for this task when I click Finish"
   - Click Finish

6. **Configure Advanced Settings**:
   - In the Properties dialog, go to the **Triggers** tab
   - Select your trigger and click **Edit**
   - Check "Repeat task every:" and set to `30 minutes`
   - Set "for a duration of:" to `Indefinitely`
   - Click OK

7. **Configure Additional Settings** (Optional but Recommended):
   - Go to the **General** tab:
     - Check "Run whether user is logged on or not" (if you want it to run in background)
     - Or keep "Run only when user is logged on" (simpler, but requires you to be logged in)
   - Go to the **Settings** tab:
     - Check "Allow task to be run on demand"
     - Check "Run task as soon as possible after a scheduled start is missed"
     - Set "If the task fails, restart every:" to `10 minutes` (optional)
   - Click OK

#### Method B: Using PowerShell (Advanced)

Run PowerShell as Administrator and execute:

```powershell
$action = New-ScheduledTaskAction -Execute "D:\OneDrive\work\school\project\Job\run_job_collector.bat" -WorkingDirectory "D:\OneDrive\work\school\project\Job"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 365)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName "Job Collector - Every 30 Minutes" -Action $action -Trigger $trigger -Settings $settings -Description "Runs job collector script every 30 minutes"
```

### Step 3: Test the Task

1. In Task Scheduler, find your task
2. Right-click and select "Run"
3. Check if it executes successfully
4. Verify that `job_classifications.csv` is updated

### Step 4: View Task History

1. In Task Scheduler, select your task
2. Click "History" tab at the bottom to see execution logs
3. Check for any errors

## Linux/Mac/WSL Cron (Alternative)

If you're using Linux, Mac, or Windows Subsystem for Linux (WSL), you can use cron.

### Step 1: Create a Shell Script

Create a file `run_job_collector.sh`:

```bash
#!/bin/bash
# Change to the script directory
cd "$(dirname "$0")"

# Activate conda environment and run the script
source $(conda info --base)/etc/profile.d/conda.sh
conda activate job-classifier
python job_collector.py --query "software engineer" --limit 50 --time-filter 30

# Optional: Log output
# python job_collector.py --query "software engineer" --limit 50 --time-filter 30 >> job_collector.log 2>&1
```

Make it executable:
```bash
chmod +x run_job_collector.sh
```

### Step 2: Set Up Cron Job

1. Open crontab:
   ```bash
   crontab -e
   ```

2. Add the following line to run every 30 minutes:
   ```cron
   */30 * * * * /path/to/your/project/run_job_collector.sh
   ```

   Replace `/path/to/your/project/` with your actual project path, for example:
   ```cron
   */30 * * * * /home/username/projects/Job/run_job_collector.sh
   ```

3. Save and exit (in vi: press `Esc`, type `:wq`, press Enter)

### Cron Schedule Format

The format is: `minute hour day month weekday`

- `*/30 * * * *` = Every 30 minutes
- `0 */2 * * *` = Every 2 hours
- `0 9 * * *` = Every day at 9:00 AM
- `0 9 * * 1-5` = Every weekday at 9:00 AM

## Customizing the Schedule

### Change Frequency

**Windows Task Scheduler:**
- Edit the task → Triggers → Edit → Change "Repeat task every" to your desired interval

**Cron:**
- Edit crontab and change the schedule:
  - Every 15 minutes: `*/15 * * * *`
  - Every hour: `0 * * * *`
  - Every 2 hours: `0 */2 * * *`

### Change Command Arguments

Edit `run_job_collector.bat` (Windows) or `run_job_collector.sh` (Linux/Mac) to modify:
- Search query: `--query "your query"`
- Job limit: `--limit 100`
- Time filter: `--time-filter 60` (last 60 minutes)
- Output file: `--output "custom_output.csv"`
- Disable LLM: Add `--no-llm` flag

## Troubleshooting

### Windows Task Scheduler Issues

1. **Task doesn't run**:
   - Check if conda is in PATH
   - Try running the batch file manually first
   - Check Task Scheduler History for errors
   - Ensure "Start in" directory is set correctly

2. **Conda not found**:
   - Add conda to system PATH, or
   - Modify `run_job_collector.bat` to use full path to conda:
     ```batch
     C:\Users\YourUsername\anaconda3\Scripts\activate.bat job-classifier
     ```

3. **Python not found**:
   - Ensure conda environment is activated correctly
   - Check that Python is installed in the conda environment

### Cron Issues

1. **Script doesn't run**:
   - Check cron logs: `grep CRON /var/log/syslog` (Linux) or check system logs
   - Ensure script has execute permissions: `chmod +x run_job_collector.sh`
   - Use absolute paths in the script

2. **Conda not found in cron**:
   - Use full path to conda in the script
   - Or source conda initialization in the script:
     ```bash
     source ~/anaconda3/etc/profile.d/conda.sh
     ```

3. **Environment variables not set**:
   - Set them in the script before activating conda:
     ```bash
     export OPENAI_API_KEY="your-key-here"
     ```

## Logging

To log output to a file, modify the batch/shell script:

**Windows (`run_job_collector.bat`):**
```batch
call conda activate job-classifier && python job_collector.py --query "software engineer" --limit 50 --time-filter 30 >> job_collector.log 2>&1
```

**Linux/Mac (`run_job_collector.sh`):**
```bash
python job_collector.py --query "software engineer" --limit 50 --time-filter 30 >> job_collector.log 2>&1
```

This will append all output (including errors) to `job_collector.log`.

## Notes

- The `--time-filter 30` option filters jobs posted in the last 30 minutes, which works well with a 30-minute schedule
- If you change the schedule frequency, adjust `--time-filter` accordingly
- Ensure your computer is on and not sleeping for scheduled tasks to run
- For Windows, if you want tasks to run when the computer is sleeping, you may need to prevent sleep or use a different approach

