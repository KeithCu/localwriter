#!/bin/bash
# Script de création du package .oxt pour l'extension LocalWriter

# Nom de l'extension
EXTENSION_NAME="localwriter"

# Supprime l'ancien package s'il existe
if [ -f "${EXTENSION_NAME}.oxt" ]; then
    echo "Suppression de l'ancien package..."
    rm "${EXTENSION_NAME}.oxt"
fi

# Crée le nouveau package
echo "Création du package ${EXTENSION_NAME}.oxt..."
zip -r "${EXTENSION_NAME}.oxt" \
    Accelerators.xcu \
    Addons.xcu \
    description.xml \
    main.py \
    META-INF/ \
    registration/ \
    assets/ \
    -x "*.git*" -x "*.DS_Store"

if [ $? -eq 0 ]; then
    echo "✅ Package créé avec succès : ${EXTENSION_NAME}.oxt"
    echo ""
    echo "Pour installer :"
    echo "  1. Ouvrez LibreOffice"
    echo "  2. Outils → Gestionnaire des extensions"
    echo "  3. Ajouter → Sélectionnez ${EXTENSION_NAME}.oxt"
    echo ""
    echo "Ou via la ligne de commande :"
    echo "  unopkg add ${EXTENSION_NAME}.oxt"
else
    echo "❌ Erreur lors de la création du package"
    exit 1
fi
