#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Plot hydrodynamic recap for a given timestep in a VTK results folder.
"""

import sys
import os
import argparse
from pathlib import Path
from copy import deepcopy

import dask
from dask.distributed import LocalCluster, Client
import matplotlib as mpl
mpl.use('agg')
import matplotlib.pyplot as plt

if os.uname()[1].startswith('belenos'):
    path_tolosa_path = "~/SAVE/DATA/Scripts/personal_tolosa_tools/"
else:
    path_tolosa_path = "~/DATA/Scripts/personal_tolosa_tools/"
os.environ['PATH'] += os.pathsep + os.path.expanduser(f'{path_tolosa_path}/scripts/tools/')
sys.path.append(os.path.expanduser(path_tolosa_path))
import personal_tolosa_tools as ptt


# -- Plotter defaults ----------------------------------------------------------
FIGSIZE        = (3, 3)
XLIM           = (None, None)
YLIM           = (None, None)
ZOOM_ZONES     = [# (xmin, xmax, ymin, ymax),  
                #   (-3500, -2500, -5500,  -3500),  
                #   (-10000, -3000, -4000,  1000),  
                #   ( -7000, -2000,  4500,  8500), 
                #   (-17000,-12000,-10000, -5000), 
                #   ( -1000,  4000, -2000,  2000), 
                  (0, 60_000, -25_000, 25_000), 
                  ]
TICK_FONTSIZE  = 5
PCOLOR_MAX     = 3          # overridable via --pcolormax
PCOLOR_KEY     = 'ssh'
CONTOUR_KEY    = ''
CONTOUR_LW     = 0.2
QUIVER_SCALE   = 25         # overridable via --quiverscale
QUIVER_SPACING = 10        # density factor for quiver arrows


# -- Dask worker count per host ------------------------------------------------
DASK_WORKERS = {
    'belenos':           128,
    'vmtl-submar-prod':  15,
}
DEFAULT_WORKERS = 8


def parse_args():
    parser = argparse.ArgumentParser(
        description='Plot a hydrodynamic recap for the i-th timestep.'
    )
    parser.add_argument('args', nargs='*',
                        help='Positional: folder, timestep')
    parser.add_argument('-f', '--folder',    default=None,
                        help='Results folder (relative or absolute path)')
    parser.add_argument('-t', '--timestep',  default='0',
                        help='Timestep: int or iterable as an eval()-able string')
    parser.add_argument('--pcolormax',  type=float, default=None,
                        help=f'Max value for centered colormap (default {PCOLOR_MAX})')
    parser.add_argument('--quiverscale', type=float, default=None,
                        help=f'Quiver arrow scaling factor (default {QUIVER_SCALE})')
    parser.add_argument("--verbose", "-v", action="store_true", default=None,
                        help="Print additional information.")
    return parser.parse_args()


def resolve_params(args, current_path):
    """Merge positional args, keyword args, and defaults into a single dict."""
    positional = args.args

    folder     = positional[0] if len(positional) >= 1 else current_path
    timestep   = positional[1] if len(positional) >= 2 else '0'
    pcolormax  = float(positional[2]) if len(positional) >= 3 else PCOLOR_MAX
    quiverscale = float(positional[3]) if len(positional) >= 4 else QUIVER_SCALE
    verbose = False

    if args.folder      is not None: folder      = args.folder
    if args.timestep    is not None: timestep    = args.timestep
    if args.pcolormax   is not None: pcolormax   = args.pcolormax
    if args.quiverscale is not None: quiverscale = args.quiverscale
    if args.verbose     is not None: verbose = args.verbose

    return {
        'folder':      (current_path / Path(folder)).resolve(),
        'timestep':    timestep,
        'pcolormax':   pcolormax,
        'quiverscale': quiverscale,
        'verbose':     verbose,
    }


def build_plotter(output_dir, pcolormax, quiverscale):
    plotter = ptt.Plotter(output_dir)
    plotter.figsize              = FIGSIZE
    plotter.figure_tickfontsize  = TICK_FONTSIZE
    plotter.pcolor_key           = PCOLOR_KEY
    plotter.pcolor_max           =  pcolormax
    plotter.pcolor_min           = -pcolormax
    plotter.contour_key          = CONTOUR_KEY
    plotter.contour_linewidths   = CONTOUR_LW
    plotter.figure_xlim          = XLIM
    plotter.figure_ylim          = YLIM
    plotter.quiver_scale         = quiverscale
    plotter.quiver_lengthkey     = 1 / quiverscale
    plotter.quiver_spacing       = QUIVER_SPACING
    plotter.rectangle_positions  = ZOOM_ZONES
    # plotter.triplot = True
    return plotter


def make_dask_client(verbose=True):
    hostname = os.uname()[1]
    n_workers = next(
        (v for k, v in DASK_WORKERS.items() if hostname.startswith(k)),
        DEFAULT_WORKERS,
    )
    cluster = LocalCluster(n_workers=n_workers, threads_per_worker=1)
    client  = Client(cluster)
    assert client.submit(lambda x: x + 1, 10).result() == 11
    assert client.submit(lambda x: x + 1, 20, workers=2).result() == 21
    ptt.p_ok(f"Dask dashboard: {client.dashboard_link}", verbose)
    return client


def main():
    print("\nPlotting hydrodynamic recap for requested timestep(s)...")

    current_path = Path.cwd()
    
    params = resolve_params(parse_args(), current_path)
    folder      = params['folder']
    timestep    = params['timestep']
    pcolormax   = params['pcolormax']
    quiverscale = params['quiverscale']
    verbose     = params['verbose']

    ptt.p_ok(f"Launched from: {current_path}", verbose)
    ptt.p_ok(f"Folder   : {folder}", verbose)
    ptt.p_ok(f"Timestep : {timestep}", verbose)

    try:
        timestep_eval = eval(timestep)
    except Exception:
        ptt.p_error("Unrecognised timestep format for eval().", verbose)
        sys.exit(1)

    # -- Output folder & plotter -----------------------------------------------
    output_dir = (current_path / f'Figures_{current_path.name}').resolve()
    ptt.p_ok(f"Output folder: {output_dir}", verbose)

    plotter      = build_plotter(output_dir, pcolormax, quiverscale)
    base_filename = plotter.auto_filename()

    # -- Dask cluster ----------------------------------------------------------
    client = make_dask_client(verbose)

    # -- Build delayed plot tasks ----------------------------------------------
    to_be_processed = ptt.files_for_timesteps(timestep_eval, folder, verbose)

    steps = (
        [(timestep_eval, to_be_processed[0])]
        if isinstance(timestep_eval, int)
        else zip(timestep_eval, to_be_processed)
    )

    delayed_plots = []
    for t, step in steps:
        # FOR THE ORIGINAL DOMAIN
        plotter.figure_title    = f"Timestep = {t:05d}"
        plotter.figure_filename = f"{base_filename}_complet_{t:05d}"
        delayed_plots.append(ptt.plot_data_plotter(deepcopy(plotter), *step))

        # FOR ZOOMED SUBDOMAINS
        if len(ZOOM_ZONES):
            zipped_zooms = zip(plotter.zoomed_plotters, [f"zoom_{i}" for i in range(len(ZOOM_ZONES))])
            for zoomed, suffix in zipped_zooms:
                zoomed.figure_filename  = f"{base_filename}_{suffix}_{t:05d}"
                delayed_plots.append(ptt.plot_data_plotter(deepcopy(zoomed), *step))

    print("\nComputing and saving figures...")
    dask.compute(*delayed_plots)

    client.shutdown()


if __name__ == "__main__":
    exit(main())