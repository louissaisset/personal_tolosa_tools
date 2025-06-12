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


# strategy factory pattern ?
class Reader(ABC):
    PATTERN = re.compile(r"^(?P<name>[a-z_]*)(?:_(?P<num>\d{6}))?\.(?P<ext>bin|txt|vtk|plt)$")

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
                        1 : {'date_written': False, 'minmax_written': True}, # if min / max values of each field written at the beginning of each time step
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
                return(np.fromfile(file, **p_filter_args(np.fromfile, kwargs)))
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
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename

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
                return(self._read(file, variables=variables))
            
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
                return(self._read(file, variables=variables, count=count))
                
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
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename
    
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

                return self._data(file, dtype='i4')
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
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename
    
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
                return self.lon_lat
        
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
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename

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
                return self.lon_lat
        
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
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename

    def read(self):
        """_summary_

        Returns:
            _type_: _description_
        """
        try:
            with open(os.path.join(self.path, self.filename), 'rb') as file:
                (self.num_nodes, self.num_cells) = np.fromfile(file, dtype='i4', count=2)
                self.nodes = np.fromfile(file, dtype='f4', count=2*self.num_nodes).reshape(self.num_nodes, 2)
                self.cells = np.fromfile(file, dtype='i4', count=4*self.num_cells).reshape(self.num_cells, 4) - 1 # numerotation starts at one

            return {'num_nodes' : self.num_nodes, 'num_cells' : self.num_cells, 'nodes': self.nodes, 'cells' : self.cells}
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
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename

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
                                              'variables' : [variable.strip() for variable in match.group('variables').split(',')] if match.group('variables') else None,
                                              'num_elements' : int(match.group('num_elements')) if match.group("num_elements") else None,
                                              'date' : match.group('date') == 'yes' if match.group('date') else None,
                                              'start_date': match.group('start_date') if match.group('start_date') else None,
                                              'min_max' : match.group('min_max') == 'yes' if match.group('min_max') else None}#,
                                            #   'concatenated' : True if re.search(r'timeseries', match.group('filename')) else (False if re.search(r'xxxxxx', match.group('filename')) else None)}
        
        self.infos = p_strip_None(infos)
        return self.infos


class DataMinMaxTxtReader(TxtReader):
    """_summary_

    Args:
        TxtReader (_type_): _description_
    """
    PATTERN = re.compile(r"^.*(data_minmax)\.txt$")

    def __init__(self, path :str, filename :str):
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename

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


class VTKReader(Reader):
    """
    """
    PATTERN = re.compile(r"^([a-z_]*)(?:_(?P<num>\d{6}))?\.vtk$")

    def __init__(self, path :str, filename :str):
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename

    
    def read(self, **kwargs):
        raise NotImplementedError
    

class DataVTKReader(VTKReader):
    """
    """
    PATTERN = re.compile(r"^.*(\d{6})\.vtk$")

    def __init__(self, path :str, filename :str):
        """_summary_

        Args:
            path (str): _description_
            filename (str): _description_
        """
        self.path = path
        self.filename = filename


    def read(self, **kwargs):
        """
        Returns a vtk.vtkUnstructuredGrid object to be processed separately
        """
        try:
            reader = vtk.vtkUnstructuredGridReader()
            
            reader.SetFileName(os.path.join(self.path, self.filename))
            
            reader.ReadAllVectorsOn()
            reader.ReadAllScalarsOn()
            reader.Update()
            
            return reader.GetOutput()
        except FileNotFoundError:
            logging.error("%s doesn\'t exist", os.path.join(self.path, self.filename))
    
    
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
        self._readers = {#('bin', 'default') : BinReader,
                         ('bin', 'data') : DataBinReader,
                         ('bin', 'concat_data') : ConcatDataBinReader,
                         ('bin', 'gmsh_element') : GmshElementBinReader,
                         ('bin', 'lon_lat_degrees') : LonLatDegBinReader,
                         ('bin', 'lon_lat_radians') : LonLatRadBinReader,
                         ('bin', 'mesh') : MeshBinReader,
                         #('txt', 'default') : TxtReader,
                         ('txt', 'info') : InfoTxtReader,
                         ('txt', 'data_minmax') : DataMinMaxTxtReader,
                         #('vtk', 'default') : VTKReader,
                         ('vtk', 'data') : DataVTKReader,
                         #('plt', 'default') : TecplotReader,
                         ('plt', 'data') : DataTecplotReader}
        
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




###############################################################################
################################  OLD VERSION   ###############################
###############################################################################



# # strategy factory pattern ?
# class Reader(ABC):
#     PATTERN = re.compile(r"^[^_]*_(?P<name>\w*).(?P<ext>bin|txt|vtk)$")

#     @abstractmethod
#     def read(self, path : str, filename : str, **kwargs):
#         pass

#     @classmethod
#     @abstractmethod
#     def search(cls, path : str, name :str, ext :str):
#         for file in os.listdir(path):
#             match = cls.PATTERN.match(file)
#             if match.group('ext') == ext and (match.group('name') == name or match.group('name').startswith(name)):
#                 yield file
#         #         break # break after the first occurrence
#         # else:
#         #     logging.error('info.txt output file not found')

#     @classmethod
#     def parse_filename(cls, filename : str):
#         """
#         parse filename
#         return name and extension
#         """
#         match = cls.PATTERN.match(filename)
#         if match:
#             name = match.group('name')
#             ext = match.group('ext')
#             # if name.startswith('data') and ext == 'bin': # better way ? how to get the increment also
#             #     name = 'data'
            
#             return name, ext
#         else:
#             logging.error('at least one match not found')


# class VTKDataReader(Reader):
    
#     EXT = 'vtk'
    
#     def read(self, path : str, filename : str, **kwargs):
#         """
#         """            
#         try:
#             reader = vtk.vtkUnstructuredGridReader()
            
#             reader.SetFileName(os.path.join(path, filename))
            
#             reader.ReadAllVectorsOn()
#             reader.ReadAllScalarsOn()
#             reader.Update()
            
#             return reader.GetOutput()
#         except FileNotFoundError:
#             logging.error("%s doesn\'t exist", os.path.join(path, filename))
            
#     @classmethod
#     def search(cls, path):
#         return super().search(path, '', cls.EXT)


# # default class reader
# class BinReader(Reader):
#     EXT = 'bin'
#     def _key(self, file, offset=0):
#         """
#         read the key to define the content of the file
#         file : buffered reader
#         offset : reader offset
#         """
#         _key_options = {0: {'date_written': False, 'minmax_written': False},
#                         1 : {'date_written': False, 'minmax_written': True}, # if min / max values of each field written at the beginning of each time step
#                         2 : {'date_written': True, 'minmax_written': False}, # if date written at the beginning of each time step
#                         3 : {'date_written': True, 'minmax_written': True}}
#         try:
#             self.key = np.fromfile(file, dtype='i4', count=1, offset=offset)[0]
        
#             if self.key in _key_options:
#                 self.date_written = _key_options[self.key]['date_written']
#                 self.minmax_written = _key_options[self.key]['minmax_written']
#             else:
#                 logging.error("key value %s not valid", self.key)
#         except Exception as e:
#             logging.error('failed to read key due to %s', str(e))

#     def _date(self, file, offset=0):
#         """
#         read date at the beginning of each binary file
#         file : buffered reader
#         offset : reader offset
#         """
#         self.i  = np.fromfile(file, dtype='f4', count=1, offset=offset)[0]

#         gregorian_date = np.fromfile(file, dtype='i4', count=5, offset=offset)
#         gregorian_date_dt = dt.strptime(''.join(list(map(str, gregorian_date))), '%Y%m%d%H%M')
#         self._gregorian_date = gregorian_date_dt.strftime('%Y-%m-%d_%H:%M')
        
#         self._julian_cnes_date = str(np.fromfile(file, dtype='f4', count=1, offset=offset)[0])
    
#     @property
#     def date(self):
#         try:
#             return (self._gregorian_date, self._julian_cnes_date)
#         except AttributeError:
#             logging.error("date doesn\' t exist")

#     def _minmax(self, file, variables, offset = 0):
#         """
#         read minimum and maximum values of each field.
#         file   : buffered reader
#         offset : reader offset
#         variables : variables
#         """
#         self.minmax = np.fromfile(file, dtype='f4', count=2*len(variables), offset=offset)
    
#     def _data(self, file, dtype='f4', count=-1, offset=0):
#         """
#         read binary buffer file
#         return an array
#         file   : buffered reader
#         type   : variable type to be read
#         count  : number of elements to be read
#         offset : reader offset
#         """
#         return np.fromfile(file, dtype=dtype, count=count, offset=offset)
    
#     def read(self, path : str, filename : str, **kwargs):
#         """
#         read binary buffer file
#         return an array
#         """            
#         try:
#             with open(os.path.join(path, filename), 'rb') as file:
#                 return(np.fromfile(file, **kwargs))
#         except FileNotFoundError:
#             logging.error("%s doesn\'t exist", os.path.join(path, filename))




# class Data(BinReader):
#     """
#     """
#     NAME = 'data'

#     def read(self, path : str, filename : str, variables : list, **kwargs): # ** unpack a dict with splat operator
#         """
#         read data binary file
#         path : path of the binary file
#         filename : filename of the binary file
#         """
#         # variables = kwargs.pop(arg) # get value and delete key
#         try:
#             with open(os.path.join(path, filename), 'rb') as file:
                
#                 self._key(file, **p_filter_args(self._key, kwargs))
#                 if self.date_written:
#                     self._date(file, **p_filter_args(self._date, kwargs))
                    
#                 if self.minmax_written:
#                     self._minmax(file, variables, **p_filter_args(self._minmax, kwargs))

#                 return (self.date[0], np.reshape(self._data(file, **p_filter_args(self._data, kwargs)), (len(variables), -1))) # np.reshape( data, (len(variables), -1))
#         except FileNotFoundError:
#             logging.error("%s doesn\'t exist", os.path.join(path, filename))

#     @staticmethod
#     def _count_byte(variables, num_cells, date_written, minmax_written):
#         num_byte = 4 * ( 1 + len(variables) * num_cells)
#         if date_written:
#             num_byte += 4 * 7
#         if minmax_written:
#             num_byte += 4 * 2 * len(variables)
#         return num_byte
    
#     @classmethod
#     def search(cls, path):
#         return super().search(path, cls.NAME, cls.EXT)
    

# class GmshElement(BinReader):
#     NAME = 'gmsh_element'
#     def _data(self, file, dtype='i4', count=-1, offset=0):
#         return super()._data(file, dtype, count, offset)
    
#     def read(self, path : str, filename : str, **kwargs):
#         try:
#             with open(os.path.join(path, filename), 'rb') as file:
#                 self._key(file, **p_filter_args(self._key, kwargs))
#                 if self.date_written:
#                     self._date(file, **p_filter_args(self._date, kwargs))
                    
#                 if self.minmax_written:
#                     self._minmax(file, **p_filter_args(self._minmax, kwargs))

#                 return {'key' : self.key, 'data' : self._data(file, **p_filter_args(self._data, kwargs))}
#         except FileNotFoundError:
#             logging.error("%s doesn\'t exist", os.path.join(path, filename))


# class LonLatDeg(BinReader):
#     NAME = 'lon_lat_degrees'
#     def read(self, path : str, filename : str, num_nodes : int, **kwargs):
#         try:
#             with open(os.path.join(path, filename), 'rb') as file:
#                 self._key(file, **p_filter_args(self._key, kwargs))
#                 if self.date_written:
#                     self._date(file, **p_filter_args(self._date, kwargs))
                    
#                 if self.minmax_written:
#                     self._minmax(file, **p_filter_args(self._minmax, kwargs))
#                 self.lon_lat = np.fromfile(file, dtype='f4', count=2*num_nodes).reshape(2, num_nodes)

#             return {'lon_lat' : self.lon_lat}
#         except FileNotFoundError:
#             logging.error("%s doesn\'t exist", os.path.join(path, filename))


# class LonLatRad(BinReader):
#     NAME = 'lon_lat_radians'
#     def read(self, path : str, filename : str, num_nodes : int, **kwargs):
#         try:
#             with open(os.path.join(path, filename), 'rb') as file:
#                 self._key(file, **p_filter_args(self._key, kwargs))
#                 if self.date_written:
#                     self._date(file, **p_filter_args(self._date, kwargs))
                    
#                 if self.minmax_written:
#                     self._minmax(file, **p_filter_args(self._minmax, kwargs))
#                 self.lon_lat = np.fromfile(file, dtype='f4', count=2*num_nodes).reshape(2, num_nodes)

#             return {'lon_lat' : self.lon_lat}
#         except FileNotFoundError:
#             logging.error("%s doesn\'t exist", os.path.join(path, filename))


# class Mesh(BinReader):
#     NAME = 'mesh'
#     def read(self, path : str, filename : str, **kwargs):
#         try:
#             with open(os.path.join(path, filename), 'rb') as file:
#                 (self.num_nodes, self.num_cells) = np.fromfile(file, dtype='i4', count=2)
#                 self.nodes = np.fromfile(file, dtype='f4', count=2*self.num_nodes).reshape(self.num_nodes, 2)
#                 self.cells = np.fromfile(file, dtype='i4', count=4*self.num_cells).reshape(self.num_cells, 4)

#             return {'num_nodes' : self.num_nodes, 'num_cells' : self.num_cells, 'nodes': self.nodes, 'cells' : self.cells}
#         except FileNotFoundError:
#                 logging.error("%s doesn\'t exist", os.path.join(path, filename))
    
#     @classmethod
#     def search(cls, path):
#         """
#         """
#         return super().search(path, cls.NAME, cls.EXT)
        

# # default class reader
# class TxtReader(Reader):
#     EXT = 'txt'
#     def read(self, path : str, filename : str):
#         try:
#             with open(os.path.join(path, filename), 'r') as file:
#                 return(file.read())
#         except FileNotFoundError:
#             logging.error("%s doesn\'t exist", os.path.join(path, filename))
        

# class Info(TxtReader):
#     NAME = 'info'
#     def read(self, path, filename, **kwargs):
#         _content = super().read(path, filename)
#         _pattern = re.compile(r"(?P<filename>\w+\.bin).*:\n\s+- type: (?P<type>.*)" # re.compile = regular expression to regular expression object
#                               r"(?:\n\s*- number of nodes: (?P<num_nodes>\w+))?"
#                               r"(?:\n\s*- number of cells: (?P<num_cells>\w+))?"
#                               r"(?:\n\s*- variables:(?P<variables>.*))?"
#                               r"(?:\n\s*- number of elements \(per var\.\): (?P<num_elements>[0-9]*))?"
#                               r"(?:\n\s*- date:\s(?P<date>\w+)(?:,\sStarting\sDate\s=\s(?P<start_date>[0-9-T:]+))?)?"
#                               r"(?:\n\s*- min/max: (?P<min_max>\w+))?")
        
#         infos = {}
#         for match in _pattern.finditer(_content): # return an iterator of match objects
#             infos[match.group('filename')] = {'type' : match.group('type'),
#                                               'num_nodes' : int(match.group('num_nodes')) if match.group('num_nodes') else None,
#                                               'num_cells' : int(match.group('num_cells')) if match.group('num_cells') else None,
#                                               'variables' : [variable.strip() for variable in match.group('variables').split(',')] if match.group('variables') else None,
#                                               'num_elements' : int(match.group('num_elements')) if match.group("num_elements") else None,
#                                               'date' : match.group('date') == 'yes' if match.group('date') else None,
#                                               'start_date': match.group('start_date') if match.group('start_date') else None,
#                                               'min_max' : match.group('min_max') == 'yes' if match.group('min_max') else None}#,
#                                             #   'concatenated' : True if re.search(r'timeseries', match.group('filename')) else (False if re.search(r'xxxxxx', match.group('filename')) else None)}

#         return p_strip_None(infos)

#     @classmethod
#     def search(cls, path):
#         """
#         search info filename based on name and extension
#         return a generator object
#         """
#         return super().search(path, cls.NAME, cls.EXT)


# class DataMinMax(TxtReader):
#     NAME = 'data_minmax'
#     def read(self, path, filename, **kwargs) -> pd.DataFrame:
#         """
#         return a pandas.DataFrame
#         """
#         return(pd.read_csv(os.path.join(path, filename), sep=r"/s+", engine='python', **p_filter_args(pd.read_csv, kwargs)))

#     @classmethod
#     def search(cls, path):
#         return super().search(path, cls.NAME, cls.EXT)

# class WhichReader():
#     def __init__(self):   
#         self._bin_readers = {'default' : BinReader,
#                              'data' : Data,
#                              'gmsh_element' : GmshElement,
#                              'lon_lat_degrees' : LonLatDeg,
#                              'lon_lat_radians' : LonLatRad, #'lon_lat_degrees' : LonLatDeg, 'lon_lat_radians' : LonLatRad ?
#                              'mesh' : Mesh}
                             
#         self._txt_readers = {'default' : TxtReader,
#                              'info' : Info,
#                              'data_minmax' : DataMinMax}
        
#         self._vtk_readers = {'default': VTKDataReader}
        
    
#     def _reader(self, ext : str, name : str='default') -> 'Reader':
#         if ext == 'bin':
#             return self._bin_readers.get(name, BinReader)
#         elif ext == 'txt':
#             return self._txt_readers.get(name, TxtReader)
#         elif ext == 'vtk':
#             return self._vtk_readers.get(name, VTKDataReader)


# # facade      
# class FileReader:
#     def __init__(self):
#         self._which_rdr = WhichReader()
#         self._cache_readers = {} # registery of already created reader instances

#     def read_file(self, path : str, filename : str, readername : str=None, **kwargs):
#         name_parse, ext = Reader.parse_filename(filename)
#         print(name_parse, ext)
#         if name_parse.startswith('data') and ext == 'bin':
#             name_parse = 'data'
#         if not readername:
#             name = kwargs.get('name', name_parse) # useful ? _filter_args ?
#         else:
#             name = readername
#         if (path, filename) not in self._cache_readers:
#             if ext == 'vtk':
#                 self._cache_readers[(path, filename)] = self._which_rdr._reader(ext)()
#             else:
#                 self._cache_readers[(path, filename)] = self._which_rdr._reader(ext, name)()
#         return self._cache_readers[(path, filename)].read(path, filename, **kwargs)

#     def cache_reader(self, path : str, filename : str):
#         return self._cache_readers[(path, filename)]

#     @property
#     def cache_readers(self):
#         return self._cache_readers
    
    
    
    
    
# if __name__ == '__main__':

#     import os
#     from init import set_logging
#     import matplotlib.pyplot as plt
    
#     set_logging('info', 'log/')

#     # example path
#     path = 'path/to/full/'

#     # search examples
#     supported_filenames = list(Reader.search(path))
#     binary_filenames = list(BinReader.search(path))
#     data_binary_filenames = list(DataBinReader.search(path))
#     txt_filenames = list(TxtReader.search(path))
#     info_txt_filename = next(InfoTxtReader.search(path))
#     mesh_binary_filename = next(MeshBinReader.search(path))
#     lon_lat_binary_filename = next(LonLatDegBinReader.search(path))
#     concat_data_binary_filename = next(ConcatDataBinReader.search(path))
#     data_minmax_txt_filename = next(DataMinMaxTxtReader.search(path))

#     # reader object
#     file_rdr = FileReader()

#     # read examples
#     details = file_rdr.read_file(path, info_txt_filename)

#     # indexing through details dictionnary
#     num_nodes = details[mesh_binary_filename]['num_nodes']
#     num_cells = details[mesh_binary_filename]['num_cells']
#     variables = details[concat_data_binary_filename]['variables']
#     minmax_written = details[concat_data_binary_filename]['min_max']
#     date_written = details[concat_data_binary_filename]['date']
#     # count number of bytes
#     num_bytes_per_records = ConcatDataBinReader.count_bytes_per_records(variables, num_cells, date_written, minmax_written)

#     lon_lat = file_rdr.read_file(path, lon_lat_binary_filename, num_nodes=num_nodes)
#     triangles = file_rdr.read_file(path, mesh_binary_filename)['cells'][:,:3]

#     concat_data_bin_rdr = ConcatDataBinReader(path, concat_data_binary_filename)
#     # get the number totals of outputs times
#     num_times = concat_data_bin_rdr.count_times(num_bytes_per_records)
#     # list of dates
#     dates = list(concat_data_bin_rdr.dates(num_times, num_bytes_per_records))

#     # read concatened data binary file
#     count = len(variables) * num_cells
#     concat_data = {}
#     offset = 0
#     for t in range(num_times):
#         concat_data.update(file_rdr.read_file(path, concat_data_binary_filename, variables=variables,
#                                             count=count, offset=offset, prions=2))
#         offset += num_bytes_per_records
    
#     # plot example
#     # date = '1997-12-28_20:00'
#     # fig, ax = plt.subplots(figsize=(8,6))
#     # im = ax.tripcolor(lon_lat[0,:], lon_lat[1,:], triangles, concat_data[date][0, :]) # indexing at 0 for the first variable
#     # plt.show()

