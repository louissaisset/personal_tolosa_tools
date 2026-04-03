#!/bin/bash

usage() {
    cat <<EOF
Usage: $(basename "$0") [options]

Description:
  Prepare configuration and run prmsl_ref tool using a .msh mesh file.

Options:
  -m <file>   Specify .msh file (default: auto-detect *_latlong.msh)
  -r <file>   Reference atmospheric pressure NetCDF file
              (default: $REF_ATM_PRES_FILE)
  -p <file>   prmsl_ref python executable
              (default: $PRMSL_REF_EXE)
  -h          Display this help and exit

Examples:
  $(basename "$0")
  $(basename "$0") -m mesh_latlong.msh
  $(basename "$0") -r my_data.nc -p ./exe.py

Notes:
  - If no .msh file is provided, the script searches for *_latlong.msh
  - The script must be run in a directory containing mesh files
EOF
}

# Get the global path of the current directory
CURRENT_DIR=$(pwd)

# Hardcoded paths towards the data files and the prmsl_ref scripts
REF_ATM_PRES_FILE=/home/ext/sh/csho/saissetl/DATA/CONFIG_DATA/mean_ERA5_2010-2019.nc
PRMSL_REF_EXE=/home/ext/sh/csho/saissetl/SOFTS/config_prep_tools/prmsl_ref/exe.py

# Default values (already defined in your script)
MSH_FILE=""
# REF_ATM_PRES_FILE already set
# PRMSL_REF_EXE already set

# Parse options
while getopts ":m:r:p:h" opt; do
    case ${opt} in
        m )
            MSH_FILE="$OPTARG"
            ;;
        r )
            REF_ATM_PRES_FILE="$OPTARG"
            ;;
        p )
            PRMSL_REF_EXE="$OPTARG"
            ;;
        h )
            usage
            exit 0
            ;;
        \? )
            echo "Error: Invalid option -$OPTARG" >&2
            usage
            exit 1
            ;;
        : )
            echo "Error: Option -$OPTARG requires an argument." >&2
            usage
            exit 1
            ;;
    esac
done

shift $((OPTIND -1))

# If user did not provide a .msh file, auto-detect
if [ -z "$MSH_FILE" ]; then

    txtCount=$(find . -maxdepth 1 -name "*.msh" -type f | wc -l)

    if [ "$txtCount" -gt 1 ]; then
        echo -e "  \e[33mWARNING:\e[0m Multiple .msh files found"
    fi

    MSH_FILE=$(find . -maxdepth 1 -name "*_latlong.msh" -type f | sort | head -1)

fi

# Validate .msh file
if [ -z "$MSH_FILE" ] || [ ! -f "$MSH_FILE" ]; then
    echo -e "    \e[31mERROR:\e[0m No valid .msh file found."
    echo -e "    \e[31mERROR:\e[0m Use -m option or ensure *_latlong.msh exists."
    exit 1
else
    echo -e "       \e[32mOK:\e[0m Using .msh file: $MSH_FILE"
fi

# # # Find the first file matching the pattern *_latlong.msh
# # MSH_FILE=$(find "$CURRENT_DIR" -name "*_latlong.msh" | head -n 1 | xargs basename)
# # Vérifier l'existence d'un fichier .msh dans le dossier
# if [ ! `ls *_latlong.msh >& /dev/null; echo $status` ]; then
# 
#     # Ajout d'un warning si de multiples fichiers .msh existent dans le dossier
#     txtCount=$(find . -maxdepth 1 -name "*.msh" -type f | wc -l)
#     if [ $txtCount > 1 ]; then
#         echo -e "  \e[33mWARNING:\e[0m Multiple .msh files found"
#     fi
#     
#     # Utilisation de find pour récupérer seulement le premier fichier _latlong.msh
#     MSH_FILE=$(find . -maxdepth 1 -name "*_latlong.msh" -type f | sort | head -1)
#     
#     # Si il y a au moins un fichier .msh
#     if [ -f "$MSH_FILE" ]; then
#         echo -e "       \e[32mOK:\e[0m Found .msh file: $MSH_FILE"
# 
#     else
#         echo -e "    \e[31mERROR:\e[0m No .msh files found in the current directory."
#         echo -e "    \e[31mERROR:\e[0m Cannot proceed without either no argument or an existing .msh file"
#         exit 1
#     fi
# else
#     echo -e "    \e[31mERROR:\e[0m No .msh files found in the current directory."
#     echo -e "    \e[31mERROR:\e[0m Cannot proceed without either no argument or an existing .msh file"
#     exit 1
# fi

# Ensure Reference pressure file exists
if [ ! -f "$REF_ATM_PRES_FILE" ]; then
    echo -e "    \e[31mERROR:\e[0m Mean pressure NetCDF file does not exist: $REF_ATM_PRES_FILE"
    exit 1
fi

# Ensure python executable exists
if [ ! -f "$PRMSL_REF_EXE" ]; then
    echo -e "    \e[31mERROR:\e[0m Python executable file does not exist: $PRMSL_REF_EXE"
    exit 1
fi

# Create symbolic link to the ERA5 data
ln -sf $REF_ATM_PRES_FILE mean_ERA5_2010-2019.nc
echo -e "       \e[32mOK:\e[0m Created a symbolic link towards $REF_ATM_PRES_FILE"
ln -sf $PRMSL_REF_EXE prmsl_ref_exe
echo -e "       \e[32mOK:\e[0m Created a symbolic link towards $PRMSL_REF_EXE"

# Define the content of the config.yaml file
CONFIG_CONTENT="# =============================================================================
# Reference atmospheric pressure generator : config file
# =============================================================================

inputs_path : $CURRENT_DIR/
outputs_path : $CURRENT_DIR/

#output_deg.msh
msh_deg_filename : $MSH_FILE

# mean nc file
ref_atm_pres_filename : mean_ERA5_2010-2019.nc

# params
# interpolation method amond linear and cubic
method : cubic

# among big and little
endianness : little
"

# Write the content to config.yaml
echo "$CONFIG_CONTENT" > config.yaml
echo -e "       \e[32mOK:\e[0m Created config.yaml"

# Launch prmsl
echo "Launching prmsl_ref_exe..."
python3 $CURRENT_DIR/prmsl_ref_exe
