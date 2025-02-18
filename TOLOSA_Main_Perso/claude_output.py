#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Object-oriented implementation for plotting VTK data using matplotlib
Author: Louis Saisset (Original code)
Modified for OOP structure
"""

import vtk
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import os
from typing import Dict, Tuple, List, Optional


class VTKDataReader:
    def __init__(self, vtk_directory: str):
        self.vtk_directory = vtk_directory
        self.vtk_files = self._get_vtk_files()
        
    def _get_vtk_files(self) -> List[str]:
        """Get all VTK files in the directory."""
        vtk_files = [os.path.join(self.vtk_directory, f) 
                    for f in os.listdir(self.vtk_directory) 
                    if f.endswith(".vtk")]
        return sorted(vtk_files)
    
    def read_file(self, time_step: int) -> vtk.vtkUnstructuredGrid:
        """Read VTK file for given time step."""
        reader = vtk.vtkUnstructuredGridReader()
        reader.SetFileName(self.vtk_files[time_step])
        reader.ReadAllVectorsOn()
        reader.ReadAllScalarsOn()
        reader.Update()
        return reader.GetOutput()


class VTKDataProcessor:
    def __init__(self, data: vtk.vtkUnstructuredGrid):
        self.data = data
        self.points, self.num_points, 
        self.cells, self.num_cells, 
        self.cell_type = self._extract_points_cells()
        self.cell_data, self.cell_centers, 
        self.points_array = self._create_cell_data()
        
    def _extract_points_cells(self) -> Tuple:
        """Extract points and cells information from VTK data."""
        points = self.data.GetPoints()
        num_points = self.data.GetNumberOfPoints()
        cells = self.data.GetCells()
        num_cells = self.data.GetNumberOfCells()
        
        cell_types = [self.data.GetCell(i).GetCellType() for i in range(num_cells)]
        
        if all(ct == 9 for ct in cell_types):
            cell_type = 'all_Quad'
        elif all(ct == 5 for ct in cell_types):
            cell_type = 'all_Triangle'
        else:
            cell_type = np.unique(cell_types)
            
        return points, num_points, cells, num_cells, cell_type
    
    def _create_cell_data(self) -> Tuple:
        """Create dictionary of cell data and compute cell centers."""
        # Create dictionary of cell data
        cell_data = {}
        for i in range(self.data.GetCellData().GetNumberOfArrays()):
            name = self.data.GetCellData().GetArrayName(i)
            cell_data[name] = np.array(self.data.GetCellData().GetArray(i))
        
        # Compute cell centers
        cell_centers = np.zeros([self.num_cells, 3])
        for i in range(self.num_cells):
            cell = self.data.GetCell(i)
            num_cell_points = cell.GetNumberOfPoints()
            for j in range(num_cell_points):
                point = self.points.GetPoint(cell.GetPointId(j))
                cell_centers[i, :] += np.array(point)/num_cell_points
        
        points_array = np.array(self.points.GetData())
        
        return cell_data, cell_centers, points_array
    
    def reshape_to_grid(self) -> Tuple:
        """Reshape data to grid format for quad cells."""
        shape = [len(np.unique(self.cell_centers[:, 0])),
                len(np.unique(self.cell_centers[:, 1]))]
        center_grid_X = self.cell_centers[:, 0].reshape(shape)
        center_grid_Y = self.cell_centers[:, 1].reshape(shape)
        cell_data_grid = {k: v.reshape(shape) for k, v in self.cell_data.items()}
        return center_grid_X, center_grid_Y, cell_data_grid
    
    def compute_triangulations(self) -> Tuple:
        """Compute triangulations for triangle cells."""
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
            self.cell_centers[:, 0],
            self.cell_centers[:, 1])
        
        # Create mask
        xtri = self.cell_centers[:, 0][tricontour_triangulation.triangles] - \
               np.roll(self.cell_centers[:, 0][tricontour_triangulation.triangles], 1, axis=1)
        ytri = self.cell_centers[:, 1][tricontour_triangulation.triangles] - \
               np.roll(self.cell_centers[:, 1][tricontour_triangulation.triangles], 1, axis=1)
        sizes = np.array([np.array(self.data.GetCell(i).GetBounds()[0::2]) - 
                         np.array(self.data.GetCell(i).GetBounds()[1::2]) 
                         for i in range(self.num_cells)])
        max_size = max(np.hypot(sizes[:,0], sizes[:,1], sizes[:,2]))
        tricontour_triangulation.set_mask(np.max(np.sqrt(xtri**2 + ytri**2), axis=1) > max_size)
        
        return tripcolor_triangulation, tricontour_triangulation


class VTKPlotter:
    def __init__(self, output_dir: str, pcolormax: float = 50, 
                 quiver_scale: float = 100, quiver_spacing: int = 15):
        self.output_dir = output_dir
        self.pcolormax = pcolormax
        self.quiver_scale = quiver_scale
        self.quiver_spacing = quiver_spacing
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
    
    def _setup_figure(self) -> Tuple[plt.Figure, plt.Axes]:
        """Create and setup the figure and axes."""
        fig, ax = plt.subplots(1, 1, figsize=[4, 4], dpi=300)
        ax.set_aspect(1)
        ax.tick_params(axis='both', direction='in')
        ax.grid(linestyle='dashed', zorder=1)
        return fig, ax
    
    def _setup_colorbar(self, fig: plt.Figure, ax: plt.Axes, 
                       mappable) -> None:
        """Setup colorbar for the plot."""
        cax = fig.add_axes([ax.get_position().x1 + 0.03,
                           ax.get_position().y0,
                           0.05,
                           ax.get_position().height])
        cax.tick_params(axis='y', direction='in')
        cax.set_yticks(cax.get_yticks(),
                      labels=cax.get_yticklabels(),
                      rotation=90, va='center')
        fig.colorbar(mappable, cax=cax)
    
    def plot_quad_data(self, time_step: int, center_grid_X: np.ndarray,
                      center_grid_Y: np.ndarray, cell_data: Dict) -> None:
        """Plot quad cell data."""
        fig, ax = self._setup_figure()
        
        # Plot SSH
        ssh_plot = ax.pcolor(center_grid_X, center_grid_Y, cell_data['ssh'],
                           vmin=-self.pcolormax, vmax=self.pcolormax,
                           cmap='RdBu', zorder=0)
        
        # Plot bathymetry
        bathy_plot = ax.contour(center_grid_X, center_grid_Y, cell_data['bathy'],
                              levels=4, linestyles=['solid', 'dashed', 'dashdot', 'dotted'],
                              linewidths=1, colors='r', zorder=2)
        ax.clabel(bathy_plot)
        
        # Plot currents
        N = self.quiver_spacing
        current_plot = ax.quiver(center_grid_X[::N, ::N], center_grid_Y[::N, ::N],
                               cell_data['u'][::N, ::N], cell_data['v'][::N, ::N],
                               scale=self.quiver_scale, scale_units='width', zorder=10)
        ax.quiverkey(current_plot, .85, 1.03, 1, '1m/s', labelpos='E')
        
        self._setup_colorbar(fig, ax, ssh_plot)
        fig.suptitle(f'Iteration={time_step:05d}', y=0.93)
        
        fig.savefig(os.path.join(self.output_dir, f"ssh_bathy_u_v_{time_step:05d}.png"),
                   format='png', bbox_inches='tight')
        plt.close(fig)
    
    def plot_triangle_data(self, time_step: int, tripcolor_tri: mpl.tri.Triangulation,
                          tricontour_tri: mpl.tri.Triangulation,
                          cell_data: Dict, cell_centers: np.ndarray) -> None:
        """Plot triangle cell data."""
        fig, ax = self._setup_figure()
        
        # Plot SSH
        ssh_plot = ax.tripcolor(tripcolor_tri, cell_data['ssh'],
                              vmin=-self.pcolormax, vmax=self.pcolormax,
                              cmap='RdBu', zorder=0)
        
        # Plot bathymetry
        bathy_plot = ax.tricontour(tricontour_tri, cell_data['bathy'],
                                 levels=4, linestyles=['solid', 'dashed', 'dashdot', 'dotted'],
                                 linewidths=1, colors='r', zorder=2)
        ax.clabel(bathy_plot)
        
        # Plot currents
        random_indices = np.random.choice(len(cell_data['bathy']),
                                        size=len(cell_data['bathy'])//self.quiver_spacing,
                                        replace=False)
        current_plot = ax.quiver(cell_centers[:,0][random_indices],
                               cell_centers[:,1][random_indices],
                               cell_data['u'][random_indices],
                               cell_data['v'][random_indices],
                               scale=self.quiver_scale, scale_units='width', zorder=10)
        ax.quiverkey(current_plot, .85, 1.03, 1, '1m/s', labelpos='E')
        
        self._setup_colorbar(fig, ax, ssh_plot)
        fig.suptitle(f'Iteration={time_step:05d}', y=0.93)
        
        fig.savefig(os.path.join(self.output_dir, f"ssh_bathy_u_v_{time_step:05d}.png"),
                   format='png', bbox_inches='tight')
        plt.close(fig)


def main():
    # Initialize parameters
    vtk_directory = os.getcwd()
    output_dir = os.path.join(vtk_directory, 'Figures')
    time_step = int(sys.argv[1])
    
    # Initialize classes
    reader = VTKDataReader(vtk_directory)
    if not reader.vtk_files:
        print("No VTK files found in directory")
        return
    
    # Read and process data
    vtk_data = reader.read_file(time_step)
    processor = VTKDataProcessor(vtk_data)
    plotter = VTKPlotter(output_dir)
    
    # Plot based on cell type
    if processor.cell_type == 'all_Quad':
        center_grid_X, center_grid_Y, cell_data_grid = processor.reshape_to_grid()
        plotter.plot_quad_data(time_step, center_grid_X, center_grid_Y, cell_data_grid)
    elif processor.cell_type == 'all_Triangle':
        tripcolor_tri, tricontour_tri = processor.compute_triangulations()
        plotter.plot_triangle_data(time_step, tripcolor_tri, tricontour_tri,
                                 processor.cell_data, processor.cell_centers)


if __name__ == "__main__":
    import sys
    main()
