#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 30 11:19:16 2026

@author: llsaisset
"""

import sys
import argparse
from pathlib import Path

from copy import deepcopy
from contextlib import contextmanager, nullcontext
from time import perf_counter

from numpy import atleast_1d
from pandas import concat, DataFrame
from geopandas import read_file, GeoDataFrame, clip
from shapely import intersection, STRtree
from shapely.ops import linemerge, polygonize, unary_union, polygonize_full
from shapely.geometry import Polygon, MultiPolygon

import matplotlib.pyplot as plt

# =============================================================================
# Global hardcoded variables
# =============================================================================
METHODS = ['corrected', 'direct', 'extended', 'only_infra', 'C', 'D', 'E', 'O']
REMOVED_CATSLC = []#[9, 12, 13]


# =============================================================================
# Argument parsing
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="launch_create_inter_shp_reso.py",
        description="Generate an inner shoreline shapefile from EXTER + LTM inputs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # --- Positional arguments ------------------------------------------------
    parser.add_argument(
        "shp_file",
        type=Path,
        help="Path to the EXTER boundary shapefile (.shp).",
    )
    parser.add_argument(
        "reso",
        type=float,
        help=(
            "Target mesh resolution in metres. "
            "Controls smoothing, simplification and island-removal thresholds. "
        ),
    )

    # --- Processing parameters -----------------------------------------------
    parser.add_argument(
        "--method", "-m",
        type=str,
        default="C",
        choices=METHODS,
        metavar="METHOD",
        help=(
            "Method used to process the shoreline. "
            "Either :"
            "    - 'direct',     'd' : smoothed coast and islands only, no inner line"
            "    - 'extended',   'e' : smoothed coast and islands only, no inner line"
            "    - 'corrected',  'c' : keep inner lines with buffered infrastructures. (default)"
            "    - 'only_infra', 'o' : keep only buffered infras. (for later mesh depth correction)"
        ),
    )
    parser.add_argument(
        "--kept_poly",
        type=int,
        nargs="+",
        default=None,
        metavar="IDX",
        help=(
            "Space-separated indices of polygons to keep as coastline "
            "(0-based). "
            "If omitted, all candidate polygons are plotted and the user is "
            "prompted interactively."
        ),
    )
    parser.add_argument(
        "--exter_buff",
        type=float,
        default=-500,
        metavar="METERS",
        help=(
            "Buffer distance applied to the EXTER boundary "
            "(negative = inward shrink). Default: -500 m."
        ),
    )
    parser.add_argument(
        "--ltm_file",
        type=Path,
        default="/local/home/lsaisset/DATA/CONFIG_DATA/SHP_LAYERS/LTM_ATL.shp",
        help="Path to the LTM shoreline shapefile (.shp).",
    )
    parser.add_argument(
        "--workdir", "-w",
        type=str,
        default=None,
        help="Working directory (default: directory of the input mesh file).",
    )
    parser.add_argument(
        '--save_in', '-s',
        type=str,
        default='NEW.shp',
        help='Name of resulting file (default: INNER.shp).'
    )

    # --- Geometry tuning parameters ------------------------------------------
    parser.add_argument(
        "--tombolo_dmin",
        type=float,
        default=None,
        metavar="METERS",
        help=(
            "Inner radius of the tombolo-risk annular band: islands whose "
            "nearest larger neighbour is *closer* than this are assumed to be "
            "touching/overlapping and are kept. "
            "Default: 1 × reso."
        ),
    )
    parser.add_argument(
        "--tombolo_dmax",
        type=float,
        default=None,
        metavar="METERS",
        help=(
            "Outer radius of the tombolo-risk annular band: islands whose "
            "nearest larger neighbour is *farther* than this are left alone. "
            "Default: 3 × reso."
        ),
    )
    parser.add_argument(
        "--smooth_buff",
        type=float,
        default=None,
        metavar="METERS",
        help=(
            "Buffer distance used during the morphological open "
            "(buffer then unbuffer) smoothing pass. "
            "Default: 2 × reso."
        ),
    )
    parser.add_argument(
        "--simplify_tol",
        type=float,
        default=None,
        metavar="METERS",
        help=(
            "Douglas-Peucker tolerance applied when simplifying polygon "
            "boundaries (coast and infrastructure). "
            "Default: 0.1 × reso."
        ),
    )
    parser.add_argument(
        "--island_dist",
        type=float,
        default=None,
        metavar="METERS",
        help=(
            "Proximity threshold for island removal: an island is a removal "
            "candidate if a larger neighbour lies within this distance. "
            "Default: 5 × reso."
        ),
    )
    parser.add_argument(
        "--island_perim",
        type=float,
        default=None,
        metavar="METERS",
        help=(
            "Minimum perimeter (metres) below which a polygon is removed "
            "during the small-island filtering step. "
            "Default: 10 × reso."
        ),
    )
    parser.add_argument(
        "--island_area",
        type=float,
        default=None,
        metavar="M2",
        help=(
            "Minimum area (m²) below which a polygon is removed during the "
            "small-island filtering step. "
            "Default: 15 × reso²."
        ),
    )
    parser.add_argument(
        "--infra_buff",
        type=float,
        default=None,
        metavar="METERS",
        help=(
            "Buffer distance applied to infrastructure lines to generate "
            "their contour polygon. "
            "Default: 1 × reso."
        ),
    )
    parser.add_argument(
        "--infra_sep_buff",
        type=float,
        default=None,
        metavar="METERS",
        help=(
            "Larger buffer distance applied to infrastructure lines to carve "
            "them out of the coast/island polygons (separation mask). "
            "Default: 3 × reso."
        ),
    )

    # --- Behaviour flags ------------------------------------------------------
    parser.add_argument(
        "--no_plot",
        action="store_true",
        help=(
            "Skip the final diagnostic plot. "
            "Ignored when --kept_poly is not provided, because the "
            "interactive polygon-selection plot is always shown in that case."
        ),
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-step timing information.",
    )

    return parser.parse_args()


# =============================================================================
# Helpers
# =============================================================================

def p_colorize(text, color_code):
    """Adds color to terminal output"""
    return f"\033[{color_code}m{text}\033[0m"

def p_error(message, verbose=True):
    """Prints an error message in red"""
    print(f"    {p_colorize('ERROR:', '31')} {message}") if verbose else nullcontext()

def p_ok(message, verbose=True):
    """Prints an ok message in green"""
    print(f"       {p_colorize('OK:', '32')} {message}") if verbose else nullcontext()

def p_warning(message, verbose=True):
    """Prints a warning message in yellow"""
    print(f"  {p_colorize('WARNING:', '33')} {message}") if verbose else nullcontext()


@contextmanager
def _timer(name: str = ''):
    start = perf_counter()
    yield
    end = perf_counter()
    p_ok(f"{name}   {end - start:.6f}s")

def p_timer(name: str = '', verbose: bool = False):
    """Returns p_timer if verbose, else a silent no-op."""
    return _timer(name) if verbose else nullcontext()

def _check_file(path: Path, label: str) -> None:
    if not path.is_file():
        p_error(f"[ERROR] {label} not found: {path}")
        sys.exit(1)

def _check_output_dir(path: Path) -> None:
    if not path.parent.exists():
        p_error(f"[ERROR] Output directory does not exist: {path.parent}")
        sys.exit(1)

def _resolve_args(args: argparse.Namespace) -> argparse.Namespace:
    """
    Post-process parsed arguments:
      1. Resolve all paths relative to the working directory.
      2. Fill geometry parameters that were left as None with their reso-relative defaults.
    """

    # -------------------------------------------------------------------------
    # 1. Working directory
    # -------------------------------------------------------------------------
    current_path = Path(args.workdir) if args.workdir is not None else Path.cwd()
    args.current_path = current_path

    # -------------------------------------------------------------------------
    # 2. Path resolution
    # -------------------------------------------------------------------------
    shp_file = Path(args.shp_file)
    args.shp_file = shp_file if shp_file.is_absolute() else current_path / shp_file

    ltm_file = Path(args.ltm_file)
    args.ltm_file = ltm_file if ltm_file.is_absolute() else current_path / ltm_file

    save_in = Path(args.save_in)
    args.save_in = save_in if save_in.is_absolute() else current_path / save_in

    # -------------------------------------------------------------------------
    # 3. Reso-relative geometry defaults
    # -------------------------------------------------------------------------
    r = args.reso
    defaults = {
        "tombolo_dmin":  1.0  * r,
        "tombolo_dmax":  3.0  * r,
        "smooth_buff":   2.0  * r,
        "simplify_tol":  0.1  * r,
        "island_dist":   5.0  * r,
        "island_perim":  10.0 * r,
        "island_area":   15.0 * r ** 2,
        "infra_buff":    0.5  * r,
        "infra_sep_buff":3.0  * r,
    }
    for attr, value in defaults.items():
        if getattr(args, attr) is None:
            setattr(args, attr, value)

    # -------------------------------------------------------------------------
    # 4. Index-relative geometry values
    # -------------------------------------------------------------------------
    args.kept_poly = atleast_1d(args.kept_poly) if args.kept_poly else []

    return args

def _print_nice_args(args: argparse.Namespace) -> None:
    """
    Prints the most important contents of the parsed arguments
    """
    v = args.verbose
    p_ok("Parsed arguments:",                           verbose=v)
    p_ok("  -- I/O --",                                 verbose=v)
    p_ok(f"  shp_file:       {args.shp_file}",          verbose=v)
    p_ok(f"  ltm_file:       {args.ltm_file}",          verbose=v)
    p_ok(f"  save_in:        {args.save_in}",           verbose=v)
    p_ok(f"  workdir:        {args.current_path}",      verbose=v)

    p_ok("  -- SHP construction method --",             verbose=v)
    p_ok(f"  method:         Methode {args.method}",    verbose=v)

    p_ok("  -- Mesh resolution --",                     verbose=v)
    p_ok(f"  reso:           {args.reso} m",            verbose=v)

    p_ok("  -- EXTER boundary --",                      verbose=v)
    p_ok(f"  exter_buff:     {args.exter_buff} m",      verbose=v)
    p_ok(f"  kept_poly:      {args.kept_poly}",         verbose=v)

    p_ok("  -- Tombolo filtering --",                   verbose=v)
    p_ok(f"  tombolo_dmin:   {args.tombolo_dmin} m",    verbose=v)
    p_ok(f"  tombolo_dmax:   {args.tombolo_dmax} m",    verbose=v)

    p_ok("  -- Smoothing --",                           verbose=v)
    p_ok(f"  smooth_buff:    {args.smooth_buff} m",     verbose=v)
    p_ok(f"  simplify_tol:   {args.simplify_tol} m",   verbose=v)

    p_ok("  -- Island removal --",                      verbose=v)
    p_ok(f"  island_dist:    {args.island_dist} m",     verbose=v)
    p_ok(f"  island_perim:   {args.island_perim} m",    verbose=v)
    p_ok(f"  island_area:    {args.island_area} m²",    verbose=v)

    p_ok("  -- Infrastructure --",                      verbose=v)
    p_ok(f"  infra_buff:     {args.infra_buff} m",      verbose=v)
    p_ok(f"  infra_sep_buff: {args.infra_sep_buff} m",  verbose=v)
    print()

def _plot_gdf(gdf: GeoDataFrame(),
               key: str = 'index') -> None:

    fig, ax = plt.subplots(1, 1, figsize=(12, 8))

    if key == 'index':
        column = gdf.index
    else:
        column = gdf.get(key)
    # Create the plot
    gdf.plot(column=column,
             cmap='viridis',
             categorical=True,
             legend=True,
             linewidth=1,
             ax=ax)

    # Improve legend
    if ax.get_legend():
        legend = ax.get_legend()
        legend.set_title('Physical Type')
        legend.set_bbox_to_anchor((1.05, 1))

    # Add grid
    ax.grid(True, linestyle='--', alpha=0.6, linewidth=0.5)
    ax.set_axisbelow(True)

    # Improve tick labels
    for label in ax.get_yticklabels():
        label.set_rotation(90)
        label.set_verticalalignment('center')
        label.set_horizontalalignment('center')

    for label in ax.get_xticklabels():
        label.set_rotation(0)
        label.set_verticalalignment('center')

    plt.tight_layout()
    plt.show()

    return None


# =============================================================================
# TOOLS FOR SHP PROCESSING
# =============================================================================

def select_size_dist(poly, p, a, d):
    work = deepcopy(poly)
    work['perimeter'] = work.geometry.boundary.length
    work['area'] = work.geometry.area
    islands_mask = work.physical == 'island'

    tree = STRtree(work.geometry)
    left, right = tree.query(work.geometry, predicate='dwithin', distance=d)

    df_pairs = DataFrame({'left': left, 'right': right})
    df_pairs = df_pairs[df_pairs['left'] != df_pairs['right']]
    df_pairs = df_pairs[islands_mask.iloc[df_pairs['left']].values]
    df_pairs['area_left']  = work['area'].iloc[df_pairs['left'].values].values
    df_pairs['area_right'] = work['area'].iloc[df_pairs['right'].values].values

    too_close = df_pairs[df_pairs['area_right'] > df_pairs['area_left']]['left'].unique()
    too_close = work.index[too_close]

    small_perimeter = work['perimeter'] < p
    small_area = work['area'] < a
    in_too_close = work.index.isin(too_close)

    to_remove = small_perimeter | small_area | in_too_close

    return to_remove


def select_dist_range(poly, dmin, dmax):
    """
    Select polygons that have a bigger neighbour at a distance in (dmin, dmax).

    i.e. not touching/overlapping (further than dmin) but still close (closer than dmax).
    This is useful to identify isolated small islands sitting just offshore
    of a larger feature — too far to be merged, too close to be kept.

    Parameters
    ----------
    poly : GeoDataFrame with a 'physical' column
    dmin : minimum distance to a bigger neighbour (exclusive)
    dmax : maximum distance to a bigger neighbour (inclusive)
    """
    work = poly.copy()
    work['area'] = work.geometry.area
    islands_mask = work.physical == 'island'

    tree = STRtree(work.geometry)

    left_far, right_far   = tree.query(work.geometry, predicate='dwithin', distance=dmax)
    left_near, right_near = tree.query(work.geometry, predicate='dwithin', distance=dmin)

    pairs_far  = set(zip(left_far.tolist(),  right_far.tolist()))
    pairs_near = set(zip(left_near.tolist(), right_near.tolist()))

    pairs_band = pairs_far - pairs_near

    df_pairs = DataFrame(list(pairs_band), columns=['left', 'right'])

    df_pairs = df_pairs[df_pairs['left'] != df_pairs['right']]
    df_pairs = df_pairs[islands_mask.iloc[df_pairs['left']].values]

    df_pairs['area_left']  = work['area'].iloc[df_pairs['left'].values].values
    df_pairs['area_right'] = work['area'].iloc[df_pairs['right'].values].values
    df_pairs = df_pairs[df_pairs['area_right'] > df_pairs['area_left']]

    idx = df_pairs['left'].unique()
    in_range = work.index[idx] if idx.size > 0 else []

    return work.index.isin(in_range)


# =============================================================================
# SHARED PROCESSING STEPS
# =============================================================================

def _format_exter(EXTER_gdf: GeoDataFrame,
                  LTM_gdf: GeoDataFrame,
                  args: argparse.Namespace,
                  need_proj: bool = False,
                  verbose: bool = True):
    """
    Build BND (single Polygon) and BND_buff (buffered boundary) from EXTER_gdf.

    Parameters
    ----------
    EXTER_gdf : GeoDataFrame
    LTM_gdf   : GeoDataFrame — only used when need_proj is True.
    args      : argparse.Namespace
    need_proj : bool
        If True, also return BND_buff_proj reprojected into LTM_gdf.crs.
        Used by methods C and O, which need to clip LTM features.
    verbose   : bool

    Returns
    -------
    BND           : GeoDataFrame  — single-row Polygon in EXTER_gdf.crs
    BND_buff      : GeoSeries     — buffered boundary in EXTER_gdf.crs
    BND_buff_proj : GeoDataFrame  — only when need_proj=True
    """
    with p_timer("Formatting the EXTER boundary", verbose=verbose):
        BND = GeoDataFrame(
            geometry=[Polygon(linemerge(EXTER_gdf.union_all()))],
            crs=EXTER_gdf.crs
        )
        BND_buff = BND.buffer(args.exter_buff)

        if need_proj:
            BND_buff_proj = (
                GeoDataFrame(geometry=BND_buff, crs=EXTER_gdf.crs)
                .to_crs(LTM_gdf.crs)
            )
            return BND, BND_buff, BND_buff_proj

    return BND, BND_buff


def _build_coast_island_polygons(EXTER_gdf: GeoDataFrame,
                                  LTM_gdf: GeoDataFrame,
                                  BND: GeoDataFrame,
                                  args: argparse.Namespace,
                                  verbose: bool = True) -> GeoDataFrame:
    """
    Clip and polygonize the LTM coastline inside BND, then tag each polygon
    as 'coast' or 'island'.

    The user is prompted interactively to select coast polygons when
    args.kept_poly is empty; the selection is stored back into args.kept_poly
    so subsequent calls within the same run skip the prompt.

    Parameters
    ----------
    EXTER_gdf : GeoDataFrame
    LTM_gdf   : GeoDataFrame
    BND       : GeoDataFrame — single-row Polygon (output of _format_exter)
    args      : argparse.Namespace

    Returns
    -------
    merged_gdf : GeoDataFrame with columns geometry and physical
    """
    with p_timer("Formatting the INNER contour into polygons", verbose=verbose):
        # Reproject LTM into EXTER crs and split coast / islands
        simpler_LTM = (
            GeoDataFrame(geometry=[linemerge(LTM_gdf.union_all())], crs=LTM_gdf.crs)
            .explode()
            .reset_index(drop=True)
            .to_crs(EXTER_gdf.crs)
        )
        coast_ini  = simpler_LTM[simpler_LTM.length == simpler_LTM.length.max()]
        island_ini = (
            simpler_LTM[simpler_LTM.index != coast_ini.index.values[0]]
            .reset_index(drop=True)
        )
        coast = coast_ini.reset_index(drop=True)

        # Clip coast to BND and polygonize
        simpler_coast = intersection(coast, BND).explode().reset_index(drop=True)
        merged = linemerge(
            list(simpler_coast.values.flatten())
            + list(BND.buffer(args.exter_buff / 2).boundary)
        )
        borders = unary_union(merged)
        poly = GeoDataFrame(geometry=list(polygonize(borders)), crs=coast.crs)

        # Interactive or pre-supplied coast polygon selection
        if not len(args.kept_poly):
            _plot_gdf(poly)
            inp = input("Polygons to be kept as shore (space separated):")
            args.kept_poly = atleast_1d(inp.split()).astype(int)
        coast_poly = poly.iloc[args.kept_poly].reset_index(drop=True)

        # Polygonize islands (closed lines inside BND)
        simpler_island = (
            island_ini[island_ini.covered_by(BND.iloc[0].values[0])]
            .reset_index(drop=True)
        )
        simpler_island = simpler_island[simpler_island.is_closed]
        island_poly = GeoDataFrame(
            geometry=list(polygonize(unary_union(simpler_island))),
            crs=simpler_island.crs
        )

        merged_gdf = concat(
            [island_poly.assign(physical='island'),
             coast_poly.assign(physical='coast')],
            ignore_index=True
        )

    return merged_gdf


def _remove_tombolo(merged_gdf: GeoDataFrame,
                    args: argparse.Namespace,
                    verbose: bool = True) -> GeoDataFrame:
    """
    Drop islands that sit in the tombolo-risk annular band (dmin, dmax) around
    a larger neighbour, to prevent artificial tombolo formation during smoothing.

    Parameters
    ----------
    merged_gdf : GeoDataFrame with physical column
    args       : argparse.Namespace

    Returns
    -------
    GeoDataFrame — tombolo candidates removed
    """
    with p_timer(
        f"Remove elements to avoid the creation of artificial tombolo"
        f" - {args.tombolo_dmin} < distance < {args.tombolo_dmax}",
        verbose=verbose
    ):
        to_remove = select_dist_range(merged_gdf, args.tombolo_dmin, args.tombolo_dmax)
        return merged_gdf[~to_remove].reset_index(drop=True)


def _smooth_and_simplify(merged_gdf: GeoDataFrame,
                          args: argparse.Namespace,
                          add_physical: bool = True,
                          verbose: bool = True) -> GeoDataFrame:
    """
    Morphological open (buffer / unbuffer) to smooth polygon boundaries,
    followed by a Douglas-Peucker simplification pass.

    Coast/island tags are re-derived from the original geometry after merging.

    Parameters
    ----------
    merged_gdf : GeoDataFrame with physical column
    args       : argparse.Namespace

    Returns
    -------
    smoothed : GeoDataFrame — Polygon rows with physical column
    """
    with p_timer(
        f"Smoothing the polygons"
        f" - buffer {args.smooth_buff} / unbuffer {-args.smooth_buff}",
        verbose=verbose
    ):
        poly_union = merged_gdf.geometry.buffer(args.smooth_buff).union_all()
        if poly_union.__class__ == Polygon:
            poly_union = MultiPolygon([poly_union])

        merged_union = (
            GeoDataFrame(geometry=list(poly_union.geoms), crs=merged_gdf.crs)
            .exterior
            .polygonize()
        )

        unbuffered = (
            merged_union.geometry
            .buffer(-1 * args.smooth_buff)
            .explode()
            .reset_index(drop=True)
        )

        smoothed = (
            GeoDataFrame(geometry=unbuffered, crs=unbuffered.crs)
            .explode()
            .reset_index(drop=True)
        )
        smoothed = smoothed[smoothed.geometry.geom_type == 'Polygon'].reset_index(drop=True)
        
        if add_physical:
            # Re-assign tags from original geometry
            coast_orig_union = merged_gdf[merged_gdf.physical == 'coast'].union_all()
            smoothed['physical'] = smoothed.geometry.apply(
                lambda g: 'coast' if g.intersects(coast_orig_union) else 'island'
            )

    with p_timer(
        f"Simplify the polygons - tolerance {args.simplify_tol}",
        verbose=verbose
        ):
        smoothed.geometry = smoothed.geometry.simplify(tolerance=args.simplify_tol)

    return smoothed


def _remove_small_islands(smoothed: GeoDataFrame,
                           args: argparse.Namespace,
                           verbose: bool = True) -> GeoDataFrame:
    """
    Drop polygons that are too small (perimeter / area thresholds) or too
    close to a larger neighbour (distance threshold).

    Parameters
    ----------
    smoothed : GeoDataFrame with physical column
    args     : argparse.Namespace

    Returns
    -------
    GeoDataFrame — small islands removed
    """
    with p_timer(
        f"Removing small islands or objects too close to one another"
        f" - perimeter {args.island_perim}"
        f" - area {args.island_area}"
        f" - distance {args.island_dist}",
        verbose=verbose
        ):
        to_remove = select_size_dist(
            smoothed, args.island_perim, args.island_area, args.island_dist
        )
        return smoothed[~to_remove].reset_index(drop=True)


def _polygons_to_lines(clean_inner_polygons: GeoDataFrame,
                        BND_buff,
                        verbose: bool = True) -> GeoDataFrame:
    """
    Convert coast/island Polygons to their boundary LineStrings and clip to
    BND_buff.

    Parameters
    ----------
    clean_inner_polygons : GeoDataFrame with physical column
    BND_buff             : GeoSeries — clipping boundary

    Returns
    -------
    clean_inner_lines : GeoDataFrame with physical column
    """
    with p_timer("Formatting the inner contours back to LineStrings", verbose=verbose):
        clean_inner_lines = GeoDataFrame(
            geometry=clean_inner_polygons.boundary,
            crs=clean_inner_polygons.crs
        )
        clean_inner_lines["physical"] = clean_inner_polygons.physical
        clean_inner_lines = (
            clip(clean_inner_lines, BND_buff, sort=True)
            .explode()
            .reset_index(drop=True)
        )

    return clean_inner_lines


def _extract_and_buffer_infra(LTM_gdf: GeoDataFrame,
                               BND_buff_proj: GeoDataFrame,
                               target_crs,
                               args: argparse.Namespace,
                               verbose: bool = True):
    """
    Clip LTM to BND_buff_proj, keep infrastructure categories, buffer them to
    produce contour polygons, and return both the contour GeoDataFrame and the
    raw buffered lines (needed by method C for the separation mask).

    Parameters
    ----------
    LTM_gdf       : GeoDataFrame — full LTM dataset
    BND_buff_proj : GeoDataFrame — clipping boundary in LTM crs
    target_crs    : CRS object   — reproject infra result into this crs
    args          : argparse.Namespace

    Returns
    -------
    infra_buff_merged : GeoDataFrame — LineString contours tagged 'infras'
    infra_lines       : GeoDataFrame — raw clipped infra lines (for sep mask)
    """
    with p_timer("Extracting the infrastructures", verbose=verbose):
        LTM_gdf_cut = clip(LTM_gdf, BND_buff_proj)
        infra_lines = LTM_gdf_cut[
            LTM_gdf_cut["CATSLC"].notna()
            & ~LTM_gdf_cut["CATSLC"].isin(REMOVED_CATSLC)
        ]

    with p_timer(
        f"Create a buffer around infrastructures"
        f" - buffer {args.infra_buff} / simplify {args.simplify_tol}",
        verbose=verbose
    ):
        infra_lines_buff = infra_lines.buffer(args.infra_buff)
        infra_buff_merged = (
            GeoDataFrame(geometry=[infra_lines_buff.union_all()], crs=LTM_gdf.crs)
            .explode()
            .exterior
            .polygonize()
            .reset_index(drop=True)
            .to_crs(target_crs)
        )
        
        
        infra_buff_merged_clean = _smooth_and_simplify(infra_buff_merged, 
                                                       args, 
                                                       add_physical=False, 
                                                       verbose=verbose)
        
        infra_buff_merged_clean = GeoDataFrame(
            geometry=infra_buff_merged_clean.boundary,
            crs=target_crs
        )

        infra_buff_merged_clean['physical'] = 'infras'

    return infra_buff_merged_clean, infra_lines


# =============================================================================
# PROCESSING PIPES
# =============================================================================

def pipe_methode_c(EXTER_gdf, LTM_gdf, args, verbose=True) -> GeoDataFrame:
    """
    Method C — corrected: smoothed coast + islands + buffered infrastructure
    contours. Infrastructure polygons are carved out of coast/island lines.
    """
    # --- shared steps --------------------------------------------------------
    BND, BND_buff, BND_buff_proj = _format_exter(
        EXTER_gdf, LTM_gdf, args, need_proj=True, verbose=verbose
    )
    merged_gdf        = _build_coast_island_polygons(EXTER_gdf, LTM_gdf, BND, args, verbose)
    merged_gdf        = _remove_tombolo(merged_gdf, args, verbose)
    smoothed          = _smooth_and_simplify(merged_gdf, args, True, verbose)
    clean_polys       = _remove_small_islands(smoothed, args, verbose)
    clean_inner_lines = _polygons_to_lines(clean_polys, BND_buff, verbose)
    infra_buff_merged, infra_lines = _extract_and_buffer_infra(
        LTM_gdf, BND_buff_proj, clean_inner_lines.crs, args, verbose
    )

    # --- unique to C: carve infra separation mask out of coast/island lines --
    with p_timer(
        f"Separate infrastructures from shore and islands"
        f" - buffer sep {args.infra_sep_buff}",
        verbose=verbose
    ):
        infra_lines_buff_sep = infra_lines.buffer(args.infra_sep_buff)
        infra_buff_sep_merged = (
            GeoDataFrame(geometry=[infra_lines_buff_sep.union_all()], crs=infra_lines_buff_sep.crs)
            .explode()
            .exterior
            .polygonize()
            .reset_index(drop=True)
        )
        infra_buff_sep_merged = (
            GeoDataFrame(geometry=infra_buff_sep_merged, crs=infra_lines_buff_sep.crs)
            .to_crs(clean_inner_lines.crs)
        )

        mask = infra_buff_sep_merged.union_all()
        cut_lines = clean_inner_lines.copy()
        cut_lines.geometry = clean_inner_lines.geometry.difference(mask)
        clean_inner_lines_cut = (
            cut_lines[~cut_lines.geometry.is_empty]
            .explode()
            .reset_index(drop=True)
        )

        # Drop coast fragments shorter than island_dist
        clean_inner_lines_cut['perimeter'] = clean_inner_lines_cut.geometry.length
        clean_inner_lines_cut = (
            clean_inner_lines_cut[clean_inner_lines_cut.perimeter > args.island_dist]
            .drop(columns="perimeter")
            .reset_index(drop=True)
        )

    # --- merge infra + cut lines ---------------------------------------------
    with p_timer("Merge the buffed infra, coast and island LineStrings", verbose=verbose):
        result = GeoDataFrame(
            concat([infra_buff_merged, clean_inner_lines_cut], ignore_index=True),
            crs=infra_buff_merged.crs
        )

    return result


def pipe_methode_d(EXTER_gdf, LTM_gdf, args, verbose=True) -> GeoDataFrame:
    """
    Method D — direct: smoothed coast + islands + explicit exterior boundary
    segments (tagged oceani). Spurious loops are removed after assembly.
    """
    # --- shared steps --------------------------------------------------------
    BND, BND_buff     = _format_exter(EXTER_gdf, LTM_gdf, args, need_proj=False, verbose=verbose)
    merged_gdf        = _build_coast_island_polygons(EXTER_gdf, LTM_gdf, BND, args, verbose)
    merged_gdf        = _remove_tombolo(merged_gdf, args, verbose)
    smoothed          = _smooth_and_simplify(merged_gdf, args, True, verbose)
    clean_polys       = _remove_small_islands(smoothed, args, verbose)
    clean_inner_lines = _polygons_to_lines(clean_polys, BND_buff, verbose)

    # --- unique to D: build outer boundary lines and tag them ----------------
    with p_timer("Building outer boundary lines", verbose=verbose):
        outer_lines = GeoDataFrame(geometry=BND_buff.boundary, crs=BND_buff.crs)

        clean_outer_lines = outer_lines.copy()
        clean_outer_lines['geometry'] = clean_outer_lines.geometry.apply(
            lambda line: linemerge(line.difference(clean_polys.union_all()))
        )
        clean_outer_lines = (
            clean_outer_lines[~clean_outer_lines.is_empty]
            .explode()
            .reset_index(drop=True)
        )
        clean_outer_lines["physical"] = [
            f"ocean{i}" for i in clean_outer_lines.index.values
        ]

        not_so_clean_lines = GeoDataFrame(
            concat([clean_outer_lines, clean_inner_lines], ignore_index=True),
            crs=clean_outer_lines.crs
        )

    # --- unique to D: remove spurious loops ----------------------------------
    with p_timer("Removing spurious loops", verbose=verbose):
        coast_other_mask = not_so_clean_lines["physical"].str.fullmatch(r"coast|ocean\d+")
        coast_other_gdf  = not_so_clean_lines[coast_other_mask]
        island_gdf       = not_so_clean_lines[~coast_other_mask]

        polygons, dangles, cut_edges, _ = polygonize_full(coast_other_gdf.geometry)

        all_polys = list(polygons.geoms)
        if not all_polys:
            raise ValueError("No closed loop found in coast/other lines.")

        main_polygon = max(all_polys, key=lambda p: p.area)

        kept_coast_other = coast_other_gdf[coast_other_gdf.covered_by(main_polygon.boundary)]
        kept_islands     = island_gdf[island_gdf.within(main_polygon)]

        result = GeoDataFrame(
            concat([kept_coast_other, kept_islands], ignore_index=True),
            crs=clean_inner_lines.crs,
        )

        # Re-index oceani tags consecutively
        other_mask = result["physical"].str.fullmatch(r"ocean\d+")
        old_tags   = result.loc[other_mask, "physical"].unique()
        remap = {old: f"other_{i}" for i, old in enumerate(old_tags)}
        result.loc[other_mask, "physical"] = result.loc[other_mask, "physical"].map(remap)

    return result


def pipe_methode_e(EXTER_gdf, LTM_gdf, args, verbose=True) -> GeoDataFrame:
    """
    Method E — extended: smoothed coast + islands only, clipped to BND_buff.
    No infrastructure, no outer boundary segments.
    """
    # --- shared steps (nothing unique after _polygons_to_lines) --------------
    BND, BND_buff = _format_exter(EXTER_gdf, LTM_gdf, args, need_proj=False, verbose=verbose)
    merged_gdf    = _build_coast_island_polygons(EXTER_gdf, LTM_gdf, BND, args, verbose)
    merged_gdf    = _remove_tombolo(merged_gdf, args, verbose)
    smoothed      = _smooth_and_simplify(merged_gdf, args, True, verbose)
    clean_polys   = _remove_small_islands(smoothed, args, verbose)
    return _polygons_to_lines(clean_polys, BND_buff, verbose)


def pipe_methode_o(EXTER_gdf, LTM_gdf, args, verbose=True) -> GeoDataFrame:
    """
    Method O — only_infra: buffered infrastructure contours only.
    No coast or island geometry is processed.
    """
    BND, BND_buff, BND_buff_proj = _format_exter(
        EXTER_gdf, LTM_gdf, args, need_proj=True, verbose=verbose
    )
    infra_buff_merged, _ = _extract_and_buffer_infra(
        LTM_gdf, BND_buff_proj, BND.crs, args, verbose
    )
    return infra_buff_merged


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    # =========================================================================
    # Parsing arguments
    # =========================================================================
    args = _resolve_args(parse_args())

    _check_file(args.shp_file, "EXTER boundary shapefile")
    _check_file(args.ltm_file,   "LTM shoreline shapefile")
    _check_output_dir(args.save_in.parent)

    _print_nice_args(args)

    # =========================================================================
    # Loading the original shapefiles
    # =========================================================================
    with p_timer("Reading the shapefiles", verbose=args.verbose):
        LTM_gdf   = read_file(args.ltm_file)
        EXTER_gdf = read_file(args.shp_file)

    # =========================================================================
    # Select the processing pipe
    # =========================================================================
    if args.method in ['corrected', 'C']:
        result = pipe_methode_c(EXTER_gdf, LTM_gdf, args, verbose=args.verbose)
    elif args.method in ['direct', 'D']:
        result = pipe_methode_d(EXTER_gdf, LTM_gdf, args, verbose=args.verbose)
    elif args.method in ['extended', 'E']:
        result = pipe_methode_e(EXTER_gdf, LTM_gdf, args, verbose=args.verbose)
    elif args.method in ['only_infra', 'O']:
        result = pipe_methode_o(EXTER_gdf, LTM_gdf, args, verbose=args.verbose)
    else:
        sys.exit(1)

    # =========================================================================
    # Save the result as a .shp file
    # =========================================================================
    with p_timer(f"Saving file as: {args.save_in}", verbose=args.verbose):
        result.to_file(args.save_in)

    # =========================================================================
    # Plot the results
    # =========================================================================
    if not args.no_plot:
        _plot_gdf(result, 'physical')


if __name__ == "__main__":
    main()


