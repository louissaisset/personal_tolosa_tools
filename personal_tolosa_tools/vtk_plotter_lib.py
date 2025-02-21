#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VTK Data Plotting Library
Provides classes for reading, processing, and plotting VTK data
"""

import os
import typing

import vtk
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt


class VTKDataReader:
    """
    Handles reading of VTK files from a specified directory.
    
    Attributes:
        vtk_directory (str): Path to directory containing VTK files
        vtk_files (List[str]): Sorted list of VTK file paths
    """
    def __init__(self, vtk_directory: str):
        """
        Initialize VTKDataReader.
        
        Args:
            vtk_directory (str): Path to directory containing VTK files
        """
        self.vtk_directory = vtk_directory
        self.vtk_files = self._get_vtk_files()
        
    def _get_vtk_files(self) -> typing.List[str]:
        """
        Retrieve and sort VTK files from the specified directory.
        
        Returns:
            List of sorted VTK file paths
        """
        vtk_files = [os.path.join(self.vtk_directory, f) 
                    for f in os.listdir(self.vtk_directory) 
                    if f.endswith(".vtk")]
        return sorted(vtk_files)
    
    def read_file(self, time_step: int) -> vtk.vtkUnstructuredGrid:
        """
        Read VTK file for a given time step.
        
        Args:
            time_step (int): Index of the VTK file to be read
        
        Returns:
            VTK unstructured grid data
        """
        reader = vtk.vtkUnstructuredGridReader()
        reader.SetFileName(self.vtk_files[time_step])
        reader.ReadAllVectorsOn()
        reader.ReadAllScalarsOn()
        reader.Update()
        return reader.GetOutput()


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
        self.data = data
        self.points, self.num_points = self._extract_points()
        self.cells, self.num_cells= self._extract_cells()
        self.edgepoints, self.num_edgepoints = self._extract_edgepoints()
        self.cell_type = self._extract_celltype()
        self.cell_data = self._create_cell_data_dict()
        self.cell_centers_array = self._create_cell_center_array()
        self.points_array = self._create_points_array()
        self.edgepoints_array = self._create_edgepoints_array()
        self.xmin, self.xmax, self.ymin, self.ymax = self.get_data_lims()
        
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
    
    def _extract_edgepoints(self) -> typing.Tuple:
        """
        Extract points and point number from the edge of VTK data.
        
        Returns:
            Tuple containing edgepoints, number of edgepoints
        """
        
        # Convert vtkUnstructuredGrid to vtkPolyData
        geometry_filter = vtk.vtkGeometryFilter()
        geometry_filter.SetInputData(self.data)
        geometry_filter.Update()
        # poly_data = geometry_filter.GetOutput()
        
        # connectivity_filter = vtk.vtkConnectivityFilter()
        # connectivity_filter.SetInputData(poly_data)
        # connectivity_filter.SetExtractionModeToLargestRegion()
        # connectivity_filter.Update()
    
        # largest_component = connectivity_filter.GetOutput()
        
        feature_edges = vtk.vtkFeatureEdges()
        feature_edges.SetInputConnection(geometry_filter.GetOutputPort())
        feature_edges.BoundaryEdgesOn()
        feature_edges.FeatureEdgesOff()
        feature_edges.ManifoldEdgesOff()
        feature_edges.NonManifoldEdgesOff()
        feature_edges.Update()
        
        edgepoints = feature_edges.GetOutput().GetPoints()
        num_edgepoints = feature_edges.GetOutput().GetNumberOfPoints()
        
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
    
    def get_data_lims(self) -> typing.Tuple:
        """
        Returns the X and Y limits of the grid
        """
        xmin = np.nanmin(self.points_array[:, 0])
        xmax = np.nanmax(self.points_array[:, 0])
        ymin = np.nanmin(self.points_array[:, 1])
        ymax = np.nanmax(self.points_array[:, 1])
        
        return (xmin, xmax, ymin, ymax)
    
    def reshape_to_grid(self) -> typing.Tuple:
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
    
    def compute_triangulations(self) -> typing.Tuple:
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
    
    def interp_upon_regular_grid(self, ):
        return
    
    
    # def create_mask_path_N(self, X, Y, N):
    #     boundary_path = mpltPath.Path(largest_boundary[:,0:2])
    #     points = np.column_stack((X.ravel(), Y.ravel()))
    #     mask = boundary_path.contains_points(points).reshape(X.shape)
    #     return(mask)

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
                 figure_size: tuple = (4, 4),
                 figure_dpi: int = 300,
                 figure_xlim: tuple = (None, None),
                 figure_ylim: tuple = (None, None),
                 figure_format: str = 'png',
                 figure_labelfontsize: int = 8,
                 figure_tickfontsize: int = 7,
                 
                 # timestep: int = 0,
                 
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
                 quiver_fontsize: int = 8
                 ):
        """
        Initialize VTKPlotter.
        
        Args:
            figure_outputdir (str): Directory to save output figures, Defaults to './Figures/'
            figure_title (str): The figure title, Defaults to ''
            figure_filename (str): Filename with which the figure is saved, Defaults to '', (will be created through the autofilename method)
            figure_size (tuple, optional): Figure size in inches. Defaults to (4,4).
            figure_dpi (int, optional): Resolution of the figure. Defaults to 300.
            figure_xlim (tuple, optional): X axis view limit in the x units. Defaults to (None None).
            figure_ylim (tuple, optional): Y axis view limit in the y units. Defaults to (None None).
            figure_format (str, optional): Format of the figure. Defaults to 'png'.
            figure_labelfontsize (int, optional): Fontsize of all axis labels outside the axis. Defaults to 8
            figure_tickfontsize (int, optional): Fontsize of all axis labels outside the axis. Defaults to 8
            
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
        """
        # timestep (int, optional): Timestep corresponding to the data. Defaults to 4.
        
        
        self.figure_outputdir = figure_outputdir
        self.figure_title= figure_title 
        self.figure_filename = figure_filename
        self.figure_size = figure_size
        self.figure_dpi = figure_dpi
        self.figure_xlim = figure_xlim
        self.figure_ylim = figure_ylim
        self.figure_format = figure_format 
        self.figure_labelfontsize = figure_labelfontsize
        self.figure_tickfontsize = figure_tickfontsize
        
        # self.timestep = timestep
        
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
        
        if not os.path.exists(figure_outputdir):
            os.makedirs(figure_outputdir)
            
            
    def _setup_figure(self) -> typing.Tuple[plt.Figure, plt.Axes]:
        """
        Create and setup the figure and axes.
        
        Returns:
            Tuple of matplotlib figure and axes
        """
        fig, ax = plt.subplots(1, 1, 
                               figsize=self.figure_size, 
                               dpi=self.figure_dpi)
        ax.set_aspect(1)
        return fig, ax

    def _setup_colorbar(self, fig: plt.Figure, ax: plt.Axes, mappable) -> None:
        """
        Setup colorbar for the plot.
        
        Args:
            fig (plt.Figure): Matplotlib figure
            ax (plt.Axes): Matplotlib axes
            mappable: Mappable object for colorbar
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
        
    def _adjust_axes(self, fig: plt.Figure, ax: plt.Axes) -> None:
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
        ax.grid(linestyle='dashed', zorder=1)
    
    def auto_filename(self):
        key_list = [self.pcolor_key, 
                    self.contour_key, 
                    self.quiver_u_key, 
                    self.quiver_v_key]
        # fig_title = f"{self.pcolor_key}_{self.contour_key}_{self.quiver_u_key}_{self.quiver_v_key}_{self.timestep:05d}.{self.figure_format}"
        fig_filename = '_'.join(filter(None, key_list))
        return fig_filename
    
    
    def _finalize_figure(self, fig: plt.Figure, ax: plt.Axes) -> None:
        """
        Finalize the figure by a suptitle and saving.
        
        Args:
            ax (plt.Axes): Matplotlib axes to finalize
        """
        
        # Add title at the bottom
        ax.set_title(self.figure_title, fontsize=self.figure_labelfontsize)
        
        # Save the figure
        if self.figure_filename:
            figure_filename = self.figure_filename
        else:
            figure_filename = self.auto_filename()
        
        fig.savefig(os.path.join(self.figure_outputdir, 
                                 f"{figure_filename}.{self.figure_format}"),
                    format=self.figure_format, 
                    bbox_inches='tight')
        
        # Close the figure
        plt.close(fig)
    
    def dash_patterns(self) -> typing.List:
        """
        Custom dash patterns.
    
        Returns:
        list: List of as many custom dash patterns as self.contour_levels.
        """
        N = self.contour_levels
        dash_patterns = []
        for i in range(N):
            # Define a custom dash pattern
            on_off_sequence = (i % (N + 2) + 1, i % (N + 2)//2 + 1)  # Vary the lengths of dashes and spaces
            dash_patterns.append((0, on_off_sequence))
        return dash_patterns
    
    def plot_quad_data(self, time_step: int, 
                       center_grid_X: np.ndarray, center_grid_Y: np.ndarray, 
                       cell_data: typing.Dict) -> None:
        """
        Plot quad cell data.
        
        Args:
            time_step (int): Current time step
            center_grid_X (np.ndarray): Grid X coordinates
            center_grid_Y (np.ndarray): Grid Y coordinates
            cell_data (Dict): Dictionary of cell data
        """
        fig, ax = self._setup_figure()
        
        # Plot SSH   
        if self.pcolor_key:
            pcolor_plot = ax.pcolor(center_grid_X, center_grid_Y, 
                                 cell_data[self.pcolor_key],
                                 vmin=self.pcolor_min, 
                                 vmax=self.pcolor_max,
                                 cmap=self.pcolor_cmap, 
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
                         f'{self.quiver_lengthkey} {self.quiver_units}', 
                         labelpos='E',
                         fontproperties={'size':self.quiver_fontsize})
        
        
        # Adjust the axes and grid looks
        self._adjust_axes(fig, ax)
        
        # Add the colorbar if any
        if self.pcolor_key:
            self._setup_colorbar(fig, ax, pcolor_plot)
        
        # Ada a title and save
        self._finalize_figure(fig, ax)
    
    def plot_triangle_data(self, 
                           tripcolor_tri: mpl.tri.Triangulation,
                           tricontour_tri: mpl.tri.Triangulation,
                           cell_data: typing.Dict, 
                           cell_centers_array: np.ndarray) -> None:
        """
        Plot triangle cell data.
        
        Args:
            tripcolor_tri (mpl.tri.Triangulation): Triangulation for color plot
            tricontour_tri (mpl.tri.Triangulation): Triangulation for contour plot
            cell_data (Dict): Dictionary of cell data
            cell_centers_array (np.ndarray): Cell center coordinates
        """
        fig, ax = self._setup_figure()
        
        # Plot SSH   
        if self.pcolor_key:
            ssh_plot = ax.tripcolor(tripcolor_tri, 
                                    cell_data[self.pcolor_key],
                                    vmin=self.pcolor_min, 
                                    vmax=self.pcolor_max,
                                    cmap=self.pcolor_cmap, 
                                    zorder=0)
        
        # Plot the grid
        if self.triplot:
            ax.triplot(tripcolor_tri, 
                       linewidth=self.triplot_linewidth, 
                       color=self.triplot_color)
        
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
                                     zorder=10)
            ax.quiverkey(current_plot, 
                         self.quiver_positionkey[0], 
                         self.quiver_positionkey[1],  
                         self.quiver_lengthkey, 
                         f'{self.quiver_lengthkey} {self.quiver_units}', 
                         labelpos='E',
                         fontproperties={'size':self.quiver_fontsize})
        
        # Adjust the axes and grid looks
        self._adjust_axes(fig, ax)
        
        # Add the colorbar if any
        if self.pcolor_key:
            self._setup_colorbar(fig, ax, ssh_plot)
        
        # Ada a title and save
        self._finalize_figure(fig, ax)