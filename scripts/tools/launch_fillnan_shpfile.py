#!/usr/bin/env python3

import numpy as np
import rasterio
from rasterio.enums import Resampling
from scipy import ndimage, interpolate
import argparse
from pathlib import Path
import sys

def fill_nan_with_nearest(data, mask, domain_mask):
    target_mask = mask & domain_mask
    filled = data.copy()
    nearest_indices = ndimage.distance_transform_edt(
        target_mask, return_distances=False, return_indices=True
    )
    filled[target_mask] = data[tuple(nearest_indices[:, target_mask])]
    return filled

def fill_nan_bilinear(data, mask, domain_mask):
    target_mask = mask & domain_mask
    y, x = np.indices(data.shape)
    valid_points = ~mask & domain_mask
    coords = np.array((x[valid_points], y[valid_points])).T
    values = data[valid_points]
    filled = data.copy()
    interpolated = interpolate.griddata(
        coords, values, (x, y), method='linear', fill_value=np.nan
    )
    # fallback to nearest if needed
    if np.isnan(interpolated[target_mask]).any():
        nearest_fallback = fill_nan_with_nearest(data, np.isnan(interpolated), domain_mask)
        interpolated[np.isnan(interpolated)] = nearest_fallback[np.isnan(interpolated)]
    filled[target_mask] = interpolated[target_mask]
    return filled

def process_tif(input_path: Path, output_path: Path, method='nearest'):
    with rasterio.open(str(input_path)) as src:
        data = src.read(1)
        profile = src.profile
        nodata = src.nodata

        if nodata is not None:
            mask = data == nodata
        else:
            mask = np.isnan(data)

        # Domain mask: where we expect valid data
        domain_mask = ndimage.binary_fill_holes(~mask)

        if method == 'nearest':
            filled_data = fill_nan_with_nearest(data, mask, domain_mask)
        elif method == 'bilinear':
            filled_data = fill_nan_bilinear(data, mask, domain_mask)
        else:
            raise ValueError("Method must be 'nearest' or 'bilinear'")

        # Keep NaNs outside the domain
        filled_data[~domain_mask & mask] = np.nan

        profile.update(dtype=rasterio.float32, nodata=None)

        with rasterio.open(str(output_path), 'w', **profile) as dst:
            dst.write(filled_data.astype(np.float32), 1)

def parse_args():
    parser = argparse.ArgumentParser(
        description="Remplit les trous (NaNs internes) dans un fichier TIFF avec interpolation.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-f", "--file",
        type=Path,
        required=True,
        help="Chemin vers le fichier .tif d'entrée"
    )
    parser.add_argument(
        "--method",
        choices=["nearest", "bilinear"],
        default="nearest",
        help="Méthode d'interpolation à utiliser"
    )
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    input_path = args.file.resolve()

    if not input_path.exists() or input_path.suffix.lower() != ".tif":
        sys.exit(f"Erreur : le fichier spécifié n'existe pas ou n'est pas un fichier .tif : {input_path}")

    output_path = input_path.with_stem(input_path.stem + f"_filled_{args.method}")
    process_tif(input_path, output_path, args.method)
    print(f"Fichier interpolé sauvegardé : {output_path}")

