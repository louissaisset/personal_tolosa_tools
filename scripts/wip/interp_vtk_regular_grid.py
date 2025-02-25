#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Feb 21 13:56:34 2025

@author: llsaisset
"""


import sys
sys.path.append("/local/home/lsaisset/DATA/Scripts/personal_tolosa_tools/")
import personal_tolosa_tools as ptt

import numpy as np
from pathlib import Path
import copy
import matplotlib.pyplot as plt

# Define paths to the VTK folders and output folder
# folder_path = Path("/local/home/lsaisset/DATA/tests_persos/Comparaison/version_datarmor/res/vtk/")
folder_path = Path("/local/home/lsaisset/DATA/Configs_Brest/Tests_versions_meshtool/BC_0_constraint_all_algo_6_smoothing_00050m")


timestep = 0
reader = ptt.VTKDataReader(folder_path)
data = reader.read_file(timestep)
processor = ptt.VTKDataProcessor(data)



xmin, xmax, ymin, ymax = processor.get_data_lims()

xmin, xmax, ymin, ymax = -18000, -12000, -8000, -4000
xreso = 100
yreso = 50

x = np.arange(xmin, xmax, xreso)
y = np.arange(ymin, ymax, yreso)

X, Y = np.meshgrid(x, y)

largest_boundary, index_largest_boundary = processor.calculate_largest_boundary()
other_boundaries = copy.deepcopy(processor.boundary_list)
other_boundaries.pop(index_largest_boundary)

mask = processor.compute_masks_for_paths(X, Y, 
                                         inside_paths=largest_boundary,
                                         outside_paths=other_boundaries)
complete_mask = mask['inside'] & mask['outside']


# data_key = 'ssh'
data_key = 'bathy'
interpolated_value = processor.compute_interpolation_masked_grid(processor.cell_centers_array[:,0], 
                                                                 processor.cell_centers_array[:,1],
                                                                 processor.cell_data[data_key],
                                                                 X, Y,
                                                                 mask=complete_mask,
                                                                 method='linear'
                                                                 )

tripcolor_tri, _ = processor.compute_triangulations()





fig, ax = plt.subplots(1, 1, dpi=300)
# ax.set_xlim(-10000, -5000)
# ax.set_ylim(-5000, 0)
# ax.set_xlim(-18000, -12000)
# ax.set_ylim(-8000, -4000)
ax.set_aspect(1)
plt.tripcolor(tripcolor_tri, processor.cell_data[data_key])

# ax.plot(processor.edgepoints_array[:,0],
#          processor.edgepoints_array[:,1],
#          '+r')

ax.plot(largest_boundary[:,0], 
         largest_boundary[:,1], '-b')

# ax.pcolormesh(X, Y, interpolated_value)


# plt.triplot(tripcolor_tri)

ax.grid()
plt.show()






