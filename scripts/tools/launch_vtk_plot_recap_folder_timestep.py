#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jan 31 14:22:52 2025

@author: llsaisset
"""

import sys, os
if os.uname()[1].startswith('belenos'):
    path_tolosa_path = "~/SAVE/DATA/Scripts/personal_tolosa_tools/"
else:
    path_tolosa_path = "~/DATA/Scripts/personal_tolosa_tools/"
os.environ['PATH'] += os.pathsep +  os.path.expanduser(f'{path_tolosa_path}/scripts/tools/')
sys.path.append(os.path.expanduser(path_tolosa_path))
import personal_tolosa_tools as ptt

from pathlib import Path
import argparse

from copy import deepcopy
import matplotlib as mpl
mpl.use('agg')

import matplotlib.pyplot as plt
# Paramètres d'affichage pour que ce soit toujours plus propre
plt.rcParams["font.size"] = 8
if not os.uname()[1].startswith('belenos'):
    plt.rcParams["font.family"] = "cmr10"
    plt.rcParams['text.usetex'] = True
    plt.rcParams['axes.formatter.use_mathtext'] = True
    plt.rcParams['mathtext.fontset'] = "custom"
    plt.rcParams['mathtext.rm'] = "cmr10"
    plt.rcParams['mathtext.it'] = "cmr10:italic"
    plt.rcParams['mathtext.bf'] = "cmr10:bold"

import dask
from dask.distributed import LocalCluster, Client
    
@dask.delayed
def plot_data_plotter(reader, plotter, t):

    vtk_data = reader.read_file(t) 
    processor = ptt.VTKDataProcessor(vtk_data)
    # ptt.p_ok("Defined the plotter arguments:")
    # print(plotter.__dict__)
    plotter.Plot(processor)
    ptt.p_ok("Figure created and saved")

def main():
    print("\nBeginning script for plotting the ith timestep in the VTK results folder...")
    
    # Initialize parameters
    current_path = Path.cwd()
    ptt.p_ok(f"Launched from : {current_path}")
    
    # Initialize with default values
    folder = current_path
    timestep = ''
    pcolormax = 3
    quiverscale = 25
    
    # Read args and kwargs
    parser = argparse.ArgumentParser(description='Small python script to plot an hydrodynamic recap of the i-th timestep')
    parser.add_argument('args', nargs='*', help='Positional arguments: folder, timestep')
    parser.add_argument('-f', '--folder', dest='folder', default=None, help='Folder parameter as kwarg. Should be an existing relative or global path declared as str')
    parser.add_argument('-t', '--timestep', dest='timestep', default=None, help='Timestep parameter as kwarg. Should be an int or any iterable declared as a string for eval(timestep)')
    parser.add_argument('--pcolormax', dest='pcolormax', type=float, default=None, help='Max value for centered colormap plot. Default to 3')
    parser.add_argument('--quiverscale', dest='quiverscale', type=float, default=None, help='Scaling coefficient for que quiver arrows. Default to 25')
    
    args = parser.parse_args()
    
    # Process positional args if provided
    if len(args.args) >= 1:
        folder = args.args[0]
    if len(args.args) >= 2:
        timestep = args.args[1]
    if len(args.args) >= 3:
        pcolormax = args.args[2]
    if len(args.args) >= 4:
        quiverscale = args.args[3]
    
    # Override with kwargs if provided
    if args.folder is not None:
        folder = args.folder
    if args.timestep is not None:
        timestep = args.timestep
    if args.pcolormax is not None:
        pcolormax = args.pcolormax
    if args.quiverscale is not None:
        quiverscale = args.quiverscale
    
    folder = (current_path / Path(folder)).resolve()
    
    ptt.p_ok(f"Asking for files from folder: {folder}")
    ptt.p_ok(f"Asking for timestep: {timestep}")
    try:
        timestep_eval = eval(timestep)
    except:
        ptt.p_error("Unrecognised timestep format for eval.")
        sys.exit(1)
    
    # Create 'Figures' folder 
    output_dir = (current_path / f'Figures_{current_path.name}').resolve()
    ptt.p_ok(f"Defined Figure folder : {output_dir}")

    
    print("\nInitializing the data Plotter")
    # Configure the data plots
    plotter = ptt.Plotter(output_dir)
    plotter.figsize = (3,3)
    plotter.figure_tickfontsize = 5
    plotter.pcolor_max = pcolormax
    plotter.pcolor_min = -plotter.pcolor_max
    plotter.contour_key = ''
    # plotter.contour_fontsize = 4
    # plotter.contour_levels = 5
    # plotter.quiver_lengthkey = 1 
    plotter.quiver_lengthkey = 1/quiverscale
    plotter.contour_linewidths = 0.2
#    plotter.rectangle_positions = [(-10000, -3000, -4000, 1000), 
#                                   (-7000, -2000, 4500, 8500), 
#                                   (-17000, -12000, -10000, -5000), 
#                                   (-1000, 4000, -2000, 2000)]
#    plotter.rectangle_colors = 'k'
#    new_figsize_list = [(4,4),
#                        (3.5,3.5),
#                        (3,3),
#                        (3.5,3.5)]
#    new_filename_list = ['zoom_ilelongue',
#                         'zoom_port',
#                         'zoom_pointepenhir',
#                         'zoom_bassinest']
    
    # Keep the original file name in memory
    old_filename = plotter.auto_filename()
    
    # Define some density factor of the quivers from the BC types
    # factor = (6-int(current_path.stem.split('_')[1])) # from 6 to 1
    factor = 1 # from 6 to 1
    
    # Creating the local cluster
    if os.uname()[1].startswith('belenos'):
        # cluster = SLURMRunner()
        cluster = LocalCluster(n_workers=128, threads_per_worker=1)
    else:
        cluster = LocalCluster(n_workers=8, threads_per_worker=1)
    
    # Link the cluster to the client
    client = Client(cluster)
    
    if not os.uname()[1].startswith('belenos'):
        cluster.scale(8)
    
    # Checking for the client to be correctly configured
    assert client.submit(lambda x : x+1, 10).result() == 11
    assert client.submit(lambda x : x+1, 20, workers=2).result() == 21
    ptt.p_ok(f"See client dashboard via dask at: {client.dashboard_link}")
    
    
    
    
    print("\nDefining the necessary reading processes...")
    to_be_processed = ptt.files_for_timesteps(timestep_eval, folder)
    
    # Create the delayed task list
    if timestep_eval.__class__ == int:
        pair = zip([timestep_eval], to_be_processed)
    else:
        pair = zip(timestep_eval, to_be_processed)
        
    print("\nProcessing and plotting the data...")
    delayed_plot = []
    for t, step in pair:
        # Create the delayed complete figure
        plotter.figure_title = f"Timestep = {t:05d}"
        plotter.figure_filename = '_'.join([old_filename, 'complet', f"{t:05d}"])
        plotter.quiver_spacing = int(170/factor)
        plotter.quiver_scale = quiverscale
        delayed_plot += [ptt.plot_data_plotter(deepcopy(plotter), *step)]
        
#        # Iterate over the zoom zones and delay the corresponding figure plotting
#        for newplotter, new_filename, new_figsize in zip(plotter.zoomed_plotters, new_filename_list, new_figsize_list):
#            newplotter.figure_filename = '_'.join([old_filename, f'{new_filename}', f"{t:05d}"])
#            newplotter.figure_size = new_figsize
#            newplotter.quiver_spacing = int(20/factor)
#            # newplotter.quiver_scale = 15
#            newplotter.quiver_scale = quiverscale
#            delayed_plot += [ptt.plot_data_plotter(deepcopy(newplotter), *step)]
    
    # Ask for the computing and saving of such figures
    dask.compute(*delayed_plot)
    
    client.shutdown()
    
if __name__ == "__main__":
    exit(main())
