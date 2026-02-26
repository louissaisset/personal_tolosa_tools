#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VTK Data Plotting Library
Provides classes for reading, processing, and plotting VTK data
"""
from .common import p_ok, p_error, p_warning

import os, sys
import typing
from copy import deepcopy, copy


import vtk
import numpy as np
from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from shapely import LineString, Polygon, polygonize
from shapely.vectorized import contains

import matplotlib as mpl
import matplotlib.pyplot as plt

# from matplotlib.path import Path
# import time




class VTKDataProcessor:
    """
    Processes VTK data for plotting.
    
    Attributes:
        data (vtk.vtkUnstructuredGrid): Input VTK data
        cell_type (str): Type of cells in the grid
    """
    def __init__(self, data: vtk.vtkUnstructuredGrid):
        """
        Initialize VTKDataProcessor.
        
        Args:
            data (vtk.vtkUnstructuredGrid): Input VTK data
        """
        # The vtk data structure
        self.data = data                                                    # output of the reader for a file
        
        self.points, self.num_points = self._extract_points()               # the vtk object of the points and the int of the number of points
        self.points_array = self._create_points_array()                     # a numpy array of the points position
        
        self.cells, self.num_cells= self._extract_cells()                   # the vtk object of the cells and the int of the number of cells
        self.cell_centers_array = self._create_cell_center_array()          # a numpy array of the cell center position
        self.cell_type = self._extract_celltype()                           # a str flag used in the plotter
        self.cell_data = self._create_cell_data_dict()                      # a dict containing the cell data, in cell order
        
        self.boundary_edges = self._extract_boundary_edges()                # the vtk object of the edges constructing the boundaries of the grid
        self.edgepoints, self.num_edgepoints = self._extract_edgepoints()   # the vtk object of the points on the boundaries and the int of the number of such points
        self.edgepoints_array = self._create_edgepoints_array()             # a numpy array of the boundary points position 
        
        self.boundary_polygon_list = self._create_boundary_polygon_list()
        self.boundary_polygon = self._create_boundary_polygon()
        
        
        self.xmin, self.xmax, self.ymin, self.ymax = self._extract_data_lims()   # the min/max of the points coordinates
        
        #####################  OLD TESTS  #####################
        # self.connect_map_all = self._compute_adjacency_boundary_points_complete() 
        # self.connect_map_junction_points = self._compute_adjacency_boundary_points_junction_points()
        # self.connect_map_segment_points = self._compute_adjacency_boundary_points_segment_points()
        # self.connect_map_other_points = self._compute_adjacency_boundary_points_other_points()
        # self.segment_list, self.isolated_loops = self._compute_segments_and_isolated_loops_boundary_points()
        # self.segment_to_points, self.point_to_segments, self.segment_adjacency, self.point_adjacency = self._compute_links_segments_points()
        
        
        
    def _extract_points(self) -> typing.Tuple:
        """
        Extract points and point number from VTK data.
        
        Returns:
            Tuple containing points, number of points
        """
        points = self.data.GetPoints()
        num_points = self.data.GetNumberOfPoints()
        
        return points, num_points
    
    def _extract_cells(self) -> typing.Tuple:
        """
        Extract cells and number of cells from VTK data.
        
        Returns:
            Tuple containing points, number of points
        """
        cells = self.data.GetCells()
        num_cells = self.data.GetNumberOfCells()
        
        return cells, num_cells
    
    def _extract_boundary_edges(self):
        """
        Extract all boundary edges from the VTK data.

        Returns:
            vtkPolyData: Boundary edges
        """
        # Create a geometry filter to convert unstructured grid to polydata
        geometry_filter = vtk.vtkGeometryFilter()
        geometry_filter.SetInputData(self.data)
        geometry_filter.Update()

        # Create a feature edges filter with all types of edges enabled
        feature_edges = vtk.vtkFeatureEdges()
        feature_edges.SetInputConnection(geometry_filter.GetOutputPort())
        feature_edges.BoundaryEdgesOn()
        # feature_edges.FeatureEdgesOn()
        # feature_edges.NonManifoldEdgesOn()
        # feature_edges.ManifoldEdgesOn()
        feature_edges.FeatureEdgesOff()
        feature_edges.ManifoldEdgesOff()
        feature_edges.NonManifoldEdgesOff()
        
        # Set feature angle for feature edge detection
        feature_edges.Update()

        return feature_edges.GetOutput()
    
    def _extract_edgepoints(self) -> typing.Tuple:
        """
        Extract points and point number from the edge of VTK data.
        
        Returns:
            Tuple containing edgepoints, number of edgepoints
        """
        
        edgepoints = self.boundary_edges.GetPoints()
        num_edgepoints = self.boundary_edges.GetNumberOfPoints()
        
        return edgepoints, num_edgepoints
    
    def _extract_celltype(self) -> str:
        """
        Extract the cell type of cells from VTK data.
        
        Returns:
            'all_Quad' if all cells are of type 9 and 'all_Triangle' if all 
            cells are of type 5.
        """
        cell_types = [self.data.GetCell(i).GetCellType() for i in range(self.num_cells)]
        
        if all(ct == 9 for ct in cell_types):
            cell_type = 'all_Quad'
        elif all(ct == 5 for ct in cell_types):
            cell_type = 'all_Triangle'
        else:
            cell_type = np.unique(cell_types)
            
        return cell_type
        
    def _extract_data_lims(self) -> typing.Tuple:
        """
        Returns the X and Y limits of the grid
        """
        xmin = np.nanmin(self.points_array[:, 0])
        xmax = np.nanmax(self.points_array[:, 0])
        ymin = np.nanmin(self.points_array[:, 1])
        ymax = np.nanmax(self.points_array[:, 1])
        
        return (xmin, xmax, ymin, ymax)
    
    def _create_cell_data_dict(self) -> dict:
        """
        Create dictionary of cell data.
        
        Returns:
            Dictionary containing the cell data entries and values in cell order
        """
        # Create dictionary of cell data
        cell_data = {}
        for i in range(self.data.GetCellData().GetNumberOfArrays()):
            name = self.data.GetCellData().GetArrayName(i)
            cell_data[name] = np.array(self.data.GetCellData().GetArray(i))
        
        return cell_data
    
    def _create_cell_center_array(self) -> np.array:
        """
        Returns:
            Numpy array containing the cell center coordinates
        """
        # Compute cell centers
        cell_centers_array = np.zeros([self.num_cells, 3])
        for i in range(self.num_cells):
            cell = self.data.GetCell(i)
            num_cell_points = cell.GetNumberOfPoints()
            for j in range(num_cell_points):
                point = self.points.GetPoint(cell.GetPointId(j))
                cell_centers_array[i, :] += np.array(point)/num_cell_points
        
        return cell_centers_array
    
    def _create_points_array(self) -> np.array:
        """
        Returns:
            Numpy array containing points coordinates
        """
        
        return np.array(self.points.GetData())

    def _create_edgepoints_array(self) -> np.array:
        """
        Returns:
            Numpy array containing edgepoints coordinates
        """
        
        return np.array(self.edgepoints.GetData())
    
    def _create_boundary_polygon_list(self) -> list:
        
        list_coords_boundary_edges = [np.array(self.boundary_edges.GetCell(i).GetPoints().GetData()) for i in range(self.boundary_edges.GetNumberOfCells())]
        list_LineString_test = [LineString(L) for L in list_coords_boundary_edges]
        boundary_polygon_list = [g for g in polygonize(list_LineString_test).geoms]
        
        return(boundary_polygon_list)
    
    def _create_boundary_polygon(self) -> Polygon:
        
        boundary_polygon_list = self.boundary_polygon_list
        
        all_polygons_area = [g.area for g in boundary_polygon_list]
        biggest_polygon = boundary_polygon_list[all_polygons_area.index(max(all_polygons_area))]
        other_polygons = [boundary_polygon_list[i] for i in range(len(boundary_polygon_list)) if i != all_polygons_area.index(max(all_polygons_area))]

        boundary_polygon = Polygon(shell=biggest_polygon, holes=other_polygons)
        
        return(boundary_polygon)
    
    def reshape_to_grid(self) -> tuple:
        """
        Reshape data to grid format for quad cells.
        
        Returns:
            Tuple of grid X coordinates, grid Y coordinates, and reshaped cell data
        """
        shape = [len(np.unique(self.cell_centers_array[:, 0])),
                len(np.unique(self.cell_centers_array[:, 1]))]
        center_grid_X = self.cell_centers_array[:, 0].reshape(shape)
        center_grid_Y = self.cell_centers_array[:, 1].reshape(shape)
        cell_data_grid = {k: v.reshape(shape) for k, v in self.cell_data.items()}
        return center_grid_X, center_grid_Y, cell_data_grid
    
    def compute_triangulations(self) -> tuple:
        """
        Compute triangulations for triangle cells.
        
        Returns:
            Tuple of tripcolor and tricontour triangulations
        """
        # Compute tripcolor triangulation
        cell_point_indexes = np.zeros([self.num_cells, 3])
        for i in range(self.num_cells):
            cell = self.data.GetCell(i)
            cell_point_indexes[i] = [cell.GetPointId(j) for j in range(3)]
            
        tripcolor_triangulation = mpl.tri.Triangulation(
            self.points_array[:, 0],
            self.points_array[:, 1],
            triangles=cell_point_indexes)
        
        # Compute tricontour triangulation
        tricontour_triangulation = mpl.tri.Triangulation(
            self.cell_centers_array[:, 0],
            self.cell_centers_array[:, 1])
        
        # Create mask
        xtri = self.cell_centers_array[:, 0][tricontour_triangulation.triangles] - \
               np.roll(self.cell_centers_array[:, 0][tricontour_triangulation.triangles], 1, axis=1)
        ytri = self.cell_centers_array[:, 1][tricontour_triangulation.triangles] - \
               np.roll(self.cell_centers_array[:, 1][tricontour_triangulation.triangles], 1, axis=1)
        sizes = np.array([np.array(self.data.GetCell(i).GetBounds()[0::2]) - 
                         np.array(self.data.GetCell(i).GetBounds()[1::2]) 
                         for i in range(self.num_cells)])
        max_size = max(np.hypot(sizes[:,0], sizes[:,1], sizes[:,2]))
        tricontour_triangulation.set_mask(np.max(np.sqrt(xtri**2 + ytri**2), axis=1) > max_size)
        
        return tripcolor_triangulation, tricontour_triangulation
    
    def compute_radiusratio(self) -> np.array:
        
        mesh_filter = vtk.vtkMeshQuality()
        mesh_filter.SetInputData(self.data)
        mesh_filter.SetTriangleQualityMeasureToAspectRatio()
        mesh_filter.Update()
        
        # Récupérer les résultats
        quality_array = mesh_filter.GetOutput().GetCellData().GetArray("Quality")
        
        # Créer un tableau numpy pour stocker les aires
        new_data = np.zeros(self.num_cells)
        
        # Remplir le tableau avec les aires
        for i in range(self.num_cells):
            new_data[i] = quality_array.GetValue(i)
        
        return new_data
    
    def compute_cell_data_differences(self, other_processor) -> dict:
        
        # Check if the cell centers are the same in both datasets
        N_equal_cells = (self.cell_centers_array == other_processor.cell_centers_array).sum()
        if N_equal_cells != 3*self.num_cells:
            print("    \033[31mERROR:\033[0m The cell centers do not match between the two datasets.")
            return {}
    
        # Extract cell data
        cell_data1 = self.cell_data
        cell_data2 = other_processor.cell_data
    
        # Calculate the differences in cell data
        cell_data_diff = {k: (cell_data1[k] - cell_data2[k]) for k in cell_data1.keys() if k in cell_data2.keys()}
        
        return cell_data_diff
        

    def compute_mask_grid(self, X, Y) -> np.array:
        """
        Create masks for points 'inside' and 'outside' given boundary paths using vectorized operations.
        Handles both single paths and lists of paths.

        Args:
            X (np.ndarray): X coordinates of the grid
            Y (np.ndarray): Y coordinates of the grid

        Returns:
            complete_mask: a np.array containing the gridded mask of the points inside of self.boundary_polygon
        """
        
        complete_mask = contains(self.boundary_polygon, X.ravel(), Y.ravel()).reshape(X.shape)
        
        return complete_mask
    
    def compute_interpolation_masked_grid(self, x, y, z, X, Y, method='linear'):
        """
        Interpolate scattered data onto a grid, optionally using a mask.
        
        Args:
            x (np.ndarray): x coordinates of scattered points
            y (np.ndarray): y coordinates of scattered points
            z (np.ndarray): values at scattered points
            X (np.ndarray): X coordinates grid
            Y (np.ndarray): Y coordinates grid
            mask (np.ndarray, optional): Boolean mask (True for valid points). If None, interpolates entire grid
            method (str): 'linear' or 'nearest'
            
        Returns:
            np.ndarray: Interpolated values on the grid
        """
        
        # Original data points
        points = np.column_stack((x, y))
        
        # Choose interpolator
        if method == 'linear':
            interpolator = LinearNDInterpolator(points, z)
        elif method == 'nearest':
            interpolator = NearestNDInterpolator(points, z)
        else:
            print("    \033[31mERROR:\033[0m Valid interpolation methods are 'linear' or 'nearest'")
            return np.array([])
        
        mask = self.compute_mask_grid(X, Y)
        
        # Initialize result array
        result = np.full(X.shape, np.nan)
        
        # Points where we need to interpolate (masked points)
        points_to_interpolate = np.column_stack((X[mask].ravel(), Y[mask].ravel()))
        
        # Interpolate only at masked points
        result[mask] = interpolator(points_to_interpolate)
        
        return result
    
    # OLD UNUSED AND UNEFFICIENT
    def _compute_adjacency_boundary_points_complete(self):
        
        list_edge_point_ids = []
        for i in range(self.boundary_edges.GetNumberOfCells()):
            cell = self.boundary_edges.GetCell(i)
            point_ids = [cell.GetPointId(j) for j in range(cell.GetNumberOfPoints())]
            list_edge_point_ids.append(point_ids)
        
        adj_list = {}
        for edge in list_edge_point_ids:
            if edge[0] not in adj_list:
                adj_list[edge[0]] = []
            if edge[1] not in adj_list:
                adj_list[edge[1]] = []
            if edge[1] not in adj_list[edge[0]]:
                adj_list[edge[0]].append(edge[1])
            if edge[0] not in adj_list[edge[1]]:
                adj_list[edge[1]].append(edge[0])
        return(adj_list)
    
    # OLD UNUSED AND UNEFFICIENT
    def _compute_adjacency_boundary_points_junction_points(self):
        connect_map_junction_points = {i: connect for i, connect in self.connect_map_all.items() if len(connect)>2}
        return(connect_map_junction_points)

    # OLD UNUSED AND UNEFFICIENT
    def _compute_adjacency_boundary_points_segment_points(self):
        connect_map_segment_points = {i: connect for i, connect in self.connect_map_all.items() if len(connect)==2}
        return(connect_map_segment_points)

    # OLD UNUSED AND UNEFFICIENT
    def _compute_adjacency_boundary_points_other_points(self):
        connect_map_other_points = {i: connect for i, connect in self.connect_map_all.items() if len(connect)<2}
        return(connect_map_other_points)

    # OLD UNUSED AND UNEFFICIENT
    def _compute_segments_and_isolated_loops_boundary_points(self):
        segment_list = []
        visited_points = list(self.connect_map_junction_points.keys())
        for i, connections in self.connect_map_junction_points.items():
            for c in connections:
                if c not in visited_points:
                    segment = [i]
                    current_point = copy(c)
                    while current_point not in visited_points:
                        visited_points.append(current_point)
                        segment.append(current_point)
                        p1, p2 = self.connect_map_segment_points[current_point]
                        
                        if (p1 not in visited_points) and (p2 not in visited_points):
                            current_point = p1
                        elif (p1 in visited_points) and (p2 not in visited_points):
                            current_point = p2
                        elif (p2 in visited_points) and (p1 not in visited_points):
                            current_point = p1
                        elif (p1 in visited_points) and (p2 in visited_points):
                            if (p1 == i) and (p2 == i):
                                segment.append(p1)
                            elif (p1 == i) and (p2 in self.connect_map_junction_points.keys()):
                                segment.append(p2)
                            elif (p2 == i) and (p1 in self.connect_map_junction_points.keys()):
                                segment.append(p1)
                            elif (p1 != i) and (p2 in self.connect_map_junction_points.keys()):
                                segment.append(p2)
                            elif (p2 != i) and (p1 in self.connect_map_junction_points.keys()):
                                segment.append(p1)
                            break
                    segment_list.append(segment)
        
        isolated_loops = []
        for i, connections in self.connect_map_segment_points.items():
            if i not in visited_points:
                loop = [i]
                current_point = copy(i)
                while current_point not in visited_points:
                    loop.append(current_point)
                    visited_points.append(current_point)
                    p1, p2 = self.connect_map_segment_points[current_point]
                    
                    if (p1 not in visited_points) and (p2 not in visited_points):
                        current_point = p1
                    elif (p1 in visited_points) and (p2 not in visited_points):
                        current_point = p2
                    elif (p2 in visited_points) and (p1 not in visited_points):
                        current_point = p1
                    elif (p1 in visited_points) and (p2 in visited_points):
                        if (p1 == i) and (p2 == i):
                            loop.append(p1)
                        elif p1 == i:
                            loop.append(p2)
                        elif p2 == i:
                            loop.append(p1)
                        break
                isolated_loops.append(loop)
        return(segment_list, isolated_loops)

    # OLD UNUSED AND UNEFFICIENT
    # SOME 2 points segments are not taken !!!!!
    def _compute_links_segments_points(self):
        
        segment_to_points = {i: [self.segment_list[i][0], self.segment_list[i][-1]] for i in range(len(self.segment_list))}
        
        point_to_segments = {p:[] for p in self.connect_map_junction_points.keys()}
        for s, p_list in segment_to_points.items():
            for p in p_list:
                point_to_segments[p].append(s)
                
        segment_adjacency = {s:[] for s in segment_to_points.keys()}
        for s, p_list in segment_to_points.items():
            for p in p_list:
                for new_s in point_to_segments[p]:
                    if (new_s not in segment_adjacency[s]) and (new_s != s):
                        segment_adjacency[s].append(new_s)
        

        point_adjacency = {p:[] for p in point_to_segments.keys()}
        for p, s_list in point_to_segments.items():
            for s in s_list:
                for new_p in segment_to_points[s]:
                    if (new_p not in point_adjacency[p]) and (new_p != p):
                        point_adjacency[p].append(new_p)
        
        return(segment_to_points, point_to_segments, segment_adjacency,point_adjacency)
    
        
    # def _compute_points_path(self, start_point, path):
        
    #     visited_points = (len(path)+1)*[None]
    #     # Initialize the set of visited points with the start point
    #     current_point = start_point
    #     cnt = 0
    #     visited_points[cnt] = current_point
    #     # Iterate through the segments
    #     for segment in path:
    #         cnt += 1
    #         # Check if the segment is connected to the point
    #         if segment in self.point_to_segments[current_point]:
    #             # Get the points for this segment
    #             segment_points = self.segment_to_points[segment]
    #             # Find the point in this segment that is different from the current point
    #             next_point = next((point for point in segment_points if point != current_point), None)
    #         else:
    #             next_point = None
    #         visited_points[cnt] = next_point
    #         current_point = next_point
    #     return visited_points
    
    # def _compute_path_to_be_visited(self, start_point, current_path, visited_paths):
    #     if current_path == []:
    #         all_new_paths = [[s] for s in self.point_to_segments[start_point]]
    #     else:
    #         all_new_paths = []
    #         for s in self.point_to_segments[self._compute_points_path(start_point, current_path)[-1]]:
    #             if s not in current_path:
    #                 all_new_paths.append(current_path + [s])
    #     resu = [p for p in all_new_paths if set(p) not in visited_paths]
    #     return(resu)
    
    # def _compute_all_closed_loops(self, start_point, depth=10000):
    #     start_path = []
    #     closed_loops = []
    #     current_path = start_path
    #     visited_paths = []
    #     cnt = 0
    #     while True:
            
    #         if current_path not in visited_paths:
    #             visited_paths.append(set(current_path))
                
    #         visited_points = self._compute_points_path(start_point, current_path)
    #         possible_new_paths = self._compute_path_to_be_visited(start_point, current_path, visited_paths)
            
    #         # if not cnt % 10000:
    #         # print('   cnt', cnt)
    #         # print('   current_path', current_path)
    #         # print('   visited_points', visited_points)
    #         # print('   possible_new_paths', possible_new_paths)
                
    #         # fig, ax = plt.subplots(1, 1, dpi=300)
    #         # ax.set_aspect(1)
    #         # ax.tripcolor(tripcolor_tri, processor.cell_data['bathy'], cmap='Greys_r')
    #         # for L in processor.segment_to_points.keys():
    #         #     if L in current_path:
    #         #         code = '-r'
    #         #     elif L in list(itertools.chain(*possible_new_paths)):
    #         #         code = '-k'
    #         #     else:
    #         #         code = '-y'
    #         #     ax.plot(processor.edgepoints_array[processor.segment_list[L], 0], 
    #         #             processor.edgepoints_array[processor.segment_list[L], 1], 
    #         #             code, ms=3)   
    #         # for P in processor.connect_map_junction_points.keys():
    #         #     if P in visited_points:
    #         #         code = '^b'
    #         #     else:
    #         #         code = '^y'
    #         #     ax.plot(processor.edgepoints_array[P,0], 
    #         #             processor.edgepoints_array[P,1], 
    #         #             code, ms=6)
            
    #         # ax.grid()
    #         # plt.show()
            
    #         if (current_path == []) and (possible_new_paths == []):
    #             break
    #         elif len(current_path) < depth+1:
    #             if (visited_points[-1] == visited_points[0]) and len(current_path)>0:
    #                 print('   FOUND CLOSED LOOP')
    #                 closed_loops.append(current_path)
    #                 current_path = current_path[:-1]
    #             elif visited_points[-1] in visited_points[:-1] and len(current_path)>0:
    #                 # print('   MUST GO BACK')
    #                 current_path = current_path[:-1]
    #             else:
    #                 if len(possible_new_paths):
    #                     current_path = possible_new_paths.pop()
    #                 else:
    #                     current_path = current_path[:-1]
    #         else:
    #             # print('   TOO BIG')
    #             current_path = current_path[:-1]
                
    #         cnt += 1
    #     return(closed_loops)
    
    # def _compute_complete_closed_loop_point_indices(self, start_point, loop_segments):
    #     loop_junction_points = self._compute_points_path(start_point, loop_segments)
    #     all_points = []
    #     for seg, stp in zip(loop_segments, loop_junction_points[:-1]):
    #         if self.segment_list[seg][0] == stp:
    #             all_points += self.segment_list[seg]
    #         else:
    #             all_points += self.segment_list[seg][::-1]
    #     return(all_points)
    
    # def _compute_biggest_bounday(self):
    #     """"
    #     Nouvelle méthode pour calculer la frontière englobant la plus grande 
    #     aire.
    #     Je pars d'un point quelconque
    #     Je cherche la plus grosse boucle obtenue pour un minimum d'étape
    #     
    #     Cherche du coté boucle géographique (points ou segments à l'intérieur d'une boucle)
    #     """

    #     start_point = 0
    #     closed_loops = processor._compute_all_closed_loops(start_point, depth=7)
        
    #     all_points = processor._compute_complete_closed_loop_point_indices(start_point, closed_loops[2])
    #     processor.calculate_area(processor.edgepoints_array[all_points])
    #     plt.figure()
    #     plt.plot(processor.edgepoints_array[all_points,0], 
    #             processor.edgepoints_array[all_points,1]) 
    #     plt.show()
        
        
    #     resu = []
    #     for start_point in processor.point_to_segments.keys():
    #         init_depth = 2
    #         closed_loops = []
    #         while not closed_loops:
    #             closed_loops = processor._compute_all_closed_loops(start_point, depth=init_depth)
    #             if len(closed_loops) == 1:
    #                 biggest_closed_loop = closed_loops[0]
    #             else:
    #                 biggest_closed_loop, biggest_closed_loop_area = None, 0
    #                 for C in closed_loops:
    #                     all_points = processor._compute_complete_closed_loop_point_indices(start_point, C)
    #                     area = processor.calculate_area(processor.edgepoints_array[all_points])
    #                     if area > biggest_closed_loop_area:
    #                         biggest_closed_loop_area = area
    #                         biggest_closed_loop = C
    #             init_depth += 1
    #         resu.append(biggest_closed_loop)
        
    #     for C, start_point in zip(resu, processor.point_to_segments.keys()):
    #         fig, ax = plt.subplots(1, 1, dpi=300)
    #         ax.set_aspect(1)
    #         ax.tripcolor(tripcolor_tri, processor.cell_data['bathy'], cmap='Greys_r')
    #         for L in processor.segment_to_points.keys():
    #             if L in C:
    #                 code = '-r'
    #             else:
    #                 code = '-y'
    #             ax.plot(processor.edgepoints_array[processor.segment_list[L], 0], 
    #                     processor.edgepoints_array[processor.segment_list[L], 1], 
    #                     code, ms=3)   
    #         for P in processor.connect_map_junction_points.keys():
    #             if P in processor._compute_points_path(start_point, C):
    #                 code = '^b'
    #             else:
    #                 code = '^y'
    #             ax.plot(processor.edgepoints_array[P,0], 
    #                     processor.edgepoints_array[P,1], 
    #                     code, ms=6)
            
    #         ax.grid()
    #         plt.show()
    
    
    # def _create_boundary_edges_connectors(self):
    #     """
    #     Extract edge connectors from the boundary edges.

    #     Args:
    #         boundary_edges_all (vtkPolyData): Boundary edges

    #     Returns:
    #         list: List of edge point IDs
    #     """
    #     list_edge_point_ids = []
    #     for i in range(self.boundary_edges.GetNumberOfCells()):
    #         cell = self.boundary_edges.GetCell(i)
    #         point_ids = [cell.GetPointId(j) for j in range(cell.GetNumberOfPoints())]
    #         list_edge_point_ids.append(point_ids)
            
    #     return list_edge_point_ids

    # # UNUSED
    # # ERROR SUR LES SORTIES VTK DE TOLOSA 
    # def _create_grouped_boundary_points_list(self):
    #     """
    #     Order points along boundaries and return only the boundary with the largest area.

    #     Returns:
    #         tuple: Tuple containing list of boundary points and the largest boundary points
    #     """
    #     # Create adjacency list representation
    #     adj_list = {}
    #     for edge in self.list_edge_point_ids:
    #         if edge[0] not in adj_list:
    #             adj_list[edge[0]] = []
    #         if edge[1] not in adj_list:
    #             adj_list[edge[1]] = []
    #         adj_list[edge[0]].append(edge[1])
    #         adj_list[edge[1]].append(edge[0])

    #     # Find all separate boundary loops
    #     boundaries_id = []
    #     unvisited = set(adj_list.keys())
    #     # print(unvisited)
    #     while unvisited:
    #         # Start a new boundary
    #         start_point = next(iter(unvisited))
    #         current = start_point
    #         boundary = []
    #         boundary_set = set()

    #         while True:
    #             boundary.append(current)
    #             boundary_set.add(current)
    #             unvisited.remove(current)

    #             # Find next unvisited neighbor
    #             next_point = None
    #             for neighbor in adj_list[current]:
    #                 if neighbor not in boundary_set:
    #                     next_point = neighbor
    #                     break

    #             if next_point is None or next_point == start_point:
    #                 break

    #             current = next_point

    #         # Only add boundaries_id with at least 3 points (needed for area calculation)
    #         if len(boundary) >= 3:
    #             boundaries_id.append(boundary)

    #     if not boundaries_id:
    #         return []
        
    #     boundaries_points_list = [self.edgepoints_array[b] for b in boundaries_id]
        
    #     # print(boundaries_points_list)
        
    #     return boundaries_points_list
    
    # def calculate_area(self, points):
    #     """
    #     Calculate the area of a polygon using the shoelace formula.

    #     Args:
    #         points (np.ndarray): Array of point coordinates

    #     Returns:
    #         float: Area of the polygon
    #     """
    #     # Calculate area using the shoelace formula
    #     x = points[:, 0]
    #     y = points[:, 1]

    #     # Roll the coordinates to get pairs for the formula
    #     x_next = np.roll(x, -1)
    #     y_next = np.roll(y, -1)

    #     # Shoelace formula
    #     area = 0.5 * np.abs(np.sum(x * y_next - x_next * y))
    #     return area
    
    # def calculate_largest_boundary(self, boundary_list):
    #     """
    #     Calculate the area for each boundary and find the largest
        
    #     Returns:
    #         tuple: the point list and the index of the boundary
    #     """
    #     area_list = [self.calculate_area(b_point) for b_point in boundary_list]

    #     max_area = max(area_list)
    #     largest_boundary_index = area_list.index(max_area)
    #     largest_boundary = boundary_list[largest_boundary_index]
    #     return largest_boundary, largest_boundary_index
    

class VTKPlotter:
    """
    Handles plotting of VTK data.
    
    Attributes:
        output_dir (str): Directory to save output figures
        pcolormax (float): Maximum value for color scaling
        quiver_scale (float): Scale for quiver plot
        quiver_spacing (int): Spacing for quiver plot sampling
    """
    def __init__(self, 
                 figure_outputdir: str = './Figures/', 
                 figure_title: str = '', 
                 figure_filename: str = '', 
                 figure_save = True,
                 figure_size: tuple = (4, 4),
                 figure_dpi: int = 300,
                 figure_xlim: tuple = (None, None),
                 figure_ylim: tuple = (None, None),
                 figure_format: str = 'png',
                 figure_labelfontsize: int = 8,
                 figure_tickfontsize: int = 7,
                 figure_grid_linewidth: float = .5,
                 figure_axes_color = 'k',
                 
                 pcolor_key: str = 'ssh',
                 pcolor_max: float = None, 
                 pcolor_min: float = None, 
                 pcolor_cmap: str = 'RdBu',
                 pcolor_units: str = 'm',
                 
                 triplot: bool = False,
                 triplot_color: str = 'seagreen',
                 triplot_linewidth: float = 0.2,
                 
                 contour_key: str = 'bathy',
                 contour_levels: int = 4,
                 contour_colors: str = 'r',
                 contour_linewidths: float = 1,
                 contour_units: str = 'm',
                 contour_fontsize: int = 8,
                 
                 quiver_u_key: str = 'u',
                 quiver_v_key: str = 'v',
                 quiver_scale: float = 100, 
                 quiver_spacing: int = 10,
                 quiver_positionkey: tuple = (.85, 1.03),
                 quiver_lengthkey: float = 1,
                 quiver_units: str = 'm/s',
                 quiver_fontsize: int = 8,
                 
                 rectangle_positions = None,
                 rectangle_colors = 'k',
                 rectangle_linewidths = 1
                 ):
        """
        Initialize VTKPlotter.
        
        Args:
            figure_outputdir (str): Directory to save output figures, Defaults to './Figures/'
            figure_title (str): The figure title, Defaults to ''
            figure_filename (str): Filename with which the figure is saved, Defaults to '', (will be created through the autofilename method)
            figure_save (bool): Boolean flag to activate figure saving, Defaults to True.
            figure_size (tuple, optional): Figure size in inches. Defaults to (4,4).
            figure_dpi (int, optional): Resolution of the figure. Defaults to 300.
            figure_xlim (tuple, optional): X axis view limit in the x units. Defaults to (None None).
            figure_ylim (tuple, optional): Y axis view limit in the y units. Defaults to (None None).
            figure_format (str, optional): Format of the figure. Defaults to 'png'.
            figure_labelfontsize (int, optional): Fontsize of all axis labels outside the axis. Defaults to 8
            figure_tickfontsize (int, optional): Fontsize of all axis labels outside the axis. Defaults to 8
            figure_grid_linewidth (float, optional): linewidth of the grid lines. Defaults to .5
            figure_axes_color (float or tuple, optional): Color of the axes ticks and frame. Defaults to 'k'
            
            pcolor_key (str, optional): Key name for the data displayed as pcolor. Defaults to 'ssh'.
            pcolor_max (float, optional): Maximum value for color scaling. Defaults to 1.
            pcolor_min (float, optional): Minimum value for color scaling. Defaults to -1.
            pcolor_cmap (str, optional): Colormap name. Defaults to 'RdBu'.
            pcolor_units (str, optional): Pcolor data units. Defaults to 'm'.
            
            triplot (Bool, optional): Bool flag to plot the tripcolor grid. Defaults to False.
            triplot_color (str, optional): Color of the triplot unstructured grid. Defaults to 'seagreen',
            triplot_linewidth (float, optional): Linewith of the triplot unstructured grid. Defaults to 0.2,
            
            contour_key (str, optional): Key name for the data displayed as contour. Defaults to 'bathy'.
            contour_levels (int, optional): Number of contours displayed. Defaults to 4,
            contour_colors (str, optional): Colors of the contours displayed. Defaults to 'r',
            contour_linewidths (float, optional): Linewiths of the contours displayed. Defaults to 1,
            contour_units (str, optional): Contour data units. Defaults to 'm'.
            contour_fontsize (int, optional): Fontsize of all contour labels. Defaults to 8
            
            quiver_u_key (str, optional): Key name for the data displayed as u axis in quiver. Defaults to 'u'.
            quiver_v_key (str, optional): Key name for the data displayed as v axis in quiver. Defaults to 'v'.
            quiver_scale (float, optional): Scale for quiver plot. Defaults to 100.
            quiver_spacing (int, optional): Spacing for quiver plot sampling. Defaults to 10.
            quiver_positionkey (tuple, optional): Position of the quiverkey relative to the plt.axis. Defaults to .85, 1.03)
            quiver_lengthkey (tuple, optional): Length of the quiverkey arrow. Defaults to .85, 1.03)
            quiver_units (str, optional): Quiver data units. Defaults to 'm/s'.
            quiver_fontsize (int, optional): Fontsize of quiverkey. Defaults to 8
            
            rectangle_positions (list or tuple, optional): List of optional zoom positions (xmin, xmax, ymin, ymax). Defaults to None
            rectangle_colors (list or str, optional): List of colors for the rectangles displaying the zoom positions. Defaults to 'k'
            rectangle_linewidths (list or int, optional): List of linewidths for the rectangles displaying the zoom positions. Defaults to 10
        """
        
        self.figure_outputdir = figure_outputdir
        self.figure_title= figure_title 
        self.figure_filename = figure_filename
        self.figure_save = figure_save
        self.figure_size = figure_size
        self.figure_dpi = figure_dpi
        self.figure_xlim = figure_xlim
        self.figure_ylim = figure_ylim
        self.figure_format = figure_format 
        self.figure_labelfontsize = figure_labelfontsize
        self.figure_tickfontsize = figure_tickfontsize
        self.figure_grid_linewidth = figure_grid_linewidth 
        self.figure_axes_color = figure_axes_color 
        
        self.pcolor_key = pcolor_key
        self.pcolor_max = pcolor_max
        self.pcolor_min = pcolor_min
        self.pcolor_cmap = pcolor_cmap
        self.pcolor_units = pcolor_units
        
        self.triplot = triplot
        self.triplot_color = triplot_color
        self.triplot_linewidth = triplot_linewidth
        
        self.contour_key = contour_key
        self.contour_levels = contour_levels
        self.contour_colors = contour_colors
        self.contour_linewidths = contour_linewidths
        self.contour_units = contour_units
        self.contour_fontsize = contour_fontsize
        
        self.quiver_u_key = quiver_u_key
        self.quiver_v_key = quiver_v_key
        self.quiver_scale = quiver_scale
        self.quiver_spacing = quiver_spacing
        self.quiver_positionkey = quiver_positionkey
        self.quiver_lengthkey = quiver_lengthkey
        self.quiver_units = quiver_units
        self.quiver_fontsize = quiver_fontsize
        
        self.rectangle_positions = rectangle_positions if rectangle_positions is not None else []
        self.rectangle_colors = rectangle_colors if rectangle_colors is not None else []
        self.rectangle_linewidths = rectangle_linewidths if rectangle_linewidths is not None else []
            
        if (not os.path.exists(figure_outputdir)) and (self.figure_save):
            os.makedirs(figure_outputdir)
            
            
    def _setup_figure(self) -> typing.Tuple[plt.Figure, plt.Axes]:
        """
        Create and setup the figure and axes.

        Returns
        -------
        fig : TYPE
            A plt.Figure containing a single axes.
        ax : TYPE
            The axes object of such plt.Figure.
        """

        fig, ax = plt.subplots(1, 1, 
                               figsize=self.figure_size, 
                               dpi=self.figure_dpi)
        ax.spines['bottom'].set_color(self.figure_axes_color)
        ax.spines['top'].set_color(self.figure_axes_color)
        ax.spines['left'].set_color(self.figure_axes_color)
        ax.spines['right'].set_color(self.figure_axes_color)

        ax.set_aspect(1)

        return fig, ax

    def _setup_colorbar(self, fig: plt.Figure, ax: plt.Axes, mappable) -> None:
        """
        Adds a colorbar to the right of an axis using an existing mappable.

        Parameters
        ----------
        fig : plt.Figure
            The plt.Figure to which the colorbar should be added.
        ax : plt.Axes
            The plt.Axes to the right of which the colorbar should be added.
        mappable : TYPE
            The mappable object from which the colorbar will be constructed.

        Returns
        -------
        None
        """
        cax = fig.add_axes([ax.get_position().x1 + 0.03,
                           ax.get_position().y0,
                           0.05,
                           ax.get_position().height])
        fig.colorbar(mappable, cax=cax)
        cax.tick_params(axis='y', direction='in')
        # cax.ticklabel_format(axis='y', 
        #                      style='sci', 
        #                      # scilimits=(-2,4), 
        #                      useOffset=False)
        cax.set_yticks(cax.get_yticks()[1:-1],
                      labels=cax.get_yticklabels()[1:-1],
                      rotation=90, va='center',
                      fontsize=self.figure_tickfontsize)
        cax.set_ylabel(f'{self.pcolor_key} in {self.pcolor_units}',
                       fontsize=self.figure_labelfontsize)
        
    def _adjust_axes(self, ax: plt.Axes) -> None:
    # def _adjust_axes(self, fig: plt.Figure, ax: plt.Axes) -> None:
        """
        Changes the figure ax by adding grid and adjusting ticks.

        Parameters
        ----------
        fig : plt.Figure
            The plt.Figure to be adjusted.
        ax : plt.Axes
            The axes of such figure which is to be adjusted.

        Returns
        -------
        None
            DESCRIPTION.

        """
        """
        Changes the figure ax by adding grid and adjusting ticks.
        
        Args:
            ax (plt.Axes): Matplotlib axes to finalize
        """
        
        # Adjust limits
        ax.set_xlim(self.figure_xlim)
        ax.set_ylim(self.figure_ylim)
        
        # Adjust ticks
        ax.tick_params(axis='both', direction='in', 
                       labelcolor='k',
                       colors=self.figure_axes_color, 
                       width = self.figure_grid_linewidth,
                       labelsize = self.figure_tickfontsize)
        ax.set_xticks(ax.get_xticks()[1:-1], 
                      labels=ax.get_xticklabels()[1:-1], 
                      fontsize=self.figure_tickfontsize)
        ax.set_yticks(ax.get_yticks()[1:-1], 
                      labels=ax.get_yticklabels()[1:-1], 
                      rotation=90, va='center', 
                      fontsize=self.figure_tickfontsize)
        # Add labels
        ax.set_xlabel('X coordinate', fontsize=self.figure_labelfontsize)
        ax.set_ylabel('Y coordinate', fontsize=self.figure_labelfontsize)
        
        # Add grid
        if self.figure_grid_linewidth:
            ax.grid(linestyle='dashed', 
                    zorder=1,
                    linewidth = self.figure_grid_linewidth,
                    color=self.figure_axes_color,
                    alpha=0.5)
    
    def auto_filename(self):
        """
        Defines a default filename from the keys used in the figure.

        Returns
        -------
        fig_filename : str
        """
        key_list = [self.pcolor_key, 
                    self.contour_key, 
                    self.quiver_u_key, 
                    self.quiver_v_key]
        # fig_title = f"{self.pcolor_key}_{self.contour_key}_{self.quiver_u_key}_{self.quiver_v_key}_{self.timestep:05d}.{self.figure_format}"
        fig_filename = '_'.join(filter(None, key_list))
        return fig_filename
    
    
    def _finalize_figure(self, fig: plt.Figure, ax: plt.Axes) -> None:
        """
        Finalizes the figure by aadding a suptitle and saving.

        Parameters
        ----------
        fig : plt.Figure
            The plt.Figure to be finalized.
        ax : plt.Axes
            The axes of such figure to which the title to be added.

        Returns
        -------
        None
        """
        
        # Add title at the bottom
        ax.set_title(self.figure_title, fontsize=self.figure_labelfontsize)
        
        # Save the figure
        if self.figure_filename:
            figure_filename = self.figure_filename
        else:
            figure_filename = self.auto_filename()
        
        if self.figure_save :
            fig.savefig(os.path.join(self.figure_outputdir, 
                                     f"{figure_filename}.{self.figure_format}"),
                        format=self.figure_format, 
                        bbox_inches='tight')
            
            # Close the figure
            plt.close(fig)
        else :
            return(fig, ax)
            
    def updated_rectangle_args(self):
        """
        Updates the contents of self.rectangle_positions to make it usable
        """

        if self.rectangle_positions is None :   
            new_rectangle_positions = []
        elif isinstance(self.rectangle_positions, (list, tuple)) and len(self.rectangle_positions) == 4 and all(isinstance(x, (int, float)) for x in self.rectangle_positions):
            new_rectangle_positions = [self.rectangle_positions]
        else:
            new_rectangle_positions = self.rectangle_positions
        
        if self.rectangle_colors is None:
            new_rectangle_colors = []
        elif self.rectangle_colors == 'auto':
            new_rectangle_colors = self.evenly_spaced_colors(len(new_rectangle_positions), 
                                                             colormap_name='jet')
        elif not isinstance(self.rectangle_colors, list):
            new_rectangle_colors = [self.rectangle_colors]
        else :
            new_rectangle_colors = self.rectangle_colors 
        if len(new_rectangle_colors) != len(new_rectangle_positions):
            new_rectangle_colors = len(new_rectangle_positions)*[new_rectangle_colors[0]]
            
        if isinstance(self.rectangle_linewidths, (float, int)):
            new_rectangle_linewidths = [self.rectangle_linewidths]
        else :
            new_rectangle_linewidths = self.rectangle_linewidths
        if len(new_rectangle_linewidths) != len(new_rectangle_positions):
            new_rectangle_linewidths = len(new_rectangle_positions)*[new_rectangle_linewidths[0]]
        
        return(new_rectangle_positions, new_rectangle_colors, new_rectangle_linewidths)
    
    @property
    def zoomed_plotters(self):
        """
        A property that permits to select new plotters from the different 
        zoomed subzones. The default filename for such plots are :
            self.figure_filename + '_zoom_' 'Number of the subzones'

        Returns
        -------
        list_plotters : List
            A list of new plotters which are deep copies of the current plotter
            zoomed on each of the self.updated_rectangle_args().
        """
        
        new_rectangle_positions, new_rectangle_colors, new_rectangle_linewidths = self.updated_rectangle_args()
        
        if new_rectangle_positions:
            list_plotters = []
            i = 0
            for (xmin, xmax, ymin, ymax), c in zip(new_rectangle_positions, new_rectangle_colors):
                
                newplotter = deepcopy(self)
                
                newplotter.figure_axes_color = c
                newplotter.figure_xlim = (xmin, xmax)
                newplotter.figure_ylim = (ymin, ymax)
                
                newplotter.rectangle_positions = []
                newplotter.figure_filename = self.figure_filename + f'_zoom_{i}'
                
                list_plotters += [newplotter]
                i += 1
            return list_plotters
        else:
            return None
        
    def dash_patterns(self) -> typing.List:
        """
        Custom dash patterns.

        Returns
        -------
        dash_patterns : List
            List of as many custom dash patterns as self.contour_levels.
        """

        N = self.contour_levels
        dash_patterns = []
        for i in range(N):
            # Define a custom dash pattern
            on_off_sequence = (i % (N + 2) + 1, i % (N + 2)//2 + 1)  # Vary the lengths of dashes and spaces
            dash_patterns.append((0, on_off_sequence))
        return dash_patterns
    
    def evenly_spaced_colors(self, n, colormap_name='viridis') -> typing.List:
        """Generates n colors evenly spaced inside a named colormap of matplotlib"""
        cmap = mpl.cm.get_cmap(colormap_name)
        return [cmap(i / (n - 1)) for i in range(n)]
    
    def plot_quad_data(self, #time_step: int, 
                       center_grid_X: np.ndarray, center_grid_Y: np.ndarray, 
                       cell_data: typing.Dict) -> None:
        """
        Plot quad cell data.

        Parameters
        ----------
        center_grid_X : np.ndarray
            Grid X coordinates.
        center_grid_Y : np.ndarray
            Grid Y coordinates.
        cell_data : typing.Dict
            Dictionary of cell data.

        Returns
        -------
        None
        """
        
        fig, ax = self._setup_figure()
        
        # Plot SSH   
        if self.pcolor_key:
            pcolor_plot = ax.pcolor(center_grid_X, center_grid_Y, 
                                 cell_data[self.pcolor_key],
                                 vmin=self.pcolor_min, 
                                 vmax=self.pcolor_max,
                                 cmap=self.pcolor_cmap, 
                                 rasterized=True,
                                 zorder=0)
        
        # Plot bathymetry
        if self.contour_key:
            contour_plot = ax.contour(center_grid_X, center_grid_Y, 
                                    cell_data[self.contour_key],
                                    levels=self.contour_levels, 
                                    linestyles=self.generate_custom_dash_patterns(),
                                    linewidths=self.contour_linewidths, 
                                    colors=self.contour_colors, 
                                    zorder=2)
            ax.clabel(contour_plot, fontsize=self.contour_fontsize)
        
        # Plot currents
        if self.quiver_u_key and self.quiver_v_key:
            N = self.quiver_spacing
            quiver_plot = ax.quiver(center_grid_X[::N, ::N], 
                                     center_grid_Y[::N, ::N],
                                     cell_data[self.quiver_u_key][::N, ::N], 
                                     cell_data[self.quiver_v_key][::N, ::N],
                                     scale=self.quiver_scale, 
                                     scale_units='width', 
                                     zorder=10)
            ax.quiverkey(quiver_plot, 
                         self.quiver_positionkey[0], 
                         self.quiver_positionkey[1], 
                         self.quiver_lengthkey, 
                         f'{self.quiver_lengthkey:0.3f} {self.quiver_units}', 
                         labelpos='E',
                         fontproperties={'size':self.quiver_fontsize})
        
        # Plot the optional zoom positions
        new_rectangle_positions, new_rectangle_colors, new_rectangle_linewidths = self.updated_rectangle_args()
        if new_rectangle_positions:
            for (xmin, xmax, ymin, ymax), c, lw in zip(new_rectangle_positions, new_rectangle_colors, new_rectangle_linewidths):
                lx = xmax - xmin
                ly = ymax - ymin
                rect = mpl.patches.Rectangle((xmin, ymin), lx, ly, 
                                             edgecolor=c, facecolor=None,
                                             linewidth=lw,
                                             zorder=100)
                ax.add_patch(rect)
        
        
        # Adjust the axes and grid looks
        # self._adjust_axes(fig, ax)
        self._adjust_axes(ax)
        
        # Add the colorbar if any
        if self.pcolor_key:
            self._setup_colorbar(fig, ax, pcolor_plot)
        
        if self.figure_save:
            # Ad a title and save
            self._finalize_figure(fig, ax)
        else :
            fig, ax = self._finalize_figure(fig, ax)
            return(fig, ax)
    
    def plot_triangle_data(self, 
                           tripcolor_tri: mpl.tri.Triangulation,
                           tricontour_tri: mpl.tri.Triangulation,
                           cell_data: typing.Dict, 
                           cell_centers_array: np.ndarray) -> None:
        """
        Plot triangle cell data.

        Parameters
        ----------
        tripcolor_tri : mpl.tri.Triangulation
            Triangulation for color plot.
        tricontour_tri : mpl.tri.Triangulation
            Triangulation for contour plot.
        cell_data : Dict
            Dictionary of cell data.
        cell_centers_array : np.ndarray
            Cell center coordinates.

        Returns
        -------
        None
        """
        
        fig, ax = self._setup_figure()
        
        # Plot SSH   
        if self.pcolor_key:
            ssh_plot = ax.tripcolor(tripcolor_tri, 
                                    cell_data[self.pcolor_key],
                                    vmin=self.pcolor_min, 
                                    vmax=self.pcolor_max,
                                    cmap=self.pcolor_cmap,  
                                    rasterized=True,
                                    clip_on=True,
                                    zorder=0)
        
        # Plot the grid
        if self.triplot:
            ax.triplot(tripcolor_tri, 
                       linewidth=self.triplot_linewidth, 
                       color=self.triplot_color,
                       clip_on=True)
        
        # Plot bathymetry
        if self.contour_key:
            bathy_plot = ax.tricontour(tricontour_tri, 
                                       cell_data[self.contour_key],
                                       levels=self.contour_levels, 
                                       linestyles=self.dash_patterns(),
                                       linewidths=self.contour_linewidths, 
                                       colors=self.contour_colors,
                                       zorder=2)
            ax.clabel(bathy_plot, fontsize=self.contour_fontsize)
        
        # Plot currents
        if self.quiver_u_key and self.quiver_v_key:
            random_indices = np.random.choice(len(cell_data[self.quiver_u_key]),
                                              size=len(cell_data[self.quiver_u_key])//self.quiver_spacing,
                                              replace=False)
            current_plot = ax.quiver(cell_centers_array[:,0][random_indices],
                                     cell_centers_array[:,1][random_indices],
                                     cell_data[self.quiver_u_key][random_indices],
                                     cell_data[self.quiver_v_key][random_indices],
                                     scale=self.quiver_scale, 
                                     scale_units='width', 
                                     clip_on=True,
                                     zorder=10)
            ax.quiverkey(current_plot, 
                         self.quiver_positionkey[0], 
                         self.quiver_positionkey[1],  
                         self.quiver_lengthkey, 
                         f'{self.quiver_lengthkey} {self.quiver_units}', 
                         labelpos='E',
                         fontproperties={'size':self.quiver_fontsize})
        
        # Plot the optional zoom positions
        new_rectangle_positions, new_rectangle_colors, new_rectangle_linewidths = self.updated_rectangle_args()
        if new_rectangle_positions:
            for (xmin, xmax, ymin, ymax), c, lw in zip(new_rectangle_positions, new_rectangle_colors, new_rectangle_linewidths):
                lx = xmax - xmin
                ly = ymax - ymin
                rect = mpl.patches.Rectangle((xmin, ymin), lx, ly, 
                                             edgecolor=c, facecolor=(1,1,1,0), 
                                             linewidth=lw,
                                             zorder=100)
                ax.add_patch(rect)
                
        # Adjust the axes and grid looks
        # self._adjust_axes(fig, ax)
        self._adjust_axes(ax)
        
        # Add the colorbar if any
        if self.pcolor_key:
            self._setup_colorbar(fig, ax, ssh_plot)
        
        if self.figure_save:
            # Ad a title and save
            self._finalize_figure(fig, ax)
        else :
            fig, ax = self._finalize_figure(fig, ax)
            return(fig, ax)
    
    def Plot(self, processor):
        """
        

        Parameters
        ----------
        processor : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """
        
        print("       \033[32mOK:\033[0m Creating, plotting and saving")
        # Plot based on cell type
        if processor.cell_type == 'all_Quad':
            center_grid_X, center_grid_Y, cell_data_grid = processor.reshape_to_grid()
            self.plot_quad_data(center_grid_X, 
                                center_grid_Y, 
                                cell_data_grid)
        elif processor.cell_type == 'all_Triangle':
            tripcolor_tri, tricontour_tri = processor.compute_triangulations()
            self.plot_triangle_data(tripcolor_tri, 
                                    tricontour_tri,
                                    processor.cell_data, 
                                    processor.cell_centers_array)
        print("       \033[32mOK:\033[0m Figure created and saved")
