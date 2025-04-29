#!/bin/bash

# Define paths
SOURCE_LIST="path/tide/list"
OUTPUT_FILE="tide.list"

# Check if source file exists
if [ ! -f "$SOURCE_LIST" ]; then
    echo "Error: Source file $SOURCE_LIST not found!"
    exit 1
fi

# Copy the header lines (first two lines) to the output file
head -2 "$SOURCE_LIST" > "$OUTPUT_FILE"

# Find available forcing components
COMPONENTS=()
for file in forcing.*tide.a; do
    if [ -f "$file" ]; then
        # Extract component name from filename (between forcing. and tide.a)
        COMPONENT=$(echo "$file" | sed 's/forcing\.\(.*\)tide\.a/\1/')
        
        # Check if corresponding .b file exists
        if [ -f "forcing.${COMPONENT}tide.b" ]; then
            COMPONENTS+=("$COMPONENT")
        fi
    fi
done

# Add NIVMOY to the components list if not already present
if [[ ! " ${COMPONENTS[@]} " =~ " NIVMOY " ]]; then
    COMPONENTS+=("NIVMOY")
fi

# Process each line in the source file and write matching components to output
while IFS= read -r line; do
    # Skip the header lines
    if [[ "$line" == *"Nom /"* || "$line" == "---" ]]; then
        continue
    fi
    
    # Extract component name from the line (first field, trimmed)
    COMPONENT=$(echo "$line" | awk '{print $1}')
    
    # Check if this component should be included
    for comp in "${COMPONENTS[@]}"; do
        if [ "$COMPONENT" == "$comp" ]; then
            echo "$line" >> "$OUTPUT_FILE"
            break
        fi
    done
done < "$SOURCE_LIST"

echo "Generated $OUTPUT_FILE with ${#COMPONENTS[@]} components: ${COMPONENTS[*]}"
