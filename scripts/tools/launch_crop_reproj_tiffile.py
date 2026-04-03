#!/usr/bin/env python3

import argparse
from pathlib import Path
import sys
import geopandas as gpd
import rasterio
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling

def crop_raster_with_shape(raster_path, shapefile_path, tmp_crop_path):
    with rasterio.open(raster_path) as src:
        gdf = gpd.read_file(shapefile_path).to_crs(src.crs)
        shapes = [geom for geom in gdf.geometry]

        out_image, out_transform = mask(src, shapes=shapes, crop=True)
        out_meta = src.meta.copy()
        out_meta.update({
            "height": out_image.shape[1],
            "width": out_image.shape[2],
            "transform": out_transform
        })

        with rasterio.open(tmp_crop_path, "w", **out_meta) as dest:
            dest.write(out_image)

    print(f"Raster découpé : {tmp_crop_path}")

def reproject_raster_bilinear(src_path, dst_path, dst_crs):
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds
        )
        kwargs = src.meta.copy()
        kwargs.update({
            "crs": dst_crs,
            "transform": transform,
            "width": width,
            "height": height
        })

        with rasterio.open(dst_path, "w", **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear
                )

    print(f"Raster reprojeté (bilinéaire) : {dst_path}")

def extract_suffix(shapefile_name):
    name = Path(shapefile_name).stem
    return name.replace("Zone_Delim_", "") if name.startswith("Zone_Delim_") else name

def parse_args():
    parser = argparse.ArgumentParser(description="Découpe un raster sur un polygone, puis reprojette avec bilinéaire.")
    parser.add_argument("-r", "--raster", required=True, type=Path, help="Fichier raster d’entrée (.tif)")
    parser.add_argument("-s", "--shapefile", required=True, type=Path, help="Shapefile polygonal de découpe")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    raster_path = args.raster.resolve()
    shapefile_path = args.shapefile.resolve()

    suffix = extract_suffix(shapefile_path.name)

    stereo_crs = "+proj=sterea +lat_0=48.315551 +lon_0=-4.431506 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"

    tmp_crop_path = raster_path.with_name(f"{raster_path.stem}_cropped_tmp.tif")
    output_path = raster_path.with_name(f"{raster_path.stem}_cropped_{suffix}_reprojstereo.tif")

    crop_raster_with_shape(raster_path, shapefile_path, tmp_crop_path)
    reproject_raster_bilinear(tmp_crop_path, output_path, stereo_crs)
    tmp_crop_path.unlink()  # Suppression du raster temporaire

