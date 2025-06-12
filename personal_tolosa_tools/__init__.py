# my_library/__init__.py

# Importer les modules principaux
from .common import p_colorize, p_error, p_ok, p_warning
from .common import p_filter_args, p_strip_None
from .common import p_convert_julian_day_to_gregorian_date
from .common import p_convert_gregorian_date_to_julian_day

from .initialize_logs import set_logging

from .plotters import Plotter

from .readers import FileReader, WhichReader, Reader
from .readers import BinReader, DataBinReader, ConcatDataBinReader
from .readers import GmshElementBinReader, MeshBinReader
from .readers import LonLatDegBinReader, LonLatRadBinReader
from .readers import TxtReader, InfoTxtReader, DataMinMaxTxtReader
from .readers import VTKReader, DataVTKReader
from .readers import TecplotReader, DataTecplotReader
# OLD NAMES
# from .readers import VTKDataReader
# from .readers import LonLatDeg, LonLatRad, BinReader, GmshElement, Data, Mesh
# from .readers import TxtReader, DataMinMax, Info

from .processors import DataProcessor, VTKDataProcessor, BinDataProcessor

# Old version of readers, Processors and plotters
# from .vtk_plotter_lib import VTKDataReader, VTKDataProcessor, VTKPlotter

from .yaml_meshtool import YAMLHandler, FileHandler, YAMLEditor

from .wrappers import files_for_timesteps, files_for_timestep
from .wrappers import process_bin, process_vtk
from .wrappers import plot_data_plotter, plot_tri_data_comparison
from .wrappers import interp_data_on_grid
# # Importer les sous-modules
# from .Dossier1.module import Class3, function3

# Définir la version de la bibliothèque
__version__ = '0.0.1'

# Définir ce qui est exposé publiquement
__all__ = [
    'p_colorize', 'p_error', 'p_warning', 'p_ok',
    'p_filter_args', 'p_strip_None',
    'p_convert_julian_day_to_gregorian_date', 
    'p_convert_gregorian_date_to_julian_day',
    'set_logging',
    'Plotter',
    'FileReader', 'WhichReader', 'Reader',
    'BinReader', 'DataBinReader', 'ConcatDataBinReader',
    'GmshElementBinReader', 'MeshBinReader',
    'LonLatDegBinReader', 'LonLatRadBinReader',
    'TxtReader', 'InfoTxtReader', 'DataMinMaxTxtReader',
    'VTKReader', 'DataVTKReader',
    'TecplotReader', 'DataTecplotReader',
    # 'FileReader', 'WhichReader', 'VTKDataReader',
    # 'LonLatDeg', 'LonLatRad', 'BinReader', 'GmshElement', 'Data', 'Mesh',
    # 'TxtReader', 'DataMinMax', 'Info',
    'DataProcessor', 'VTKDataProcessor', 'BinDataProcessor',
    'YAMLHandler', 'FileHandler', 'YAMLEditor',
    'files_for_timesteps', 'files_for_timestep',
    'process_bin', 'process_vtk',
    'plot_data_plotter', 'plot_tri_data_comparison',
    'interp_data_on_grid'
]
