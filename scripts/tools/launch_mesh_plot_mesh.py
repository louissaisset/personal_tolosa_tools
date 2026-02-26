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

from matplotlib.collections import LineCollection


from pathlib import Path
import argparse


def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="A small python script to generate matplotlib figures of \
    a mesh using the informations of either a given file or the first '.msh' \
    file found inside the current path",
        formatter_class=argparse.RawDescriptionHelpFormatter
        )
    
    parser.add_argument(
        '--mesh_file', 
        type=str,
        default=None,
        help='Mesh File (default: first .msh file in current folder)'
    )
    
    parser.add_argument(
        '--workdir', '-w',
        type=str,
        default=None,
        help='Working directory (default: current directory)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Activate verbosity'
    )
    
    parser.add_argument(
        '--triangle', '-t',
        action='store_true',
        help='Activate triangular cell plotting'
    )
    
    parser.add_argument(
        '--node', '-n',
        action='store_true',
        help='Activate node z plotting'
    )
    
    parser.add_argument(
        '--line', '-l',
        action='store_true',
        help='Activate line plotting'
    )
    
    parser.add_argument(
        '--vertex', '-p',
        action='store_true',
        help='Activate vertex plotting'
    )
    
    return parser


def checkfile(file):
    if file.exists():
        ptt.p_ok(f"Working with file : {file}")
    else :
        ptt.p_error(f"No such file: {file}")
        return(0)

def main():

    print("\nBeginning script for plotting the grid info from the diag.vtk file...")
    
    # Read args and kwargs
    parser = create_parser()
    args = parser.parse_args()

    verbose = args.verbose
    if verbose:
        ptt.p_ok(f"Verbosity: {verbose}")

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
    if verbose:
        ptt.p_ok(f"Defined Figure folder : {output_dir}")

    # current_path = str(current_path)
    
    
    # Select file
    if not args.mesh_file:
        mesh_files = sorted(list(ptt.MshReader.search(current_path)))
        if not mesh_files:
            ptt.p_error("No .msh files found.")
            sys.exit(1)
        mesh_file = current_path / Path(mesh_files[0])
        if verbose:
            ptt.p_ok(f"Using mesh file: {mesh_file}")
    else:
        mesh_file = Path(args.mesh_file)

        # Case 2: mesh_file is not absolute → make it relative to workdir
        if not mesh_file.is_absolute():
            mesh_file = current_path / mesh_file
        
        checkfile(mesh_file)
        if verbose:
            ptt.p_ok(f"Using mesh file: {mesh_file}")
    
    if verbose:
        ptt.p_ok("Beginning the plotting...")
        
    # Instantiate the reader
    file_rdr = ptt.FileReader()
    mesh = file_rdr.read_file(os.path.dirname(mesh_file), 
                              os.path.basename(mesh_file))
    
    # Processdata
    processor = ptt.MeshDataProcessor(mesh)
    
    # Configure the data plots
    plotter = ptt.Plotter(output_dir)
    plotter.figure_format = 'pdf'
    plotter.figure_tickfontsize = 5
    plotter.figure_size = (6,6)
    
    plotter.pcolor_key = ''
    plotter.contour_key = ''
    plotter.quiver_u_key = ''
    plotter.quiver_v_key = ''
    
    plotter.figure_filename = os.path.basename(mesh_file)
    
    plotter.triplot = args.triangle
        
    if args.node:
        if 'z' in processor.point_data.keys():
            plotter.scatter_from_points = True
            plotter.scatter_c_key = 'z'
            plotter.scatter_s = .5
            
    if args.line:
        if 'line' in processor.data.cells_dict.keys():
            l_index = processor.data.cells_dict['line']
            lines = processor.data.points[l_index][:, :, :2]
            with mpl.rc_context({'lines.marker': '>'}):
                plotter.collections = [
                    LineCollection(
                        lines, 
                        linewidths=.5, 
                        colors='red', 
                        linestyle='-',
                        joinstyle='round',   # 'miter', 'round', or 'bevel'
                        capstyle='round')]
    
    if args.vertex:
        if 'vertex' in processor.data.cells_dict.keys():
            v_index = processor.data.cells_dict['vertex'].squeeze()
            vertexes = processor.data.points[v_index][:,:2]
            plotter.line_plots = [([vertexes[:,0], 
                                    vertexes[:,1]], 
                                   {'ms':.5, 
                                    'marker':'.', 
                                    'linestyle':'None', 
                                    'color': 'orange'})]
    if verbose:
        ptt.p_ok("Defined the plotter arguments:")
        print(plotter.__dict__)
    
    plotter.Plot(processor)
    
    
if __name__ == "__main__":
    # exit(main())
    main()
