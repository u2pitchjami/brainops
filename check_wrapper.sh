#!/bin/bash

# === CONFIGURATION ===
SCRIPT_DIR=$(dirname "$(realpath "$0")")
source ${SCRIPT_DIR}/obsidian_scripts/.env


# Activer l'environnement virtuel
if [ -d "$ENV_PATH" ]; then
    source "$ENV_PATH/bin/activate"
else
    echo "[$(date)] ERREUR : Environnement virtuel introuvable : $ENV_PATH"
    exit 1
fi

# Exécuter le script Python
if [ -f "$SCRIPT_CHECK" ]; then
    python "$SCRIPT_CHECK"
else
    echo "[$(date)] ERREUR : Script introuvable : $SCRIPT_CHECK"
    deactivate
    exit 1
fi

# Désactiver l'environnement virtuel
deactivate
