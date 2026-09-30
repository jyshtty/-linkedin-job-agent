import os
import pandas as pd
import PyPDF2
from openai import AzureOpenAI
from typing import Dict, List, Optional
from dotenv import load_dotenv
import json
import re
from linkedin_scraper import LinkedInJobScraper
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_LEFT, TA_CENTER


class ResumeTailor:
    """Agent for tailoring resumes based on job descriptions."""

    def __init__(self):
        load_dotenv()

        # Load DIAL API credentials
        dial_api_key = os.getenv('DIAL_API_KEY')
        azure_endpoint = os.getenv('AZURE_ENDPOINT')
        api_version = os.getenv('API_VERSION')
        self.deployment_name = os.getenv('DEPLOYMENT_NAME')

        if not dial_api_key or not azure_endpoint:
            raise ValueError("DIAL_API_KEY and AZURE_ENDPOINT not found in .env file")

        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_key=dial_api_key,
            api_version=api_version,
            azure_endpoint=azure_endpoint
        )
        self.scraper = LinkedInJobScraper()
        self.searched_jobs_file = 'searched_job_list/searched_jobs.csv'
        self.original_resume_pdf = 'original_resume/Ajay_resume.pdf'
        self.original_resume_tex = 'original_resume/Ajay_resume.tex'
        self.tailored_resume_dir = 'tailored_resume'
        self.latex_dir = os.path.join(self.tailored_resume_dir, 'latex')
        os.makedirs(self.tailored_resume_dir, exist_ok=True)
        os.makedirs(self.latex_dir, exist_ok=True)

    def _extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF resume."""
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            text = ''
            for page in pdf_reader.pages:
                text += page.extract_text()
        return text

    def _get_job_by_serial(self, serial_number: int) -> Optional[Dict]:
        """Get job details by serial number from CSV."""
        if not os.path.exists(self.searched_jobs_file):
            print("No searched jobs found. Run search command first.")
            return None

        df = pd.read_csv(self.searched_jobs_file)
        job_row = df[df['serial_number'] == serial_number]

        if job_row.empty:
            print(f"No job found with serial number {serial_number}")
            return None

        return job_row.iloc[0].to_dict()

    def _calculate_match_percentage(self, resume_text: str, job_description: str) -> float:
        """Calculate match percentage between resume and JD using Claude."""
        prompt = f"""You are an expert ATS (Applicant Tracking System) and resume matcher.

Analyze the following resume and job description, then calculate a match percentage (0-100).

Consider:
- Skills match (technical and soft skills)
- Experience relevance
- Education requirements
- Keywords alignment
- Role responsibilities match

Resume:
{resume_text}

Job Description:
{job_description}

Return ONLY a JSON object with this structure:
{{
    "match_percentage": <number between 0-100>,
    "matching_skills": ["skill1", "skill2", ...],
    "missing_skills": ["skill1", "skill2", ...],
    "strengths": ["strength1", "strength2", ...],
    "gaps": ["gap1", "gap2", ...]
}}
"""

        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=2000
        )

        response_text = response.choices[0].message.content
        # Extract JSON from response
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            analysis = json.loads(json_match.group())
            return analysis
        else:
            return {"match_percentage": 0, "matching_skills": [], "missing_skills": [], "strengths": [], "gaps": []}

    def _generate_star_bullets(self, job_description: str, missing_skills: List[str], company: str) -> List[str]:
        """Generate realistic STAR format bullet points based on JD."""
        prompt = f"""You are a professional resume writer. Generate 2 realistic STAR format bullet points for a resume based on the job requirements.

Company: {company}
Job Description: {job_description}
Missing Skills to incorporate: {', '.join(missing_skills)}

Requirements for each bullet point:
1. Follow STAR format (Situation, Task, Action, Result)
2. Include realistic, specific metrics (e.g., "scaled system to 10 servers handling 10K QPS", "reduced latency by 40%")
3. Use strong action verbs
4. Be concise (1-2 lines max per bullet)
5. Make them believable and relevant to the role
6. Incorporate the missing skills naturally

Return ONLY a JSON array of 2 bullet points:
[
    "Bullet point 1...",
    "Bullet point 2..."
]
"""

        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=1000
        )

        response_text = response.choices[0].message.content
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            bullets = json.loads(json_match.group())
            return bullets
        else:
            return []

    def _identify_sections_to_remove(self, resume_text: str, job_description: str) -> List[str]:
        """Identify unnecessary sections to remove from resume."""
        prompt = f"""You are a resume optimization expert. Analyze this resume and job description.

Identify which sections or experiences are NOT relevant to this specific job and should be removed or minimized.

Resume:
{resume_text}

Job Description:
{job_description}

Return ONLY a JSON array of section names or specific experiences to remove:
[
    "Section/experience 1 to remove",
    "Section/experience 2 to remove"
]

If nothing should be removed, return an empty array: []
"""

        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=1000
        )

        response_text = response.choices[0].message.content
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            sections = json.loads(json_match.group())
            return sections
        else:
            return []

    def _generate_tailored_latex(self, analysis: Dict, new_bullets: List[str],
                                output_filename: str, job_info: Dict) -> str:
        """Generate tailored LaTeX resume using original template."""

        # Read original LaTeX template
        with open(self.original_resume_tex, 'r') as f:
            latex_content = f.read()

        # Ask AI to tailor the LaTeX
        prompt = f"""You are an expert LaTeX resume editor. I'm tailoring my resume for this job:

Job Title: {job_info['job_title']}
Company: {job_info['company']}

Match Analysis:
- Matching Skills: {', '.join(analysis.get('matching_skills', [])[:10])}
- Missing Skills: {', '.join(analysis.get('missing_skills', [])[:10])}

New STAR Bullets to Add:
{chr(10).join(f"{i+1}. {bullet}" for i, bullet in enumerate(new_bullets))}

Original LaTeX Resume:
{latex_content}

TASK:
1. In the Skills section, ADD these missing skills: {', '.join(analysis.get('missing_skills', [])[:5])}
2. Add the new STAR bullets to the MOST RELEVANT experience section (Eli Lilly is most recent)
3. REMOVE or reduce emphasis on experiences least relevant to DevOps/GitLab (keep structure intact)
4. Keep ALL formatting, packages, colors, and structure EXACTLY the same
5. Do NOT change name, contact info, or education
6. Return ONLY the complete LaTeX code, no explanations

Return the FULL modified LaTeX document from \\documentclass to \\end{{document}}.
"""

        response = self.client.chat.completions.create(
            model=self.deployment_name,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=8000
        )

        tailored_latex = response.choices[0].message.content

        # Extract LaTeX from markdown code blocks if present
        latex_match = re.search(r'```(?:latex|tex)?\n(.*?)\n```', tailored_latex, re.DOTALL)
        if latex_match:
            tailored_latex = latex_match.group(1)

        # Post-process: Fix common LaTeX issues
        # 1. Replace excessive spacing with consistent 6pt
        tailored_latex = tailored_latex.replace(r'\vspace{40pt}', r'\vspace{6pt}')
        # 2. Fix escaped less-than sign
        tailored_latex = tailored_latex.replace(r'\<', '<')

        # Save tailored LaTeX in latex subdirectory
        tex_filename = output_filename.replace('.pdf', '.tex')
        tex_path = os.path.join(self.latex_dir, tex_filename)
        with open(tex_path, 'w') as f:
            f.write(tailored_latex)

        return tex_path

    def _compile_latex_to_pdf(self, tex_path: str) -> Optional[str]:
        """Compile LaTeX to PDF using tectonic, pdflatex, or Docker fallback."""
        import subprocess

        # PDF should go to tailored_resume/, not latex/
        tex_filename = os.path.basename(tex_path)
        pdf_filename = tex_filename.replace('.tex', '.pdf')
        pdf_path = os.path.join(self.tailored_resume_dir, pdf_filename)

        # Try Tectonic first (modern, single-binary LaTeX compiler)
        try:
            # Tectonic outputs PDF in the same directory as .tex by default
            result = subprocess.run(
                ['tectonic', tex_path],
                capture_output=True,
                text=True,
                timeout=120
            )

            # Tectonic creates PDF in same dir as .tex, need to move it
            temp_pdf = tex_path.replace('.tex', '.pdf')
            if os.path.exists(temp_pdf):
                # Move PDF from latex/ to tailored_resume/
                os.rename(temp_pdf, pdf_path)
                print("   ✅ Compiled via Tectonic!")
                return pdf_path

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Try local pdflatex second
        try:
            # pdflatex can output directly to tailored_resume_dir
            result = subprocess.run(
                ['pdflatex', '-interaction=nonstopmode', '-output-directory',
                 self.tailored_resume_dir, tex_path],
                capture_output=True,
                text=True,
                timeout=30
            )

            if os.path.exists(pdf_path):
                # Clean up auxiliary files in tailored_resume dir
                for ext in ['.aux', '.log', '.out']:
                    aux_file = os.path.join(self.tailored_resume_dir, pdf_filename.replace('.pdf', ext))
                    if os.path.exists(aux_file):
                        os.remove(aux_file)
                print("   ✅ Compiled via pdflatex!")
                return pdf_path

        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        # Try Docker as last resort
        try:
            print("   Trying Docker LaTeX container...")
            tex_filename = os.path.basename(tex_path)
            tex_dirname = os.path.dirname(os.path.abspath(tex_path))

            result = subprocess.run(
                ['docker', 'run', '--rm',
                 '-v', f'{tex_dirname}:/workdir',
                 '-w', '/workdir',
                 'texlive/texlive:latest',
                 'pdflatex', '-interaction=nonstopmode', tex_filename],
                capture_output=True,
                text=True,
                timeout=60
            )

            if os.path.exists(pdf_path):
                # Clean up auxiliary files
                for ext in ['.aux', '.log', '.out']:
                    aux_file = tex_path.replace('.tex', ext)
                    if os.path.exists(aux_file):
                        os.remove(aux_file)
                print("   ✅ Compiled via Docker!")
                return pdf_path

        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.CalledProcessError):
            pass

        return None

    def tailor_resume(self, serial_number: int) -> Optional[str]:
        """Main function to tailor resume for a specific job."""
        print(f"\n{'='*80}")
        print(f"TAILORING RESUME FOR JOB #{serial_number}")
        print(f"{'='*80}\n")

        # Get job details
        job = self._get_job_by_serial(serial_number)
        if not job:
            return None

        print(f"Job: {job['job_title']}")
        print(f"Company: {job['company']}")
        print(f"Location: {job['location']}")

        # Fetch full job details (description, company link) on-demand
        print("📥 Fetching full job details from LinkedIn...")
        job_details = self.scraper.fetch_job_details(job['linkedin_job_id'])
        job_description = job_details['job_description']
        company_apply_link = job_details['company_apply_link']
        company_job_id = job_details['company_job_id']

        if job_description == 'N/A':
            print("⚠️  Could not fetch full job description. Using basic info for tailoring.")
            job_description = f"Job Title: {job['job_title']}\nCompany: {job['company']}\nLocation: {job['location']}"

        print(f"🔗 Company Career Page: {company_apply_link}")
        if company_apply_link == 'EASY_APPLY':
            print("⚠️  This is an Easy Apply job (no external career page)")
        elif company_apply_link != 'N/A':
            print(f"   Job ID on company site: {company_job_id}")
        print()

        # Extract resume text
        print("📄 Reading original resume...")
        resume_text = self._extract_pdf_text(self.original_resume_pdf)

        # Calculate match percentage
        print("🔍 Analyzing match with job description...")
        analysis = self._calculate_match_percentage(resume_text, job_description)
        match_percentage = analysis['match_percentage']

        print(f"\n📊 Match Score: {match_percentage}%")
        print(f"✓ Matching Skills: {', '.join(analysis['matching_skills'][:5])}")
        print(f"✗ Missing Skills: {', '.join(analysis['missing_skills'][:5])}\n")

        if match_percentage >= 80:
            print(f"✓ Resume already matches {match_percentage}% - No tailoring needed!")
            return None

        print(f"⚡ Match below 80% - Tailoring resume...\n")

        # Identify sections to remove
        print("🗑️  Identifying irrelevant sections...")
        sections_to_remove = self._identify_sections_to_remove(resume_text, job_description)
        if sections_to_remove:
            print(f"   Removing: {', '.join(sections_to_remove)}")

        # Generate new STAR bullets
        print("✨ Generating STAR format bullet points...")
        new_bullets = self._generate_star_bullets(
            job_description,
            analysis['missing_skills'][:3],  # Top 3 missing skills
            job['company']
        )
        for i, bullet in enumerate(new_bullets, 1):
            print(f"   {i}. {bullet}")

        # Generate output filename (sanitize for filesystem)
        company_name = job['company'].replace(' ', '_').replace('/', '_')
        safe_job_id = company_job_id.replace('/', '_').replace('\\', '_') if company_job_id != 'N/A' else 'NA'
        output_filename = f"{company_name}_{serial_number}_{job['linkedin_job_id']}_{safe_job_id}.pdf"

        # Generate tailored LaTeX
        print(f"\n📝 Generating tailored LaTeX resume...")
        tex_path = self._generate_tailored_latex(
            analysis,
            new_bullets,
            output_filename,
            job
        )

        print("🔨 Compiling LaTeX to PDF...")
        pdf_path = self._compile_latex_to_pdf(tex_path)

        if pdf_path:
            print(f"\n{'='*80}")
            print(f"✅ SUCCESS! Tailored resume saved to: {pdf_path}")
            print(f"{'='*80}\n")
            return pdf_path
        else:
            print(f"\n{'='*80}")
            print(f"⚠️  LaTeX file created: {tex_path}")
            print(f"\n💡 Attempting automated Overleaf compilation...")
            print(f"{'='*80}\n")

            # Try automated Overleaf compilation
            try:
                import subprocess
                result = subprocess.run(
                    ['python', 'overleaf_auto_compiler.py', tex_path],
                    capture_output=True,
                    text=True,
                    timeout=180
                )

                expected_pdf = tex_path.replace('.tex', '.pdf')
                if os.path.exists(expected_pdf):
                    print(f"\n✅ SUCCESS via Overleaf automation!")
                    return expected_pdf

            except Exception as e:
                print(f"⚠️  Automated compilation not available: {e}")

            print(f"\n{'='*80}")
            print(f"📋 MANUAL COMPILATION OPTIONS:")
            print(f"{'='*80}")
            print(f"1. Automated (Recommended):")
            print(f"   python overleaf_auto_compiler.py {tex_path}")
            print(f"\n2. Web Interface:")
            print(f"   open open_in_overleaf.html")
            print(f"\n3. Install LaTeX locally:")
            print(f"   brew install --cask basictex")
            print(f"   Then: cd {self.tailored_resume_dir} && pdflatex {os.path.basename(tex_path)}")
            print(f"{'='*80}\n")
            return tex_path
