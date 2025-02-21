#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 31 14:22:52 2025

@author: llsaisset
"""

import sys, os
sys.path.append("/local/home/lsaisset/DATA/Scripts/personal_tolosa_tools/")
import personal_tolosa_tools as ptt

from pathlib import Path

# print("    \033[31mERROR:\033[0m 
# print("       \033[32mOK:\033[0m 
# print("  \033[33mWARNING:\033[0m 

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
    
    output_dir = (current_path / 'Figures').resolve()
    print(f"       \033[32mOK:\033[0m Defined Figure folder : {output_dir}")
    
    
    
    print("\nBeginning the plotting...")
    
    # Read data
    vtk_data = reader.read_file(0)
    
    # Processdata
    processor = ptt.VTKDataProcessor(vtk_data)
    
    # Configure the data plots
    plotter = ptt.VTKPlotter(output_dir)
    plotter.figure_filename = 'mesh'
    plotter.figsize = (3,3)
    plotter.figure_tickfontsize = 5
    
    plotter.triplot = True
    plotter.pcolor_key = ''
    plotter.contour_key = ''
    plotter.quiver_u_key = ''
    plotter.quiver_v_key = ''
    
    # plotter.figure_xlim = (-100000, -90000)
    # plotter.figure_ylim = (-780000, -775000)
    
    print(f"       \033[32mOK:\033[0m Defined the plotter arguments:")
    print(plotter.__dict__)
    
    
    print(f"       \033[32mOK:\033[0m Creating, plotting and saving")
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
                                   processor.cell_centers_array)
    print(f"       \033[32mOK:\033[0m Figure created and saved")
    
if __name__ == "__main__":
    exit(main())