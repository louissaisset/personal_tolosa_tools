#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 17 10:03:33 2025

@author: Louis Saisset

Petit script pour faire l'affichage automatique des sorties vtk de Tolosa-sw
sur maillage triangulaire
"""


import vtk
import matplotlib as mpl
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os, sys

def Read_data_file(vtk_file):
        
    # Read the vtk file
    reader = vtk.vtkUnstructuredGridReader()
    reader.SetFileName(vtk_files[time])
    reader.ReadAllVectorsOn()
    reader.ReadAllScalarsOn()
    reader.Update()
    
    return(reader.GetOutput())



def Extract_points_cells(data):
    # Get every grid point
    points = data.GetPoints()
    num_pnt = data.GetNumberOfPoints()
    
    # Get every grid cell
    cells = data.GetCells()
    num_cel = data.GetNumberOfCells()
    
    # Check all cell types
    cell_type_list = [data.GetCell(i).GetCellType() for i in range(num_cel)]
    
    
    if cell_type_list == len(cell_type_list)*[9]:
        cell_type = 'all_Quad'
    elif cell_type_list == len(cell_type_list)*[5]:
        cell_type = 'all_Triangle'
    else :
        cell_type = np.unique(cell_type_list)
    
    return(points, num_pnt,
           cells, num_cel,
           cell_type)
    


def Create_Dico_cells(data):

    points, _, _, num_cel, _ = Extract_points_cells(data)
    
    # Get the cell data into a dictionnary of arrays
    Dico = {}
    for i in range(data.GetCellData().GetNumberOfArrays()):
        Dico[data.GetCellData().GetArrayName(i)] = np.array(data.GetCellData().GetArray(i))
    
    # Compute the cell center position
    cell_center_array = np.zeros([num_cel, 3]) # initialize the center list
    for i in range(num_cel): # iterate over the number of cells
        cell = data.GetCell(i) # select a cell
        num_cell_points = cell.GetNumberOfPoints() # Get the number of points composing the cell
        
        # Ponderated sum of point coordinates
        for j in range(num_cell_points):
            point = points.GetPoint(cell.GetPointId(j))
            cell_center_array[i, :] += np.array(point)/num_cell_points
    
    # Get all points coordinates into a np.array
    points_data_array = np.array(points.GetData())
    
    return(Dico, cell_center_array, points_data_array)


def Reshape_Dico_to_grid(cell_center_array, Dico):
    # Put the lists into a simpler np.array because the data are Quad cells
    shape = [np.unique(cell_center_array[:, 0]).__len__(),
             np.unique(cell_center_array[:, 1]).__len__()]
    center_grid_X = cell_center_array[:, 0].reshape(shape)
    center_grid_Y = cell_center_array[:, 1].reshape(shape)
    Dico_grid = {k: v.reshape(shape) for k, v in Dico.items()}
    return(center_grid_X, center_grid_Y, Dico_grid)
            

def Compute_tripcolor_triangulation(data, num_cel, points_data_array):

    # For each cell get the points indices composing the cell
    cell_point_indexes = np.zeros([num_cel, 3])
    for i in range(num_cel):
        cell = data.GetCell(i)
        cell_point_indexes[i, 0] = int(cell.GetPointId(0))
        cell_point_indexes[i, 1] = int(cell.GetPointId(1))
        cell_point_indexes[i, 2] = int(cell.GetPointId(2))

    
    Triangles = mpl.tri.Triangulation(points_data_array[:, 0],
                                      points_data_array[:, 1],
                                      triangles=cell_point_indexes)
    return(Triangles)



def Compute_tricontour_triangulation(data, cell_center_array):
    # Create a specific triangulation
    new_triangulation = mpl.tri.Triangulation(cell_center_array[:, 0],
                                              cell_center_array[:, 1])
    # Create mask
    xtri = cell_center_array[:, 0][new_triangulation.triangles] - np.roll(cell_center_array[:, 0][new_triangulation.triangles], 1, axis=1)
    ytri = cell_center_array[:, 1][new_triangulation.triangles] - np.roll(cell_center_array[:, 1][new_triangulation.triangles], 1, axis=1)
    sizes = np.array([np.array(data.GetCell(i).GetBounds()[0::2]) - 
                      np.array(data.GetCell(i).GetBounds()[1::2]) for i in range(num_cel)])
    max_size = max(np.hypot(sizes[:,0], sizes[:,1], sizes[:,2]))
    new_triangulation.set_mask(np.max(np.sqrt(xtri**2 + ytri**2), axis=1)>max_size)
    return(new_triangulation)



def Plot_quad_ssh_bathy_u_v(center_grid_X, center_grid_Y, Dico_grid,
                            pcolormax, quiverscale):
    
    # Create the figure and axes. Initializes the rendrer 
    fig, ax = plt.subplots(1,1, figsize=[4,4], dpi=300)
    
    # Plot the ssh as a pcolor
    scb1 = ax.pcolor(center_grid_X, center_grid_Y, Dico_grid['ssh'], 
                    vmin=-pcolormax, vmax=pcolormax, cmap='RdBu', zorder=0)
    
    # Plot the bathy as contour
    scb2 = ax.contour(center_grid_X, center_grid_Y, Dico_grid['bathy'], 
                      levels=4, 
                      linestyles=['solid', 'dashed', 
                                  'dashdot', 'dotted'], 
                      linewidths=1,
                      colors='r', zorder=2)
    # Add the labels of the contours
    ax.clabel(scb2) 
    
    # Plot the currents as a quiver
    scb3 = ax.quiver(center_grid_X[::N,::N], center_grid_Y[::N,::N], 
                     Dico_grid['u'][::N,::N], Dico_grid['v'][::N,::N],
                     scale=quiverscale, scale_units='width',
                     zorder=10)
    # Add a quiverkey
    ax.quiverkey(scb3, .85, 1.03, 1, '1m/s', labelpos='E') 
    
    # Make the plot nicer
    ax.set_aspect(1)
    # ax.xaxis.set_major_formatter(formatter)
    # ax.yaxis.set_major_formatter(formatter)
    ax.tick_params(axis='both', direction='in')
    ax.set_xticks(ax.get_xticks()[1:-1], 
                  labels=ax.get_xticklabels()[1:-1])
    ax.set_yticks(ax.get_yticks()[1:-1], 
                  labels=ax.get_yticklabels()[1:-1], 
                  rotation=90, va='center')
    
    # Add a grid
    ax.grid(linestyle='dashed', zorder=1)
    
    # Create colorbar
    cax = fig.add_axes([ax.get_position().x1+0.03, ax.get_position().y0,
                        0.05, ax.get_position().height])
    
    # Make the colorbar nicer
    cax.tick_params(axis='y', direction='in')
    cax.set_yticks(cax.get_yticks(), 
                   labels=cax.get_yticklabels(), 
                   rotation=90, va='center')
    fig.colorbar(scb1, cax=cax)
    
    fig.suptitle(f'Iteration={time:05d}', y=0.93)
    
    # Save the figure
    fig.savefig(os.path.join(fig_folder, f"ssh_bathy_u_v_{time:05d}.png"),
                format='png', bbox_inches='tight')
    plt.close(fig)
    
    
    
def Plot_tri_ssh_bathy_u_v(time, Triangles, new_triangulation, 
                           Dico, cell_center_array, 
                           pcolormax, N, quiverscale):

    
    ########### CREATE FIGURE ###########
    fig, ax = plt.subplots(1,1, figsize=[4,4], dpi=300)
    
    # ax.set_xlim(None, None)
    # ax.set_ylim(-810000, -800000)
    
    
    # Plot the ssh as a pcolor
    scb1 = ax.tripcolor(Triangles, Dico['ssh'], 
                        vmin=-pcolormax, vmax=pcolormax, 
                        cmap='RdBu', zorder=0)
    
    # # Plot the cell vertexes
    # ax.triplot(Triangles, linewidth=0.5, color='lightgrey')
    
    scb2 = ax.tricontour(new_triangulation,
                         Dico['bathy'], 
                         levels=4, 
                         linestyles=['solid', 'dashed', 
                                     'dashdot', 'dotted'], 
                         linewidths=1,
                         colors='r', zorder=2)
    # Add the labels of the contours
    ax.clabel(scb2) 
    
    # Select 1 over N cells
    random_indices = np.random.choice(Dico['bathy'].__len__(), 
                                      size=Dico['bathy'].__len__()//N, 
                                      replace=False)
    scb3 = ax.quiver(cell_center_array[:,0][random_indices],
                     cell_center_array[:,1][random_indices], 
                     Dico['u'][random_indices], 
                     Dico['v'][random_indices],
                     scale=quiverscale, scale_units='width',
                     zorder=10)
    # Add a quiverkey
    ax.quiverkey(scb3, .85, 1.03, 1, '1m/s', labelpos='E') 
    
    # Make the plot nicer
    ax.set_aspect(1)
    ax.tick_params(axis='both', direction='in')
    ax.set_xticks(ax.get_xticks()[1:-1], 
                  labels=ax.get_xticklabels()[1:-1])
    ax.set_yticks(ax.get_yticks()[1:-1], 
                  labels=ax.get_yticklabels()[1:-1], 
                  rotation=90, va='center')
    # ax.xaxis.set_major_formatter(formatter)
    # ax.yaxis.set_major_formatter(formatter)
    
    # Add a grid
    ax.grid(linestyle='dashed', zorder=1)
    
    # Create colorbar
    cax = fig.add_axes([ax.get_position().x1+0.03, ax.get_position().y0,
                        0.05, ax.get_position().height])
    
    # Make the colorbar nicer
    cax.tick_params(axis='y', direction='in')
    cax.set_yticks(cax.get_yticks(), 
                   labels=cax.get_yticklabels(), 
                   rotation=90, va='center')
    fig.colorbar(scb1, cax=cax)
    
    fig.suptitle(f'Iteration={time:05d}', y=0.93)
    
    # Save the figure
    fig.savefig(os.path.join(fig_folder, f"ssh_bathy_u_v_{time:05d}.png"),
                format='png', bbox_inches='tight')
    plt.close(fig)



# Main script
if __name__ == "__main__":
    
    # plt.rcParams["font.family"] = "cmr10"
    # plt.rcParams["font.size"] = 8
    # plt.rcParams['mathtext.fontset'] = "custom"
    # plt.rcParams['mathtext.rm'] = "cmr10"
    # plt.rcParams['mathtext.it'] = "cmr10:italic"
    # plt.rcParams['mathtext.bf'] = "cmr10:bold"
    # plt.rcParams['text.usetex'] = True
    # plt.rcParams['axes.formatter.use_mathtext'] = True
    
    # formatter = mpl.ticker.ScalarFormatter(useMathText=True)
    # formatter.set_scientific(True)
    # formatter.set_powerlimits((-1000, 1000))
    
    # Get current folder
    vtk_directory = os.getcwd()
    
    # Create Figures folder
    fig_folder = os.path.join(vtk_directory, 'Figures')
    if not os.path.exists(fig_folder):
        os.makedirs(fig_folder)
    
    
    
    N = 15
    quiverscale = 100
    pcolormax = 50
    if len(sys.argv) == 1:
        time = 10
    else :
        time = int(sys.argv[1])

    # List all .vtk files in the directory
    vtk_files = [os.path.join(vtk_directory, f) for f in os.listdir(vtk_directory) if f.endswith(".vtk")]
    vtk_files.sort()
    
    # If there are vtk files in the folder
    if vtk_files.__len__():
        
        # Select one time step
        vtk_file = vtk_files[time]
        
        # Read the vtk file
        data = Read_data_file(vtk_file)
        
        # Get the points and cells in the vtk objects format
        points, num_pnt, cells, num_cel, cell_type = Extract_points_cells(data)
                
        # Get the cell data and cell center positions in a usable format
        Dico, cell_center_array, points_data_array = Create_Dico_cells(data)
        
        # If all cell types are Quad, no need to triangulate, reshape and pcolor
        if cell_type == 'all_Quad':
            
            # Put the lists into a simpler np.array because the data are Quad cells
            center_grid_X, center_grid_Y, Dico_grid = Reshape_Dico_to_grid(cell_center_array, Dico)
            
            Plot_quad_ssh_bathy_u_v(center_grid_X, center_grid_Y, Dico_grid,
                                        pcolormax, quiverscale)
        
        
        
        # If all cell types are triangular, triangulate and use tripcolor
        elif cell_type == 'all_Triangle':
            
            
            Triangles = Compute_tripcolor_triangulation(data, num_cel, points_data_array)
            
            new_triangulation = Compute_tricontour_triangulation(data, cell_center_array)
            
            Plot_tri_ssh_bathy_u_v(time, Triangles, new_triangulation, 
                                       Dico, cell_center_array, 
                                       pcolormax, N, quiverscale)
