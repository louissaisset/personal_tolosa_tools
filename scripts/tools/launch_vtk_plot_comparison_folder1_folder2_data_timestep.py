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

def main():
    print("\nBeginning script for comparing the results of two folders...")
    
    # Initialize parameters
    current_path = Path.cwd()
    ptt.p_ok(f"Launched from : {current_path}")
    
    # Initialize with default values
    timestep = ''
    folder1 = current_path
    folder2 = current_path
    data_key = 'ssh'
    timestep = 0
    maxval = 0.001
    BCtype = 'some_description'
    
    # Read args and kwargs
    parser = argparse.ArgumentParser(description='Some script plotting the differences in the ith timestep for two folders sharing the same mesh.')
    parser.add_argument('args', nargs='*', help='Positional arguments: folder1, folder2, data_key, timestep, maxval, BCtype')
    parser.add_argument('--folder1', dest='folder1', default=None, help='First folder parameter as kwarg')
    parser.add_argument('--folder2', dest='folder2', default=None, help='Second folder parameter as kwarg')
    parser.add_argument('--data_key', dest='data_key', default=None, help='Type of data to compare as kwarg')
    parser.add_argument('--timestep', dest='timestep', default=None, help='Timestep parameter as kwarg')
    parser.add_argument('--maxval', dest='maxval', default=None, help='Centered colorbar max value')
    parser.add_argument('--BCtype', dest='BCtype', default=None, help='Some description of the BC that are compared (for the figure names)')
    
    args = parser.parse_args()
    
    # Process positional args if provided
    if len(args.args) >= 1:
        folder1 = args.args[0]
    if len(args.args) >= 2:
        folder2 = args.args[1]
    if len(args.args) >= 3:
        data_key = args.args[2]
    if len(args.args) >= 4:
        timestep = args.args[3]
    if len(args.args) >= 5:
        maxval = args.args[4]
    if len(args.args) >= 6:
        maxval = args.args[5]
    
    # Override with kwargs if provided
    if args.folder1 is not None:
        folder1 = args.folder1
    if args.folder2 is not None:
        folder2 = args.folder2
    if args.data_key is not None:
        data_key = args.data_key
    if args.timestep is not None:
        timestep = args.timestep
    if args.maxval is not None:
        maxval = args.maxval
    if args.BCtype is not None:
        BCtype = args.BCtype
    
    folder1 = (current_path / Path(folder1)).resolve()
    folder2 = (current_path / Path(folder2)).resolve()
    
    ptt.p_ok(f"Comparing files from first folder: {folder1}")
    ptt.p_ok(f"Comparing files to second folder: {folder2}")
    ptt.p_ok(f"Comparing hydrodynamics for: {data_key}")
    ptt.p_ok(f"Asking for timestep: {timestep}")
    ptt.p_ok(f"Asking for maxval: {maxval}")
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
    plotter.pcolor_cmap = 'RdBu'
    plotter.pcolor_max = 0.1
    plotter.pcolor_min = -plotter.pcolor_max
    plotter.pcolor_key = data_key
    plotter.contour_key = ''
    plotter.quiver_u_key = ''
    plotter.quiver_v_key = ''
    plotter.rectangle_positions = [(-10000, -3000, -4000, 1000), 
                                   (-7000, -2000, 4500, 8500), 
                                   (-17000, -12000, -10000, -5000), 
                                   (-1000, 4000, -2000, 2000)]
    plotter.rectangle_colors = 'k'
    new_figsize_list = [(4,4),
                        (3.5,3.5),
                        (3,3),
                        (3.5,3.5)]
    new_filename_list = ['zoom_ilelongue',
                         'zoom_port',
                         'zoom_pointepenhir',
                         'zoom_bassinest']
    
    # Keep the original file name in memory
    N1 = folder1.parents[-current_path.parents.__len__()-2].name
    N2 = folder2.parents[-current_path.parents.__len__()-2].name
    old_filename = f'Comparison_{BCtype}_{data_key}_{N1}_MOINS_{N2}'
    
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
    to_be_processed_1 = ptt.files_for_timesteps(timestep_eval, str(folder1))
    to_be_processed_2 = ptt.files_for_timesteps(timestep_eval, str(folder2))
    
    # Create the delayed task list
    if timestep_eval.__class__ == int:
        triplet = zip([timestep_eval], to_be_processed_1, to_be_processed_2)
    else:
        triplet = zip(timestep_eval, to_be_processed_1, to_be_processed_2)
    
    
    
    print("\nProcessing and plotting the data...")
    delayed_plot = []
    for t, step_1, step_2 in triplet:
        if step_1[0] != step_2[0]:
            continue
        else:
            process_type = step_1[0]
            step_1 = step_1[1:]
            step_2 = step_2[1:]
        
        # Create the delayed complete figure
        plotter.figure_title = f"Timestep = {t:05d}"
        plotter.figure_filename = '_'.join([old_filename, 'complet', f"{t:05d}"])
        delayed_plot += [ptt.plot_tri_data_comparison(deepcopy(plotter), 
                                                      process_type, 
                                                      step_1, step_2)]
        
        # Iterate over the zoom zones and delay the corresponding figure plotting
        for newplotter, new_filename, new_figsize in zip(plotter.zoomed_plotters, new_filename_list, new_figsize_list):
            newplotter.figure_filename = '_'.join([old_filename, f'{new_filename}', f"{t:05d}"])
            newplotter.figure_size = new_figsize
            delayed_plot += [ptt.plot_tri_data_comparison(deepcopy(newplotter), 
                                                          process_type, 
                                                          step_1, step_2)]
            
    # Ask for the computing and saving of such figures
    dask.compute(*delayed_plot)
    
    client.shutdown()
    
if __name__ == "__main__":
    exit(main())
