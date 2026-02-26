#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 31 14:22:52 2025

@author: llsaisset
"""

import sys, os
if os.uname()[1].startswith('belenos'):
    path_tolosa_path = "~/SAVE/DATA/Scripts/personal_tolosa_tools/"
else:
    path_tolosa_path = "~/DATA/Scripts/personal_tolosa_tools/"
os.environ['PATH'] += os.pathsep +  os.path.expanduser(f'{path_tolosa_path}/scripts/tools/')
sys.path.append(os.path.expanduser(path_tolosa_path))
import personal_tolosa_tools as ptt

import matplotlib as mpl
# mpl.use('agg')

import matplotlib.pyplot as plt
# Paramètres d'affichage pour que ce soit toujours plus propre
plt.rcParams["font.family"] = "cmr10"
plt.rcParams["font.size"] = 8
if not os.uname()[1].startswith('belenos'):
    plt.rcParams['text.usetex'] = True
    plt.rcParams['axes.formatter.use_mathtext'] = True
    plt.rcParams['mathtext.fontset'] = "custom"
    plt.rcParams['mathtext.rm'] = "cmr10"
    plt.rcParams['mathtext.it'] = "cmr10:italic"
    plt.rcParams['mathtext.bf'] = "cmr10:bold"

from pathlib import Path
import argparse

def main():

    # Read args and kwargs
    parser = argparse.ArgumentParser(
        description="A small python script to generate matplotlib figures of \
    a mesh using the informations of the first '.vtk' file found inside the \
    current path"
        )
    # Parse arguments
    args = parser.parse_args()


    print("\nBeginning script for plotting the grid info from the diag.vtk file...")

    # Initialize parameters
    current_path = Path.cwd()
    ptt.p_ok(f"Launched from : {current_path}")

    output_dir = str((current_path / f'Figures_{current_path.name}').resolve())
    ptt.p_ok(f"Defined Figure folder : {output_dir}")

    current_path = str(current_path)

    # Instantiate Reader Class
    # reader = ptt.VTKDataReader(current_path)

    # New version using Roman's method
    supported_filenames = sorted(list(ptt.Reader.search(current_path)))
    ptt.p_ok(f"Supported filenames for reader: {supported_filenames}")

    # Needed for Binary plots
    txt_info_files = sorted(list(ptt.InfoTxtReader.search(current_path)))
    bin_data_files = sorted(list(ptt.DataBinReader.search(current_path)))
    bin_mesh_files = sorted(list(ptt.MeshBinReader.search(current_path)))
    ptt.p_ok(f"Supported filenames for binary data:")
    if len(txt_info_files) == 0:
        ptt.p_error(f"Info file: {txt_info_files}")
    elif len(txt_info_files) == 1:
        ptt.p_ok(f"Info file: {txt_info_files}")
    else:
        ptt.p_warning(f"Info file: {txt_info_files}")
    if len(bin_data_files) == 0:
        ptt.p_error(f"Data files: {bin_data_files}")
    elif len(bin_data_files) == 1:
        ptt.p_ok(f"Data files: {bin_data_files}")
    else:
        ptt.p_warning(f"Data files: {bin_data_files}")
    if len(bin_mesh_files) == 0:
        ptt.p_error(f"Mesh files: {bin_mesh_files}")
    elif len(bin_mesh_files) == 1:
        ptt.p_ok(f"Mesh files: {bin_mesh_files}")
    else:
        ptt.p_warning(f"Mesh files: {bin_mesh_files}")
    
    # Needed for VTK plots
    vtk_diag_files = sorted(list(ptt.DiagVTKReader.search(current_path)))
    ptt.p_ok(f"Supported filenames for vtk data:")
    if len(vtk_diag_files) == 0:
        ptt.p_error(f"Diagnostic files: {vtk_diag_files}")
    elif len(vtk_diag_files) == 1:
        ptt.p_ok(f"Diagnostic files: {vtk_diag_files}")
    else:
        ptt.p_warning(f"Diagnostic files: {vtk_diag_files}")
    
    # Instantiate the reader
    file_rdr = ptt.FileReader()
    
    print("\nBeginning the plotting...")
    
    # New version
    if len(bin_data_files) and len(bin_mesh_files) and len(txt_info_files):
        ptt.p_ok(f"Using Binary Data file: {bin_data_files[0]}")
        ptt.p_ok(f"Using Binary Mesh file: {bin_mesh_files[0]}")
        ptt.p_ok(f"Using Text info file: {txt_info_files[0]}")
        
        details = file_rdr.read_file(current_path, txt_info_files[0])
        if len(bin_data_files) > 1:
            variables = details['result_data_xxxxxx.bin']['variables']
        elif len(bin_data_files) == 1:
            variables = details[bin_data_files[0]]['variables']
        ptt.p_ok(f"Using Variables: {variables}")
        
        data = file_rdr.read_file(current_path, bin_data_files[0], variables=variables)
        mesh = file_rdr.read_file(current_path, bin_mesh_files[0])
        
        # Processdata
        processor = ptt.BinDataProcessor(data, mesh, variables)
        
        # processor.cell_data['radiusratio'] = processor.compute_radiusratio()
        
    elif len(vtk_diag_files) > 0:
        data = file_rdr.read_file(current_path, vtk_diag_files[0])
        # Processdata
        processor = ptt.VTKDataProcessor(data)
        processor.cell_data['radiusratio'] = processor.compute_radiusratio()
    else:
        sys.exit()
    
    # Configure the data plots
    plotter = ptt.Plotter(output_dir)
    plotter.figure_format = 'pdf'
    plotter.figure_tickfontsize = 5
    plotter.figure_size = (6,6)
    
    plotter.triplot = False
    plotter.pcolor_key = ''
    plotter.contour_key = ''
    plotter.quiver_u_key = ''
    plotter.quiver_v_key = ''
    plotter.rectangle_positions = [(-10000, -3000, -4000, 1000), 
                                   (-7000, -2000, 4500, 8500), 
                                   (-17000, -12000, -10000, -5000), 
                                   (-1000, 4000, -2000, 2000)]
    plotter.rectangle_colors = 'k'
    
    new_figsize_list = [(4,4),
                        (3.5,3.5),
                        (3,3),
                        (3.5,3.5)]
    new_filename_list = ['mesh_zoom_ilelongue',
                         'mesh_zoom_port',
                         'mesh_zoom_pointepenhir',
                         'mesh_zoom_bassinest']
    
    
    
    
    plotter.figure_filename = 'mesh_complet'
    plotter.triplot = True
    ptt.p_ok("Defined the plotter arguments:")
    print(plotter.__dict__)
    
    plotter.Plot(processor)
    
    for newplotter, new_filename, new_figsize in zip(plotter.zoomed_plotters, new_filename_list, new_figsize_list):
        newplotter.figure_filename = new_filename
        newplotter.figure_size = new_figsize
        ptt.p_ok("Defined the plotter arguments:")
        print(newplotter.__dict__)
        newplotter.Plot(processor)
        
    
    
    plotter.figure_filename = 'bathy_complet'
    plotter.figure_size = (7,7)
    plotter.triplot = False
    plotter.pcolor_key = 'bathy'
    plotter.pcolor_units = 'm'
    plotter.pcolor_cmap = 'gist_earth_r'
    plotter.pcolor_min = -25
    plotter.pcolor_max = 50
    ptt.p_ok("Defined the plotter arguments:")
    print(plotter.__dict__)
    
    plotter.Plot(processor)
    
    new_figsize_list = [(4,4),
                        (3.5,3.5),
                        (3,3),
                        (3.5,3.5)]
    new_filename_list = ['bathy_zoom_ilelongue',
                         'bathy_zoom_port',
                         'bathy_zoom_pointepenhir',
                         'bathy_zoom_bassinest']
    
    for newplotter, new_filename, new_figsize in zip(plotter.zoomed_plotters, new_filename_list, new_figsize_list):
        newplotter.figure_filename = new_filename
        newplotter.figure_size = new_figsize
        ptt.p_ok("Defined the plotter arguments:")
        print(newplotter.__dict__)
        newplotter.Plot(processor)
    
    
    
    plotter.figure_filename = 'resolution_complet'
    plotter.figure_size = (7,7)
    plotter.triplot = False
    plotter.pcolor_key = 'resolution'
    plotter.pcolor_units = 'm'
    plotter.pcolor_cmap = 'gist_rainbow_r'
    plotter.pcolor_min = 0
    plotter.pcolor_max = 700
    
    plotter.Plot(processor)
    
    new_figsize_list = [(4,4),
                        (3.5,3.5),
                        (3,3),
                        (3.5,3.5)]
    new_filename_list = ['resolution_zoom_ilelongue',
                         'resolution_zoom_port',
                         'resolution_zoom_pointepenhir',
                         'resolution_zoom_bassinest']
    
    for newplotter, new_filename, new_figsize in zip(plotter.zoomed_plotters, new_filename_list, new_figsize_list):
        newplotter.figure_filename = new_filename
        newplotter.figure_size = new_figsize
        ptt.p_ok("Defined the plotter arguments:")
        print(newplotter.__dict__)
        newplotter.Plot(processor)
        
        
        
    plotter.figure_filename = 'radiusratio_complet'
    plotter.figure_size = (7,7)
    plotter.triplot = False
    plotter.pcolor_key = 'radiusratio'
    plotter.pcolor_min = 0
    plotter.pcolor_max = 2
    plotter.pcolor_units = ''
    plotter.pcolor_cmap = 'Reds'
    plotter.pcolor_min = 1
    plotter.pcolor_max = 2.5
    
    plotter.Plot(processor)
    
    new_figsize_list = [(4,4),
                        (3.5,3.5),
                        (3,3),
                        (3.5,3.5)]
    new_filename_list = ['radiusratio_zoom_ilelongue',
                         'radiusratio_zoom_port',
                         'radiusratio_zoom_pointepenhir',
                         'radiusratio_zoom_bassinest']
    
    for newplotter, new_filename, new_figsize in zip(plotter.zoomed_plotters, new_filename_list, new_figsize_list):
        newplotter.figure_filename = new_filename
        newplotter.figure_size = new_figsize
        ptt.p_ok("Defined the plotter arguments:")
        print(newplotter.__dict__)
        newplotter.Plot(processor)
    
if __name__ == "__main__":
    # exit(main())
    main()
