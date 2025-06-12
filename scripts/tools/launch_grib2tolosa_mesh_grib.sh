#!/bin/bash

# Script for grib2tolosa_mpi processing

# Default values
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORKING_DIR=$(pwd)
GRIB2TOLOSA_PATH=~/SOFTS/grib2tolosa/grib2tolosa_mpi  # Default path - Replace with actual path
DEFAULT_GRIB_FILE=~/DATA/CONFIG_DATA/grib/ATL/20090121000000_20090126230000_AROME_1h_0.01deg.tar  # Default grib file path
OUTPUT_PATH="${WORKING_DIR}"
MESH_FILE=""
GRIB_FILE=""
CHARNOCK_METHOD=3
CHARNOCK_VALUE=0.028

# Function to display usage information
usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -m <path>      Path to mesh file (*_latlong.msh) - if not provided, will use first *_latlong.msh file in working directory"
    echo "  -g <path>      Path to grib file (default: $DEFAULT_GRIB_FILE)"
    echo "  -p <path>      Path to grib2tolosa_mpi executable (default: $GRIB2TOLOSA_PATH)"
    echo "  -o <path>      Output directory for processed files (default: current directory)"
    echo "  -c             Charnock stress computation method (default: 3)"
    echo "  -v             Charnock coefficient value (default: 0.028)"
    echo "  -h             Display this help message"
    exit 1
}

# Parse command line arguments
while getopts "m:g:p:oi:m:c:h" opt; do
    case $opt in
        m) MESH_FILE="$OPTARG" ;;
        g) GRIB_FILE="$OPTARG" ;;
        p) GRIB2TOLOSA_PATH="$OPTARG" ;;
        o) OUTPUT_PATH="$OPTARG" ;;
        c) CHARNOCK_METHOD="$OPTARG" ;;
        v) CHARNOCK_VALUE="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

# Handle mesh file - if not provided, use first *_latlong.msh file in working directory
if [ -z "$MESH_FILE" ]; then
    MESH_FILE=$(find "$WORKING_DIR" -maxdepth 1 -name "*_latlong.msh" | head -n 1)
    if [ -z "$MESH_FILE" ]; then
        echo "Error: No *_latlong.msh file found in current directory. Please provide a mesh file with -m option."
        exit 1
    fi
    echo "Using mesh file: $MESH_FILE"
fi

# Ensure mesh file exists
if [ ! -f "$MESH_FILE" ]; then
    echo "Error: Mesh file $MESH_FILE does not exist"
    exit 1
fi

# Convert to absolute path
MESH_FILE=$(realpath "$MESH_FILE")

# Handle grib file - if not provided, use default path
if [ -z "$GRIB_FILE" ]; then
    GRIB_FILE="$DEFAULT_GRIB_FILE"
    echo "Using default grib file: $GRIB_FILE"
fi

# Ensure grib file exists
if [ ! -f "$GRIB_FILE" ]; then
    echo "Error: Grib file $GRIB_FILE does not exist"
    exit 1
fi

# Convert to absolute path
GRIB_FILE=$(realpath "$GRIB_FILE")

# Extract the directory containing the grib2tolosa_mpi executable
GRIB2TOLOSA_DIR=$(dirname "$GRIB2TOLOSA_PATH")

# Create symbolic links towards the grib_2_tolosa executable, the mesh and the grib files
echo "Creating symbolic links to mesh and grib files..."
ln -sf "$MESH_FILE" "${WORKING_DIR}/input.msh"
ln -sf "$GRIB_FILE" "${WORKING_DIR}/input.grb"
ln -sf "$GRIB2TOLOSA_PATH" "${WORKING_DIR}/grib2tolosa_mpi"

# Run grib2tolosa_mpi
echo "Running grib2tolosa_mpi..."
echo "$GRIB2TOLOSA_PATH $CHARNOCK_METHOD $CHARNOCK_VALUE"
./$(basename "$GRIB2TOLOSA_PATH $CHARNOCK_METHOD $CHARNOCK_VALUE")

# Check if the command was successful
if [ $? -ne 0 ]; then
    echo "Error: grib2tolosa_mpi execution failed"
    popd > /dev/null
    exit 1
fi




# # Create output directory if it doesn't exist
# mkdir -p "$OUTPUT_PATH"
# OUTPUT_PATH=$(realpath "$OUTPUT_PATH")
# 
# # Clean up any existing symbolic links in the grib2tolosa directory
# echo "Cleaning up grib2tolosa directory..."
# echo BEFORE
# ls $GRIB2TOLOSA_DIR
# if [ -d "$GRIB2TOLOSA_DIR" ]; then
#     rm -f "${GRIB2TOLOSA_DIR}"/input.msh "${GRIB2TOLOSA_DIR}"/input.grb
#     rm "${GRIB2TOLOSA_DIR}"/forcing*.a "${GRIB2TOLOSA_DIR}"/forcing*.b
# else
#     echo "Error: grib2tolosa directory $GRIB2TOLOSA_DIR does not exist"
#     exit 1
# fi
# 
# echo AFTER 
# ls $GRIB2TOLOSA_DIR
# 
# # Create symbolic links to mesh and grib files
# echo "Creating symbolic links to mesh and grib files..."
# ln -sf "$MESH_FILE" "${GRIB2TOLOSA_DIR}/input.msh"
# ln -sf "$GRIB_FILE" "${GRIB2TOLOSA_DIR}/input.grb"
# 
# # Change to grib2tolosa directory
# echo "Changing to grib2tolosa directory: $GRIB2TOLOSA_DIR"
# pushd "$GRIB2TOLOSA_DIR" > /dev/null
# 
# # Run grib2tolosa_mpi
# echo "Running grib2tolosa_mpi..."
# echo "$GRIB2TOLOSA_PATH $CHARNOCK_METHOD $CHARNOCK_VALUE"
# ./$(basename "$GRIB2TOLOSA_PATH $CHARNOCK_METHOD $CHARNOCK_VALUE")
# 
# # Check if the command was successful
# if [ $? -ne 0 ]; then
#     echo "Error: grib2tolosa_mpi execution failed"
#     popd > /dev/null
#     exit 1
# fi
# 
# # Copy all resulting forcing.* files back to the output directory
# echo "Copying resulting files to output directory: $OUTPUT_PATH"
# cp -f forcing.* "$OUTPUT_PATH/"
# 
# # Return to original directory
# popd > /dev/null
# 
# # Clean up symbolic links
# echo "Cleaning up symbolic links..."
# rm -f "${GRIB2TOLOSA_DIR}/input.msh" "${GRIB2TOLOSA_DIR}/input.grb"
# 
# # Clean up old results
# echo "Cleaning up old results..."
# rm "${GRIB2TOLOSA_DIR}/forcing.*"
# 
# echo "All processing complete. Output files are in $OUTPUT_PATH"
