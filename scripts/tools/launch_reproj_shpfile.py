#!/usr/bin/env python3

import argparse
from pathlib import Path
import geopandas as gpd
from pyproj import CRS
import sys

def reproject_shapefile(input_path: Path, output_path: Path):
    # Définir la projection stéréographique personnalisée
    stereo_crs = CRS.from_proj4(
        "+proj=sterea +lat_0=48.315551 +lon_0=-4.431506 "
        "+k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )

    # Charger, reprojeter et sauvegarder
    gdf = gpd.read_file(str(input_path))
    gdf_reproj = gdf.to_crs(stereo_crs)
    gdf_reproj.to_file(str(output_path))

    print(f"Fichier reprojeté : {output_path}")

def parse_args():
    parser = argparse.ArgumentParser(
        description="Reprojette un fichier Shapefile (.shp) vers une projection stéréographique personnalisée.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-f", "--file",
        type=Path,
        required=True,
        help="Chemin vers le fichier .shp à reprojeter"
    )
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    input_path = args.file.resolve()

    if not input_path.exists() or input_path.suffix.lower() != ".shp":
        sys.exit(f"Erreur : le fichier spécifié n'existe pas ou n'est pas un fichier .shp : {input_path}")

    # Générer automatiquement le nom du fichier de sortie
    output_path = input_path.with_stem(input_path.stem + "_reproj_stereo")

    reproject_shapefile(input_path, output_path)

