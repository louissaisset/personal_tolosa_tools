#!/usr/bin/env python3


import sys, os
os.environ['PATH'] += os.pathsep +  os.path.expanduser('~/DATA/Scripts/personal_tolosa_tools/scripts/tools/')
sys.path.append(os.path.expanduser("~/DATA/Scripts/personal_tolosa_tools/"))
from personal_tolosa_tools import p_error

import subprocess


def main():
    print(os.environ['PATH'])
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
            p_error(f"Failed to run meshtool: {e}")
        except FileNotFoundError:
            p_error("Command not found : launch_meshtool_yaml.sh")
    return 0

if __name__ == "__main__":
    exit(main())

