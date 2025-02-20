# my_library/__init__.py

# Importer les modules principaux
from .vtk_plotter_lib import VTKDataReader, VTKDataProcessor, VTKPlotter
from .yaml_meshtool import YAMLHandler, FileHandler, YAMLEditor

# # Importer les sous-modules
# from .Dossier1.module import Class3, function3

# Définir la version de la bibliothèque
__version__ = '0.0.1'

# Définir ce qui est exposé publiquement
__all__ = [
    'VTKDataReader', 'VTKDataProcessor', 'VTKPlotter',
    'YAMLHandler', 'FileHandler', 'YAMLEditor'
]
