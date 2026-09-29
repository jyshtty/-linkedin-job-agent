# LinkedIn Job Search Agent - README

## Overview

The LinkedIn Job Search Agent is an automated tool that searches for job postings on LinkedIn based on specified criteria and stores the results in a structured CSV format. The agent is designed to help job seekers efficiently track and manage job opportunities from LinkedIn.

## Features

- 🔍 **Automated Job Search**: Searches LinkedIn jobs using public API (no authentication required)
- 📅 **Past Week Filter**: Automatically filters jobs posted in the last 7 days
- 🇮🇳 **India Location Filter**: Searches jobs across all cities in India (Bangalore, Mumbai, Pune, Hyderabad, Chennai, etc.)
- 📊 **CSV Export**: Saves results in a structured CSV file with serial numbers and job details
- 🔄 **Duplicate Prevention**: Automatically filters out duplicate jobs based on LinkedIn Job ID
- 📝 **Flexible Search**: Search by specific job role and/or company, or use predefined roles from file
- 🎯 **Multiple Role Support**: Can search for multiple job roles in a single run

## Project Structure

```
linkedin-job-agent/
├── main.py                      # Main entry point for the agent
├── linkedin_scraper.py          # Core scraper logic
├── command_list.json            # Command definitions and descriptions
├── .env                         # Environment variables (credentials)
├── .env.example                 # Template for environment variables
├── pyproject.toml               # Project dependencies
├── interested_job_role/
│   └── job_role.txt            # List of job roles to search
├── searched_job_list/
│   └── searched_jobs.csv       # Output CSV with search results
└── README_SEARCH_AGENT.md      # This file
```

## Installation

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Step 1: Clone or Navigate to Project

```bash
cd /Users/ajaykumar_shetty/PycharmProjects/-linkedin-job-agent
```

### Step 2: Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -e .
```

This will install:
- `beautifulsoup4>=4.12.0` - HTML parsing
- `pandas>=2.0.0` - Data manipulation and CSV handling
- `requests>=2.31.0` - HTTP requests to LinkedIn API
- `python-dotenv>=1.0.0` - Environment variable management
- `linkedin-api>=2.0.0` - LinkedIn API wrapper (backup)

## Configuration

### 1. Environment Variables (.env file)

Create a `.env` file in the project root:

```bash
LINKEDIN_EMAIL=jyshtty@gmail.com
LINKEDIN_PASSWORD=Lilly@123
```

**Note**: Currently, the scraper uses LinkedIn's public API and doesn't require authentication. These credentials are kept for potential future authenticated features.

### 2. Job Roles Configuration

Edit `interested_job_role/job_role.txt` to define default job roles:

```
Forward deployed engineer
Senior Software Engineer
Gen AI Engineer
AI Engineer
```

- One job role per line
- These roles are used when no `--job_role` argument is provided
- You can add or remove roles as needed

## Usage

### Basic Commands

The agent is invoked through the `main.py` script with the `search` command.

### Command Syntax

```bash
python main.py search [OPTIONS]
```

### Options

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `--job_role` | string | No | Specific job role to search for |
| `--company` | string | No | Company name to filter results |

### Usage Examples

#### 1. Search All Roles from File

Searches for all job roles listed in `interested_job_role/job_role.txt`:

```bash
python main.py search
```

**Output**:
- Searches for: Forward deployed engineer, Senior Software Engineer, Gen AI Engineer, AI Engineer
- Location: India (all cities)
- Time filter: Past week

#### 2. Search Specific Role

Search for a single specific job role:

```bash
python main.py search --job_role "AI Engineer"
```

**Output**:
- Searches only for: AI Engineer
- Location: India (all cities)
- Time filter: Past week

#### 3. Search Role at Specific Company

Search for a role at a particular company:

```bash
python main.py search --job_role "Software Engineer" --company "Google"
```

**Output**:
- Searches for: Software Engineer at Google
- Location: India (all cities)
- Time filter: Past week

#### 4. Search Multiple Companies

For multiple companies, run separate searches:

```bash
python main.py search --job_role "Data Scientist" --company "Amazon"
python main.py search --job_role "Data Scientist" --company "Microsoft"
```

## Output Format

### CSV File Structure

Results are saved in `searched_job_list/searched_jobs.csv` with the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| `serial_number` | Sequential number for each job | 1, 2, 3... |
| `linkedin_job_id` | Unique LinkedIn job identifier | `4454310283` |
| `linkedin_link` | Direct link to job on LinkedIn | `https://www.linkedin.com/jobs/view/4454310283` |
| `company_website_link` | Link to job on company website | `N/A` (not available in public search) |
| `job_title` | Job title/position | `Senior AI Engineer` |
| `company` | Company name | `Google` |
| `location` | Job location | `Bengaluru, Karnataka, India` |
| `posted_date` | Date job was posted | `2026-09-28` |
| `search_role` | Role keyword used in search | `AI Engineer` |

### Sample CSV Output

```csv
serial_number,linkedin_job_id,linkedin_link,company_website_link,job_title,company,location,posted_date,search_role
1,4454310283,https://www.linkedin.com/jobs/view/4454310283,N/A,Senior AI Engineer,Google,Bengaluru Karnataka India,2026-09-28,AI Engineer
2,4461654265,https://www.linkedin.com/jobs/view/4461654265,N/A,AI/ML Engineer,Amazon,Hyderabad Telangana India,2026-09-27,AI Engineer
```

### Console Output

When running the search, you'll see:

```
Searching: AI Engineer in India
Found 10 jobs

Saved 10 jobs to CSV

====================================================================================================
                                           SEARCH RESULTS                                           
====================================================================================================
 serial_number           linkedin_job_id company_website_link
             1            4454310283                  N/A
             2            4461654265                  N/A
...
====================================================================================================
```

## How It Works

### Technical Flow

1. **Initialization**
   - Creates `searched_job_list/` directory if it doesn't exist
   - Initializes HTTP session with appropriate headers

2. **Job Role Determination**
   - If `--job_role` provided: uses that single role
   - If not provided: reads all roles from `interested_job_role/job_role.txt`

3. **Search Execution**
   - For each job role:
     - Constructs search URL with parameters:
       - `keywords`: job role
       - `location`: India
       - `f_TPR`: Past week filter (timestamp-based)
       - `f_C`: Company filter (if provided)
     - Makes HTTP GET request to LinkedIn jobs API
     - Parses HTML response using BeautifulSoup

4. **Data Extraction**
   - Extracts from each job card:
     - Job ID (from URL)
     - Job title
     - Company name
     - Location
     - Posted date
     - LinkedIn job link

5. **Duplicate Prevention**
   - Loads existing CSV (if exists)
   - Filters out jobs with duplicate `linkedin_job_id`
   - Only adds new unique jobs

6. **Data Storage**
   - Converts to pandas DataFrame
   - Adds serial numbers
   - Saves to CSV with proper formatting

7. **Display Results**
   - Shows summary table in console
   - Displays serial number, job ID, and company website link

### Search Parameters Explained

#### Past Week Filter (`f_TPR`)

```python
past_week_seconds = int((datetime.now() - timedelta(days=7)).timestamp())
params['f_TPR'] = f'r{past_week_seconds}'
```

- Calculates Unix timestamp for 7 days ago
- LinkedIn uses this to filter recent jobs
- Format: `r<timestamp>` where r = recent

#### Location Filter

```python
params['location'] = 'India'
```

- Searches across all cities in India
- Includes: Bangalore, Mumbai, Pune, Hyderabad, Chennai, Delhi, etc.
- LinkedIn automatically expands to all sub-locations

#### Company Filter

```python
if company:
    params['f_C'] = company
```

- Filters results to specific company
- Optional parameter
- Must match company name on LinkedIn

## Command List Definition

The agent's commands are defined in `command_list.json`:

```json
{
  "search": {
    "description": "Search for jobs on LinkedIn for a specific role and company. If job role and company are not provided as command-line arguments, job roles will be taken from the interested_job_role file.",
    "arguments": [
      {
        "name": "job_role",
        "type": "string",
        "required": false,
        "description": "The job role/title to search for (e.g., 'Software Engineer', 'Data Scientist')"
      },
      {
        "name": "company",
        "type": "string",
        "required": false,
        "description": "The company name to search jobs for"
      }
    ],
    "usage": "python main.py search [--job_role <role>] [--company <company>]"
  }
}
```

## Rate Limiting & Best Practices

### Request Delays

```python
time.sleep(2)  # 2-second delay between role searches
```

- 2-second delay between each job role search
- Prevents overwhelming LinkedIn's servers
- Reduces risk of being rate-limited or blocked

### Best Practices

1. **Don't run searches too frequently**: Wait at least 5-10 minutes between full searches
2. **Use specific roles**: More specific = better results (e.g., "Senior Python Developer" vs "Developer")
3. **Check results regularly**: Jobs posted in past week expire quickly
4. **Backup CSV file**: Keep backups of your searched_jobs.csv

## Troubleshooting

### Issue: No jobs found

**Possible Causes**:
1. Too specific search criteria
2. No jobs posted in past week for that role/company combination
3. Network connectivity issues

**Solutions**:
- Try broader job role keywords
- Remove company filter
- Check internet connection
- Verify LinkedIn is accessible

### Issue: Duplicate jobs appearing

**Possible Causes**:
1. CSV file was manually edited and IDs were changed
2. File was deleted and recreated

**Solutions**:
- Delete `searched_job_list/searched_jobs.csv` and run fresh search
- Don't manually edit the `linkedin_job_id` column

### Issue: HTTP Errors (403, 429)

**Possible Causes**:
1. Rate limiting by LinkedIn
2. IP address temporarily blocked
3. User-Agent detection

**Solutions**:
- Wait 30-60 minutes before retrying
- Use VPN to change IP address
- Reduce search frequency

### Issue: SSL/TLS Warnings

**Warning Message**:
```
NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+
```

**Impact**: Does not affect functionality

**Solutions** (optional):
- Upgrade system OpenSSL
- Ignore the warning (safe to do so)

### Issue: Import errors

**Error**: `ModuleNotFoundError: No module named 'linkedin_scraper'`

**Solutions**:
1. Ensure virtual environment is activated
2. Reinstall dependencies: `pip install -e .`
3. Check you're in the correct directory

## Limitations

1. **Public API Only**: Uses LinkedIn's public job search, not authenticated API
   - Cannot access full job descriptions
   - Limited to publicly available job data
   - Company website links are not available

2. **Rate Limiting**: LinkedIn may block excessive requests
   - Implement delays between searches
   - Don't automate too frequently

3. **Job Count**: Returns approximately 10-50 jobs per role
   - LinkedIn limits results in public search
   - Not guaranteed to return all matching jobs

4. **Location Fixed**: Currently hardcoded to India
   - Can be modified in `linkedin_scraper.py` if needed
   - No command-line option for different locations yet

5. **Past Week Only**: Searches only jobs from last 7 days
   - Cannot search older jobs
   - Filter is fixed in code

## Future Enhancements

### Planned Features

1. **Email Notifications**
   - Send email when new jobs are found
   - Daily digest of new opportunities

2. **Job Alerts**
   - Save search criteria as "alerts"
   - Automatically run searches on schedule

3. **Advanced Filtering**
   - Salary range filters
   - Experience level filters
   - Remote/On-site/Hybrid filters

4. **Job Application Tracking**
   - Mark jobs as "Applied", "Interested", "Rejected"
   - Add notes and status updates

5. **Analytics Dashboard**
   - Visualize job trends
   - Top companies hiring
   - Most common skills required

6. **LinkedIn API Integration**
   - Full job descriptions
   - Company website links
   - Apply directly through API

7. **Resume Matching**
   - Match jobs against your resume
   - Score compatibility
   - Suggest relevant applications

## Development Notes

### Code Structure

**`linkedin_scraper.py`** - Main scraper class:
- `LinkedInJobScraper.__init__()` - Initialization
- `LinkedInJobScraper._read_job_roles()` - Read roles from file
- `LinkedInJobScraper.search_jobs()` - Main search logic
- `LinkedInJobScraper._save_jobs()` - Save and deduplicate results

**`main.py`** - CLI interface:
- Argument parsing
- Agent initialization
- Result display

### Dependencies Explained

1. **beautifulsoup4**: Parses HTML from LinkedIn job pages
2. **pandas**: Data manipulation, CSV handling, deduplication
3. **requests**: HTTP requests to LinkedIn
4. **python-dotenv**: Load environment variables from .env
5. **linkedin-api**: Backup for authenticated searches (not currently used)

### Key Variables

```python
base_url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
searched_jobs_file = 'searched_job_list/searched_jobs.csv'
past_week_seconds = int((datetime.now() - timedelta(days=7)).timestamp())
```

## Security & Privacy

### Credentials Storage

- Credentials stored in `.env` file (not tracked by git)
- Add `.env` to `.gitignore` to prevent accidental commits
- Never share `.env` file publicly

### Data Privacy

- All job data is public information from LinkedIn
- No personal data is collected or stored
- CSV files stored locally only

## Support & Contribution

### Reporting Issues

If you encounter issues:
1. Check the Troubleshooting section above
2. Verify your Python version and dependencies
3. Check LinkedIn accessibility in browser
4. Document the error message and steps to reproduce

### Modifying the Agent

To customize the agent:

**Change location filter**:
```python
# In linkedin_scraper.py, line ~24
params['location'] = 'United States'  # Instead of 'India'
```

**Change time filter**:
```python
# In linkedin_scraper.py, line ~22
past_week_seconds = int((datetime.now() - timedelta(days=30)).timestamp())  # 30 days instead of 7
```

**Add more job details**:
```python
# In linkedin_scraper.py, after line ~50, add more parsing logic
salary_tag = card.find('span', class_='salary-range')
salary = salary_tag.text.strip() if salary_tag else 'N/A'
```

## Version History

- **v0.1.0** (2026-09-29)
  - Initial release
  - Basic job search functionality
  - CSV export
  - India location filter
  - Past week time filter
  - Duplicate prevention

## License

This project is for personal use and educational purposes.

## Disclaimer

This tool is not affiliated with LinkedIn. Use responsibly and in accordance with LinkedIn's Terms of Service. Excessive scraping may result in your IP being blocked by LinkedIn.

---

**Last Updated**: 2026-09-29  
**Author**: Ajay Kumar Shetty  
**Contact**: jyshtty@gmail.com
