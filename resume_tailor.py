import os
import pandas as pd
import PyPDF2
import anthropic
from typing import Dict, List, Optional
from dotenv import load_dotenv
import json
import re


class ResumeTailor:
    """Agent for tailoring resumes based on job descriptions."""

    def __init__(self):
        load_dotenv()
        self.anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in .env file")

        self.client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        self.searched_jobs_file = 'searched_job_list/searched_jobs.csv'
        self.original_resume_path = 'original_resume/Ajay_resume.pdf'
        self.tailored_resume_dir = 'tailored_resume'
        os.makedirs(self.tailored_resume_dir, exist_ok=True)

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

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text
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

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text
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

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            sections = json.loads(json_match.group())
            return sections
        else:
            return []

    def _generate_latex_resume(self, resume_text: str, job_description: str,
                               sections_to_remove: List[str], new_bullets: List[str],
                               output_filename: str) -> str:
        """Generate tailored LaTeX resume based on Overleaf template."""
        prompt = f"""You are an expert LaTeX resume writer using Overleaf templates.

Generate a complete LaTeX resume file (.tex) that:
1. Uses a professional Overleaf template (modern, ATS-friendly)
2. Removes these sections/experiences: {sections_to_remove}
3. Adds these new STAR format bullet points in the most relevant section: {new_bullets}
4. Maintains the original resume structure and formatting
5. Optimizes for the target job description

Original Resume Content:
{resume_text}

Target Job Description:
{job_description}

Generate the COMPLETE LaTeX code for the resume. Start with \\documentclass and end with \\end{{document}}.
Use the 'article' or 'resume' document class with professional formatting.
"""

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        latex_code = message.content[0].text

        # Extract LaTeX code from markdown if wrapped
        latex_match = re.search(r'```(?:latex)?\n(.*?)\n```', latex_code, re.DOTALL)
        if latex_match:
            latex_code = latex_match.group(1)

        # Save LaTeX file
        tex_path = os.path.join(self.tailored_resume_dir, output_filename.replace('.pdf', '.tex'))
        with open(tex_path, 'w') as f:
            f.write(latex_code)

        return tex_path

    def _compile_latex_to_pdf(self, tex_path: str) -> str:
        """Compile LaTeX to PDF using pdflatex."""
        import subprocess

        try:
            # Run pdflatex twice for proper references
            for _ in range(2):
                result = subprocess.run(
                    ['pdflatex', '-interaction=nonstopmode', '-output-directory',
                     self.tailored_resume_dir, tex_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

            pdf_path = tex_path.replace('.tex', '.pdf')

            if os.path.exists(pdf_path):
                print(f"✓ PDF generated: {pdf_path}")
                # Clean up auxiliary files
                for ext in ['.aux', '.log', '.out']:
                    aux_file = tex_path.replace('.tex', ext)
                    if os.path.exists(aux_file):
                        os.remove(aux_file)
                return pdf_path
            else:
                print(f"✗ PDF compilation failed. Check {tex_path}")
                return None

        except subprocess.TimeoutExpired:
            print("✗ LaTeX compilation timed out")
            return None
        except FileNotFoundError:
            print("✗ pdflatex not found. Install LaTeX: brew install --cask mactex")
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
        print(f"Location: {job['location']}\n")

        # Extract resume text
        print("📄 Reading original resume...")
        resume_text = self._extract_pdf_text(self.original_resume_path)

        # Calculate match percentage
        print("🔍 Analyzing match with job description...")
        analysis = self._calculate_match_percentage(resume_text, job['job_description'])
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
        sections_to_remove = self._identify_sections_to_remove(resume_text, job['job_description'])
        if sections_to_remove:
            print(f"   Removing: {', '.join(sections_to_remove)}")

        # Generate new STAR bullets
        print("✨ Generating STAR format bullet points...")
        new_bullets = self._generate_star_bullets(
            job['job_description'],
            analysis['missing_skills'][:3],  # Top 3 missing skills
            job['company']
        )
        for i, bullet in enumerate(new_bullets, 1):
            print(f"   {i}. {bullet}")

        # Generate output filename
        company_name = job['company'].replace(' ', '_').replace('/', '_')
        company_job_id = job.get('company_job_id', 'NA')
        output_filename = f"{company_name}_{serial_number}_{job['linkedin_job_id']}_{company_job_id}.pdf"

        # Generate LaTeX resume
        print(f"\n📝 Generating tailored resume...")
        tex_path = self._generate_latex_resume(
            resume_text,
            job['job_description'],
            sections_to_remove,
            new_bullets,
            output_filename
        )

        # Compile to PDF
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
            print(f"   Compile manually: pdflatex {tex_path}")
            print(f"{'='*80}\n")
            return tex_path
