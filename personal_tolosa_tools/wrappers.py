#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A series of usefull wrappers to be used in multiple tools
"""

import sys
from .common import p_error, p_ok
from .processors import VTKDataProcessor, BinDataProcessor
from .readers import FileReader, InfoTxtReader, DataBinReader, MeshBinReader, DataVTKReader

from dask import delayed


def files_for_timestep(t, folder,
                       txt_info_files, bin_data_files, bin_mesh_files, 
                       vtk_data_files):
    """
    Parameters
    ----------
    t : int
        The timestep of the desired file.
    folder : str
        Global path towards the folder wich contains the result files.
    txt_info_files : list of str
        relative path towards the txt info files.
    bin_data_files : list of str
        relative paths towards the binary result files.
    bin_mesh_files : list of str
        relative path towards the binary mesh files.
    vtk_data_files : list of str
        relative path towards the result files.

    Returns
    -------
    A tuple containing the processor type expected to read the file content, 
    the folder, and the file/s corresponding to the result file of step t. If 
    no files correspond the t, then a tuple (None, '') is retuned.
    """
    if len(bin_data_files) and len(bin_mesh_files) and len(txt_info_files):
        t_file = [f for f in bin_data_files if f.endswith(f'_{t:06}.bin')]
        if t_file:
            return('bin', folder, t_file[0], bin_mesh_files[0], txt_info_files[0])
        else:
            return(None, '')
        
    elif len(vtk_data_files) > 0:
        t_file = [f for f in vtk_data_files if f.endswith(f'_{t:06}.vtk')]
        if t_file:
            return('vtk', folder, t_file[0])
        else:
            return(None, '')
    else:
        return(None, '')

def files_for_timesteps(timestep_eval, folder):
    """
    Parameters
    ----------
    timestep_eval : int or iterable
        The timestep-s of the desired file-s to be used.
    folder : str
        Global path towards the folder wich contains the result files.

    Returns
    -------
    A list of tuples containing the results of files_for_timestep(*args) for 
    any t in timestep_eval
    """
    
    # Define all available files to be read
    txt_info_files = sorted(list(InfoTxtReader.search(folder)))
    p_ok(f"Available txt info files : {txt_info_files}")
    bin_data_files = sorted(list(DataBinReader.search(folder)))
    p_ok(f"Available binary data files : {bin_data_files}")
    bin_mesh_files = sorted(list(MeshBinReader.search(folder)))
    p_ok(f"Available binary mesh files : {bin_mesh_files}")
    vtk_data_files = sorted(list(DataVTKReader.search(folder)))
    p_ok(f"Available VTK Data files : {vtk_data_files}")
    
    resu = []
    if timestep_eval.__class__ == int:
        resu += [files_for_timestep(timestep_eval, 
                                    folder,
                                    txt_info_files, 
                                    bin_data_files, 
                                    bin_mesh_files, 
                                    vtk_data_files)]
    else:
        try:
            for t in timestep_eval:
                # Check which files should be used for each timestep
                resu += [files_for_timestep(t, 
                                            folder,
                                            txt_info_files, 
                                            bin_data_files, 
                                            bin_mesh_files, 
                                            vtk_data_files)]
        except:
            p_error("Unrecognised timestep format. Should be either int or iterable")
            sys.exit(1)
    return(resu)

def process_vtk(folder, vtk_data_file):
    """
    Args
    ----------
    folder : str
        Global path towards the folder wich contains the result file.
    vtk_data_file : str
        relative path towards the result file.

    Returns
    -------
    processor :
        A personal_tolosa_tools.processors.VTKDataProcessor that uses the data
        inside vtk_data_file.
    """
    
    # Instantiate the file reader
    file_rdr = FileReader()
    
    # Read contents of VTK file
    data = file_rdr.read_file(folder, vtk_data_file)
    
    # Process the contents of the file
    processor = VTKDataProcessor(data)
    
    return(processor)

def process_bin(folder, bin_data_file, bin_mesh_file, txt_info_file):
    """
    Args
    ----------
    folder : str
        Global path towards the folder wich contains the result file.
    bin_data_file : str
        relative path towards the binary result file.
    bin_mesh_file : str
        relative path towards the binary mesh file.
    txt_info_file : str
        relative path towards the txt info file.

    Returns
    -------
    processor :
        A personal_tolosa_tools.processors.VBinDataProcessor that uses the data
        inside bin_data_file.
    """
    # Instantiate the file reader
    file_rdr = FileReader()
    
    # Read the contents of each of the txt info file
    details = file_rdr.read_file(folder, txt_info_file)
    
    # Extract the name of the variables
    possible_keys = [k for k in details.keys() if (k.endswith('_data_xxxxxx.bin') or k==bin_data_file)]
    if possible_keys :
        variables = details[possible_keys[0]]['variables']
        p_ok(f"Using Variables: {variables}")
    else:
        sys.exit()
    # Read the contents of each of the binary mesh
    mesh = file_rdr.read_file(folder, bin_mesh_file)
    
    # Read the contents of each of the binary data file
    data = file_rdr.read_file(folder, bin_data_file, variables=variables)
    
    # Process the contents of the file
    processor = BinDataProcessor(data, mesh, variables)
    
    return(processor)

@delayed
def plot_data_plotter(plotter, process_type, *args):
    """
    Args
    ----------
    plotter : str
        The plotter to be used for the figure creation
    process_type : str ('vtk' or 'bin')
        Type of data process to apply.
    *args : list 
        The list of arguments for either process_vtk or process_bin
        
    Returns
    -------
        None : lazily launches the plotting through plotter.Plot(processor)
    """
    if process_type == "vtk":
        processor = process_vtk(*args)
    elif process_type == "bin":
        processor = process_bin(*args)
    plotter.Plot(processor)


@delayed
def plot_tri_data_comparison(plotter, process_type, args1, args2):
    """
    Args
    ----------
    plotter : str
        The plotter to be used for the figure creation.
    process_type : str ('vtk' or 'bin')
        Type of data process to apply.
    args1 : iterable
        The list of arguments for either process_vtk or process_bin for the 
        first data source.
    args2 : iterable
        The list of arguments for either process_vtk or process_bin for the 
        first data source.
        
    Returns
    -------
        None : lazily launches the plotting through plotter.Plot(processor)
    """
    if process_type == "vtk":
        processor1 = process_vtk(*args1)
        processor2 = process_vtk(*args2)
    elif process_type == "bin":
        processor1 = process_bin(*args1)
        processor2 = process_bin(*args2)
    
    
    cell_data_diff = processor1.compute_cell_data_differences(processor2)
    print(cell_data_diff)
    tripcolor_tri, tricontour_tri = processor1.compute_triangulations()
    plotter.plot_triangle_data(tripcolor_tri, 
                               tricontour_tri,
                               cell_data_diff, 
                               processor1.cell_centers_array)

@delayed
def interp_data_on_grid(X, Y, data_key, process_type, *process_args):
    
    if process_type == "vtk":
        processor = process_vtk(*process_args)
    elif process_type == "bin":
        processor = process_bin(*process_args)
    
    interpolated_value = processor.compute_interpolation_masked_grid(X, Y, 
                                                                     data_key,
                                                                     method='nearest')
    return(interpolated_value)


