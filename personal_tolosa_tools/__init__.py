# my_library/__init__.py

# Importer les modules principaux
from .module1 import Class1, function1
from .module2 import Class2, function2

# Importer les sous-modules
from .Dossier1.module import Class3, function3

# Définir la version de la bibliothèque
__version__ = '0.1.0'

# Définir ce qui est exposé publiquement
__all__ = [
    'Class1', 'function1',
    'Class2', 'function2',
    'Class3', 'function3'
]
