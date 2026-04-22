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
from dask.distributed import LocalCluster
# import cfgrib
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.optimize import newton
import dask

# =============================================================================
#  Physical / numerical constants  (identical to the Fortran)
# =============================================================================
RHO_AIR = 1.29        # kg m-3
KARMAN  = 0.4         # von Karman constant
G       = 9.81        # m s-2
Z_REF   = 10.0        # reference height [m]
EPSIL   = 1.0e-10     # floor to avoid log(0) / div-by-zero
NITER   = 150         # Newton iterations
P_STD   = 101_325.0   # Standard atmospheric pressure
 
# Canonical output variable order (must match write_forcing_* expectations)
VARS = ("uwnd", "vwnd", "usst", "vsst", "msl")
 

# =============================================================================
#  CNES Julian date  (days since 1950-01-01 00:00)
# =============================================================================
 
def to_cnes_julian(dt64: np.datetime64) -> float:
    """Convert a numpy datetime64 to CNES Julian days (origin 1950-01-01)."""
    epoch = np.datetime64("1950-01-01T00:00:00", "s")
    return float((dt64.astype("datetime64[s]") - epoch) / np.timedelta64(1, "D"))
 
 
# =============================================================================
#  Charnock drag coefficient  (cd_choice == 3 in the Fortran)
# =============================================================================
 
def cd_charnock(mod_wind: np.ndarray, alpha_c: float) -> np.ndarray:
    """
    Compute the drag coefficient Cd via the Charnock roughness closure.
 
    The implicit equation solved (in u*^2, re-arranged) is:
 
        f(x)  = x . ln(x)^2 - xa . U^2 . K^2  = 0
        f'(x) = ln(x) . (ln(x) + 2)
 
    where  xa = alpha_c / (Z_ref . g).
    """
    xa = alpha_c / (Z_REF * G)
    xb = xa * mod_wind**2 * KARMAN**2
 
    def f(x):
        lx = np.log(np.maximum(x, EPSIL))
        return x * lx**2 - xb
 
    def fprime(x):
        lx = np.log(np.maximum(x, EPSIL))
        return lx * (lx + 2.0)
 
    x0 = np.full_like(mod_wind, xa * 0.01, dtype=np.float64)
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
#  Per-timestep processing  (pure function – safe for dask.delayed)
# =============================================================================

def process_one_step(u2d, v2d, p2d,
                     grib_lats: np.ndarray, grib_lons: np.ndarray,
                     query_pts: np.ndarray, alpha_c: float) -> dict:
    """
    Compute wind stress and bilinearly interpolate all five fields onto the
    unstructured mesh for a single time step.

    This is a *pure*, stateless function so that dask.delayed can schedule
    many instances concurrently without shared mutable state.

    Parameters
    ----------
    u2d, v2d : (ny, nx)  10-m wind components [m s-1]
    p2d      : (ny, nx)  mean sea-level pressure [Pa]
    grib_lats: 1-D ascending latitudes
    grib_lons: 1-D longitudes in [0, 360)
    query_pts: (N, 2) array of (lat, lon) mesh cell centres
    alpha_c  : Charnock coefficient

    Returns
    -------
    dict  {var_name: (N,) float64 array}
    """
    # Guard against dask arrays leaking in (no-op for plain numpy)
    u2d = np.asarray(u2d, dtype=np.float64)
    v2d = np.asarray(v2d, dtype=np.float64)
    p2d = np.asarray(p2d, dtype=np.float64)

    tau_u, tau_v = wind_stress_charnock(u2d, v2d, alpha_c)

    results = {}
    for var, field in zip(VARS, (u2d, v2d, tau_u, tau_v, p2d)):
        # RegularGridInterpolator construction is O(1) on a regular grid
        # (no triangulation), so recreating it per step has negligible cost.
        rgi = RegularGridInterpolator(
            (grib_lats, grib_lons), field,
            method="linear", bounds_error=False, fill_value=None,
        )
        results[var] = rgi(query_pts)
    return results

# =============================================================================
#  Output writers
# =============================================================================
 
def write_forcing_a(path: Path, records: list):
    """
    Write a .a binary forcing file.
 
    Layout (mirrors the Fortran MPI_FILE_WRITE_AT):
        record it  ->  bytes [ (it-1)*N*4 ,  it*N*4 )
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
        '(f15.6,a2,f15.6,f15.6)'  ->  "  <jul> :<min><max>"
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
 
def open_grib_variables(
        grib_path: str,
        short_names: list[str],
        chunks: dict | None = None,
        index_dir: str | None = None,
    ) -> dict[str, xr.DataArray]:
    """
    Open *multiple* variables from a single GRIB file in **one scan**.

    Trying to open all variables at once (no filter_by_keys) is the fast path:
    cfgrib indexes the file once and returns a dataset with all requested
    variables.  If the variables live on different grids/level-types cfgrib
    will raise; we then fall back to one filtered open per variable, each
    reusing the same on-disk index so the binary is only parsed once.

    Parameters
    ----------
    grib_path   : path to the GRIB file
    short_names : GRIB shortNames to extract, e.g. ["10u", "10v", "msl"]
    chunks      : dask chunk spec, e.g. {"time": 1}
    index_dir   : directory for .idx cache files (defaults to GRIB directory)

    Returns
    -------
    dict  {short_name: xr.DataArray}
    """
    if index_dir is None:
        index_dir = os.path.dirname(os.path.abspath(grib_path))
    os.makedirs(index_dir, exist_ok=True)
    grib_basename = os.path.basename(grib_path)

    common_open_kw: dict = {}
    if chunks is not None:
        common_open_kw["chunks"] = chunks

    # ------------------------------------------------------------------
    # Fast path: open everything in one shot (single index build)
    # ------------------------------------------------------------------
    shared_index = os.path.join(index_dir, f"{grib_basename}.all.idx")
    try:
        ds = xr.open_dataset(
            grib_path,
            engine="cfgrib",
            backend_kwargs={"indexpath": shared_index},
            **common_open_kw,
        )
        result: dict[str, xr.DataArray] = {}
        for sn in short_names:
            # Match by GRIB_shortName attribute
            matched = [
                v for v in ds.data_vars
                if ds[v].attrs.get("GRIB_shortName") == sn
            ]
            if not matched:
                raise KeyError(f"shortName '{sn}' not found in combined dataset")
            result[sn] = ds[matched[0]]

        print(f"  Opened {len(short_names)} variables in a single GRIB scan.")
        return result

    except Exception as fast_exc:
        print(f"  Combined open failed ({fast_exc}); falling back to per-variable opens.")

    # ------------------------------------------------------------------
    # Fallback: one filtered open per variable, but index is reused
    # across calls thanks to the persistent indexpath.
    # ------------------------------------------------------------------
    result = {}
    for sn in short_names:
        per_var_index = os.path.join(index_dir, f"{grib_basename}.{sn}.idx")
        try:
            ds = xr.open_dataset(
                grib_path,
                engine="cfgrib",
                backend_kwargs={
                    "filter_by_keys": {"shortName": sn},
                    "indexpath": per_var_index,   # persistent → only built once
                },
                **common_open_kw,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Could not open shortName='{sn}' from {grib_path}: {exc}"
            ) from exc

        data_vars = list(ds.data_vars)
        if not data_vars:
            raise RuntimeError(f"No data variables found for shortName='{sn}'.")
        result[sn] = ds[data_vars[0]]
        print(f"  Opened shortName='{sn}' (per-variable fallback).")

    return result


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
        da = (da
              .drop_vars(['stacked_time', 'time', 'step'])
              .assign_coords(stacked_time=valid_time))
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


# =============================================================================
#  Synthetic meteorological forcing
# =============================================================================

def _wind_components_from_direction(direction_deg: float,
                                    speed: float) -> tuple:
    """
    Convert meteorological wind direction + speed to (u, v) Cartesian
    components.

    Meteorological convention: direction is the angle FROM which the wind
    blows, measured clockwise from North.

        u = −|U| sin(dir)      (eastward component)
        v = −|U| cos(dir)      (northward component)

    Examples
    --------
    dir=0   (N)  ->  u= 0,  v=−|U|   (wind blowing southward)
    dir=90  (E)  ->  u=−|U|, v=0     (wind blowing westward)
    dir=180 (S)  ->  u= 0,  v=+|U|   (wind blowing northward)
    dir=270 (W)  ->  u=+|U|, v=0     (wind blowing eastward)
    """
    d = np.radians(direction_deg)
    return -speed * np.sin(d), -speed * np.cos(d)


def generate_synthetic_forcing(nb_ele2d: int,
                                direction: float,
                                wind_speed: float,
                                pressure: float,
                                t_start: str,
                                t_stop: str,
                                dt_hours: float,
                                t_ramp_h: float,
                                alpha_c: float) -> tuple:
    """
    Build spatially uniform, time-varying forcing fields for every time step.

    Wind components and wind-stress components are linearly ramped from zero
    to their target values over the first ``t_ramp_h`` hours.  MSLP is held
    constant throughout.  No GRIB file is read.

    Parameters
    ----------
    nb_ele2d   : number of unstructured-mesh cells
    direction  : meteorological wind direction [°, clockwise from N]
    wind_speed : target wind speed at 10 m [m s-1]
    pressure   : constant mean sea-level pressure [Pa]
    t_start    : ISO-8601 start datetime, e.g. ``"2024-01-01T00:00:00"``
    t_stop     : ISO-8601 stop  datetime
    dt_hours   : output time step [hours]
    t_ramp_h   : linear wind ramp duration [hours]  (0 -> no ramp)
    alpha_c    : Charnock coefficient

    Returns
    -------
    records, jul_times, min_vals, max_vals, times
        records   – {var: list of (nb_ele2d,) float32 arrays}
        jul_times – list of CNES Julian day floats
        min_vals  – {var: list of floats}
        max_vals  – {var: list of floats}
        times     – numpy array of datetime64 time values
    """
    u0, v0   = _wind_components_from_direction(direction, wind_speed)
    t0       = np.datetime64(t_start, 's')
    t1       = np.datetime64(t_stop,  's')
    dt       = np.timedelta64(int(dt_hours * 3600), 's')
    times    = np.arange(t0, t1 + dt, dt)
    t_ramp_s = t_ramp_h * 3600.0

    records   = {v: [] for v in VARS}
    jul_times = []
    min_vals  = {v: [] for v in VARS}
    max_vals  = {v: [] for v in VARS}

    for t in times:
        # -- ramp factor ----------------------------------------------------
        elapsed_s = float((t - t0) / np.timedelta64(1, 's'))
        ramp = (min(1.0, elapsed_s / t_ramp_s) if t_ramp_s > 0.0 else 1.0)

        # -- wind components at this time step ------------------------------
        u_val = ramp * u0
        v_val = ramp * v0
        mod   = ramp * wind_speed           # = ||(u_val, v_val)||

        # -- Charnock wind stress -------------------------------------------
        if mod > EPSIL:
            cd     = cd_charnock(np.array([mod]), alpha_c)[0]
            factor = RHO_AIR * cd * mod     # = rho · Cd · |U|
        else:
            factor = 0.0

        tau_u = factor * u_val              # = rho · Cd · |U| · u
        tau_v = factor * v_val
        
        # -- pressure: ramp from standard atmosphere to target value --------
        p_val = P_STD + ramp * (pressure - P_STD)
        
        # -- fill uniform fields --------------------------------------------
        field_vals = (
            np.full(nb_ele2d, u_val,    dtype=np.float32),
            np.full(nb_ele2d, v_val,    dtype=np.float32),
            np.full(nb_ele2d, tau_u,    dtype=np.float32),
            np.full(nb_ele2d, tau_v,    dtype=np.float32),
            np.full(nb_ele2d, p_val,    dtype=np.float32),
        )

        jul_times.append(to_cnes_julian(t))

        for var, arr in zip(VARS, field_vals):
            records[var].append(arr)
            # All elements are identical -> min == max == the scalar value
            scalar = float(arr[0])
            min_vals[var].append(scalar)
            max_vals[var].append(scalar)

    return records, jul_times, min_vals, max_vals, times


# =============================================================================
#  Argument parser
# =============================================================================

def create_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Convert GRIB wind/pressure data (or synthetic conditions) to "
            "Tolosa .a/.b forcing files using the Charnock wind-stress "
            "parametrisation (method 3)."
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # -- Mesh ------------------------------------------------------------------
    mesh_group = parser.add_mutually_exclusive_group()
    mesh_group.add_argument(
        "-m", "--mesh",
        help="Path to the Tolosa mesh file (*_latlong.msh).",
    )
    mesh_group.add_argument(
        "mesh_positional", nargs="?",
        help="Mesh file path (positional alternative to -m/--mesh).",
    )

    # -- GRIB -----------------------------------------------------------------
    grib_group = parser.add_mutually_exclusive_group()
    grib_group.add_argument(
        "-g", "--grib",
        help="Path to the GRIB file (cfgrib-readable; extract .tar first).",
    )
    grib_group.add_argument(
        "grib_positional", nargs="?",
        help="GRIB file path (positional alternative to -g/--grib).",
    )

    # -- Charnock --------------------------------------------------------------
    charnock_group = parser.add_mutually_exclusive_group()
    charnock_group.add_argument(
        "-v", "--charnock", type=float, default=0.028, metavar="ALPHA_C",
        help="Charnock coefficient α_c.",
    )
    charnock_group.add_argument(
        "charnock_positional", nargs="?", type=float,
        help="α_c (positional alternative to -v/--charnock).",
    )

    # -- Output ----------------------------------------------------------------
    parser.add_argument(
        "-o", "--output", default=".",
        help="Output directory for forcing.*.a/b files.",
    )

    # -- Synthetic meteorological conditions -----------------------------------
    synt = parser.add_argument_group(
        "Synthetic conditions",
        "When --synthetic is set, no GRIB file is read.  Spatially uniform "
        "fields are generated from the parameters below.  A linear ramp "
        "(--t_ramp) avoids a discontinuous wind onset.",
    )
    synt.add_argument(
        "--synthetic", action="store_true",
        help="Activate synthetic forcing (ignores --grib).",
    )
    synt.add_argument(
        "--direction", type=float, default=0.0, metavar="DEG",
        help=(
            "Meteorological wind direction [° clockwise from N]: "
            "the direction FROM which the wind blows.  "
            "0 = northerly (wind toward S), 90 = easterly (toward W)."
        ),
    )
    synt.add_argument(
        "--wind", type=float, default=10.0, metavar="M_S",
        help="Constant wind speed at 10 m [m s-1].",
    )
    synt.add_argument(
        "--pressure", type=float, default=101325.0, metavar="PA",
        help="Constant mean sea-level pressure [Pa].",
    )
    synt.add_argument(
        "--t_start", type=str, default="2021-04-01T00:00:00", metavar="ISO8601",
        help='Start datetime, e.g. "2024-06-01T00:00:00" (required with --synthetic).',
    )

    # t_stop and duration are mutually exclusive
    stop_group = synt.add_mutually_exclusive_group()
    stop_group.add_argument(
        "--t_stop", type=str, metavar="ISO8601",
        help="Stop datetime (exclusive with --duration).",
    )
    stop_group.add_argument(
        "--duration", type=float, default=240, metavar="HOURS",
        help="Simulation length [hours] (alternative to --t_stop).",
    )

    synt.add_argument(
        "--dt", type=float, default=1.0, metavar="HOURS",
        help="Output time step [hours].",
    )
    synt.add_argument(
        "--t_ramp", type=float, default=0.0, metavar="HOURS",
        help=(
            "Wind ramp duration [hours].  Wind linearly increases from 0 to "
            "--wind over this period.  0 = instantaneous onset (default)."
        ),
    )

    # -- Dask / parallelism ----------------------------------------------------
    dask_grp = parser.add_argument_group(
        "Dask / parallelism",
        "Options controlling lazy GRIB loading and parallel time-step "
        "processing.  Ignored in --synthetic mode.",
    )
    dask_grp.add_argument(
        "--workers", type=int, default=1, metavar="N",
        help=(
            "Number of parallel workers for time-step processing.  "
            "1 = sequential (no dask overhead).  "
            ">1 = threaded dask scheduler (numpy/scipy release the GIL, "
            "so threading gives real speed-up for interpolation-heavy work)."
        ),
    )
    dask_grp.add_argument(
        "--time_chunk", type=int, default=1, metavar="N",
        help=(
            "Number of time steps per dask chunk when opening GRIB files.  "
            "1 keeps peak memory to ~1 time slice per variable (default).  "
            "Increase if you have RAM to spare and want fewer small reads."
        ),
    )

    return parser

# =============================================================================
#  Main
# =============================================================================
 
def main():
    parser = create_parser()
    args = parser.parse_args()
    
    # -- Resolve mesh path -----------------------------------------------------
    mesh_path_raw = args.mesh or args.mesh_positional
    if not mesh_path_raw:
        parser.error(
            "Mesh file required.  Supply via -m/--mesh or as the first "
            "positional argument."
        )
    mesh_path = Path(mesh_path_raw).expanduser().resolve()
    
    # -- Resolve Charnock coefficient ------------------------------------------
    alpha_c = (args.charnock if args.charnock is not None
               else args.charnock_positional if args.charnock_positional is not None
               else 0.028)

    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # -- 1. Read mesh (always needed) ------------------------------------------
    print(f"Reading mesh: {mesh_path.name}")
    file_rdr  = ptt.FileReader()
    mesh      = file_rdr.read_file(str(mesh_path.parent), mesh_path.name)
    processor = ptt.MeshDataProcessor(mesh)
    cell_lon, cell_lat, _ = processor.cell_centers_array.T
    nb_ele2d = processor.num_cells

    print(f"      {nb_ele2d:,} triangle cells  "
          f"(lon [{cell_lon.min():.2f}, {cell_lon.max():.2f}]  "
          f"lat [{cell_lat.min():.2f}, {cell_lat.max():.2f}])")
    
    # Only spin up a distributed LocalCluster when parallelism is actually
    # requested.  For --workers 1 the synchronous scheduler is faster because
    # it has zero scheduling overhead and no serialisation round-trips.
    client = None
    if args.workers > 1 and not args.synthetic:
        from dask.distributed import LocalCluster, Client
        cluster = LocalCluster(n_workers=args.workers, threads_per_worker=1)
        client  = Client(cluster)
        print(f"Dask dashboard: {client.dashboard_link}")
    
    
    # =========================================================================
    #  SYNTHETIC MODE
    # =========================================================================
    if args.synthetic:
        # -- validate synthetic-specific arguments -----------------------------
        if args.t_start is None:
            parser.error("--t_start is required with --synthetic.")
        if args.t_stop is None and args.duration is None:
            parser.error("Provide either --t_stop or --duration with --synthetic.")

        # Derive t_stop from duration if needed
        if args.t_stop:
            t_stop_str = args.t_stop
        else:
            t0_np  = np.datetime64(args.t_start, 's')
            t_stop = t0_np + np.timedelta64(int(args.duration * 3600), 's')
            t_stop_str = str(t_stop)

        print("Generating synthetic forcing …")
        print(f"      direction={args.direction}°  wind={args.wind} m/s  "
              f"pressure={args.pressure} Pa")
        print(f"      {args.t_start}  ->  {t_stop_str}  "
              f"(dt={args.dt} h, ramp={args.t_ramp} h)")

        records, jul_times, min_vals, max_vals, times = generate_synthetic_forcing(
            nb_ele2d   = nb_ele2d,
            direction  = args.direction,
            wind_speed = args.wind,
            pressure   = args.pressure,
            t_start    = args.t_start,
            t_stop     = t_stop_str,
            dt_hours   = args.dt,
            t_ramp_h   = args.t_ramp,
            alpha_c    = alpha_c,
        )
        n_times = len(times)
        print(f"      {n_times} time steps generated.")

        print("Writing output files …")

    # =========================================================================
    #  GRIB MODE  (with lazy dask loading + parallel processing)
    # =========================================================================
    else:
        grib_path_raw = args.grib or getattr(args, 'grib_positional', None)
        if not grib_path_raw:
            parser.error(
                "GRIB file required in non-synthetic mode.  Supply via "
                "-g/--grib or as the second positional argument."
            )
        grib_path = Path(grib_path_raw).expanduser().resolve()

        # -- 2. Open GRIB lazily – single scan for all three variables --------
        chunks    = {"time": args.time_chunk}
        index_dir = str(grib_path.parent / ".grib_index")   # writable cache dir
        print(f"Opening GRIB (lazy, chunk={args.time_chunk} step(s)): "
              f"{grib_path.name}")

        grib_vars = open_grib_variables(
            str(grib_path),
            short_names=["10u", "10v", "msl"],
            chunks=chunks,
            index_dir=index_dir,
        )

        da_u, grib_lats, grib_lons = prepare_grib_coords(grib_vars["10u"])
        da_v, _, _                 = prepare_grib_coords(grib_vars["10v"])
        da_p, _, _                 = prepare_grib_coords(grib_vars["msl"])

        time_dim = next(d for d in da_u.dims if "time" in d)
        times    = da_u[time_dim].values
        n_times  = len(times)
        print(f"      {n_times} time steps  "
              f"({np.datetime_as_string(times[0], unit='h')} -> "
              f"{np.datetime_as_string(times[-1], unit='h')})")

        # -- 3. Build dask task graph ------------------------------------------
        query_pts       = np.column_stack([cell_lat, cell_lon])
        process_delayed = dask.delayed(process_one_step)

        print(f"Building dask task graph ({n_times} delayed tasks) …")
        tasks = [
            process_delayed(
                da_u.isel(**{time_dim: it}).data,
                da_v.isel(**{time_dim: it}).data,
                da_p.isel(**{time_dim: it}).data,
                grib_lats, grib_lons, query_pts, alpha_c,
            )
            for it in range(n_times)
        ]

        # -- 4. Execute --------------------------------------------------------
        if client is not None:
            # Distributed scheduler via LocalCluster (workers > 1)
            print(f"Computing {n_times} steps via distributed scheduler "
                  f"({args.workers} workers) …")
            futures    = client.compute(tasks)
            all_results = client.gather(futures)
        else:
            # Single worker: synchronous scheduler, zero overhead
            print(f"Computing {n_times} steps (synchronous, 1 worker) …")
            all_results = dask.compute(*tasks, scheduler="synchronous")

        # -- Assemble records dict from list-of-dicts --------------------------
        records   = {v: [] for v in VARS}
        jul_times = []
        min_vals  = {v: [] for v in VARS}
        max_vals  = {v: [] for v in VARS}

        for it, step_result in enumerate(all_results):
            jul_times.append(to_cnes_julian(times[it]))
            for var in VARS:
                data = step_result[var]
                records[var].append(data)
                min_vals[var].append(float(data.min()))
                max_vals[var].append(float(data.max()))

            if (it + 1) % max(1, n_times // 10) == 0 or it == n_times - 1:
                print(f"      assembled step {it+1:4d}/{n_times}  "
                      f"jul={jul_times[-1]:.4f}")

        print("Writing output files …")

    # =========================================================================
    #  5. Write .a / .b output files  (identical for both modes)
    # =========================================================================
    for var in VARS:
        a_path = output_dir / f"forcing.{var}.a"
        b_path = output_dir / f"forcing.{var}.b"
        write_forcing_a(a_path, records[var])
        write_forcing_b(b_path, var, nb_ele2d,
                        jul_times, min_vals[var], max_vals[var])
        size_mb = a_path.stat().st_size / 1e6
        print(f"  OK  {a_path.name}  ({size_mb:.1f} MB)  +  {b_path.name}")

    print("Done.")


if __name__ == "__main__":
    main()