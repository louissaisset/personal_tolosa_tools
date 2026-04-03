#!/usr/bin/env python3

import argparse
from pathlib import Path

import sys, os
if os.uname()[1].startswith('belenos'):
    path_tolosa_path = "~/SAVE/DATA/Scripts/personal_tolosa_tools/"
else:
    path_tolosa_path = "~/DATA/Scripts/personal_tolosa_tools/"
os.environ['PATH'] += os.pathsep +  os.path.expanduser(f'{path_tolosa_path}/scripts/tools/')
sys.path.append(os.path.expanduser(path_tolosa_path))
import personal_tolosa_tools as ptt

def parse_args_and_get_file():
    """Parse command-line arguments and resolve the YAML file path."""
    parser = argparse.ArgumentParser(description="Update a key in a YAML file.")
    parser.add_argument("-f", "--file", type=Path, help="Path to the YAML file")
    parser.add_argument("-k", "--key", required=True, help="YAML key to update")
    parser.add_argument("-v", "--value", required=True, help="New value for the key")

    args = parser.parse_args()
    editor = ptt.YAMLEditor()

    # Resolve YAML file
    if args.file:
        yaml_file = args.file
        if not yaml_file.is_file():
            ptt.p_error(f"File not found: {yaml_file}")
            sys.exit(1)
        ptt.p_ok(f"Using provided YAML file: {yaml_file}")
    else:
        ptt.p_warning("No YAML file specified. Attempting to auto-detect one in the current directory...")
        yaml_file, yaml_status = editor.file_handler.find_unique_file("yaml")
        if yaml_status == 1:
            ptt.p_error("No YAML file found in the current directory.")
            sys.exit(1)
        elif yaml_status == 2:
            ptt.p_warning("Multiple YAML files found. Defaulting to the first one.")
        yaml_file = yaml_file.resolve()
        ptt.p_ok(f"Using detected YAML file: {yaml_file}")

    return args.key, args.value, yaml_file, editor


def main():
    key, value, yaml_file, editor = parse_args_and_get_file()

    # Load YAML
    yaml_data = editor.load_yaml_file(yaml_file)
    if yaml_data is None:
        return 1

    # Update the key
    if not editor.update_field(yaml_data, key, value):
        return 1

    # Save the YAML
    if not editor.save_yaml_file(yaml_data, yaml_file):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

