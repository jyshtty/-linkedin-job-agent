# Resume Tailor Agent - README

## Overview

The Resume Tailor Agent is an intelligent tool that automatically tailors your resume for specific job postings. It analyzes the match between your resume and a job description, and if the match is below 80%, it automatically optimizes your resume by removing irrelevant sections and adding relevant STAR format bullet points with realistic metrics.

## Features

- 🎯 **Match Analysis**: Calculates percentage match between your resume and job description
- 🤖 **AI-Powered**: Uses Claude AI (Anthropic) for intelligent resume analysis and generation
- ⭐ **STAR Format**: Generates professional bullet points in STAR format (Situation, Task, Action, Result)
- 📊 **Realistic Metrics**: Includes believable numbers like "scaled to 10 servers handling 10K QPS"
- 🗑️ **Smart Removal**: Identifies and removes irrelevant sections automatically
- 📄 **LaTeX Generation**: Creates professional resumes using Overleaf-style LaTeX templates
- 🎨 **Template Consistency**: Maintains your original resume design and formatting
- 💾 **Organized Storage**: Saves tailored resumes with descriptive filenames

## How It Works

### Workflow

```
1. User runs: python main.py tailor_resume <serial_number>
2. Agent fetches job from searched_jobs.csv
3. Extracts text from original_resume/Ajay_resume.pdf
4. Calculates match percentage with Claude AI
5. If match >= 80%: No changes needed ✓
6. If match < 80%:
   a. Identify irrelevant sections to remove
   b. Generate 2 STAR format bullets with realistic metrics
   c. Create LaTeX resume incorporating changes
   d. Compile to PDF using pdflatex
7. Save as: tailored_resume/CompanyName_SerialNo_LinkedInJobID_CompanyJobID.pdf
```

### Match Analysis

The agent analyzes:
- **Skills Match**: Technical and soft skills alignment
- **Experience Relevance**: How well your experience matches the role
- **Education Requirements**: Degree and qualification fit
- **Keywords Alignment**: ATS-friendly keyword matching
- **Role Responsibilities**: Task and responsibility overlap

### STAR Format Bullet Points

Each generated bullet follows the STAR methodology:
- **S**ituation: Context and background
- **T**ask: Challenge or objective
- **A**ction: Steps taken to address it
- **R**esult: Measurable outcome with realistic metrics

**Examples:**
- "Architected microservices architecture serving 50K daily users, reducing API latency by 35% and improving system reliability to 99.9% uptime"
- "Led cross-functional team of 5 engineers to migrate legacy monolith to containerized platform, scaling throughput from 2K to 15K requests per second"

## Installation

### Prerequisites

1. **Python Dependencies** (already in pyproject.toml):
   - `PyPDF2>=3.0.0` - PDF text extraction
   - `anthropic>=0.18.0` - Claude AI API
   - `pandas>=2.0.0` - Data handling

2. **LaTeX Distribution**:
   ```bash
   # macOS
   brew install --cask mactex
   
   # Ubuntu/Debian
   sudo apt-get install texlive-full
   
   # Windows
   # Download and install MiKTeX from https://miktex.org/
   ```

3. **Anthropic API Key**:
   - Sign up at https://console.anthropic.com/
   - Create an API key
   - Add credits to your account

### Setup

1. **Install Python dependencies**:
   ```bash
   pip install -e .
   ```

2. **Configure API Key**:
   Add your Anthropic API key to `.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-api03-...
   ```

3. **Verify LaTeX installation**:
   ```bash
   pdflatex --version
   ```

4. **Prepare your resume**:
   - Place your PDF resume in `original_resume/` folder
   - Name it `Ajay_resume.pdf` (or update the path in `resume_tailor.py`)

## Usage

### Basic Command

```bash
python main.py tailor_resume <serial_number>
```

Where `<serial_number>` is the job's serial number from `searched_job_list/searched_jobs.csv`.

### Complete Example

**Step 1: Search for jobs**
```bash
python main.py search --job_role "Senior Software Engineer"
```

Output shows jobs with serial numbers:
```
====================================================================================================
                                           SEARCH RESULTS                                           
====================================================================================================
 serial_number           linkedin_job_id company_apply_link
             1            4454310283      https://company.com/careers/12345
             2            4461654265      https://company2.com/jobs/67890
...
====================================================================================================
```

**Step 2: Tailor resume for specific job**
```bash
python main.py tailor_resume 1
```

### Output Example

```
================================================================================
TAILORING RESUME FOR JOB #1
================================================================================

Job: Senior Software Engineer
Company: Google
Location: Bengaluru, Karnataka, India

📄 Reading original resume...
🔍 Analyzing match with job description...

📊 Match Score: 68%
✓ Matching Skills: Python, AWS, Docker, Kubernetes, Microservices
✗ Missing Skills: Go, gRPC, Service Mesh, Terraform, GraphQL

⚡ Match below 80% - Tailoring resume...

🗑️  Identifying irrelevant sections...
   Removing: Mobile Development Experience, PHP Projects

✨ Generating STAR format bullet points...
   1. Designed and deployed gRPC-based service mesh handling 25K RPS across 15 microservices, reducing inter-service latency by 45% and improving observability with distributed tracing
   2. Automated infrastructure provisioning using Terraform and Helm, scaling Kubernetes clusters from 20 to 100 nodes while maintaining 99.95% uptime and reducing deployment time by 60%

📝 Generating tailored resume...
🔨 Compiling LaTeX to PDF...
✓ PDF generated: tailored_resume/Google_1_4454310283_12345.pdf

================================================================================
✅ SUCCESS! Tailored resume saved to: tailored_resume/Google_1_4454310283_12345.pdf
================================================================================
```

## Output Format

### Filename Convention

```
{CompanyName}_{SerialNumber}_{LinkedInJobID}_{CompanyJobID}.pdf
```

**Examples:**
- `Google_1_4454310283_12345.pdf`
- `Amazon_5_4461654265_AWS-SDE-2024.pdf`
- `Microsoft_10_4470845643_REQ123456.pdf`

**Breakdown:**
- `CompanyName`: Company name with spaces replaced by underscores
- `SerialNumber`: Serial number from CSV
- `LinkedInJobID`: LinkedIn's internal job ID
- `CompanyJobID`: Job ID from company's career page (extracted from apply link)

### Directory Structure

```
tailored_resume/
├── Google_1_4454310283_12345.pdf
├── Google_1_4454310283_12345.tex
├── Amazon_5_4461654265_AWS-SDE-2024.pdf
├── Amazon_5_4461654265_AWS-SDE-2024.tex
└── ...
```

Both `.tex` (LaTeX source) and `.pdf` (compiled) files are saved.

## Match Percentage Thresholds

| Match % | Action | Description |
|---------|--------|-------------|
| 80-100% | No changes | Resume already well-aligned with JD |
| 60-79% | Minor tailoring | Add 1-2 relevant bullets, minimal removal |
| 40-59% | Moderate tailoring | Add 2 bullets, remove 1-2 irrelevant sections |
| 0-39% | Major tailoring | Significant restructuring recommended |

**Current threshold**: 80% (configurable in code)

## Customization

### Change Match Threshold

Edit `resume_tailor.py`:
```python
if match_percentage >= 70:  # Changed from 80 to 70
    print(f"✓ Resume already matches {match_percentage}% - No tailoring needed!")
    return None
```

### Adjust Number of Bullet Points

Edit `resume_tailor.py` in `_generate_star_bullets()`:
```python
prompt = f"""... Generate 3 realistic STAR format bullet points ...  # Changed from 2 to 3
```

And update the return statement:
```python
return bullets[:3]  # Return 3 instead of 2
```

### Modify LaTeX Template

The LaTeX template is generated by Claude AI. To customize the style, edit the prompt in `_generate_latex_resume()`:

```python
prompt = f"""You are an expert LaTeX resume writer using Overleaf templates.

Generate a complete LaTeX resume file (.tex) that:
1. Uses the 'moderncv' package with 'classic' style  # Add specific template
2. Uses 11pt font size and letter paper  # Specify formatting
3. Includes a professional header with contact info
...
"""
```

### Use Different Resume File

Edit `resume_tailor.py`:
```python
self.original_resume_path = 'original_resume/MyResume.pdf'  # Change filename
```

### Change AI Model

Edit `resume_tailor.py`:
```python
model="claude-opus-4-20250514",  # Use Opus instead of Sonnet for higher quality
```

Available models:
- `claude-sonnet-4-20250514` - Fast, balanced (default)
- `claude-opus-4-20250514` - Highest quality, slower
- `claude-haiku-4-20250319` - Fastest, economical

## Technical Details

### Resume Analysis Process

1. **PDF Text Extraction**:
   ```python
   PyPDF2.PdfReader(pdf_path)
   ```
   Extracts all text from PDF resume

2. **Match Calculation**:
   - Claude AI analyzes resume vs JD
   - Returns JSON with:
     - `match_percentage` (0-100)
     - `matching_skills` (array)
     - `missing_skills` (array)
     - `strengths` (array)
     - `gaps` (array)

3. **Content Generation**:
   - **Section Removal**: AI identifies irrelevant sections
   - **STAR Bullets**: AI generates realistic, metric-driven points
   - **LaTeX Generation**: Complete `.tex` file with formatting

4. **PDF Compilation**:
   ```bash
   pdflatex -interaction=nonstopmode -output-directory tailored_resume resume.tex
   ```
   Runs twice for proper cross-references

### API Usage

**Anthropic Claude API** is used for:
- Match percentage calculation
- Skills gap analysis
- Section removal recommendations
- STAR bullet generation
- LaTeX resume generation

**Estimated cost per resume**: ~$0.10-0.20 (varies by resume length)

### Error Handling

The agent handles:
- Missing job serial number
- PDF extraction failures
- API rate limits
- LaTeX compilation errors
- Missing dependencies

## Troubleshooting

### Issue: "ANTHROPIC_API_KEY not found"

**Solution**:
```bash
# Add to .env file
echo "ANTHROPIC_API_KEY=sk-ant-api03-your-key-here" >> .env
```

### Issue: "pdflatex not found"

**Solution**:
```bash
# macOS
brew install --cask mactex

# Verify installation
pdflatex --version
```

### Issue: LaTeX compilation failed

**Symptoms**: `.tex` file created but no `.pdf`

**Solutions**:
1. Check `.log` file in `tailored_resume/` for errors
2. Manually compile:
   ```bash
   cd tailored_resume
   pdflatex CompanyName_1_12345_67890.tex
   ```
3. Install missing LaTeX packages:
   ```bash
   sudo tlmgr install <package-name>
   ```

### Issue: Low match percentage for good matches

**Cause**: Resume keywords don't match JD keywords (even if skills are equivalent)

**Solution**: Update your original resume to use industry-standard terminology

### Issue: Generated bullets are too generic

**Cause**: Job description lacks specific details

**Solution**: Add more context to the JD or manually edit generated bullets in `.tex` file

### Issue: Company job ID is "NA"

**Cause**: Company apply link doesn't follow common URL patterns

**Solution**: 
1. Manually find job ID on company career page
2. Rename file accordingly
3. Or update regex patterns in `linkedin_scraper.py`:
   ```python
   patterns = [
       r'/jobs?[/-](\w+)',
       r'jobId[=:](\w+)',
       # Add more patterns here
   ]
   ```

## Best Practices

### Before Running

1. **Update Original Resume**: Ensure your base resume is current
2. **Run Search First**: Always search jobs before tailoring
3. **Review JD**: Check that job description was fetched correctly
4. **Check Credits**: Ensure you have Anthropic API credits

### After Generation

1. **Review Tailored Resume**: AI-generated content should be verified
2. **Check Metrics**: Ensure numbers are realistic for your experience level
3. **Verify Formatting**: LaTeX may have compilation issues
4. **Proofread**: Check for typos or awkward phrasing
5. **Test ATS**: Run through an ATS checker tool

### General Tips

- **Tailor Strategically**: Don't tailor for every job - focus on top targets
- **Maintain Honesty**: Only add content you can discuss in interviews
- **Keep Originals**: Never modify `original_resume/Ajay_resume.pdf`
- **Track Applications**: Note which tailored resume you sent where
- **Update Regularly**: Refresh your base resume as you gain experience

## Security & Privacy

### API Key Security

- **Never commit** `.env` file to git
- **Rotate keys** periodically
- **Monitor usage** on Anthropic console
- **Set spending limits** to avoid unexpected charges

### Resume Privacy

- Tailored resumes contain your personal information
- Store in secure location
- Be cautious when sharing or uploading
- Use encrypted backups

### Data Handling

- Resume text is sent to Anthropic API for processing
- Job descriptions are included in API calls
- No data is stored by Anthropic beyond API logs
- All files stored locally on your machine

## Limitations

1. **LaTeX Dependency**: Requires LaTeX installation (large download ~4GB for MacTeX)
2. **API Costs**: Each resume tailoring costs ~$0.10-0.20 in API usage
3. **Template Constraints**: Generated LaTeX may not perfectly match your original design
4. **PDF to Text**: Complex resume designs may not extract text correctly
5. **Company Job IDs**: Not all companies use extractable job ID patterns
6. **Match Accuracy**: AI matching is heuristic, not perfect
7. **Manual Review Required**: Always review generated content before sending

## Future Enhancements

### Planned Features

1. **Multiple Templates**: Support for different LaTeX resume templates
2. **Cover Letter Generation**: Auto-generate tailored cover letters
3. **Batch Processing**: Tailor for multiple jobs at once
4. **A/B Testing**: Generate multiple versions for comparison
5. **ATS Scoring**: Built-in ATS compatibility checker
6. **Interview Prep**: Generate interview questions based on tailored resume
7. **Version Control**: Track changes across tailored versions
8. **Skills Database**: Maintain inventory of your actual skills with examples

### Potential Improvements

- Support for Word (.docx) resume format
- Integration with Overleaf API for direct compilation
- Resume analytics dashboard
- Success rate tracking (interviews landed per tailored resume)
- Collaborative features for career coaches
- Multi-language support

## Command Reference

### Main Command

```bash
python main.py tailor_resume <serial_number>
```

### Examples

```bash
# Tailor for job #1 from search results
python main.py tailor_resume 1

# Tailor for job #10
python main.py tailor_resume 10

# Tailor for job #25
python main.py tailor_resume 25
```

### Related Commands

```bash
# Search jobs first
python main.py search

# Search specific role
python main.py search --job_role "Data Scientist"

# View searched jobs
cat searched_job_list/searched_jobs.csv | column -t -s,

# List tailored resumes
ls -lh tailored_resume/
```

## Development

### Code Structure

**`resume_tailor.py`** - Main tailor agent:
- `ResumeTailor.__init__()` - Initialize with API keys
- `ResumeTailor._extract_pdf_text()` - Extract text from PDF
- `ResumeTailor._get_job_by_serial()` - Fetch job from CSV
- `ResumeTailor._calculate_match_percentage()` - AI-powered matching
- `ResumeTailor._generate_star_bullets()` - Create STAR format points
- `ResumeTailor._identify_sections_to_remove()` - Find irrelevant content
- `ResumeTailor._generate_latex_resume()` - Create LaTeX file
- `ResumeTailor._compile_latex_to_pdf()` - Compile to PDF
- `ResumeTailor.tailor_resume()` - Main orchestration function

### Testing

```bash
# Test with a known job
python main.py tailor_resume 1

# Check generated files
ls -la tailored_resume/

# View LaTeX source
cat tailored_resume/Company_1_12345_67890.tex

# Manually compile if needed
cd tailored_resume && pdflatex Company_1_12345_67890.tex
```

### Debugging

Enable verbose output by adding to `resume_tailor.py`:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

View API responses:
```python
print(f"API Response: {message.content[0].text}")
```

## FAQ

**Q: How accurate is the match percentage?**  
A: Claude AI analyzes skills, experience, and keywords. It's a good estimate but not definitive. ATS systems may score differently.

**Q: Can I use this for non-technical roles?**  
A: Yes! The agent works for any role. STAR format applies to all industries.

**Q: Will this help me pass ATS?**  
A: It improves ATS compatibility by matching keywords and using standard formatting, but can't guarantee success.

**Q: How long does tailoring take?**  
A: 30-60 seconds per resume (API calls + LaTeX compilation).

**Q: Can I edit the generated resume?**  
A: Yes! Edit the `.tex` file and recompile with `pdflatex`.

**Q: What if my resume uses a custom font?**  
A: LaTeX may substitute fonts. Specify fonts in the LaTeX template or use standard fonts.

**Q: How do I know which tailored resume I sent where?**  
A: The filename includes company name and job ID. Keep a spreadsheet to track applications.

**Q: Can this work without LaTeX?**  
A: Not currently. LaTeX is required for PDF generation. Future versions may support Word format.

## Support

For issues or questions:
1. Check this README and troubleshooting section
2. Review `tailored_resume/*.log` files for LaTeX errors
3. Check Anthropic API usage and errors on console.anthropic.com
4. Verify your resume PDF is text-extractable (not an image)

## Version History

- **v0.1.0** (2026-09-29)
  - Initial release
  - Match percentage calculation
  - STAR format bullet generation
  - LaTeX PDF compilation
  - Intelligent section removal
  - Realistic metrics in bullets

---

**Last Updated**: 2026-09-29  
**Author**: Ajay Kumar Shetty  
**Contact**: jyshtty@gmail.com
