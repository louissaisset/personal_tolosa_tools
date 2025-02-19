#!/usr/bin/env python3

import os
import glob
import yaml
from pathlib import Path
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

def find_unique_file(extension: str) -> Tuple[Optional[Path], int]:
    """
    Find a file with specific extension in current directory.
    Returns (file_path, status_code) where status_code is:
    0: exactly one file found
    1: no files found
    2: multiple files found (first file is returned)
    """
    # Remove leading dot if present
    extension = extension.lstrip('.')
    
    # Find all files with the given extension
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

def update_yaml_field(yaml_data: dict, field: str, new_value: str) -> None:
    """Update a field in the YAML data structure."""
    if field not in yaml_data:
        print(f"    \033[31mERROR:\033[0m Field {field} not found in YAML file")
        return False
    
    yaml_data[field] = new_value
    print(f"       \033[32mOK:\033[0m Successfully updated {field}")
    return True

def main():
    print("\nBeginning script for yaml file paths update...")
    
    print("\nSearching for initial yaml, tif and shp files...")
    
    # Find YAML file
    yaml_file, yaml_status = find_unique_file('yaml')
    if yaml_status == 1:
        print("    \033[31mERROR:\033[0m Cannot proceed without a YAML file")
        return 1
    yaml_file = yaml_file.resolve()
    print(f"       \033[32mOK:\033[0m Found YAML file: {yaml_file}")
    
    # Find TIF file
    tif_file, tif_status = find_unique_file('tif')
    if tif_status == 1:
        print("    \033[31mERROR:\033[0m Cannot proceed without a TIF file")
        return 1
    tif_file = tif_file.resolve()
    print(f"       \033[32mOK:\033[0m Found TIF file: {tif_file}")
    
    # Find SHP file
    shp_file, shp_status = find_unique_file('shp')
    if shp_status == 1:
        print("    \033[31mERROR:\033[0m Cannot proceed without a SHP file")
        return 1
    shp_file = shp_file.resolve()
    print(f"       \033[32mOK:\033[0m Found SHP file: {shp_file}")
    
    print("\nDefining path for msh and regional.depth-ele.a files...")
    
    # Define actual paths and names
    current_path = Path.cwd()
    shp_name = shp_file.stem
    
    # Define MSH file
    msh_file = (current_path / f"{shp_name}.msh").resolve()
    print(f"       \033[32mOK:\033[0m Defined MSH file: {msh_file}")
    
    # Define projBathyFile
    proj_bathy_file = (current_path / "regional.depth-ele.a").resolve()
    print(f"       \033[32mOK:\033[0m Defined regional.depth-ele.a file: {proj_bathy_file}")
    
    # Process the YAML file
    print(f"\nProcessing {yaml_file}...")
    
    try:
        with open(yaml_file) as f:
            # yaml_data = yaml.safe_load(f)
            yaml_data = ordered_load(f, yaml.SafeLoader)
            
    except Exception as e:
        print(f"    \033[31mERROR:\033[0m Failed to read YAML file: {e}")
        return 1
    
    # Update fields if they exist in the YAML file
    fields_to_update = {
        'bathy_file_MSL': tif_file,
        'shp_file': shp_file,
        'msh_file': msh_file,
        'projBathyFile': proj_bathy_file
    }
    
    for field, new_path in fields_to_update.items():
        if field in yaml_data:
            print(f"\nUpdating {field} field...")
            current_path = Path(yaml_data[field]).resolve() if yaml_data[field] else None
            
            if not new_path.exists():
                print(f"  \033[33mWARNING:\033[0m Specified {field} path doesn't exist, still updating...")
            
            if current_path != new_path:
                update_yaml_field(yaml_data, field, str(new_path))
            else:
                print(f"       \033[32mOK:\033[0m {field} paths match, no update needed")
    
    # Write updated YAML back to file
    try:
        with open(yaml_file, 'w') as f:
            # yaml.dump(yaml_data, f, default_flow_style=False)
            ordered_dump(yaml_data, f, default_flow_style=False)
    except Exception as e:
        print(f"    \033[31mERROR:\033[0m Failed to write YAML file: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
