#!/bin/bash

echo -e "\nLaunching the tool for creating latex files from folder architecture..."

# Récupérer les dossiers qui suivent le motif ./Figures_BC_*
dossiers=(./Figures_BC_*)
echo -e "       \e[32mOK:\e[0m Asked for folders: ${dossiers}"

# Type de fichier
type_fichier='pdf'
echo -e "       \e[32mOK:\e[0m Asked for figures in format: ${type_fichier}"

# Noms des types de données à grouper
donnees=("mesh" "bathy" "radiusratio" "resolution")
echo -e "       \e[32mOK:\e[0m Asked for datas: ${donnees}"

# Noms des zones à afficher
zones=("complet" "zoom_ilelongue" "zoom_pointepenhir" "zoom_port" "zoom_bassinest")
echo -e "       \e[32mOK:\e[0m Asked for zones: ${zones}"


# Début de la boucle sur les données
echo -e "\nBeginning the latex creation..."
echo -e "\nIterating on datas..."
for donnee in "${donnees[@]}"; do
	
# Nom du fichier LaTeX de sortie
output_file="figures_${donnee}.tex"
echo -e "       \e[32mOK:\e[0m Asked for the creation of tex file: ${output_file}"

# Initialisation du fichier LaTeX
cat << 'EOF' > $output_file
\documentclass{article}
\usepackage{graphicx}
\usepackage{caption}
\usepackage[a4paper, margin=0in]{geometry}

\begin{document}
EOF


# Début de la boucle sur les dossiers
for dossier in "${dossiers[@]}"; do

# Vérifier si l'élément est un dossier
if [ -d "$dossier" ]; then
echo -e "       \e[32mOK:\e[0m ${dossier}"

# Ajout du header pour une figure sur une nouvelle page
cat << EOF >> $output_file

\newpage
\begin{figure}[htbp]
    \centering
EOF


# Début de la boucle sur les zones
for zone in "${zones[@]}"; do

# Définition du chemin de la figure
fichier=${dossier}/${donnee}_${zone}.${type_fichier}

# Vérification de l'existance du fichier
if [ -e "${fichier}" ]; then
echo -e "       \e[32mOK:\e[0m $fichier"

# Ajout du includegraphics pour le fichier
cat << EOF >> $output_file
    \includegraphics[]{$fichier}
EOF

# Si le fichier n'existe pas il est passé 
else
echo -e "  \e[33mWARNING:\e[0m File not found: $fichier"

fi

# Sortie de la boucle sur les zones
done


# Remplacer les underscores par \_ dans le nom du dossier pour le caption
dossier_caption="${dossier//_/\\_}"

# Ajouter le caption de la figure au fichier LaTeX
cat << EOF >> $output_file
    \caption{Figures de $dossier_caption}
\end{figure}
EOF
fi

# Sortie de la boucle sur les dossiers
done


# Finalisation du fichier LaTeX
cat << 'EOF' >> $output_file

\end{document}
EOF

echo -e "       \e[32mOK:\e[0m Ended the construction of LaTeX file : $output_file\n"

# Sortie de la boucle sur les données
done
