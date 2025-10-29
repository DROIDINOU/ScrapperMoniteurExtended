#!/usr/bin/env bash
# Exit on error
set -o errexit

# Installe les dépendances depuis requirements.txt
echo "Installation des dépendances..."
pip install -r requirements.txt

# Collecte les fichiers statiques pour la production
echo "Collecte des fichiers statiques..."
python manage.py collectstatic --no-input

# Créer le répertoire staticfiles si nécessaire
if [ ! -d "staticfiles" ]; then
    echo "Création du répertoire staticfiles"
    mkdir staticfiles
else
    echo "Le répertoire staticfiles existe déjà."
fi

# Applique les migrations de la base de données
echo "Application des migrations..."
#python manage.py migrate
