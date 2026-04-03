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
from meshio import Mesh, CellBlock
import numpy as np
from pandas import unique

from scipy.interpolate import LinearNDInterpolator, NearestNDInterpolator, RegularGridInterpolator
from scipy.spatial import cKDTree
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from shapely import LineString, Polygon
from shapely import points, linestrings
from shapely import polygonize
from shapely import STRtree, from_ragged_array
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
        self.index_vertex = self.cell_types.index('vertex') if 'vertex' in self.cell_types else None
        
        self.cells = self.data.cells[self.index_triangle].data.astype(int) if 'triangle' in self.cell_types else np.array([])
        self.num_cells = len(self.cells)
        self.cell_centers_array = self._create_cell_center_array()
        
        self.lines = self.data.cells[self.index_line].data.astype(int) if 'line' in self.cell_types else np.array([])
        self.num_lines = len(self.lines)
        self.line_centers_array = self._create_line_center_array()
        
        self.vertexes = self.data.cells[self.index_vertex].data.astype(int) if 'vertex' in self.cell_types else np.array([])
        self.num_vertexes = len(self.vertexes)
        
        # Extract cell and point data in dict
        self.point_data = data.point_data.copy() if data.point_data else {}
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


# =============================================================================
#     SIMPLE REFORMATTING OF CONTENTS
# =============================================================================
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
    
    
# =============================================================================
#     ALL COMPUTATIONS OF USEFUL MAPPINGS
# =============================================================================


    def compute_cell_to_node(self):
        return (self.cells)
    
    def compute_line_to_node(self):
        return (self.lines)
    
    def compute_vertex_to_node(self):
        return (self.vertexes)

    def compute_max_node_cell_adjacency(self):
        """
        Computes the max number of adjacent cells to a node

        Returns int
        """
        values, counts = np.unique(self.cells, return_counts=True)
        idx = counts.argmax()
        return int(counts[idx])
    
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
        # print(edges)
        # 2. Sort nodes inside each edge (undirected)
        edges = np.sort(edges, axis=1)
    
        # 3. Inverse mapping of Unique edges
        _, edge_ids = np.unique(edges, axis=0, return_inverse=True)
    
        # 4. Reshape back to (num_cells, 3)
        cell_to_edge = edge_ids.ravel().reshape(3, self.num_cells).T
    
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
        
        if len(self.check_duplicates('triangle')):
            p_error("Cannot compute edge_to_cell because of duplicate cells")
            return np.array([])
        
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
        # cell_ids = np.repeat(np.arange(n_cells), 3)
        cell_ids = np.tile(np.arange(n_cells), 3)
    
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
    
    
    def compute_node_to_line(self):
        """
        Computes the node to boundary-line mapping. The number of adjacent
        lines varies (typically 1 or 2). NaN-padded like node_to_cell.

        Returns np.ndarray shape (num_points, max_adj)
        """
        lines      = self.lines                                    # (M, 2)
        num_lines  = self.num_lines
        num_points = self.num_points
        
        if not num_lines:
            p_warning("No lines")
            return np.array([])
        
        max_adj  = int(np.max(np.bincount(lines.ravel(), minlength=num_points)))

        nodes    = lines.ravel()                                   # (2*M,)
        line_ids = np.repeat(np.arange(num_lines), 2)             # (2*M,)

        order    = np.argsort(nodes)
        nodes    = nodes[order]
        line_ids = line_ids[order]

        counts    = np.bincount(nodes, minlength=num_points)
        offsets   = np.cumsum(np.r_[0, counts[:-1]])
        local_idx = np.arange(nodes.size) - offsets[nodes]

        node_to_line = np.full((num_points, max_adj), np.nan)
        node_to_line[nodes, local_idx] = line_ids
        node_to_line.sort(axis=1)

        return node_to_line


    def compute_line_to_cell(self):
        """
        Computes the boundary-line to cell mapping by intersecting the
        node_to_cell rows of each line's two endpoints.

        A cell is adjacent to a line if it contains *both* endpoint nodes,
        which is exactly the intersection of node_to_cell[n1] and
        node_to_cell[n2].

        For true boundary lines the result has 1 adjacent cell;
        interior matched lines may have 2.

        Returns np.ndarray shape (num_lines, max_adj), NaN-padded.
        """
        if not self.num_lines:
            p_warning("No lines")
            return np.array([])
        node_to_cell = self.compute_node_to_cell()          # (N, max_adj)

        n1 = self.lines[:, 0]                               # (M,)
        n2 = self.lines[:, 1]                               # (M,)

        A = node_to_cell[n1]                                # (M, max_adj)  cells of node 1
        B = node_to_cell[n2]                                # (M, max_adj)  cells of node 2

        # Broadcast comparison: which cells of A also appear in B?
        # Shape: (M, max_adj_A, max_adj_B) — max_adj is typically 6-8, so fine
        matching = (A[:, :, None] == B[:, None, :]) & ~np.isnan(A[:, :, None])
        in_both = matching.any(axis=2)                         # (M, max_adj_A)

        # Collect matched cell ids, replacing non-matches with NaN
        shared = np.where(in_both, A, np.nan)               # (M, max_adj_A)

        # Pack valid values to the left: np.sort pushes NaN to the end.
        # Then take the first 2 columns (boundary -> 1 cell, shared edge -> 2).
        line_to_cell = np.sort(shared, axis=1)[:, :2]       # (M, 2)

        return line_to_cell


    def compute_cell_to_line(self):
        """
        Computes the cell to boundary-line mapping by intersecting
        node_to_line rows for each pair of nodes in the triangle.

        A line is adjacent to a cell if both its endpoint nodes belong
        to that cell, i.e. it lies on one of the 3 edges (ab, bc, ca).
        Each edge yields at most 1 boundary line.

        Returns np.ndarray shape (num_cells, 3), NaN-padded.
        Columns correspond to edges ab, bc, ca (sorted, NaN last).
        """
        node_to_line = self.compute_node_to_line()          # (N, max_adj)

        if not len(node_to_line):
            p_warning("No node_to_line mapping")
            return np.array([])

        A = node_to_line[self.cells[:, 0]]                  # (K, max_adj)
        B = node_to_line[self.cells[:, 1]]
        C = node_to_line[self.cells[:, 2]]

        def _intersect(X, Y):
            """First line-id shared between row-paired arrays X and Y -> (K, 1)."""
            match   = (X[:, :, None] == Y[:, None, :]) & ~np.isnan(X[:, :, None])
            in_both = np.where(match.any(axis=2), X, np.nan)   # (K, max_adj)
            return np.sort(in_both, axis=1)[:, 0:1]            # (K, 1), NaN if none

        edge_ab = _intersect(A, B)                          # (K, 1)
        edge_bc = _intersect(B, C)                          # (K, 1)
        edge_ca = _intersect(C, A)                          # (K, 1)

        # Stack and sort so NaNs go last                    # (K, 3)
        cell_to_line = np.sort(np.hstack([edge_ab, edge_bc, edge_ca]), axis=1)

        return cell_to_line


    def compute_node_to_vertex(self):
        """
        Computes the node to vertex mapping.
        self.vertexes is the vertex_to_node mapping of shape (V, 1).
        Each node is marked by at most one vertex, so the output is
        typically (num_points, 1) with NaN for unmarked nodes.

        Returns np.ndarray shape (num_points, max_adj), NaN-padded.
        """
        num_points   = self.num_points
        num_vertexes = self.num_vertexes
        
        if not num_vertexes:
            p_warning("No vertexes")
            return np.array([])

        nodes      = self.vertexes.ravel()                          # (V,)
        vertex_ids = np.arange(num_vertexes)                        # (V,)

        max_adj   = int(np.max(np.bincount(nodes, minlength=num_points)))

        order      = np.argsort(nodes)
        nodes      = nodes[order]
        vertex_ids = vertex_ids[order]

        counts    = np.bincount(nodes, minlength=num_points)
        offsets   = np.cumsum(np.r_[0, counts[:-1]])
        local_idx = np.arange(nodes.size) - offsets[nodes]

        node_to_vertex = np.full((num_points, max_adj), np.nan)
        node_to_vertex[nodes, local_idx] = vertex_ids

        return node_to_vertex

    def compute_cell_to_cell(self):
        etc = self.compute_edge_to_cell()
        if not len(etc):
            p_error("Not able to compute cell_to_cell because of missing edge_to_cell mapping")
            return np.array([])
            
        cte = self.compute_cell_to_edge()
        cell_indexes = np.repeat(np.arange(self.num_cells), 6).reshape((self.num_cells, 3, 2))
        
        mask = (etc[cte] != cell_indexes)
        
        ctc_list = etc[cte][mask]
        
        ctc = np.sort(ctc_list.reshape((self.num_cells, 3)), axis=-1)
        
        return ctc
    
    
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

        return sorted_polygons
    
    
    def compute_quads_array(self, verbose: bool = False):
        """
        Method that constructs the three quadrilaterals inside each cell of the
        mesh. These quadrilaterals link each node of the cell to the centroïd 
        using the centers of adjacent edges.

        Returns numpy.ndarray of shape (3*self.num_cells, 4, 3)
        """

        with p_timer("Creating the edges", verbose=verbose):
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
        
        with p_timer("Creating the edge centers", verbose=verbose):
            # get edges centers in this same order
            edge_centers_array_list = points_array[edges].mean(axis=1)
        
        
        with p_timer("Modifying the edgecenters to the right shape", verbose=verbose):
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
        
        with p_timer("Computing the cell to node coordinates", verbose=verbose):
            # Get the cell to node coordinates in the same shape (num_cells, 3 points, 3 coords)
            cell_node_array_ori = points_array[cells]
        
        with p_timer("Computing the cells centers in the right shape", verbose=verbose):
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
        
        with p_timer("Creating the quads in a block", verbose=verbose):
            # Construct the quads from the points in the following order : 
            #          [ cell node, 1st edge point, cell center, previous edge point ]
            quads_array_block = np.array([
                cell_node_array_ori,
                edge_centers_array,
                cell_centers_array_fin,
                np.roll(edge_centers_array, 1, axis=1)
                ])
            
        with p_timer("Ordering the axis of the block", verbose=verbose):
            # Reorder coordinates in (num_cells, 3 quads, 4 points, 3 coords)
            quads_array_ordered = np.moveaxis(
                quads_array_block, 
                [0, 1, 2, 3],
                [2, 0, 1, 3]
                )
            
        with p_timer("Reshaping the quads array", verbose=verbose):
            # Reshape in (3*num_cells = num_quads, 4 points, 3 coords)
            quads_array = quads_array_ordered.reshape(3*num_cells, 4, 3)
        
        return quads_array
    
    
    def compute_all_boundary_edges(self) -> np.array:
        """
        Returns a np.array of pairs of node indices forming all boundary edges.
        """
        etc = self.compute_edge_to_cell() # np.nan as second element if no cell
        if not len(etc):
            p_error("Not able to compute all_boundary_edges because of missing edge_to_cell mapping")
            return np.array([])
        
        etn = self.compute_edge_to_node()
        
        return etn[np.isnan(etc[:, 1])]
    
    
    def compute_all_boundary_nodes(self) -> np.array:
        """
        Returns a np.array of node indices forming all boundary nodes.
        """
        bnd_edge = self.compute_all_boundary_edges()
        if not len(bnd_edge):
            p_error("Not able to compute all_boundary_nodes because of missing boundary_edges mapping")
            return np.array([])
        
        return np.unique(bnd_edge.ravel())
    
    
    def compute_all_points_array_edge(self) -> typing.Tuple[np.ndarray, int]:
        """
        Extract unique boundary point coordinates.
        
        Returns:
            edgepoints_array
        """
        bnd_edges = self.compute_all_boundary_edges()
        bnd_nodes = np.unique(bnd_edges.ravel())
        
        return self.points_array[bnd_nodes]
    
    
    def compute_cell_groups(self):
        ctc = self.compute_cell_to_cell()
        n_cells = self.num_cells
        
        if not len(ctc) == n_cells:
            p_error("Not able to compute cell_groups because of missing cell_to_cell mapping")
            return []
    
        row_ids, col_positions = np.where(~np.isnan(ctc))
        neighbor_ids = ctc[row_ids, col_positions].astype(np.int32)
        row_ids = row_ids.astype(np.int32)
    
        mask = row_ids < neighbor_ids
        row_ids, neighbor_ids = row_ids[mask], neighbor_ids[mask]
    
        data = np.ones(len(row_ids), dtype=np.int8)
        adjacency = csr_matrix((data, (row_ids, neighbor_ids)), shape=(n_cells, n_cells))
    
        n_groups, labels = connected_components(adjacency, directed=False)
    
        # Sort cells by label for efficient slicing
        order = np.argsort(labels, kind="stable")
        sorted_labels = labels[order]
        split_points = np.where(np.diff(sorted_labels))[0] + 1
        groups = np.split(order, split_points)
    
        return groups
    
    
# =============================================================================
#     ALL MESH CHECKING
# =============================================================================
    def check_bottleneck_cells(self,
                                numbering: str = 'meshio') -> np.ndarray:
        """
        Returns an array of indexes of cells composed only of all boundary nodes.
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based block-local indices;
                    'gmsh'             — 1-based global gmsh indices.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        bnd_nodes = self.compute_all_boundary_nodes()
        if not len(bnd_nodes):
            p_error("Cannot compute bottleneck cells because of missing boundary_nodes")
            return np.array([])
    
        is_boundary    = np.isin(self.cells, bnd_nodes)
        bottleneck_mask = is_boundary.all(axis=1)
        meshio_indices = np.where(bottleneck_mask)[0]
    
        if numbering == 'gmsh':
            return self.meshio_to_global(cell_indices_meshio=meshio_indices)['cell_indices']
        return meshio_indices
    
    
    def check_floating_cells(self,
                              numbering: str = 'meshio') -> np.ndarray:
        """
        Returns an array of indexes of unconnected triangles to the main mesh.
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based block-local indices;
                    'gmsh'             — 1-based global gmsh indices.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        groups   = self.compute_cell_groups()
        N_groups = len(groups)
        if N_groups < 2:
            return np.array([])
    
        len_groups     = np.array([len(g) for g in groups])
        small_groups   = [groups[i] for i in range(N_groups)
                          if len_groups[i] != max(len_groups)]
        meshio_indices = np.concatenate(small_groups)
    
        if numbering == 'gmsh':
            return self.meshio_to_global(cell_indices_meshio=meshio_indices)['cell_indices']
        return meshio_indices
    
    
    def check_floating_nodes(self,
                              numbering: str = 'meshio') -> np.ndarray:
        """
        Returns an array of node indexes not referenced by any triangle.
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based node indices;
                    'gmsh'             — 1-based gmsh node indices.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        used_by_triangle = np.unique(self.cells)
        all_nodes        = np.arange(self.num_points)
        meshio_indices   = np.setdiff1d(all_nodes, used_by_triangle)
    
        if numbering == 'gmsh':
            return self.meshio_to_global(node_indices_meshio=meshio_indices)['node_indices']
        return meshio_indices
    
    
    def check_floating_vertexes(self,
                                 numbering: str = 'meshio') -> np.ndarray:
        """
        Returns a np.array of vertex indices for which the node does not
        touch any triangle.
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based block-local indices;
                    'gmsh'             — 1-based global gmsh indices.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        if not self.num_vertexes:
            return np.array([])
    
        used_by_triangle = np.unique(self.cells)
        floating_mask    = ~np.isin(self.vertexes.ravel(), used_by_triangle)
        meshio_indices   = np.where(floating_mask)[0]
    
        if numbering == 'gmsh':
            return self.meshio_to_global(vertex_indices_meshio=meshio_indices)['vertex_indices']
        return meshio_indices
    
    
    def check_floating_lines(self,
                              numbering: str = 'meshio') -> np.ndarray:
        """
        Returns a np.array of line indices that are not connected to any
        triangular cell.
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based block-local indices;
                    'gmsh'             — 1-based global gmsh indices.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        if not self.num_lines:
            return np.array([])
    
        ltc            = self.compute_line_to_cell()
        meshio_indices = np.arange(self.num_lines)[np.isnan(ltc[:, 0])]
    
        if numbering == 'gmsh':
            return self.meshio_to_global(line_indices_meshio=meshio_indices)['line_indices']
        return meshio_indices
    
    
    def check_lines_not_boundary(self,
                                  numbering: str = 'meshio') -> np.ndarray:
        """
        Returns indices of line elements connected to 2 triangular cells
        (i.e. interior lines, not true boundary lines).
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based block-local indices;
                    'gmsh'             — 1-based global gmsh indices.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        if not self.num_lines:
            return np.array([], dtype=int)
    
        ltc            = self.compute_line_to_cell()           # (L, 2)
        interior_mask  = ~np.isnan(ltc[:, 1])
        meshio_indices = np.where(interior_mask)[0]
    
        if numbering == 'gmsh':
            return self.meshio_to_global(line_indices_meshio=meshio_indices)['line_indices']
        return meshio_indices
    
    
    def check_boundary_edges_not_in_lines(self,
                                           numbering: str = 'meshio') -> np.ndarray:
        """
        Returns a np.array of pairs of boundary node indices which are not
        referenced as lines.
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based node indices in each pair;
                    'gmsh'             — 1-based gmsh node indices in each pair.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        boundary_edges = np.sort(self.compute_all_boundary_edges(), axis=-1)
        if not len(boundary_edges):
            p_warning("No boundary edges")
            return np.array([])
    
        if not self.num_lines:
            p_warning("No lines")
            result = boundary_edges
        else:
            lines = np.sort(self.lines, axis=-1)
            dtype              = np.dtype([('i', boundary_edges.dtype),
                                           ('j', boundary_edges.dtype)])
            boundary_edges_view = boundary_edges.view(dtype).reshape(-1)
            lines_view          = lines.view(dtype).reshape(-1)
            diff               = np.setdiff1d(boundary_edges_view, lines_view)
            result             = diff.view(boundary_edges.dtype).reshape(-1, 2)
    
        if numbering == 'gmsh':
            # Convert the flat list of node indices and reshape back to pairs
            flat           = result.ravel()
            flat_gmsh      = self.meshio_to_global(node_indices_meshio=flat)['node_indices']
            return flat_gmsh.reshape(-1, 2)
        return result

    def check_cells_angles(self, 
                           threshold: float = 10,
                           numbering: str   = 'meshio') -> np.ndarray:
        """
        Returns a np.array of node index for triangular cells that display at 
        least one angle smaller than threshold
    
        Parameters
        ----------
        threshold   : minimum angle threshold accepted.
        numbering  : 'meshio' (default) — returns 0-based indices local to the
                     triangle block; 'gmsh' — returns 1-based global gmsh indices.
        """
        triangles = self.points_array[self.cells][:,:,:2]
        
        # triangles shape: (N, 3, 2)
        A = triangles[:, 0, :]
        B = triangles[:, 1, :]
        C = triangles[:, 2, :]
        
        # Edge vectors
        AB = B - A
        AC = C - A
        BA = A - B
        BC = C - B
        CA = A - C
        CB = B - C
        
        def angle(u, v):
            dot = np.einsum('ij,ij->i', u, v)
            norm_u = np.linalg.norm(u, axis=1)
            norm_v = np.linalg.norm(v, axis=1)
            cos_theta = dot / (norm_u * norm_v)
            
            # numerical safety
            cos_theta = np.clip(cos_theta, -1.0, 1.0)
            
            return np.arccos(cos_theta)
        
        angle_A = angle(AB, AC)
        angle_B = angle(BA, BC)
        angle_C = angle(CA, CB)
        
        angles = np.rad2deg(np.stack([angle_A, angle_B, angle_C], axis=1))
        mask_angles = angles.min(axis=-1)<threshold
        
        meshio_indices = np.arange(self.num_cells)[mask_angles]
    
        if numbering == 'gmsh':
            return self.meshio_to_global(cell_indices_meshio=meshio_indices)['cell_indices']
    
        return meshio_indices
    
    
    def check_cell_size(self, 
                        min_reso: float = .1,
                        numbering: str   = 'meshio') -> np.ndarray:
        """
        Returns indices of triangular cells whose mean edge length is lower
        than min_reso.
    
        Parameters
        ----------
        min_reso   : minimum mean edge length threshold.
        numbering  : 'meshio' (default) — returns 0-based indices local to the
                     triangle block; 'gmsh' — returns 1-based global gmsh indices.
        """
        triangles = self.points_array[self.cells][:,:,:2]
        
        # Edge vectors
        e0 = triangles[:, 1] - triangles[:, 0]
        e1 = triangles[:, 2] - triangles[:, 1]
        e2 = triangles[:, 0] - triangles[:, 2]
    
        # Edge lengths
        l0 = np.linalg.norm(e0, axis=1)
        l1 = np.linalg.norm(e1, axis=1)
        l2 = np.linalg.norm(e2, axis=1)
    
        mean_length = (l0 + l1 + l2) / 3.0
        
        meshio_indices = np.where(mean_length < min_reso)[0]
    
        if numbering == 'gmsh':
            return self.meshio_to_global(cell_indices_meshio=meshio_indices)['cell_indices']
    
        return meshio_indices
    
    def check_duplicates(self,
                     element_type: str = "line",
                     decimals:     int = 8,
                     numbering:    str = 'meshio') -> np.ndarray:
        """
        Returns a np.array of indexes of elements found as duplicate of
        previous elements. element_type must be one of 'node', 'vertex', 'line'
        or 'triangle'.
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based block-local / node indices;
                    'gmsh'             — 1-based global gmsh indices.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        if element_type == "node":
            elements = self.points_array[:, :2].round(decimals=decimals)
        elif element_type == "vertex":
            elements = self.vertexes
        elif element_type == "line":
            elements = self.lines
        elif element_type == "triangle":
            elements = self.cells
        else:
            raise ValueError("element_type must be 'node', 'vertex', 'line' or 'triangle'")
    
        if elements is None or len(elements) == 0:
            return np.array([], dtype=int)
    
        if element_type == "node":
            sorted_elements = np.ascontiguousarray(elements, dtype=np.float64)
        else:
            sorted_elements = np.sort(
                np.ascontiguousarray(elements, dtype=np.int64), axis=1
            )
    
        row_dtype = np.dtype((np.void, sorted_elements.dtype.itemsize * sorted_elements.shape[1]))
        row_view  = sorted_elements.view(row_dtype).ravel()
    
        _, first_occurrence        = np.unique(row_view, return_index=True)
        is_first                   = np.zeros(len(elements), dtype=bool)
        is_first[first_occurrence] = True
    
        meshio_indices = np.where(~is_first)[0]
    
        if numbering == 'gmsh':
            return self._meshio_indices_to_gmsh(meshio_indices, element_type)
        return meshio_indices


    def check_duplicates_local(self,
                                local_indices: np.ndarray,
                                element_type:  str = "line",
                                decimals:      int = 8,
                                numbering:     str = 'meshio') -> np.ndarray:
        """
        Returns a np.array of indices of elements found as duplicates,
        restricted to local_indices. An element is flagged only if an earlier
        global copy (local or not) already exists.
        element_type must be one of 'node', 'vertex', 'line' or 'triangle'.
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based block-local / node indices;
                    'gmsh'             — 1-based global gmsh indices.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        local_indices = np.atleast_1d(local_indices)
    
        if element_type == "node":
            elements = self.points_array[:, :2].round(decimals=decimals)
        elif element_type == "vertex":
            elements = self.vertexes
        elif element_type == "line":
            elements = self.lines
        elif element_type == "triangle":
            elements = self.cells
        else:
            raise ValueError("element_type must be 'node', 'vertex', 'line' or 'triangle'")
    
        if elements is None or len(elements) == 0 or len(local_indices) == 0:
            return np.array([], dtype=int)
    
        if element_type == "node":
            sorted_elements = np.ascontiguousarray(elements, dtype=np.float64)
        else:
            sorted_elements = np.sort(
                np.ascontiguousarray(elements, dtype=np.int64), axis=1
            )
    
        row_dtype = np.dtype((np.void, sorted_elements.dtype.itemsize * sorted_elements.shape[1]))
        row_view  = sorted_elements.view(row_dtype).ravel()
    
        _, first_occurrence        = np.unique(row_view, return_index=True)
        is_first                   = np.zeros(len(elements), dtype=bool)
        is_first[first_occurrence] = True
    
        meshio_indices = local_indices[~is_first[local_indices]]
    
        if numbering == 'gmsh':
            return self._meshio_indices_to_gmsh(meshio_indices, element_type)
        return meshio_indices
    
    
    def check_degenerate(self,
                         element_type: str = "triangle",
                         numbering:    str = 'meshio') -> np.ndarray:
        """
        Returns a np.array of indexes of degenerate elements (elements with two
        or more identical node indices). element_type must be 'line' or 'triangle'.
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based block-local indices;
                    'gmsh'             — 1-based global gmsh indices.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        if element_type == "line":
            elements = self.lines
        elif element_type == "triangle":
            elements = self.cells
        else:
            raise ValueError("element_type must be 'line' or 'triangle'")
    
        if elements is None or len(elements) == 0:
            return np.array([], dtype=int)
    
        if element_type == "line":
            degen_mask = elements[:, 0] == elements[:, 1]
        else:
            n0, n1, n2 = elements[:, 0], elements[:, 1], elements[:, 2]
            degen_mask  = (n0 == n1) | (n1 == n2) | (n0 == n2)
    
        meshio_indices = np.where(degen_mask)[0]
    
        if numbering == 'gmsh':
            return self._meshio_indices_to_gmsh(meshio_indices, element_type)
        return meshio_indices
    
    
    def check_degenerate_local(self,
                                local_indices: np.ndarray,
                                element_type:  str = "triangle",
                                numbering:     str = 'meshio') -> np.ndarray:
        """
        Returns a np.array of indices of degenerate elements (elements with two
        or more identical node indices), restricted to local_indices.
        element_type must be 'line' or 'triangle'.
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based block-local indices;
                    'gmsh'             — 1-based global gmsh indices.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        local_indices = np.atleast_1d(local_indices)
    
        if element_type == "line":
            elements = self.lines
        elif element_type == "triangle":
            elements = self.cells
        else:
            raise ValueError("element_type must be 'line' or 'triangle'")
    
        if elements is None or len(elements) == 0 or len(local_indices) == 0:
            return np.array([], dtype=int)
    
        subset = elements[local_indices]
    
        if element_type == "line":
            degen_mask = subset[:, 0] == subset[:, 1]
        else:
            n0, n1, n2 = subset[:, 0], subset[:, 1], subset[:, 2]
            degen_mask  = (n0 == n1) | (n1 == n2) | (n0 == n2)
    
        meshio_indices = local_indices[degen_mask]
    
        if numbering == 'gmsh':
            return self._meshio_indices_to_gmsh(meshio_indices, element_type)
        return meshio_indices
    
    
    def check_triangle_orientation(self,
                                   numbering: str = 'meshio') -> np.ndarray:
        """
        Returns a np.array of indexes of triangular cells in clockwise
        direction (these triangles should be swapped).
    
        Parameters
        ----------
        numbering : 'meshio' (default) — 0-based block-local indices;
                    'gmsh'             — 1-based global gmsh indices.
        """
        if numbering not in ('meshio', 'gmsh'):
            raise ValueError(f"numbering must be 'meshio' or 'gmsh', got {numbering!r}.")
    
        points_array = self.points_array
        cells        = self.cells
    
        A = points_array[cells[:, 0]]
        B = points_array[cells[:, 1]]
        C = points_array[cells[:, 2]]
    
        cross = (B[:, 0]-A[:, 0])*(C[:, 1]-A[:, 1]) - (B[:, 1]-A[:, 1])*(C[:, 0]-A[:, 0])
    
        meshio_indices = np.where(cross < 0)[0]
    
        if numbering == 'gmsh':
            return self.meshio_to_global(cell_indices_meshio=meshio_indices)['cell_indices']
        return meshio_indices
    
    
    def check_validity(self, 
                       threshold: float=10, 
                       min_reso:  float=.1, 
                       numbering: str = 'meshio',
                       verbose:   bool=False) -> dict:
        """
        Returns a dict of basic issues found in the mesh:
          - floating_nodes/vertexes/lines : indexes of elements not connected 
          to at least one triangular cell (should be removed)
          - duplicate_nodes/vertexes/lines/cells : indexes of elements that are
          duplicates of previous element (should be removed)
          
        Parameters
        ----------
        threshold   : minimum angle threshold accepted.
        min_reso    : minimum mean edge length threshold.
        numbering   : 'meshio' (default) — 0-based block-local indices;
                      'gmsh'             — 1-based global gmsh indices.
        """
        issues = {}
    
        # --- Floating elements (not referenced by any triangle) ---
        with p_timer("Looking for floating_nodes", verbose=verbose):
            issues["floating_nodes"] = self.check_floating_nodes(numbering=numbering)
        with p_timer("Looking for floating_vertexes", verbose=verbose):
            issues["floating_vertexes"] = self.check_floating_vertexes(numbering=numbering)
        with p_timer("Looking for floating_lines", verbose=verbose):
            issues["floating_lines"] = self.check_floating_lines(numbering=numbering)
        
        # --- Duplicate elements ---
        with p_timer("Looking for duplicate_nodes", verbose=verbose):
            issues["duplicate_nodes"] = self.check_duplicates("node", numbering=numbering)
        with p_timer("Looking for duplicate_vertexes", verbose=verbose):
            issues["duplicate_vertexes"] = self.check_duplicates("vertex", numbering=numbering)
        with p_timer("Looking for duplicate_lines", verbose=verbose):
            issues["duplicate_lines"] = self.check_duplicates("line", numbering=numbering)
        with p_timer("Looking for duplicate_cells", verbose=verbose):
            issues["duplicate_cells"] = self.check_duplicates("triangle", numbering=numbering)
        
        # --- Degenerate triangles (two or more identical node indices) ---
        with p_timer("Looking for degenerate_line", verbose=verbose):
            issues["degenerate_line"] = self.check_degenerate("line", numbering=numbering)
        with p_timer("Looking for degenerate_cells", verbose=verbose):
            issues["degenerate_cells"] = self.check_degenerate("triangle", numbering=numbering)
        
        # --- Distorted triangles ---
        with p_timer("Looking for distorted_cells", verbose=verbose):
            issues["distorted_cells"] = self.check_cells_angles(threshold=threshold, numbering=numbering)
        
        # --- Misoriented cells (clockwise order of nodes) ---
        with p_timer("Looking for clockwise_cells", verbose=verbose):
            issues["clockwise_cells"] = self.check_triangle_orientation(numbering=numbering)
        
        # --- Triangular cells of smaller size than expected ---
        with p_timer("Looking for small_cells", verbose=verbose):
            issues["small_cells"] = self.check_cell_size(min_reso=min_reso, numbering=numbering)
        
        # # ===================================================================
        # # Here are some checks that are not always useful and much slower
        # # ===================================================================
        # # --- boundary edge of the mesh not in lines ---
        with p_timer("Looking for missing_bnd", verbose=verbose):
            issues["missing_bnd"] = self.check_boundary_edges_not_in_lines(numbering=numbering)
        
        # --- Floating cells unconnected to the main mesh ---
        with p_timer("Looking for floating_cells", verbose=verbose):
            issues["floating_cells"] = self.check_floating_cells(numbering=numbering)
        
        # --- Bottleneck cells (only one neighbouring cell)  ---
        with p_timer("Looking for bottleneck_cells", verbose=verbose):
            issues["bottleneck_cells"] = self.check_bottleneck_cells(numbering=numbering)
        
        return issues
    
    
    def check_float_dupli_degen(self, 
                                verbose: bool = False, 
                                numbering: str = 'meshio') -> dict:
        """
        Run only the floating-element, duplicate, and degenerate checks on a
        MeshDataProcessor.  Skips the heavier / less actionable checks
        (distorted angles, cell size, orientation) that check_validity also 
        runs.
    
        Returns
        -------
        dict with keys:
            floating_nodes, floating_vertexes, floating_lines,
            duplicate_nodes, duplicate_vertexes, duplicate_lines, 
            duplicate_cells, degenerate_line, degenerate_cells
        Each value is a np.ndarray of affected indices (empty array = no issue)
        """
        issues = {}
    
        with p_timer("Looking for floating_nodes",    verbose=verbose):
            issues["floating_nodes"]    = self.check_floating_nodes(numbering=numbering)
        with p_timer("Looking for floating_vertexes", verbose=verbose):
            issues["floating_vertexes"] = self.check_floating_vertexes(numbering=numbering)
        with p_timer("Looking for floating_lines",    verbose=verbose):
            issues["floating_lines"]    = self.check_floating_lines(numbering=numbering)
    
        with p_timer("Looking for duplicate_nodes",    verbose=verbose):
            issues["duplicate_nodes"]    = self.check_duplicates("node", numbering=numbering)
        with p_timer("Looking for duplicate_vertexes", verbose=verbose):
            issues["duplicate_vertexes"] = self.check_duplicates("vertex", numbering=numbering)
        with p_timer("Looking for duplicate_lines",    verbose=verbose):
            issues["duplicate_lines"]    = self.check_duplicates("line", numbering=numbering)
        with p_timer("Looking for duplicate_cells",    verbose=verbose):
            issues["duplicate_cells"]    = self.check_duplicates("triangle", numbering=numbering)
    
        with p_timer("Looking for degenerate_line",  verbose=verbose):
            issues["degenerate_line"]  = self.check_degenerate("line", numbering=numbering)
        with p_timer("Looking for degenerate_cells", verbose=verbose):
            issues["degenerate_cells"] = self.check_degenerate("triangle", numbering=numbering)
    
        # --- Floating cells unconnected to the main mesh ---
        with p_timer("Looking for floating_cells", verbose=verbose):
            issues["floating_cells"] = self.check_floating_cells(numbering=numbering)
            
        with p_timer("Looking for clockwise_cells", verbose=verbose):
            issues["clockwise_cells"] = self.check_triangle_orientation(numbering=numbering)
            
        return issues
    
# =============================================================================
#     USEFUL OPERATIONS ON THE MESH FOR SAVING OR PLOTTING
# =============================================================================

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
        segments = linestrings(points[edges])

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
    
    
    def compute_median_depth_per_node_tiled(
            self,
            X_bathy:      np.ndarray,
            Y_bathy:      np.ndarray,
            bathy:        np.ndarray,
            points_array: np.ndarray,
            dual:         np.ndarray,
            nodata:       int = 0,
            min_points:   int = 5,
            row_chunk:    int = 256,       # number of bathy rows per chunk — controls memory
            verbose:      bool = False
        ) -> np.ndarray:
    
        n_nodes = len(points_array)
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
    
                # -- Build Shapely points for this chunk (vectorized, no Python loop) --
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
                p_warning(f"  {outside_mask.sum()}/{n_nodes} nodes outside extent — NN fallback")
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
    
    
    def compute_boundary_polygon_list(self) -> list:
        """
        Create list of boundary polygons from boundary edges.
        
        Returns:
            list: List of Shapely Polygon objects
        """
        bnd_edges = self.compute_all_boundary_edges()
        
        list_LineString = linestrings(self.points_array[bnd_edges][:, :, :2])
        
        # Use polygonize to create polygons from line segments
        boundary_polygon_list = [geom for geom in polygonize(list_LineString).geoms]
        
        return boundary_polygon_list
    
    
    def compute_boundary_polygon(self) -> Polygon:
        """
        Create a single boundary polygon with holes.
        
        The largest polygon by area is used as the shell, and smaller polygons as holes.
        
        Returns:
            Polygon: Shapely Polygon object
        """
        boundary_polygon_list = self.compute_boundary_polygon_list()
        
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


    def reshape_to_grid(self):
        """
        Reshape data to grid format for quad cells. 
        --- NOT WORKING FOR UNSTRUCTURED MESHES ---
        
        Returns:
            Tuple of grid X coordinates, grid Y coordinates, and reshaped cell data
        """
        shape = [len(np.unique(self.cell_centers_array[:, 0])),
                len(np.unique(self.cell_centers_array[:, 1]))]
        center_grid_X = self.cell_centers_array[:, 0].reshape(shape)
        center_grid_Y = self.cell_centers_array[:, 1].reshape(shape)
        cell_data_grid = {k: v.reshape(shape) for k, v in self.cell_data.items()}
        
        return center_grid_X, center_grid_Y, cell_data_grid
    

# =============================================================================
#     OPERATIONS TO PRODUCE NEW PROCESSOR OBJECTS 
# =============================================================================


    def convert_tolosa_mesh_to_ww3(self, 
                                   bnd_tag_list: np.ndarray,
                                   X_bathy:      np.ndarray | None = None, 
                                   Y_bathy:      np.ndarray | None = None, 
                                   bathy:        np.ndarray | None = None,
                                   verbose:      bool = False):
        """
        Returns a new MeshDataProcessor object containing a 
        Parameters
        ----------
        bnd_tag_list : np.ndarray
            DESCRIPTION.
        X_bathy : np.ndarray
            DESCRIPTION.
        Y_bathy : np.ndarray
            DESCRIPTION.
        bathy : np.ndarray
            DESCRIPTION.
        verbose : bool, optional
            DESCRIPTION. The default is False.

        Returns
        -------
        new_processor : TYPE
            DESCRIPTION.

        """
        
        with p_timer("Computing bathy at nodes", verbose=verbose):
            if X_bathy is None or Y_bathy is None or bathy is None:
                p_warning("No valid X_bathy, Y_bathy or bathy - keeping node depths as is")
                new_depths = self.points_array[:,-1]
            elif not X_bathy.shape == Y_bathy.shape == bathy.shape:
                p_warning("No valid X_bathy, Y_bathy or bathy shape - keeping node depths as is")
                new_depths = self.points_array[:,-1]
            else:
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
                p_error('No line in the input mesh')
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
    
    
    def global_to_meshio(
        self,
        node_indices_gmsh:   np.ndarray | list | None = None,
        cell_indices_gmsh:   np.ndarray | list | None = None,
        line_indices_gmsh:   np.ndarray | list | None = None,
        vertex_indices_gmsh: np.ndarray | list | None = None,
        ) -> dict:
        """
        Translate gmsh GUI element/node numbering to meshio numbering.
    
        gmsh differences vs meshio
        --------------------------
        - Nodes    : 1-based  ->  meshio 0-based  (subtract 1)
        - Elements : globally numbered across ALL blocks in block order,
                     1-based  ->  meshio per-block 0-based index
    
        Parameters
        ----------
        node_indices_gmsh   : gmsh node indices (1-based)
        cell_indices_gmsh   : gmsh global element indices for triangles (1-based)
        line_indices_gmsh   : gmsh global element indices for lines (1-based)
        vertex_indices_gmsh : gmsh global element indices for vertexes (1-based)
    
        Returns
        -------
        dict with keys 'node_indices', 'cell_indices', 'line_indices',
        'vertex_indices' — all 0-based meshio indices, or None if not requested.
        """
        # --- Build block offset table (cumulative element counts per block) ------
        block_sizes   = np.array([len(b.data) for b in self.data.cells], dtype=np.intp)
        block_offsets = np.concatenate([[0], np.cumsum(block_sizes)])   # (n_blocks+1,)
    
        def _global_to_local(gmsh_indices, target_block_index):
            """
            Convert 1-based gmsh global element indices to 0-based local indices
            within the block at target_block_index.
            Raises ValueError if any index does not belong to that block.
            """
            if gmsh_indices is None:
                return None
            arr = np.atleast_1d(np.asarray(gmsh_indices, dtype=np.intp)).ravel()
            # gmsh is 1-based -> 0-based global
            global_0 = arr - 1
            block_start = block_offsets[target_block_index]
            block_end   = block_offsets[target_block_index + 1]
            out_of_block = (global_0 < block_start) | (global_0 >= block_end)
            if out_of_block.any():
                raise ValueError(
                    f"gmsh indices {arr[out_of_block]} do not belong to block "
                    f"{target_block_index} "
                    f"(global range [{block_start+1}, {block_end}])."
                )
            return (global_0 - block_start).astype(np.intp)
    
        # --- Nodes: simply 1-based -> 0-based ------------------------------------
        node_out = None
        if node_indices_gmsh is not None:
            arr = np.atleast_1d(np.asarray(node_indices_gmsh, dtype=np.intp)).ravel()
            node_out = (arr - 1).astype(np.intp)
    
        # --- Elements: global -> per-block local index ---------------------------
        cell_out   = _global_to_local(cell_indices_gmsh,   self.index_triangle)
        line_out   = _global_to_local(line_indices_gmsh,   self.index_line)
        vertex_out = _global_to_local(vertex_indices_gmsh, self.index_vertex)
    
        return {
            "node_indices":   node_out,
            "cell_indices":   cell_out,
            "line_indices":   line_out,
            "vertex_indices": vertex_out,
        }
    
    def _meshio_indices_to_gmsh(self,
                                 meshio_indices: np.ndarray,
                                 element_type:   str) -> np.ndarray:
        """
        Route meshio_indices through meshio_to_global using the correct
        keyword for the given element_type.
        """
        _kwarg = {
            "node":     "node_indices_meshio",
            "vertex":   "vertex_indices_meshio",
            "line":     "line_indices_meshio",
            "triangle": "cell_indices_meshio",
        }
        key = _kwarg[element_type]
        return self.meshio_to_global(**{key: meshio_indices})[key.replace("_meshio", "")]
    
    def meshio_to_global(
        self,
        node_indices_meshio:   np.ndarray | list | None = None,
        cell_indices_meshio:   np.ndarray | list | None = None,
        line_indices_meshio:   np.ndarray | list | None = None,
        vertex_indices_meshio: np.ndarray | list | None = None,
        ) -> dict:
        """
        Translate meshio numbering back to gmsh GUI element/node numbering.
    
        meshio differences vs gmsh
        --------------------------
        - Nodes    : 0-based  ->  gmsh 1-based  (add 1)
        - Elements : per-block 0-based index  ->  gmsh globally numbered
                     across ALL blocks in block order, 1-based
    
        Parameters
        ----------
        node_indices_meshio   : meshio node indices (0-based)
        cell_indices_meshio   : meshio local triangle indices (0-based, within triangle block)
        line_indices_meshio   : meshio local line indices (0-based, within line block)
        vertex_indices_meshio : meshio local vertex indices (0-based, within vertex block)
    
        Returns
        -------
        dict with keys 'node_indices', 'cell_indices', 'line_indices',
        'vertex_indices' — all 1-based gmsh global indices, or None if not requested.
        """
        # --- Build block offset table (cumulative element counts per block) ----------
        block_sizes   = np.array([len(b.data) for b in self.data.cells], dtype=np.intp)
        block_offsets = np.concatenate([[0], np.cumsum(block_sizes)])  # (n_blocks+1,)
    
        def _local_to_global(meshio_indices, target_block_index):
            """
            Convert 0-based meshio local indices to 1-based gmsh global indices
            for the block at target_block_index.
            Raises ValueError if any index is out of range for that block.
            """
            if meshio_indices is None:
                return None
            arr = np.atleast_1d(np.asarray(meshio_indices, dtype=np.intp)).ravel()
            block_size = block_offsets[target_block_index + 1] - block_offsets[target_block_index]
            out_of_block = (arr < 0) | (arr >= block_size)
            if out_of_block.any():
                raise ValueError(
                    f"meshio indices {arr[out_of_block]} are out of range for block "
                    f"{target_block_index} (valid range [0, {block_size - 1}])."
                )
            # local 0-based  ->  global 0-based  ->  gmsh 1-based
            return (arr + block_offsets[target_block_index] + 1).astype(np.intp)
    
        # --- Nodes: simply 0-based -> 1-based ----------------------------------------
        node_out = None
        if node_indices_meshio is not None:
            arr = np.atleast_1d(np.asarray(node_indices_meshio, dtype=np.intp)).ravel()
            node_out = (arr + 1).astype(np.intp)
    
        # --- Elements: per-block local index -> global gmsh index --------------------
        cell_out   = _local_to_global(cell_indices_meshio,   self.index_triangle)
        line_out   = _local_to_global(line_indices_meshio,   self.index_line)
        vertex_out = _local_to_global(vertex_indices_meshio, self.index_vertex)
    
        return {
            "node_indices":   node_out,
            "cell_indices":   cell_out,
            "line_indices":   line_out,
            "vertex_indices": vertex_out,
        }
    
    def _make_new_processor(
        self,
        keep_nodes_mask:    np.ndarray,   # bool (num_points,)
        keep_cells_mask:    np.ndarray,   # bool (num_cells,)
        keep_lines_mask:    np.ndarray,   # bool (num_lines,)   — pass np.array([], bool) if no lines
        keep_vertexes_mask: np.ndarray,   # bool (num_vertexes,) — pass np.array([], bool) if no vertexes
        ) -> "MeshDataProcessor":
        """
        Rebuild a MeshDataProcessor from four boolean keep-masks.
    
        Steps
        -----
        1. Build a node remapping vector  old_id -> new_id  (-1 = deleted).
        2. Slice points and point_data with keep_nodes_mask.
        3. Walk self.data.cells in original block order; apply the right mask
           to each block's connectivity and remap node indices.
        4. Apply the same per-block masks to every key in self.data.cell_data.
        5. Copy field_data (physical / geometrical tags, projection, …) verbatim.
        6. Construct a fresh meshio.Mesh and return MeshDataProcessor(new_mesh).
    
        The block order is preserved, so self.index_triangle / index_line /
        index_vertex remain valid in the returned processor.
        """
        # -- 1. Node remapping ----------------------------------------------------
        node_remap = np.full(self.num_points, -1, dtype=np.intp)
        node_remap[keep_nodes_mask] = np.arange(keep_nodes_mask.sum(), dtype=np.intp)
    
        # -- 2. New points & point_data -------------------------------------------
        new_points = self.data.points[keep_nodes_mask].copy()
    
        new_point_data = {}
        for k, v in self.data.point_data.items():
            new_point_data[k] = v[keep_nodes_mask].copy()
    
        # -- 3 & 4. Walk blocks in original order ---------------------------------
        # Build a dict:  block_index -> boolean keep-mask for that block
        block_masks = {}
        if self.index_triangle is not None:
            block_masks[self.index_triangle] = keep_cells_mask
        if self.index_line is not None and len(keep_lines_mask):
            block_masks[self.index_line] = keep_lines_mask
        if self.index_vertex is not None and len(keep_vertexes_mask):
            block_masks[self.index_vertex] = keep_vertexes_mask
    
        new_cells_blocks = []
        new_cell_data    = {k: [] for k in self.data.cell_data}
    
        for i, block in enumerate(self.data.cells):
            # Determine which rows of this block to keep
            mask = block_masks.get(i, np.ones(len(block.data), dtype=bool))
    
            # Remap connectivity (node ids)
            kept_conn = block.data[mask]
            new_conn  = node_remap[kept_conn]
    
            # Safety: no reference should point to a deleted node
            if (new_conn < 0).any():
                bad_cells = np.where((new_conn < 0).any(axis=1))[0] if new_conn.ndim > 1 \
                            else np.where(new_conn < 0)[0]
                raise ValueError(
                    f"Block '{block.type}' (index {i}): rows {bad_cells} still reference "
                    f"deleted nodes after masking. Remove those elements first."
                )
    
            new_cells_blocks.append(CellBlock(block.type, new_conn))
    
            for k, all_blocks in self.data.cell_data.items():
                new_cell_data[k].append(all_blocks[i][mask].copy())
    
        # -- 5. Carry over field_data (gmsh tags, projection, ...) verbatim ---------
        field_data = deepcopy(self.data.field_data) if self.data.field_data else {}
    
        # -- 6. Build new mesh and wrap it ----------------------------------------
        new_mesh = Mesh(
            points     = new_points,
            cells      = new_cells_blocks,
            point_data = new_point_data,
            cell_data  = new_cell_data,
            field_data = field_data,
        )
    
        return MeshDataProcessor(new_mesh)
    
    
    def remove_elements(
            self,
            node_indices:   np.ndarray | list | None = None,
            cell_indices:   np.ndarray | list | None = None,
            line_indices:   np.ndarray | list | None = None,
            vertex_indices: np.ndarray | list | None = None,
            numbering:      str = "meshio",
            ) -> "MeshDataProcessor":
        """
        Remove elements by index without any floating-element cleanup.
    
        When node_indices are provided, any cell, line or vertex that
        references a deleted node is automatically removed as well
        (a warning is raised to inform the caller).
    
        Parameters
        ----------
        numbering : 'meshio' (default) or 'gmsh'
            'meshio' : 0-based, per-block indices (default)
            'gmsh'   : 1-based, globally numbered across all blocks
        """
        if numbering == "gmsh":
            idx = self.global_to_meshio(node_indices, cell_indices,
                                        line_indices, vertex_indices)
            node_indices   = idx["node_indices"]
            cell_indices   = idx["cell_indices"]
            line_indices   = idx["line_indices"]
            vertex_indices = idx["vertex_indices"]
        elif numbering != "meshio":
            raise ValueError("numbering must be 'meshio' or 'gmsh'")
        
        def _make_mask(total: int, indices) -> np.ndarray:
            mask = np.ones(total, dtype=bool)
            if indices is not None and len(indices):
                idx = np.atleast_1d(np.asarray(indices, dtype=np.intp)).ravel()
                mask[idx] = False
            return mask
    
        keep_nodes    = _make_mask(self.num_points,   node_indices)
        keep_cells    = _make_mask(self.num_cells,     cell_indices)
        keep_lines    = (_make_mask(self.num_lines,    line_indices)
                         if self.num_lines    else np.array([], dtype=bool))
        keep_vertexes = (_make_mask(self.num_vertexes, vertex_indices)
                         if self.num_vertexes else np.array([], dtype=bool))
    
        # --- Cascade: drop elements that reference deleted nodes -----------------
        if node_indices is not None and len(node_indices):
            dead_nodes = np.atleast_1d(np.asarray(node_indices, dtype=np.intp)).ravel()
    
            connected_cells = np.isin(self.cells, dead_nodes).any(axis=1)
            if connected_cells.any():
                p_warning("Some connected cells were removed alongside the deleted nodes")
                keep_cells &= ~connected_cells
    
            if self.num_lines:
                connected_lines = np.isin(self.lines, dead_nodes).any(axis=1)
                if connected_lines.any():
                    p_warning("Some connected lines were removed alongside the deleted nodes")
                    keep_lines &= ~connected_lines
    
            if self.num_vertexes:
                connected_vertexes = np.isin(self.vertexes.ravel(), dead_nodes)
                if connected_vertexes.any():
                    p_warning("Some connected vertexes were removed alongside the deleted nodes")
                    keep_vertexes &= ~connected_vertexes
    
        return self._make_new_processor(keep_nodes, keep_cells, keep_lines, keep_vertexes)


    def remove_all_floating(self) -> "MeshDataProcessor":
        """
        Removes all floating elements from the mesh in two passes:
          1. Remove floating cells (disconnected from the main mesh group)
          2. Remove floating lines, vertexes and nodes left after cell removal
        """
        # --- Pass 1: floating cells ---
        floating_cells = self.check_floating_cells()
        proc = self.remove_elements(cell_indices=floating_cells) if len(floating_cells) else self
    
        # --- Pass 2: floating lines, vertexes, nodes ---
        floating_nodes    = proc.check_floating_nodes()
        floating_vertexes = proc.check_floating_vertexes()
        floating_lines    = proc.check_floating_lines()
    
        proc = proc.remove_elements(
            node_indices   = floating_nodes    if len(floating_nodes)    else None,
            line_indices   = floating_lines    if len(floating_lines)    else None,
            vertex_indices = floating_vertexes if len(floating_vertexes) else None,
        )
    
        return proc
    
    
    def remove_elements_clean(
            self,
            node_indices:   np.ndarray | list | None = None,
            cell_indices:   np.ndarray | list | None = None,
            line_indices:   np.ndarray | list | None = None,
            vertex_indices: np.ndarray | list | None = None,
            numbering:      str = "meshio",
            ) -> "MeshDataProcessor":
        """
        Remove elements by index, then clean up all floating elements.
    
        Combines remove_elements() and remove_all_floating() in a single call.
        See remove_elements() for parameter details.
        """
        return self.remove_elements(
            node_indices   = node_indices,
            cell_indices   = cell_indices,
            line_indices   = line_indices,
            vertex_indices = vertex_indices,
            numbering      = numbering
            ).remove_all_floating()
    
    
    def add_elements(
            self,
            new_nodes:    np.ndarray | None = None,  # (M, 3) coordinates
            new_cells:    dict       | None = None,
            new_lines:    dict       | None = None,
            new_vertexes: dict       | None = None,
            numbering:    str = "meshio",
            ) -> "MeshDataProcessor":
        """
        Append new nodes and/or elements to the mesh.
    
        Parameters
        ----------
        new_nodes : array (M, 3)
            Coordinates of new nodes to append.
    
        new_cells / new_lines / new_vertexes : dict, optional
            Each dict must contain a 'data' key with the connectivity array,
            plus one key per cell_data field with the corresponding values.
            Scalar values are broadcast to all new elements; arrays must match
            the number of new elements exactly. Missing cell_data keys default
            to 0.
    
            Example::
    
                new_cells = {
                    'data':             np.array([[100, 200, 300],
                                                  [101, 201, 301]]),
                    'gmsh:physical':    [11, 11],
                    'gmsh:geometrical': [1,  1 ],
                }
                new_lines = {
                    'data':             np.array([[50, 51]]),
                    'gmsh:physical':    [1],
                    'gmsh:geometrical': [29],
                }
                
        numbering : 'meshio' (default) or 'gmsh'
            'meshio' : 0-based, per-block indices (default)
            'gmsh'   : 1-based, globally numbered across all blocks
    
        Returns
        -------
        MeshDataProcessor
            New processor; the original is untouched.
        """
        
        if numbering not in ("meshio", "gmsh"):
            raise ValueError("numbering must be 'meshio' or 'gmsh'")
    
        # --- Convert node indices inside connectivity arrays ---------------------
        def _convert_conn(d):
            """If gmsh numbering, shift 1-based node indices in 'data' to 0-based."""
            if d is None or numbering == "meshio":
                return d
            return {**d, 'data': np.asarray(d['data']) - 1}
    
        new_cells    = _convert_conn(new_cells)
        new_lines    = _convert_conn(new_lines)
        new_vertexes = _convert_conn(new_vertexes)
        
        # --- 0. Validate input dicts ---------------------------------------------
        def _parse_block(d, label):
            """Extract connectivity and per-field values from an element dict."""
            if d is None:
                return None, {}
            if 'data' not in d:
                raise ValueError(f"new_{label} dict must contain a 'data' key.")
            conn       = np.atleast_2d(np.asarray(d['data']))
            field_vals = {k: v for k, v in d.items() if k != 'data'}
            return conn, field_vals
    
        cells_conn,    cells_fields    = _parse_block(new_cells,    'cells')
        lines_conn,    lines_fields    = _parse_block(new_lines,    'lines')
        vertexes_conn, vertexes_fields = _parse_block(new_vertexes, 'vertexes')
    
        additions = {
            'triangle': (cells_conn,    cells_fields,    self.index_triangle),
            'line':     (lines_conn,    lines_fields,    self.index_line),
            'vertex':   (vertexes_conn, vertexes_fields, self.index_vertex),
        }
    
        # --- 1. New points -------------------------------------------------------
        new_points = (
            np.vstack([self.data.points, np.atleast_2d(new_nodes)])
            if new_nodes is not None
            else self.data.points.copy()
        )
    
        n_new_nodes = len(new_nodes) if new_nodes is not None else 0
        new_point_data = {}
        for k, v in self.data.point_data.items():
            padding = np.zeros((n_new_nodes, *v.shape[1:]), dtype=v.dtype)
            new_point_data[k] = np.concatenate([v, padding])
        
        # --- 1b. Check and fix orientation of new triangular cells ---------------
        if cells_conn is not None:
            cells_conn = cells_conn.copy()             # ensure writable
            pts   = new_points[cells_conn]             # (K, 3, 3)
            AB    = pts[:, 1, :2] - pts[:, 0, :2]     # (K, 2)
            AC    = pts[:, 2, :2] - pts[:, 0, :2]     # (K, 2)
            cross = AB[:, 0] * AC[:, 1] - AB[:, 1] * AC[:, 0]
            flipped = cross < 0
            if flipped.any():
                p_warning("New cell orientation has been corrected")
                tmp = cells_conn[flipped, 1].copy()
                cells_conn[flipped, 1] = cells_conn[flipped, 2]
                cells_conn[flipped, 2] = tmp

            # Refresh additions so the block-walk uses the corrected connectivity
            additions['triangle'] = (cells_conn, cells_fields, self.index_triangle)
                    
        # --- 2. Helper: resolve a single cell_data field for new elements --------
        def _resolve(field_key, field_vals, n_elements, ref_dtype):
            if field_key in field_vals:
                val = field_vals[field_key]
            else:
                # Default to the minimum existing value for this field
                existing_values = [
                    blk for blk in self.data.cell_data.get(field_key, [])
                    if blk is not None and len(blk)
                ]
                val = int(np.min([v.min() for v in existing_values])) if existing_values else 0
        
            arr = np.atleast_1d(np.asarray(val, dtype=ref_dtype))
            if arr.size == 1:
                return np.full(n_elements, arr[0], dtype=ref_dtype)
            if arr.size != n_elements:
                raise ValueError(
                    f"'{field_key}' has {arr.size} values "
                    f"but {n_elements} new elements were provided."
                )
            return arr
    
        # --- 3. Walk existing blocks, appending where needed ---------------------
        new_cells_blocks = []
        new_cell_data    = {k: [] for k in self.data.cell_data}
    
        for i, block in enumerate(self.data.cells):
            # Find if this block receives new elements
            new_conn, field_vals, n_new = None, {}, 0
            for btype, (conn, fvals, bidx) in additions.items():
                if bidx == i and conn is not None:
                    new_conn    = conn.astype(block.data.dtype)
                    field_vals  = fvals
                    n_new       = len(new_conn)
                    break
    
            merged_conn = np.vstack([block.data, new_conn]) if n_new else block.data
            new_cells_blocks.append(CellBlock(block.type, merged_conn))
    
            for k, all_blocks in self.data.cell_data.items():
                existing   = all_blocks[i]
                if n_new:
                    appended = _resolve(k, field_vals, n_new, existing.dtype)
                    new_cell_data[k].append(np.concatenate([existing, appended]))
                else:
                    new_cell_data[k].append(existing.copy())
    
        # --- 4. field_data verbatim ----------------------------------------------
        field_data = deepcopy(self.data.field_data) if self.data.field_data else {}
    
        # --- 5. Build and return -------------------------------------------------
        new_mesh = Mesh(
            points     = new_points,
            cells      = new_cells_blocks,
            point_data = new_point_data,
            cell_data  = new_cell_data,
            field_data = field_data,
        )
        return MeshDataProcessor(new_mesh)
    
    
    def change_elements(
            self,
            element_type: str,
            indices:      np.ndarray | list | int,
            numbering:    str = "meshio",
            **kwargs,
            ) -> "MeshDataProcessor":
        """
        Return a new processor with modified data for a subset of elements.
    
        Parameters
        ----------
        element_type : str
            One of 'node', 'vertex', 'line', 'cell'.
            
        indices : int or array-like of int
            Indices of the elements to modify.
            
        numbering : 'meshio' (default) or 'gmsh'
            'meshio' : 0-based, per-block indices (default)
            'gmsh'   : 1-based, globally numbered across all blocks
            
        **kwargs
            Fields to modify.  The key selects what to change:
    
            - 'data'              : new coordinates (nodes) or connectivity
                                    (vertex/line/cell). Must be an array whose
                                    first dimension matches len(indices).
            - 'gmsh:physical'     : new physical tag(s)  — scalar or array
            - 'gmsh:geometrical'  : new geometrical tag(s) — scalar or array
            - any other key present in self.data.cell_data
    
            Scalar values are broadcast to all selected indices.
    
        Returns
        -------
        MeshDataProcessor
            New processor; the original is untouched.
    
        Examples
        --------
        # Move two nodes
        proc2 = proc.change_elements('node', [10, 11], 
                                      data=np.array([[1.0, 2.0, 0.0],
                                                     [1.5, 2.5, 0.0]]))
    
        # Change the physical tag of cells 0 and 5
        proc2 = proc.change_elements('cell', [0, 5], **{'gmsh:physical': 3})
    
        # Change both connectivity and tags of line 7
        proc2 = proc.change_elements('line', 7, 
                                      data=np.array([[100, 200]]),
                                      **{'gmsh:physical': 2, 
                                         'gmsh:geometrical': 5})
        """
        if numbering not in ("meshio", "gmsh"):
            raise ValueError("numbering must be 'meshio' or 'gmsh'")
    
        # --- Convert element selector indices ------------------------------------
        if numbering == "gmsh":
            key_map = {'node':   'node_indices',
                       'cell':   'cell_indices',
                       'line':   'line_indices',
                       'vertex': 'vertex_indices'}
            gmsh_kwarg = {f"{key_map[element_type]}_gmsh": indices}
            indices = self.global_to_meshio(**gmsh_kwarg)[key_map[element_type]]
    
            # --- Convert node indices inside 'data' kwarg (connectivity only) ----
            # Nodes: 'data' is coordinates -> no conversion
            # Others: 'data' is a connectivity array of node indices -> 1-based to 0-based
            if element_type != 'node' and 'data' in kwargs:
                kwargs = {**kwargs, 'data': np.asarray(kwargs['data']) - 1}
        
        indices = np.atleast_1d(np.asarray(indices, dtype=np.intp)).ravel()
    
        if element_type not in ('node', 'vertex', 'line', 'cell'):
            raise ValueError("element_type must be 'node', 'vertex', 'line' or 'cell'")
    
        # --- Validate kwargs keys ------------------------------------------------
        valid_keys = {'data'} | set(self.data.cell_data.keys())
        unknown = set(kwargs) - valid_keys
        if unknown:
            raise ValueError(f"Unknown field(s): {unknown}. "
                             f"Valid fields are: {valid_keys}")
    
        if element_type == 'node' and set(kwargs.keys()) - {'data'}:
            raise ValueError("Only 'data' (coordinates) can be changed for nodes.")
    
        # --- Helper: broadcast scalar or validate array length -------------------
        def _resolve(val, n, dtype):
            arr = np.atleast_1d(np.asarray(val, dtype=dtype))
            if arr.shape[0] == 1:
                return np.repeat(arr, n, axis=0)
            if arr.shape[0] != n:
                raise ValueError(f"Expected {n} values, got {arr.shape[0]}.")
            return arr
    
        n = len(indices)
    
        # NODES
        if element_type == 'node':
            new_points = self.data.points.copy()
            if 'data' in kwargs:
                new_coords = _resolve(kwargs['data'], n, self.data.points.dtype)
                new_points[indices] = new_coords
    
            new_point_data = {k: v.copy() for k, v in self.data.point_data.items()}
    
            new_mesh = Mesh(
                points     = new_points,
                cells      = deepcopy(self.data.cells),
                point_data = new_point_data,
                cell_data  = deepcopy(self.data.cell_data),
                field_data = deepcopy(self.data.field_data) if self.data.field_data else {},
            )
            return MeshDataProcessor(new_mesh)
    
        # ELEMENT TYPES (vertex / line / cell)
        block_index = {
            'vertex': self.index_vertex,
            'line':   self.index_line,
            'cell':   self.index_triangle,
        }[element_type]
    
        if block_index is None:
            raise ValueError(f"No '{element_type}' block found in this mesh.")
        
        # --- Check and fix orientation when changing cell connectivity -----------
        if element_type == 'cell' and 'data' in kwargs:
            new_conn_data = _resolve(kwargs['data'], n, 
                                     self.data.cells[self.index_triangle].data.dtype)
            new_conn_data = new_conn_data.copy()       # ensure writable
            pts   = self.data.points[new_conn_data]    # (K, 3, 3)
            AB    = pts[:, 1, :2] - pts[:, 0, :2]     # (K, 2)
            AC    = pts[:, 2, :2] - pts[:, 0, :2]     # (K, 2)
            cross = AB[:, 0] * AC[:, 1] - AB[:, 1] * AC[:, 0]
            flipped = cross < 0
            if flipped.any():
                p_warning("New cell orientation has been corrected")
                tmp = new_conn_data[flipped, 1].copy()
                new_conn_data[flipped, 1] = new_conn_data[flipped, 2]
                new_conn_data[flipped, 2] = tmp
            kwargs = {**kwargs, 'data': new_conn_data}
        
        # --- Rebuild cell blocks -------------------------------------------------
        new_cells_blocks = []
        new_cell_data    = {k: [] for k in self.data.cell_data}
    
        for i, block in enumerate(self.data.cells):
            new_conn = block.data.copy()
    
            if i == block_index and 'data' in kwargs:
                new_conn[indices] = _resolve(kwargs['data'], n, block.data.dtype)
    
            new_cells_blocks.append(CellBlock(block.type, new_conn))
    
            for k, all_blocks in self.data.cell_data.items():
                new_blk = all_blocks[i].copy()
                if i == block_index and k in kwargs:
                    new_blk[indices] = _resolve(kwargs[k], n, all_blocks[i].dtype)
                new_cell_data[k].append(new_blk)
    
        new_mesh = Mesh(
            points     = self.data.points.copy(),
            cells      = new_cells_blocks,
            point_data = {k: v.copy() for k, v in self.data.point_data.items()},
            cell_data  = new_cell_data,
            field_data = deepcopy(self.data.field_data) if self.data.field_data else {},
        )
        return MeshDataProcessor(new_mesh)
    
    
    def swap_orientation(self,
                         cell_ids:  np.ndarray,
                         numbering: str = "meshio") -> "MeshDataProcessor":
        """
        Returns a new MeshDataProcessor where the triangular cells in cell_ids
        have swapped orientation (swap of first two nodes).
        """
        if numbering not in ("meshio", "gmsh"):
            raise ValueError("numbering must be 'meshio' or 'gmsh'")
    
        if numbering == "gmsh":
            new_indexes_dict = self.global_to_meshio(cell_indices_gmsh=cell_ids)
            new_cell_ids = new_indexes_dict['cell_indices'].astype(int)
            cell_ids = new_cell_ids.reshape(cell_ids.shape)
    
        cell_ids = np.atleast_1d(np.asarray(cell_ids, dtype=np.intp)).ravel()
    
        # Step 1: select current connectivity
        current = self.cells[cell_ids].copy()          # (K, 3)
    
        # Step 2: swap node_0 and node_1
        swapped = current.copy()
        swapped[:, 0] = current[:, 1]
        swapped[:, 1] = current[:, 0]
    
        return self.change_elements('cell', cell_ids, data=swapped)
    
    
    def swap_edges_cells(self,
                         cell_ids:  np.ndarray,
                         numbering: str = "meshio") -> "MeshDataProcessor":
        """
        Returns a new MeshDataProcessor where each pair of triangular cells in
        cell_ids have swapped their common edge.
    
        cell_ids must be of shape (P, 2): each row is a pair of adjacent cells.
        For each pair [a,b,c] + [d,c,b], the result is [a,b,d] + [d,c,a].
        """
        cell_ids = np.atleast_2d(np.asarray(cell_ids))
    
        if numbering not in ("meshio", "gmsh"):
            raise ValueError("numbering must be 'meshio' or 'gmsh'")
    
        if numbering == "gmsh":
            flat = cell_ids.ravel()
            new_indexes_dict = self.global_to_meshio(cell_indices_gmsh=flat)
            cell_ids = new_indexes_dict['cell_indices'].astype(int).reshape(cell_ids.shape)
    
        # Step 1: check for duplicates
        flat_ids = cell_ids.ravel()
        unique_ids, counts = np.unique(flat_ids, return_counts=True)
        if (counts > 1).any():
            p_warning(f"Duplicate cell ids detected in swap_edges_cells: "
                      f"{unique_ids[counts > 1]}. These pairs will be skipped.")
            # filter out pairs containing duplicated ids
            dup_ids = set(unique_ids[counts > 1])
            mask = ~np.array([i in dup_ids or j in dup_ids
                              for i, j in cell_ids])
            cell_ids = cell_ids[mask]
    
        if not len(cell_ids):
            return self
    
        id0 = cell_ids[:, 0]                           # (P,)
        id1 = cell_ids[:, 1]                           # (P,)
        tri0 = self.cells[id0]                         # (P, 3)
        tri1 = self.cells[id1]                         # (P, 3)
    
        # Step 2: find the 2 common nodes and the 2 opposite nodes
        # For each pair, common nodes are those appearing in both triangles
        new_tri0 = np.empty_like(tri0)
        new_tri1 = np.empty_like(tri1)
        valid = np.ones(len(cell_ids), dtype=bool)
    
        for k, (t0, t1) in enumerate(zip(tri0, tri1)):
            common   = np.intersect1d(t0, t1)
            if len(common) != 2:
                p_warning(f"Cell pair ({id0[k]}, {id1[k]}) does not share exactly 2 nodes — skipping.")
                valid[k] = False
                continue
            opp0 = t0[~np.isin(t0, common)][0]        # node in tri0 not in tri1
            opp1 = t1[~np.isin(t1, common)][0]        # node in tri1 not in tri0
    
            # New triangles share the new edge (opp0, opp1) instead
            new_tri0[k] = [opp0, common[0], opp1]
            new_tri1[k] = [opp1, common[1], opp0]
    
        if not valid.all():
            id0, id1 = id0[valid], id1[valid]
            new_tri0, new_tri1 = new_tri0[valid], new_tri1[valid]
    
        if not len(id0):
            return self
        
        # Step 3: remove the old common edge from lines if it exists
        if self.num_lines and valid.any():
            lines_to_remove = []
            lines_sorted = np.sort(self.lines, axis=1)          # (L, 2)
    
            for k in np.where(valid)[0]:
                t0, t1  = tri0[k], tri1[k]
                common  = np.intersect1d(t0, t1)                # the swapped edge
                edge    = np.sort(common)                        # (2,)
                match   = np.where((lines_sorted[:, 0] == edge[0]) &
                                    (lines_sorted[:, 1] == edge[1]))[0]
                if len(match):
                    lines_to_remove.append(match[0])
                    p_warning(f"Removed common edge {common} from lines")
    
            if lines_to_remove:
                lines_to_remove = np.unique(lines_to_remove)
                # Apply connectivity change and line removal in one shot
                all_ids  = np.concatenate([id0,     id1])
                all_data = np.vstack(    [new_tri0, new_tri1])
                return (self
                        .change_elements('cell', all_ids, data=all_data)
                        .remove_elements(line_indices=lines_to_remove))
    
        # Step 4: no lines to remove, apply connectivity change only
        all_ids  = np.concatenate([id0, id1])
        all_data = np.vstack([new_tri0, new_tri1])
    
        return self.change_elements('cell', all_ids, data=all_data)
        
    
    def merge_nodes(self,
                    node_ids:  np.ndarray,
                    numbering: str = "meshio") -> "MeshDataProcessor":
        """
        Returns a new MeshDataProcessor where node_ids[:, 0] has been replaced
        by node_ids[:, 1] everywhere in the connectivity.
    
        After remapping, only degenerate and duplicate elements that are
        *local* to the merged nodes are removed.
        """
        node_ids = np.atleast_2d(np.asarray(node_ids))
    
        if numbering not in ("meshio", "gmsh"):
            raise ValueError("numbering must be 'meshio' or 'gmsh'")
    
        if numbering == "gmsh":
            flat = node_ids.ravel()
            new_indexes_dict = self.global_to_meshio(node_indices_gmsh=flat)
            node_ids = new_indexes_dict['node_indices'].astype(int).reshape(node_ids.shape)
    
        # Drop identity pairs
        pairs_mask           = node_ids[:, 0] != node_ids[:, 1]
        node_indices_to_drop = node_ids[pairs_mask, 0]
        node_indices_to_keep = node_ids[pairs_mask, 1]
    
        if not len(node_indices_to_drop):
            return self
    
        # ------------------------------------------------------------------ #
        #  Helper: gather element indices connected to a set of node indices #
        # ------------------------------------------------------------------ #
        def _local_elements(mapping, node_indices):
            """
            Given a node to element mapping (rows = nodes, cols = element 
            indices or NaN) return the unique element indices reachable from 
            node_indices.
            """
            if mapping.size == 0:
                return np.array([], dtype=int)
            rows = mapping[node_indices].ravel()
            return np.unique(rows[~np.isnan(rows)]).astype(int)
    
        # Step 1: remap connectivity in all element types
        def _remap(conn):
            conn = conn.copy()
            for drop, keep in zip(node_indices_to_drop, node_indices_to_keep):
                conn[conn == drop] = keep
            return conn
    
        new_cells_data    = _remap(self.cells)
        new_lines_data    = _remap(self.lines)    if self.num_lines    else None
        new_vertexes_data = _remap(self.vertexes) if self.num_vertexes else None
    
        # Step 2: apply remapped connectivity
        proc = self.change_elements('cell', np.arange(self.num_cells),
                                    data=new_cells_data)
        if self.num_lines:
            proc = proc.change_elements('line', np.arange(self.num_lines),
                                        data=new_lines_data)
        if self.num_vertexes:
            proc = proc.change_elements('vertex', np.arange(self.num_vertexes),
                                        data=new_vertexes_data)
    
        # Step 3: collect elements *local* to the affected nodes
        #         (both the dropped and kept sides can now host bad elements)
        affected_nodes = np.unique(np.concatenate([node_indices_to_drop,
                                                   node_indices_to_keep]))
    
        local_cells    = _local_elements(proc.compute_node_to_cell(),   affected_nodes)
        local_lines    = _local_elements(proc.compute_node_to_line(),   affected_nodes)
        local_vertexes = _local_elements(proc.compute_node_to_vertex(), affected_nodes)
    
        # Step 4: intersect global degenerate/duplicate results with local sets
        degen_cells  = proc.check_degenerate_local(local_cells,    'triangle')
        degen_lines  = proc.check_degenerate_local(local_lines,    'line')     if self.num_lines    else np.array([], dtype=int)
        # dup_cells    = proc.check_duplicates_local(local_cells,    'triangle')
        dup_lines    = proc.check_duplicates_local(local_lines,    'line')     if self.num_lines    else np.array([], dtype=int)
        dup_vertexes = proc.check_duplicates_local(local_vertexes, 'vertex')   if self.num_vertexes else np.array([], dtype=int)
    
        # bad_cells    = np.unique(np.concatenate([degen_cells,  dup_cells]))
        bad_cells    = degen_cells
        bad_lines    = np.unique(np.concatenate([degen_lines,  dup_lines]))
        bad_vertexes = dup_vertexes
    
        if len(bad_cells):
            p_warning(f"Degenerate cells removed after node merge: {len(bad_cells)}")
        if len(bad_lines):
            p_warning(f"Degenerate or duplicate lines removed after node merge: {len(bad_lines)}")
        if len(bad_vertexes):
            p_warning(f"Duplicate vertexes removed after node merge: {len(bad_vertexes)}")
    
        proc = proc.remove_elements(
            cell_indices   = bad_cells    if len(bad_cells)    else None,
            line_indices   = bad_lines    if len(bad_lines)    else None,
            vertex_indices = bad_vertexes if len(bad_vertexes) else None,
        )
    
        # Step 5: check for lines that became interior after the merge
        #         (again, restrict to lines local to the affected nodes)
        local_lines_after = _local_elements(proc.compute_node_to_line(), affected_nodes)
        interior_lines    = np.intersect1d(proc.check_lines_not_boundary(), local_lines_after)
        if len(interior_lines):
            p_warning(f"{len(interior_lines)} lines became interior after node "
                      f"merge and were removed.")
            proc = proc.remove_elements(line_indices=interior_lines)
    
        # Step 6: remove the now-unused merged-away nodes
        proc = proc.remove_elements(node_indices=node_indices_to_drop)
    
        return proc

# =============================================================================
#     SAVING THE MESH IN VARIOUS .msh FORMATS
# =============================================================================
    

    def save_mesh(self, 
                  path: str = './', 
                  filename: str = 'toto.msh',
                  file_format: str ='gmsh22', 
                  binary: bool = False,
                  float_fmt: str = '.8f'):
        
        filepath = os.path.join(path, filename)
        
        if 'gmsh:dim_tags' not in self.data.point_data.keys():
            self.data.point_data['gmsh:dim_tags'] = np.array(len(self.data.points)*[0])
            
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
    