#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 21 15:57:56 2025

@author: llsaisset
"""

from abc import ABC, abstractmethod
import typing
from copy import copy

import vtk
import numpy as np

from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator
from shapely import LineString, Polygon, polygonize
from shapely.vectorized import contains

from .common import p_error, p_warning

import matplotlib as mpl

class DataProcessor(ABC):
    """
    Abstract mother class that states the necessary methods for use of the 
    data processors inside the data plotter.
    """
    def __init__(self, data):
        # the source of data from which to construct the rest.
        # Should ideally be the direct result of some reader.
        self.data = data
        
        # a str flag used in the plotter
        self.cell_type = self._extract_celltype()       
        
        # A dict containing the cell data, in cell order
        self.cell_data = self._create_cell_data_dict()
        
        # An array containing the cell center positions
        self.cell_centers_array = self._create_cell_center_array()
        
    @abstractmethod
    def _extract_celltype(self):
        pass
    
    @abstractmethod
    def _create_cell_data_dict(self):
        pass
   
    @abstractmethod
    def  _create_cell_center_array(self):
        pass
    
    @abstractmethod
    def compute_triangulations(self):
        pass
        
    @abstractmethod
    def reshape_to_grid(self):
        pass
    
    def compute_cell_data_differences(self, other_processor) -> dict:
        
        # Check if the cell centers are the same in both datasets
        N_equal_cells = (self.cell_centers_array == other_processor.cell_centers_array).sum()
        if N_equal_cells != 3*self.num_cells:
            p_warning("The cell centers do not match between the two datasets.")
        if self.num_cells == other_processor.num_cells:
            p_error("The cell centers do not match between the two datasets.")
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
    
    def compute_interpolation_masked_grid(self, X, Y, data_key, method='linear'):
        """
        Interpolate scattered data onto a grid, optionally using a mask.
        
        Args:
            data_key (str): key upon which to interpolate the values for the 
                            data inside processor.cell_data[data_key]
            X (np.ndarray): X coordinates grid
            Y (np.ndarray): Y coordinates grid
            method (str): 'linear' or 'nearest'
            
        Returns:
            np.ndarray: Interpolated values on the (X, Y) grid
        """
        
        # Original data points
        points = self.cell_centers_array[:, 0:2]
        
        # Choose interpolator
        if method == 'linear':
            interpolator = LinearNDInterpolator(points, self.cell_data[data_key])
        elif method == 'nearest':
            interpolator = NearestNDInterpolator(points, self.cell_data[data_key])
        else:
            p_error("Valid interpolation methods are 'linear' or 'nearest'")
            return np.array([])
        
        mask = self.compute_mask_grid(X, Y)
        
        # Initialize result array
        result = np.full(X.shape, np.nan)
        
        # Points where we need to interpolate (masked points)
        points_to_interpolate = np.column_stack((X[mask].ravel(), Y[mask].ravel()))
        
        # Interpolate only at masked points
        result[mask] = interpolator(points_to_interpolate)
        
        return result


class BinDataProcessor(DataProcessor):
    """
    Processes the contents of a binary output file from Tolosa-sw
    """
    def __init__(self, 
                 data: typing.Tuple, 
                 mesh: typing.Dict,
                 variables: typing.List):
        """
        Initialize VTKDataProcessor.
        
        Args:
            data (vtk.vtkUnstructuredGrid): Input VTK object
        """
        # The contents of the file given as an output from the reader
        self.data = {'variables':variables, "mesh":mesh, "data": data}
        
        self.num_points = self.data['mesh']['num_nodes']
        self.num_cells = self.data['mesh']['num_cells']
        self.points_array = self.data['mesh']['nodes']
        
        self.cell_type = self._extract_celltype()                           # a str flag used in the plotter
        self.cells = self._extract_cells()                                  # The connectivity list between cells and their nodes
        
        self.boundary_edges = self._extract_boundary_edges()                # a numpy array of tuples of node indexes for egdes on the boundaries of the mesh
        self.edgepoints_array, self.num_edgepoints = self._extract_edgepoints()   # the numpy array of boundary point coordinates of the number of such points
        
        self.cell_data = self._create_cell_data_dict()                      # a dict containing the cell data, in cell order
        self.cell_centers_array = self._create_cell_center_array()          # a numpy array of the cell centers coordinates
        
        self.boundary_polygon_list = self._create_boundary_polygon_list()
        self.boundary_polygon = self._create_boundary_polygon()
        
        self.xmin, self.xmax, self.ymin, self.ymax = self._extract_data_lims()   # the min/max of the points coordinates
        
    def _extract_celltype(self) -> str:
        """
        Extract the cell type of cells from Binary data, supposing the data is 
        either on a triangular mesh or a quad mesh.
        
        Returns:
            'all_Quad' if all cells are quadrilaterals and 'all_Triangle' if 
            all cells are triangular.
        """
        
        mesh_last_col = self.data['mesh']['cells'][:,-1]
        same_value_last_col = (mesh_last_col == mesh_last_col[0]).sum() == self.num_cells
        if same_value_last_col:
            cell_type = "all_Triangle"
        else:
            cell_type = "all_Quad"
            
        return(cell_type)
    
    def _extract_cells(self) -> str:
        """
        Extract the cell connectivity and dropping non usefull columns
        
        Returns:
            nm.array of node indexes comprised in the cells
        """
        if self.cell_type == "all_Triangle":
            cells = self.data['mesh']['cells'][:, :-1]
        elif self.cell_type == "all_Quad":
            cells = self.data['mesh']['cells']
        else:
            cells = np.array([])
            
        return(cells)

    def _extract_boundary_edges(self):
        # Use neighbors to find boundary triangles
        neighbors = self.compute_tripcolor_tri().neighbors
        
        # Which neighbor corresponds to each edge
        neighbor_indices = [2, 1, 0] # ICI FAUT PAS SE TROMPER !
        
        # Find boundary edges by looking at triangles with -1 neighbors
        boundary_edges = set()
        for tri_idx, triangle in enumerate(self.cells):
            tri_neighbors = neighbors[tri_idx]
            
            # Check each edge of the triangle
            edges = [(triangle[0], triangle[1]),  # Edge 0-1, neighbor index 2
                     (triangle[1], triangle[2]),  # Edge 1-2, neighbor index 0  
                     (triangle[2], triangle[0])   # Edge 2-0, neighbor index 1
                     ]
            
            for edge_idx, edge in enumerate(edges):
                neighbor_idx = neighbor_indices[edge_idx]
                if tri_neighbors[neighbor_idx] == -1:  # No neighbor = boundary edge
                    boundary_edges.add(edge)
        
        # Remove duplicates
        boundary_edges = list(set(boundary_edges))
        
        return(boundary_edges)
    
    def _extract_edgepoints(self):
        # Extract boundary point indices
        boundary_indices = set()
        for edge in self.boundary_edges:
            boundary_indices.update(edge)
            
        boundary_indices = np.array(sorted(boundary_indices))
        edgepoints_array = self.points_array[boundary_indices]
        
        return(edgepoints_array, len(edgepoints_array))
    
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
        Extracts only the cell data 
        
        Returns:
            a dict containing all 
        """
        
        N = len(self.data['variables'])
        cell_data_dict = {}
        for i in range(N):
            cell_data_dict[self.data['variables'][i]] = self.data['data'][list(self.data['data'].keys())[0]][i]
            
        return(cell_data_dict)
    
    def _create_cell_center_array(self):
        """
        Returns:
            Numpy array containing the cell center coordinates
        """
        # Compute cell centers
        cell_centers_array = np.zeros((self.cells.shape[0], self.points_array.shape[1]))
        num_cell_points = self.cells.shape[-1]
        for i in range(num_cell_points):
            cell_centers_array[:, :] += self.points_array[self.cells[:, i]]/num_cell_points
        
        return cell_centers_array
        
    def reshape_to_grid(self):
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
    
    def compute_tripcolor_tri(self):
        tripcolor_triangulation = mpl.tri.Triangulation(
                                    self.points_array[:, 0],
                                    self.points_array[:, 1],
                                    triangles=self.cells)
        return(tripcolor_triangulation)
        
    def compute_tricontour_tri(self):
        # Compute tricontour triangulation
        tricontour_triangulation = mpl.tri.Triangulation(
                                                self.cell_centers_array[:, 0],
                                                self.cell_centers_array[:, 1]
                                                )
        
        # Create mask
        xtri = self.cell_centers_array[:, 0][tricontour_triangulation.triangles] - \
               np.roll(self.cell_centers_array[:, 0][tricontour_triangulation.triangles], 1, axis=1)
        ytri = self.cell_centers_array[:, 1][tricontour_triangulation.triangles] - \
               np.roll(self.cell_centers_array[:, 1][tricontour_triangulation.triangles], 1, axis=1)
    
        # Compute the maximum cell size to be considered inside the new triangulation
        min_cells = self.points_array[self.cells].min(axis=1)
        max_cells = self.points_array[self.cells].max(axis=1)
        sizes = max_cells - min_cells
        max_size = max(np.hypot(sizes[:,0], sizes[:,1]))
        
        tricontour_triangulation.set_mask(np.max(np.sqrt(xtri**2 + ytri**2), axis=1) > max_size)
        
        return(tricontour_triangulation)
    
    def _create_boundary_polygon_list(self) -> list:
        
        list_coords_boundary_edges = self.points_array[self.boundary_edges]
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
    
    def compute_triangulations(self):
        """
        Compute triangulations for triangle cells.
        
        Returns:
            Tuple of tripcolor and tricontour triangulations
        """
        
        tripcolor_tri = self.compute_tripcolor_tri()
        tricontour_tri = self.compute_tricontour_tri()
        
        return(tripcolor_tri, tricontour_tri)
    
    # def compute_triangulations(self) -> tuple:
    #     """
    #     Compute triangulations for triangle cells.
        
    #     Returns:
    #         Tuple of tripcolor and tricontour triangulations
    #     """
    #     # Compute tripcolor triangulation
    #     cell_point_indexes = np.zeros([self.num_cells, 3])
    #     for i in range(self.num_cells):
    #         cell = self.data.GetCell(i)
    #         cell_point_indexes[i] = [cell.GetPointId(j) for j in range(3)]
            
    #     tripcolor_triangulation = mpl.tri.Triangulation(
    #         self.points_array[:, 0],
    #         self.points_array[:, 1],
    #         triangles=cell_point_indexes)
        
    #     # Compute tricontour triangulation
    #     tricontour_triangulation = mpl.tri.Triangulation(
    #         self.cell_centers_array[:, 0],
    #         self.cell_centers_array[:, 1])
        
    #     # Create mask
    #     xtri = self.cell_centers_array[:, 0][tricontour_triangulation.triangles] - \
    #            np.roll(self.cell_centers_array[:, 0][tricontour_triangulation.triangles], 1, axis=1)
    #     ytri = self.cell_centers_array[:, 1][tricontour_triangulation.triangles] - \
    #            np.roll(self.cell_centers_array[:, 1][tricontour_triangulation.triangles], 1, axis=1)
    #     sizes = np.array([np.array(self.data.GetCell(i).GetBounds()[0::2]) - 
    #                      np.array(self.data.GetCell(i).GetBounds()[1::2]) 
    #                      for i in range(self.num_cells)])
    #     max_size = max(np.hypot(sizes[:,0], sizes[:,1], sizes[:,2]))
    #     tricontour_triangulation.set_mask(np.max(np.sqrt(xtri**2 + ytri**2), axis=1) > max_size)
        
    #     return tripcolor_triangulation, tricontour_triangulation

class VTKDataProcessor(DataProcessor):
    """
    Processes the contents of a VTK output file from Tolosa-sw
    """
    def __init__(self, data: vtk.vtkUnstructuredGrid):
        """
        Initialize VTKDataProcessor.
        
        Args:
            data (vtk.vtkUnstructuredGrid): Input VTK object
        """
        # The vtk data structure given as an output from the reader
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