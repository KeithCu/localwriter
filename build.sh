#!/bin/bash
# Script to create the .oxt package for the LocalWriter extension

# Extension name
EXTENSION_NAME="localwriter"

# Remove old package if it exists
if [ -f "${EXTENSION_NAME}.oxt" ]; then
    echo "Removing old package..."
    rm "${EXTENSION_NAME}.oxt"
fi

# Create the new package
# Create the new package
echo "Creating package ${EXTENSION_NAME}.oxt..."
# We need to include 'plugin' as a directory, and everything *inside* 'extension' at the root.
(cd extension && zip -r "../${EXTENSION_NAME}.oxt" . -x "*.git*" -x "*.DS_Store" -x "__pycache__*" -x "*.pyc")
zip -r "${EXTENSION_NAME}.oxt" \
    plugin/ \
    -x "*.git*" -x "*.DS_Store" -x "__pycache__*" -x "*.pyc"

if [ $? -eq 0 ]; then
    echo "✅ Package created successfully: ${EXTENSION_NAME}.oxt"
    echo ""
    echo "To install:"
    echo "  1. Open LibreOffice"
    echo "  2. Tools → Extension Manager"
    echo "  3. Add → Select ${EXTENSION_NAME}.oxt"
    echo ""
    echo "Or via command line:"
    echo "  unopkg add ${EXTENSION_NAME}.oxt"
else
    echo "❌ Error creating package"
    exit 1
fi
