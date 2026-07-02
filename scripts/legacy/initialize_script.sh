#!/bin/csh

source /usr/share/Modules/3.2.10/init/csh

# Charger le module nécessaire
module load intel-fc-20/19.1.3

# Sauvegarder le chemin de départ
set start_path = $cwd

# Définir le chemin vers le répertoire cini
set path_cini = ~/SOFTS/config_prep_tools/cini

# Boucle sur les fichiers/répertoires commençant par "BC_"
foreach f (BC_*)
    echo $f

    # Créer des liens symboliques
    ln -sf ${start_path}/$f/Version_0_2_laterales_ligne_offshore_no_buffer_islands_reprojstereo_latlong.msh $path_cini/input.msh
    ln -sf ${start_path}/$f/regional.depth-ele.a $path_cini/regional.depth.a

    # Exécuter la commande inicon dans le répertoire cini
    cd $path_cini
    ./inicon
    sleep 5

    # Copier les fichiers résultants et revenir au répertoire initial
    cd $start_path/$f
    cp $path_cini/rest_* .
    cd $start_path
end

# Décharger tous les modules
module purge
