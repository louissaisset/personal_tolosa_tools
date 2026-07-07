#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare gauge SSH data between two folders, each of which may contain
either .csv gauge files or .nc REFMAR files.

The type of each folder ('csv' or 'nc') is auto-detected from its
contents. Depending on the combination, files are matched as follows:

- csv folder vs csv folder : matched by exact identical filename (stem).
- nc folder  vs nc folder  : matched by exact identical 'station_name'.
- csv folder vs nc folder  : matched by CSV filename vs netCDF
  'station_name', after stripping digits/underscores and case-folding
  (e.g. 'LeConquet.csv' <-> station_name 'LE_CONQUET', 'Audierne2.csv'
  <-> 'AUDIERNE'), since csv/nc naming conventions differ.

One figure is produced per matched pair. x-axis is always julian_cnes
days (CNES epoch, 1950-01-01); for csv files this comes straight from
the 'julian_cnes' column, for nc files the datetime64 'time' coordinate
is converted to fractional julian_cnes days.

Note on ptt.p_convert_gregorian_date_to_julian_day: that helper parses a
'%Y-%m-%d' string and returns an *integer* number of days, so it cannot
be used directly on the netCDF's sub-daily timestamps without losing all
time-of-day resolution (every sample within a day would collapse to the
same value). nc_time_to_julian_cnes() below uses the exact same CNES
epoch (1950-01-01) but keeps the fractional day - it is the natural
vectorised generalisation of that function to sub-daily timestamps.
"""

import sys
import os
import re
import argparse
from pathlib import Path
from datetime import datetime

import numpy as np
import xarray as xr

import personal_tolosa_tools as ptt

CNES_EPOCH = datetime(1950, 1, 1)


def parse_bound(value: str) -> float | None:
    """Convert a single bound string to float or None."""
    if value.lower() == 'none':
        return None
    try:
        return float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid limit value '{value}': must be a number or 'None'"
        )


class TupleAction(argparse.Action):
    """Stores nargs values as a tuple instead of argparse's default list."""
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, tuple(values))


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Plot a comparison figure for every matched pair of "
        "files between two folders. Each folder may contain .csv gauge "
        "files or .nc REFMAR files (auto-detected); matching rule adapts "
        "to whether the two folders are the same type or not (see module "
        "docstring).",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        'dir1',
        type=str,
        help='First folder to compare (.csv or .nc files)'
    )

    parser.add_argument(
        'dir2',
        type=str,
        help='Second folder to compare (.csv or .nc files)'
    )

    parser.add_argument(
        '--workdir', '-w',
        type=str,
        default=None,
        help='Output directory for the figures (default: current directory)'
    )

    parser.add_argument(
        '--method', '-m',
        type=str,
        choices=['direct', 'bias', "diff"],
        default="direct",
        help='Comparison method. Can be direct or bias (default: direct)'
    )

    parser.add_argument(
        '-y',
        type=str,
        default='ssh',
        help="Data column/variable to compare (must exist in both sides, default 'ssh')"
    )

    parser.add_argument(
        '--xlim',
        nargs=2,
        type=parse_bound,
        action=TupleAction,
        metavar=('MIN', 'MAX'),
        default=None,
        help="X-axis (julian_cnes) limits, e.g. '--xlim None 10'"
    )

    parser.add_argument(
        '--ylim',
        nargs=2,
        type=parse_bound,
        action=TupleAction,
        metavar=('MIN', 'MAX'),
        default=None,
        help="Y-axis limits, e.g. '--ylim None 10'"
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Activate verbosity'
    )

    return parser


def normalize_name(name: str) -> str:
    """
    Fold a station/file name down to bare lowercase letters, so that
    'LeConquet', 'LE_CONQUET', 'Audierne2' and 'AUDIERNE' can be compared
    regardless of case, underscores, or trailing digits. Only used for
    the csv-vs-nc (mixed) matching case.
    """
    return re.sub(r'[^a-z]', '', name.lower())


def safe_filename(name: str) -> str:
    """Sanitize a matching key into something safe to use as a filename."""
    return re.sub(r'[^A-Za-z0-9_-]', '_', name)


def differing_part(*paths) -> list[Path]:
    parts = [p.expanduser().parts for p in paths]

    # Common prefix
    start = 0
    while all(start < len(p) for p in parts):
        x = parts[0][start]
        if all(p[start] == x for p in parts):
            start += 1
        else:
            break

    # Common suffix
    end = 0
    while all(end < len(p) - start for p in parts):
        x = parts[0][-1-end]
        if all(p[-1-end] == x for p in parts):
            end += 1
        else:
            break

    return [Path(*p[start:len(p)-end]) for p in parts]


def nc_time_to_julian_cnes(time_values) -> np.ndarray:
    """
    Convert a netCDF datetime64 time coordinate to fractional julian_cnes
    days (CNES epoch 1950-01-01). See module docstring for why this isn't
    routed through ptt.p_convert_gregorian_date_to_julian_day directly.
    """
    delta = time_values - np.datetime64(CNES_EPOCH)
    return delta / np.timedelta64(1, 'D')


def detect_folder_type(folder: Path) -> str:
    """
    Inspect a folder's contents and decide whether it holds .csv gauge
    files or .nc REFMAR files. Returns 'csv' or 'nc', or exits with an
    error if the folder is ambiguous (both types present) or contains
    neither.
    """
    n_csv = len(list(folder.glob('*.csv')))
    n_nc = len(list(folder.glob('*.nc')))

    if n_csv and n_nc:
        ptt.p_error(
            f"Folder {folder} contains both .csv ({n_csv}) and .nc ({n_nc}) "
            "files - cannot tell which role it plays, please split them."
        )
        sys.exit(1)
    if n_csv:
        return 'csv'
    if n_nc:
        return 'nc'

    ptt.p_error(f"Folder {folder} contains neither .csv nor .nc files.")
    sys.exit(1)


def get_nc_station_name(nc_file: Path) -> str:
    """Return the (raw, un-normalized) station_name of a netCDF file."""
    ds = xr.load_dataset(nc_file)
    if 'station_name' in ds.variables:
        name = str(ds['station_name'].values)
    else:
        name = nc_file.stem
    ds.close()
    return name


def build_exact_index(folder: Path, filetype: str, verbose: bool) -> dict:
    """
    Build a dict {key: file path} for a single folder, using an EXACT
    key: the file stem for csv, the raw station_name for nc.
    """
    index = {}
    if filetype == 'csv':
        for f in sorted(folder.glob('*.csv')):
            index[f.stem] = f
    else:
        for f in sorted(folder.glob('*.nc')):
            name = get_nc_station_name(f)
            index[name] = f
            ptt.p_ok(f"NetCDF '{f.name}' -> station '{name}'", verbose)

    if not index:
        ptt.p_error(f"No .{filetype} files found in {folder}")
        sys.exit(1)
    return index


def build_normalized_index(folder: Path, filetype: str, verbose: bool) -> dict:
    """
    Build a dict {normalized_key: file path} for a single folder, used
    only for the mixed csv-vs-nc matching case.
    """
    index = {}
    if filetype == 'csv':
        for f in sorted(folder.glob('*.csv')):
            index[normalize_name(f.stem)] = f
    else:
        for f in sorted(folder.glob('*.nc')):
            name = get_nc_station_name(f)
            key = normalize_name(name)
            index[key] = f
            ptt.p_ok(f"NetCDF '{f.name}' -> station '{name}' (key='{key}')", verbose)

    if not index:
        ptt.p_error(f"No .{filetype} files found in {folder}")
        sys.exit(1)
    return index


def match_pairs_same_type(index1: dict, index2: dict) -> list[tuple[str, Path, Path]]:
    """Exact key match between two folders of the same file type."""
    common_keys = sorted(set(index1) & set(index2))
    return [(key, index1[key], index2[key]) for key in common_keys]


def match_pairs_mixed(index_csv: dict, index_nc: dict) -> list[tuple[str, Path, Path]]:
    """
    Normalized-key match between a csv-folder index and an nc-folder
    index, with a containment fallback for keys that don't match exactly
    (e.g. an extra prefix/suffix on either side).
    """
    pairs = []
    used_nc_keys = set()
    for csv_key, csv_file in index_csv.items():
        nc_key = None
        if csv_key in index_nc:
            nc_key = csv_key
        else:
            for candidate in index_nc:
                if candidate in used_nc_keys:
                    continue
                if csv_key in candidate or candidate in csv_key:
                    nc_key = candidate
                    break
        if nc_key is not None:
            pairs.append((csv_key, csv_file, index_nc[nc_key]))
            used_nc_keys.add(nc_key)
    return pairs


def read_series(file: Path, filetype: str, y_key: str, file_rdr):
    """
    Read (x, y) = (julian_cnes, y_key) from a csv or nc file.
    Returns (x, y, None) on success, or (None, None, missing_keys) if the
    required column/variable is absent.
    """
    if filetype == 'csv':
        data = file_rdr.read_file(str(file.parent), file.name)
        missing = [k for k in ('julian_cnes', y_key) if k not in data.keys()]
        if missing:
            return None, None, missing
        return data['julian_cnes'], data[y_key], None
    else:
        ds = xr.load_dataset(file)
        if y_key not in ds.variables:
            ds.close()
            return None, None, [y_key]
        x = nc_time_to_julian_cnes(ds['time'].values)
        y = ds[y_key].values
        ds.close()
        return x, y, None


def main():

    print("\nBeginning script for comparing gauge data between two folders...")

    parser = create_parser()
    args = parser.parse_args()

    ptt.p_ok(f"Verbosity: {args.verbose}", args.verbose)

    dir1 = Path(args.dir1).absolute()
    dir2 = Path(args.dir2).absolute()

    for folder in (dir1, dir2):
        if not folder.is_dir():
            ptt.p_error(f"Not a directory: {folder}")
            sys.exit(1)

    type1 = detect_folder_type(dir1)
    type2 = detect_folder_type(dir2)
    ptt.p_ok(f"Detected {dir1} as the '{type1}' folder", args.verbose)
    ptt.p_ok(f"Detected {dir2} as the '{type2}' folder", args.verbose)

    workdir = Path(args.workdir).absolute() if args.workdir else Path.cwd()
    output_dir = str((workdir / f'Figures_{dir1.name}_vs_{dir2.name}').resolve())
    ptt.p_ok(f"Defined Figure folder : {output_dir}", args.verbose)

    if type1 == type2:
        # Same-type comparison: exact-match by filename (csv) or
        # station_name (nc).
        index1 = build_exact_index(dir1, type1, args.verbose)
        index2 = build_exact_index(dir2, type2, args.verbose)
        pairs = match_pairs_same_type(index1, index2)
        filetype1 = filetype2 = type1
    else:
        # Mixed comparison: fuzzy-match csv filename vs nc station_name.
        index_csv = build_normalized_index(dir1 if type1 == 'csv' else dir2, 'csv', args.verbose)
        index_nc = build_normalized_index(dir1 if type1 == 'nc' else dir2, 'nc', args.verbose)
        pairs = match_pairs_mixed(index_csv, index_nc)
        # Preserve (dir1, dir2) ordering for reading/labelling below.
        if type1 == 'csv':
            filetype1, filetype2 = 'csv', 'nc'
            pairs = [(key, csv_f, nc_f) for key, csv_f, nc_f in pairs]
        else:
            filetype1, filetype2 = 'nc', 'csv'
            pairs = [(key, nc_f, csv_f) for key, nc_f, csv_f in pairs]

    if not pairs:
        ptt.p_error("No matching pairs found between the two folders.")
        sys.exit(1)

    ptt.p_ok(f"Found {len(pairs)} matched pair(s): {[key for key, *_ in pairs]}", args.verbose)

    file_rdr = ptt.FileReader()

    n_done = 0
    for key, file1, file2 in pairs:
        ptt.p_ok(f"Matched '{key}': {file1.name} <-> {file2.name}", args.verbose)

        x1, y1, missing1 = read_series(file1, filetype1, args.y, file_rdr)
        if missing1:
            ptt.p_error(f"Skipping '{key}': {file1.name} missing {missing1}")
            continue

        x2, y2, missing2 = read_series(file2, filetype2, args.y, file_rdr)
        if missing2:
            ptt.p_error(f"Skipping '{key}': {file2.name} missing {missing2}")
            continue
        
        if args.method == "direct":
            # --- plot direct comparison ---
            plotter = ptt.Plotter(output_dir)
            plotter.figure_format = 'pdf'
            plotter.figure_tickfontsize = 5
            plotter.figure_size = (6, 6)
            plotter.figure_axes_aspect = 'auto'
            plotter.figure_xlabel = 'julian_cnes'
            plotter.figure_ylabel = args.y

            if args.xlim:
                plotter.figure_xlim = args.xlim
            if args.ylim:
                plotter.figure_ylim = args.ylim

            plotter.pcolor_key = ''
            plotter.contour_key = ''
            plotter.quiver_u_key = ''
            plotter.quiver_v_key = ''
            plotter.figure_filename = f"{safe_filename(key)}_{args.method}"

            plotter.line_plots = [
                ([x1, y1], {'label': f"{dir1.name}/{file1.stem}"}),
                ([x2, y2], {'label': f"{dir2.name}/{file2.stem}"}),
            ]

            fig, ax = plotter._setup_figure()
            plotter._draw_collections_and_lines(ax)
            ax.legend(fontsize=plotter.figure_tickfontsize)
            plotter._postprocess(fig, ax)

            n_done += 1

        else :
            # interpolation over the same timeline
            new_xmin = max(x1.min(), x2.min())
            new_xmax = min(x1.max(), x2.max())
            freq = max((new_xmax - new_xmin)/(10*24*60), 1/(24*60))
            new_x = np.arange(new_xmin, new_xmax, freq)
            ptt.p_ok(f"Different x axis interpolate over frequency: {freq}", args.verbose)
            
            # Update the x and y
            y1 = np.interp(new_x, x1, y1)
            y2 = np.interp(new_x, x2, y2)
            x1 = new_x 
            x2 = new_x

            # --- plot direct comparison ---
            plotter = ptt.Plotter(output_dir)
            plotter.figure_format = 'pdf'
            plotter.figure_tickfontsize = 5
            plotter.figure_size = (6, 6)
            plotter.figure_axes_aspect = 'auto'

            if args.method == "bias":
                labels = differing_part(dir1, dir2)
                plotter.figure_xlabel = labels[0]
                plotter.figure_ylabel = labels[1]
            elif args.method == "diff":
                plotter.figure_xlabel = 'julian_cnes'
                plotter.figure_ylabel = args.y

            if args.xlim:
                plotter.figure_xlim = args.xlim
            if args.ylim:
                plotter.figure_ylim = args.ylim

            plotter.pcolor_key = ''
            plotter.contour_key = ''
            plotter.quiver_u_key = ''
            plotter.quiver_v_key = ''
            plotter.figure_filename = f"{safe_filename(key)}_{args.method}"

            if args.method == "bias":
                plotter.line_plots = [
                    ([y1, y2], {'linestyle': 'none', 
                                'label': args.y,
                                'marker': '.'}),
                ]
            elif args.method == "diff":
                plotter.line_plots = [
                    ([new_x, y1-y2], {'label': f"{file1.stem}"}),
                ]
            
            fig, ax = plotter._setup_figure()
            plotter._draw_collections_and_lines(ax)
            ax.legend(fontsize=plotter.figure_tickfontsize)
            plotter._postprocess(fig, ax)

            n_done += 1





    ptt.p_ok(f"Done. {n_done}/{len(pairs)} figures produced in {output_dir}", args.verbose)


if __name__ == "__main__":
    main()
