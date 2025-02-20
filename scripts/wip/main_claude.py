#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 31 14:22:52 2025

@author: llsaisset
"""

import sys, os

sys.path.append("/local/home/lsaisset/DATA/Scripts/personal_tolosa_tools/")
import personal_tolosa_tools as ptt


if __name__ == "__main__":
    
    # Initialize parameters
    vtk_directory = os.getcwd()
    # vtk_directory =  "/local/home/lsaisset/DATA/tests_persos/Comparaison/version_locale/res/vtk"
    
    output_dir = os.path.join(vtk_directory, 'Figures')
    
    timestep = int(sys.argv[1])
    # timestep = int("10")
    
    # Initialize classes
    reader = ptt.VTKDataReader(vtk_directory)
    if not reader.vtk_files:
        print("No VTK files found in directory")
    else :
        # Read data
        vtk_data = reader.read_file(timestep)
        
        # Processdata
        processor = ptt.VTKDataProcessor(vtk_data)
        
        # Configure the data plots
        plotter = ptt.VTKPlotter(output_dir)
        plotter.figure_title = f"Timestep = {timestep:05d}"
        plotter.figure_filename = plotter.auto_filename()+f"_{timestep:05d}"
        # plotter.timestep = timestep
        plotter.triplot = True
        plotter.figsize = (3,3)
        plotter.figure_tickfontsize = 5
        plotter.contour_fontsize = 5
        plotter.contour_levels = 3
        plotter.quiver_lengthkey = 1
        plotter.quiver_spacing = 20
        plotter.quiver_scale = 15
        # plotter.figure_xlim = (-100000, -90000)
        # plotter.figure_ylim = (-780000, -775000)
        plotter.contour_linewidths = 0.2
        
        # plotter.pcolor_max = 0.1
        # plotter.pcolor_min = -plotter.pcolor_max
        
        # Plot based on cell type
        if processor.cell_type == 'all_Quad':
            center_grid_X, center_grid_Y, cell_data_grid = processor.reshape_to_grid()
            plotter.plot_quad_data(center_grid_X, 
                                   center_grid_Y, 
                                   cell_data_grid)
        elif processor.cell_type == 'all_Triangle':
            tripcolor_tri, tricontour_tri = processor.compute_triangulations()
            plotter.plot_triangle_data(tripcolor_tri, 
                                       tricontour_tri,
                                       processor.cell_data, 
                                       processor.cell_centers)
