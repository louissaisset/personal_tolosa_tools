#!/usr/bin/env python3

import os
import sys
import subprocess
from pathlib import Path
import yaml
from typing import Optional, Tuple
from collections import OrderedDict

def ordered_load(stream, Loader=yaml.SafeLoader, object_pairs_hook=OrderedDict):
    class OrderedLoader(Loader):
        pass
    def construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return object_pairs_hook(loader.construct_pairs(node))
    OrderedLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping)
    return yaml.load(stream, OrderedLoader)

def ordered_dump(data, stream=None, Dumper=yaml.SafeDumper, **kwds):
    class OrderedDumper(Dumper):
        pass
    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())
    OrderedDumper.add_representer(OrderedDict, _dict_representer)
    
    # Override representers for individual None values (so that they are not serialized)
    def _represent_none(dumper, value):
        return dumper.represent_scalar('tag:yaml.org,2002:null', '')

    # Adding the custom representer for None values
    OrderedDumper.add_representer(type(None), _represent_none)
    
    return yaml.dump(data, stream, OrderedDumper, **kwds)

# def ordered_load(stream, Loader=yaml.SafeLoader, object_pairs_hook=OrderedDict):
#     class OrderedLoader(Loader):
#         pass
#     
#     def construct_mapping(loader, node):
#         loader.flatten_mapping(node)
#         # Convert any None values to empty in the pairs
#         pairs = [(key, value if value is not None else None) 
#                 for key, value in loader.construct_pairs(node)]
#         return object_pairs_hook(pairs)
#     
#     # Handle scalar nodes (for single values)
#     def construct_scalar(loader, node):
#         value = loader.construct_scalar(node)
#         return value if value is not None else None
#     
#     OrderedLoader.add_constructor(
#         yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
#         construct_mapping)
#     
#     # Add constructor for scalar nodes
#     OrderedLoader.add_constructor(
#         yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG,
#         construct_scalar)
#     
#     return yaml.load(stream, OrderedLoader)
# 
# def ordered_dump(data, stream=None, Dumper=yaml.SafeDumper, **kwds):
#     class OrderedDumper(Dumper):
#         pass
#     
#     def dict_representer(dumper, data):
#         # Keep key but with no value for None values
#         items = [(key, value if value is not None else None) 
#                 for key, value in data.items()]
#         return dumper.represent_mapping(
#             yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
#             items)
#     
#     # Add representer for None values to omit them
#     def none_representer(dumper, _):
#         return dumper.represent_scalar(
#             yaml.resolver.BaseResolver.DEFAULT_SCALAR_TAG, '')
#     
#     OrderedDumper.add_representer(OrderedDict, dict_representer)
#     OrderedDumper.add_representer(type(None), none_representer)
#     
#     return yaml.dump(data, stream, OrderedDumper, **kwds)

# def ordered_load(stream, Loader=yaml.SafeLoader, object_pairs_hook=OrderedDict):
#     class OrderedLoader(Loader):
#         pass
#     def construct_mapping(loader, node):
#         loader.flatten_mapping(node)
#         return object_pairs_hook(loader.construct_pairs(node))
#     OrderedLoader.add_constructor(
#         yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
#         construct_mapping)
#     return yaml.load(stream, OrderedLoader)
# 
# def ordered_dump(data, stream=None, Dumper=yaml.SafeDumper, **kwds):
#     class OrderedDumper(Dumper):
#         pass
#     def _dict_representer(dumper, data):
#         return dumper.represent_mapping(
#             yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
#             data.items())
#     OrderedDumper.add_representer(OrderedDict, _dict_representer)
#     return yaml.dump(data, stream, OrderedDumper, **kwds)

def find_unique_file(extension: str) -> Tuple[Optional[Path], int]:
    """
    Find a file with specific extension in current directory.
    Returns (file_path, status_code) where status_code is:
    0: exactly one file found
    1: no files found
    2: multiple files found (first file is returned)
    """
    extension = extension.lstrip('.')
    files = list(Path('.').glob(f'*.{extension}'))
    
    if not files:
        print(f"    \033[31mERROR:\033[0m No files found with extension .{extension}")
        return None, 1
        
    if len(files) > 1:
        print(f"  \033[33mWARNING:\033[0m Multiple files found with extension .{extension}:")
        for file in files:
            print(file)
        print(f"Using: {files[0]}")
        return files[0], 2
        
    return files[0], 0

def update_yaml_tool(yaml_file: Path, new_tool: str) -> bool:
    """Update the tool field in the YAML file."""
    try:
        with open(yaml_file) as f:
            # yaml_data = yaml.safe_load(f)
            yaml_data = ordered_load(f, yaml.SafeLoader)
    except Exception as e:
        print(f"    \033[31mERROR:\033[0m Failed to read YAML file: {e}")
        return False

    if 'tool' not in yaml_data:
        print(f"    \033[31mERROR:\033[0m Cannot proceed without a 'tool:' entry in the yaml file")
        return False

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
        print(f"       \033[32mOK:\033[0m tool entries match, no update needed")
   
    if current_smoothBathy and current_smoothBathy_tool != new_tool:
        need_update += 1
        yaml_data['smoothBathy']['tool'] = new_tool
        print(f"       \033[32mOK:\033[0m Successfully updated smoothBathy: tool to {new_tool}")
    else:
        need_update += 0
        print(f"       \033[32mOK:\033[0m smoothBathy: tool entries match, no update needed")
    
    if need_update:
        try:
            with open(yaml_file, 'w') as f:
                # yaml.dump(yaml_data, f, default_flow_style=False)
                ordered_dump(yaml_data, f, default_flow_style=False)
                print(f"       \033[32mOK:\033[0m Successfully updated YAML file tool entries in {yaml_file}")
        except Exception as e:
            print(f"    \033[31mERROR:\033[0m Failed to write YAML file: {e}")
            return False
    return True

def run_meshtool(yaml_file: Path, tool: str) -> bool:
    """Run meshtool with specified tool and YAML file."""
    print(f"\nUsing tool: {tool}")
    
    if not update_yaml_tool(yaml_file, tool):
        return False
    
    print(f"\nLaunching meshtool: launch_meshtool_yaml.sh {yaml_file}")
    try:
        subprocess.run(['launch_meshtool_yaml.sh', str(yaml_file)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"    \033[31mERROR:\033[0m Failed to run meshtool: {e}")
        return False
    except FileNotFoundError:
        print(f"    \033[31mERROR:\033[0m launch_meshtool_yaml command not found")
        return False
    
    return True

def main():
    print("\nBeginning script for launching meshtool 4 times with yaml file")
    
    # Get YAML file path from argument or find in current directory
    if len(sys.argv) > 1:
        yaml_file = Path(sys.argv[1])
        if yaml_file.is_file():
            print(f"       \033[32mOK:\033[0m Found YAML file: {yaml_file}")
        else:
            print(f"    \033[31mERROR:\033[0m Cannot proceed without a YAML file")
            return 1
    else:
        print("  \033[33mWARNING:\033[0m No yaml file as argument")
        yaml_file, status = find_unique_file('yaml')
        if status == 1:
            print(f"    \033[31mERROR:\033[0m Cannot proceed without a YAML file")
            return 1
        yaml_file = yaml_file.resolve()
        print(f"       \033[32mOK:\033[0m Found YAML file: {yaml_file}")
    
    # List of tools to run in sequence
    tools = ['create_mesh', 'bathy_smooth', 'regional_grid', 'diagnostic']
    
    # Run meshtool for each tool
    for tool in tools:
        if not run_meshtool(yaml_file, tool):
            return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
