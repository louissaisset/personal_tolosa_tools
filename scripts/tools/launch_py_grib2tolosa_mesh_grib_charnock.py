#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 26 13:59:14 2026

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

import xarray as xr
import cfgrib
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.optimize import newton

# =============================================================================
#  Physical / numerical constants  (identical to the Fortran)
# =============================================================================
RHO_AIR = 1.29        # kg m-3
KARMAN  = 0.4         # von Karman constant
G       = 9.81        # m s-2
Z_REF   = 10.0        # reference height [m]
EPSIL   = 1.0e-10     # floor to avoid log(0) / div-by-zero
NITER   = 150         # Newton iterations
 
 
# =============================================================================
#  CNES Julian date  (days since 1950-01-01 00:00)
# =============================================================================
 
def to_cnes_julian(dt64: np.datetime64) -> float:
    """Convert a numpy datetime64 to CNES Julian days (origin 1950-01-01)."""
    epoch = np.datetime64("1950-01-01T00:00:00", "s")
    return float((dt64.astype("datetime64[s]") - epoch) / np.timedelta64(1, "D"))
 
 
# =============================================================================
#  Charnock drag coefficient  (cd_choice == 3 in the Fortran)
#  Uses scipy.optimize.newton with analytical derivative for efficiency.
# =============================================================================
 
def cd_charnock(mod_wind: np.ndarray, alpha_c: float) -> np.ndarray:
    """
    Compute the drag coefficient Cd via the Charnock roughness closure.
 
    The implicit equation solved (in u*^2, re-arranged) is:
 
        f(x)  = x . ln(x)^2 - xa . U^2 . kappa^2  = 0
        f'(x) = ln(x) . (ln(x) + 2)
 
    where  xa = alpha_c / (Z_ref . g).
 
    scipy.optimize.newton operates element-wise on the full wind array,
    replacing the explicit Fortran Newton loop.
    """
    xa = alpha_c / (Z_REF * G)
    xb = xa * mod_wind**2 * KARMAN**2
 
    def f(x):
        lx = np.log(np.maximum(x, EPSIL))
        return x * lx**2 - xb
 
    def fprime(x):
        lx = np.log(np.maximum(x, EPSIL))
        return lx * (lx + 2.0)
 
    x0   = np.full_like(mod_wind, xa * 0.01, dtype=np.float64)
    xsol = newton(f, x0, fprime=fprime, maxiter=NITER, tol=1e-10)
 
    return xsol / np.maximum(EPSIL, xa * mod_wind**2)
 
 
def wind_stress_charnock(u10: np.ndarray, v10: np.ndarray,
                         alpha_c: float):
    """
    Compute the two wind-stress components on the GRIB grid:
 
        tau_u = rho_air . Cd . |U| . u10
        tau_v = rho_air . Cd . |U| . v10
    """
    mod_wind = np.sqrt(u10**2 + v10**2)
    cd       = cd_charnock(mod_wind.ravel(), alpha_c).reshape(mod_wind.shape)
    factor   = RHO_AIR * cd * mod_wind
    return factor * u10, factor * v10
 
 
# =============================================================================
#  Bilinear interpolation via scipy.interpolate.RegularGridInterpolator
# =============================================================================
 
# def build_interpolator(grib_lats: np.ndarray, grib_lons: np.ndarray,
#                        field_2d: np.ndarray) -> RegularGridInterpolator:
#     """
#     Wrap a (ny, nx) GRIB field in a RegularGridInterpolator.
 
#     Parameters
#     ----------
#     grib_lats : 1-D array, strictly ascending [degrees]
#     grib_lons : 1-D array, in [0, 360) [degrees]
#     field_2d  : 2-D array, shape (ny, nx)
 
#     Returns
#     -------
#     RegularGridInterpolator  (method='linear', nearest-edge extrapolation)
#     """
#     return RegularGridInterpolator(
#         (grib_lats, grib_lons), field_2d,
#         method="linear",
#         bounds_error=False,  # don't raise at mesh boundary / slightly outside
#         fill_value=None,     # use nearest boundary value (mirrors Fortran)
#     )

class UpdatableRegularGridInterpolator:
    """
    Wrapper around RegularGridInterpolator that allows updating the field values
    without recreating the entire interpolator object.
    """
    def __init__(self, lat_grid, lon_grid):
        self.lat_grid = lat_grid
        self.lon_grid = lon_grid
        self._interpolator = None
        self._field = None
    
    def update_field(self, field):
        """Update the field values (2D array) without recreating grid structure."""
        self._field = field
        self._interpolator = RegularGridInterpolator(
            (self.lat_grid, self.lon_grid), field,
            method="linear",
            bounds_error=False,
            fill_value=None
        )
    
    def __call__(self, points):
        """Interpolate at given points."""
        if self._interpolator is None:
            raise ValueError("Field not initialized. Call update_field() first.")
        return self._interpolator(points)


# =============================================================================
#  Output writers
# =============================================================================
 
def write_forcing_a(path: Path, records: list):
    """
    Write a .a binary forcing file.
 
    Layout (mirrors the Fortran MPI_FILE_WRITE_AT):
        record it  →  bytes [ (it-1)*N*4 ,  it*N*4 )
    where N = nb_ele2d and the dtype is float32.
 
    Parameters
    ----------
    path    : output file path
    records : list of ndarray (nb_ele2d,) float64  – one array per timestep
    """
    with open(path, "wb") as fh:
        for rec in records:
            fh.write(rec.astype(np.float32).tobytes())
 
 
def write_forcing_b(path: Path, var_name: str, nb_ele2d: int,
                    jul_times: list, min_vals: list, max_vals: list):
    """
    Write a .b ASCII metadata file.
 
    Format (Fortran):
        '(f15.6,a2,f15.6,f15.6)'  →  "  <jul> :<min><max>"
    """
    with open(path, "w") as fh:
        fh.write(f"{'%    External Forcing for tolosa':<50}\n")
        fh.write(f"{'%    ---------------------------':<50}\n")
        fh.write(f"{'%    Number of elements:':<50}{nb_ele2d:7d}\n")
        fh.write(f"{'%    Short name of the grib parameter database :':<50}{var_name:<4}\n")
        fh.write(f"{'%    Time       -       min     -       max':<50}\n")
        for jul, mn, mx in zip(jul_times, min_vals, max_vals):
            fh.write(f"{jul:15.6f} :{mn:15.6f}{mx:15.6f}\n")
            
# =============================================================================
#  GRIB reader
# =============================================================================
 
def open_grib_variable(grib_path: str, short_name: str) -> xr.DataArray:
    """
    Open one variable from a GRIB file using cfgrib.
 
    Returns an xarray DataArray with dimensions (time, latitude, longitude).
    Raises RuntimeError if the variable is not found.
    """
    try:
        ds = cfgrib.open_dataset(
            grib_path,
            backend_kwargs={"filter_by_keys": {"shortName": short_name}},
            indexpath=None,       # avoid stale .idx files
        )
    except Exception as exc:
        raise RuntimeError(
            f"Could not open shortName='{short_name}' from {grib_path}: {exc}"
        ) from exc
 
    # cfgrib variable names vary; pick the first data variable
    data_vars = list(ds.data_vars)
    if not data_vars:
        raise RuntimeError(f"No data variables found for shortName='{short_name}'.")
    return ds[data_vars[0]]

def stack_time_step(da: xr.DataArray) -> xr.DataArray:
    """
    Stack 'time' and 'step' dimensions into a single 'time' dimension.
    
    This function handles GRIB files that have both 'time' (analysis time) and
    'step' (forecast hour) dimensions by creating a single time dimension
    using the valid_time coordinate.
    
    Parameters
    ----------
    da : xr.DataArray
        DataArray with dimensions (time, step, ...) or just (time, ...)
    
    Returns
    -------
    xr.DataArray
        DataArray with a single 'time' dimension containing all valid times
    """
    # If no step dimension, return as is
    if 'step' not in da.dims:
        return da
    
    # Stack time and step into a single dimension
    da = da.stack(stacked_time=('time', 'step'))
    
    # Create proper time coordinate using valid_time if it exists
    if 'valid_time' in da.coords:
        # valid_time is a coordinate with dimensions (time, step)
        # After stacking, we need to extract it properly
        valid_time = da.valid_time.values.ravel()
        da = da.drop_vars(['stacked_time', 'time', 'step']).assign_coords(stacked_time=valid_time)
    else:
        # If valid_time doesn't exist, compute from time + step
        time_vals = da.time.values
        step_vals = da.step.values
        valid_time = np.add.outer(time_vals, step_vals).ravel()
        da = da.assign_coords(stacked_time=valid_time)
    
    # Rename stacked_time to time for consistency
    da = da.rename({'stacked_time': 'time'})
    
    # Ensure time coordinate is sorted
    time_argsort = np.argsort(da.time.values)
    if not np.all(time_argsort == np.arange(len(da.time))):
        da = da.isel(time=time_argsort)
    
    return da

def prepare_grib_coords(da: xr.DataArray):
    """
    Return the DataArray with latitudes ensured ascending, plus the
    1-D lat and lon arrays (lons mapped to [0, 360) to match the Fortran).
    """
    
    new_da = stack_time_step(da)
    
    lat_name = "latitude" if "latitude" in new_da.dims else "lat"
    lon_name = "longitude" if "longitude" in new_da.dims else "lon"
 
    lats = new_da[lat_name].values
    lons = new_da[lon_name].values   # Fortran convention
 
    if lats[0] > lats[-1]:              # flip to ascending
        new_da   = new_da.isel(**{lat_name: slice(None, None, -1)})
        lats = new_da[lat_name].values
 
    return new_da, lats, lons


def create_parser():
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description="Convert GRIB wind/pressure data to Tolosa .a/.b forcing files "
                    "using the Charnock wind-stress parametrization (method 3)."
    )
    
    # Create a mutually exclusive group for input method
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument(
        "-m", "--mesh", 
        help="Path to the Tolosa mesh file (*_latlong.msh)."
    )
    input_group.add_argument(
        "mesh_positional", nargs="?",
        help="Path to the Tolosa mesh file (*_latlong.msh) (positional alternative)."
    )
    
    grib_group = parser.add_mutually_exclusive_group()
    grib_group.add_argument(
        "-g", "--grib",
        help="Path to the GRIB file (cfgrib-readable; extract .tar before calling)."
    )
    grib_group.add_argument(
        "grib_positional", nargs="?",
        help="Path to the GRIB file (positional alternative)."
    )
    
    charnock_group = parser.add_mutually_exclusive_group()
    charnock_group.add_argument(
        "-v", "--charnock", type=float, default=0.028, metavar="ALPHA_C",
        help="Charnock coefficient alpha_c (default: 0.028)."
    )
    charnock_group.add_argument(
        "charnock_positional", nargs="?", type=float,
        help="Charnock coefficient alpha_c (positional alternative)."
    )
    
    parser.add_argument(
        "-o", "--output", default=".",
        help="Output directory for forcing.*.a/b files (default: current directory)."
    )
    return parser

# =============================================================================
#  Main
# =============================================================================
 
def main():
    parser = create_parser()
    args = parser.parse_args()
    
    # Determine mesh path
    if args.mesh:
        mesh_path = args.mesh
    elif args.mesh_positional:
        mesh_path = args.mesh_positional
    else:
        parser.error("Mesh file is required. Provide via -m/--mesh or as first positional argument.")
    
    # Determine GRIB path
    if args.grib:
        grib_path = args.grib
    elif args.grib_positional:
        grib_path = args.grib_positional
    else:
        parser.error("GRIB file is required. Provide via -g/--grib or as second positional argument.")
    
    # Determine Charnock coefficient
    if args.charnock is not None:
        alpha_c = args.charnock
    elif args.charnock_positional is not None:
        alpha_c = args.charnock_positional
    else:
        alpha_c = 0.028
    
    # Convert to Path objects
    mesh_path = Path(mesh_path).expanduser().resolve()
    grib_path = Path(grib_path).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    
    output_dir.mkdir(parents=True, exist_ok=True)
 
    # -- 1. Read mesh ----------------------------------------------------------
    print(f"[1/4] Reading mesh: {mesh_path.name}")
    file_rdr = ptt.FileReader()
    mesh = file_rdr.read_file(str(mesh_path.parent), mesh_path.name)
    processor = ptt.MeshDataProcessor(mesh)
    cell_lon, cell_lat, _ = processor.cell_centers_array.T
    nb_ele2d = processor.num_cells
    
    print(f"      {nb_ele2d:,} triangle cells  "
          f"(lon [{cell_lon.min():.2f}, {cell_lon.max():.2f}]  "
          f"lat [{cell_lat.min():.2f}, {cell_lat.max():.2f}])")
 
    # -- 2. Open GRIB variables ------------------------------------------------
    print(f"[2/4] Opening GRIB: {Path(grib_path).name}")
    da_u, grib_lats, grib_lons = prepare_grib_coords(open_grib_variable(grib_path, "10u"))
    da_v, _,          _        = prepare_grib_coords(open_grib_variable(grib_path, "10v"))
    da_p, _,          _        = prepare_grib_coords(open_grib_variable(grib_path, "msl"))
 
    time_dim = next(d for d in da_u.dims if "time" in d)
    times    = da_u[time_dim].values
    n_times  = len(times)
    print(f"      {n_times} time steps  "
          f"({np.datetime_as_string(times[0], unit='h')} -> "
          f"{np.datetime_as_string(times[-1], unit='h')})")
    
    
    # -- 3. Build interpolation infrastructure (once) --
    print("[3/4] Preparing interpolation infrastructure ...")
    
    query_pts = np.column_stack([cell_lat, cell_lon])
    
    # Create updatable interpolators for each variable
    interpolators = {
        "uwnd": UpdatableRegularGridInterpolator(grib_lats, grib_lons),
        "vwnd": UpdatableRegularGridInterpolator(grib_lats, grib_lons),
        "usst": UpdatableRegularGridInterpolator(grib_lats, grib_lons),
        "vsst": UpdatableRegularGridInterpolator(grib_lats, grib_lons),
        "msl":  UpdatableRegularGridInterpolator(grib_lats, grib_lons)
    }
    
    # -- 4. Time loop (now efficient!) ------------------------------------------
    print(f"[4/4] Processing {n_times} time steps ...")
    
    records = {v: [] for v in ("uwnd", "vwnd", "usst", "vsst", "msl")}
    jul_times = []
    min_vals = {v: [] for v in records}
    max_vals = {v: [] for v in records}
    
    for it in range(n_times):
        
        jul_times.append(to_cnes_julian(times[it]))
        
        # Get 2-D slices (ny, nx)
        kw = {time_dim: it}
        u2d = da_u.isel(**kw).values.astype(np.float64)
        v2d = da_v.isel(**kw).values.astype(np.float64)
        p2d = da_p.isel(**kw).values.astype(np.float64)
        
        # Wind stress on the GRIB grid
        tau_u2d, tau_v2d = wind_stress_charnock(u2d, v2d, alpha_c)
        
        # Update each interpolator with new field values
        interpolators["uwnd"].update_field(u2d)
        interpolators["vwnd"].update_field(v2d)
        interpolators["usst"].update_field(tau_u2d)
        interpolators["vsst"].update_field(tau_v2d)
        interpolators["msl"].update_field(p2d)
        
        # Perform all interpolations (no recreating interpolators!)
        interp = {
            var: interpolators[var](query_pts)
            for var in interpolators.keys()
        }
        
        # Store results
        for var, data in interp.items():
            records[var].append(data)
            min_vals[var].append(float(data.min()))
            max_vals[var].append(float(data.max()))
        
        if (it + 1) % max(1, n_times // 10) == 0 or it == n_times - 1:
            print(f"      step {it+1:4d}/{n_times}  jul={jul_times[-1]:.4f}")
 
    # -- 5. Write output files -------------------------------------------------
    print("Writing output files ...")
    for var in ("uwnd", "vwnd", "usst", "vsst", "msl"):
        a_path = output_dir / f"forcing.{var}.a"
        b_path = output_dir / f"forcing.{var}.b"
        write_forcing_a(a_path, records[var])
        write_forcing_b(b_path, var, nb_ele2d, jul_times, min_vals[var], max_vals[var])
        print(f"  OK  {a_path.name}  ({a_path.stat().st_size/1e6:.1f} MB)  +  {b_path.name}")
 
    print("Done.")
 
 
if __name__ == "__main__":
    main()