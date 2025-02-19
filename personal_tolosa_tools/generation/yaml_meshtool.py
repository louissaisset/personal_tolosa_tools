from pathlib import Path
from typing import Tuple, Optional, OrderedDict
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
            print(f" \033[31mERROR:\033[0m No files found with extension .{extension}")
            return None, 1
            
        if len(files) > 1:
            print(f" \033[33mWARNING:\033[0m Multiple files found with extension .{extension}:")
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
        except Exception as e:
            print(f" \033[31mERROR:\033[0m Failed to load YAML file: {e}")
            return None
            
    def save_yaml_file(self, data: OrderedDict, file_path: Path) -> bool:
        """Save data to a YAML file"""
        try:
            with open(file_path, 'w') as f:
                self.yaml_handler.dump(data, f)
            return True
        except Exception as e:
            print(f" \033[31mERROR:\033[0m Failed to save YAML file: {e}")
            return False
            
    def update_field(self, yaml_data: dict, field: str, new_value: str) -> bool:
        """Update a field in the YAML data structure"""
        if field not in yaml_data:
            print(f" \033[31mERROR:\033[0m Field {field} not found in YAML file")
            return False
            
        yaml_data[field] = new_value
        print(f" \033[32mOK:\033[0m Successfully updated {field}")
        return True
