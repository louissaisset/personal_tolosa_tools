#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 21 13:56:34 2025

@author: llsaisset
"""


import sys, os
sys.path.append("/local/home/lsaisset/DATA/Scripts/personal_tolosa_tools/")
import personal_tolosa_tools as ptt

import numpy as np

import matplotlib.path as mpltPath
from pathlib import Path

import vtk

def _get_boundary_edges_all(data):
    # Create a geometry filter to convert unstructured grid to polydata
    geometry_filter = vtk.vtkGeometryFilter()
    geometry_filter.SetInputData(data)
    geometry_filter.Update()
    
    # Create a feature edges filter with all types of edges enabled
    feature_edges = vtk.vtkFeatureEdges()
    feature_edges.SetInputConnection(geometry_filter.GetOutputPort())
    feature_edges.BoundaryEdgesOn()
    feature_edges.FeatureEdgesOn()
    feature_edges.NonManifoldEdgesOn()
    feature_edges.ManifoldEdgesOn()
    
    # Set feature angle for feature edge detection
    feature_edges.Update()
    
    boundary_edges_all = feature_edges.GetOutput()
    
    return boundary_edges_all
    
def _get_boundary_points_array_all(boundary_edges_all):
    boundary_points = np.array(boundary_edges_all.GetPoints().GetData())
    return(boundary_points)

def _get_boundary_edges_connectors(boundary_edges_all):
    list_edge_point_ids = []
    for i in range(boundary_edges_all.GetNumberOfCells()):
        cell = boundary_edges_all.GetCell(i)
        point_ids = [cell.GetPointId(j) for j in range(cell.GetNumberOfPoints())]
        list_edge_point_ids.append(point_ids)
    return list_edge_point_ids
    

def calculate_area(points):
    
    # Calculate area using the shoelace formula
    x = points[:, 0]
    y = points[:, 1]
    
    # Roll the coordinates to get pairs for the formula
    x_next = np.roll(x, -1)
    y_next = np.roll(y, -1)
    
    # Shoelace formula
    area = 0.5 * np.abs(np.sum(x * y_next - x_next * y))
    return area

def _get_boundary_points_array_ext(points, list_edge_point_ids):
    """
    Order points along boundaries and return only the boundary with the largest area.
    
    Parameters:
    points: numpy.ndarray
        Array of point coordinates
    list_edge_point_ids: numpy.ndarray
        Array of edge vertex indices
        
    Returns:
    numpy.ndarray
        Ordered array of points for the boundary with largest area
    """
    # Create adjacency list representation
    adj_list = {}
    for edge in list_edge_point_ids:
        if edge[0] not in adj_list:
            adj_list[edge[0]] = []
        if edge[1] not in adj_list:
            adj_list[edge[1]] = []
        adj_list[edge[0]].append(edge[1])
        adj_list[edge[1]].append(edge[0])
    
    # Find all separate boundary loops
    boundaries_id = []
    unvisited = set(adj_list.keys())
    
    
    while unvisited:
        # Start a new boundary
        start_point = next(iter(unvisited))
        current = start_point
        boundary = []
        boundary_set = set()
        
        while True:
            boundary.append(current)
            boundary_set.add(current)
            unvisited.remove(current)
            
            # Find next unvisited neighbor
            next_point = None
            for neighbor in adj_list[current]:
                if neighbor not in boundary_set:
                    next_point = neighbor
                    break
            
            if next_point is None or next_point == start_point:
                break
                
            current = next_point
        
        # Only add boundaries_id with at least 3 points (needed for area calculation)
        if len(boundary) >= 3:
            boundaries_id.append(boundary)
    
    if not boundaries_id:
        return np.array([])
    
    # Calculate area for each boundary and find the largest
    max_area = 0
    largest_boundary = None
    
    boundaries_points_list = [points[b] for b in boundaries_id]
    area_list = [calculate_area(b_point) for b_point in boundaries_points_list]
    
    np.argmax(area_list)
    
    max_area = max(area_list)
    largest_boundary = boundaries_points_list[area_list.index(max_area)]
    
    print(f"Found {len(boundaries_id)} closed boundaries_id")
    print(f"Largest boundary area: {max_area:.2f}")
    
    return boundaries_points_list, largest_boundary
    

def create_mask_path(X, Y, path):
    boundary_path = mpltPath.Path(largest_boundary[:,0:2])
    points = np.column_stack((X.ravel(), Y.ravel()))
    mask = boundary_path.contains_points(points).reshape(X.shape)
    return(mask)

# Define paths to the VTK folders and output folder
# folder_path = Path("/local/home/lsaisset/DATA/tests_persos/Comparaison/version_datarmor/res/vtk/")
folder_path = Path("/local/home/lsaisset/DATA/Configs_Brest/Tests_versions_meshtool/BC_5_constraint_all_algo_6_smoothing_00500m")


timestep = 0
reader = ptt.VTKDataReader(folder_path)
data = reader.read_file(timestep)
processor = ptt.VTKDataProcessor(data)



xmin, xmax, ymin, ymax = processor.get_data_lims()
xreso = 100
yreso = 50

x = np.arange(xmin, xmax, xreso)
y = np.arange(ymin, ymax, yreso)

X, Y = np.meshgrid(x, y)

boundary_edges_all = _get_boundary_edges_all(data)
boundary_points = _get_boundary_points_array_all(boundary_edges_all)
edge_list = _get_boundary_edges_connectors(boundary_edges_all)
boundaries, largest_boundary = _get_boundary_points_array_ext(boundary_points, edge_list)
mask = create_mask_path(X, Y, largest_boundary)

tripcolor_tri, _ = processor.compute_triangulations()


import matplotlib.pyplot as plt
plt.figure()
# plt.tripcolor(tripcolor_tri, processor.cell_data['ssh'])
plt.tripcolor(tripcolor_tri, processor.cell_data['resolution'])
plt.plot(processor.edgepoints_array[:,0],
         processor.edgepoints_array[:,1],
         '+r')

plt.plot(largest_boundary[:,0], 
         largest_boundary[:,1], '-b')

# plt.pcolormesh(X, Y, mask)

plt.show()






