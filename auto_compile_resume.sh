#!/bin/bash
#
# Automated Resume Compilation Script
# Tries multiple methods to convert .tex to .pdf
#

set -e

TEX_FILE="$1"

if [ -z "$TEX_FILE" ]; then
    echo "Usage: ./auto_compile_resume.sh <path_to_tex_file>"
    exit 1
fi

if [ ! -f "$TEX_FILE" ]; then
    echo "❌ File not found: $TEX_FILE"
    exit 1
fi

PDF_FILE="${TEX_FILE%.tex}.pdf"

echo "================================================================================"
echo "                   AUTOMATED LATEX TO PDF COMPILATION"
echo "================================================================================"
echo ""
echo "Input:  $TEX_FILE"
echo "Output: $PDF_FILE"
echo ""

# Method 1: Local pdflatex
echo "🔍 Method 1: Checking for local pdflatex..."
if command -v pdflatex &> /dev/null; then
    echo "✅ Found pdflatex, compiling..."
    DIR=$(dirname "$TEX_FILE")
    FILENAME=$(basename "$TEX_FILE")
    cd "$DIR"
    pdflatex -interaction=nonstopmode "$FILENAME" > /dev/null 2>&1

    if [ -f "$PDF_FILE" ]; then
        # Clean up auxiliary files
        rm -f "${TEX_FILE%.tex}.aux" "${TEX_FILE%.tex}.log" "${TEX_FILE%.tex}.out" 2>/dev/null
        SIZE=$(du -h "$PDF_FILE" | cut -f1)
        echo "✅ SUCCESS! PDF created via pdflatex ($SIZE)"
        echo "   Location: $PDF_FILE"
        echo ""
        echo "================================================================================"
        exit 0
    fi
else
    echo "❌ pdflatex not found"
fi

echo ""

# Method 2: Docker
echo "🐳 Method 2: Trying Docker..."
if command -v docker &> /dev/null; then
    echo "✅ Docker found, pulling LaTeX image..."
    docker pull texlive/texlive:latest > /dev/null 2>&1

    echo "🔨 Compiling with Docker..."
    DIR=$(dirname "$(realpath "$TEX_FILE")")
    FILENAME=$(basename "$TEX_FILE")

    docker run --rm \
        -v "$DIR:/workdir" \
        -w /workdir \
        texlive/texlive:latest \
        pdflatex -interaction=nonstopmode "$FILENAME" > /dev/null 2>&1

    if [ -f "$PDF_FILE" ]; then
        # Clean up auxiliary files
        rm -f "${TEX_FILE%.tex}.aux" "${TEX_FILE%.tex}.log" "${TEX_FILE%.tex}.out" 2>/dev/null
        SIZE=$(du -h "$PDF_FILE" | cut -f1)
        echo "✅ SUCCESS! PDF created via Docker ($SIZE)"
        echo "   Location: $PDF_FILE"
        echo ""
        echo "================================================================================"
        exit 0
    fi
else
    echo "❌ Docker not found"
fi

echo ""

# Method 3: Python automation (Overleaf)
echo "🌐 Method 3: Trying Overleaf automation..."
if [ -f "overleaf_auto_compiler.py" ]; then
    echo "✅ Running browser automation..."
    python overleaf_auto_compiler.py "$TEX_FILE"

    if [ -f "$PDF_FILE" ]; then
        SIZE=$(du -h "$PDF_FILE" | cut -f1)
        echo "✅ SUCCESS! PDF created via Overleaf ($SIZE)"
        echo "   Location: $PDF_FILE"
        echo ""
        echo "================================================================================"
        exit 0
    fi
else
    echo "❌ overleaf_auto_compiler.py not found"
fi

echo ""

# All methods failed
echo "================================================================================"
echo "❌ ALL AUTOMATED METHODS FAILED"
echo "================================================================================"
echo ""
echo "Please try one of these manual methods:"
echo ""
echo "1. Web Interface (Easiest):"
echo "   open open_in_overleaf.html"
echo "   Then upload: $TEX_FILE"
echo ""
echo "2. Install LaTeX locally (One-time setup):"
echo "   /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
echo "   brew install --cask basictex"
echo "   Then run this script again"
echo ""
echo "3. Install Docker:"
echo "   Download from: https://www.docker.com/products/docker-desktop"
echo "   Then run this script again"
echo ""
echo "================================================================================"
exit 1
