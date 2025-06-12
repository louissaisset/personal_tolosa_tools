#!/bin/bash

# Improved script for interp_tide_fes2014b processing
# Usage: ./tide_processor.sh [-f forcing_path] [-m mesh_file] [-o output_path]

# Default values
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
WORKING_DIR=$(pwd)
INTERP_TIDE_PATH="/home/ext/sh/csho/saissetl/SAVE/SOFTS/config_prep_tools/global_tide"  # HARD-CODED PATH - Replace with actual path
OUTPUT_PATH="${WORKING_DIR}"
MESH_FILE=""
FORCING_PATH="~/DATA/CONFIG_DATA/fes2022b_elevations_34_tidal_constituents/"

# Function to display usage information
usage() {
    echo "Usage: $0 [options]"
    echo "Options:"
    echo "  -f <path>      Path to forcing file(s) - can be a single file, a folder, wildcards pattern, or a list of files (comma-separated) (default: ~/DATA/CONFIG_DATA/fes2022b_elevations_34_tidal_constituents/)"
    echo "  -m <path>      Path to mesh file (.msh) - if not provided, will use first .msh file in working directory"
    echo "  -o <path>      Output directory for processed files (default: current directory)"
    echo "  -h             Display this help message"
    exit 1
}

# Parse command line arguments
while getopts "f:m:o:h" opt; do
    case $opt in
        f) FORCING_PATH="$OPTARG" ;;
        m) MESH_FILE="$OPTARG" ;;
        o) OUTPUT_PATH="$OPTARG" ;;
        h) usage ;;
        *) usage ;;
    esac
done

# Validate arguments
if [ -z "$FORCING_PATH" ]; then
    echo "Error: Forcing path (-f) is required"
    usage
fi

# Handle mesh file - if not provided, use first .msh file in working directory
if [ -z "$MESH_FILE" ]; then
    MESH_FILE=$(find "$WORKING_DIR" -maxdepth 1 -name "*.msh" | head -n 1)
    if [ -z "$MESH_FILE" ]; then
        echo "Error: No mesh file found in current directory. Please provide a mesh file with -m option."
        exit 1
    fi
    echo "Using mesh file: $MESH_FILE"
fi

# Ensure mesh file exists
if [ ! -f "$MESH_FILE" ]; then
    echo "Error: Mesh file $MESH_FILE does not exist"
    exit 1
fi

MESH_FILE=$(realpath $MESH_FILE)

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_PATH"

# Clean up interp_tide_fes2014b directory
echo "Cleaning up interp_tide_fes2014b directory..."
rm -f "${INTERP_TIDE_PATH}"/forcing.*.a "${INTERP_TIDE_PATH}"/forcing.*.b
rm -f "${INTERP_TIDE_PATH}"/*.nc
rm -f "${INTERP_TIDE_PATH}"/*.msh

# Create symbolic link to mesh file
echo "Creating symbolic link to mesh file..."
ln -sf "$MESH_FILE" "${INTERP_TIDE_PATH}/input.msh"

# Process forcing files
process_forcing_file() {
    local forcing_file="$1"

    # Check if file exists
    if [ ! -f "$forcing_file" ]; then
        echo "Warning: File $forcing_file does not exist, skipping."
        return
    fi
    
    # Get base filename without path and extension
    local filename=$(basename "$forcing_file")
    local basename="${filename%.nc.gz}"
    
    echo "Processing $filename..."
    
    # Create a temporary directory
    local temp_dir=$(mktemp -d)
    
    # Copy the compressed file to temp directory
    cp "$forcing_file" "$temp_dir/"
    
    # Change to temp directory
    pushd "$temp_dir" > /dev/null
    
    # Decompress the file
    gzip -d "$filename"
    local decompressed_file="${filename%.gz}"
     
    # Go to interp_tide_fes2014b directory
    pushd "$INTERP_TIDE_PATH" > /dev/null
    
    # Create symbolic link to the decompressed file
    ln -sf "$temp_dir/$decompressed_file" onde.nc

    # Run interp_tide_fes2014b
    ./interp_tide_fes2014b < param.input
    
    # Move output files to output directory
    mv ./forcing.XXtide.a "$OUTPUT_PATH/forcing.${basename}tide.a"
    mv ./forcing.XXtide.b "$OUTPUT_PATH/forcing.${basename}tide.b"
    
    # Remove symbolic links
    rm -f onde.nc
    
    # Return to temp directory
    popd > /dev/null
    
    # Recompress the file
    gzip "$decompressed_file"
    
    # Return to original directory
    popd > /dev/null
    
    # Clean up temporary directory
    rm -rf "$temp_dir"
    
    echo "Completed processing $filename"
}

# Process forcing files based on input type
if [ -d "$FORCING_PATH" ]; then
    # Process all .nc.gz files in the directory
    echo "Processing all .nc.gz files in directory: $FORCING_PATH"
    for file in "$FORCING_PATH"/*.nc.gz; do
        process_forcing_file "$file"
    done
elif [[ "$FORCING_PATH" == *,* ]]; then
    # Process comma-separated list of files
    echo "Processing specified list of files"
    IFS=',' read -ra FILES <<< "$FORCING_PATH"
    for file in "${FILES[@]}"; do
        process_forcing_file "$file"
    done
elif [ -f "$FORCING_PATH" ]; then
    # Process single file
    echo "Processing single file: $FORCING_PATH"
    process_forcing_file "$FORCING_PATH"
else
    echo "Error: No valid files found matching $FORCING_PATH"
    exit 1
fi

# remove last symbolic link
rm -f ${INTERP_TIDE_PATH}/input.msh

echo "All processing complete. Output files are in $OUTPUT_PATH"
