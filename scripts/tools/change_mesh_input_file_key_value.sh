#!/bin/bash

# Vérifier qu'on a bien deux arguments
if [ $# -ne 3 ]; then
    echo "Usage: $0 fichier texte_a_chercher nouveau_texte"
    exit 1
fi

# Récupérer les arguments
fichier=$1
texte_recherche=$2
nouveau_texte=$3

# Appliquer la transformation avec sed
# sed -E "s/([0-9]+ [0-9]+) \"[^\"]*\"( \"$texte_recherche\")?$/\1 \"$nouveau_texte\" \"$texte_recherche\"/g" $fichier > $fichier.new
# sed -E "/\"$texte_recherche\"/ s/([0-9]+ [0-9]+) \"([^\"]*)\"$/\1 \"$nouveau_texte\" \"$texte_recherche\"/g" $fichier > $fichier.new

sed -i -E "/\"$texte_recherche\"/ {
    # Cas 1: ligne avec un seul groupe de guillemets comme '1 6 \"penfeld\"'
    s/([0-9]+ [0-9]+) \"$texte_recherche\"$/\1 \"$nouveau_texte\" \"$texte_recherche\"/g;
    # Cas 2: ligne avec deux groupes de guillemets comme '1 6 \"truc\" \"penfeld\"'
    s/([0-9]+ [0-9]+) \"[^\"]+\" \"$texte_recherche\"$/\1 \"$nouveau_texte\" \"$texte_recherche\"/g;
}" $fichier

