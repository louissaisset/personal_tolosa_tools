#!/usr/bin/env python3
"""
Script to change a key's value in a configuration file while preserving whitespace.
Usage: change_key_file.py file.txt key new_value
"""

import sys
import os
import re
import shutil

def colorize(text, color_code):
    """Add color to terminal output"""
    return f"\033[{color_code}m{text}\033[0m"

def error(message):
    """Print error message in red"""
    print(f"    {colorize('ERROR:', '31')} {message}")

def ok(message):
    """Print ok message in green"""
    print(f"       {colorize('OK:', '32')} {message}")

def warning(message):
    """Print warning message in yellow"""
    print(f"  {colorize('WARNING:', '33')} {message}")

def main():
    # Check argument count
    if len(sys.argv) != 4:
        error("Wrong number of arguments")
        print(f"Usage: {sys.argv[0]} file.txt key new_value")
        sys.exit(1)
    
    # Assign arguments to variables
    file_path = sys.argv[1]
    key = sys.argv[2]
    new_value = sys.argv[3]
    
    # Check if file exists
    if not os.path.isfile(file_path):
        error(f"File '{file_path}' does not exist")
        sys.exit(1)
    
    ok(f"Modifying file: '{file_path}'")
    
    # Check if key exists in file
    key_found = False
    pattern = re.compile(r'\s*' + re.escape(key) + r'\s*=')
    
    with open(file_path, 'r') as f:
        for line in f:
            if pattern.match(line):
                key_found = True
                break
    
    if not key_found:
        error(f"Key '{key}' not found in '{file_path}'")
        sys.exit(1)
    
    ok(f"Found key: {key}")
    ok(f"Modifying to the new value: {new_value}")
    
    # Display the line from backup
    with open(file_path, 'r') as f:
        for line in f:
            if re.search(re.escape(key), line):
                ok("Original line:")
                print(line.rstrip())
                break
    
    def replace_value(match):
        # This gets the whitespace and key part from group 1
        # and the trailing part from group 2
        return match.group(1) + new_value + match.group(2)

    # Replace the value while preserving whitespace
    pattern = re.compile(r'(\s*' + re.escape(key) + r'\s*=\s*)[^\s]*(.*)')
    
    # Read the entire file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Perform the replacement
    modified_content = re.sub(pattern, replace_value, content)
    
    # Write back to the file
    with open(file_path, 'w') as f:
        f.write(modified_content)
   
    # Display the modified line
    with open(file_path, 'r') as f:
        for line in f:
            if re.search(re.escape(key), line):
                ok("New line:")
                print(line.rstrip())
                break
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
