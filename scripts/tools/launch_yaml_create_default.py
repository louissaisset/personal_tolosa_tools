#!/usr/bin/env python3

import sys, os
sys.path.append(os.path.expanduser("~/DATA/Scripts/personal_tolosa_tools/"))
import personal_tolosa_tools as ptt

from pathlib import Path

def main():
    print("\nBeginning script for the creation of a default yaml file...")
    
    # Get current working directory and create file path
    current_path = Path.cwd()
    default_yaml_path = current_path / "default_input.yaml"
    default_yaml_path = default_yaml_path.resolve()
    
    # Create the file
    default_yaml_path.touch()
    ptt.p_ok(f"Created the default yaml file: {default_yaml_path}")
    
    # Write content to the file
    editor = ptt.YAMLEditor()
    default_yaml_data = editor.load_default_yaml()
    editor.save_yaml_file(default_yaml_data, default_yaml_path)
    # create_default_yaml(default_yaml_path)
    ptt.p_ok(f"Added the contents of the default yaml file to: {default_yaml_path}")
    
    return 0

if __name__ == "__main__":
    exit(main())
