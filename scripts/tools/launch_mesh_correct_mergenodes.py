#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 23 09:59:19 2026

@author: llsaisset
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
import numpy as np


def create_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Read a .msh mesh file, merge specified nodes, "
            "and save the corrected mesh in Tolosa format."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python correct_mesh.py --input_mesh my_file.msh --nodes 2836 2838 2836 2838 2850 2851 5033 5226\n"
            "  python correct_mesh.py --input_mesh my_file.msh --nodes 2836 2838 -n gmsh -v\n"
        ),
    )

    parser.add_argument(
        "--input_mesh",
        type=str,
        required=True,
        help="Path to the .msh mesh file to correct.",
    )

    parser.add_argument(
        "--workdir", "-w",
        type=str,
        default=None,
        help="Working directory (default: directory of the input mesh file).",
    )

    parser.add_argument(
        "--nodes", "-N",
        type=int,
        nargs="+",
        required=True,
        help=(
            "Flat list of node pairs to merge, given as a sequence of integers. "
            "Must contain an even number of values, each consecutive pair (a, b) "
            "defines one merge operation. "
            "Example: --nodes 2836 2838 2850 2851"
        ),
    )

    parser.add_argument(
        "--numbering", "-n",
        type=str,
        default="meshio",
        choices=["meshio", "gmsh"],
        help="Numbering convention of mesh node indices (default: meshio).",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print per-step timing information.",
    )

    return parser


def parse_merge_nodes(flat_list):
    """Convert a flat list of integers into an (N, 2) numpy array of node pairs."""
    if len(flat_list) % 2 != 0:
        raise ValueError(
            f"--nodes requires an even number of values; got {len(flat_list)}."
        )
    arr = np.array(flat_list, dtype=int).reshape(-1, 2)
    return arr


def build_output_filename(input_mesh):
    """Append '_mergenodes' before the file extension of the input mesh filename."""
    base, ext = os.path.splitext(os.path.basename(input_mesh))
    return f"{base}_mergenodes{ext}"


def main():
    parser = create_parser()
    args = parser.parse_args()

    # Resolve working directory
    if args.workdir is not None:
        path = args.workdir
    else:
        path = os.path.dirname(os.path.abspath(args.input_mesh))

    file_mesh = os.path.basename(args.input_mesh)

    # Parse and validate the merge-node pairs
    try:
        nodes = parse_merge_nodes(args.nodes)
    except ValueError as exc:
        parser.error(str(exc))

    # Read the mesh
    file_rdr = ptt.FileReader()
    with ptt.p_timer("Reading the mesh file", verbose=args.verbose):
        mesh = file_rdr.read_file(path, file_mesh)

    # Build the processor and merge nodes
    with ptt.p_timer("Creating the processor for the initial mesh", verbose=args.verbose):
        processor = ptt.MeshDataProcessor(mesh)

    p = processor.merge_nodes(nodes, numbering=args.numbering)

    # Save the corrected mesh
    new_file_mesh = build_output_filename(file_mesh)
    with ptt.p_timer("Save the new mesh", verbose=args.verbose):
        p.save_mesh(path, new_file_mesh, file_format="tolosa")

    if args.verbose:
        print(f"Corrected mesh saved to: {os.path.join(path, new_file_mesh)}")


if __name__ == "__main__":
    main()