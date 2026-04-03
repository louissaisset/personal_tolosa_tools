#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 09:59:19 2026

@author: llsaisset

Mesh correction tool: removes duplicate and degenerate elements from a .msh file.

Usage:
    python correct_mesh.py --input_mesh my_file.msh
    python correct_mesh.py --input_mesh my_file.msh --save_in my_file_fixed.msh -v
"""

import sys
import os

# --- Path setup (mirrors the reference tool) ---------------------------------
if os.uname()[1].startswith('belenos'):
    path_tolosa_path = "~/SAVE/DATA/Scripts/personal_tolosa_tools/"
else:
    path_tolosa_path = "~/DATA/Scripts/personal_tolosa_tools/"
os.environ['PATH'] += os.pathsep + os.path.expanduser(f'{path_tolosa_path}/scripts/tools/')
sys.path.append(os.path.expanduser(path_tolosa_path))
import personal_tolosa_tools as ptt

import argparse
from pathlib import Path
import numpy as np


# =============================================================================
# ARGUMENT PARSER
# =============================================================================

def create_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Cleans a Tolosa/gmsh .msh file by removing duplicate and "
            "degenerate nodes, lines, and triangular cells, then saves the "
            "corrected mesh."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python correct_mesh.py --input_mesh my_file.msh\n"
            "  python correct_mesh.py --input_mesh my_file.msh "
            "--save_in my_file_fixed.msh -v\n"
        ),
    )

    parser.add_argument(
        "--input_mesh",
        type=str,
        required=True,
        help="Path to the input .msh mesh file to correct.",
    )

    parser.add_argument(
        "--save_in", "-s",
        type=str,
        default="",
        help=(
            "Path / filename for the corrected output mesh. "
            "Defaults to <input_stem>_corrected.msh next to the input file."
        ),
    )

    parser.add_argument(
        "--workdir", "-w",
        type=str,
        default=None,
        help="Working directory (default: current directory).",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed progress information.",
    )

    return parser


# =============================================================================
# HELPERS
# =============================================================================

def checkfile(file: Path) -> bool:
    if file.exists():
        ptt.p_ok(f"Found file: {file}")
        return True
    else:
        ptt.p_error(f"No such file: {file}")
        return False


def _print_issues(issues: dict) -> bool:
    """Pretty-print the check results. Returns True if any issue was found."""
    any_issue = False
    labels = {
        "floating_nodes":    "Floating nodes",
        "floating_vertexes": "Floating vertexes",
        "floating_lines":    "Floating lines",
        "floating_cells":    "Floating cells",
        "duplicate_nodes":   "Duplicate nodes",
        "duplicate_vertexes":"Duplicate vertexes",
        "duplicate_lines":   "Duplicate lines",
        "duplicate_cells":   "Duplicate cells",
        "degenerate_line":   "Degenerate lines",
        "degenerate_cells":  "Degenerate cells", 
        "clockwise_cells":   "Clockwise cells",
    }
    for key, label in labels.items():
        arr = issues.get(key, np.array([]))
        n   = len(arr)
        if n:
            any_issue = True
            ptt.p_warning(f"  {label}: {n} found  ->  indices {arr[:10]}"
                          + (" ..." if n > 10 else ""))
        else:
            ptt.p_ok(f"  {label}: none")
    if not any_issue:
        ptt.p_ok("  Mesh is clean — nothing to remove.")
    return any_issue


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n--- Parse arguments ---")
    parser = create_parser()
    args   = parser.parse_args()
    verbose = args.verbose

    # ------------------------------------------------------------------
    # Working directory
    # ------------------------------------------------------------------
    if args.workdir:
        current_path = Path(args.workdir).absolute()
        if not current_path.exists() or not current_path.is_dir():
            ptt.p_error(f"Working directory is invalid: {current_path}")
            sys.exit(1)
    else:
        current_path = Path.cwd()

    ptt.p_ok(f"Working directory: {current_path}")

    # ------------------------------------------------------------------
    # Resolve input mesh path
    # ------------------------------------------------------------------
    input_mesh = Path(args.input_mesh)
    if not input_mesh.is_absolute():
        input_mesh = current_path / input_mesh

    if not checkfile(input_mesh):
        sys.exit(1)

    # ------------------------------------------------------------------
    # Read mesh
    # ------------------------------------------------------------------
    file_rdr = ptt.FileReader()
    with ptt.p_timer(f"Reading mesh: {input_mesh.name}", verbose=verbose):
        mesh = file_rdr.read_file(input_mesh.parent, input_mesh.name)

    with ptt.p_timer("Building mesh processor", verbose=verbose):
        processor = ptt.MeshDataProcessor(mesh)

    ptt.p_ok(
        f"Mesh loaded — {processor.num_points} nodes, "
        f"{processor.num_cells} triangles, "
        f"{processor.num_lines} lines, "
        f"{processor.num_vertexes} vertexes."
    )

    # ------------------------------------------------------------------
    # Check for floating / duplicate / degenerate elements
    # ------------------------------------------------------------------
    print("\n--- Validity check (before correction) ---")
    with ptt.p_timer("Running checks", verbose=verbose):
        issues = processor.check_float_dupli_degen(numbering='meshio', 
                                                   verbose=verbose)

    any_issue = _print_issues(issues)

    if not any_issue:
        ptt.p_ok("Nothing to correct — exiting without writing a new file.")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Collect indices to remove
    # ------------------------------------------------------------------
    node_indices   = issues.get("duplicate_nodes",    np.array([], dtype=int))
    cell_indices   = np.unique(np.concatenate([
                         issues.get("duplicate_cells",   np.array([], dtype=int)),
                         issues.get("degenerate_cells",  np.array([], dtype=int)),
                     ]))
    line_indices   = np.unique(np.concatenate([
                         issues.get("duplicate_lines",   np.array([], dtype=int)),
                         issues.get("degenerate_line",   np.array([], dtype=int)),
                     ]))
    vertex_indices = issues.get("duplicate_vertexes", np.array([], dtype=int))

    print("\n--- Removing problematic elements ---")
    if verbose:
        ptt.p_ok(f"  Nodes to remove   : {len(node_indices)}")
        ptt.p_ok(f"  Cells to remove   : {len(cell_indices)}")
        ptt.p_ok(f"  Lines to remove   : {len(line_indices)}")
        ptt.p_ok(f"  Vertexes to remove: {len(vertex_indices)}")

    with ptt.p_timer("Removing elements", verbose=verbose):
        corrected = processor.remove_elements_clean(
            node_indices   = node_indices   if len(node_indices)   else None,
            cell_indices   = cell_indices   if len(cell_indices)   else None,
            line_indices   = line_indices   if len(line_indices)   else None,
            vertex_indices = vertex_indices if len(vertex_indices) else None,
        )

    ptt.p_ok(
        f"Corrected mesh — {corrected.num_points} nodes "
        f"({processor.num_points - corrected.num_points:+d}), "
        f"{corrected.num_cells} triangles "
        f"({processor.num_cells - corrected.num_cells:+d}), "
        f"{corrected.num_lines} lines "
        f"({processor.num_lines - corrected.num_lines:+d})."
    )
    # ------------------------------------------------------------------
    # Fix cell orientation (clockwise -> counter-clockwise)
    # ------------------------------------------------------------------
    print("\n--- Correcting cell orientation ---")
    # Re-check on the corrected mesh: some clockwise cells may have been
    # removed in the previous step (degenerate / duplicate), so we recompute
    # to avoid swapping non-existent indices.
    with ptt.p_timer("Re-checking orientation after removal", verbose=verbose):
        clockwise_cells = corrected.check_triangle_orientation()
 
    if len(clockwise_cells):
        with ptt.p_timer("Swapping orientation", verbose=verbose):
            corrected = corrected.swap_orientation(clockwise_cells)
        ptt.p_ok(f"  {len(clockwise_cells)} cell(s) reoriented counter-clockwise.")
    else:
        ptt.p_ok("--- Orientation: all cells already counter-clockwise ---")
        
    # ------------------------------------------------------------------
    # Quick post-correction check
    # ------------------------------------------------------------------
    print("\n--- Validity check (after correction) ---")
    with ptt.p_timer("Running post-correction checks", verbose=verbose):
        issues_after = corrected.check_float_dupli_degen(verbose=verbose)
    _print_issues(issues_after)

    # ------------------------------------------------------------------
    # Resolve output path
    # ------------------------------------------------------------------
    if args.save_in:
        save_in = Path(args.save_in)
        if not save_in.is_absolute():
            save_in = current_path / save_in
    else:
        stem    = ".".join(input_mesh.name.split(".")[:-1])
        save_in = input_mesh.parent / f"{stem}_corrected.msh"

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    with ptt.p_timer(f"Saving corrected mesh to: {save_in}", verbose=verbose):
        corrected.save_mesh(
            path        = str(save_in.parent),
            filename    = save_in.name,
            file_format = "tolosa",
        )

    print(f"\nDone. Corrected mesh written to: {save_in}\n")


if __name__ == "__main__":
    main()