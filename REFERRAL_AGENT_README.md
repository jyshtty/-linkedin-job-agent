# 🤝 LinkedIn Referral Agent

## Overview

The Referral Agent automates the process of finding employees at target companies and generating personalized referral request messages.

## Features

✅ **Automated Employee Search** - Finds employees at target company on LinkedIn  
✅ **Personalized Messages** - Generates customized referral requests  
✅ **Configurable** - Set number of referrals per job  
✅ **Template-Based** - Customize your referral message template  
✅ **Logging** - Tracks all referral requests in CSV  
✅ **Backup Contacts** - Provides additional contacts beyond your target  

---

## Quick Start

### 1. Search for Jobs
```bash
python main.py search --job_role "DevOps Engineer"
```

### 2. Request Referrals
```bash
python main.py request_referral 1
```

This will:
1. Find employees at the company (Job #1)
2. Generate personalized referral messages
3. Display messages ready to send
4. Log all requests to `referral_log.csv`

---

## Configuration

### `referral_config.txt`

Edit this file to customize your settings:

```ini
# Number of referral requests per job
referrals_per_job=2

# Your professional information
your_title=Senior Software Engineer
your_expertise=DSA and System Design
```

**Parameters:**
- `referrals_per_job`: How many referral requests to generate (default: 2)
- `your_title`: Your professional title
- `your_expertise`: Your key skills/expertise areas

---

## Message Template

### `referral_template.txt`

Customize your referral message template:

```
Hi {name},

I'm a {your_title} with strong expertise in {your_expertise}.

I've been following {company} and would love to be part of the team — would you be open to referring me for the {job_title} position?

Job link: {job_link}

Even a referral submission makes a huge difference — really appreciate any help!

Best regards
```

**Available Variables:**
- `{name}` - Employee's first name
- `{your_title}` - Your title from config
- `{your_expertise}` - Your expertise from config
- `{company}` - Target company name
- `{job_title}` - Job position title
- `{job_link}` - LinkedIn job posting link

---

## How It Works

### Step 1: Employee Discovery

The agent searches LinkedIn for employees at the target company:
- Searches by company name
- Extracts profile information (name, title, profile link)
- Fetches 2x your target number (for backup contacts)

### Step 2: Message Generation

For each employee:
- Extracts first name
- Populates template with job details
- Generates personalized message

### Step 3: Display & Log

- Displays formatted messages ready to copy
- Shows profile links for each contact
- Logs all referrals to `referral_log.csv`
- Provides backup contacts list

---

## Usage Examples

### Example 1: Basic Usage
```bash
# Request 2 referrals for job #1 (default)
python main.py request_referral 1
```

### Example 2: Change Configuration
```bash
# Edit config to request 5 referrals
echo "referrals_per_job=5" > referral_config.txt

# Run agent
python main.py request_referral 3
```

### Example 3: Customize Template
```bash
# Edit template file
nano referral_template.txt

# Run agent with new template
python main.py request_referral 5
```

---

## Output

### Console Output

```
================================================================================
REFERRAL AGENT - JOB #1
================================================================================

Job: DevOps Engineer - GitLab Enterprise
Company: Luxoft
Location: Mumbai, Maharashtra, India
LinkedIn Link: https://www.linkedin.com/jobs/view/...

Target: 2 referral request(s)

🔍 Searching for employees at Luxoft...
   ✓ Found: Vinay Kumar - Senior Engineering Manager
   ✓ Found: Priya Sharma - Lead DevOps Engineer
   ✓ Found: Rahul Singh - Engineering Manager
   ✓ Found: Anita Desai - Principal Engineer

✅ Found 4 employees at Luxoft

================================================================================
REFERRAL MESSAGES (Top 2 contacts)
================================================================================

────────────────────────────────────────────────────────────────────────────────
REFERRAL #1
────────────────────────────────────────────────────────────────────────────────
To: Vinay Kumar
Title: Senior Engineering Manager
Profile: https://www.linkedin.com/in/vinay-kumar-...

Message:
────────────────────────────────────────────────────────────────────────────────
Hi Vinay,

I'm a Senior Software Engineer with strong expertise in DSA and System Design.

I've been following Luxoft and would love to be part of the team — would you be 
open to referring me for the DevOps Engineer - GitLab Enterprise position?

Job link: https://www.linkedin.com/jobs/view/devops-engineer-gitlab-enterprise...

Even a referral submission makes a huge difference — really appreciate any help!

Best regards
────────────────────────────────────────────────────────────────────────────────

[... Referral #2 ...]

================================================================================
BACKUP CONTACTS (2 additional)
================================================================================

1. Rahul Singh - Engineering Manager
   https://www.linkedin.com/in/rahul-singh-...
2. Anita Desai - Principal Engineer
   https://www.linkedin.com/in/anita-desai-...

================================================================================
✅ REFERRAL REQUESTS PREPARED!
================================================================================

📋 Next Steps:
   1. Copy the messages above
   2. Visit each profile link
   3. Send connection request with the message
   4. Or message directly if already connected

💾 All referrals logged to: referral_log.csv
================================================================================
```

---

## Referral Log

All referrals are tracked in `referral_log.csv`:

| timestamp | job_serial | company | job_title | employee_name | employee_title | profile_link | sent |
|-----------|------------|---------|-----------|---------------|----------------|--------------|------|
| 2026-10-01 10:30:00 | 1 | Luxoft | DevOps Engineer | Vinay Kumar | Senior Engineering Manager | https://... | No |
| 2026-10-01 10:30:01 | 1 | Luxoft | DevOps Engineer | Priya Sharma | Lead DevOps Engineer | https://... | No |

---

## Tips for Success

### 1. **Personalize Further**
While the template is personalized, consider adding:
- Specific mutual connections
- Relevant projects you've worked on
- Why you're specifically interested in that company

### 2. **Timing**
- Send requests during business hours
- Avoid weekends
- Space out requests (don't spam)

### 3. **Profile Optimization**
Before requesting referrals:
- Update your LinkedIn profile
- Add relevant skills
- Ensure your experience is current

### 4. **Follow Up**
- Thank people who respond
- Update referral_log.csv with `sent=Yes` after sending
- Keep track of responses

### 5. **Be Genuine**
- Only request referrals for jobs you're genuinely interested in
- Research the company before reaching out
- Be respectful of people's time

---

## LinkedIn Login Required

The agent requires LinkedIn login to search for employees:

1. Browser window will open automatically
2. Log in to your LinkedIn account
3. Agent will continue automatically
4. Login session is remembered (cookies)

**First Time:**
- Manual login required
- Takes ~30 seconds

**Subsequent Runs:**
- May reuse session (if cookies valid)
- Or may require re-login

---

## Privacy & Ethics

⚠️ **Important Notes:**

1. **Rate Limiting** - LinkedIn may block excessive requests
2. **Terms of Service** - Use responsibly within LinkedIn's ToS
3. **Personal Data** - Employee data is publicly available on LinkedIn
4. **Consent** - Only reach out to people who accept connection requests
5. **No Spam** - Space out your referral requests

---

## Troubleshooting

### "No employees found"
- **Solution:** Company name might not match exactly. Try variations.
- **Check:** Is the company name spelled correctly in searched_jobs.csv?

### "Login timeout"
- **Solution:** Log in faster within the 120-second window
- **Alternative:** Close browser and try again

### "Browser not opening"
- **Solution:** Install Chrome WebDriver: `pip install selenium webdriver-manager`
- **Check:** Is Chrome installed on your system?

### Template not working
- **Solution:** Check template syntax - variables must be in `{curly_braces}`
- **Verify:** File is named exactly `referral_template.txt`

---

## Advanced Usage

### Standalone Script

You can also run the referral agent directly:

```bash
python referral_agent.py 1
```

### Integration with Other Tools

```python
from referral_agent import ReferralAgent

# Create agent
agent = ReferralAgent()

# Find employees
employees = agent.find_company_employees("Luxoft", limit=5)

# Generate message for specific employee
job = agent._get_job_by_serial(1)
config = agent._load_config()
message = agent.generate_referral_message(employees[0], job, config)
```

---

## Files Created

| File | Purpose |
|------|---------|
| `referral_agent.py` | Main agent code |
| `referral_config.txt` | Configuration settings |
| `referral_template.txt` | Message template |
| `referral_log.csv` | Request tracking log |

---

## Complete Workflow

```bash
# 1. Search for jobs
python main.py search --job_role "DevOps Engineer"

# 2. Review search results
# searched_job_list/searched_jobs.csv

# 3. Tailor resume (optional)
python main.py tailor_resume 1

# 4. Request referrals
python main.py request_referral 1

# 5. Copy messages and send via LinkedIn

# 6. Track responses in referral_log.csv
```

---

## Best Practices

### Do's ✅
- ✅ Personalize the template for each company
- ✅ Update your LinkedIn profile first
- ✅ Research the company before reaching out
- ✅ Thank people who help you
- ✅ Keep track of your requests
- ✅ Follow up professionally

### Don'ts ❌
- ❌ Don't spam people with requests
- ❌ Don't use the same message for everyone
- ❌ Don't request referrals for jobs you're not interested in
- ❌ Don't forget to thank people
- ❌ Don't send too many requests at once
- ❌ Don't be pushy if someone doesn't respond

---

## Future Enhancements

Planned features:
- [ ] Auto-send messages via LinkedIn API
- [ ] Track message responses
- [ ] A/B test different templates
- [ ] AI-powered message personalization
- [ ] Integration with applicant tracking

---

## Support

For issues or questions:
1. Check this README
2. Review `referral_log.csv` for errors
3. Open an issue on GitHub

---

**Happy Networking! 🤝**
