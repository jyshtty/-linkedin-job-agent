# How to Compile LaTeX Resumes to PDF

Your tailored resumes are saved as `.tex` files in the `tailored_resume/` folder. To convert them to PDFs, use one of these methods:

## ✅ Option 1: Overleaf (Easiest - No Installation Required)

### Automated Upload (Coming Soon)
We're working on automating this, but for now:

### Manual Upload Steps:
1. **Go to** [Overleaf.com](https://www.overleaf.com/)
2. **Sign up/Login** (free account)
3. **Click** "New Project" → "Upload Project"
4. **Select** your `.tex` file from `tailored_resume/` folder
5. **Wait** for auto-compilation (2-3 seconds)
6. **Download** PDF by clicking "Download PDF" button

**Files to upload:**
```
tailored_resume/Luxoft_1_devops-engineer-gitlab-enterprise-at-luxoft-4469134309_NA.tex
tailored_resume/Tata_Consultancy_Services_8_azure-devops-engineer-terraform-%2B-kubernetes-at-tata-consultancy-services-4469102982_NA.tex
```

---

## Option 2: Install LaTeX Locally (One-time Setup)

### For macOS (using Homebrew):
```bash
# Install Homebrew if not installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install BasicTeX
brew install --cask basictex

# Add to PATH
export PATH="/Library/TeX/texbin:$PATH"
echo 'export PATH="/Library/TeX/texbin:$PATH"' >> ~/.zshrc

# Install required packages
sudo tlmgr update --self
sudo tlmgr install newtx enumitem titlesec setspace hyperref xcolor geometry

# Compile
cd tailored_resume
pdflatex filename.tex
```

### For macOS (without Homebrew):
```bash
# Download BasicTeX (90MB)
curl -O http://mirror.ctan.org/systems/mac/mactex/BasicTeX.pkg

# Install
sudo installer -pkg BasicTeX.pkg -target /

# Add to PATH and install packages (same as above)
```

---

## Option 3: Use Docker (If Docker is installed)

```bash
# Pull LaTeX image (once)
docker pull texlive/texlive:latest

# Compile any .tex file
cd tailored_resume
docker run --rm -v $(pwd):/workdir -w /workdir texlive/texlive:latest pdflatex filename.tex
```

---

## Option 4: Online Compilers (Manual)

Upload your `.tex` file to any of these:
- https://www.overleaf.com/ (Best)
- https://www.latex-project.org/get/#online-services
- https://latexbase.com/

---

## ⚡ Quick Test

After installing LaTeX locally, test with:
```bash
cd tailored_resume
pdflatex Tata_Consultancy_Services_8_*.tex
```

If successful, you'll see a PDF file with the same name.

---

## 🐛 Troubleshooting

### "pdflatex not found"
- LaTeX not installed or not in PATH
- Solution: Follow Option 2 above

### "Missing package" errors
```bash
sudo tlmgr install <package-name>
```

### "Permission denied"
```bash
sudo chmod +x /Library/TeX/texbin/pdflatex
```

---

## 📝 Note

The resume tailor agent automatically generates `.tex` files but cannot compile them to PDF because:
1. No LaTeX compiler (`pdflatex`) is installed on your system
2. Free online APIs have size/rate limits
3. Overleaf API requires authentication

**Recommendation:** Use Overleaf web interface for immediate results, or install BasicTeX for local compilation.
