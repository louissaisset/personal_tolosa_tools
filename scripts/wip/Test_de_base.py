# -*- coding: utf-8 -*-
"""
Éditeur de Spyder

Ceci est un script temporaire.
"""

import sys, os
sys.path.append("/local/home/lsaisset/DATA/Scripts/personal_tolosa_tools/")
import personal_tolosa_tools as ptt

from pathlib import Path

# print("    \033[31mERROR:\033[0m 
# print("       \033[32mOK:\033[0m 
# print("  \033[33mWARNING:\033[0m 


def main():
    
    print("\nBeginning script for comparing two vtk folders using the same grid")
    
    
    
    # Define paths to the VTK folders and output folder
    folder1_path = Path("/local/home/lsaisset/DATA/tests_persos/Comparaison/version_datarmor/res/vtk/")
    if not folder1_path.is_dir():
        print("    \033[31mERROR:\033[0m Cannot proceed without a valid first folder")
    folder1_path = folder1_path.resolve()
    print(f"       \033[32mOK:\033[0m First input folder exists : {folder1_path}")
        


    folder2_path = Path("/local/home/lsaisset/DATA/tests_persos/Comparaison/version_locale/res/vtk/")
    if not folder2_path.is_dir():
        print("    \033[31mERROR:\033[0m Cannot proceed without a valid second folder")
    folder2_path = folder2_path.resolve()
    print(f"       \033[32mOK:\033[0m Second input folder exists : {folder2_path}")
    


    folder_out_path = Path("/local/home/lsaisset/DATA/tests_persos/Comparaison/Figures")
    print(f"       \033[32mOK:\033[0m Defined outfolder : {folder_out_path}")
    
    
    timestep=0
    # if len(sys.argv) > 1:
    #     try:
    #         timestep = int(sys.argv[1])
    #         print(f"       \033[32mOK:\033[0m Asking for timestep : {timestep}")
    #     except ValueError:
    #         print("    \033[31mERROR:\033[0m Cannot proceed without a valid timestep")
    #         return 1
    # else:
    #     print("    \033[31mERROR:\033[0m Cannot proceed without a valid timestep")


    print("\nBeginning the plots creation...")
    
    # Initialize VTKDataReader for both folders
    reader1 = ptt.VTKDataReader(folder1_path)
    reader2 = ptt.VTKDataReader(folder2_path)

    # Read the VTK files for the specified timestep
    data1 = reader1.read_file(timestep)
    data2 = reader2.read_file(timestep)
    print("       \033[32mOK:\033[0m VTK data correctly read")

    # Process the VTK data
    processor1 = ptt.VTKDataProcessor(data1)
    processor2 = ptt.VTKDataProcessor(data2)
    print("       \033[32mOK:\033[0m VTK data correctly processed")


    # Calculate the differences in cell data
    cell_data_diff = processor1.compute_cell_data_differences(processor2)

    if not cell_data_diff:
        print("    \033[31mERROR:\033[0m No common cell data keys found between the two datasets.")
        return 1
    else:
        print("       \033[32mOK:\033[0m Common cell data keys found : {cell_data_diff.keys()}")

    # Configure the data plots
    plotter = ptt.VTKPlotter(folder_out_path)

    # Compute triangulations for plotting
    tripcolor_tri, tricontour_tri = processor1.compute_triangulations()

    # Set plotter configurations
    plotter.figure_title = f"Timestep = {timestep:05d}"
    plotter.figsize = (3, 3)
    plotter.figure_tickfontsize = 5
    plotter.contour_key = ''
    plotter.quiver_u_key = ''
    plotter.quiver_v_key = ''
    plotter.pcolor_max = 1
    plotter.pcolor_min = -plotter.pcolor_max

    dico_units = {'ssh': '10^-7 m',
                  'u': '10^-7 m/s',
                  'v': '10^-7 m/s',
                  'bathy': '10^-7 m'}

    # Plot the differences for each key
    for k in cell_data_diff.keys():
        
        plotter.figure_filename = f"{k}_{timestep:05d}"
        plotter.pcolor_key = k
        plotter.pcolor_units = dico_units[k]
        plotter.plot_triangle_data(tripcolor_tri,
                                   tricontour_tri,
                                   cell_data_diff,
                                   processor1.cell_centers_array)
        print(f"       \033[32mOK:\033[0m Difference plot for key '{k}' generated successfully.")

# Main script
if __name__ == "__main__":
    exit(main())
        

        
        
        