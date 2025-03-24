#!/usr/bin/env python3


import sys, os
os.environ['PATH'] += os.pathsep + '~/DATA/Scripts/personal_tolosa_tools/scripts/tools/'


import subprocess


def main():
    
    print("\nBeginning script for launching meshtool 4 times using a single yaml file")
    
    # List of tools to run in sequence
    tools = ['create_mesh', 'bathy_smooth', 'regional_grid', 'diagnostic']
    
    # Run meshtool for each tool
    for tool in tools:
        pass_args = sys.argv[1:]
        finalargs = ''
        if pass_args:
            for a in pass_args:
                finalargs = finalargs + str(a)
        command = ' '.join(['launch_meshtool_yaml_tool.py', finalargs, f"--tool {tool}"])
        
        try:
            subprocess.run(command, shell=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"    \033[31mERROR:\033[0m Failed to run meshtool: {e}")
        except FileNotFoundError:
            print("    \033[31mERROR:\033[0m launch_meshtool_yaml.sh command not found")
    return 0

if __name__ == "__main__":
    exit(main())

