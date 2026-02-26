#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 09:59:19 2026

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

import argparse
from pathlib import Path
import numpy as np
import rasterio
from rasterio.env import Env
from rasterio.warp import calculate_default_transform, reproject, Resampling
from pyproj import CRS

def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description='Creates a new mesh file in WW3 format using a tolosa mesh and its original tif depth file',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    
    parser.add_argument(
        '--input_mesh', 
        type=str, 
        required=True,
        help='Path to the original Tolosa mesh'
    )
    
    parser.add_argument(
        '--input_tags', 
        nargs='+',
        type=int, 
        required=True,
        help='Path to the original Tolosa mesh'
    )
    
    parser.add_argument(
        '--input_tif',
        type=str, 
        required=True,
        help='Path to the depth TIF file'
    )
    
    parser.add_argument(
        '--workdir', '-w',
        type=str,
        default=None,
        help='Working directory (default: current directory)'
    )
    
    parser.add_argument(
        '--save_in', '-s',
        type=str,
        default='',
        help='Path to the resulting file (default: toto_ww3.msh)'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Activate verbosity'
    )
    
    return parser


def checkfile(file):
    if file.exists():
        ptt.p_ok(f"Working with file : {file}")
    else :
        ptt.p_error(f"No such file: {file}")
        return(0)

def read_tif(input_tif, input_mesh, mesh_crs):
    with Env(GDAL_NUM_THREADS="ALL_CPUS"):
        with rasterio.open(input_tif) as src:
            bathy = src.read(1)  # Read first band as 2D numpy array
            transform = src.transform  # Affine transform
            height, width = bathy.shape
            nodata = src.nodata
            raster_crs = CRS.from_wkt(src.crs.to_wkt())
    
            # -----------------------------------------------------------------
            # CRS CHECK
            # -----------------------------------------------------------------
    
            if raster_crs is None:
                ptt.p_warning("TIF has no CRS. Assigning mesh CRS.")
    
                new_tif_path = input_tif.parent / f"{input_tif.stem}_with_crs.tif"
    
                profile = src.profile
                profile.update(crs=mesh_crs)
    
                with rasterio.open(new_tif_path, "w", **profile) as dst:
                    dst.write(bathy, 1)
    
                ptt.p_ok(f"New TIF written with mesh CRS: {new_tif_path}")
    
                raster_crs = mesh_crs
    
            elif not raster_crs.equals(mesh_crs):
    
                ptt.p_warning("Raster CRS differs from mesh CRS.")
                ptt.p_warning("Reprojecting raster to mesh CRS...")
    
                transform_new, width_new, height_new = calculate_default_transform(
                    raster_crs,
                    mesh_crs,
                    width,
                    height,
                    *src.bounds
                )
    
                profile = src.profile.copy()
                profile.update({
                    "crs": mesh_crs,
                    "transform": transform_new,
                    "width": width_new,
                    "height": height_new
                })
    
                new_tif_path = input_mesh.parent / f"{input_tif.stem}_reprojected.tif"
    
                with rasterio.open(new_tif_path, "w", **profile) as dst:
                    reproject(
                        source=bathy,
                        destination=rasterio.band(dst, 1),
                        src_transform=transform,
                        src_crs=raster_crs,
                        dst_transform=transform_new,
                        dst_crs=mesh_crs,
                        resampling=Resampling.bilinear
                    )
    
                ptt.p_ok(f"Reprojected TIF written: {new_tif_path}")
    
                # Reopen reprojected file
                with rasterio.open(new_tif_path) as reproj_src:
                    bathy = reproj_src.read(1)
                    transform = reproj_src.transform
                    height, width = bathy.shape
    
                raster_crs = mesh_crs
    
            else:
                ptt.p_ok("Raster CRS matches mesh CRS.")
    # Create 1D coordinate arrays
    cols = np.arange(width, dtype='float32')
    rows = np.arange(height, dtype='float32')

    X = transform.c + cols * transform.a
    Y = transform.f + rows * transform.e

    # Expand to 2D grids
    X_bathy, Y_bathy = np.meshgrid(X, Y)
    bathy = np.where(bathy == nodata, np.nan, bathy)
    
    return X_bathy, Y_bathy, bathy
    
def main():
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
    
    bnd_tag_list = np.array(args.input_tags)
    if verbose:
        ptt.p_ok(f"Tags to use for WW3 vertex definition: {bnd_tag_list}")
    
        
    # Make input paths absolute paths : mesh file
    input_mesh = Path(args.input_mesh)
    if not input_mesh.is_absolute():
        input_mesh = current_path / input_mesh
    checkfile(input_mesh)
    if verbose:
        ptt.p_ok(f"Using input mesh : {input_mesh}")
    
    # Make input paths absolute paths : tif file
    input_tif = Path(args.input_tif)
    if not input_tif.is_absolute():
        input_tif = current_path / input_tif
    checkfile(input_tif)
    if verbose:
        ptt.p_ok(f"Using input tif : {input_tif}")
    
    
    file_rdr = ptt.FileReader()
    with ptt.p_timer(f'Reading the mesh file {os.path.join(input_mesh.parent, input_mesh.name)}', verbose=verbose):
        mesh = file_rdr.read_file(input_mesh.parent, input_mesh.name)
    
    with ptt.p_timer('Creating the processor for the initial mesh', verbose=verbose):
        processor = ptt.MeshDataProcessor(mesh)
        # print(processor.data.field_data)
        # sys.exit()
        
        mesh_wkt = processor.data.field_data.get("projection_wkt", None)

        if mesh_wkt is None:
            ptt.p_warning("Mesh does not contain CRS information.")
        
        mesh_crs = CRS.from_wkt(mesh_wkt)
        
    with ptt.p_timer(f'Reading the bathy in {input_tif}', verbose=verbose):
        X_bathy, Y_bathy, bathy = read_tif(input_tif, input_mesh, mesh_crs)
        
    with ptt.p_timer("Total time for creating the new mesh", verbose=verbose):
        new_processor = processor.convert_tolosa_mesh_to_ww3(bnd_tag_list,
                                                             X_bathy, 
                                                             Y_bathy, 
                                                             bathy,
                                                             verbose=verbose)
        
    with ptt.p_timer("Total time for saving new mesh", verbose=verbose):
        # Make input paths absolute paths : ouput file
        save_in_str = args.save_in
        if not save_in_str:
            new_mesh_filename = f"{'.'.join(input_mesh.name.split('.')[:-1])}_ww3.msh"
        else:
            new_mesh_filename = save_in_str
        save_in = Path(new_mesh_filename)
        if not save_in.is_absolute():
            save_in = current_path / save_in
        if verbose:
            ptt.p_ok(f"Saving in file : {save_in}")
            
        new_processor.save_mesh(save_in.parent, 
                                save_in.name, 
                                file_format="ww3")




if __name__ == "__main__":
    exit(main())
    # main()
    
    # file = './DATA/CONFIG_DATA/final_bathy/fusion_litto3d_5m_rge_5m_homonim_100m_recropped_10m.tif'

