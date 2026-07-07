#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Project maregraphic data vertically from ZR into the NM reference.
"""
import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
import xarray as xr

import personal_tolosa_tools as ptt

WATER_LEVEL_VAR = "ssh"

DEFAULT_RAM_FILE       = "/home/uli_lsaisset/DATA/CONFIG_DATA/RAM_PACK/CSV/RAM.csv"
DEFAULT_BATHYELLI_FILE = "/home/uli_lsaisset/DATA/CONFIG_DATA/BATHYELLI/BathyElliv2.1_ATL_NM_interpolated.tif"


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Project maregraphic (tide gauge) netCDF data vertically from the "
            "ZR reference to the NM reference, using a RAM CSV file (ZR -> "
            "Ellipsoid) and a BathyElli raster (Ellipsoid -> NM). "
            "This tool is meant to be used after the 'obs_fetcher' tool. "
            "It expects the same netCDF structure as this tools' output."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python launch_nc_maregraph_from_ZH_to_NM.py --input_dir ./refmar\n"
            "  python launch_nc_maregraph_from_ZH_to_NM.py --ram_file RAM.csv "
            "--bathyelli_file BathyElli.tif --input_dir ./refmar --workdir ./nm -v\n"
        ),
    )

    parser.add_argument(
        "--ram_file",
        type=str,
        default=DEFAULT_RAM_FILE,
        help=f"Path to the RAM CSV file (default: {DEFAULT_RAM_FILE}).",
    )

    parser.add_argument(
        "--bathyelli_file",
        type=str,
        default=DEFAULT_BATHYELLI_FILE,
        help=f"Path to the BathyElli .tif raster (default: {DEFAULT_BATHYELLI_FILE}).",
    )

    parser.add_argument(
        "--input_dir", "-i",
        type=str,
        required=True,
        help="Folder containing the input tide gauge .nc files.",
    )

    parser.add_argument(
        "--workdir", "-w",
        type=str,
        default=None,
        help="Working directory where the '_NM.nc' output files are written (default: current directory).",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print informational and warning messages.",
    )

    return parser


def get_elli_to_nm_offset(bathyelli_dataset, lon, lat):
    """
    Sample the BathyElli conversion raster at (lon, lat) and return the
    Ellipsoid -> NM vertical offset, i.e. the value to ADD to an ellipsoidal
    height to obtain the corresponding NM height.

    NOTE: verify the sign convention of the BathyElli raster (it may encode
    NM - Ellipsoid or Ellipsoid - NM depending on how it was produced).
    """
    row, col = bathyelli_dataset.index(lon, lat)
    if not (0 <= row < bathyelli_dataset.height and 0 <= col < bathyelli_dataset.width):
        raise ValueError(f"point ({lon}, {lat}) is outside the BathyElli raster extent")

    value = list(bathyelli_dataset.sample([(lon, lat)]))[0][0]

    nodata = bathyelli_dataset.nodata
    if nodata is not None and np.isclose(value, nodata):
        raise ValueError(f"no BathyElli value at ({lon}, {lat}) (nodata)")
    if np.isnan(value):
        raise ValueError(f"BathyElli value is NaN at ({lon}, {lat})")

    return float(value)


def main() -> None:

    # ------------------------------------------------------------------
    # Parse the arguments
    # ------------------------------------------------------------------
    parser = create_parser()
    args = parser.parse_args()

    ram_file = Path(args.ram_file).expanduser()
    bathyelli_file = Path(args.bathyelli_file).expanduser()
    input_dir = Path(args.input_dir).expanduser()
    output_dir = Path(args.workdir).expanduser() if args.workdir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Read RAM CSV file (contains, among others, the ZR -> Ellipsoid
    # vertical offset for each station: column "ZH_Elli")
    # ------------------------------------------------------------------
    if not ram_file.exists():
        ptt.p_error(f"RAM file not found: {ram_file}")
        sys.exit(1)

    ram_data = pd.read_csv(ram_file, sep='\t', encoding="utf-8", na_values=["", " "])

    for required_col in ("SITE", "ZH_Elli"):
        if required_col not in ram_data.columns:
            ptt.p_error(f"Column '{required_col}' missing from RAM file {ram_file}")
            sys.exit(1)

    ram_names_lowercase = ram_data.SITE.str.lower()

    # ------------------------------------------------------------------
    # Read the BathyElli.tif file (Ellipsoid -> NM conversion surface)
    # ------------------------------------------------------------------
    if not bathyelli_file.exists():
        ptt.p_error(f"BathyElli file not found: {bathyelli_file}")
        sys.exit(1)

    bathyelli_dataset = rasterio.open(bathyelli_file)
    ptt.p_ok(f"BathyElli CRS: {bathyelli_dataset.crs}", args.verbose)
    if bathyelli_dataset.crs is not None and not bathyelli_dataset.crs.is_geographic:
        ptt.p_warning(
            "BathyElli raster is not in a geographic (lon/lat) CRS — "
            "station coordinates will need to be reprojected before sampling.",
            args.verbose,
        )

    # ------------------------------------------------------------------
    # Read the tide gauge data files
    # ------------------------------------------------------------------
    if not input_dir.exists():
        ptt.p_error(f"Maregraph data folder not found: {input_dir}")
        sys.exit(1)

    tide_files = sorted(input_dir.glob("*.nc"))
    if not tide_files:
        ptt.p_error(f"No .nc files found in {input_dir}")
        sys.exit(1)

    for tide_file in tide_files:
        ptt.p_ok(f"Read file           : {tide_file}", args.verbose)
        data = xr.load_dataset(tide_file)

        if "station_name" not in data.variables and "station_name" not in data:
            ptt.p_warning(f"'station_name' not found in {tide_file}, skipping file", args.verbose)
            continue

        if WATER_LEVEL_VAR not in data.variables:
            ptt.p_warning(f"'{WATER_LEVEL_VAR}' not found in {tide_file}, skipping file", args.verbose)
            continue

        # --------------------------------------------------------------
        # Projection verticale ZR -> Ellipsoide (via RAM)
        # --------------------------------------------------------------
        data_station_name = str(data.station_name.data)
        ptt.p_ok(f"Looking for station : {data_station_name}", args.verbose)
        data_station_name_simpler = ' '.join(data_station_name.lower().split('_'))
        matching_names = ram_names_lowercase.str.startswith(data_station_name_simpler)

        if not matching_names.any():
            ptt.p_warning(
                f"Station '{data_station_name}' not found in RAM file "
                f"({tide_file}), skipping file",
                args.verbose,
            )
            continue
        if matching_names.sum() > 1:
            ptt.p_warning(
                f"Multiple RAM matches for '{data_station_name}', "
                f"using the first: {ram_data.SITE[matching_names].values}",
                args.verbose,
            )

        ptt.p_ok(f"Found station in RAM: {ram_data.SITE[matching_names].values[0]}", args.verbose)

        value_from_zh_to_elli = ram_data.ZH_Elli[matching_names].values
        if np.isnan(value_from_zh_to_elli[0]):
            ptt.p_warning(
                f"ZH_Elli is missing for station '{data_station_name}' "
                f"({tide_file}), skipping file",
                args.verbose,
            )
            continue

        zh_to_elli = float(value_from_zh_to_elli[0])
        ptt.p_ok(f"ZH to Ellipsoid     : {zh_to_elli}", args.verbose)

        # --------------------------------------------------------------
        # Projection verticale Ellipsoide -> NM (via BathyElli)
        # --------------------------------------------------------------
        lon = float(data.longitude.values)
        lat = float(data.latitude.values)

        try:
            elli_to_nm = get_elli_to_nm_offset(bathyelli_dataset, lon, lat)
        except ValueError as err:
            ptt.p_warning(
                f"Elli to NM offset missing for station '{data_station_name}' "
                f"({tide_file}): {err}, skipping file",
                args.verbose,
            )
            continue

        ptt.p_ok(f"Ellipsoid to NM     : {elli_to_nm}", args.verbose)

        total_offset = zh_to_elli - elli_to_nm
        ptt.p_ok(f"Total ZR to NM      : {total_offset}", args.verbose)

        # --------------------------------------------------------------
        # Application de la correction verticale à ssh
        # --------------------------------------------------------------
        data[WATER_LEVEL_VAR] = data[WATER_LEVEL_VAR] + total_offset
        data[WATER_LEVEL_VAR].attrs["vertical_reference"] = "NM"
        data.attrs["zr_to_nm_offset_m"] = total_offset

        # --------------------------------------------------------------
        # Write the result, one file per station, suffixed with '_NM'
        # --------------------------------------------------------------
        output_file = output_dir / f"{tide_file.stem}_NM{tide_file.suffix}"
        data.to_netcdf(output_file)
        ptt.p_ok(f"Written             : {output_file}", args.verbose)

    bathyelli_dataset.close()


if __name__ == "__main__":
    main()
