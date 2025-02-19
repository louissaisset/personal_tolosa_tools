#!/usr/bin/env python3

from pathlib import Path

DEFAULT_YAML_CONTENT = """
tool: 
bathy_file_MSL: 
shp_file: 
msh_file: 
projBathyFile: 
coordinatesystem: +proj=sterea +lat_0=48.315551 +lon_0=-4.431506 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs
regional:
  input_srs: +proj=sterea +lat_0=48.315551 +lon_0=-4.431506 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_def
  output_srs: +proj=latlong +ellps=WGS84 +unit=degrees
algo: 6 
constraints: resolution, bathy_grad, min_dt, dispersion
min_size: 10.
physicalsBC:
  -
    tags: ocean, est, ouest
    sampling: 0.01
    threshold:
      d0: 1000
      l0: 300
      d1: 4000
      l1: 100
      d2: 10000
      l2: 50
  -
    tags: cote, iles
    sampling: 0.01
    threshold:
      d0: 200
      l0: 10
      d1: 1000
      l1: 30
      d2: 2000
      l2: 50
  -
    tags: aulne, camfrout, elorn, mignonne, penfeld
    sampling: 0.01
    threshold:
      d0: 300
      l0: 10
      d1: 1000
      l1: 20
      d2: 2000
      l2: 50
wave_length:
  dispersion: airy #, sw, lct
  file:
  period_min: 360   #seconds
  nb_pts: 10
coeff_grad:
  active: True
  coeff_max: 5.
  slope: 1000.
min_dt:
  cfl: 1.
  umax: 3.
  dt: 1.
smoothBathy:
  tool: create_mesh 
  size_filtering: 500. #m
  smoothBathyFile: #/your/path/to/your/smoothed/bathymetry.nc # OPTIONNAL
diagnostic : time_step, size
"""

def create_default_yaml(file_path: Path) -> None:
    """Create a default YAML file with predefined content."""
    with open(file_path, 'w') as f:
        f.write(DEFAULT_YAML_CONTENT)

def main():
    print("\nBeginning script for the creation of a default yaml file...")
    
    # Get current working directory and create file path
    current_path = Path.cwd()
    default_yaml_path = current_path / "default_input.yaml"
    default_yaml_path = default_yaml_path.resolve()
    
    # Create the file
    default_yaml_path.touch()
    print(f"       \033[32mOK:\033[0m Created the default yaml file: {default_yaml_path}")
    
    # Write content to the file
    create_default_yaml(default_yaml_path)
    print(f"       \033[32mOK:\033[0m Added the contents of the default yaml file to: {default_yaml_path}")
    
    return 0

if __name__ == "__main__":
    exit(main())
