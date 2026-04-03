#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Mar 17 10:15:32 2026

@author: llsaisset
"""

import sys
import argparse
from geopandas import read_file, GeoDataFrame
import matplotlib.pyplot as plt


def print_tag(gdf, tag, short=False):
    if tag == "all":
        for col in gdf.columns:
            if col != "geometry":
                print(f"  {col}: {gdf[col].unique()}")
        if not short:
            for idx, row in gdf.iterrows():
                print(f"\n--- Feature {idx} ---")
                for col in gdf.columns:
                    if col != "geometry":
                        print(f"  {col}: {row[col]}")
                print(f"  geometry_type: {row.geometry.geom_type}")
    else:
        if tag not in gdf.columns:
            print(f"Error: tag '{tag}' not found in file.")
            print(f"Available tags: {', '.join(c for c in gdf.columns if c != 'geometry')}")
            sys.exit(1)
        else:
            print(f"  {tag}: {gdf[tag].unique()}")
            if not short:
                print("\n")
                for idx, row in gdf.iterrows():
                    print(f"Feature {idx} | {tag}: {row[tag]} | geometry: {row.geometry.geom_type}")


def _plot_gdf(gdf: GeoDataFrame(), 
               key: str = 'index') -> None:

    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    
    if key == 'index':
        column = gdf.index
    else:
        column = gdf.get(key)
    # Create the plot
    gdf.plot(column=column, 
             cmap='viridis', 
             categorical=True, 
             legend=True,
             linewidth=1,
             ax=ax)
    
    # Improve legend
    if ax.get_legend():
        legend = ax.get_legend()
        legend.set_title('Physical Type')
        legend.set_bbox_to_anchor((1.05, 1))
    
    # Add grid
    ax.grid(True, linestyle='--', alpha=0.6, linewidth=0.5)
    ax.set_axisbelow(True)  # Put grid behind the data
    
    # Improve tick labels - make them vertical and centered
    for label in ax.get_yticklabels():
        label.set_rotation(90)
        label.set_verticalalignment('center')
        label.set_horizontalalignment('center')
        
    for label in ax.get_xticklabels():
        label.set_rotation(0)  # Y labels typically horizontal
        label.set_verticalalignment('center')
    
    plt.tight_layout()
    plt.show()
    
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Print contents of a .shp file filtered by tag."
    )
    parser.add_argument("shapefile", 
                        type=str,
                        help="Path to the .shp file")
    parser.add_argument("--tag", '-t',
                        type=str,
                        default='all',
                        help="Tag (column) to print, or 'all'")
    parser.add_argument('--short', '-s',
                        action='store_true',
                        help='Activate verbosity')
    parser.add_argument('--plot', '-p',
                        action='store_true',
                        help='Activate shp plotting')

    args = parser.parse_args()

    try:
        gdf = read_file(args.shapefile)
    except Exception as e:
        print(f"Error reading shapefile: {e}")
        sys.exit(1)
    
    if not args.short:
        print(f"Loaded {len(gdf)} features")
        print(f"CRS: {gdf.crs}")
        print(12*"-")
    print(f"Available tags: {', '.join(c for c in gdf.columns if c != 'geometry')}\n")
    
    print_tag(gdf, args.tag, args.short)

    if args.plot:
        _plot_gdf(gdf, 'physical')
        
if __name__ == "__main__":
    main()