#!/bin/bash
# Build script for the LocalWriter .oxt extension package

# Extension name
EXTENSION_NAME="localwriter"

# Remove old package if it exists
if [ -f "${EXTENSION_NAME}.oxt" ]; then
    echo "Removing old package..."
    rm "${EXTENSION_NAME}.oxt"
fi

# Create the new package
echo "Creating package ${EXTENSION_NAME}.oxt..."
zip -r "${EXTENSION_NAME}.oxt" \
    Accelerators.xcu \
    Addons.xcu \
    assets \
    description.xml \
    main.py \
    pythonpath \
    META-INF \
    registration \
    README.md

if [ $? -eq 0 ]; then
    echo "Package created successfully: ${EXTENSION_NAME}.oxt"
    echo ""
    echo "To install:"
    echo "  1. Open LibreOffice"
    echo "  2. Tools > Extension Manager"
    echo "  3. Add > Select ${EXTENSION_NAME}.oxt"
    echo ""
    echo "Or via command line:"
    echo "  unopkg add ${EXTENSION_NAME}.oxt"
else
    echo "Error creating package"
    exit 1
fi
