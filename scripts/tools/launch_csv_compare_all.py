#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: llsaisset
"""

import argparse
import os
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

import personal_tolosa_tools as ptt

# --------------------------------------------------------------------
# 1) Flatten (ReaderClass, filepath) entries out of readable(s)
# --------------------------------------------------------------------
def _iter_entries(readable_or_list):
    """
    Recursively flatten nested lists of readables down to individual
    (ReaderClass, filepath) tuples, as returned by reader.readable().
    """
    if isinstance(readable_or_list, list):
        for item in readable_or_list:
            yield from _iter_entries(item)
    elif isinstance(readable_or_list, tuple) and len(readable_or_list) == 2:
        yield readable_or_list
    else:
        raise TypeError(
            f"Unexpected item while flattening readables: {readable_or_list!r} "
            "(expected a (ReaderClass, filepath) tuple, or a list of those)."
        )


def _basename_no_ext(filepath):
    return os.path.splitext(os.path.basename(filepath))[0]


# --------------------------------------------------------------------
# 2) Name normalization / matching -- tune this to your naming rules
# --------------------------------------------------------------------
def normalize_name(name, strip_digits=True):
    """
    Upper-case, drop separators (space/underscore/hyphen), optionally
    drop digits. e.g. "Audierne2" -> "AUDIERNE",
    "ssh_refmar_BREST_2023-08-01_2024-03-01_NM" -> "SSHREFMARBRESTNM".
    """
    name = re.sub(r"[\s_\-]", "", name.upper())
    if strip_digits:
        name = re.sub(r"\d", "", name)
    return name


def names_match(name_a, name_b, min_len=4):
    """
    Default rule: exact match on normalized names, or one contained
    in the other (substring), guarded by a minimum length so very
    short names don't match everything.
    """
    if not name_a or not name_b:
        return False
    if name_a == name_b:
        return True
    shorter, longer = sorted((name_a, name_b), key=len)
    if len(shorter) < min_len:
        return False
    return shorter in longer


# --------------------------------------------------------------------
# 3) The grouping function
# --------------------------------------------------------------------
def group_files_by_name(
    primary_sources,
    secondary_sources=(),
    matcher=names_match,
    normalizer=normalize_name,
    aliases=None,
):
    """
    Parameters
    ----------
    primary_sources : readable(s)
        Defines the group keys (e.g. `readable_bin_list`, the gauge
        csv files). Nested lists are flattened automatically, so you
        can pass the whole `readable_bin_list` (list of per-folder
        lists of (ReaderClass, filepath) tuples) directly.
    secondary_sources : readable(s)
        Other formats to attach to a matching primary group (e.g.
        `[readable_hfs, readable_nc]`).
    matcher : callable(norm_a, norm_b) -> bool
        Matching rule between two normalized names.
    normalizer : callable(str) -> str
        Normalization applied to basenames before matching.
    aliases : dict[str, list[str]] or None
        Optional manual overrides for names that won't match
        automatically, e.g. {"Brest": ["BREST_TG"]}. Values are
        extra raw (non-normalized) name hints checked in addition to
        the primary key's own basename.

    Returns
    -------
    dict[str, list[tuple[type, str]]]
        primary basename -> list of (ReaderClass, filepath) entries
        (primary entries first, then any matched secondary entries).
    """
    aliases = aliases or {}
    primary_entries = list(_iter_entries(primary_sources))
    secondary_entries = list(_iter_entries(list(secondary_sources)))

    groups = defaultdict(list)
    normalized_keys = defaultdict(set)

    # seed groups from the primary source(s)
    for entry in primary_entries:
        _, path = entry
        base = _basename_no_ext(path)
        groups[base].append(entry)
        normalized_keys[base].add(normalizer(base))
        for alias in aliases.get(base, []):
            normalized_keys[base].add(normalizer(alias))

    # attach secondary entries wherever a name matches
    for entry in secondary_entries:
        _, path = entry
        norm_base = normalizer(_basename_no_ext(path))
        for key, norm_variants in normalized_keys.items():
            if any(matcher(v, norm_base) for v in norm_variants):
                groups[key].append(entry)

    return dict(groups)


def paths_only(groups):
    """Convenience: convert {name: [(cls, path), ...]} -> {name: [path, ...]}."""
    return {name: [path for _, path in entries] for name, entries in groups.items()}


# CNES julian day epoch. Used to convert the gauge .csv `julian_cnes`
# column into an actual calendar datetime axis.
CNES_EPOCH = pd.Timestamp("1950-01-01")


# --------------------------------------------------------------------
# 4) Data-source label, derived from the folder structure
# --------------------------------------------------------------------
def source_label(reader_class, filepath):
    """
    A short label naming *where the data comes from*, used in the plot
    legend (the group name itself now goes into the figure title, not
    the labels):
      - CsvReader (gauge)  -> the simulation folder name, e.g.
                               ".../SW_ML1_10m_TIDE_DR/res/gauge/x.csv"
                               -> "SW_ML1_10m_TIDE_DR"
      - HFSReader           -> the folder the .hfs lives in, e.g. "MAS"
      - NcReader             -> the folder two levels up, e.g. "REFMAR"
                               (".../REFMAR/output/x.nc")
    Falls back to the reader class name if the path is too shallow.
    """
    name = reader_class.__name__
    path = Path(filepath)
    parents = path.parents

    try:
        if name == "CsvReader":
            return parents[2].name
        if name == "HFSReader":
            return parents[0].name
        if name == "NcReader":
            return parents[1].name
    except IndexError:
        pass

    return name


# --------------------------------------------------------------------
# 5) Per-format extraction of (x, y) from a read file
# --------------------------------------------------------------------
def extract_time_series(reader_class, filepath, data, y_key="ssh"):
    """
    Given the reader class, the file path it came from, and the object
    returned by reader.read_file(), return (x, y) ready to be plotted.
    """
    name = reader_class.__name__

    # --- NcReader: xarray.Dataset ------------------------------------
    if hasattr(data, "coords") and hasattr(data, "attrs"):
        if y_key not in data:
            raise ValueError(f"'{y_key}' not found in {name} dataset ({filepath})")
        x = data["time"].values
        y = data[y_key].values
        return x, y

    # --- pandas DataFrame: CsvReader (gauge) or HFSReader ------------
    if "julian_cnes" in data.columns:
        x = CNES_EPOCH + pd.to_timedelta(data["julian_cnes"], unit="D")
    elif "time" in data.columns:
        x = data["time"]
    else:
        raise ValueError(
            f"No time-like column found for {name} in {filepath}: {list(data.columns)}"
        )

    if y_key not in data.columns:
        raise ValueError(
            f"'{y_key}' column not found for {name} in {filepath}: {list(data.columns)}"
        )
    y = data[y_key]

    return x, y


# --------------------------------------------------------------------
# 6) Build one comparison plot for a single group
# --------------------------------------------------------------------
def plot_group_ssh(
    group_name,
    entries,
    output_dir="./",
    reader=None,
    y_key="ssh",
    xlim=None,
    ylim=None,
):
    """
    Parameters
    ----------
    group_name : str
        Used as the figure title and filename (e.g. "Brest").
    entries : list[tuple[type, str]]
        (ReaderClass, filepath) entries for this group, as returned by
        `group_files_by_name`.
    output_dir : str
        Passed to ptt.Plotter().
    reader : ptt.FileReader or None
        Reused if provided (avoids re-instantiating for every group).
    y_key : str
        Column / variable name to compare (default 'ssh').
    xlim, ylim : tuple[float | None, float | None] or None
        Forwarded to plotter.figure_xlim / figure_ylim if provided.

    Returns
    -------
    (fig, ax) or (None, None) if nothing could be plotted.
    """
    reader = reader or ptt.FileReader()

    # --- read every file first: we need to know whether a REFMAR (nc)
    #     dataset is available *before* building the hfs line, so its
    #     ZH-referenced ssh can be corrected to the NM reference used
    #     by the csv/nc data. ---------------------------------------
    read_entries = []  # list of (reader_class, filepath, data)
    for reader_class, filepath in entries:
        path = Path(filepath)
        try:
            data = reader.read_file(path.parent, path.name)
        except Exception as exc:  # noqa: BLE001 - keep the batch going
            ptt.p_warning(f"[{group_name}] failed to read {filepath}: {exc}")
            continue
        read_entries.append((reader_class, filepath, data))

    if not read_entries:
        ptt.p_warning(f"[{group_name}] no readable data found, skipping figure.")
        return None, None

    # ZH -> NM offset, taken from the REFMAR (.nc) dataset if present.
    zh_to_nm_offset = None
    if y_key == "ssh":
        for reader_class, filepath, data in read_entries:
            if reader_class.__name__ == "NcReader" and hasattr(data, "attrs"):
                offset = data.attrs.get("zr_to_nm_offset_m")
                if offset is not None:
                    zh_to_nm_offset = float(offset)
                    break

    # --- build the line plots -----------------------------------------
    line_plots = []
    for reader_class, filepath, data in read_entries:
        try:
            x, y = extract_time_series(reader_class, filepath, data, y_key=y_key)
        except Exception as exc:  # noqa: BLE001 - keep the batch going
            ptt.p_warning(f"[{group_name}] skipping {filepath}: {exc}")
            continue

        if reader_class.__name__ == "HFSReader" and y_key == "ssh":
            if zh_to_nm_offset is not None:
                y = y + zh_to_nm_offset
            else:
                ptt.p_warning(
                    f"[{group_name}] no REFMAR offset available for {filepath}; "
                    "hfs ssh left in ZH reference (not converted to NM)."
                )

        label = source_label(reader_class, filepath)
        line_plots.append(([x, y], {"label": label}))

    if not line_plots:
        ptt.p_warning(f"[{group_name}] no plottable data found, skipping figure.")
        return None, None

    plotter = ptt.Plotter(output_dir)
    plotter.figure_format = "pdf"
    plotter.figure_tickfontsize = 5
    plotter.figure_size = (6, 6)
    plotter.figure_axes_aspect = "auto"
    plotter.figure_xlabel = "time"
    plotter.figure_ylabel = y_key
    plotter.figure_title = group_name

    plotter.pcolor_key = ""
    plotter.contour_key = ""
    plotter.quiver_u_key = ""
    plotter.quiver_v_key = ""
    plotter.figure_filename = group_name

    plotter.line_plots = line_plots

    if xlim:
        plotter.figure_xlim = xlim
    if ylim:
        plotter.figure_ylim = ylim

    fig, ax = plotter._setup_figure()
    plotter._draw_collections_and_lines(ax)
    ax.legend(fontsize=plotter.figure_tickfontsize)
    plotter._postprocess(fig, ax)

    return fig, ax


# --------------------------------------------------------------------
# 7) Command-line interface
# --------------------------------------------------------------------
def parse_bound(value: str):
    """Convert a single bound string to float or None."""
    if value.lower() == "none":
        return None
    try:
        return pd.to_datetime(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Invalid limit value '{value}': must be a Timestamp or 'None'"
        )


class TupleAction(argparse.Action):
    """Stores nargs values as a tuple instead of argparse's default list."""

    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, tuple(values))


def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Plot ssh comparison figures for every matched group of "
        "gauge (.csv), hfs (.hfs) and REFMAR (.nc) files. Files are grouped "
        "by station name (see group_files_by_name / names_match).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "gauge_dirs",
        nargs="+",
        type=str,
        help="One or more gauge bin folders (.csv files), e.g. the DR and "
        "NR run folders. Defines the groups (one per unique station).",
    )

    parser.add_argument(
        "--MAS_dir",
        type=str,
        default=None,
        help="MAS folder containing .hfs files (optional).",
    )

    parser.add_argument(
        "--REFMAR_dir",
        type=str,
        default=None,
        help="REFMAR folder containing .nc files (optional).",
    )

    parser.add_argument(
        "--workdir",
        "-w",
        type=str,
        default=None,
        help="Output directory for the figures (default: current directory).",
    )

    parser.add_argument(
        "--method",
        "-m",
        type=str,
        choices=["direct", "bias", "diff"],
        default="direct",
        help="Comparison method (default: direct). NOTE: only 'direct' "
        "(plot every series overlaid) is currently implemented; 'bias' "
        "and 'diff' are reserved for a future extension.",
    )

    parser.add_argument(
        "-y",
        type=str,
        default="ssh",
        help="Data column/variable to compare (must exist in every "
        "source, default 'ssh').",
    )

    parser.add_argument(
        "--xlim",
        nargs=2,
        type=parse_bound,
        action=TupleAction,
        metavar=("MIN", "MAX"),
        default=None,
        help="X-axis limits, e.g. '--xlim None 10'",
    )

    parser.add_argument(
        "--ylim",
        nargs=2,
        type=parse_bound,
        action=TupleAction,
        metavar=("MIN", "MAX"),
        default=None,
        help="Y-axis limits, e.g. '--ylim None 10'",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Activate verbosity",
    )

    return parser


def main():

    print("\nBeginning script for comparing gauge/hfs/REFMAR ssh data...")

    parser = create_parser()
    args = parser.parse_args()

    ptt.p_ok(f"Verbosity: {args.verbose}", args.verbose)

    if args.method != "direct":
        ptt.p_warning(
            f"method='{args.method}' is not implemented yet; plotting all "
            "series overlaid ('direct') instead."
        )

    output_dir = args.workdir or "./"

    reader = ptt.FileReader()
    readable_bin_list = [reader.readable(d, verbose=args.verbose) for d in args.gauge_dirs]
    readable_hfs = reader.readable(args.MAS_dir, verbose=args.verbose) if args.MAS_dir else []
    readable_nc = reader.readable(args.REFMAR_dir, verbose=args.verbose) if args.REFMAR_dir else []

    groups = group_files_by_name(
        primary_sources=readable_bin_list,
        secondary_sources=[readable_hfs, readable_nc],
    )

    for name, entries in groups.items():
        if args.verbose:
            print(name)
            for reader_class, path in entries:
                print("   ", reader_class.__name__, path)
        plot_group_ssh(
            name,
            entries,
            output_dir=output_dir,
            reader=reader,
            y_key=args.y,
            xlim=args.xlim,
            ylim=args.ylim,
        )

    return 0


if __name__ == "__main__":
    exit(main())