#!/usr/bin/env python3
"""
Script to change a key's value in a configuration file while preserving whitespace.
Usage: change_key_file.py file.txt key new_value
"""

import sys, os
if os.uname()[1].startswith('belenos'):
    path_tolosa_path = "~/SAVE/DATA/Scripts/personal_tolosa_tools/"
else:
    path_tolosa_path = "~/DATA/Scripts/personal_tolosa_tools/"
os.environ['PATH'] += os.pathsep +  os.path.expanduser(f'{path_tolosa_path}/scripts/tools/')
sys.path.append(os.path.expanduser(path_tolosa_path))
from personal_tolosa_tools import p_error, p_ok, p_warning


import re
import shutil

def main():
    # Check argument count
    if len(sys.argv) != 4:
        p_error("Wrong number of arguments")
        print(f"Usage: {sys.argv[0]} file.txt key new_value")
        sys.exit(1)
    
    # Assign arguments to variables
    file_path = sys.argv[1]
    key = sys.argv[2]
    new_value = sys.argv[3]
    
    # Check if file exists
    if not os.path.isfile(file_path):
        p_error(f"File '{file_path}' does not exist")
        sys.exit(1)
    
    p_ok(f"Modifying file: '{file_path}'")
    
    # Check if key exists in file
    key_found = False
    pattern = re.compile(r'\s*' + re.escape(key) + r'\s*=')
    
    with open(file_path, 'r') as f:
        for line in f:
            if pattern.match(line):
                key_found = True
                break
    
    if not key_found:
        p_error(f"Key '{key}' not found in '{file_path}'")
        sys.exit(1)
    
    p_ok(f"Found key: {key}")
    p_ok(f"Modifying to the new value: {new_value}")
    
    # Display the line from backup
    with open(file_path, 'r') as f:
        for line in f:
            if re.search(re.escape(key), line):
                p_ok("Original line:")
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
                p_ok("New line:")
                print(line.rstrip())
                break
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
