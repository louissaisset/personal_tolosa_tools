from pathlib import Path
from typing import Tuple, Optional
from collections import OrderedDict
import yaml

class YAMLHandler:
    class OrderedLoader(yaml.SafeLoader):
        pass
        
    class OrderedDumper(yaml.SafeDumper):
        pass
        
    def __init__(self):
        # Configure the custom loader
        self.OrderedLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            self._construct_mapping
        )
        
        # Configure the custom dumper
        self.OrderedDumper.add_representer(
            OrderedDict,
            self._dict_representer
        )
        self.OrderedDumper.add_representer(
            type(None),
            self._represent_none
        )
        
    @staticmethod
    def _construct_mapping(loader, node):
        loader.flatten_mapping(node)
        return OrderedDict(loader.construct_pairs(node))
    
    @staticmethod
    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items()
        )
    
    @staticmethod
    def _represent_none(dumper, value):
        return dumper.represent_scalar('tag:yaml.org,2002:null', '')
    
    
    
    def load(self, stream) -> OrderedDict:
        """Load YAML content while preserving order"""
        return yaml.load(stream, self.OrderedLoader)
    
    def dump(self, data, stream=None, **kwargs) -> str:
        """Dump data to YAML format while preserving order"""
        return yaml.dump(data, stream, self.OrderedDumper, **kwargs)


class FileHandler:
    @staticmethod
    def find_unique_file(extension: str) -> Tuple[Optional[Path], int]:
        """
        Find a file with specific extension in current directory.
        
        Returns:
            Tuple[Optional[Path], int]: (file_path, status_code) where status_code is:
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


class YAMLEditor:
    def __init__(self):
        self.yaml_handler = YAMLHandler()
        self.file_handler = FileHandler()
        
    def load_yaml_file(self, file_path: Path) -> Optional[OrderedDict]:
        """Load and parse a YAML file"""
        try:
            with open(file_path, 'r') as f:
                return self.yaml_handler.load(f)
            print(f"       \033[32mOK:\033[0m Loaded YAML data from {file_path}")
        except Exception as e:
            print(f"    \033[31mERROR:\033[0m Failed to load YAML file: {e}")
            return None
            
    def save_yaml_file(self, data: OrderedDict, file_path: Path) -> bool:
        """Save data to a YAML file"""
        try:
            with open(file_path, 'w') as f:
                self.yaml_handler.dump(data, f, default_flow_style=False)
            print(f"       \033[32mOK:\033[0m Saved YAML file {file_path}")
            return True
        except Exception as e:
            print(f"    \033[31mERROR:\033[0m Failed to save YAML file: {e}")
            return False
            
    def update_field(self, yaml_data: dict, field: str, new_value: str) -> bool:
        """Update a field in the YAML data structure"""
        if field not in yaml_data:
            print(f"    \033[31mERROR:\033[0m Field not found in YAML file: {field}")
            return False
            
        yaml_data[field] = new_value
        print(f"       \033[32mOK\033[0m Successfully updated {field}")
        return True
    
    def update_all_tool_field(self, yaml_data: dict, new_tool: str) -> bool:
        """Update all instances of 'tool' in the YAML data structure"""
        

    def load_default_yaml(self):

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
        
        return self.yaml_handler.load(DEFAULT_YAML_CONTENT)