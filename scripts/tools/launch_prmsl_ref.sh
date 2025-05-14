#!/bin/bash

# Get the global path of the current directory
CURRENT_DIR=$(pwd)

# Find the first file matching the pattern *_latlong.msh
MSH_FILE=$(find "$CURRENT_DIR" -name "*_latlong.msh" | head -n 1 | xargs basename)

# Hardcoded paths towards the data files and the prmsl_ref scripts
REF_ATM_PRES_FILE=/home/ext/sh/csho/saissetl/DATA/CONFIG_DATA/mean_ERA5_2010-2019.nc
PRMSL_REF_EXE=/home/ext/sh/csho/saissetl/SOFTS/config_prep_tools/prmsl_ref/exe.py


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

# Create symbolic link to the ERA5 data
echo "    Create a symbolic link towards $REF_ATM_PRES_FILE"
ln -s $REF_ATM_PRES_FILE mean_ERA5_2010-2019.nc

# Write the content to config.yaml
echo "    Create config.yaml"
echo "$CONFIG_CONTENT" > config.yaml

# Launch prmsl
echo "    Launch prmsl_ref/exe.py"
python3 $PRMSL_REF_EXE
