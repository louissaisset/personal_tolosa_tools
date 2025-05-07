#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 21 13:56:34 2025

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
    
import numpy as np

import time
import dask
from dask.distributed import LocalCluster, Client


@dask.delayed
def plot_quad_data_plotter(plotter, X, Y, data_key, cell_data):
    data = {data_key: cell_data}
    plotter.plot_quad_data(X, Y, data)
    ptt.p_ok("Figure created and saved")

@dask.delayed
def interp_data(reader, t, X, Y, data_key):
    
    vtk_data = reader.read_file(t) 
    processor = ptt.VTKDataProcessor(vtk_data)
    interpolated_value = processor.compute_interpolation_masked_grid(processor.cell_centers_array[:,0], 
                                                                     processor.cell_centers_array[:,1],
                                                                     processor.cell_data[data_key],
                                                                     X, Y, method='nearest')
    ptt.p_ok("Interpolation done")
    return(interpolated_value)

def main():
    print("\nBeginning script for comparing the results of 2 simulations on a same regular grid...")
    
    # Initialize parameters
    current_path = Path.cwd()
    ptt.p_ok(f"Launched from : {current_path}")
    
    # Initialize with default values
    folder1 = current_path
    folder2 = current_path
    data_key = 'bathy'
    timestep = ''
    xreso = 10
    yreso = 10
    BCtype = 'some_description'
    
    # Read args and kwargs
    parser = argparse.ArgumentParser(description='Some script plotting the differences in the results of the ith timestep for two folders, unsig an interpolation of the results over a common regular grid.')
    parser.add_argument('args', nargs='*', help='Positional arguments: folder1, folder2, data_key, timestep, maxval, xreso, yreso, BCtype')
    parser.add_argument('--folder1', dest='folder1', default=None, help='Folder parameter as kwarg')
    parser.add_argument('--folder2', dest='folder2', default=None, help='Folder parameter as kwarg')
    parser.add_argument('--data_key', dest='data_key', default=None, help='Type of data to compare as kwarg')
    parser.add_argument('--timestep', dest='timestep', default=None, help='Timestep parameter as kwarg')
    parser.add_argument('--xreso', dest='xreso', default=None, help='X resolution of the comparison grid as kwarg')
    parser.add_argument('--yreso', dest='yreso', default=None, help='Y resolution of the comparison grid as kwarg')
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
        xreso = args.args[4]
    if len(args.args) >= 6:
        yreso = args.args[5]
    if len(args.args) >= 7:
        BCtype = args.args[6]
    
    # Override with kwargs if provided
    if args.folder1 is not None:
        folder1 = args.folder1
    if args.folder2 is not None:
        folder2 = args.folder2
    if args.data_key is not None:
        data_key = args.data_key
    if args.timestep is not None:
        timestep = args.timestep
    if args.xreso is not None:
        xreso = args.xreso
    if args.yreso is not None:
        yreso = args.yreso
    if args.BCtype is not None:
        BCtype = args.BCtype
    
    # Update folders to global path
    folder1 = (current_path / Path(folder1)).resolve()
    folder2 = (current_path / Path(folder2)).resolve()
    
    # Print all info and check the format validity
    ptt.p_ok(f"Asking for files from folder 1: {folder1}")
    ptt.p_ok(f"Asking for files from folder 2: {folder2}")
    ptt.p_ok(f"Asking for data: {data_key}")
    ptt.p_ok(f"Asking for timestep: {timestep}")
    try:
        timestep_eval = eval(timestep)
    except:
        ptt.p_error("Unrecognised timestep format for eval.")
        sys.exit(1)
    ptt.p_ok(f"Asking for x resolution: {xreso}")
    try:
        xreso_eval = eval(xreso)
    except:
        ptt.p_error("Unrecognised xreso format for eval.")
        sys.exit(1)
    ptt.p_ok(f"Asking for y resolution: {yreso}")
    try:
        yreso_eval = eval(yreso)
    except:
        ptt.p_error("Unrecognised yreso format for eval.")
        sys.exit(1)
    
    # Create 'Figures' folder for the outputs
    output_dir = (current_path / f'Figures_{current_path.name}_interp').resolve()
    ptt.p_ok(f"Defined Figure folder : {output_dir}")

    



    print("\nInitializing the data Readers...")
    
    # Initialize classes
    reader1 = ptt.VTKDataReader(str(folder1))
    reader2 = ptt.VTKDataReader(str(folder2))
    
    
    
    
    
    print("\nInitializing the data Plotters...")
    
    # Configure the data plots
    plotter = ptt.VTKPlotter(output_dir)
    # plotter.figure_save = False
    plotter.figure_tickfontsize = 5
    plotter.pcolor_key = data_key
    plotter.pcolor_max = 0.0001
    plotter.pcolor_min = -plotter.pcolor_max
    plotter.pcolor_cmap = 'RdBu'
    plotter.contour_key = ''
    plotter.quiver_u_key = ''
    plotter.quiver_v_key = ''
    plotter.rectangle_positions = [(-29000, -12500, -15000, 0), 
                                   (-10000, -3000, -4000, 1000), 
                                   (-7000, -2000, 4500, 8500), 
                                   (-17000, -12000, -10000, -5000), 
                                   (-1000, 4000, -2000, 2000)]
    plotter.rectangle_colors = 'k'
    new_figsize_list = [(5,5),
                        (5,5),
                        (4,4),
                        (4,4),
                        (4,4)]
    new_filename_list = ['zoom_ouest',
                         'zoom_ilelongue',
                         'zoom_port',
                         'zoom_pointepenhir',
                         'zoom_bassinest']
    
    
    
    
    
    print("\nInitializing the new grids...")
    
    X_list, Y_list = [], []
    for xmin, xmax, ymin, ymax in plotter.rectangle_positions:
        x = np.arange(xmin, xmax + xreso_eval, xreso_eval)
        y = np.arange(ymin, ymax + yreso_eval, yreso_eval)
        X, Y = np.meshgrid(x, y)
        X_list += [X]
        Y_list += [Y]
    
    
    
    
    print("\nInitializing the dask local cluster...")
    # Creating the local cluster and client 
    cluster = LocalCluster(n_workers=8, threads_per_worker=1)
    client = Client(cluster)
    ptt.p_ok(f"See client dashboard via dask at: {client.dashboard_link}")
    cluster.scale(8)
    
    
    print("\nInterpolating the data over the new grids...")
 
    delayed_interpolation = []
    if timestep_eval.__class__ == int:
        
        # Iterate over the zoom zones and delay the corresponding figure plotting
        for X, Y in zip(X_list, Y_list):
            delayed_interpolation += [interp_data(reader1, timestep_eval, 
                                                  X, Y, data_key)]
            delayed_interpolation += [interp_data(reader2, timestep_eval, 
                                                  X, Y, data_key)]
            
    else:
        try:
            for t in timestep_eval:
                # Iterate over the zoom zones and delay the corresponding figure plotting
                for X, Y in zip(X_list, Y_list):
                    delayed_interpolation += [interp_data(deepcopy(reader1), t, 
                                                          X, Y, data_key)]
                    delayed_interpolation += [interp_data(deepcopy(reader2), t, 
                                                          X, Y, data_key)]
        except:
            ptt.p_error("Unrecognised timestep format. Should be either int or iterable")
            sys.exit(1)
    
    # Ask for the computing of such interpolations
    grid_data_list = dask.compute(*delayed_interpolation)
    



    
    print("\nPlotting the data comparison...")
    # Create the delayed task list
    delayed_plot = []
    N1 = folder1.parents[-current_path.parents.__len__()-2].name
    N2 = folder2.parents[-current_path.parents.__len__()-2].name
    old_filename = f'Comparison_{BCtype}_{data_key}_{N1}_MOINS_{N2}'
    if timestep_eval.__class__ == int:
        # Iterate over the zoom zones and delay the corresponding figure plotting
        for i in range(len(plotter.zoomed_plotters)):
            newplotter = deepcopy(plotter.zoomed_plotters[i])
            new_filename = new_filename_list[i]
            new_figsize = new_figsize_list[i]
            new_X = X_list[i]
            new_Y = Y_list[i]
            new_grid_data_1 = grid_data_list[i*2]
            new_grid_data_2 = grid_data_list[i*2 + 1]
            grid_data_comparison = new_grid_data_1 - new_grid_data_2
            
            newplotter.figure_filename = '_'.join([old_filename, f'{new_filename}', f"{timestep_eval:05d}"])
            newplotter.figure_size = new_figsize
            delayed_plot += [plot_quad_data_plotter(deepcopy(newplotter), 
                                                    new_X, new_Y, 
                                                    data_key,
                                                    grid_data_comparison)]
    else:
        try:
            for t in timestep_eval:
                # Iterate over the zoom zones and delay the corresponding figure plotting
                for i in range(len(plotter.zoomed_plotters)):
                    newplotter = deepcopy(plotter.zoomed_plotters[i])
                    new_filename = new_filename_list[i]
                    new_figsize = new_figsize_list[i]
                    new_X = X_list[i]
                    new_Y = Y_list[i]
                    new_grid_data_1 = grid_data_list[i*2]
                    new_grid_data_2 = grid_data_list[i*2 + 1]
                    grid_data_comparison = new_grid_data_1 - new_grid_data_2
                    
                    print(newplotter.figure_filename)
                    
                    newplotter.figure_filename = '_'.join([old_filename, f'{new_filename}', f"{t:05d}"])
                    print(newplotter.figure_filename)
                    newplotter.figure_size = new_figsize
                    delayed_plot += [plot_quad_data_plotter(deepcopy(newplotter), 
                                                            new_X, new_Y, 
                                                            data_key,
                                                            grid_data_comparison)]
        except:
            ptt.p_error("Unrecognised timestep format. Should be either int or iterable")
            sys.exit(1)
    
    # Ask for the computing and saving of such figures
    dask.compute(*delayed_plot)
    
    ptt.p_ok('Fin des affichages !')
    
    client.close()
    time.sleep(1)
    cluster.close()

if __name__ == "__main__":
    exit(main())