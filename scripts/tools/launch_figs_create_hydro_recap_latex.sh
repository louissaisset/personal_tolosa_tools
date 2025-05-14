#!/bin/bash

# Function to display help information
display_help() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
  -h, --help               Display this help message and exit.
  -f, --dossiers           List of directories to process. Default: (${dossiers[@]})
  -d, --donnees            List of data files to process. Default: (${donnees[@]})
  -z, --zones              List of zones to process. Default: (${zones[@]})
  -ti, --tstart            Start time for processing. Default: $tstart
  -tf, --tstop             Stop time for processing. Default: $tstop
  -ts, --tstep             Time step for processing. Default: $tstep
  --type_fichier           Type of file to process.

Examples:
  $0 -f dir1 dir2 --donnees data1 data2 -z zone1 zone2 -ti 0 -tf 100 -ts 10 --type_fichier csv
  $0 --dossiers dir1 --donnees data1 --zones zone1 --tstart 0 --tstop 100 --tstep 10 --type_fichier csv
EOF
}

echo -e "\nLaunching the tool for creating latex files from folder architecture..."

# Récupérer les dossiers qui suivent le motif ./Figures_BC_*
dossiers=("./Fig*")

# Noms des types de données à grouper
donnees=("ssh_u_v")

# Noms des zones à afficher
zones=("complet" "zoom_ilelongue" "zoom_pointepenhir" "zoom_port" "zoom_bassinest")

# noms des pas de temps à conserver
tstart=0
tstop=99
tstep=1

# Type de fichier
type_fichier='png'

# Check if -h or --help is in the arguments
for arg in "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
        display_help
        exit 0
    fi
done

# Gérer la déclaration d'arguments spécifiques
while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
       display_help
       exit 0
       ;;
    -f|--dossiers)
      shift
      dossiers=()
      while [[ $# -gt 0 && "$1" != -* ]]; do
        dossiers+=("$1")
        shift
      done
      ;;
    -d|--donnees)
      shift
      donnees=()
      while [[ $# -gt 0 && "$1" != -* ]]; do
        donnees+=("$1")
        shift
      done
      ;;
    -z|--zones)
      shift
      zones=()
      while [[ $# -gt 0 && "$1" != -* ]]; do
        zones+=("$1")
        shift
      done
      ;;
    -ti|--tstart)
      tstart="$2"
      shift 2
      ;;
    -tf|--tstop)
      tstop="$2"
      shift 2
      ;;
    -ts|--tstep)
      tstep="$2"
      shift 2
      ;;
    --type_fichier)
      type_fichier="$2"
      shift 2
      ;;
    *)
      echo "Invalid option: -$1" 
      exit 1
      ;;
  esac
done


timesteps=$(seq -f "%05g" $tstart $tstep $tstop)


echo -e "       \e[32mOK:\e[0m Asked for folders: ${dossiers}"
echo -e "       \e[32mOK:\e[0m Asked for datas: ${donnees}"
echo -e "       \e[32mOK:\e[0m Asked for zones: ${zones}"
echo -e "       \e[32mOK:\e[0m Asked for time range: ${tstart} ${tstep} ${tstop}"
echo -e "       \e[32mOK:\e[0m Asked for figures in format: ${type_fichier}"



# Début de la boucle sur les données
echo -e "\nBeginning the latex creation..."
echo -e "\nIterating on datas..."
for donnee in "${donnees[@]}"; do
	
# Nom du fichier LaTeX de sortie
output_file="figures_${donnee}.tex"
echo -e "       \e[32mOK:\e[0m Asked for the creation of tex file: ${output_file}"

# Initialisation du fichier LaTeX
cat << 'EOF' > $output_file
\documentclass{Shom_doc}
% % Pour OVERLEAF UTILISER LA LIGNE SUIVANTE
% \documentclass{Shom_template_contents/Shom_doc}

% % ADD RED STAMPS FOR DR DOCUMENTS
% \makeDR

% ADD RED AND BLUE STAMPS FOR DRSF DOCUMENTS
% \makeDRSF



%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%% START OF DOCUMENT %%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

\begin{document}

% Apply first page geometry and style
\firstpagegeometry
\thispagestyle{firstpage}

\begin{flushright}
    Direction des opérations, de la production et des services,\\
    Division des Sciences et Techniques marines,\\
    Département Recherche Océanographie physique\\[\baselineskip]
    Toulouse, le \today\\[\baselineskip]
    N° \hspace{1cm}/Shom/DOPS/STM/SUBMAR\\[\baselineskip]
\end{flushright}

\begin{center}
    \textbf{COMPTE RENDU}\\
    Relatif aux efforts de production numérique de l'état des surcote dans la rade de Brest
\end{center}

\begin{table}[!ht]
\begin{tabular}{llp{15cm}}
\textbf{OBJET}              & : & Récapitulatif exhaustif des caractéristiques des maillages utilisés\\
\end{tabular}
\end{table}


\section*{Abstract}

Document d'annexe présentant les caractéristiques des maillages pour une série de configurations numériques




%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%


\clearpage
\restoregeometry       % Apply original page geometry for subsequent pages

\listoffigures
EOF


# Début de la boucle sur les dossiers
for dossier in $dossiers; do

# Vérifier si l'élément est un dossier
if [ -d "$dossier" ]; then
echo -e "       \e[32mOK:\e[0m ${dossier}"

# Début de la boucle sur les pas de temps
for timestep in $timesteps; do

# Ajout du header pour une figure sur une nouvelle page
cat << EOF >> $output_file

\newpage
\noindent\makebox[\linewidth]{%
\begin{minipage}{20cm}
    \centering
EOF


# Début de la boucle sur les zones
for zone in "${zones[@]}"; do

# Définition du chemin de la figure
fichier=${dossier}/${donnee}_${zone}_${timestep}.${type_fichier}

# Vérification de l'existence du fichier
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
dossier_caption="${dossier//_/\\_\\-}"

# Ajouter le caption de la figure au fichier LaTeX
cat << EOF >> $output_file
    \captionof{figure}{Pas de temps ${timestep} de la simulation $dossier_caption}
\end{minipage}%
}
EOF

# Sortie de la boucle sur les pas de temps
done

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
