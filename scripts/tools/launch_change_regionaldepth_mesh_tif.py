#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul 15 15:23:11 2025

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
import re, struct, copy
import numpy as np
import rasterio
import geopandas as gpd
from shapely.geometry import Point

def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description='Creates a new regional.depth file, corrected for infrastructures depth',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    
    parser.add_argument(
        '--shp_infras', 
        type=str, 
        required=True,
        help='Path to the structure zones shapefile'
    )
    
    parser.add_argument(
        '--tif_rectified',
        type=str, 
        required=True,
        help='Path to the new depth TIF file'
    )
    parser.add_argument(
        '--physical_list',
        type=str,
        nargs='+',
        default=[],
        help='List of physical tags (at least one required). Example: --physical_list tag1 tag2 tag3'
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
        default='regional.depth-ele_NEW.a',
        help='Name of resulting file (default: regional.depth-ele_NEW.a)'
    )
    
    return parser

def read_depth_ele_a(file_depth_ele_a, file_depth_ele_b):
    fb = open( file_depth_ele_b , "r")
    for line in fb:
        m = re.match("\s*(\d+) depth values", line)
        if m:
            nv = int(m.group(1))
            break
    fb.close()
    
    fa = open(file_depth_ele_a , "rb")
    temp = fa.read(nv*4)
    bathy = np.array(struct.unpack('>' + 'f'*nv, temp))

    return(bathy)

def read_grid_ele_a(file_grid_ele_a, file_grid_ele_b):
    fb = open( file_grid_ele_b , "r")
    for line in fb:
        m = re.match("\s*(\d+) longitude values", line)
        if m:
            nv = int(m.group(1))
            break
    fb.close()
    
    fa = open(file_grid_ele_a , "rb")
    total_len = int(((nv+4095)/4096))*4096
    temp = fa.read(total_len*4*2)
    latlon = np.array(struct.unpack('>' + 'f'*total_len*2, temp))
    
    cut_latlon = latlon.reshape(2, total_len)[:,:nv]
    
    return(cut_latlon)

def write_depth_ele_a(newfile, bath_cell):
    bath_cell_bigendian = struct.pack('>' + 'f'*len(bath_cell), *bath_cell)
    fa = open( newfile , "wb" )
    fa.write(bath_cell_bigendian)
    fa.close()

def assign_depth_to_points_optimized(latlon, 
                                     depth_file, 
                                     polygons_file, 
                                     physical_list=[]):

    polygons_gdf = gpd.read_file(polygons_file)

    # Note: Point(lon, lat) — GeoDataFrame expects (x, y) = (lon, lat)
    points_gdf = gpd.GeoDataFrame(
        {'point_idx': range(len(latlon))},
        geometry=[Point(lat, lon) for lat, lon in latlon],
        crs='EPSG:4326'
    )

    with rasterio.open(depth_file) as depth_raster:
        depth_crs = depth_raster.crs
        
        if polygons_gdf.crs != depth_crs:
            polygons_gdf = polygons_gdf.to_crs(depth_crs)
        if points_gdf.crs != depth_crs:
            points_gdf = points_gdf.to_crs(depth_crs)
        
        # Select only tagged elements
        if physical_list:
            polygons_gdf = polygons_gdf[polygons_gdf['physical'].isin(physical_list)].reset_index(drop=True)
        
        # Need polygons to select "points within"
        if not all(polygons_gdf.geom_type.unique() =='Polygon'):
            polygons_gdf['geometry'] = polygons_gdf.polygonize()
        depths = np.full(len(latlon), np.nan)

        # Vectorized spatial join - replaces the entire per-point loop
        points_in_polygons = gpd.sjoin(
            points_gdf, polygons_gdf, how='inner', predicate='within'
        )

        if points_in_polygons.empty:
            return depths

        # Deduplicate: a point may fall in multiple polygons
        points_in_polygons = points_in_polygons.drop_duplicates(subset='point_idx')

        # Single batched rasterio.sample() call for all matching points
        coords = [
            (geom.x, geom.y)
            for geom in points_in_polygons.geometry
        ]
        sampled = np.array(list(depth_raster.sample(coords)))  # shape: (N, bands)

        depth_vals = sampled[:, 0].astype(float)

        # Mask nodata values
        if depth_raster.nodata is not None:
            depth_vals[depth_vals == depth_raster.nodata] = np.nan

        # Write back using original indices
        original_indices = points_in_polygons['point_idx'].values
        depths[original_indices] = depth_vals

    return depths


def assign_depth_to_points_optimized_OLD(latlon, depth_file, polygons_file):
    """
    Optimized version using rasterio.sample for depth extraction.
    """
    
    # Load the polygons shapefile
    polygons_gdf = gpd.read_file(polygons_file)
    
    # Convert lat/lon points to geodataframe
    points_gdf = gpd.GeoDataFrame(
        geometry=[Point(lat, lon) for lat, lon in latlon],
        crs='EPSG:4326'
    )
    
    # Open depth raster
    with rasterio.open(depth_file) as depth_raster:
        depth_crs = depth_raster.crs
        
        # Transform geometries to match depth raster CRS
        if polygons_gdf.crs != depth_crs:
            polygons_gdf = polygons_gdf.to_crs(depth_crs)
            
        if points_gdf.crs != depth_crs:
            points_gdf = points_gdf.to_crs(depth_crs)
        
        # Initialize depth array
        depths = np.full(len(latlon), np.nan)
        
        # Create spatial index for polygons for faster lookup
        polygons_sindex = polygons_gdf.sindex
        
        
        # For each point, check if it's in any polygon
        for point_idx, point in points_gdf.iterrows():
            
            # Get potential polygon matches using spatial index
            possible_matches_idx = list(polygons_sindex.intersection(point.geometry.bounds))
            possible_matches = polygons_gdf.iloc[possible_matches_idx]
            
            # Check actual intersection
            intersecting_polygons = possible_matches[possible_matches.intersects(point.geometry)]
            
            if not intersecting_polygons.empty:
                # Point is inside at least one polygon
                # Sample depth value at this point
                coords = [(point.geometry.x, point.geometry.y)]
                depth_values = list(depth_raster.sample(coords))
                
                if depth_values and depth_values[0][0] != depth_raster.nodata:
                    depths[point_idx] = depth_values[0][0]

        return depths

def checkfile(file):
    if file.exists():
        ptt.p_ok(f"Working with file : {file}")
    else :
        ptt.p_error(f"No such file: {file}")
        return(0)

def main():
    """
    The program creates a new regional.depth-ele.a type file saved as --save_in
    inside --workdir.
    
    It uses the polygons contained in --shp_infras and the rectified depths 
    inside --tif_rectified (absolute paths). 
    
    The program assumes all the original depths and cell centers are in the 
    regional.ele and regional.depth files in --workdir. 
    
    The resulting regional.depth.a file is saved inside --workdir under the 
    file name --save_in
    """
    parser = create_parser()
    args = parser.parse_args()
    
    # Set working directory, with current directory as default
    if args.workdir:
        current_path = Path(args.workdir)
        if not current_path.exists():
            ptt.p_error(f"Working directory does not exist: {current_path}")
            sys.exit(1)
        if not current_path.is_dir():
            ptt.p_error(f"Working directory is not a directory: {current_path}")
            sys.exit(1)
    else:
        current_path = Path.cwd()
    
    print(f"Launched from : {current_path}")
    
    # Handle user-specified files (can be absolute or relative paths)
    file_structzones_shp = Path(args.shp_infras)
    if not file_structzones_shp.is_absolute():
        file_structzones_shp = current_path / file_structzones_shp
    checkfile(file_structzones_shp)
    
    file_newdepth_tif = Path(args.tif_rectified)
    if not file_newdepth_tif.is_absolute():
        file_newdepth_tif = current_path / file_newdepth_tif
    checkfile(file_newdepth_tif)
    
    
    # Check required grid files in working directory
    file_grid_ele_a = current_path / "regional.grid-ele.a"
    checkfile(file_grid_ele_a)
        
    file_grid_ele_b = current_path / "regional.grid-ele.b"
    checkfile(file_grid_ele_b)
    
    file_depth_ele_a = current_path / "regional.depth-ele.a"
    checkfile(file_depth_ele_a)
        
    file_depth_ele_b = current_path / "regional.depth-ele.b"
    checkfile(file_depth_ele_b)
    
    
    # Define the result file path
    depth_ele_a_new = current_path / args.save_in
    ptt.p_ok(f"Creating file : {depth_ele_a_new}")
    
    
    # Read cell centers
    latlon = read_grid_ele_a(file_grid_ele_a, file_grid_ele_b).T

    # Read initial cell depth
    depths = read_depth_ele_a(file_depth_ele_a, file_depth_ele_b)
    
    # Compute the new sampled depths for the cells inside the infrastructures
    new_depth_struct = assign_depth_to_points_optimized(latlon, 
                                                        file_newdepth_tif, 
                                                        file_structzones_shp,
                                                        args.physical_list)
    
    # Assemble the depth values
    new_depth = copy.copy(depths)
    new_depth[~np.isnan(new_depth_struct)] = -1*new_depth_struct[~np.isnan(new_depth_struct)]
    
    # Write the new depth values to the result file
    write_depth_ele_a(depth_ele_a_new, new_depth)


if __name__ == "__main__":
    # exit(main())
    main()
    
    
    
    
    # # Structure cells in original bathy
    # fig, ax = plt.subplots(1,1, dpi=300)
    # scb = ax.scatter(latlon[:,0][~np.isnan(new_depth_struct)], 
    #                  latlon[:, 1][~np.isnan(new_depth_struct)], 
    #                  c=depths[~np.isnan(new_depth_struct)], 
    #                  s=3, vmin=-5, vmax=5)
    # ax.set_aspect(1)
    # fig.colorbar(scb)
    # plt.show()
    
    
    
    # # Rectified cells    
    # fig, ax = plt.subplots(1,1, dpi=300)
    # scb = ax.scatter(latlon[:,0], 
    #                  latlon[:, 1], 
    #                  c=new_depth_struct, 
    #                  s=3, vmin=-5, vmax=5)
    # ax.set_aspect(1)
    # fig.colorbar(scb)
    # xmin, xmax = fig.axes[0].get_xlim()
    # ymin, ymax = fig.axes[0].get_ylim()
    # plt.show()
    
    

    # # Original bathy from meshtool
    # fig, ax = plt.subplots(1,1, dpi=300)
    # scb = ax.scatter(latlon[:,0], 
    #                  latlon[:, 1], 
    #                  c=new_depth, 
    #                  s=3, vmin=-30, vmax=30, cmap='RdBu')
    # ax.set_xlim(xmin, xmax)
    # ax.set_ylim(ymin, ymax)
    # ax.set_aspect(1)
    # fig.colorbar(scb)
    # plt.show()
    
    

    # # Comparison
    # fig, (ax1, ax2) = plt.subplots(1, 2, dpi=300)
    # ax1.scatter(latlon[:,0], 
    #             latlon[:, 1], 
    #             c=depths, 
    #             s=1, vmin=-5, vmax=5, cmap='RdBu')
    # ax2.scatter(latlon[:,0], 
    #             latlon[:, 1], 
    #             c=new_depth, 
    #             s=1, vmin=-5, vmax=5, cmap='RdBu')
    # ax1.set_xlim(xmin, xmax)
    # ax1.set_ylim(ymin, ymax)
    # ax1.set_aspect(1)
    # ax2.set_xlim(xmin, xmax)
    # ax2.set_ylim(ymin, ymax)
    # ax2.set_aspect(1)
    # plt.show()

