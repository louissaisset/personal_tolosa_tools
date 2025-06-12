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
    print("\nBeginning script for plotting the ith timestep in the VTK results folder...")
    
    # Initialize parameters
    current_path = Path.cwd()
    ptt.p_ok(f"Launched from : {current_path}")
    
    output_dir = str((current_path / f'Figures_{current_path.name}').resolve())
    ptt.p_ok(f"Defined Figure folder : {output_dir}")
    
    # Initialize with default values
    folder = "res/bin"
    folder = (current_path / Path(folder)).resolve()
    
    # New version using Roman's method
    supported_filenames = sorted(list(ptt.Reader.search(folder)))
    ptt.p_ok(f"Supported filenames for reader: {supported_filenames}")
    
    # Define all available files to be read
    txt_info_files = sorted(list(ptt.InfoTxtReader.search(folder)))
    bin_data_files = sorted(list(ptt.DataBinReader.search(folder)))
    bin_mesh_files = sorted(list(ptt.MeshBinReader.search(folder)))
    vtk_data_files = sorted(list(ptt.DataVTKReader.search(folder)))
    
    timestep_eval = range(100)
    
    to_be_processed = ptt.files_for_timesteps(timestep_eval, 
                                              folder,
                                              txt_info_files, 
                                              bin_data_files, 
                                              bin_mesh_files, 
                                              vtk_data_files)
    
    # Configure the data plots
    plotter = ptt.Plotter(output_dir)
    plotter.figsize = (3,3)
    plotter.figure_tickfontsize = 5
    plotter.pcolor_max = 3
    plotter.pcolor_min = -plotter.pcolor_max
    plotter.contour_key = ''
    # plotter.contour_fontsize = 4
    # plotter.contour_levels = 5
    # plotter.quiver_lengthkey = 1 
    plotter.quiver_lengthkey = 1/5
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
    
    # Creating the local cluster
    if os.uname()[1].startswith('belenos'):
        # cluster = SLURMRunner()
        cluster = LocalCluster(n_workers=128, threads_per_worker=1)
    else:
        cluster = LocalCluster(n_workers=8, threads_per_worker=1)
    
    # Link the cluster to the client
    client = Client(cluster)
    
    delayed_processing = []
    for step in to_be_processed:
        delayed_processing += [ptt.plot_data_plotter(plotter, *step)]
    
    dask.compute(*delayed_processing)
    
if __name__ == '__main__':
    main()
    
    