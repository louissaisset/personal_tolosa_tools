#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Mar 16 15:05:39 2026

@author: llsaisset
"""


import sys
import shutil
import argparse
import subprocess
from pathlib import Path


TOOLS = ["create_mesh", "bathy_smooth", "regional_grid", "diagnostic"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wrapper for 'python3 -m meshtool'.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "yaml_file",
        type=Path,
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "shp_file",
        type=Path,
        help="Path to the primary shapefile (.shp). "
             "Companion files are derived from this path unless overridden.",
    )
    parser.add_argument(
        "bathy_file_MSL",
        type=Path,
        help="Path to the bathymetry file.",
    )
    parser.add_argument(
        "--tool", "-t",
        required=True,
        nargs="+",
        choices=TOOLS + ["all"],
        metavar="TOOL",
        help=(
            "One or more tools to run in sequence: "
            + ", ".join(TOOLS)
            + ", or 'all' to run all of them. "
            "Example: --tool bathy_smooth regional_grid diagnostic"
        ),
    )
    parser.add_argument(
        "--msh_file",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Path to the mesh file (.msh). "
            "Defaults to <shp_file_stem>.msh in the shapefile directory."
        ),
    )
    parser.add_argument(
        "--proj_bathy_file",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Path to the projected bathymetry file (.a). "
            "Defaults to regional.depth-ele.a in the shapefile directory."
        ),
    )
    parser.add_argument(
        "--shp_file_interior",
        type=Path,
        default=None,
        metavar="FILE",
        help=(
            "Path to the interior shapefile (.shp). "
            "When provided, the INTER/EXTER auto-detection is skipped entirely."
        ),
    )
    parser.add_argument(
        "--output_dir", "-o",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "Directory where output files are moved "
            "(default: current working directory). "
            "Has no effect when --no_move is set."
        ),
    )
    parser.add_argument(
        "--no_move",
        action="store_true",
        help=(
            "Do not move output files after the run. "
            "Files remain in the shapefile directory."
        ),
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Per-tool expected output helpers
# ---------------------------------------------------------------------------

def _tool_output_spec(tool: str, stem: str) -> tuple[list[str], list[str]]:
    """
    Return (exact_names, glob_patterns) describing the expected outputs of
    *tool* for a shapefile whose stem is *stem*.

    Both lists contain bare filenames / patterns, not full paths — they are
    resolved against shp_dir by the callers below.

    Expected outputs per tool
    -------------------------
    create_mesh    : <stem>.msh
    bathy_smooth   : bathy_smooth_*.nc  |  regional.depth-*
    regional_grid  : <stem>_latlong.msh  |  regional.grid-*
    diagnostic     : <stem>_diag.vtk
    """
    if tool == "create_mesh":
        return ([f"{stem}.msh"], [])
    elif tool == "bathy_smooth":
        return ([], ["bathy_smooth_*.nc", "regional.depth-*"])
    elif tool == "regional_grid":
        return ([f"{stem}_latlong.msh"], ["regional.grid-*"])
    elif tool == "diagnostic":
        return ([f"{stem}_diag.vtk"], [])
    return ([], [])


def resolve_expected_files(tools: list[str],
                           shp_dir: Path,
                           stem: str) -> list[Path]:
    """
    Collect every file in *shp_dir* that currently exists on disk and matches
    the expected output spec of any tool in *tools*.
    """
    found: list[Path] = []
    seen: set[Path] = set()

    for tool in tools:
        exact_names, patterns = _tool_output_spec(tool, stem)

        for name in exact_names:
            p = shp_dir / name
            if p.exists() and p not in seen:
                found.append(p)
                seen.add(p)

        for pattern in patterns:
            for p in sorted(shp_dir.glob(pattern)):
                if p not in seen:
                    found.append(p)
                    seen.add(p)

    return found


def warn_preexisting(files: list[Path]) -> None:
    """Print a warning for each file that already existed before the run."""
    if not files:
        return
    print(f"\n  WARNING: {len(files)} expected output file(s) already exist "
          "and will be moved to the output directory:")
    for f in files:
        print(f"  [!] {f}")


def move_outputs(files: list[Path], destination: Path) -> None:
    """Move *files* to *destination*, printing each action."""
    if not files:
        print("  (no output files to move)")
        return

    for src in files:
        dst = destination / src.name
        # Avoid clobbering: append a counter suffix when needed
        if dst.exists() and dst != src:
            base, suffix = dst.stem, dst.suffix
            counter = 1
            while dst.exists():
                dst = destination / f"{base}_{counter}{suffix}"
                counter += 1
        print(f"  Move : {src} -> {dst}")
        shutil.move(str(src), str(dst))


# ---------------------------------------------------------------------------
# Command building & execution
# ---------------------------------------------------------------------------

def build_command(tool: str,
                  yaml_file: Path,
                  bathy_file_MSL: Path,
                  shp_file: Path,
                  msh_file: Path,
                  proj_bathy_file: Path,
                  shp_file_interior: Path | None) -> list[str]:
    """Assemble the full python3 -m meshtool … command."""
    cmd = [
        sys.executable, "-m", "meshtool",
        str(yaml_file),
        "-tool", tool,
        "-bathy_file_MSL", str(bathy_file_MSL),
        "-shp_file", str(shp_file),
        "-msh_file", str(msh_file),
        "-projBathyFile", str(proj_bathy_file),
    ]
    if shp_file_interior is not None:
        cmd += ["-shp_file_interior", str(shp_file_interior)]
    else:
        cmd += ["-shp_file_interior", "None"]
    return cmd


def run_tool(tool: str,
             yaml_file: Path,
             bathy_file_MSL: Path,
             shp_file: Path,
             msh_file: Path,
             proj_bathy_file: Path,
             shp_file_interior: Path | None) -> int:
    """Run a single meshtool tool."""

    print(f"\n{'='*60}")
    print(f"  Tool : {tool}")
    print(f"{'='*60}")

    cmd = build_command(tool, yaml_file, bathy_file_MSL, shp_file, msh_file,
                        proj_bathy_file, shp_file_interior)

    print("  Command:", " ".join(cmd))

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"\n  ERROR: meshtool exited with code {result.returncode}")
        return result.returncode

    return 0


# ---------------------------------------------------------------------------
# Shapefile INTER / EXTER detection
# ---------------------------------------------------------------------------

def transform_INTER_EXTER(chemin_original: Path) -> tuple[Path, Path | None]:
    """
    Derives the exterior/interior shapefile pair from a single path.

    - If the filename contains 'INTER', it is treated as the interior file;
      the corresponding exterior file is derived by replacing 'INTER' with
      'EXTER'.
    - If the filename contains 'EXTER', it is already the exterior file and
      no interior file is used.
    - Otherwise returns (None, None).
    """
    chemin = Path(chemin_original)
    parties = chemin.name.split('_')

    if 'INTER' in parties:
        index_inter = parties.index('INTER')
        parties[index_inter] = 'EXTER'
        nouveau_nom = '_'.join(parties[:index_inter + 2]) + '_stereo.shp'
        return chemin.parent / nouveau_nom, chemin_original

    elif 'EXTER' in parties:
        return chemin_original, None

    else:
        return None, None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:

    args = parse_args()

    # ---- Resolve tools list -----------------------------------------------

    if "all" in args.tool:
        tools_to_run = TOOLS
    else:
        seen_tools: set[str] = set()
        tools_to_run = []
        for t in args.tool:
            if t not in seen_tools:
                tools_to_run.append(t)
                seen_tools.add(t)

    # ---- Resolve mandatory paths ------------------------------------------

    bathy_file_MSL: Path = args.bathy_file_MSL.resolve()
    yaml_file: Path      = args.yaml_file.resolve()
    raw_shp_file: Path   = args.shp_file.resolve()

    if not yaml_file.exists():
        print(f"ERROR: YAML file not found: {yaml_file}")
        return 1
    if not bathy_file_MSL.exists():
        print(f"ERROR: Bathymetry file not found: {bathy_file_MSL}")
        return 1
    if not raw_shp_file.exists():
        print(f"ERROR: Shapefile not found: {raw_shp_file}")
        return 1

    # ---- Resolve shp_file / shp_file_interior -----------------------------

    if args.shp_file_interior is not None:
        # Explicit interior file provided — skip INTER/EXTER detection.
        shp_file          = raw_shp_file
        shp_file_interior = args.shp_file_interior.resolve()
        if not shp_file_interior.exists():
            print(f"ERROR: Interior shapefile not found: {shp_file_interior}")
            return 1
    else:
        shp_file, shp_file_interior = transform_INTER_EXTER(raw_shp_file)
        if shp_file is None:
            print(
                "ERROR: Could not derive exterior shapefile from "
                f"'{raw_shp_file}'. "
                "The filename must contain 'INTER' or 'EXTER', "
                "or pass --shp_file_interior explicitly."
            )
            return 1

    shp_dir: Path = shp_file.parent
    stem: str     = shp_file.stem

    # ---- Resolve optional companion files ---------------------------------

    msh_file: Path = (
        args.msh_file.resolve()
        if args.msh_file is not None
        else shp_dir / f"{stem}.msh"
    )
    proj_bathy_file: Path = (
        args.proj_bathy_file.resolve()
        if args.proj_bathy_file is not None
        else shp_dir / "regional.depth-ele.a"
    )

    # ---- Output destination -----------------------------------------------

    output_dir: Path = (
        args.output_dir.resolve()
        if args.output_dir
        else Path.cwd()
    )
    if not args.no_move:
        output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Summary ----------------------------------------------------------

    print("meshtool wrapper")
    print("----------------")
    print(f"  Tool(s)            : {', '.join(tools_to_run)}")
    print(f"  YAML file          : {yaml_file}")
    print(f"  TIF file           : {bathy_file_MSL}")
    print(f"  shp_file           : {shp_file}")
    print(f"  shp_file_interior  : {shp_file_interior or '(none)'}")
    print(f"  msh_file           : {msh_file}")
    print(f"  projBathyFile      : {proj_bathy_file}")
    if args.no_move:
        print(f"  Output dir         : (not moving — files stay in {shp_dir})")
    else:
        print(f"  Output dir         : {output_dir}")

    # ---- Pre-run: warn about already-existing expected outputs ------------

    preexisting = resolve_expected_files(tools_to_run, shp_dir, stem)
    warn_preexisting(preexisting)

    # ---- Run tools --------------------------------------------------------

    overall_rc = 0

    for tool in tools_to_run:
        rc = run_tool(
            tool=tool,
            yaml_file=yaml_file,
            bathy_file_MSL=bathy_file_MSL,
            shp_file=shp_file,
            msh_file=msh_file,
            proj_bathy_file=proj_bathy_file,
            shp_file_interior=shp_file_interior,
        )
        if rc != 0:
            overall_rc = rc
            print(f"\n  Aborted: tool '{tool}' failed (exit code {rc}).")
            break

    # ---- Collect and move expected outputs --------------------------------

    outputs = resolve_expected_files(tools_to_run, shp_dir, stem)

    print(f"\n  Output files detected ({len(outputs)}):")
    if args.no_move:
        for f in outputs:
            print(f"  (kept) {f}")
        if not outputs:
            print("  (no output files detected)")
    else:
        move_outputs(outputs, output_dir)

    print(f"\n{'='*60}")
    status = "OK" if overall_rc == 0 else f"FAILED (code {overall_rc})"
    print(f"  Done — {status}")
    print(f"{'='*60}\n")

    return overall_rc


if __name__ == "__main__":
    sys.exit(main())

# #!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# """
# Created on Mon Mar 16 15:05:39 2026

# @author: llsaisset
# """


# import sys, os
# import shutil
# import argparse
# import subprocess
# from pathlib import Path


# TOOLS = ["create_mesh", "bathy_smooth", "regional_grid", "diagnostic"]
# OUTPUT_GLOBS = ["*.msh", "*.a", "*.b", "*.vtk", "*.nc"]


# def parse_args() -> argparse.Namespace:
#     parser = argparse.ArgumentParser(
#         description="Wrapper for 'python3 -m meshtool'.",
#         formatter_class=argparse.RawDescriptionHelpFormatter,
#         epilog=__doc__,
#     )

#     parser.add_argument(
#         "yaml_file",
#         type=Path,
#         help="Path to the YAML configuration file.",
#     )
#     parser.add_argument(
#         "shp_file",
#         type=Path,
#         help="Path to the primary shapefile (.shp). "
#              "Companion files are derived from this path.",
#     )
#     parser.add_argument(
#         "bathy_file_MSL",
#         type=Path,
#         help="Path to the bathymety file. ",
#     )
#     parser.add_argument(
#         "--tool", "-t",
#         required=True,
#         choices=TOOLS + ["all"],
#         metavar="TOOL",
#         help=(
#             "Tool to run: "
#             + ", ".join(TOOLS)
#             + ", or 'all' to run them in sequence."
#         ),
#     )
#     parser.add_argument(
#         "--output_dir", "-o",
#         type=Path,
#         default=None,
#         metavar="DIR",
#         help=(
#             "Directory where output files are moved "
#             "(default: current working directory)."
#         ),
#     )
#     return parser.parse_args()
    
# # ---------------------------------------------------------------------------
# # Helpers
# # ---------------------------------------------------------------------------

# def snapshot(directory: Path) -> dict[Path, float]:
#     """Return a {path: mtime} map for every file under *directory*."""
#     state: dict[Path, float] = {}
#     for root, _, files in os.walk(directory):
#         for fname in files:
#             p = Path(root) / fname
#             try:
#                 state[p] = p.stat().st_mtime
#             except OSError:
#                 pass
#     return state


# def new_output_files(before: dict[Path, float],
#                      after:  dict[Path, float],
#                      globs:  list[str]) -> list[Path]:
#     """
#     Return files that:
#       • did not exist in *before*, OR have a newer mtime in *after*
#       • AND match at least one pattern in *globs*
#     """
#     results: list[Path] = []
#     for path, mtime in after.items():
#         if path not in before or before[path] < mtime:
#             if any(path.match(g) for g in globs):
#                 results.append(path)
#     return sorted(results)


# def move_outputs(files: list[Path], destination: Path) -> None:
#     """Move *files* to *destination*, printing each action."""
#     if not files:
#         print("  (no new output files detected)")
#         return

#     for src in files:
#         dst = destination / src.name
#         # Avoid clobbering: append a counter suffix when needed
#         if dst.exists() and dst != src:
#             stem, suffix = dst.stem, dst.suffix
#             counter = 1
#             while dst.exists():
#                 dst = destination / f"{stem}_{counter}{suffix}"
#                 counter += 1
#         print(f"Move : {str(src)} to {str(dst)}")
#         shutil.move(str(src), str(dst))

# def build_command(tool: str,
#                   yaml_file: Path,
#                   bathy_file_MSL: Path,
#                   shp_file: Path,
#                   msh_file: Path,
#                   proj_bathy_file: Path,
#                   shp_file_interior: Path | None) -> list[str]:
#     """Assemble the full python3 -m meshtool … command."""
#     cmd = [
#         sys.executable, "-m", "meshtool",
#         str(yaml_file),
#         "-tool", tool,
#         "-bathy_file_MSL", str(bathy_file_MSL),
#         "-shp_file", str(shp_file),
#         "-msh_file", str(msh_file),
#         "-projBathyFile", str(proj_bathy_file),
#     ]
#     if shp_file_interior is not None:
#         cmd += ["-shp_file_interior", str(shp_file_interior)]
#     else :
#         cmd += ["-shp_file_interior", "None"]
#     return cmd


# def run_tool(tool: str,
#              yaml_file: Path,
#              bathy_file_MSL: Path,
#              shp_file: Path,
#              msh_file: Path,
#              proj_bathy_file: Path,
#              shp_file_interior: Path | None,
#              output_dir: Path) -> int:
#     """Run a single meshtool tool and move its outputs."""

#     print(f"\n{'='*60}")
#     print(f"  Tool : {tool}")
#     print(f"{'='*60}")

#     cmd = build_command(tool, yaml_file, bathy_file_MSL, shp_file, msh_file,
#                         proj_bathy_file, shp_file_interior)

#     print("  Command:", " ".join(cmd))

    
#     result = subprocess.run(cmd)

#     if result.returncode != 0:
#         print(f"\n  ERROR: meshtool exited with code {result.returncode}")
#         return result.returncode

#     return 0



# def transform_INTER_EXTER(chemin_original):
#     """
#     Transforme un chemin de fichier selon le format spécifié.
    
#     Args:
#         chemin_original (str ou Path): Le chemin original à transformer
        
#     Returns:
#         Path: Le chemin transformé
#     """
#     # Convertir en objet Path si ce n'est pas déjà le cas
#     chemin = Path(chemin_original)
    
#     # Récupérer le nom du fichier
#     nom_fichier = chemin.name
    
#     # Séparer les parties du nom de fichier
#     # Format original: METHODE_X_YYY_ZZZ_smooth_AAm_stereo.shp
#     parties = nom_fichier.split('_')
#     if 'INTER' in parties:
#         # Garder: tout jusqu'à INTER +1 et ajouter _stereo.shp
#         index_smooth = parties.index('INTER')
#         parties[index_smooth] = 'EXTER'
#         nouveau_nom = '_'.join(parties[:index_smooth+2]) + '_stereo.shp'
        
#         # Retourner le chemin avec le nouveau nom
#         shp_file = chemin.parent / nouveau_nom
#         shp_file_interior = chemin_original
#         return shp_file, shp_file_interior
#     elif 'EXTER' in parties:
#         shp_file = chemin_original
#         shp_file_interior = None
#         return shp_file, shp_file_interior
#     else:
#         return None, None
    
    
    

# def main() -> int:
    
#     args = parse_args()

#     # ---- Resolve paths ----------------------------------------------------

#     bathy_file_MSL: Path = args.bathy_file_MSL.resolve()
#     yaml_file: Path = args.yaml_file.resolve()
#     shp_file:  Path = args.shp_file.resolve()
#     shp_dir:   Path = shp_file.parent

#     if not yaml_file.exists():
#         print(f"ERROR: YAML file not found: {yaml_file}")
#         return 1
#     if not bathy_file_MSL.exists():
#         print(f"ERROR: Tif not found: {bathy_file_MSL}")
#         return 1
#     if not shp_file.exists():
#         print(f"ERROR: Shapefile not found: {shp_file}")
#         return 1
    
#     # Correct shp files
#     shp_file, shp_file_interior = transform_INTER_EXTER(args.shp_file)
    
#     # Companion files
#     msh_file: Path = (shp_dir / (shp_file.stem + ".msh"))
#     proj_bathy_file: Path = (shp_dir / "regional.depth-ele.a")
    
#     # Output destination
#     output_dir: Path = (
#         args.output_dir.resolve()
#         if args.output_dir
#         else Path.cwd()
#     )
#     output_dir.mkdir(parents=True, exist_ok=True)

#     # ---- Summary ----------------------------------------------------------

#     print("meshtool wrapper")
#     print("----------------")
#     print(f"  Tool(s)            : {args.tool}")
#     print(f"  YAML file          : {yaml_file}")
#     print(f"  TIF file           : {bathy_file_MSL}")
#     print(f"  shp_file           : {shp_file}")
#     if shp_file_interior:
#         print(f"  shp_file_interior  : {shp_file_interior or '(none)'}")
#     print(f"  msh_file           : {msh_file}")
#     print(f"  projBathyFile      : {proj_bathy_file}")
#     print(f"  Output dir         : {output_dir}")
#     print(f"  Watch dir          : {shp_dir}")

#     # ---- Run tools --------------------------------------------------------

#     tools_to_run = TOOLS if args.tool == "all" else [args.tool]
#     overall_rc = 0
    
#     before = snapshot(shp_dir)
    
#     for tool in tools_to_run:
#         rc = run_tool(
#             tool=tool,
#             yaml_file=yaml_file,
#             bathy_file_MSL=bathy_file_MSL,
#             shp_file=shp_file,
#             msh_file=msh_file,
#             proj_bathy_file=proj_bathy_file,
#             shp_file_interior=shp_file_interior,
#             output_dir=output_dir
#         )
#         if rc != 0:
#             overall_rc = rc
#             print(f"\nAborted: tool '{tool}' failed (exit code {rc}). ")
#             break

#     after = snapshot(shp_dir)
#     outputs = new_output_files(before, after, OUTPUT_GLOBS)

#     print(f"\n  Output files detected ({len(outputs)}):")
#     move_outputs(outputs, output_dir)
    
#     print(f"\n{'='*60}")
#     status = "OK" if overall_rc == 0 else f"FAILED (code {overall_rc})"
#     print(f"  Done — {status}")
#     print(f"{'='*60}\n")

    
    
# if __name__ == "__main__":
#     sys.exit(main())