#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 31 14:22:52 2025

@author: llsaisset
"""

import sys
import os
import argparse
from pathlib import Path

if os.uname()[1].startswith('belenos'):
    path_tolosa_path = "~/SAVE/DATA/Scripts/personal_tolosa_tools/"
else:
    path_tolosa_path = "~/DATA/Scripts/personal_tolosa_tools/"
os.environ['PATH'] += os.pathsep +  os.path.expanduser(f'{path_tolosa_path}/scripts/tools/')
sys.path.append(os.path.expanduser(path_tolosa_path))
import personal_tolosa_tools as ptt


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
        description="A small python script to generate matplotlib figures of \
    gauge data, using either a given file, or every '.csv' file found inside \
    the current path plotted together on one single figure",
        formatter_class=argparse.RawDescriptionHelpFormatter
        )

    parser.add_argument(
        '--file',
        type=str,
        default=None,
        help='CSV gauge extraction file (default: all .csv files in current folder, combined on one figure)'
    )

    parser.add_argument(
        '--workdir', '-w',
        type=str,
        default=None,
        help='Working directory (default: current directory)'
    )

    parser.add_argument(
        '-x',
        type=str,
        default='time',
        help='Data to use as abscissa (needs to match the tag in the csv)'
    )

    parser.add_argument(
        '-y',
        type=str,
        default='ssh',
        help='Data to use as ordinate (needs to match the tag in the csv)'
    )

    parser.add_argument(
        '--xlim',
        nargs=2,
        type=parse_bound,
        action=TupleAction,
        metavar=('MIN', 'MAX'),
        default=None,
        help="X-axis limits, e.g. '--xlim None 10' or '--xlim 5 5'"
    )

    parser.add_argument(
        '--ylim',
        nargs=2,
        type=parse_bound,
        action=TupleAction,
        metavar=('MIN', 'MAX'),
        default=None,
        help="Y-axis limits, e.g. '--ylim None 10' or '--ylim 5 5'"
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Activate verbosity'
    )

    return parser


def checkfile(file: Path) -> bool:
    """Return True if file exists, log and return False otherwise."""
    if file.exists():
        ptt.p_ok(f"Working with file : {file}")
        return True
    else:
        ptt.p_error(f"No such file: {file}")
        return False


def gather_files(args, current_path: Path) -> list[Path]:
    """
    Resolve the list of CSV file(s) to plot.

    - If --file is given: a single-element list with that file (the previous,
      single-file behaviour).
    - Otherwise: every .csv file found in current_path, sorted, so they can
      all be drawn on the same figure.
    """
    if args.file:
        file = Path(args.file)
        if not file.is_absolute():
            file = current_path / file
        if not checkfile(file):
            sys.exit(1)
        if file.is_dir:
            list_of_csv = list(file.glob('*.csv'))
            if len(list_of_csv):
                return list_of_csv
        elif file.is_file:
            return [file]

    found = sorted(list(ptt.CsvReader.search(current_path)))
    if not found:
        ptt.p_error("No .csv files found.")
        sys.exit(1)
    return [current_path / Path(f) for f in found]


def main():

    print("\nBeginning script for plotting gauge data from CSV file(s)...")

    # Read args and kwargs
    parser = create_parser()
    args = parser.parse_args()

    ptt.p_ok(f"Verbosity: {args.verbose}", args.verbose)

    # Set working directory, with current directory as default
    if args.workdir:
        current_path = Path(args.workdir).absolute()
        if not current_path.exists():
            ptt.p_err(f"Working directory does not exist: {current_path}")
            sys.exit(1)
        if not current_path.is_dir():
            ptt.p_err(f"Working directory is not a directory: {current_path}")
            sys.exit(1)
    else:
        current_path = Path.cwd()
    ptt.p_ok(f"Launched from : {current_path}")

    # Create a Figure_thing folder
    output_dir = str((current_path / f'Figures_{current_path.name}').resolve())
    ptt.p_ok(f"Defined Figure folder : {output_dir}", args.verbose)

    # Select file(s): either the one given with --file, or every .csv in current_path
    files = gather_files(args, current_path)
    ptt.p_ok(
        f"Found {len(files)} CSV file(s) to plot: {[f.name for f in files]}",
        args.verbose
    )

    ptt.p_ok("Beginning the plotting...", args.verbose)

    # Instantiate the reader
    file_rdr = ptt.FileReader()

    # Configure the data plots
    plotter = ptt.Plotter(output_dir)
    plotter.figure_format = 'pdf'
    plotter.figure_tickfontsize = 5
    plotter.figure_size = (6, 6)
    plotter.figure_axes_aspect = 'auto'

    plotter.figure_xlabel = args.x
    plotter.figure_ylabel = args.y

    if args.xlim:
        plotter.figure_xlim = args.xlim
    if args.ylim:
        plotter.figure_ylim = args.ylim

    plotter.pcolor_key = ''
    plotter.contour_key = ''
    plotter.quiver_u_key = ''
    plotter.quiver_v_key = ''

    plotter.figure_filename = (
        os.path.basename(files[0]) if len(files) == 1
        else f"{current_path.name}_combined_gauges"
    )

    # Build line_plots manually: one (x, y, kwargs) entry per file, all on
    # the same figure/axis. x is allowed to differ from file to file; we
    # only require that the requested y column exists in each file.
    #
    # No decorator is needed on _setup_figure / _postprocess: plot_xy
    # already calls them exactly once per figure, regardless of how many
    # entries are in self.line_plots. The only thing that changes between
    # "one file" and "all files" is how many (x, y, kwargs) entries we put
    # in that list before calling the same setup -> draw -> postprocess
    # sequence plot_xy itself uses internally.
    line_plots = []
    for file in files:
        csv_data = file_rdr.read_file(os.path.dirname(file), os.path.basename(file))

        if args.x not in csv_data.keys() or args.y not in csv_data.keys():
            missing = [k for k in (args.x, args.y) if k not in csv_data.keys()]
            ptt.p_error(f"Skipping {file.name}: missing column(s) {missing}")
            ptt.p_error(f"Available values are: {list(csv_data.keys())}")
            continue

        line_plots.append((
            [csv_data[args.x], csv_data[args.y]],
            {'label': file.stem}
        ))

    if not line_plots:
        ptt.p_error(
            f"None of the files contained both '{args.x}' and '{args.y}', nothing to plot."
        )
        sys.exit(1)

    plotter.line_plots = line_plots
    fig, ax = plotter._setup_figure()
    plotter._draw_collections_and_lines(ax)
    if len(line_plots) > 1:
        ax.legend(fontsize=plotter.figure_tickfontsize)
    plotter._postprocess(fig, ax)

    ptt.p_ok("Defined the plotter arguments:", args.verbose)
    ptt.p_ok(plotter.__dict__, args.verbose)


if __name__ == "__main__":
    # exit(main())
    main()