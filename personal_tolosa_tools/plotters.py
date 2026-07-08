#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import typing
from copy import deepcopy
import shutil

import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt


# Paramètres d'affichage pour que ce soit toujours plus propre
def latex_available():
    # quick check: is the latex binary even on PATH?
    if shutil.which("latex") is None:
        return False
    # real check: try actually rendering something with it
    try:
        fig = plt.figure()
        fig.text(0, 0, r"$\alpha$", usetex=True)
        fig.canvas.draw()
        plt.close(fig)
        return True
    except Exception:
        plt.close("all")
        return False


mpl.use("agg")
plt.rcParams["font.family"] = "cmr10"
plt.rcParams["font.size"] = 8
if latex_available():
    plt.rcParams["text.usetex"] = True
    plt.rcParams["axes.formatter.use_mathtext"] = True
    plt.rcParams["mathtext.fontset"] = "custom"
    plt.rcParams["mathtext.rm"] = "cmr10"
    plt.rcParams["mathtext.it"] = "cmr10:italic"
    plt.rcParams["mathtext.bf"] = "cmr10:bold"


class Plotter:
    """
    Builds and saves matplotlib figures for structured (quad) and unstructured
    (triangle) mesh data, with optional pcolor, contour, quiver, scatter, and
    rectangle overlays.
    """

    def __init__(
        self,
        figure_outputdir: str = "./Figures/",
        figure_title: str = "",
        figure_filename: str = "",
        figure_save: bool = True,
        figure_size: tuple = (4, 4),
        figure_dpi: int = 300,
        figure_xlabel: str = "X coordinate",
        figure_ylabel: str = "Y coordinate",
        figure_xlim: tuple = (None, None),
        figure_ylim: tuple = (None, None),
        figure_format: str = "png",
        figure_labelfontsize: int = 8,
        figure_tickfontsize: int = 7,
        figure_grid_linewidth: float = 0.5,
        figure_grid_linestyle: str = "dashed",
        figure_axes_color="k",
        figure_axes_aspect: float = 1.0,
        figure_subplots_kwargs: dict = {},
        pcolor_key: str = "ssh",
        pcolor_max: float = None,
        pcolor_min: float = None,
        pcolor_cmap: str = "RdBu_r",
        pcolor_units: str = "m",
        pcolor_kwargs: dict = {},
        triplot: bool = False,
        triplot_color: str = "seagreen",
        triplot_linewidth: float = 0.2,
        triplot_kwargs: dict = {},
        contour_key: str = "bathy",
        contour_levels: int = 4,
        contour_colors: str = "r",
        contour_linewidths: float = 1,
        contour_units: str = "m",
        contour_fontsize: int = 8,
        contour_kwargs: dict = {},
        quiver_u_key: str = "u",
        quiver_v_key: str = "v",
        quiver_scale: float = 100,
        quiver_spacing: int = 10,
        quiver_positionkey: tuple = (0.85, 1.03),
        quiver_lengthkey: float = 1,
        quiver_units: str = "m/s",
        quiver_fontsize: int = 8,
        quiver_kwargs: dict = {},
        scatter_from_points: bool = True,
        scatter_c_key: str = "",
        scatter_s: float = 0.1,
        scatter_max: float = None,
        scatter_min: float = None,
        scatter_cmap: str = "jet",
        scatter_kwargs: dict = {},
        rectangle_positions=None,
        rectangle_colors="k",
        rectangle_linewidths: float = 1,
        line_plots: list[tuple[list, dict]] = [([], {})],
        collections: list = [],
    ) -> None:
        """
        Parameters
        ----------
        figure_outputdir : str
            Directory for saved figures. Created automatically if absent.
        figure_title : str
            Axes title.
        figure_filename : str
            Output filename stem. Auto-generated from data keys when empty.
        figure_save : bool
            When True, save and close the figure. When False, return (fig, ax).
        figure_size : tuple
            Figure size in inches (width, height).
        figure_dpi : int
            Figure resolution.
        figure_xlabel, figure_ylabel: str 
            X and Y axis labels. Default "X coordinate", "Y coordinate".
        : str = "Y coordinate",
        figure_xlim, figure_ylim : tuple of (float|None, float|None)
            Axis limits. None on either side leaves that bound auto-scaled.
            Artists outside these bounds are clipped.
        figure_format : str
            File format passed to ``fig.savefig`` (e.g. 'png', 'pdf').
        figure_labelfontsize : int
            Font size for axis and colorbar labels.
        figure_tickfontsize : int
            Font size for tick labels.
        figure_grid_linewidth : float
            Grid line width. Set to 0 to disable the grid.
        figure_grid_linestyle : str
            Grid line style (e.g. 'dashed', 'dotted').
        figure_axes_color : color
            Color applied to spines and ticks.
        figure_axes_aspect : float
            Axes aspect ratio passed to ``ax.set_aspect``.
        figure_subplots_kwargs : dict
            Extra keyword arguments forwarded to ``plt.subplots``.

        pcolor_key : str
            Key in *cell_data* used for the pcolor/tripcolor layer.
        pcolor_max, pcolor_min : float or None
            Color scale bounds.
        pcolor_cmap : str
            Colormap name.
        pcolor_units : str
            Unit label shown on the colorbar.
        pcolor_kwargs : dict
            Extra kwargs forwarded to ``ax.pcolor`` / ``ax.tripcolor``.

        triplot : bool
            When True, overlay the triangulation edges.
        triplot_color : str
            Edge color for the triangle overlay.
        triplot_linewidth : float
            Line width for the triangle overlay.
        triplot_kwargs : dict
            Extra kwargs forwarded to ``ax.triplot``.

        contour_key : str
            Key in *cell_data* used for the contour/tricontour layer.
        contour_levels : int
            Number of contour lines.
        contour_colors : str
            Color(s) for contour lines.
        contour_linewidths : float
            Line width for contour lines.
        contour_units : str
            Unit label for contour clabels.
        contour_fontsize : int
            Font size for contour labels.
        contour_kwargs : dict
            Extra kwargs forwarded to ``ax.contour`` / ``ax.tricontour``.

        quiver_u_key, quiver_v_key : str
            Keys in *cell_data* for the U and V vector components.
        quiver_scale : float
            Quiver scale factor.
        quiver_spacing : int
            Subsampling stride (quad) or divisor (triangle) for quiver arrows.
        quiver_positionkey : tuple
            (X, Y) position of the quiver key in axes-fraction coordinates.
        quiver_lengthkey : float
            Reference arrow length for the quiver key.
        quiver_units : str
            Unit label for the quiver key.
        quiver_fontsize : int
            Font size for the quiver key label.
        quiver_kwargs : dict
            Extra kwargs forwarded to ``ax.quiver``.

        scatter_from_points : bool
            When True, scatter uses *points_array*; otherwise *cell_centers_array*.
        scatter_c_key : str
            Key used to color scatter points. No scatter layer when empty.
        scatter_s : float
            Marker size for scatter points.
        scatter_max, scatter_min : float or None
            Color scale bounds for scatter.
        scatter_cmap : str
            Colormap name for scatter.
        scatter_kwargs : dict
            Extra kwargs forwarded to ``ax.scatter``.

        rectangle_positions : list of (xmin, xmax, ymin, ymax) or single tuple
            Zoom-box outlines drawn on the figure.
        rectangle_colors : str, list, or 'auto'
            Colors for each rectangle. 'auto' samples evenly from the jet cmap.
        rectangle_linewidths : float or list
            Line widths for each rectangle.

        line_plots : list of (args, kwargs)
            Each entry is forwarded as ``ax.plot(*args, **kwargs)``.
        collections : list of matplotlib Collection
            Pre-built collections added via ``ax.add_collection``.
        """
        self.figure_outputdir = figure_outputdir
        self.figure_title = figure_title
        self.figure_filename = figure_filename
        self.figure_save = figure_save
        self.figure_size = figure_size
        self.figure_dpi = figure_dpi
        self.figure_xlabel = figure_xlabel
        self.figure_ylabel = figure_ylabel
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

        self.rectangle_positions = (
            rectangle_positions if rectangle_positions is not None else []
        )
        self.rectangle_colors = rectangle_colors if rectangle_colors is not None else []
        self.rectangle_linewidths = (
            rectangle_linewidths if rectangle_linewidths is not None else []
        )

        self.line_plots = line_plots
        self.collections = collections

        if self.figure_save and not os.path.exists(figure_outputdir):
            os.makedirs(figure_outputdir)

    # ------------------------------------------------------------------
    # Figure / axes setup
    # ------------------------------------------------------------------

    def _setup_figure(self) -> typing.Tuple[plt.Figure, plt.Axes]:
        """Create the figure and style the spines."""
        fig, ax = plt.subplots(
            1,
            1,
            figsize=self.figure_size,
            dpi=self.figure_dpi,
            **self.figure_subplots_kwargs,
        )
        for spine in ax.spines.values():
            spine.set_color(self.figure_axes_color)
        ax.set_aspect(self.figure_axes_aspect)
        return fig, ax

    def _setup_colorbar(self, fig: plt.Figure, ax: plt.Axes, mappable) -> None:
        """Attach a vertical colorbar to the right of *ax*."""
        cax = fig.add_axes(
            [
                ax.get_position().x1 + 0.03,
                ax.get_position().y0,
                0.05,
                ax.get_position().height,
            ]
        )
        fig.colorbar(mappable, cax=cax)
        cax.tick_params(axis="y", direction="in")
        cax.set_yticks(
            cax.get_yticks()[1:-1],
            labels=cax.get_yticklabels()[1:-1],
            rotation=90,
            va="center",
            fontsize=self.figure_tickfontsize,
        )
        cax.set_ylabel(
            f"{self.pcolor_key} in {self.pcolor_units}",
            fontsize=self.figure_labelfontsize,
        )

    def _apply_limits_and_clip(self, ax: plt.Axes) -> None:
        """
        Apply axis limits and clip every artist to the data box.

        Limits come from ``figure_xlim`` / ``figure_ylim``; a None on either
        side leaves that bound auto-scaled. After the limits are set, every
        collection, patch, and line is given the axes patch as a clip path so
        nothing bleeds outside the data box.
        """
        ax.relim()
        ax.autoscale_view()
        for col in ax.collections:
            bbox = col.get_datalim(ax.transData)
            if bbox.width > 0 or bbox.height > 0:  # skip empty/degenerate bboxes
                ax.update_datalim(bbox.get_points())
        ax.autoscale_view()  # reapply after updating datalim from collections

        xmin, xmax = self.figure_xlim
        ymin, ymax = self.figure_ylim
        cur_x = ax.get_xlim()
        cur_y = ax.get_ylim()

        ax.set_xlim(
            xmin if xmin is not None else cur_x[0],
            xmax if xmax is not None else cur_x[1],
        )
        ax.set_ylim(
            ymin if ymin is not None else cur_y[0],
            ymax if ymax is not None else cur_y[1],
        )

        clip_rect = ax.patch
        for artist in (*ax.collections, *ax.patches, *ax.lines):
            artist.set_clip_path(clip_rect)
            artist.set_clip_on(True)

    def _adjust_axes(self, ax: plt.Axes) -> None:
        """Style ticks, labels, and grid. Call after limits have been set."""
        ax.tick_params(
            axis="both",
            direction="in",
            labelcolor="k",
            colors=self.figure_axes_color,
            width=self.figure_grid_linewidth,
            labelsize=self.figure_tickfontsize,
        )

        ax.set_xticks(ax.get_xticks()[1:-1])
        ax.set_yticks(ax.get_yticks()[1:-1])
        for lbl in ax.get_yticklabels():
            lbl.set_rotation(90)
            lbl.set_va("center")

        ax.xaxis.get_offset_text().set_fontsize(self.figure_tickfontsize)
        ax.yaxis.get_offset_text().set_fontsize(self.figure_tickfontsize)

        ax.set_xlabel(self.figure_xlabel, fontsize=self.figure_labelfontsize)
        ax.set_ylabel(self.figure_ylabel, fontsize=self.figure_labelfontsize)

        if self.figure_grid_linewidth:
            ax.grid(
                linestyle=self.figure_grid_linestyle,
                zorder=1,
                linewidth=self.figure_grid_linewidth,
                color=self.figure_axes_color,
                alpha=0.5,
            )

    def _finalize_figure(
        self, fig: plt.Figure, ax: plt.Axes
    ) -> tuple[plt.Figure, plt.Axes] | None:
        """Add the title, then save-and-close or return the figure."""
        ax.set_title(self.figure_title, fontsize=self.figure_labelfontsize)
        filename = self.figure_filename or self.auto_filename()

        if self.figure_save:
            fig.savefig(
                os.path.join(self.figure_outputdir, f"{filename}.{self.figure_format}"),
                format=self.figure_format,
                bbox_inches="tight",
            )
            plt.close(fig)
        else:
            return fig, ax

    # ------------------------------------------------------------------
    # Shared drawing helpers (used by both plot methods)
    # ------------------------------------------------------------------

    def _draw_collections_and_lines(self, ax: plt.Axes) -> None:
        """Add stored collections and line plots to *ax*."""
        for col in self.collections:
            ax.add_collection(col)
        for args, kwargs in self.line_plots:
            ax.plot(*args, **kwargs)

    def _draw_rectangles(self, ax: plt.Axes) -> None:
        """Draw zoom-box rectangles on *ax*."""
        positions, colors, linewidths = self.updated_rectangle_args()
        for (xmin, xmax, ymin, ymax), c, lw in zip(positions, colors, linewidths):
            rect = mpl.patches.Rectangle(
                (xmin, ymin),
                xmax - xmin,
                ymax - ymin,
                edgecolor=c,
                facecolor=(1, 1, 1, 0),
                linewidth=lw,
                zorder=100,
            )
            ax.add_patch(rect)

    def _postprocess(self, fig: plt.Figure, ax: plt.Axes, mappable=None):
        """
        Common closing steps shared by both plot methods:
        rectangles → limits + clipping → tick/grid styling → colorbar → save.
        """
        self._draw_rectangles(ax)
        self._apply_limits_and_clip(ax)
        self._adjust_axes(ax)
        if mappable is not None:
            self._setup_colorbar(fig, ax, mappable)
        return self._finalize_figure(fig, ax)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def auto_filename(self) -> str:
        """Build a filename stem from the active data keys."""
        keys = [self.pcolor_key, self.contour_key, self.quiver_u_key, self.quiver_v_key]
        return "_".join(filter(None, keys))

    def updated_rectangle_args(self) -> typing.Tuple[list, list, list]:
        """
        Normalise ``rectangle_positions``, ``rectangle_colors``, and
        ``rectangle_linewidths`` into three lists of equal length.
        """
        # --- positions -------------------------------------------------------
        pos = self.rectangle_positions
        if pos is None:
            positions = []
        elif (
            isinstance(pos, (list, tuple))
            and len(pos) == 4
            and all(isinstance(v, (int, float)) for v in pos)
        ):
            positions = [pos]  # single rectangle given as a flat 4-tuple
        else:
            positions = list(pos)

        n = len(positions)
        if n == 0:
            return [], [], []

        # --- colors ----------------------------------------------------------
        c = self.rectangle_colors
        if c is None:
            colors = ["k"] * n
        elif c == "auto":
            colors = self.evenly_spaced_colors(n, colormap_name="jet")
        elif not isinstance(c, list):
            colors = [c] * n
        else:
            colors = c
        if len(colors) != n:
            colors = [colors[0]] * n

        # --- linewidths ------------------------------------------------------
        lw = self.rectangle_linewidths
        if isinstance(lw, (int, float)):
            linewidths = [lw] * n
        else:
            linewidths = list(lw)
        if len(linewidths) != n:
            linewidths = [linewidths[0]] * n

        return positions, colors, linewidths

    @property
    def zoomed_plotters(self) -> typing.Optional[typing.List["Plotter"]]:
        """
        Return one deep-copied Plotter per rectangle, each zoomed to the
        corresponding bounds. Filenames are suffixed ``_zoom_0``, ``_zoom_1``, …

        Returns None when no rectangles are defined.
        """
        positions, colors, _ = self.updated_rectangle_args()
        if not positions:
            return None

        plotters = []
        for i, ((xmin, xmax, ymin, ymax), c) in enumerate(zip(positions, colors)):
            p = deepcopy(self)
            p.figure_axes_color = c
            p.figure_xlim = (xmin, xmax)
            p.figure_ylim = (ymin, ymax)
            p.rectangle_positions = []
            p.figure_filename = self.figure_filename + f"_zoom_{i}"
            plotters.append(p)
        return plotters

    def dash_patterns(self) -> typing.List:
        """Return ``contour_levels`` distinct dash patterns for contour lines."""
        N = self.contour_levels
        return [(0, (i % (N + 2) + 1, i % (N + 2) // 2 + 1)) for i in range(N)]

    def evenly_spaced_colors(
        self, n: int, colormap_name: str = "viridis"
    ) -> typing.List:
        """Return *n* colors sampled evenly from a named matplotlib colormap."""
        cmap = mpl.cm.get_cmap(colormap_name)
        return [cmap(i / max(n - 1, 1)) for i in range(n)]

    # ------------------------------------------------------------------
    # Public plot methods
    # ------------------------------------------------------------------
    def plot_xy(
        self, x: np.ndarray, y: np.ndarray, **kwargs
    ) -> tuple[plt.Figure, plt.Axes] | None:
        self.line_plots = [([x, y], kwargs)]
        fig, ax = self._setup_figure()
        self._draw_collections_and_lines(ax)
        return self._postprocess(fig, ax)

    def plot_quad_data(
        self,
        center_grid_X: np.ndarray,
        center_grid_Y: np.ndarray,
        cell_data: typing.Dict,
    ) -> tuple[plt.Figure, plt.Axes] | None:
        """
        Plot data on a structured (quad) grid.

        Parameters
        ----------
        center_grid_X, center_grid_Y : np.ndarray
            2-D coordinate arrays for cell centres.
        cell_data : dict
            Data arrays keyed by ``pcolor_key``, ``contour_key``, and the
            ``quiver_*_key`` attributes.
        """
        fig, ax = self._setup_figure()
        mappable = None

        if self.pcolor_key:
            mappable = ax.pcolor(
                center_grid_X,
                center_grid_Y,
                cell_data[self.pcolor_key],
                vmin=self.pcolor_min,
                vmax=self.pcolor_max,
                cmap=self.pcolor_cmap,
                rasterized=True,
                zorder=0,
                **self.pcolor_kwargs,
            )

        if self.contour_key:
            cs = ax.contour(
                center_grid_X,
                center_grid_Y,
                cell_data[self.contour_key],
                levels=self.contour_levels,
                linestyles=self.dash_patterns(),
                linewidths=self.contour_linewidths,
                colors=self.contour_colors,
                zorder=2,
                **self.contour_kwargs,
            )
            ax.clabel(cs, fontsize=self.contour_fontsize)

        if self.quiver_u_key and self.quiver_v_key:
            N = self.quiver_spacing
            qp = ax.quiver(
                center_grid_X[::N, ::N],
                center_grid_Y[::N, ::N],
                cell_data[self.quiver_u_key][::N, ::N],
                cell_data[self.quiver_v_key][::N, ::N],
                scale=self.quiver_scale,
                scale_units="width",
                zorder=10,
                **self.quiver_kwargs,
            )
            ax.quiverkey(
                qp,
                *self.quiver_positionkey,
                self.quiver_lengthkey,
                f"{self.quiver_lengthkey:0.3f} {self.quiver_units}",
                labelpos="E",
                fontproperties={"size": self.quiver_fontsize},
            )

        self._draw_collections_and_lines(ax)
        return self._postprocess(fig, ax, mappable)

    def plot_triangle_data(
        self,
        points_array: np.ndarray,
        tripcolor_tri: mpl.tri.Triangulation,
        tricontour_tri: mpl.tri.Triangulation,
        cell_centers_array: np.ndarray,
        cell_data: typing.Dict,
        point_data: typing.Dict,
    ) -> tuple[plt.Figure, plt.Axes] | None:
        """
        Plot data on an unstructured (triangle) mesh.

        Parameters
        ----------
        points_array : np.ndarray, shape (N, 2)
            Node coordinates used by the scatter layer.
        tripcolor_tri : mpl.tri.Triangulation
            Triangulation for the tripcolor layer.
        tricontour_tri : mpl.tri.Triangulation
            Triangulation for the tricontour layer.
        cell_centers_array : np.ndarray, shape (N, 2)
            Cell-centre coordinates used by the quiver layer.
        cell_data : dict
            Cell-centred data arrays.
        point_data : dict
            Node-centred dictionary of data arrays (used when ``scatter_from_points`` is True).
        """
        fig, ax = self._setup_figure()
        mappable = None

        if self.pcolor_key:
            mappable = ax.tripcolor(
                tripcolor_tri,
                cell_data[self.pcolor_key].squeeze(),
                vmin=self.pcolor_min,
                vmax=self.pcolor_max,
                cmap=self.pcolor_cmap,
                rasterized=True,
                clip_on=True,
                zorder=0,
                **self.pcolor_kwargs,
            )

        if self.triplot:
            ax.triplot(
                tripcolor_tri,
                linewidth=self.triplot_linewidth,
                color=self.triplot_color,
                clip_on=True,
                **self.triplot_kwargs,
            )

        if self.contour_key:
            cs = ax.tricontour(
                tricontour_tri,
                cell_data[self.contour_key].squeeze(),
                levels=self.contour_levels,
                linestyles=self.dash_patterns(),
                linewidths=self.contour_linewidths,
                colors=self.contour_colors,
                zorder=2,
                **self.contour_kwargs,
            )
            ax.clabel(cs, fontsize=self.contour_fontsize)

        if self.scatter_c_key:
            print(point_data[self.scatter_c_key])
            if self.scatter_from_points:
                x, y = points_array[:, 0], points_array[:, 1]
                data = point_data[self.scatter_c_key].squeeze()
            else:
                x, y = cell_centers_array[:, 0], cell_centers_array[:, 1]
                data = cell_data.squeeze()
            ax.scatter(
                x,
                y,
                c=data,
                s=self.scatter_s,
                vmin=self.scatter_min,
                vmax=self.scatter_max,
                cmap=self.scatter_cmap,
                **self.scatter_kwargs,
            )

        if self.quiver_u_key and self.quiver_v_key:
            n_cells = len(cell_data[self.quiver_u_key])
            idx = np.random.choice(
                n_cells, size=n_cells // self.quiver_spacing, replace=False
            )
            qp = ax.quiver(
                cell_centers_array[:, 0][idx],
                cell_centers_array[:, 1][idx],
                cell_data[self.quiver_u_key].squeeze()[idx],
                cell_data[self.quiver_v_key].squeeze()[idx],
                scale=self.quiver_scale,
                scale_units="width",
                clip_on=True,
                zorder=10,
                **self.quiver_kwargs,
            )
            ax.quiverkey(
                qp,
                *self.quiver_positionkey,
                self.quiver_lengthkey,
                f"{self.quiver_lengthkey} {self.quiver_units}",
                labelpos="E",
                fontproperties={"size": self.quiver_fontsize},
            )

        self._draw_collections_and_lines(ax)
        return self._postprocess(fig, ax, mappable)

    def Plot(self, processor) -> None:
        """
        Dispatch to the correct plot method based on ``processor.cell_type``.

        Parameters
        ----------
        processor : Processor
            Must expose ``cell_type`` (``'all_Quad'`` or ``'all_Triangle'``),
            ``cell_data``, ``cell_centers_array``, and either
            ``reshape_to_grid()`` (quad) or ``compute_triangulations()`` plus
            ``points_array`` and ``point_data`` (triangle).
        """
        print("       \033[32mOK:\033[0m Creating, plotting and saving")

        if processor.cell_type == "all_Quad":
            X, Y, data = processor.reshape_to_grid()
            self.plot_quad_data(X, Y, data)

        elif processor.cell_type == "all_Triangle":
            tri_color, tri_contour = processor.compute_triangulations()
            self.plot_triangle_data(
                processor.points_array,
                tri_color,
                tri_contour,
                processor.cell_centers_array,
                processor.cell_data,
                processor.point_data,
            )

        print("       \033[32mOK:\033[0m Figure created and saved")
