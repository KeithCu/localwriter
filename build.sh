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
echo "Creating package ${EXTENSION_NAME}.oxt..."
zip -r "${EXTENSION_NAME}.oxt" \
    core/ \
    Accelerators.xcu \
    Addons.xcu \
    description.xml \
    main.py \
    prompt_function.py \
    chat_panel.py \
    XPromptFunction.rdb \
    LocalWriterDialogs/ \
    META-INF/ \
    registration/ \
    registry/ \
    assets/ \
    -x "*.git*" -x "*.DS_Store"

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
