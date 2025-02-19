#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 17 10:03:33 2025

@author: Louis Saisset

Petit script pour faire l'affichage automatique des sorties vtk  de Tolosa-sw
sur maillage Quad
"""


import vtk
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import os, sys

# Main script
if __name__ == "__main__":
    
    # Get current folder
    vtk_directory = os.getcwd()
    
    if len(sys.argv) == 1:
        time = 10
    else :
        time = int(sys.argv[1])
    N = 15

    # List all .vtk files in the directory
    vtk_files = [os.path.join(vtk_directory, f) for f in os.listdir(vtk_directory) if f.endswith(".vtk")]
    vtk_files.sort()
    
    # If there are vtk files in the folder
    if vtk_files.__len__():
        
        vtk_file = vtk_files[time]
        
        reader = vtk.vtkUnstructuredGridReader()
        reader.SetFileName(vtk_files[time])
        reader.ReadAllVectorsOn()
        reader.ReadAllScalarsOn()
        reader.Update()
        data = reader.GetOutput()
        
        points_data_array = np.array(data.GetPoints().GetData())
        
        # num_cel = data.GetNumberOfCells()
        # num_pnt = data.GetNumberOfPoints()
        # One_cell_type = data.GetCell(0).GetCellType() # This is a cell type
        
        # Get the cell data into a usable dictionnary
        Dico = {}
        for i in range(data.GetCellData().GetNumberOfArrays()):
            Dico[data.GetCellData().GetArrayName(i)] = np.array(data.GetCellData().GetArray(i))
        
        # For each cell, compute the cell center position
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
        
        # Check all cell types
        cell_type_list = [data.GetCell(i).GetCellType() for i in range(data.GetNumberOfCells())]
        
        # Procede only if all cell types are Quad
        if cell_type_list == len(cell_type_list)*[9]:
            
            # Put the lists into a simpler np.array because the data are Quad cells
            shape = [np.unique(centerlist[:, 0]).__len__(),
                     np.unique(centerlist[:, 1]).__len__()]
            center_grid_X = centerlist[:, 0].reshape(shape)
            center_grid_Y = centerlist[:, 1].reshape(shape)
            Dico_grid = {k: v.reshape(shape) for k, v in Dico.items()}
            
            
            # Create Figures folder
            fig_folder = os.path.join(vtk_directory, 'Figures')
            if not os.path.exists(fig_folder):
                os.makedirs(fig_folder)
            
            
            fig, ax = plt.subplots(1,1, figsize=[4,4], dpi=300)
            
            # Plot the ssh as a pcolor
            scb1 = ax.pcolor(center_grid_X, center_grid_Y, Dico_grid['ssh'], 
                            vmin=-5, vmax=5, cmap='RdBu', zorder=0)
            
            # Plot the bathy as contour
            scb2 = ax.contour(center_grid_X, center_grid_Y, Dico_grid['bathy'], 
                              levels=[-750, -500, -100, -10], 
                              linestyles=['solid', 'dashed', 
                                          'dashdot', 'dotted'], 
                              linewidths=1,
                              colors='r', zorder=2)
            # Add the labels of the contours
            ax.clabel(scb2) 
            
            # Plot the currents as a quiver
            scb3 = ax.quiver(center_grid_X[::N,::N], center_grid_Y[::N,::N], 
                             Dico_grid['u'][::N,::N], Dico_grid['v'][::N,::N],
                             scale=15, scale_units='width',
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
            
            
        
        
            
            
        
        
        
    
    
    
