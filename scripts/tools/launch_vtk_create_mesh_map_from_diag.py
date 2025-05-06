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
mpl.use('agg')

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

def main():
    print("\nBeginning script for plotting the grid info from the diag.vtk file...")
    
    # Initialize parameters
    current_path = Path.cwd()
    ptt.p_ok(f"Launched from : {current_path}")
    
    # Initialize classes
    reader = ptt.VTKDataReader(current_path)
    # vtk_file = [f for f in reader._get_vtk_files() if f.endswith("_diag.vtk")][0]
    # ptt.p_ok(f"Asking for file : {vtk_file}")
    # if not vtk_file:
    #     ptt.p_error("Cannot proceed without a valid '_diag.vtk' file")
    #     return 1
    
    output_dir = (current_path / f'Figures_{current_path.name}').resolve()
    ptt.p_ok(f"Defined Figure folder : {output_dir}")
    
    
    
    print("\nBeginning the plotting...")
    
    # Read data in first encountered vtk file
    vtk_data = reader.read_file(reader.vtk_files[0])
    
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
    exit(main())
