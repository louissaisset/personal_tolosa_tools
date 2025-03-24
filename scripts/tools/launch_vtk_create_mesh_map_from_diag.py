#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 31 14:22:52 2025

@author: llsaisset
"""

import sys, os
sys.path.append("~/DATA/Scripts/personal_tolosa_tools/")
import personal_tolosa_tools as ptt

from pathlib import Path

import vtk
import numpy as np




def main():
    print("\nBeginning script for plotting the ith timestep in the VTK results folder...")
    
    # Initialize parameters
    current_path = Path.cwd()
    print(f"       \033[32mOK:\033[0m Launched from : {current_path}")
    
    # Initialize classes
    reader = ptt.VTKDataReader(current_path)
    vtk_file = [f for f in reader._get_vtk_files() if f.endswith("_diag.vtk")][0]
    print(f"       \033[32mOK:\033[0m Asking for file : {vtk_file}")
    if not vtk_file:
        print("    \033[31mERROR:\033[0m Cannot proceed without a valid '_diag.vtk' file")
        return 1
    
    output_dir = (current_path / f'Figures_{current_path.name}').resolve()
    print(f"       \033[32mOK:\033[0m Defined Figure folder : {output_dir}")
    
    
    
    print("\nBeginning the plotting...")
    
    # Read data
    vtk_data = reader.read_file(0)
    
    # Processdata
    processor = ptt.VTKDataProcessor(vtk_data)    
    processor.cell_data['radiusratio'] = processor.compute_radiusratio()
    
    # Configure the data plots
    plotter = ptt.VTKPlotter(output_dir)
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
    
    new_figsize_list = [(5,5),
                        (4,4),
                        (4,4),
                        (4,4)]
    new_filename_list = ['mesh_zoom_ilelongue',
                         'mesh_zoom_port',
                         'mesh_zoom_pointepenhir',
                         'mesh_zoom_bassinest']
    
    
    
    
    plotter.figure_filename = 'mesh_complet'
    plotter.triplot = True
    print("       \033[32mOK:\033[0m Defined the plotter arguments:")
    print(plotter.__dict__)
    
    plotter.Plot(processor)
    
    for newplotter, new_filename, new_figsize in zip(plotter.zoomed_plotters, new_filename_list, new_figsize_list):
        newplotter.figure_filename = new_filename
        newplotter.figure_size = new_figsize
        print("       \033[32mOK:\033[0m Defined the plotter arguments:")
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
    print("       \033[32mOK:\033[0m Defined the plotter arguments:")
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
        print("       \033[32mOK:\033[0m Defined the plotter arguments:")
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
        print("       \033[32mOK:\033[0m Defined the plotter arguments:")
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
        print("       \033[32mOK:\033[0m Defined the plotter arguments:")
        print(newplotter.__dict__)
        newplotter.Plot(processor)
    
if __name__ == "__main__":
    exit(main())
