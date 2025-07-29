#!/bin/bash
# AutoUAM Release Script
# Ensures we use the correct twine version for PyPI uploads

set -e

echo "🚀 AutoUAM Release Script"
echo "=========================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Must run from the AutoUAM project root"
    exit 1
fi

# Ensure we have the correct twine version
echo "📦 Installing/updating twine 3.8.0..."
python -m pip install "twine==3.8.0"

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf dist/ build/ *.egg-info/

# Build the package
echo "🔨 Building package..."
python -m build

# Check the package (optional but recommended)
echo "✅ Checking package..."
twine check dist/*

# Upload to PyPI
echo "📤 Uploading to PyPI..."
twine upload dist/* --skip-existing

echo "🎉 Release complete!"
echo "View at: https://pypi.org/project/autouam/"
