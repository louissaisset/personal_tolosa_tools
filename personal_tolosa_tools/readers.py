"""Modules"""

from .common import p_filter_args, p_strip_None
import os
import re
import logging
from abc import ABC, abstractmethod
from datetime import datetime as dt
import numpy as np
import pandas as pd

# Ajouts Louis
import vtk
from vtk.util.numpy_support import vtk_to_numpy
from meshio import read as readmesh
from meshio import Mesh

# strategy factory pattern ?
class Reader(ABC):
    # PATTERN = re.compile(r"^(?P<name>[a-z_]*)(?:_(?P<num>\d{6}))?\.(?P<ext>bin|txt|vtk|plt|msh)$")
    PATTERN = re.compile(r"^.*\.(?P<ext>bin|txt|vtk|plt|msh)$")
                         

    @abstractmethod
    def read(self, **kwargs):
        pass

    @staticmethod        
    def _search(func):
        def wrapper(cls, path :str) -> str:
            for file in os.listdir(path):
                if func(cls, file):
                    yield file
        return classmethod(wrapper)
    
    @classmethod
    def test_filename(cls, filename: str) -> bool:
        match = cls.PATTERN.match(filename)
        return bool(match)
    
    @_search
    def search(cls, filename :str) -> bool:
        return cls.test_filename(filename)
    
    

# default class reader
class BinReader(Reader):
    """_summary_

    Args:
        Reader (_type_): _description_

    Returns:
        _type_: _description_
    """
    PATTERN = re.compile(r"^([a-z_]*)(?:_(\d{6}))?\.bin$")

    def __init__(self, path :str, filename :str):
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename

    def _key(self, file, offset=0):
        """Retrieve the key to define the content of the file at the beginning of each binary file or records

        Args:
            file (_type_): buffered reader
            offset (int, optional): reader offset. Defaults to 0.
        """
        
        _key_options = {0 : {'date_written': False, 'minmax_written': False},
                        1 : {'date_written': False, 'minmax_written': True}, # if min / max values of each field written at the beginning 
                                                                             # of each time step
                        2 : {'date_written': True, 'minmax_written': False}, # if date written at the beginning of each time step
                        3 : {'date_written': True, 'minmax_written': True}}
        try:
            self.key = np.fromfile(file, dtype='i4', count=1, offset=offset)[0]
            
            if self.key in _key_options:
                self.date_written = _key_options[self.key]['date_written']
                self.minmax_written = _key_options[self.key]['minmax_written']

            else:
                logging.error("key value %s not valid", self.key)

        except Exception as e:
            logging.error('failed to read key due to %s', str(e))
            raise e

    def _date(self, file, offset=0):
        """Read date at the beginning of each binary file or records

        Args:
            file (_type_): buffered reader
            offset (int, optional): reader offset. Defaults to 0.
        """        
        
        self.i  = np.fromfile(file, dtype='f4', count=1, offset=offset)[0]

        gregorian_date = np.fromfile(file, dtype='i4', count=5, offset=offset)
        gregorian_date_dt = dt.strptime(''.join(list(map(str, gregorian_date))), '%Y%m%d%H%M')
        self._gregorian_date = gregorian_date_dt.strftime('%Y-%m-%d_%H:%M')
        
        self._julian_cnes_date = str(np.fromfile(file, dtype='f4', count=1, offset=offset)[0])
    
    @property
    def date(self):
        try:
            return (self._gregorian_date, self._julian_cnes_date)
        except AttributeError:
            raise AttributeError

    def _minmax(self, file, variables, offset =0):
        """Read minimum and maximum values of each field at the beginning of each binary file or records

        Args:
            file (_type_): buffered reader
            variables (_type_): variable
            offset (int, optional): reader offset. Defaults to 0.
        """
        
        self.minmax = np.fromfile(file, dtype='f4', count=2*len(variables), offset=offset)
    
    def _data(self, file, dtype='f4', count=-1, offset=0):
        """Read binary buffer file

        Args:
            file (_type_): buffered reader
            dtype (str, optional): variable type to be read. Defaults to 'f4'.
            count (int, optional): number of elements to be read. Defaults to -1.
            offset (int, optional): reader offset. Defaults to 0.

        Returns:
            _type_: _description_
        """        
        
        return np.fromfile(file, dtype=dtype, count=count, offset=offset)
    
    def read(self, **kwargs):
        """_summary_

        Raises:
            FileNotFoundError: _description_
        """
                  
        try:
            with open(os.path.join(self.path, self.filename), 'rb') as file:
                data = np.fromfile(file, **p_filter_args(np.fromfile, kwargs))
                return data
        except FileNotFoundError:
            logging.error("%s doesn\'t exist", os.path.join(self.path, self.filename))
            raise FileNotFoundError


class DataBinReader(BinReader):
    """Reader class of binary data outputs file

    Args:
        BinReader (_type_): _description_

    Returns:
        _type_: _description_
    """
    PATTERN = re.compile(r"^.*(?P<num>\d{6})\.bin$")

    def __init__(self, path :str, filename :str):
        super().__init__(path, filename)

    def _read(self, file, variables :list, count :int =-1):
        """
        """
        self._key(file)
        logging.debug('position after reading key : %s bytes', file.tell())
        if self.date_written:
            self._date(file)
            logging.debug('position after reading date : %s bytes', file.tell())
            
        if self.minmax_written:
            self._minmax(file, variables=variables)
            logging.debug('position after reading minmax : %s bytes', file.tell())

        self.data = {self.date[0] : np.reshape(self._data(file, count=count), (len(variables), -1))}

        return self.data
    

    def read(self, variables :list): # ** unpack a dict with splat operator
        """_summary_

        Args:
            variables (list): _description_

        Raises:
            FileNotFoundError: _description_
        """
        # variables = kwargs.pop(arg) # get value and delete key
        try:
            with open(os.path.join(self.path, self.filename), 'rb') as file:
                data = self._read(file, variables=variables)
                
                npdata = data[list(data.keys())[0]]
                ncells = npdata.shape[-1]
                
                cell_data = {}
                for i in range(npdata.shape[0]):
                    cell_data[variables[i]] = [npdata[i].squeeze()]
                    
                cells = {'triangle': np.zeros((ncells, 3))}
                
                mesh = Mesh(points=[], 
                                   cells=cells,
                                   cell_data=cell_data)
                return {list(data.keys())[0]: mesh}
            
        except FileNotFoundError:
            logging.error("%s doesn\'t exist", os.path.join(self.path, self.filename))
            raise FileNotFoundError
 

class ConcatDataBinReader(DataBinReader):
    """Reader class of concatenated binary data outputs file

    Args:
        DataBinReader (_type_): _description_

    Raises:
        FileNotFoundError: _description_
    """
    PATTERN = re.compile(r"^.*(timeserie)\.bin$")

    def __init__(self, path :str, filename :str):
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename
    
    def read(self, variables :list, offset :int, count :int =-1):#, variables :list, num_cells :int, num_bytes :int, **kwargs):
        """_summary_

        Args:
            variables (list): _description_
            num_cells (int): _description_
            num_bytes (int): _description_

        Raises:
            FileNotFoundError: _description_
        """
        # variables = kwargs.pop(arg) # get value and delete key
        try:
            with open(os.path.join(self.path, self.filename), 'rb') as file:
                file.seek(offset)
                
                datadict = self._read(file, variables=variables, count=count)
                
                dict_meshes = {}
                for date, data in datadict.items():
                    npdata = data[list(data.keys())[0]]
                    ncells = npdata.shape[-1]
                    
                    cell_data = {}
                    for i in range(npdata.shape[0]):
                        cell_data[variables[i]] = [npdata[i].squeeze()]
                        
                    cells = {'triangle': np.zeros((ncells, 3))}
                    
                    mesh = Mesh(points=[], 
                                       cells=cells,
                                       cell_data=cell_data)
                    dict_meshes[date] = mesh
                    
                return dict_meshes
                
        except FileNotFoundError:
            logging.error("%s doesn\'t exist", os.path.join(self.path, self.filename))
            raise FileNotFoundError
    
    @staticmethod
    def count_bytes_per_records(variables, num_cells, date_written, minmax_written):
        """_summary_

        Args:
            variables (_type_): _description_
            num_cells (_type_): _description_
            date_written (_type_): _description_
            minmax_written (_type_): _description_

        Returns:
            _type_: number of times per records or dates
        """
        num_bytes_per_records = 4 * ( 1 + len(variables) * num_cells)
        if date_written:
            num_bytes_per_records += 4 * 7
        if minmax_written:
            num_bytes_per_records += 4 * 2 * len(variables)
        return num_bytes_per_records
   
    def dates(self, num_times :int, num_bytes_per_records :int):
        """_summary_

        Args:
            num_times (int): _description_
            num_bytes_per_records (int): _description_

        Yields:
            _type_: _description_
        """
        offset=0
        for _ in range(num_times): # loop variable intentionally unused
            with open(os.path.join(self.path, self.filename), 'rb') as file:
                file.seek(offset)
                self._key(file)
                if self.date_written:
                    self._date(file)
                    yield self.date[0]

                else:
                    logging.info("date ain't written in the file")
                    break

            offset += num_bytes_per_records

    def count_times(self, num_bytes_per_records :int):
        """Retrieves the number of times (or records)

        Args:
            num_bytes (int): _description_

        Raises:
            FileNotFoundError: _description_
        """
        try : 
            file_size = os.path.getsize(f"{self.path}/{self.filename}") # or len(file_rdr.read_file(path, data_minmax_txt_filename)))
            return(file_size // num_bytes_per_records)
        
        except FileNotFoundError:
            logging.error("%s/%s file not found", self.path, self.filename)
            raise FileNotFoundError
    

class GmshElementBinReader(BinReader):
    """_summary_

    Args:
        BinReader (_type_): _description_

    Raises:
        FileNotFoundError: _description_

    Returns:
        _type_: _description_
    """
    PATTERN = re.compile(r"^.*(gmsh_element)\.bin$")
    VARIABLES = ['gmsh_element']

    def __init__(self, path :str, filename :str):
        super().__init__(path, filename)
    
    def read(self):
        """_summary_

        Raises:
            FileNotFoundError: _description_

        Returns:
            _type_: _description_
        """
        try:
            with open(os.path.join(self.path, self.filename), 'rb') as file:
                self._key(file)
                if self.date_written:
                    self._date(file)
                    
                if self.minmax_written:
                    self._minmax(file, variables=GmshElementBinReader.VARIABLES)
                
                data = self._data(file, dtype='i4')
                mesh = Mesh(points=np.zeros((len(data), 3)),
                                   cells={}, 
                                   point_data={'node_mapping': data})
                return mesh
        except FileNotFoundError:
            logging.error("%s doesn\'t exist", os.path.join(self.path, self.filename))
            raise FileNotFoundError


class LonLatDegBinReader(BinReader):
    """_summary_

    Args:
        BinReader (_type_): _description_

    Raises:
        FileNotFoundError: _description_

    Returns:
        _type_: _description_
    """
    PATTERN = re.compile(r"^.*(lon_lat_degrees)\.bin$")
    VARIABLES = ['lon', 'lat']

    def __init__(self, path :str, filename :str):
        super().__init__(path, filename)
    
    def read(self):
        """Read *_lon_lat_degrees.bin file

        Raises:
            FileNotFoundError: _description_

        Returns:
            _type_: _description_
        """
        try:
            with open(os.path.join(self.path, self.filename), 'rb') as file:
                self._key(file)
                if self.date_written:
                    self._date(file)
                    
                if self.minmax_written:
                    self._minmax(file, variables=LonLatDegBinReader.VARIABLES)

                self.lon_lat = self._data(file, dtype='f4').reshape(2, -1)
                
                xyz = np.zeros((3, self.lon_lat.shape[1]))
                xyz[:2,:] = self.lon_lat
                mesh = Mesh(points=xyz.T, 
                                   cells={})
                return mesh
        
        except FileNotFoundError:
            logging.error("%s doesn\'t exist", os.path.join(self.path, self.filename))
            raise FileNotFoundError


class LonLatRadBinReader(BinReader):
    """_summary_

    Args:
        BinReader (_type_): _description_

    Raises:
        FileNotFoundError: _description_

    Returns:
        _type_: _description_
    """
    PATTERN = re.compile(r"^.*(lon_lat_radians)\.bin$")
    VARIABLES = ['lon', 'lat']

    def __init__(self, path :str, filename :str):
        super().__init__(path, filename)

    def read(self):
        """_summary_

        Raises:
            FileNotFoundError: _description_

        Returns:
            _type_: _description_
        """
        try:
            with open(os.path.join(self.path, self.filename), 'rb') as file:
                self._key(file)
                if self.date_written:
                    self._date(file)
                    
                if self.minmax_written:
                    self._minmax(file, LonLatRadBinReader.VARIABLES)

                self.lon_lat = self._data(file, dtype='f4').reshape(2, -1)
                
                xyz = np.zeros((3, self.lon_lat.shape[1]))
                xyz[:2,:] = self.lon_lat
                mesh = Mesh(points=xyz.T, 
                                   cells={})
                return mesh
        
        except FileNotFoundError:
            logging.error("%s doesn\'t exist", os.path.join(self.path, self.filename))
            raise FileNotFoundError


class MeshBinReader(BinReader):
    """_summary_

    Args:
        BinReader (_type_): _description_

    Returns:
        _type_: _description_
    """
    PATTERN = re.compile(r"^.*(mesh)\.bin$")

    def __init__(self, path :str, filename :str):
        super().__init__(path, filename)

    def read(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        try:
            with open(os.path.join(self.path, self.filename), 'rb') as file:
                self.num_nodes, self.num_cells = np.fromfile(file, dtype='i4', count=2)
                self.nodes = np.fromfile(file, dtype='f4', count=2*self.num_nodes).reshape(self.num_nodes, 2)
                self.cells = np.fromfile(file, dtype='i4', count=4*self.num_cells).reshape(self.num_cells, 4) - 1 # numerotation starts at one
                
                xyz = np.zeros((self.nodes.shape[0], 3))
                xyz[:, :2] = self.nodes
                
                mesh = Mesh(points=xyz, cells={"triangle": self.cells[:, :3]})
            return mesh
        
        except FileNotFoundError:
                logging.error("%s doesn\'t exist", os.path.join(self.path, self.filename))
    
        
# default class reader
class TxtReader(Reader):
    """_summary_

    Args:
        Reader (_type_): _description_
    """
    PATTERN = re.compile(r"^.*\.txt$")

    def __init__(self, path :str, filename :str):
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename

    def read(self):
        """_summary_
        """
        try:
            with open(os.path.join(self.path, self.filename), 'r') as file:
                self.content = file.read()
                return self.content
            
        except FileNotFoundError:
            logging.error("%s doesn\'t exist", os.path.join(self.path, self.filename))
        

class InfoTxtReader(TxtReader):
    """_summary_

    Args:
        TxtReader (_type_): _description_

    Returns:
        _type_: _description_
    """
    PATTERN = re.compile(r"^.*(info)\.txt$")

    def __init__(self, path :str, filename :str):
        super().__init__(path, filename)

    def read(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        _content = super().read()
        _pattern = re.compile(r"(?P<filename>\w+\.bin).*:\n\s+- type: (?P<type>.*)" # re.compile = regular expression to regular expression object
                              r"(?:\n\s*- number of nodes: (?P<num_nodes>\w+))?"
                              r"(?:\n\s*- number of cells: (?P<num_cells>\w+))?"
                              r"(?:\n\s*- variables:(?P<variables>.*))?"
                              r"(?:\n\s*- number of elements \(per var\.\): (?P<num_elements>[0-9]*))?"
                              r"(?:\n\s*- date:\s(?P<date>\w+)(?:,\sStarting\sDate\s=\s(?P<start_date>[0-9-T:]+))?)?"
                              r"(?:\n\s*- min/max: (?P<min_max>\w+))?")
        
        infos = {}
        for match in _pattern.finditer(_content): # return an iterator of match objects
            infos[match.group('filename')] = {'type' : match.group('type'),
                                              'num_nodes' : int(match.group('num_nodes')) if match.group('num_nodes') else None,
                                              'num_cells' : int(match.group('num_cells')) if match.group('num_cells') else None,
                                              'variables' : [variable.strip() for variable in match.group('variables').split(',')] \
                                                  if match.group('variables') else None,
                                              'num_elements' : int(match.group('num_elements')) if match.group("num_elements") else None,
                                              'date' : match.group('date') == 'yes' if match.group('date') else None,
                                              'start_date': match.group('start_date') if match.group('start_date') else None,
                                              'min_max' : match.group('min_max') == 'yes' if match.group('min_max') else None}#,
                                            #   'concatenated' : True if re.search(r'timeseries', match.group('filename')) 
                                            # else (False if re.search(r'xxxxxx', match.group('filename')) else None)}
        
        self.infos = p_strip_None(infos)
        return self.infos


class DataMinMaxTxtReader(TxtReader):
    """_summary_

    Args:
        TxtReader (_type_): _description_
    """
    PATTERN = re.compile(r"^.*(data_minmax)\.txt$")

    def __init__(self, path :str, filename :str):
        super().__init__(path, filename)

    def read(self, **kwargs) -> pd.DataFrame:
        """_summary_

        Args:
            path (_type_): _description_
            filename (_type_): _description_

        Returns:
            pd.DataFrame: _description_
        """
        self.data_minmax = pd.read_csv(os.path.join(self.path, self.filename),
                                        sep=r"/s+", engine='python',
                                          **p_filter_args(pd.read_csv, kwargs))
        return self.data_minmax
    
    
class MeshIOReader(Reader):
    """
    Base class for reading mesh files using meshio library.
    Supports various mesh formats including .msh (Gmsh) and .vtk.
    
    Returns a meshio.Mesh object containing:
        - points: array of node coordinates (N x 3)
        - cells: list of cell blocks with connectivity
        - point_data: dictionary of data defined at nodes
        - cell_data: dictionary of data defined at cells
        - field_data: dictionary of field metadata
    """
    PATTERN = re.compile(r"^.*\.(?P<ext>msh|vtk)$")
    
    def __init__(self, path: str, filename: str):
        """
        Initialize MeshIO reader.
        
        Args:
            path (str): Directory path containing the file
            filename (str): Name of the mesh file
        """
        self.path = path
        self.filename = filename
    
    def read(self, **kwargs):
        """
        Read mesh file using meshio.
        
        Returns:
            meshio.Mesh: Mesh object containing geometry and data
        """
        try:
            filepath = os.path.join(self.path, self.filename)
            
            # Read the mesh using meshio
            mesh = readmesh(filepath, **kwargs)
            
            # Adding the projection if any
            projection_wkt = None

            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                in_projection = False
                projection_lines = []
    
                for line in f:
                    line = line.strip()
    
                    if line == "$Projection":
                        in_projection = True
                        continue
    
                    if line == "$EndProjection":
                        in_projection = False
                        break
    
                    if in_projection:
                        projection_lines.append(line)
    
            # Expected structure:
            # $Projection
            # WKT
            # <actual WKT>
            # $EndProjection
            if projection_lines:
                if projection_lines[0] == "WKT":
                    projection_wkt = "\n".join(projection_lines[1:])
                else:
                    projection_wkt = "\n".join(projection_lines)
    
            # Attach to mesh
            if projection_wkt:
                mesh.field_data["projection_wkt"] = projection_wkt
            
            return mesh
            
        except FileNotFoundError:
            logging.error(f"{filepath} doesn't exist")
            raise FileNotFoundError
        except Exception as e:
            logging.error(f"Error reading mesh file: {str(e)}")
            raise


class MshReader(MeshIOReader):
    """
    Reader for Gmsh .msh files using meshio.
    
    Gmsh files contain:
        - Node coordinates
        - Element connectivity (triangles, quads, tetrahedra, etc.)
        - Physical groups and tags
        - Field data
    """
    PATTERN = re.compile(r"^.*\.msh$")
    
    def __init__(self, path: str, filename: str):
        super().__init__(path, filename)


class DataMshReader(MshReader):
    """
    Reader for data-containing Gmsh .msh files.
    Specifically handles files with numerical output data.
    """
    PATTERN = re.compile(r"^.*(?P<num>\d{6})\.msh$")
    
    def __init__(self, path: str, filename: str):
        super().__init__(path, filename)


class VTKReader(MeshIOReader):
    """
    Reader for VTK files using meshio (alternative to vtk library).
    """
    PATTERN = re.compile(r"^.*\.vtk$")
    
    def __init__(self, path: str, filename: str):
        super().__init__(path, filename)
        
    def getdata(self, **kwargs):
        try:
            reader = vtk.vtkUnstructuredGridReader()
            reader.SetFileName(os.path.join(self.path, self.filename))
            reader.ReadAllVectorsOn()
            reader.ReadAllScalarsOn()
            reader.Update()
            ugrid = reader.GetOutput()
            return ugrid

        except FileNotFoundError:
            logging.error("%s doesn\'t exist", os.path.join(self.path, 
                                                            self.filename))
        
    def makedatameshio(self, ugrid, **kwargs):

        VTK_TO_MESHIO = {
            vtk.VTK_VERTEX: "vertex",
            vtk.VTK_POLY_VERTEX: "vertex",
            vtk.VTK_LINE: "line",
            vtk.VTK_POLY_LINE: "line",
            vtk.VTK_TRIANGLE: "triangle",
            vtk.VTK_TRIANGLE_STRIP: "triangle",
            vtk.VTK_POLYGON: "polygon",
            vtk.VTK_PIXEL: "quad",
            vtk.VTK_QUAD: "quad",
            vtk.VTK_TETRA: "tetra",
            vtk.VTK_VOXEL: "hexahedron",
            vtk.VTK_HEXAHEDRON: "hexahedron",
            vtk.VTK_WEDGE: "wedge",
            vtk.VTK_PYRAMID: "pyramid",
        }
        # ---- Points ----
        points = vtk_to_numpy(ugrid.GetPoints().GetData())

        # ---- Cells + bookkeeping ----
        cells = {}
        cell_indices = {}  # map: cell_type -> original VTK cell indices

        for i in range(ugrid.GetNumberOfCells()):
            cell = ugrid.GetCell(i)
            vtk_type = cell.GetCellType()

            if vtk_type not in VTK_TO_MESHIO:
                raise RuntimeError(f"Unsupported VTK cell type {vtk_type}")

            cell_type = VTK_TO_MESHIO[vtk_type]
            point_ids = [cell.GetPointId(j) for j in range(cell.GetNumberOfPoints())]

            cells.setdefault(cell_type, []).append(point_ids)
            cell_indices.setdefault(cell_type, []).append(i)

        # Convert connectivity to numpy
        cells = {k: np.asarray(v, dtype=int) for k, v in cells.items()}

        # ---- Point data ----
        point_data = {}
        pd = ugrid.GetPointData()
        for i in range(pd.GetNumberOfArrays()):
            arr = pd.GetArray(i)
            point_data[arr.GetName()] = vtk_to_numpy(arr)

        # ---- Cell data (correctly grouped) ----
        cell_data = {}
        cd = ugrid.GetCellData()

        for i in range(cd.GetNumberOfArrays()):
            arr = cd.GetArray(i)
            name = arr.GetName()
            data = vtk_to_numpy(arr)

            cell_data[name] = [
                data[cell_indices[cell_type]]
                for cell_type in cells.keys()
            ]

        return Mesh(
            points=points,
            cells=cells,
            point_data=point_data,
            cell_data=cell_data,
        )
    
    def read(self, **kwargs):
        """
        Read mesh file using either meshio or vtk (converted to meshio.Mesh).
        
        Returns:
            meshio.Mesh: Mesh object containing geometry and data
        """
        try:
            filepath = os.path.join(self.path, self.filename)
            
            # Read the mesh using meshio
            mesh = readmesh(filepath, **kwargs)
            return mesh
            
        except FileNotFoundError:
            logging.error(f"{filepath} doesn't exist")
            raise FileNotFoundError
            
        except:
            logging.warning("Error reading mesh file using meshio")
            logging.warning("Using vtk instead")
            try:
                ugrid = self.getdata()
                mesh = self.makedatameshio(ugrid)
                return mesh
            except:
                logging.error("Error reading mesh file using vtk")


class DataVTKReader(VTKReader):
    """
    Reader for data-containing VTK files using meshio.
    Specifically handles files with numerical output data.
    """
    PATTERN = re.compile(r"^.*(\d{6})\.vtk$")
    
    def __init__(self, path: str, filename: str):
        super().__init__(path, filename)


class DiagVTKReader(VTKReader):
    """
    Reader for data-containing VTK files using meshio.
    Specifically handles files with the diagnostic output data.
    """
    PATTERN = re.compile(r"^.*\_diag*\.vtk$")
    
    def __init__(self, path: str, filename: str):
        super().__init__(path, filename)


class TecplotReader(Reader):
    """
    """
    PATTERN = re.compile(r"^([a-z_]*)(?:_(?P<num>\d{6}))?\.plt$")

    def read(self, path: str, filename: str, **kwargs):
        raise NotImplementedError
    

class DataTecplotReader(Reader):
    """
    """
    PATTERN = re.compile(r"^.*(?P<num>\d{6})\.plt$")

    def read(self, path: str, filename: str, **kwargs):
        raise NotImplementedError
    

class WhichReader():
    def __init__(self): 
        self._readers = {('bin', 'data') : DataBinReader,
                         ('bin', 'concat_data') : ConcatDataBinReader,
                         ('bin', 'gmsh_element') : GmshElementBinReader,
                         ('bin', 'lon_lat_degrees') : LonLatDegBinReader,
                         ('bin', 'lon_lat_radians') : LonLatRadBinReader,
                         ('bin', 'mesh') : MeshBinReader,
                         #('bin', 'default') : BinReader,
                         ('txt', 'info') : InfoTxtReader,
                         ('txt', 'data_minmax') : DataMinMaxTxtReader,
                         #('txt', 'default') : TxtReader,
                         ('msh', 'data') : DataMshReader,
                         ('msh', 'default') : MshReader,
                         ('vtk', 'data') : DataVTKReader,
                         ('vtk', 'diag') : DiagVTKReader,
                         ('vtk', 'default') : VTKReader,
                         ('plt', 'data') : DataTecplotReader
                         #('plt', 'default') : TecplotReader,
                         }
        
    def get_reader(self, filename :str, readername :str=None):
        """_summary_

        Args:
            filename (str): _description_
            readername (str, optional): _description_. Defaults to None.

        Returns:
            Reader: _description_
        """
           
        for reader in self._readers.values():
            if not readername: 
                if reader.test_filename(filename):
                    return reader
                
            else:
                if reader.__name__ == readername:
                    return reader

 
# facade      
class FileReader:
    """
    """
    def __init__(self):
        """
        """
        self._which_rdr = WhichReader()
        self._cache_readers = {} # registery of already created reader instances

    def read_file(self, path : str, filename : str, readername : str=None, **kwargs): # forced readername if exists
        """
        """
        if (path, filename) not in self._cache_readers:
            # print(self._which_rdr.get_reader(filename, readername))
            # print(self._which_rdr.get_reader(filename, readername)(path, filename))
            self._cache_readers[(path, filename)] = self._which_rdr.get_reader(filename, readername)(path, filename)

        return self._cache_readers[(path, filename)].read(**p_filter_args(self._cache_readers[(path, filename)].read, kwargs))

    def cache_reader(self, path : str, filename : str):
        """
        """
        return self._cache_readers[(path, filename)]

    @property
    def cache_readers(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        return self._cache_readers



# =============================================================================
# MONKEY PATCH FOR MESHIO READER
# =============================================================================

from meshio.gmsh._gmsh22 import _fast_forward_to_end_block
from meshio._common import warn
from shlex import split as splitsh

def my_read_physical_names(f, field_data):
    line = f.readline().decode()
    num_phys_names = int(line)
    for _ in range(num_phys_names):
        line = splitsh(f.readline().decode())
        key = " ".join(line[2:])
        value = np.array(line[1::-1], dtype=int)
        field_data[key] = value
    _fast_forward_to_end_block(f, "PhysicalNames")

def my_write_physical_names(fh, field_data):
    # Write physical names
    entries = []
    for phys_name in field_data:
        try:
            phys_num, phys_dim = field_data[phys_name]
            phys_num, phys_dim = int(phys_num), int(phys_dim)
            entries.append((phys_dim, phys_num, phys_name))
        except (ValueError, TypeError):
            warn("Field data contains entry that cannot be processed.")
    entries.sort()
    if entries:
        fh.write(b"$PhysicalNames\n")
        fh.write(f"{len(entries)}\n".encode())
        for entry in entries:
            tokens = entry[2].split()
            quoted = " ".join(f'"{t}"' for t in tokens)
            line = f"{entry[0]} {entry[1]} {quoted}\n"
            fh.write(line.encode())
            # fh.write('{} {} "{}"\n'.format(*entry).encode())
        fh.write(b"$EndPhysicalNames\n")


# Override the original
import meshio.gmsh._gmsh22
meshio.gmsh._gmsh22._read_physical_names = my_read_physical_names
meshio.gmsh._gmsh22._write_physical_names = my_write_physical_names
