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
import geopandas as gpd
from shapely.geometry import Point
from collections import defaultdict
import matplotlib.pyplot as plt

# Script to visualize seamsh topology errors

# =========== Parameters ===========

parser = argparse.ArgumentParser(
    description="Check the contents of a .shp file. Looks for any unconnected endpoint in the geometries"
)
parser.add_argument("shapefile", 
                    type=str,
                    help="Path to the .shp file")
parser.add_argument('--plot', '-p',
                    action='store_true',
                    help='Activate verbosity')


# ========== Read arguments ==========

args = parser.parse_args()


# =========== Computations ===========

gdf = gpd.read_file(args.shapefile)

# Optionnel : ne garder que les lignes valides
gdf = gdf[gdf.is_valid]
gdf = gdf.explode(index_parts=False).reset_index(drop=True)  # décompose les MultiLineString

# === Construction du graphe point -> courbes ===
point_connections = defaultdict(list)

for idx, line in gdf.iterrows():
    coords = list(line.geometry.coords)
    start = tuple(coords[0])
    end = tuple(coords[-1])
    point_connections[start].append(idx)
    point_connections[end].append(idx)

# === Détection des problèmes ===
too_many_connections = []
dangling_points = []

for pt, connected in point_connections.items():
    if len(connected) > 2:
        too_many_connections.append(Point(pt))
    elif len(connected) == 1:
        dangling_points.append(Point(pt))

# === Résumé ===
ptt.p_ok(f"Nombre de lignes : {len(gdf)}")
if len(too_many_connections):
    ptt.p_warning(f"Points avec > 2 connexions : {len(too_many_connections)}")
if len(dangling_points):
    ptt.p_warning(f"Points isolés ou extrémités (1 connexion) : {len(dangling_points)}")
if not (len(too_many_connections) or len(dangling_points)):
    ptt.p_ok("Pas d'erreur de raccordement")

# === Affichage matplotlib ===
if args.plot:
    fig, ax = plt.subplots()
    gdf.plot(ax=ax, color='lightgray', linewidth=1)
    if too_many_connections:
        gpd.GeoSeries(too_many_connections).plot(ax=ax, color='red', label='>2 connexions')
    if dangling_points:
        gpd.GeoSeries(dangling_points).plot(ax=ax, color='orange', label='Extrémités')
    plt.legend()
    plt.title("Problèmes de topologie")
    plt.show()