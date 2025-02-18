#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 31 14:22:52 2025

@author: llsaisset
"""

import sys, os


if __name__ == "__main__":
    
    sys.path.append("/local/home/lsaisset/DATA/Scripts")
    from vtk_plotter_lib import VTKDataReader, VTKDataProcessor, VTKPlotter
    
    
    # Initialize parameters
    vtk_directory = os.getcwd()
    output_dir = os.path.join(vtk_directory, 'Figures')
    timestep = int(sys.argv[1])
    
    # Initialize classes
    reader = VTKDataReader(vtk_directory)
    if not reader.vtk_files:
        print("No VTK files found in directory")
    else :
        # Read and process data
        vtk_data = reader.read_file(timestep)
        processor = VTKDataProcessor(vtk_data)
        plotter = VTKPlotter(output_dir)
        plotter.timestep = timestep
        plotter.figsize = (3,3)
        plotter.figure_tickfontsize = 6
        plotter.contour_fontsize = 5
        plotter.contour_levels = 3
        plotter.quiver_lengthkey = 10
        plotter.quiver_spacing = 100
        plotter.quiver_scale = 150
        plotter.figure_xlim = (0, 10000)
        plotter.figure_ylim = (-110000, -100000)
        plotter.contour_linewidths = 0.2
        
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
