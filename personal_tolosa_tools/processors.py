#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May 21 15:57:56 2025

@author: llsaisset
"""

from abc import ABC, abstractmethod
import typing
from copy import copy, deepcopy

import os

import vtk
from meshio import Mesh
import numpy as np
from pandas import unique

from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator, RegularGridInterpolator
from scipy.spatial import cKDTree

from shapely import LineString, Polygon, polygonize, points, STRtree, from_ragged_array
from shapely.vectorized import contains
from shapely.ops import linemerge

# from shapely import polygons, coverage_union_all
# from shapely.geometry import mapping, box
# from rasterio.features import rasterize
# from affine import Affine

from .common import p_error, p_ok, p_warning, p_timer

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
        if self.num_cells != other_processor.num_cells:
            p_error("The two data sources do not match cell number.")
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

class MeshDataProcessor(DataProcessor):
    """
    Processes MeshIO data for plotting.
    
    This class provides a unified interface for processing mesh data from
    various formats (VTK, MSH, etc.) read using meshio library.
    
    Attributes:
        data (meshio.Mesh): Input meshio mesh object
        cell_type (str): Type of cells in the mesh
        points_array (np.ndarray): Node coordinates
        cells (dict): Dictionary of the triangular cells in the first block (supposed only block)
    """
    
    def __init__(self, data: Mesh):
        """
        Initialize MeshDataProcessor.
        
        Args:
            data (meshio.Mesh): Input meshio mesh object
        """
        # Store the mesh object
        self.data = data
        
        # Extract nodes positions if any
        self.points_array = self.data.points  # (N x 3) array of coordinates
        self.num_points = len(self.points_array)
        
        # In this object only triangular cells matter : extract triangular cells if any
        self.num_blocks = len(self.data.cells)
        self.cell_types = [a.type for a in self.data.cells] if self.num_blocks else []
        self.index_triangle = self.cell_types.index('triangle') if 'triangle' in self.cell_types else None
        self.index_line = self.cell_types.index('line') if 'line' in self.cell_types else None
        
        self.cells = self.data.cells[self.index_triangle].data if 'triangle' in self.cell_types else np.array([])
        self.num_cells = len(self.cells)
        self.cell_centers_array = self._create_cell_center_array()
        
        self.lines = self.data.cells[self.index_line].data if 'line' in self.cell_types else np.array([])
        self.num_lines = len(self.lines)
        self.line_centers_array = self._create_line_center_array()
        
        # Extract cell and point data in dict
        self.point_data = data.point_data if data.point_data else {}
        if self.points_array.any() and 'z' not in self.point_data.keys(): 
            self.point_data['z'] = self.points_array[:,-1]
        self.cell_data = self._create_cell_data_dict()
        self.line_data = self._create_line_data_dict()
        
        # Check cell_type : If triangular cells are valid and match some cell data, then cell_type = 'all_Triangle'
        self.cell_type = self._extract_celltype()
        
        # Boundary processing directly from connectivity
        self.xmin, self.xmax, self.ymin, self.ymax = self._extract_data_lims()
        # self.boundary_edges = self._extract_boundary_edges()
        # self.edgepoints_array, self.num_edgepoints = self._extract_edgepoints()
        # self.boundary_polygon_list = self._create_boundary_polygon_list()
        # self.boundary_polygon = self._create_boundary_polygon()
        
        # For boundary nodes and boundary types from mesh information refer to the following :
        # self.extract_edgepoints_from_msh()
        
        # # Compute node to cell connectivity
        
        # # Compute node centered polygons from cell centers

    
    def _create_cell_center_array(self) -> np.ndarray:
        """
        Compute cell centers by averaging node coordinates.
        
        Returns:
            np.ndarray: (num_cells x 3) array of cell centers
        """
        if not self.num_cells:
            return np.array([])
        elif not self.num_points:
            return np.array([])
        elif self.cells.max() > self.num_points :
            return np.array([])
        else:
            bigmap = self.points_array[self.cells]
            return bigmap.sum(axis=1)/3
        
    def _create_line_center_array(self) -> np.ndarray:
        """
        Compute line centers by averaging node coordinates.
        
        Returns:
            np.ndarray: (num_cells x 3) array of cell centers
        """
        if not self.num_lines:
            return np.array([])
        elif not self.num_points:
            return np.array([])
        elif self.lines.max() > self.num_points  :
            return np.array([])
        else:
            bigmap = self.points_array[self.lines]
            return bigmap.sum(axis=1)/2
    
    def _extract_celltype(self) -> str:
        """
        Determine the predominant cell type.
        
        Returns:
            str: 'all_Triangle', 'all_Quad', or 'mixed'
        """
        if self.index_triangle != None:
            return 'all_Triangle'
        else :
            return 'no_triangles'
        
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
    
    def _create_cell_data_dict(self) -> dict:
        """
        Flatten cell data from blocks to single arrays per variable.
        
        MeshIO stores cell_data as: {var_name: [block1_data, block2_data, ...]}
        We flatten to: {var_name: concatenated_data}
        
        Returns:
            dict: Flattened cell data
        """
        cell_data = {}
        
        if self.index_triangle == None :
            return cell_data
        
        else :
            for var_name, data_blocks in self.data.cell_data.items():
                cell_data[var_name] = data_blocks[self.index_triangle]
                
            return cell_data
        
    def _create_line_data_dict(self) -> dict:
        """
        Flatten line data from blocks to single arrays per variable.
        
        MeshIO stores cell_data as: {var_name: [block1_data, block2_data, ...]}
        We flatten to: {var_name: concatenated_data}
        
        Returns:
            dict: Flattened cell data
        """
        line_data = {}
        
        if self.index_line == None :
            return line_data
        
        else :
            for var_name, data_blocks in self.data.cell_data.items():
                line_data[var_name] = data_blocks[self.index_line]
                
            return line_data
    
    def _extract_data_lims(self) -> typing.Tuple:
        """
        Extract X and Y limits of the mesh.
        
        Returns:
            Tuple of (xmin, xmax, ymin, ymax)
        """
        if self.num_points:
            xmin = np.min(self.points_array[:, 0])
            xmax = np.max(self.points_array[:, 0])
            ymin = np.min(self.points_array[:, 1])
            ymax = np.max(self.points_array[:, 1])
        else:
            xmin, xmax, ymin, ymax = None, None, None, None
        return (xmin, xmax, ymin, ymax)
    
    
    
    def compute_triangulations(self) -> tuple:
        """
        Compute matplotlib triangulations for triangle meshes.
        
        Returns:
            Tuple of (tripcolor_triangulation, tricontour_triangulation)
        """
        if self.cell_type != 'all_Triangle':
            raise ValueError("Triangulations only supported for all-triangle meshes")
        
        # Get triangle cell connectivity
        triangle_cells = self.cells
        if not len(triangle_cells) :
            raise ValueError("No triangle cells found")
        
        # Create tripcolor triangulation (for coloring faces)
        tripcolor_triangulation = mpl.tri.Triangulation(
            self.points_array[:, 0],
            self.points_array[:, 1],
            triangles=triangle_cells
        )
        
        # Create tricontour triangulation (for contouring at cell centers)
        tricontour_triangulation = mpl.tri.Triangulation(
            self.cell_centers_array[:, 0],
            self.cell_centers_array[:, 1]
        )
        
        # Create mask for tricontour to avoid large triangles
        xtri = self.cell_centers_array[:, 0][tricontour_triangulation.triangles] - \
               np.roll(self.cell_centers_array[:, 0][tricontour_triangulation.triangles], 1, axis=1)
        ytri = self.cell_centers_array[:, 1][tricontour_triangulation.triangles] - \
               np.roll(self.cell_centers_array[:, 1][tricontour_triangulation.triangles], 1, axis=1)
        
        # Compute characteristic cell size
        min_cells = self.points_array[triangle_cells].min(axis=1)
        max_cells = self.points_array[triangle_cells].max(axis=1)
        sizes = max_cells - min_cells
        max_size = max(np.hypot(sizes[:, 0], sizes[:, 1]))
        
        # Apply mask
        tricontour_triangulation.set_mask(
            np.max(np.sqrt(xtri**2 + ytri**2), axis=1) > max_size
        )
        
        return tripcolor_triangulation, tricontour_triangulation
    
    def _linestrings_from_edges(self, edges: np.ndarray, points: np.ndarray):
        """
        Convert edges (M,2) to merged shapely LineString / MultiLineString.
        """
        segments = [
            LineString(points[edge])
            for edge in edges
        ]

        merged = linemerge(segments)
        return merged
    
    def compute_lines_by_physical(self):
        phys = self.line_data["gmsh:physical"]
        result = {}
        link = dict([(v[0], k) for k, v in self.data.field_data.items()])
    
        for pid in np.unique(phys):
            edges = self.lines[phys == pid]
            merged = self._linestrings_from_edges(edges, self.points_array)
            result[link[int(pid)]] = merged
        return result
    
    def compute_lines_by_geometrical(self):
        phys = self.line_data["gmsh:geometrical"]
        result = {}
    
        for pid in np.unique(phys):
            edges = self.lines[phys == pid]
            merged = self._linestrings_from_edges(edges, self.points_array)
            result[int(pid)] = merged
        return result
    
    
    
    
    
    

    def compute_max_node_cell_adjacency(self):
        """
        Computes the max number of adjacent cells to a node

        Returns int
        """
        values, counts = np.unique(self.cells, return_counts=True)
        idx = counts.argmax()
        return int(counts[idx])
    
    def compute_cell_to_node(self):
        return (self.cells)
    
    def compute_edge_to_node(self):
        """
        Computes the edges from the cell to nodes mapping. Edges are 
        unique, in order of occurence inside cells

        Returns np.ndarray
        """
        # 1. Build edges per cell (same order as triangles)
        edges = np.vstack((self.cells[:, [0, 1]],
                           self.cells[:, [1, 2]],
                           self.cells[:, [2, 0]]))
        
        # 2. Sort nodes inside each edge (undirected)
        edges = np.sort(edges, axis=1)
        
        # 3. Unique edges
        edge_to_node = np.unique(edges, axis=0)
        
        return edge_to_node
    
    def compute_cell_to_edge(self):
        # 1. Build edges per cell (same order as triangles)
        edges = np.vstack([
            self.cells[:, [0, 1]],
            self.cells[:, [1, 2]],
            self.cells[:, [2, 0]]
        ])
    
        # 2. Sort nodes inside each edge (undirected)
        edges = np.sort(edges, axis=1)
    
        # 3. Inverse mapping of Unique edges
        _, edge_ids = np.unique(edges, axis=0, return_inverse=True)
    
        # 4. Reshape back to (num_cells, 3)
        cell_to_edge = edge_ids.reshape(3, self.num_cells).T
    
        return cell_to_edge
        
    def compute_node_to_cell(self):
        """
        Computes the node to cells mapping in the mesh. The number of adjacent
        cells varies. By default, np.nan are used if no such cell exists.

        Returns np.ndarray 
        """
        
        cells = self.cells
        num_cells = self.num_cells
        num_points = self.num_points
        max_adj = self.compute_max_node_cell_adjacency()
    
        # 1) Flatten node indices and corresponding cell ids
        nodes = cells.ravel()                             # (3*Nc,)
        cell_ids = np.repeat(np.arange(num_cells), 3)     # (3*Nc,)
    
        # 2) Sort by node index
        order = np.argsort(nodes)
        nodes = nodes[order]
        cell_ids = cell_ids[order]
    
        # 3) Count how many times each node appears
        counts = np.bincount(nodes, minlength=num_points)
    
        # 4) Compute per-node offsets
        offsets = np.cumsum(np.r_[0, counts[:-1]])
    
        # 5) Local index inside each node group
        local_idx = np.arange(nodes.size) - offsets[nodes]
    
        # 6) Allocate output (NaN-filled)
        node_to_cell = np.full((num_points, max_adj), np.nan, dtype=float)
    
        # 7) Scatter
        node_to_cell[nodes, local_idx] = cell_ids
        
        # 8) sort cells 
        node_to_cell.sort(axis=1)
        
        return node_to_cell
    
    def compute_node_to_edge(self):
        """
        Computes the node to edges mapping in the mesh. The number of adjacent
        edges varies. By default, np.nan are used if no such edge exists.

        Returns np.ndarray 
        """
        edge_to_node = self.compute_edge_to_node()
        n_edges = edge_to_node.shape[0]
        n_points = self.num_points
    
        # Max adjacency (can be computed similarly to node to cell)
        max_adj = np.max(np.bincount(edge_to_node.ravel(), minlength=n_points))
    
        # 1. Expand edges to nodes
        node_ids = edge_to_node.ravel()                     # (2 * n_edges,)
        edge_ids = np.repeat(np.arange(n_edges), 2)         # (2 * n_edges,)
    
        # 2. Stable grouping by node (preserves edge order)
        order = np.argsort(node_ids, kind="stable")
        node_ids_sorted = node_ids[order]
        edge_ids_sorted = edge_ids[order]
    
        # 3. Count edges per node
        counts = np.bincount(node_ids_sorted, minlength=n_points)
    
        # 4. Starting offsets per node
        starts = np.cumsum(np.r_[0, counts[:-1]])
    
        # 5. Output array
        node_to_edge = np.full((n_points, max_adj), np.nan)
    
        # 6. Column indices inside each node row
        local_idx = np.arange(node_ids_sorted.size) - starts[node_ids_sorted]
    
        # 7. Assign
        node_to_edge[node_ids_sorted, local_idx] = edge_ids_sorted
    
        return node_to_edge
    
    def compute_edge_to_cell(self):
        """
        Computes the edge to cells mapping in the mesh. The number of adjacent
        cells can be 1 or 2. By default, np.nan are used if no such second
        cell exists.

        Returns np.ndarray 
        """
        cells = self.cells
        n_cells = self.num_cells
    
        # 1. Build edges per cell (same construction as edge_to_node)
        edges = np.vstack([
            cells[:, [0, 1]],
            cells[:, [1, 2]],
            cells[:, [2, 0]]
        ])
        edges = np.sort(edges, axis=1)
    
        # 2. Map to global edge indices (order matches edge_to_node)
        _, edge_ids = np.unique(edges, axis=0, return_inverse=True)
    
        # 3. Cell indices (each repeated 3 times)
        cell_ids = np.repeat(np.arange(n_cells), 3)
    
        # 4. Stable grouping by edge index
        order = np.argsort(edge_ids, kind="stable")
        edge_ids_sorted = edge_ids[order]
        cell_ids_sorted = cell_ids[order]
    
        n_edges = edge_ids.max() + 1
    
        # 5. Count cells per edge (1 or 2)
        counts = np.bincount(edge_ids_sorted, minlength=n_edges)
    
        # 6. Starting offsets per edge
        starts = np.cumsum(np.r_[0, counts[:-1]])
    
        # 7. Output array
        edge_to_cell = np.full((n_edges, 2), np.nan)
    
        # 8. Column indices (0 or 1)
        local_idx = np.arange(edge_ids_sorted.size) - starts[edge_ids_sorted]
    
        # 9. Assign
        edge_to_cell[edge_ids_sorted, local_idx] = cell_ids_sorted
    
        return edge_to_cell
    
    
    def compute_node_to_quad(self):
        cells = self.cells
        num_cells = self.num_cells
        num_points = self.num_points
        
        max_adj = self.compute_max_node_cell_adjacency()
        
        # 1) Flatten node indices (same as before)
        nodes = cells.ravel()   # (3*num_cells,)
        
        # 2) Build corresponding quad indices
        # quad_id = 3*cell_id + local_node_index
        quad_ids = (
            3 * np.repeat(np.arange(num_cells), 3)
            + np.tile(np.arange(3), num_cells)
        )
        
        # 3) Sort by node index
        order = np.argsort(nodes)
        nodes = nodes[order]
        quad_ids = quad_ids[order]
        
        # 4) Count occurrences per node
        counts = np.bincount(nodes, minlength=num_points)
        
        # 5) Offsets
        offsets = np.cumsum(np.r_[0, counts[:-1]])
        
        # 6) Local indices inside node group
        local_idx = np.arange(nodes.size) - offsets[nodes]
        
        # 7) Allocate output
        node_to_quad = np.full((num_points, max_adj), np.nan)
        
        # 8) Scatter
        node_to_quad[nodes, local_idx] = quad_ids
        
        # Optional: sort quad indices per node
        node_to_quad.sort(axis=1)
        
        return node_to_quad
    
    def compute_cell_to_quad(self):
        """
        Only works because the quads computing is done in order 
                 [ 1st edge of all cells (num_cells list), 
                   2nd edge of all cells (num_cells list),
                   3rd edge of all cells (num_cells list) ]
        """
        num_cells = self.num_cells
    
        cell_ids = np.arange(num_cells)
        cell_to_quad = 3 * cell_ids[:, None] + np.arange(3)
    
        return cell_to_quad
    
    def compute_quad_to_cell(self):
        """
        Only works because the quads computing is done in order 
                 [ 1st edge of all cells (num_cells list), 
                   2nd edge of all cells (num_cells list),
                   3rd edge of all cells (num_cells list) ]
        """
        num_cells = self.num_cells
        num_quads = 3 * num_cells
    
        quad_to_cell = np.arange(num_quads) // 3
    
        return quad_to_cell

    
    def compute_quad_to_node(self):
        """
        Only works because the quads computing is done in order 
                 [ 1st edge of all cells (num_cells list), 
                   2nd edge of all cells (num_cells list),
                   3rd edge of all cells (num_cells list) ]
        """
        cells = self.cells
        num_cells = self.num_cells
        num_quads = 3 * num_cells
    
        quad_ids = np.arange(num_quads)
    
        cell_ids = quad_ids // 3
        local_node_ids = quad_ids % 3
    
        quad_to_node = cells[cell_ids, local_node_ids]
    
        return quad_to_node


    
    def _compute_dual_mesh_from_mappings(self, verbose: bool = False):
        with p_timer("Compute mappings", verbose=verbose):
            node_to_cell = self.compute_node_to_cell()
            node_to_edge = self.compute_node_to_edge()
            edge_to_cell = self.compute_edge_to_cell()
            edge_to_node = self.compute_edge_to_node()
        
        with p_timer("Compute adjacent cell centers", verbose=verbose):
            # Compute the adjacent cell centers
            node_to_cell_flat = node_to_cell.ravel()
            node_to_cell_flat_cut = node_to_cell_flat[~np.isnan(node_to_cell_flat)].astype(int)
            node_to_cell_flat_cut_center = self.cell_centers_array[node_to_cell_flat_cut]
            
        with p_timer("Compute cell center to node index mapping", verbose=verbose):
            # With the corresponding cell center to node index mapping
            node_to_cell_flat_mapping = np.repeat(np.arange(len(node_to_cell)), node_to_cell.shape[1])
            node_to_cell_flat_mapping_cut = node_to_cell_flat_mapping[~np.isnan(node_to_cell_flat)]
        
        with p_timer("Compute adjacent boundary edges centers", verbose=verbose):
            # Compute the adjacent boundary edges centers
            node_to_edge_flat = node_to_edge.ravel()
            node_to_edge_flat_cut = node_to_edge_flat[~np.isnan(node_to_edge_flat)].astype(int)
            bnd_edge_filter = np.isnan(edge_to_cell[node_to_edge_flat_cut]).any(axis=1)
            node_to_edge_flat_cut_edge = node_to_edge_flat_cut[bnd_edge_filter]
            node_to_edge_flat_cut_edge_center = self.points_array[edge_to_node[node_to_edge_flat_cut_edge]].mean(axis=1)
        with p_timer("Compute edge center to node index mapping", verbose=verbose):
            # With the corresponding edge center to node index mapping
            node_to_edge_flat_mapping = np.repeat(np.arange(len(node_to_edge)), node_to_edge.shape[1])
            node_to_edge_flat_mapping_cut = node_to_edge_flat_mapping[~np.isnan(node_to_edge_flat)]
            node_to_edge_flat_mapping_cut_edge = node_to_edge_flat_mapping_cut[bnd_edge_filter]
        
        with p_timer("Extract boundary points (inside the boundary polygons)", verbose=verbose):
            # Extract boundary points (inside the boundary polygons)
            node_bnd_mapping = unique(node_to_edge_flat_mapping_cut_edge)
            node_bnd = self.points_array[node_bnd_mapping]
        
        with p_timer("Concatenate all center points", verbose=verbose):
            # Concatenate all center points
            center_types = np.array(
                [0]*len(node_bnd_mapping)
                + [1]*len(node_to_edge_flat_mapping_cut_edge)
                + [2]*len(node_to_cell_flat_mapping_cut)
                )
            full_centers = np.concatenate((
                node_bnd, 
                node_to_edge_flat_cut_edge_center,
                node_to_cell_flat_cut_center
                ))
            full_centers_mapping = np.concatenate((
                node_bnd_mapping,
                node_to_edge_flat_mapping_cut_edge,
                node_to_cell_flat_mapping_cut
                ))
        
        with p_timer("Sort and split according to the mapping", verbose=verbose):
            # Sort according to the mapping
            order = np.argsort(full_centers_mapping)
            points = full_centers[order]
            types  = center_types[order]
            mapping = full_centers_mapping[order]
        
            # Split according to the mapping
            split_idx = np.flatnonzero(np.diff(mapping)) + 1
            points_groups = np.split(points, split_idx)
            types_groups  = np.split(types, split_idx)
        
        def sort_group(points, types, ref):
            dx = points[:, 0] - ref[0]
            dy = points[:, 1] - ref[1]
            angles = np.arctan2(dy, dx) + np.pi
        
            order = np.argsort(angles)
            sorted_points = points[order]
            sorted_types  = types[order]
        
            # Case 1: no reference point in group
            if 0 not in sorted_types:
                return Polygon(sorted_points)
        
            # Case 2: reference point is in the group
            ref_idx = np.flatnonzero(sorted_types == 0)[0]
            ref_point = sorted_points[ref_idx]
        
            # Remove reference point temporarily
            points_wo_ref = np.delete(sorted_points, ref_idx, axis=0)
            types_wo_ref  = np.delete(sorted_types, ref_idx)
        
            # Find type==1 indices (must be exactly two)
            idx1 = np.flatnonzero(types_wo_ref == 1)
            if len(idx1) != 2:
                raise ValueError("Expected exactly two type==1 points")
        
            i0, i1 = idx1
        
            # Wrap-around case: [1, ..., 1]
            if i0 == 0 and i1 == len(types_wo_ref) - 1:
                new_points = np.vstack([
                    ref_point,
                    points_wo_ref
                ])
            else:
                # Insert ref point between the two type==1 points
                insert_pos = max(i0, i1)
                new_points = np.vstack([
                    points_wo_ref[:insert_pos],
                    ref_point,
                    points_wo_ref[insert_pos:]
                ])
        
            return Polygon(new_points)
                
        
        with p_timer("Sort points inside the polygons", verbose=verbose):
            sorted_polygons = [
                sort_group(pts, tps, ref)
                for pts, tps, ref in zip(points_groups, types_groups, self.points_array)
                ]

        # order = np.argsort(mapping)
        
        # return full_centers, full_centers_mapping, center_types
        return sorted_polygons
    
    def compute_quads_array(self, verbose: bool = False):
        """
        Method that constructs the three quadrilaterals inside each cell of the
        mesh. These quadrilaterals link each node of the cell to the centroïd 
        using the centers of adjacent edges.

        Returns numpy.ndarray of shape (3*self.num_cells, 4, 3)
        """

        with p_timer("Create edges", verbose=verbose):
            # simple renaming of usefull data
            cells = self.cells
            num_cells  = self.num_cells
            points_array = self.points_array
            cell_centers_array = self.cell_centers_array
            
            # Create all edges (with multiple defs) in order 
            #         [ 1st edge of all cells (num_cells list), 
            #           2nd edge of all cells (num_cells list),
            #           3rd edge of all cells (num_cells list) ]
            edges = np.vstack([
                cells[:, [0, 1]],
                cells[:, [1, 2]],
                cells[:, [2, 0]]
                ])
        
        with p_timer("Create edge centers", verbose=verbose):
            # get edges centers in this same order
            edge_centers_array_list = points_array[edges].mean(axis=1)
        
        
        with p_timer("Modify the edgecenters to the right shape", verbose=verbose):
            # Rearange edge centers to get a shape (num_cells, 3 points, 3 coords)
            edge_centers_array_block = np.array([
                edge_centers_array_list[:num_cells],
                edge_centers_array_list[num_cells:2*num_cells],
                edge_centers_array_list[2*num_cells:3*num_cells]
                ])
            edge_centers_array = np.moveaxis(
                edge_centers_array_block, 
                [0, 1, 2], 
                [1, 0, 2]
                )
        
        with p_timer("compute the cell to node coordinates", verbose=verbose):
            # Get the cell to node coordinates in the same shape (num_cells, 3 points, 3 coords)
            cell_node_array_ori = points_array[cells]
        
        with p_timer("compute the cells centers in the right shape", verbose=verbose):
            # get the cells centers in shape (num_cells, 3 times the center, 3 coords)
            cell_centers_array_ori_list = np.repeat(cell_centers_array, 3)
            cell_centers_array_ori_list_reshape = cell_centers_array_ori_list.reshape(
                num_cells, 3, 3
                )
            cell_centers_array_fin = np.moveaxis(
                cell_centers_array_ori_list_reshape, 
                [0, 1, 2], 
                [0, 2, 1]
                )
        
        with p_timer("Create the quads in a block", verbose=verbose):
            # Construct the quads from the points in the following order : 
            #          [ cell node, 1st edge point, cell center, previous edge point ]
            quads_array_block = np.array([
                cell_node_array_ori,
                edge_centers_array,
                cell_centers_array_fin,
                np.roll(edge_centers_array, 1, axis=1)
                ])
            
        with p_timer("Order the axis of the block", verbose=verbose):
            # Reorder coordinates in (num_cells, 3 quads, 4 points, 3 coords)
            quads_array_ordered = np.moveaxis(
                quads_array_block, 
                [0, 1, 2, 3],
                [2, 0, 1, 3]
                )
            
        with p_timer("reshape the quads array", verbose=verbose):
            # Reshape in (3*num_cells = num_quads, 4 points, 3 coords)
            quads_array = quads_array_ordered.reshape(3*num_cells, 4, 3)
        
        return quads_array
    
    
    
    # def compute_dual_mesh(self, batch_size=10_000):
    #     """
    #     Merge all quads attached to each node into a single polygon.
    
    #     Returns
    #     -------
    #     numpy.ndarray of shapely geometries
    #         Shape: (num_points,)
    #     """
    #     num_points = self.num_points
        
    #     with p_timer("Full timing for the quads creation"):
    #         # 1) Build quad polygons (vectorized, fast)
    #         quads_array = self.compute_quads_array()
    #         quads_xy = quads_array[..., :2]                   # (3*N, 4, 2) — still just a view

    #     with p_timer("Node to quad connectivity — flatten"):
    #         node_to_quad = self.compute_node_to_quad()
    
    #         flat_quad_ids = node_to_quad.ravel()
    #         flat_node_ids = np.repeat(np.arange(num_points), node_to_quad.shape[1])
    
    #         mask          = ~np.isnan(flat_quad_ids)
    #         flat_quad_ids = flat_quad_ids[mask].astype(int)
    #         flat_node_ids = flat_node_ids[mask]
    
    #         split_idx     = np.flatnonzero(np.diff(flat_node_ids)) + 1
    #         quad_id_groups = np.split(flat_quad_ids, split_idx)
    #         present_nodes  = flat_node_ids[np.concatenate([[0], split_idx])]
    
    #     node_polygons = np.full(num_points, None, dtype=object)
    
    #     with p_timer("Merge quads per node in batches"):
    #         p_ok("Merge quads per node in batches")
    #         for batch_start in range(0, len(present_nodes), batch_size):
    #             p_ok(f"    batch {batch_start//batch_size} sur {len(present_nodes)//batch_size}")
    #             batch_nodes  = present_nodes[batch_start : batch_start + batch_size]
    #             batch_groups = quad_id_groups[batch_start : batch_start + batch_size]
    
    #             # Collect unique quad ids needed for this batch only
    #             batch_quad_ids = np.unique(np.concatenate(batch_groups))
    
    #             # Build Shapely polygons only for this batch's quads
    #             batch_polys = polygons(quads_xy[batch_quad_ids])
    
    #             # Remap global quad ids to local indices within batch_polys
    #             remap = np.empty(quads_xy.shape[0], dtype=np.intp)
    #             remap[batch_quad_ids] = np.arange(len(batch_quad_ids))
    
    #             for nid, grp in zip(batch_nodes, batch_groups):
    #                 node_polygons[nid] = coverage_union_all(batch_polys[remap[grp]])
    
    #     return node_polygons
    
    
    
    def compute_dual_mesh(self, verbose: bool = False):
        import shapely
        num_points = self.num_points
        pts_xy = self.points_array[:, :2]
    
        with p_timer("Build quads array", verbose=verbose):
            quads_array = self.compute_quads_array()
            quads_xy    = quads_array[..., :2]              # (3N, 4, 2)
    
        with p_timer("Node-to-quad mapping — flatten", verbose=verbose):
            node_to_quad  = self.compute_node_to_quad()
            flat_quad_ids = node_to_quad.ravel()
            flat_node_ids = np.repeat(np.arange(num_points), node_to_quad.shape[1])
            mask          = ~np.isnan(flat_quad_ids)
            flat_quad_ids = flat_quad_ids[mask].astype(int)
            flat_node_ids = flat_node_ids[mask]
    
        with p_timer("Group boundaries", verbose=verbose):
            # Sort by node id only — chain-following will give us the right vertex order
            order           = np.argsort(flat_node_ids, kind="stable")
            sorted_quad_ids = flat_quad_ids[order]
            sorted_node_ids = flat_node_ids[order]
    
            split_pos     = np.flatnonzero(np.diff(sorted_node_ids)) + 1
            present_nodes = sorted_node_ids[np.concatenate([[0], split_pos])]
            group_starts  = np.concatenate([[0], split_pos])
            group_ends    = np.concatenate([split_pos, [len(sorted_quad_ids)]])
            group_sizes   = group_ends - group_starts
            n_present     = len(present_nodes)
    
        with p_timer("Chain-order quads per group + interior/boundary detection", verbose=verbose):
            # Hash ec_prev and ec_next to scalars for O(1) lookup
            # Use a view trick: treat each (x,y) pair as two int64s and fold into one int64
            def _hash_coords(arr):
                # arr: (M, 2) float64 to (M,) int64, robust for coords in [-1e9, 1e9]
                ix = np.round(arr[:, 0] * 1000).astype(np.int64)  # mm precision
                iy = np.round(arr[:, 1] * 1000).astype(np.int64)
                return ix * (10**9 + 7) + iy               # collision-resistant scalar
    
            ec_prev_hash = _hash_coords(quads_xy[sorted_quad_ids, 3, :])  # (M,)
            ec_next_hash = _hash_coords(quads_xy[sorted_quad_ids, 1, :])  # (M,)
    
            # Reorder each group to follow the chain ec_next[i] to ec_prev[i+1]
            # and detect is_interior = chain closes on itself
            chain_sorted_quad_ids = sorted_quad_ids.copy()
            is_interior           = np.zeros(n_present, dtype=bool)
    
            for i in range(n_present):
                s, e = group_starts[i], group_ends[i]
                k    = e - s
    
                ep_h = ec_prev_hash[s:e]                   # local ec_prev hashes
                en_h = ec_next_hash[s:e]                   # local ec_next hashes
    
                # Build: ec_prev_hash to local index
                prev_to_local = {h: j for j, h in enumerate(ep_h)}
    
                # Interior: every ec_next has a matching ec_prev to closed ring
                # Boundary: exactly one ec_next is unmatched (the open end)
                unmatched_next = [j for j, h in enumerate(en_h) if h not in prev_to_local]
    
                if len(unmatched_next) == 0:
                    # Interior: start from local index 0, follow chain
                    is_interior[i] = True
                    start_local    = 0
                else:
                    # Boundary: start from the quad whose ec_next is unmatched
                    # (i.e. the last quad in the chain — so the open boundary edge
                    #  ec_next to node to ec_prev_of_first is assembled correctly)
                    # Actually we want to start from the quad whose ec_prev is unmatched
                    unmatched_prev = [j for j, h in enumerate(ep_h) if h not in
                                      {h2: None for h2 in en_h}]
                    start_local    = unmatched_prev[0] if unmatched_prev else 0
    
                # Follow the chain from start_local
                ordered = np.empty(k, dtype=np.intp)
                cur     = start_local
                for step in range(k):
                    ordered[step] = cur
                    next_h        = en_h[cur]
                    cur           = prev_to_local.get(next_h, start_local)  # wraps for interior
    
                chain_sorted_quad_ids[s:e] = sorted_quad_ids[s:e][ordered]
    
            sorted_quad_ids = chain_sorted_quad_ids
            # Recompute coord views after reordering
            ec_prev_all = quads_xy[sorted_quad_ids, 3, :]
            ec_next_all = quads_xy[sorted_quad_ids, 1, :]
            cc_all      = quads_xy[sorted_quad_ids, 2, :]
    
        with p_timer("Assemble ring coordinates", verbose=verbose):
            bnd_mask   = ~is_interior
            extra      = np.where(is_interior, 1, 3)
            ring_sizes = 2 * group_sizes + extra
    
            total_coords = int(ring_sizes.sum())
            final_coords = np.empty((total_coords, 2), dtype=np.float64)
    
            ring_offsets = np.empty(n_present + 1, dtype=np.intp)
            ring_offsets[0] = 0
            ring_offsets[1:] = np.cumsum(ring_sizes)
            ring_start_pos = ring_offsets[:-1]
    
            # Interleave ec_prev (even) and cc (odd) for all M quads
            interleaved = np.empty((2 * len(sorted_quad_ids), 2), dtype=np.float64)
            interleaved[0::2] = ec_prev_all
            interleaved[1::2] = cc_all
    
            # Vectorized scatter of 2M values
            dest_offsets  = np.repeat(ring_start_pos,    2 * group_sizes)
            local_offsets = (np.arange(2 * len(sorted_quad_ids))
                             - np.repeat(2 * group_starts, 2 * group_sizes))
            final_coords[dest_offsets + local_offsets] = interleaved
    
            # Interior: closing coord = first ec_prev
            int_close_pos = ring_start_pos[is_interior] + 2 * group_sizes[is_interior]
            final_coords[int_close_pos] = ec_prev_all[group_starts[is_interior]]
    
            # Boundary: ec_next_of_last_quad, then the mesh node itself, then close
            bnd_base = ring_start_pos[bnd_mask] + 2 * group_sizes[bnd_mask]
            final_coords[bnd_base]     = ec_next_all[group_ends[bnd_mask] - 1]
            final_coords[bnd_base + 1] = pts_xy[present_nodes[bnd_mask]]       # ← the mesh node
            final_coords[bnd_base + 2] = ec_prev_all[group_starts[bnd_mask]]   # close ring
    
        with p_timer("Build Shapely polygons", verbose=verbose):
            geom_offsets = np.arange(n_present + 1, dtype=np.intp)
            all_polygons = from_ragged_array(
                shapely.GeometryType.POLYGON,
                final_coords,
                (ring_offsets, geom_offsets),
            )
    
        node_polygons = np.full(num_points, None, dtype=object)
        node_polygons[present_nodes] = all_polygons
        return node_polygons
    
    def compute_median_depth_per_node_tiled(
            self,
            X_bathy: np.ndarray,
            Y_bathy: np.ndarray,
            bathy: np.ndarray,
            points_array: np.ndarray,
            dual: np.ndarray,
            nodata: int = 0,
            min_points: int = 5,
            row_chunk: int = 256,       # number of bathy rows per chunk — controls memory
            verbose: bool = False
        ) -> np.ndarray:
    
        n_nodes = self.num_points
        nrows, ncols = bathy.shape
    
        x_flat = X_bathy.ravel()        # (nrows*ncols,)  — views, no copy
        y_flat = Y_bathy.ravel()
        z_flat = bathy.ravel()
    
        with p_timer("STR tree", verbose=verbose):
            strtree = STRtree(dual)
    
        node_depth_lists = [[] for _ in range(n_nodes)]
        chunk_pixels = row_chunk * ncols
    
        with p_timer("Spatial join — chunked", verbose=verbose):
            for chunk_start in range(0, nrows * ncols, chunk_pixels):
                chunk_end = min(chunk_start + chunk_pixels, nrows * ncols)
    
                # ── Build Shapely points for this chunk (vectorized, no Python loop) ──
                pts = points(x_flat[chunk_start:chunk_end],
                                     y_flat[chunk_start:chunk_end])
                
                pt_idx, poly_idx = strtree.query(pts, predicate="covered_by")  # original order, fixed predicate

                if len(poly_idx) == 0:
                    continue
                
                depths = z_flat[chunk_start + pt_idx]   # pt_idx correctly indexes into bathy points
                
                order       = np.argsort(poly_idx, kind="stable")
                sorted_poly = poly_idx[order]
                sorted_dep  = depths[order]
                
                unique_polys, first_occ = np.unique(sorted_poly, return_index=True)
                depth_groups = np.split(sorted_dep, first_occ[1:])
                
                for pid, dg in zip(unique_polys, depth_groups):
                    node_depth_lists[pid].append(dg)   # pid is now a genuine dual polygon index
    
        with p_timer("Median computing", verbose=verbose):
            depth_per_node = np.full(n_nodes, np.nan, dtype=np.float64)
            needs_interp   = np.ones(n_nodes, dtype=bool)
    
            for node_id, depth_list in enumerate(node_depth_lists):
                if depth_list:
                    all_depths = np.concatenate(depth_list)
                    if len(all_depths) >= min_points:
                        depth_per_node[node_id] = np.median(all_depths)
                        needs_interp[node_id]   = False
    
        with p_timer("Bilinear interpolation", verbose=verbose):
            n_interp = needs_interp.sum()
            if n_interp > 0:
                p_warning(f"  {n_interp}/{n_nodes} nodes sparse or empty — bilinear interpolation")
                x_axis = X_bathy[0, :]
                y_axis = Y_bathy[:, 0]
                interp = RegularGridInterpolator(
                    (y_axis, x_axis), bathy,
                    method="linear",
                    bounds_error=False,
                    fill_value=np.nan,
                )
                interp_xy = points_array[needs_interp, :2]
                depth_per_node[needs_interp] = interp(interp_xy[:, ::-1])
    
        with p_timer("Nearest-neighbour fallback", verbose=verbose):
            outside_mask = np.isnan(depth_per_node)
            if outside_mask.any():
                print(f"  {outside_mask.sum()}/{n_nodes} nodes outside extent — NN fallback")
                bathy_xy       = np.column_stack([x_flat, y_flat])
                tree           = cKDTree(bathy_xy)
                _, nearest_idx = tree.query(points_array[outside_mask, :2], workers=-1)
                depth_per_node[outside_mask] = z_flat[nearest_idx]
    
        return depth_per_node
    
    
    
    def compute_bathy_at_node(self, 
                              X_bathy: np.ndarray,
                              Y_bathy: np.ndarray,
                              bathy: np.ndarray,
                              nodata: int = 0,
                              min_points: int = 5,
                              row_chunk: int = 256, 
                              verbose: bool = False
                              ) -> np.ndarray:
        
        dual = self.compute_dual_mesh(verbose=verbose)
        depth_per_node = self.compute_median_depth_per_node_tiled(
                X_bathy, Y_bathy, bathy,
                self.points_array, dual,
                nodata=nodata,
                min_points=min_points,
                row_chunk=row_chunk,
                verbose=verbose)
        
        return depth_per_node
    
    
    def convert_tolosa_mesh_to_ww3(self, 
                                   bnd_tag_list: np.ndarray,
                                   X_bathy: np.ndarray, 
                                   Y_bathy: np.ndarray, 
                                   bathy: np.ndarray,
                                   verbose: bool = False):
        
        with p_timer("Computing bathy at nodes", verbose=verbose):
            # Compute depths at nodes
            new_depths = self.compute_bathy_at_node(X_bathy, 
                                                    Y_bathy, 
                                                    bathy,
                                                    verbose=verbose)
        
        
        with p_timer("Creating the equivalent ww3 Mesh object", 
                     verbose=verbose):
            # Create the node list
            points = deepcopy(self.points_array)
            points[:,2] = new_depths
        
            # Keep the triangular cells
            triangle = self.data.cells_dict['triangle']
            
            # Get the physical tags for line cells (block 0)
            line_tags = self.data.cell_data['gmsh:physical'][0]
            
            # Get the line cell connectivity (block 0)
            if 'line' in self.data.cells_dict.keys():
                line_cells = self.data.cells_dict['line']  # shape (n_lines, 2)
            else:
                p_error('Pas de line en frontière')
                return
            
            # Boolean mask: which lines belong to the selected tags
            mask = np.isin(line_tags, bnd_tag_list)
            
            # Get all node indices appearing in those lines
            vertex_list = np.unique(line_cells[mask].ravel())
            vertex = vertex_list.reshape((len(vertex_list), 1))
            
            # Create the cell blocks
            cells = {'vertex': vertex, 'triangle': triangle}
            
            # Create the data tags
            # BEWARE THE THIRD TAG ISSUE: I KEEP ONLY THE FIRST 2 TAGS INSTEAD OF 3
            cell_data = {
                'gmsh:physical': [
                    np.ones(len(cells['vertex'])),
                    np.zeros(len(cells['triangle']))
                    ], 
                'gmsh:geometrical': [
                    np.zeros(len(cells['vertex'])),
                    np.arange(1, len(cells['triangle'])+1)],
                # 'cell_tags': [
                #     np.zeros(len(cells['vertex'])),
                #     np.zeros(len(cells['triangle']))
                #     ]
                }
            
            # Create the meshio.Mesh object
            new_mesh = Mesh(points=points, 
                            cells=cells, 
                            cell_data=cell_data)
        
        with p_timer("Creating the processor of the new mesh", 
                     verbose=verbose):
            new_processor = MeshDataProcessor(new_mesh)
        
        return new_processor
    
    
    def save_mesh(self, 
                  path: str = './', 
                  filename: str = 'toto.msh',
                  file_format: str ='gmsh22', 
                  binary: bool = False,
                  float_fmt: str = '.8f'):
        
        filepath = os.path.join(path, filename)
        
        if 'gmsh:dim_tags' not in self.data.point_data.keys():
            self.data.point_data['gmsh:dim_tags'] = [len(self.data.points)*[0]]
            
        if file_format == "tolosa":
            self.data.write(filepath, 
                            file_format='gmsh22', 
                            binary=False,
                            float_fmt='.12f')
        
        elif file_format == "ww3":
            self.data.write(filepath, 
                            file_format='gmsh22', 
                            binary=False,
                            float_fmt='.8f')

            # Modify second line safely (stream rewrite)
            tmp_path = filepath + ".tmp"
    
            with open(filepath, "r") as fin, open(tmp_path, "w") as fout:
                fout.write(fin.readline())  # first line unchanged
    
                second_line = fin.readline()
                parts = second_line.split()
                parts[0] = "2"
                fout.write(" ".join(parts) + "\n")
    
                for line in fin:
                    fout.write(line)
    
            os.replace(tmp_path, filepath)
        
        else:
            self.data.write(filepath, 
                            file_format=file_format, 
                            binary=binary,
                            float_fmt=float_fmt)
            
        if file_format in ["gmsh", "tolosa"] and not binary:
            print('ici')
            projection_wkt = None
            if 'field_data' in self.data.__dict__.keys():
                if 'projection_wkt' in self.data.field_data.keys():
                    projection_wkt = self.data.field_data['projection_wkt']
                    if projection_wkt:
                        with open(filepath, "a", encoding="utf-8") as f:
                            f.write("$Projection\n")
                            f.write("WKT\n")
                            f.write(projection_wkt.strip() + "\n")
                            f.write("$EndProjection\n")
        
    # def compute_edge_to_segment(self):
    #     edge_to_cell = self.compute_edge_to_cell()
    #     cell_centers_array = self.cell_centers_array
    #     edge_centers_array = self.points_array[self.compute_edge_to_node()].mean(axis=1)
        
    #     flat_edge_to_cell = edge_to_cell.ravel()
    #     flat_edge_to_cell_mapping = np.repeat(np.arange(len(edge_to_cell)), 2)
        
    #     resu = np.array(len(edge_to_cell), 2, 3)
    #     resu[:, , 3] = 
    
    # def compute_node_to_segments(self):
    #     nodes = self.points_array
    #     node_to_edge = self.compute_node_to_edge()
    #     edge_to_segment = self.compute_edge_to_segment()
        
    
    # def compute_node_to_adjacent_boundary_lines_mapping(self):
    #     boundary_nodes = np.unique(self.lines.flatten())
    #     node_lines = {N: [] for N in boundary_nodes}

    #     for line_id, (N0, N1) in enumerate(self.lines):
    #         node_lines[N0].append(line_id)
    #         node_lines[N1].append(line_id)
    #     return node_lines
    
    # def compute_cell_to_cell_mapping(self):
    #     num_cells = self.cells.shape[0]
    
    #     # 1) Extract edges (3 per triangle)
    #     edges = np.vstack([
    #         self.cells[:, [0, 1]],
    #         self.cells[:, [1, 2]],
    #         self.cells[:, [2, 0]],
    #     ])
    
    #     # Normalize edges so (i, j) == (j, i)
    #     edges = np.sort(edges, axis=1)
    
    #     # Track which cell each edge came from
    #     cell_ids = np.repeat(np.arange(num_cells), 3)
    
    #     # 2) Group edges
    #     edge_to_cells = defaultdict(list)
    #     for edge, cid in zip(edges, cell_ids):
    #         edge_to_cells[tuple(edge)].append(cid)
    
    #     # 3) Build adjacency
    #     neighbors = [set() for _ in range(num_cells)]
    
    #     for cell_list in edge_to_cells.values():
    #         if len(cell_list) == 2:
    #             c0, c1 = cell_list
    #             neighbors[c0].add(c1)
    #             neighbors[c1].add(c0)
    #         # len == 1 to boundary edge
    #         # len > 2 to non-manifold (ignored or handle separately)
    
    #     # Convert sets to arrays
    #     return [np.array(sorted(n), dtype=np.int32) for n in neighbors]
    
    def _extract_boundary_edges(self) -> list:
        """
        Extract boundary edges.
        
        For 2D meshes, boundary edges are those that belong to only one cell.
        
        Returns:
            list: List of boundary edge node pairs (as tuples)
        """
        boundary_edges = []
        
        # For triangular meshes, we can detect boundary edges
        if self.cell_type == 'all_Triangle':
            # Build edge dictionary
            edge_count = {}
            
            for cell in self.cells:
                # For triangles, get the three edges
                edges = [
                    tuple(sorted([cell[0], cell[1]])),
                    tuple(sorted([cell[1], cell[2]])),
                    tuple(sorted([cell[2], cell[0]]))
                ]
                
                for edge in edges:
                    edge_count[edge] = edge_count.get(edge, 0) + 1
            
            # Boundary edges appear only once
            boundary_edges = [edge for edge, count in edge_count.items() if count == 1]
        
        return boundary_edges
    
    def _extract_edgepoints(self) -> typing.Tuple[np.ndarray, int]:
        """
        Extract unique boundary point coordinates.
        
        Returns:
            Tuple of (edgepoints_array, num_edgepoints)
        """
        # Extract unique boundary point indices
        boundary_indices = set()
        for edge in self.boundary_edges:
            boundary_indices.update(edge)
            
        boundary_indices = np.array(sorted(boundary_indices))
        
        if len(boundary_indices) > 0:
            edgepoints_array = self.points_array[boundary_indices]
        else:
            edgepoints_array = np.array([])
        
        return edgepoints_array, len(edgepoints_array)
    
    def _create_boundary_polygon_list(self) -> list:
        """
        Create list of boundary polygons from boundary edges.
        
        Returns:
            list: List of Shapely Polygon objects
        """
        if not self.boundary_edges:
            return []
        
        # Convert boundary edges to LineString objects
        list_coords_boundary_edges = []
        for edge in self.boundary_edges:
            coords = self.points_array[list(edge)]
            list_coords_boundary_edges.append(coords)
        
        list_LineString = [LineString(coords) for coords in list_coords_boundary_edges]
        
        # Use polygonize to create polygons from line segments
        boundary_polygon_list = [geom for geom in polygonize(list_LineString).geoms]
        
        return boundary_polygon_list
    
    def _create_boundary_polygon(self) -> Polygon:
        """
        Create a single boundary polygon with holes.
        
        The largest polygon by area is used as the shell, and smaller polygons as holes.
        
        Returns:
            Polygon: Shapely Polygon object
        """
        boundary_polygon_list = self.boundary_polygon_list
        
        if not boundary_polygon_list:
            # Return empty polygon if no boundaries
            return Polygon()
        
        if len(boundary_polygon_list) == 1:
            return boundary_polygon_list[0]
        
        # Find the polygon with largest area (outer boundary)
        all_polygons_area = [geom.area for geom in boundary_polygon_list]
        max_area_idx = all_polygons_area.index(max(all_polygons_area))
        biggest_polygon = boundary_polygon_list[max_area_idx]
        
        # All other polygons are holes
        other_polygons = [boundary_polygon_list[i] 
                         for i in range(len(boundary_polygon_list)) 
                         if i != max_area_idx]
        
        # Create polygon with shell and holes
        boundary_polygon = Polygon(shell=biggest_polygon.exterior.coords, 
                                  holes=[p.exterior.coords for p in other_polygons])
        
        return boundary_polygon
    
    def compute_node_domain(self):
        node_lines = self.compute_node_to_adjacent_boundary_lines_mapping()
        node_cells = self.compute_node_to_cell_mapping()
        
        coordinate_list = [np.array([]) for _ in range(self.num_points)]
        for N in range(self.num_points):
            coordinate_list[N] = self.cell_centers_array[node_cells[N]]
            if N in node_lines.keys():
                coordinate_list[N] = np.concatenate((coordinate_list[N], self.line_centers_array[node_lines[N]]))
        polygon_list = [Polygon(l).convex_hull for l in coordinate_list] # ICI C'est FAUX aux frontières concaves mais l'alternative est horrible.
        return polygon_list


# =============================================================================
# LEGACY PROCESSORS
# =============================================================================
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
    