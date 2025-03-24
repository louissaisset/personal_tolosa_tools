#!/bin/csh

echo "\nBeginning the initialisation using 'cini'..."

# Définir le chemin vers le répertoire cini
set path_cini = ~/SOFTS/config_prep_tools/cini
echo "       \e[32mOK:\e[0m Assumed path to cini: $path_cini"

# Charger le module nécessaire
source /usr/share/Modules/3.2.10/init/csh
module load intel-fc-20/19.1.3
echo "       \e[32mOK:\e[0m Loaded modules: intel-fc-20/19.1.3"

# Sauvegarder le chemin de départ
set start_path = $cwd
echo "       \e[32mOK:\e[0m Selected folder: $start_path"

# Vérifier l'existence d'un fichier .msh dans le dossier
if (! `ls *.msh >& /dev/null; echo $status`) then

    # Ajout d'un warning Si de multiples fichiers .msh existent dans le dossier
    set txtCount = `find . -maxdepth 1 -name "*.msh" -type f | wc -l`
    if ($txtCount > 1) then
        echo "  \e[33mWARNING:\e[0m Multiple .msh files found"
    endif
    
    # Utilisation de find pour récupérer seulement le premier fichier .msh
    set firstmshFile = `find . -maxdepth 1 -name "*.msh" -type f | sort | head -1`
    
    # Si il y a au moins un fichier .msh
    if ("$firstmshFile" != "") then
        
        # Récupération du chemin absolu
        set absolutePathmsh = `realpath "$firstmshFile"`
        echo "       \e[32mOK:\e[0m Found .msh file: $absolutePathmsh"
        
        # Création du lien symbolique
        ln -sf $absolutePathmsh $path_cini/input.msh
        echo "       \e[32mOK:\e[0m Added .msh file symbolic link to $path_cini/input.msh "

    else
        echo "    \e[31mERROR:\e[0m No .msh files found in the current directory."
        exit 1
    endif
else
    echo "    \e[31mERROR:\e[0m No .msh files found in the current directory."
    exit 1
endif


# Vérifier l'existence d'un fichier regional.depth-ele.a dans le dossier
if (! `ls regional.depth-ele.a >& /dev/null; echo $status`) then

    # Récupération du chemin absolu
    set absolutePathregional = `realpath ./regional.depth-ele.a`
    echo "       \e[32mOK:\e[0m Found regional.depth-ele.a: $absolutePathregional"
    
    # Création du lien symbolique
    ln -sf ${start_path}/regional.depth-ele.a $path_cini/regional.depth.a
    echo "       \e[32mOK:\e[0m Added regional.depth-ele.a file symbolic link to $path_cini/input.msh"

else
    echo "    \e[31mERROR:\e[0m No regional.depth-ele.a files found in the current directory."
    exit 1
endif


# Déplacement vers le dossier contenant l'outil cini
cd $path_cini
echo "       \e[32mOK:\e[0m Moved to $path_cini"

# Création des fichiers d'initialisation
echo "\n Beginning the creation of initialisation files..."
./inicon
sleep 5
echo "       \e[32mOK:\e[0m End of cini tool"


set resfiles = `ls $path_cini/rest_*`
echo "       \e[32mOK:\e[0m Initialisation files created by cini: $resfiles"


# Copier les fichiers résultants et revenir au répertoire initial
cd $start_path
echo "       \e[32mOK:\e[0m Moved to $start_path"

cp $path_cini/rest_* .
echo "       \e[32mOK:\e[0m Copied files to current folder"

# Décharger tous les modules
module purge
echo "       \e[32mOK:\e[0m Purged all modules"

