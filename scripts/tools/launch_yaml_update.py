#!/usr/bin/env python3


import sys
sys.path.append("/local/home/lsaisset/DATA/Scripts/personal_tolosa_tools/")
import personal_tolosa_tools as ptt

from pathlib import Path

def main():
    print("\nBeginning script for yaml file paths update...")
    
    editor = ptt.YAMLEditor()
    
    print("\nSearching for initial yaml, tif and shp files...")
    
    # Get YAML file path from argument or find in current directory
    if len(sys.argv) > 1:
        yaml_file = Path(sys.argv[1])
        if not yaml_file.is_file():
            print("    \033[31mERROR:\033[0m Cannot proceed without a valid YAML file")
            return 1
        print(f"       \033[32mOK:\033[0m Found YAML file: {yaml_file}")
    else:
        yaml_file, yaml_status = editor.file_handler.find_unique_file('yaml')
        if yaml_status == 1:
            print("    \033[31mERROR:\033[0m Cannot proceed without a YAML file")
            return 1
        yaml_file = yaml_file.resolve()
        print(f"       \033[32mOK:\033[0m Found YAML file: {yaml_file}")
    
    # Find TIF file
    tif_file, tif_status = editor.file_handler.find_unique_file('tif')
    if tif_status == 1:
        print("    \033[31mERROR:\033[0m Cannot proceed without a TIF file")
        return 1
    tif_file = tif_file.resolve()
    print(f"       \033[32mOK:\033[0m Found TIF file: {tif_file}")
    
    # Find SHP file
    shp_file, shp_status = editor.file_handler.find_unique_file('shp')
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
    
    
    yaml_data = editor.load_yaml_file(yaml_file)
    if not yaml_data:
        print("    \033[31mERROR:\033[0m Cannot proceed without YAML data")
        return 1
    
    # Update fields if they exist in the YAML file
    fields_to_update = {
        'bathy_file_MSL': tif_file,
        'shp_file': shp_file,
        'msh_file': msh_file,
        'projBathyFile': proj_bathy_file
    }
    
    update_status = 0
    for field, new_path in fields_to_update.items():
        if field in yaml_data:
            print(f"\nUpdating {field} field...")
            current_path = Path(yaml_data[field]).resolve() if yaml_data[field] else None
            
            if not new_path.exists():
                print(f"  \033[33mWARNING:\033[0m Specified {field} path doesn't exist, still updating...")
            
            if current_path != new_path:
                update_status += editor.update_field(yaml_data, field, str(new_path))
            else:
                print(f"       \033[32mOK:\033[0m {field} paths match, no update needed")
    
    
    print(f"\nSaving the updated YAML file...")
    if update_status:
        save_status = editor.save_yaml_file(yaml_data, yaml_file)
        if not save_status:
            return 1
    else :
        print(f"       \033[32mOK:\033[0m No need to change {yaml_file}")
    
    return 0

if __name__ == "__main__":
    exit(main())
