# -*- coding: utf-8 -*-
"""
Éditeur de Spyder

Ceci est un script temporaire.
"""

import vtk

from vtk.util import numpy_support as VN

import matplotlib.pyplot as plt
import numpy as np
import os

# # Function to read VTK file and extract point data
# def read_vtk_file(file_path):
#     reader = vtk.vtkUnstructuredGridReader()
#     reader.SetFileName(file_path)
#     reader.Update()
#     data = reader.GetOutput()
    
#     points = data.GetPoints()
#     point_data = data.GetPointData()
    
#     # Extract coordinates and scalar values
#     coords = np.array([points.GetPoint(i) for i in range(points.GetNumberOfPoints())])
    
#     # Assuming scalar values are in the first array of point data
#     scalars = None
#     if point_data.GetNumberOfArrays() > 0:
#         scalars_array = point_data.GetArray(0)
#         scalars = np.array([scalars_array.GetValue(i) for i in range(scalars_array.GetNumberOfTuples())])

#     return coords, scalars

# # Function to plot data
# def plot_data(coords, scalars, output_file=None):
#     if scalars is not None:
#         plt.figure(figsize=(10, 6))
#         scatter = plt.scatter(coords[:, 0], coords[:, 1], c=scalars, cmap='viridis')
#         plt.colorbar(scatter, label='Scalar Value')
#         plt.xlabel('X Coordinate')
#         plt.ylabel('Y Coordinate')
#         plt.title('VTK Scalar Field')
#         if output_file:
#             plt.savefig(output_file)
#         else:
#             plt.show()
#     else:
#         print("No scalar data available to plot.")

# Main script
if __name__ == "__main__":
    # Replace with the directory containing your VTK files
    
    vtk_directory = "/local/home/lsaisset/DATA/tests_persos/Test_base/V5/res/vtk"

    # List all .vtk files in the directory
    vtk_files = [os.path.join(vtk_directory, f) for f in os.listdir(vtk_directory) if f.endswith(".vtk")]

    # Sort files (optional, for chronological order if files are numbered)
    vtk_files.sort()
    
    # for time in range(len(vtk_files)):
    for time in range(1):
        
        vtk_file = vtk_files[time]
        
        reader = vtk.vtkUnstructuredGridReader()
        reader.SetFileName(vtk_files[time])
        reader.ReadAllVectorsOn()
        reader.ReadAllScalarsOn()
        reader.Update()
        data = reader.GetOutput()
        
        num_cel = data.GetNumberOfCells()
        num_pnt = data.GetNumberOfPoints()
        One_cell_type = data.GetCell(0).GetCellType() # This is a cell type
        
        
        points_data_array = np.array(data.GetPoints().GetData())
        
        D0_name = data.GetCellData().GetArrayName(0)
        D0_data = np.array(data.GetCellData().GetArray(0))
        
        D1_name = data.GetCellData().GetArrayName(1)
        D1_data = np.array(data.GetCellData().GetArray(1))
        
        D2_name = data.GetCellData().GetArrayName(2)
        D2_data = np.array(data.GetCellData().GetArray(2))
        
        Dico ={}
        for i in range(data.GetCellData().GetNumberOfArrays()):
            Dico[data.GetCellData().GetArrayName(i)] = np.array(data.GetCellData().GetArray(i))
        
        centerlist = []
        for i in range(data.GetNumberOfCells()):
            cell = data.GetCell(i)
            num_points = cell.GetNumberOfPoints()
            
            center = np.array([0., 0., 0.])
            for j in range(num_points):
                point_id = cell.GetPointId(j)
                point = data.GetPoints().GetPoint(point_id)
                
                center += np.array(point)/num_points
                
            
            centerlist += [center]
        centerlist = np.array(centerlist)
            
        
        fig, ax = plt.subplots(1,1)
        ax.scatter(centerlist[:,0],centerlist[:,1], c=Dico['ssh'], vmin=-5, vmax=5)
        ax.set_aspect(1)
        
        
        fig, ax = plt.subplots(1,1)
        ax.quiver(centerlist[:,0], centerlist[:,1], Dico['u'], Dico['v'])
        ax.set_aspect(1)
        
        
        fig, ax = plt.subplots(1,1)
        ax.tripcolor(centerlist[:,0],centerlist[:,1], D, vmin=-5, vmax=5)
        ax.set_aspect(1)
        
        
    
    
    
    
    
    # coords, scalars = read_vtk_file(vtk_files[0])
    
    
    
    
    # Iterate over VTK files, read and plot data
    # for idx, vtk_file in enumerate(vtk_files[:100]):
    #     print(f"Processing file {idx + 1}/{len(vtk_files)}: {vtk_file}")
    #     coords, scalars = read_vtk_file(vtk_file)
        
    #     # Save the plot for each file
    #     output_plot = f"vtk_plot_{idx + 1}.png"
    #     plot_data(coords, scalars, output_file=output_plot)
    #     print(f"Plot saved: {output_plot}")


    # for i in range(10):
        
    #     plt.figure()
    #     plt.plot(np.arange(10), 2.*np.arange(10))
    #     plt.show()