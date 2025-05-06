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
plt.rcParams["font.family"] = "cmr10"
plt.rcParams["font.size"] = 8
if not os.uname()[1].startswith('belenos'):
    plt.rcParams['text.usetex'] = True
    plt.rcParams['axes.formatter.use_mathtext'] = True
    plt.rcParams['mathtext.fontset'] = "custom"
    plt.rcParams['mathtext.rm'] = "cmr10"
    plt.rcParams['mathtext.it'] = "cmr10:italic"
    plt.rcParams['mathtext.bf'] = "cmr10:bold"

import dask
from dask.distributed import Client
if os.uname()[1].startswith('belenos'):
    # from dask_mpi import initialize
    from dask_jobqueue.slurm import SLURMCluster, SLURMRunner
else:
    from dask.distributed import LocalCluster
    
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
    timestep = ''
    folder = current_path
    
    # Read args and kwargs
    parser = argparse.ArgumentParser(description='Process VTK folder and timestep parameters')
    parser.add_argument('args', nargs='*', help='Positional arguments: folder, timestep')
    parser.add_argument('--folder', dest='folder', default=None, help='Folder parameter as kwarg')
    parser.add_argument('--timestep', dest='timestep', default=None, help='Timestep parameter as kwarg')
    
    args = parser.parse_args()
    
    # Process positional args if provided
    if len(args.args) >= 1:
        folder = args.args[0]
    if len(args.args) >= 2:
        timestep = args.args[1]
    
    # Override with kwargs if provided
    if args.timestep is not None:
        timestep = args.timestep
    if args.folder is not None:
        folder = args.folder
    
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

    
    print("\nInitializing the data Reader and Plotter")
    
    # Initialize classes
    reader = ptt.VTKDataReader(str(folder))
    
    # Configure the data plots
    plotter = ptt.VTKPlotter(output_dir)
    plotter.figsize = (3,3)
    plotter.figure_tickfontsize = 5
    plotter.pcolor_max = 1
    plotter.pcolor_min = -plotter.pcolor_max
    plotter.contour_key = ''
    # plotter.contour_fontsize = 4
    # plotter.contour_levels = 5
    plotter.quiver_lengthkey = 1
    plotter.contour_linewidths = 0.2
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
    old_filename = plotter.auto_filename()
    
    # Creating the local cluster
    if os.uname()[1].startswith('belenos'):
        # initialize()
        # cluster = SLURMCluster(cores=1,
        #                        memory='2GB',
        #                        account='saissetl',
        #                        queue='normal256')
        cluster = SLURMRunner()
    else:
        cluster = LocalCluster(n_workers=8, threads_per_worker=1)
    
    # Link the cluster to the client
    client = Client(cluster)
    # client.wait_for_workers(1)
    
    # Checking for the client to be correctly configured
    assert client.submit(lambda x : x+1, 10).result() == 11
    assert client.submit(lambda x : x+1, 20, workers=2).result() == 21
    
    
    
    ptt.p_ok(f"See client dashboard via dask at: {client.dashboard_link}")
    
    
    
    if os.uname()[1].startswith('belenos'):
        cluster.scale(128)
    else:
        cluster.scale(8)
    
    
    
    # Create the delayed task list
    delayed_plot = []
    if timestep_eval.__class__ == int:
        # Create the delayed complete figure
        plotter.figure_title = f"Timestep = {timestep_eval:05d}"
        plotter.figure_filename = '_'.join([old_filename, 'complet', f"{timestep_eval:05d}"])
        plotter.quiver_spacing = 170
        plotter.quiver_scale = 30
        delayed_plot += [plot_data_plotter(deepcopy(reader), 
                                           deepcopy(plotter),
                                           timestep_eval)]
        
        # Iterate over the zoom zones and delay the corresponding figure plotting
        for newplotter, new_filename, new_figsize in zip(plotter.zoomed_plotters, new_filename_list, new_figsize_list):
            newplotter.figure_filename = '_'.join([old_filename, f'{new_filename}', f"{timestep_eval:05d}"])
            newplotter.figure_size = new_figsize
            newplotter.quiver_spacing = 20
            newplotter.quiver_scale = 15
            delayed_plot += [plot_data_plotter(deepcopy(reader), 
                                               deepcopy(newplotter),
                                               timestep_eval)]
    else:
        try:
            for t in timestep_eval:
                # Create the delayed complete figure
                plotter.figure_title = f"Timestep = {t:05d}"
                plotter.figure_filename = '_'.join([old_filename, 'complet', f"{t:05d}"])
                plotter.quiver_spacing = 170
                plotter.quiver_scale = 30
                delayed_plot += [plot_data_plotter(deepcopy(reader), 
                                                   deepcopy(plotter),
                                                   t)]
                # Iterate over the zoom zones and delay the corresponding figure plotting
                for newplotter, new_filename, new_figsize in zip(plotter.zoomed_plotters, new_filename_list, new_figsize_list):
                    newplotter.figure_filename = '_'.join([old_filename, f'{new_filename}', f"{t:05d}"])
                    newplotter.figure_size = new_figsize
                    newplotter.quiver_spacing = 20
                    newplotter.quiver_scale = 15
                    delayed_plot += [plot_data_plotter(deepcopy(reader), 
                                                       deepcopy(newplotter), 
                                                       t)]
        except:
            ptt.p_error("Unrecognised timestep format. Should be either int or iterable")
            sys.exit(1)
            
    # Ask for the computing and saving of such figures
    dask.compute(*delayed_plot)
    
    client.shutdown()
    
if __name__ == "__main__":
    exit(main())
