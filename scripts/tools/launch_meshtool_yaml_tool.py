#!/usr/bin/env python3

import sys, os
sys.path.append(os.path.expanduser("~/DATA/Scripts/personal_tolosa_tools/"))
import personal_tolosa_tools as ptt

os.environ['PATH'] += os.pathsep + os.path.expanduser('~/DATA/Scripts/personal_tolosa_tools/scripts/tools/')

import subprocess
from pathlib import Path
import argparse

def main():
    print("\nBeginning script for launching meshtool using specific yaml file and/or tool argument...")
    
    editor = ptt.YAMLEditor()

    print("\nParsing arg and kargs for yaml file and/or tool arguments")

    # Read args and kwargs
    parser = argparse.ArgumentParser(description='Process file and tool parameters')
    parser.add_argument('args', nargs='*', help='Positional arguments for file and tool')
    parser.add_argument('--yaml_file', dest='yaml_file_kwarg', default=None, help='File parameter as kwarg')
    parser.add_argument('--tool', dest='tool_kwarg', default=None, help='Tool parameter as kwarg')
    
    args = parser.parse_args()
    
    # Initialize with default values
    yaml_file = ''
    tool = ''
    
    # Process positional args if provided
    if len(args.args) >= 1:
        yaml_file = args.args[0]
    if len(args.args) >= 2:
        tool = args.args[1]
    
    # Override with kwargs if provided
    if args.yaml_file_kwarg is not None:
        yaml_file = args.yaml_file_kwarg
    if args.tool_kwarg is not None:
        tool = args.tool_kwarg
    
    ptt.p_ok(f"Asking for file: {yaml_file}")
    ptt.p_ok(f"Asking for tool: {tool}")
    
    print("\nChecking the asked files and tools...")

    # Get YAML file path from argument or find in current directory
    if yaml_file:
        yaml_file = Path(sys.argv[1])
        if yaml_file.is_file():
            ptt.p_ok(f"Found YAML file: {yaml_file}")
        else:
            ptt.p_error("Cannot proceed without a valid YAML file")
            return 1
    else:
        ptt.p_warning("No yaml file as argument")
        yaml_file, status = editor.file_handler.find_unique_file('yaml')
        if status == 1:
            ptt.p_error("Cannot proceed without a YAML file")
            return 1
        yaml_file = yaml_file.resolve()
        ptt.p_ok(f"Found YAML file: {yaml_file}")
    
    
    try:
        yaml_data = editor.load_yaml_file(yaml_file)
        ptt.p_ok(f"Loaded YAML file: {yaml_file}")
    except:
        ptt.p_error(f"Could not load {yaml_file}")


    try:
        current_tool = yaml_data.get('tool', '') 
        ptt.p_ok(f"Current tool in yaml file: {current_tool}")
    except:
        ptt.p_error("Could not get 'tool' from yaml file")
        return 1

    if not tool:
        tool = current_tool
        ptt.p_ok(f"Kept tool as: {tool}")
    elif tool == current_tool:
        ptt.p_ok(f"Kept tool as: {tool}")
    elif tool in ['create_mesh', 'bathy_smooth', 'regional_grid', 'diagnostic'] and tool!=current_tool:
        ptt.p_ok(f"Asking for tool: {tool}")
        yaml_data['tool'] = tool
        editor.save_yaml_file(yaml_data, yaml_file)
    else:
        ptt.p_error("Asked tool is neither of 'create_mesh', 'bathy_smooth', 'regional_grid' or 'diagnostic'")
        return 1

    # Run meshtool for with the new tool
    command = f'launch_meshtool_yaml.sh {str(yaml_file)}'
    try:
        subprocess.run(command, shell=True, check=True)
    except subprocess.CalledProcessError as e:
        ptt.p_error(f"Failed to run meshtool: {e}")
    except FileNotFoundError:
        ptt.p_error("launch_meshtool_yaml.sh command not found")
    return 0

if __name__ == "__main__":
    exit(main())
