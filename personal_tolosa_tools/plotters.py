#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

import typing
from copy import deepcopy

import numpy as np

import matplotlib as mpl
import matplotlib.pyplot as plt

class Plotter:
    """
    Class that handles the construction of simple matplotlib figures on a fixed
    display format for extensive parallel use.
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
                 figure_grid_linestyle: str = 'dashed',
                 figure_axes_color = 'k',
                 figure_axes_aspect: float = 1.,
                 figure_subplots_kwargs: dict = {},
                 
                 pcolor_key: str = 'ssh',
                 pcolor_max: float = None, 
                 pcolor_min: float = None, 
                 pcolor_cmap: str = 'RdBu_r',
                 pcolor_units: str = 'm',
                 pcolor_kwargs: dict = {},
                 
                 triplot: bool = False,
                 triplot_color: str = 'seagreen',
                 triplot_linewidth: float = 0.2,
                 triplot_kwargs: dict = {},
                 
                 contour_key: str = 'bathy',
                 contour_levels: int = 4,
                 contour_colors: str = 'r',
                 contour_linewidths: float = 1,
                 contour_units: str = 'm',
                 contour_fontsize: int = 8,
                 contour_kwargs: dict = {},
                 
                 quiver_u_key: str = 'u',
                 quiver_v_key: str = 'v',
                 quiver_scale: float = 100, 
                 quiver_spacing: int = 10,
                 quiver_positionkey: tuple = (.85, 1.03),
                 quiver_lengthkey: float = 1,
                 quiver_units: str = 'm/s',
                 quiver_fontsize: int = 8,
                 quiver_kwargs: dict = {},
                 
                 scatter_from_points: bool = True,
                 scatter_c_key: str = '',
                 scatter_s: float = .1,
                 scatter_max: float = None, 
                 scatter_min: float = None, 
                 scatter_cmap: str = 'jet',
                 scatter_kwargs: dict = {},
                 
                 rectangle_positions = None,
                 rectangle_colors = 'k',
                 rectangle_linewidths: float = 1,
                 
                 line_plots: list = [], # list of (args, kwargs) tuples to be plotted last
                 
                 collections: list = []
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
        # timestep (int, optional): Timestep corresponding to the data. Defaults to 4.
        
        
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
        self.figure_grid_linestyle = figure_grid_linestyle
        self.figure_axes_color = figure_axes_color 
        self.figure_axes_aspect = figure_axes_aspect
        self.figure_subplots_kwargs = figure_subplots_kwargs
        
        # self.timestep = timestep
        
        self.pcolor_key = pcolor_key
        self.pcolor_max = pcolor_max
        self.pcolor_min = pcolor_min
        self.pcolor_cmap = pcolor_cmap
        self.pcolor_units = pcolor_units
        self.pcolor_kwargs = pcolor_kwargs
        
        self.triplot = triplot
        self.triplot_color = triplot_color
        self.triplot_linewidth = triplot_linewidth
        self.triplot_kwargs = triplot_kwargs
        
        self.contour_key = contour_key
        self.contour_levels = contour_levels
        self.contour_colors = contour_colors
        self.contour_linewidths = contour_linewidths
        self.contour_units = contour_units
        self.contour_fontsize = contour_fontsize
        self.contour_kwargs = contour_kwargs
        
        self.quiver_u_key = quiver_u_key
        self.quiver_v_key = quiver_v_key
        self.quiver_scale = quiver_scale
        self.quiver_spacing = quiver_spacing
        self.quiver_positionkey = quiver_positionkey
        self.quiver_lengthkey = quiver_lengthkey
        self.quiver_units = quiver_units
        self.quiver_fontsize = quiver_fontsize
        self.quiver_kwargs = quiver_kwargs
        
        self.scatter_from_points = scatter_from_points
        self.scatter_c_key = scatter_c_key
        self.scatter_s = scatter_s
        self.scatter_max = scatter_max
        self.scatter_min = scatter_min
        self.scatter_cmap = scatter_cmap
        self.scatter_kwargs = scatter_kwargs
        
        self.rectangle_positions = rectangle_positions if rectangle_positions is not None else []
        self.rectangle_colors = rectangle_colors if rectangle_colors is not None else []
        self.rectangle_linewidths = rectangle_linewidths if rectangle_linewidths is not None else []
        
        self.line_plots = line_plots
        
        self.collections = collections
            
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
                               dpi=self.figure_dpi,
                               **self.figure_subplots_kwargs)
        ax.spines['bottom'].set_color(self.figure_axes_color)
        ax.spines['top'].set_color(self.figure_axes_color)
        ax.spines['left'].set_color(self.figure_axes_color)
        ax.spines['right'].set_color(self.figure_axes_color)

        ax.set_aspect(self.figure_axes_aspect)

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
        
        # Recompute limits from all artists, including collections
        ax.relim()
        ax.autoscale_view()
        for col in ax.collections:
            bbox = col.get_datalim(ax.transData)
            if bbox.width > 0 or bbox.height > 0:  # skip empty/degenerate bboxes
                ax.update_datalim(bbox.get_points())
        ax.autoscale_view()  # reapply after updating datalim from collections
        
        # Only override axes limits where the user explicitly provided a value
        xmin, xmax = self.figure_xlim
        ymin, ymax = self.figure_ylim
        
        if xmin is not None or xmax is not None:
            current_xlim = ax.get_xlim()
            ax.set_xlim(
                xmin if xmin is not None else current_xlim[0],
                xmax if xmax is not None else current_xlim[1]
            )
        
        if ymin is not None or ymax is not None:
            current_ylim = ax.get_ylim()
            ax.set_ylim(
                ymin if ymin is not None else current_ylim[0],
                ymax if ymax is not None else current_ylim[1]
            )
        
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
            ax.grid(linestyle=self.figure_grid_linestyle, 
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
                                 zorder=0,
                                 **self.pcolor_kwargs)
        
        # Plot bathymetry
        if self.contour_key:
            contour_plot = ax.contour(center_grid_X, center_grid_Y, 
                                    cell_data[self.contour_key],
                                    levels=self.contour_levels, 
                                    linestyles=self.generate_custom_dash_patterns(),
                                    linewidths=self.contour_linewidths, 
                                    colors=self.contour_colors, 
                                    zorder=2,
                                    **self.contour_kwargs)
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
                                     zorder=10,
                                     **self.quiver_kwargs)
            ax.quiverkey(quiver_plot, 
                         self.quiver_positionkey[0], 
                         self.quiver_positionkey[1], 
                         self.quiver_lengthkey, 
                         f'{self.quiver_lengthkey:0.3f} {self.quiver_units}', 
                         labelpos='E',
                         fontproperties={'size':self.quiver_fontsize})
    
        # Add all collections :
        for col in self.collections:
            ax.add_collection(col)
            
        # Add all Line2D :
        for a, k in self.line_plots:
            ax.plot(*a, **k)
            
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
                           points_array: np.ndarray,
                           tripcolor_tri: mpl.tri.Triangulation,
                           tricontour_tri: mpl.tri.Triangulation,
                           cell_centers_array: np.ndarray,
                           cell_data: typing.Dict, 
                           point_data) -> None:
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
                                    cell_data[self.pcolor_key].squeeze(),
                                    vmin=self.pcolor_min, 
                                    vmax=self.pcolor_max,
                                    cmap=self.pcolor_cmap,  
                                    rasterized=True,
                                    clip_on=True,
                                    zorder=0,
                                    **self.pcolor_kwargs)
        
        # Plot the grid
        if self.triplot:
            ax.triplot(tripcolor_tri, 
                       linewidth=self.triplot_linewidth, 
                       color=self.triplot_color,
                       clip_on=True,
                       **self.triplot_kwargs)
        
        # Plot tricontour
        if self.contour_key:
            bathy_plot = ax.tricontour(tricontour_tri, 
                                       cell_data[self.contour_key].squeeze(),
                                       levels=self.contour_levels, 
                                       linestyles=self.dash_patterns(),
                                       linewidths=self.contour_linewidths, 
                                       colors=self.contour_colors,
                                       zorder=2,
                                       **self.contour_kwargs)
            ax.clabel(bathy_plot, fontsize=self.contour_fontsize)
        
        
        # Plot scatter
        if self.scatter_c_key:
            if self.scatter_from_points == True:
                x, y = points_array[:, 0], points_array[:, 1]
                data = point_data.squeeze()
            else :
                x, y = cell_centers_array[:, 0], cell_centers_array[:, 1]
                data = cell_data.squeeze()
            ax.scatter(x, y, 
                       c=data[self.scatter_c_key],
                       s=self.scatter_s,
                       vmin=self.scatter_min, 
                       vmax=self.scatter_max,
                       cmap=self.scatter_cmap, 
                       **self.scatter_kwargs
                       )
        
        # Plot currents
        if self.quiver_u_key and self.quiver_v_key:
            random_indices = np.random.choice(len(cell_data[self.quiver_u_key]),
                                              size=len(cell_data[self.quiver_u_key])//self.quiver_spacing,
                                              replace=False)
            current_plot = ax.quiver(cell_centers_array[:,0][random_indices],
                                     cell_centers_array[:,1][random_indices],
                                     cell_data[self.quiver_u_key].squeeze()[random_indices],
                                     cell_data[self.quiver_v_key].squeeze()[random_indices],
                                     scale=self.quiver_scale, 
                                     scale_units='width', 
                                     clip_on=True,
                                     zorder=10,
                                     **self.quiver_kwargs)
            ax.quiverkey(current_plot, 
                         self.quiver_positionkey[0], 
                         self.quiver_positionkey[1],  
                         self.quiver_lengthkey, 
                         f'{self.quiver_lengthkey} {self.quiver_units}', 
                         labelpos='E',
                         fontproperties={'size':self.quiver_fontsize})
        
        # Add all collections :
        for col in self.collections:
            ax.add_collection(col)
            
        # Add all Line2D :
        for a, k in self.line_plots:
            ax.plot(*a, **k)
            
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
        
        # Add all Line2D :
        for a, k in self.line_plots:
            ax.plot(*a, **k)
        
        # Adjust the axes and grid looks
        self._adjust_axes(ax)
        
        # Add the colorbar if any
        if self.pcolor_key:
            self._setup_colorbar(fig, ax, ssh_plot)

        if self.figure_save:
            # Add a title and save
            self._finalize_figure(fig, ax)
        else :
            fig, ax = self._finalize_figure(fig, ax)
            return(fig, ax)
    
    def Plot(self, processor):
        """
        Launches the right plotter if a Proccessor is given

        Parameters
        ----------
        processor : Processor object
            Processor object countaining: 
                processor.cell_type,
                    processor.reshape_to_grid()
                    OR
                    processor.compute_triangulations(),
                    processor.cell_data,
                    processor.cell_centers_array

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
            self.plot_triangle_data(processor.points_array,
                                    tripcolor_tri, 
                                    tricontour_tri,
                                    processor.cell_centers_array,
                                    processor.cell_data, 
                                    processor.point_data)
        print("       \033[32mOK:\033[0m Figure created and saved")
