#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 09:59:19 2026

@author: llsaisset

Mesh check tool: reads a .msh file and reports floating, duplicate, and
degenerate elements without modifying anything.

Usage:
    python check_mesh.py --input_mesh my_file.msh
    python check_mesh.py --input_mesh my_file.msh -v
"""

import sys
import os

# --- Path setup --------------------------------------------------------------
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
            "Read a .msh mesh file and report floating, duplicate, and "
            "degenerate elements. No file is written."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python check_mesh.py --input_mesh my_file.msh\n"
            "  python check_mesh.py --input_mesh my_file.msh -v\n"
        ),
    )

    parser.add_argument(
        "--input_mesh",
        type=str,
        required=True,
        help="Path to the .msh mesh file to check.",
    )

    parser.add_argument(
        "--workdir", "-w",
        type=str,
        default=None,
        help="Working directory (default: current directory).",
    )

    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=10.0,
        help="Minimum angle (degrees) below which a cell is flagged as distorted (default: 10.0).",
    )

    parser.add_argument(
        "--min_reso", "-r",
        type=float,
        default=0.1,
        help="Minimum mean edge length below which a cell is flagged as too small (default: 0.1).",
    )

    parser.add_argument(
        "--numbering", "-n",
        type=str,
        default='meshio',
        help="Numbering method of mesh elements either meshio or gmsh (default: meshio).",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-check timing information.",
    )

    return parser


# =============================================================================
# DISPLAY HELPER
# =============================================================================

ISSUE_LABELS = {
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
    "distorted_cells":   "Distorted cells",
    "clockwise_cells":   "Clockwise cells",
    "small_cells":       "Small cells",
    "missing_bnd":       "Missing boundary edges",
    "bottleneck_cells":  "Bottleneck cells",
}

def print_issues(issues: dict) -> bool:
    """
    Pretty-print check results grouped by category.
    Returns True if at least one issue was found.
    """
    groups = {
        "Floating elements":   ["floating_nodes",   "floating_vertexes",
                                "floating_lines",    "floating_cells"],
        "Duplicate elements":  ["duplicate_nodes",   "duplicate_vertexes",
                                "duplicate_lines",   "duplicate_cells"],
        "Degenerate elements": ["degenerate_line",   "degenerate_cells"],
        "Cell quality":        ["distorted_cells",   "clockwise_cells",
                                "small_cells"],
        "Boundary":            ["missing_bnd",       "bottleneck_cells"],
    }

    any_issue = False

    for group_title, keys in groups.items():
        ptt.p_ok(f"{group_title}:")
        for key in keys:
            arr   = issues.get(key, np.array([]))
            n     = len(arr)
            label = ISSUE_LABELS.get(key, key)
            if n:
                any_issue = True
                sample = arr[:10]
                suffix = " ..." if n > 10 else ""
                ptt.p_warning(f"    {label:<25}: found {n} (e.g. {sample}{suffix})")
            else:
                ptt.p_ok(f"    {label:<25}: none")

    return any_issue


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n--- Parse arguments ---")
    parser  = create_parser()
    args    = parser.parse_args()
    verbose   = args.verbose
    threshold = args.threshold
    numbering = args.numbering
    min_reso  = args.min_reso

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

    # ------------------------------------------------------------------
    # Resolve and verify input path
    # ------------------------------------------------------------------
    input_mesh = Path(args.input_mesh)
    if not input_mesh.is_absolute():
        input_mesh = current_path / input_mesh

    if not input_mesh.exists():
        ptt.p_error(f"No such file: {input_mesh}")
        sys.exit(1)

    ptt.p_ok(f"Checking file: {input_mesh}")

    # ------------------------------------------------------------------
    # Read mesh
    # ------------------------------------------------------------------
    print("\n--- Read File ---")
    file_rdr = ptt.FileReader()
    with ptt.p_timer("Reading mesh", verbose=verbose):
        mesh = file_rdr.read_file(input_mesh.parent, input_mesh.name)

    with ptt.p_timer("Building mesh processor", verbose=verbose):
        processor = ptt.MeshDataProcessor(mesh)

    ptt.p_ok(
        f"Mesh summary: {processor.num_points} nodes, "
        f"{processor.num_cells} triangles, "
        f"{processor.num_lines} lines, "
        f"{processor.num_vertexes} vertexes."
    )
    ptt.p_ok(f"Check parameters: threshold={threshold}°, min_reso={min_reso}")

    # ------------------------------------------------------------------
    # Run checks
    # ------------------------------------------------------------------
    print("\n--- Check results ---")
    with ptt.p_timer("Running checks", verbose=verbose):
        issues = processor.check_validity(threshold=threshold,
                                          min_reso=min_reso,
                                          numbering=numbering,
                                          verbose=verbose)

    any_issue = print_issues(issues)

    # ------------------------------------------------------------------
    # Summary line
    # ------------------------------------------------------------------
    print("\n--- Summary ---")
    if any_issue:
        ptt.p_warning("  Issues found — run correct_mesh.py to remove them.")
    else:
        ptt.p_ok("  Mesh is clean — no issues found.")

    print("\n")
    
if __name__ == "__main__":
    main()