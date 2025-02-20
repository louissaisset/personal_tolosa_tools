#!/usr/bin/env python3

import sys
sys.path.append("/local/home/lsaisset/DATA/Scripts/personal_tolosa_tools/")
import personal_tolosa_tools as ptt

import subprocess
from pathlib import Path


def update_tool_fields(yaml_data: dict, new_tool: str) -> bool:

    current_tool = yaml_data.get('tool', '')

    current_smoothBathy = yaml_data.get('smoothBathy', '')
    if current_smoothBathy:
        current_smoothBathy_tool = current_smoothBathy.get('tool', '')
    else : 
        current_smoothBathy_tool = ''
    
    need_update = 0
    if current_tool != new_tool:
        need_update += 1
        yaml_data['tool'] = new_tool
        print(f"       \033[32mOK:\033[0m Successfully updated tool to {new_tool}")
    else:
        need_update += 0
        print("       \033[32mOK:\033[0m tool entries match, no update needed")
   
    if current_smoothBathy and current_smoothBathy_tool != new_tool:
        need_update += 1
        yaml_data['smoothBathy']['tool'] = new_tool
        print(f"       \033[32mOK:\033[0m Successfully updated smoothBathy: tool to {new_tool}")
    else:
        need_update += 0
        print("       \033[32mOK:\033[0m smoothBathy: tool entries match, no update needed")
    
    return(need_update > 0)

def main():
    print("\nBeginning script for launching meshtool 4 times using a single yaml file")
    
    
    editor = ptt.YAMLEditor()
    
    # Get YAML file path from argument or find in current directory
    if len(sys.argv) > 1:
        yaml_file = Path(sys.argv[1])
        if yaml_file.is_file():
            print(f"       \033[32mOK:\033[0m Found YAML file: {yaml_file}")
        else:
            print("    \033[31mERROR:\033[0m Cannot proceed without a valid YAML file")
            return 1
    else:
        print("  \033[33mWARNING:\033[0m No yaml file as argument")
        yaml_file, status = editor.file_handler.find_unique_file('yaml')
        if status == 1:
            print("    \033[31mERROR:\033[0m Cannot proceed without a YAML file")
            return 1
        yaml_file = yaml_file.resolve()
        print(f"       \033[32mOK:\033[0m Found YAML file: {yaml_file}")
    
    
    yaml_data = editor.load_yaml_file(yaml_file)
    
    # List of tools to run in sequence
    tools = ['create_mesh', 'bathy_smooth', 'regional_grid', 'diagnostic']
    
    # Run meshtool for each tool
    for tool in tools:
        
        print(f"\nUpdating the YAML tool fields...")
        update_tool_fields(yaml_data, tool)
        editor.save_yaml_file(yaml_data, yaml_file)
            
        print(f"\nLaunching meshtool: launch_meshtool_yaml.sh {yaml_file}")
        try:
            subprocess.run(['launch_meshtool_yaml.sh', str(yaml_file)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"    \033[31mERROR:\033[0m Failed to run meshtool: {e}")
        except FileNotFoundError:
            print("    \033[31mERROR:\033[0m launch_meshtool_yaml.sh command not found")
    return 0

if __name__ == "__main__":
    exit(main())

