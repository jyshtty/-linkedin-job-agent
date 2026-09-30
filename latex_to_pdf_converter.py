"""
Simple LaTeX to PDF converter using online API or local fallback
"""
import requests
import os
import sys
from pathlib import Path


def compile_latex_online(tex_content: str, output_path: str) -> bool:
    """
    Compile LaTeX using texlive.net API
    """
    try:
        # Use texlive.net API - simpler endpoint
        url = "https://texlive.net/cgi-bin/latexcgi"

        print(f"📤 Uploading LaTeX to online compiler...")

        # Send as form data
        response = requests.post(
            url,
            data={
                'filecontents': tex_content,
                'filename': 'document.tex',
                'engine': 'pdflatex',
                'return': 'pdf'
            },
            timeout=90
        )

        if response.status_code == 200:
            # Check if response is PDF
            if response.content[:4] == b'%PDF':
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                print(f"✅ PDF compiled successfully: {output_path}")
                return True
            else:
                print(f"❌ Response is not a PDF")
                print(f"Response preview: {response.text[:500]}")
                return False
        else:
            print(f"❌ Compilation failed: {response.status_code}")
            if response.text:
                print(f"Error: {response.text[:500]}")
            return False

    except Exception as e:
        print(f"❌ Online compilation error: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python latex_to_pdf_converter.py <path_to_tex_file>")
        sys.exit(1)

    tex_path = sys.argv[1]

    if not os.path.exists(tex_path):
        print(f"Error: File not found: {tex_path}")
        sys.exit(1)

    # Read LaTeX content
    with open(tex_path, 'r') as f:
        tex_content = f.read()

    # Output path
    output_path = tex_path.replace('.tex', '.pdf')

    print(f"\n{'='*80}")
    print(f"COMPILING LATEX TO PDF")
    print(f"{'='*80}\n")
    print(f"Input:  {tex_path}")
    print(f"Output: {output_path}\n")

    # Try online compilation
    success = compile_latex_online(tex_content, output_path)

    if success:
        file_size = os.path.getsize(output_path) / 1024  # KB
        print(f"\n{'='*80}")
        print(f"✅ SUCCESS! PDF created ({file_size:.1f} KB)")
        print(f"{'='*80}\n")
    else:
        print(f"\n{'='*80}")
        print(f"⚠️  Compilation failed.")
        print(f"Alternative: Upload the .tex file to https://overleaf.com")
        print(f"{'='*80}\n")
        sys.exit(1)


if __name__ == '__main__':
    main()
