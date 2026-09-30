"""
Compile LaTeX using various online APIs
"""
import requests
import os
import sys
import time
import base64
from pathlib import Path


def compile_with_latexbase(tex_content: str, output_path: str) -> bool:
    """
    Compile using LaTeX.Base API
    https://latexbase.com/
    """
    try:
        print(f"📤 Trying LaTeX.Base API...")

        url = "https://latexbase.com/api/v1/compile"

        payload = {
            "compiler": "pdflatex",
            "resources": [
                {
                    "content": tex_content,
                    "main": True
                }
            ]
        }

        response = requests.post(url, json=payload, timeout=90)

        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success' and result.get('pdf'):
                # Decode base64 PDF
                pdf_bytes = base64.b64decode(result['pdf'])
                with open(output_path, 'wb') as f:
                    f.write(pdf_bytes)
                print(f"✅ PDF compiled successfully via LaTeX.Base!")
                return True

        print(f"❌ LaTeX.Base failed: {response.status_code}")
        return False

    except Exception as e:
        print(f"❌ LaTeX.Base error: {e}")
        return False


def compile_with_overleaf_gateway(tex_content: str, output_path: str) -> bool:
    """
    Compile using Overleaf's public gateway
    """
    try:
        print(f"📤 Trying Overleaf Gateway API...")

        # Overleaf's compile endpoint (uses their public gateway)
        url = "https://www.overleaf.com/docs"

        # Note: This is a simplified approach - real Overleaf API requires auth
        # We'll try the public compile endpoint
        compile_url = "https://www.overleaf.com/project/compile"

        # This typically requires authentication
        print(f"⚠️  Overleaf API requires authentication - skipping")
        return False

    except Exception as e:
        print(f"❌ Overleaf error: {e}")
        return False


def compile_with_anonfiles(tex_content: str, output_path: str) -> bool:
    """
    Use a simple LaTeX compilation service
    """
    try:
        print(f"📤 Trying LaTeXML service...")

        # Try using a public LaTeX service
        url = "http://latex.codecogs.com/pdf.download"

        # Create a minimal LaTeX document if needed
        params = {
            'latex': tex_content
        }

        response = requests.get(url, params=params, timeout=90)

        if response.status_code == 200 and response.content[:4] == b'%PDF':
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ PDF compiled successfully!")
            return True

        return False

    except Exception as e:
        print(f"❌ LaTeXML error: {e}")
        return False


def compile_with_pdflatex_online(tex_content: str, output_path: str) -> bool:
    """
    Try pdflatex.online service
    """
    try:
        print(f"📤 Trying PDFLaTeX.Online...")

        url = "https://pdflatex.online/compile"

        files = {
            'file': ('document.tex', tex_content, 'text/plain')
        }

        response = requests.post(url, files=files, timeout=90)

        if response.status_code == 200 and response.content[:4] == b'%PDF':
            with open(output_path, 'wb') as f:
                f.write(response.content)
            print(f"✅ PDF compiled successfully via PDFLaTeX.Online!")
            return True

        print(f"❌ PDFLaTeX.Online failed: {response.status_code}")
        return False

    except Exception as e:
        print(f"❌ PDFLaTeX.Online error: {e}")
        return False


def compile_with_latex_http(tex_content: str, output_path: str) -> bool:
    """
    Use latex.http.com service
    """
    try:
        print(f"📤 Trying LaTeX.HTTP service...")

        # Create a POST request with the LaTeX content
        url = "https://latex.http.com/compile"

        data = {
            'content': tex_content,
            'engine': 'pdflatex'
        }

        response = requests.post(url, json=data, timeout=90)

        if response.status_code == 200:
            result = response.json()
            if result.get('pdf_url'):
                # Download the PDF
                pdf_response = requests.get(result['pdf_url'], timeout=60)
                if pdf_response.status_code == 200:
                    with open(output_path, 'wb') as f:
                        f.write(pdf_response.content)
                    print(f"✅ PDF compiled successfully!")
                    return True

        return False

    except Exception as e:
        print(f"❌ LaTeX.HTTP error: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("Usage: python overleaf_compiler.py <path_to_tex_file>")
        sys.exit(1)

    tex_path = sys.argv[1]

    if not os.path.exists(tex_path):
        print(f"Error: File not found: {tex_path}")
        sys.exit(1)

    # Read LaTeX content
    with open(tex_path, 'r', encoding='utf-8') as f:
        tex_content = f.read()

    # Output path
    output_path = tex_path.replace('.tex', '.pdf')

    print(f"\n{'='*80}")
    print(f"COMPILING LATEX TO PDF VIA ONLINE SERVICES")
    print(f"{'='*80}\n")
    print(f"Input:  {tex_path}")
    print(f"Output: {output_path}\n")

    # Try different services in order
    services = [
        compile_with_pdflatex_online,
        compile_with_latexbase,
        compile_with_latex_http,
    ]

    for service in services:
        if service(tex_content, output_path):
            file_size = os.path.getsize(output_path) / 1024  # KB
            print(f"\n{'='*80}")
            print(f"✅ SUCCESS! PDF created ({file_size:.1f} KB)")
            print(f"Location: {output_path}")
            print(f"{'='*80}\n")
            return
        print()  # Empty line between attempts

    # All services failed
    print(f"\n{'='*80}")
    print(f"❌ All online compilation services failed.")
    print(f"\nManual alternatives:")
    print(f"1. Upload to Overleaf: https://overleaf.com/project/new")
    print(f"2. Install BasicTeX: brew install --cask basictex")
    print(f"3. Use online compiler: https://www.latex-online.com/")
    print(f"{'='*80}\n")
    sys.exit(1)


if __name__ == '__main__':
    main()
