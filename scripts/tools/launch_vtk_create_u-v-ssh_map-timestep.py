#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 31 14:22:52 2025

@author: llsaisset
"""

import sys, os
sys.path.append(os.path.expanduser("~/DATA/Scripts/personal_tolosa_tools/"))
import personal_tolosa_tools as ptt

from pathlib import Path

def main():
    print("\nBeginning script for plotting the ith timestep in the VTK results folder...")
    
    # Initialize parameters
    current_path = Path.cwd()
    ptt.p_ok(f"Launched from : {current_path}")
    
    if len(sys.argv) > 1:
        try:
            timestep = int(sys.argv[1])
            ptt.p_ok(f"Asking for timestep : {timestep}")
        except ValueError:
            ptt.p_error("Cannot proceed without a valid timestep")
    else:
        ptt.p_error("Cannot proceed without a valid timestep")
    
    vtk_file = (current_path / "res" / "vtk" / f"result_{timestep:06d}.vtk").resolve()
    vtk_folder = vtk_file.parent
    ptt.p_ok(f"Asking for file : {vtk_file}")
    if vtk_file.is_file():
        ptt.p_ok(f"Found VTK file: {vtk_file}")
    else:
        ptt.p_error("Cannot proceed without a valid VTK file")
        return 1
    
    output_dir = (current_path / 'Figures').resolve()
    ptt.p_ok(f"Defined Figure folder : {output_dir}")
    
    print("\nBeginning the plotting...")
    # Initialize classes
    reader = ptt.VTKDataReader(vtk_folder)
    
    # Read data
    vtk_data = reader.read_file(timestep)
    
    # Processdata
    processor = ptt.VTKDataProcessor(vtk_data)
    
    # Configure the data plots
    plotter = ptt.VTKPlotter(output_dir)
    plotter.figure_title = f"Timestep = {timestep:05d}"
    plotter.figure_filename = plotter.auto_filename()+f"_{timestep:05d}"
    plotter.figsize = (3,3)
    plotter.figure_tickfontsize = 5
    plotter.contour_fontsize = 5
    plotter.contour_levels = 3
    plotter.quiver_lengthkey = 1
    plotter.quiver_spacing = 20
    plotter.quiver_scale = 15
    plotter.contour_linewidths = 0.2
    
    # plotter.figure_xlim = (-100000, -90000)
    # plotter.figure_ylim = (-780000, -775000)
    # plotter.pcolor_max = 0.1
    # plotter.pcolor_min = -plotter.pcolor_max
    
    ptt.p_ok("Defined the plotter arguments:")
    print(plotter.__dict__)
    
    
    ptt.p_ok("Creating, plotting and saving")
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
    ptt.p_ok("Figure created and saved")
    
if __name__ == "__main__":
    exit(main())
