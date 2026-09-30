"""
Simple automated PDF compilation without browser automation
Uses Docker or installs tectonic (lightweight LaTeX compiler)
"""
import os
import sys
import subprocess
from pathlib import Path


def compile_with_docker(tex_path: str) -> bool:
    """Try compiling with Docker"""
    try:
        print("📦 Trying Docker LaTeX compilation...")

        tex_filename = os.path.basename(tex_path)
        tex_dirname = os.path.dirname(os.path.abspath(tex_path))
        pdf_path = tex_path.replace('.tex', '.pdf')

        # Pull image if not exists
        subprocess.run(
            ['docker', 'pull', 'texlive/texlive:latest'],
            capture_output=True,
            timeout=300
        )

        # Compile
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

            file_size = os.path.getsize(pdf_path) / 1024
            print(f"✅ PDF created via Docker ({file_size:.1f} KB)")
            print(f"   Location: {pdf_path}")
            return True

        return False

    except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError) as e:
        print(f"❌ Docker compilation failed: {e}")
        return False


def install_and_compile_with_tectonic(tex_path: str) -> bool:
    """Install Tectonic (single-binary LaTeX) and compile"""
    try:
        print("🔧 Trying Tectonic (lightweight LaTeX compiler)...")

        # Check if tectonic is installed
        result = subprocess.run(['which', 'tectonic'], capture_output=True)

        if result.returncode != 0:
            print("📥 Installing Tectonic...")
            # Try to install via curl
            install_result = subprocess.run(
                ['curl', '--proto', '=https', '--tlsv1.2', '-fsSL',
                 'https://drop-sh.fullyjustified.net', '|', 'sh'],
                shell=True,
                capture_output=True,
                timeout=60
            )

            if install_result.returncode != 0:
                print("❌ Could not install Tectonic automatically")
                return False

            print("✅ Tectonic installed")

        # Compile with tectonic
        pdf_path = tex_path.replace('.tex', '.pdf')
        result = subprocess.run(
            ['tectonic', tex_path],
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode == 0 and os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path) / 1024
            print(f"✅ PDF created via Tectonic ({file_size:.1f} KB)")
            print(f"   Location: {pdf_path}")
            return True

        print(f"❌ Tectonic compilation failed")
        if result.stderr:
            print(f"   Error: {result.stderr[:200]}")
        return False

    except Exception as e:
        print(f"❌ Tectonic error: {e}")
        return False


def compile_with_local_pdflatex(tex_path: str) -> bool:
    """Try local pdflatex"""
    try:
        print("🔍 Checking for local pdflatex...")
        result = subprocess.run(['which', 'pdflatex'], capture_output=True)

        if result.returncode != 0:
            print("❌ pdflatex not found")
            return False

        print("✅ Found pdflatex, compiling...")
        tex_dirname = os.path.dirname(os.path.abspath(tex_path))
        tex_filename = os.path.basename(tex_path)
        pdf_path = tex_path.replace('.tex', '.pdf')

        result = subprocess.run(
            ['pdflatex', '-interaction=nonstopmode',
             '-output-directory', tex_dirname, tex_path],
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

            file_size = os.path.getsize(pdf_path) / 1024
            print(f"✅ PDF created via pdflatex ({file_size:.1f} KB)")
            print(f"   Location: {pdf_path}")
            return True

        print(f"❌ pdflatex compilation failed")
        if result.stderr:
            print(f"   Error: {result.stderr[:500]}")
        return False

    except Exception as e:
        print(f"❌ pdflatex error: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python simple_pdf_compiler.py <path_to_tex_file>")
        sys.exit(1)

    tex_path = sys.argv[1]

    if not os.path.exists(tex_path):
        print(f"❌ File not found: {tex_path}")
        sys.exit(1)

    print(f"\n{'='*80}")
    print(f"AUTOMATED LATEX TO PDF COMPILATION")
    print(f"{'='*80}\n")
    print(f"Input: {tex_path}\n")

    # Try methods in order
    methods = [
        compile_with_local_pdflatex,
        compile_with_docker,
        install_and_compile_with_tectonic,
    ]

    for method in methods:
        try:
            if method(tex_path):
                print(f"\n{'='*80}")
                print(f"✅ SUCCESS!")
                print(f"{'='*80}\n")
                sys.exit(0)
            print()  # Empty line between attempts
        except Exception as e:
            print(f"Method failed: {e}\n")
            continue

    # All methods failed
    print(f"\n{'='*80}")
    print(f"❌ ALL COMPILATION METHODS FAILED")
    print(f"{'='*80}\n")
    print("Please use one of these alternatives:")
    print("1. Run: python overleaf_auto_compiler.py " + tex_path)
    print("2. Open: open_in_overleaf.html (manual upload)")
    print("3. Install LaTeX: brew install --cask basictex")
    print(f"{'='*80}\n")
    sys.exit(1)


if __name__ == '__main__':
    main()
