#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb 25 09:35:54 2025

@author: llsaisset
"""


import sys
sys.path.append("/local/home/lsaisset/DATA/Scripts/personal_tolosa_tools/")
import personal_tolosa_tools as ptt

from pathlib import Path
import numpy as np


# print("    \033[31mERROR:\033[0m 
# print("       \033[32mOK:\033[0m 
# print("  \033[33mWARNING:\033[0m 



start_path = Path("/local/home/lsaisset/DATA/Configs_Brest/Tests_versions_meshtool")

all_folder_meshes = sorted([folder for folder in start_path.iterdir() if folder.is_dir() and folder.name.startswith("BC_")])


resu_points = len(all_folder_meshes)*[0]
resu_cells = len(all_folder_meshes)*[0]
for folder, folder_index in zip(all_folder_meshes, range(len(all_folder_meshes))) :
    
    print(folder.name)
    
    reader = ptt.VTKDataReader(folder)
    vtk_files = [f for f in reader._get_vtk_files() if f.endswith("_diag.vtk")]

    if vtk_files:
        vtk_file = vtk_files[0]
        
        # Read data
        vtk_data = reader.read_file(0)
        
        # Processdata
        processor = ptt.VTKDataProcessor(vtk_data)
        
        resu_points[folder_index] = processor.num_points
        resu_cells[folder_index] = processor.num_cells
    


list_name_folder = [f.name for f in all_folder_meshes]
list_name_BC = list(dict.fromkeys(['_'.join(f.split('_')[0:2]) for f in list_name_folder]))
list_name_cond = list(dict.fromkeys(['_'.join(f.split('_')[2:]) for f in list_name_folder]))

# dictionnaire_dossiers = {'_'.join(nom.split('_')[0:2]): nom for nom in list_name_folder}


tableau = np.full((len(list_name_BC), len(list_name_cond)), None)
for folder, n_cells in zip(list_name_folder, resu_cells):
    BC = '_'.join(folder.split('_')[0:2])
    cond = '_'.join(folder.split('_')[2:])
    # Trouver l'indice du nom et de la valeur
    i = list_name_BC.index(BC)
    j = list_name_cond.index(cond)
    # Ajouter la valeur dans le tableau à la position (i, j)
    tableau[i, j] = n_cells






list_name_BC

list_name_cond

print(' & '.join(map(str, tableau.T[3,:])))


print(' & '.join(map(str, tableau.T[2, :])))

# In[]



times = np.array([[218, 18, 1049, np.nan, np.nan, 16125],
                  [262, 20, 1092, np.nan, np.nan, np.nan],
                  [219, 18, 1068, np.nan, np.nan, 4325],
                  [235, 27, 1058, np.nan, np.nan, 17057],
                  [260, 29, 1105, 9228, 9060, 4033],
                  [252, 30, 1122, 10498, 10462, 4695],
                  [252, 29, 1138, 9465, 9302, 4579],
                  [260, 29, 1105, 9228, 9060, 4033],
                  [324, 67, 1258, 10461, 10303, 5437],
                  [260, 29, 1105, 9228, 9060, 4033],
                  [282, 32, 1103, 7851, 7847, 3757],
                  [244, 32, 1081, 7516, 7474, 3541],
                  [255, 34, 1074, 6897, 6908, 3460]])


cells = np.array([[32622, 32622, 93186, np.nan, np.nan, 2772015],
                  [32624, 32622, 93175, np.nan, np.nan, np.nan],
                  [32622, 32622, 93186, np.nan, np.nan, 375207],
                  [32650, 32652, 93186, np.nan, np.nan, 2772015],
                  [32692, 32690, 93175, 375302, 375302, 374886],
                  [33810, 33814, 103345, 414180, 414180, 413778],
                  [33810, 33814, 103345, 414180, 414180, 413778],
                  [32692, 32690, 93175, 375302, 375302, 374886],
                  [46279, 46277, 103771, 427077, 427077, 425868],
                  [32692, 32690, 93175, 375302, 375302, 374886],
                  [32642, 32640, 93186, 351601, 351601, 351699],
                  [32652, 32654, 93186, 330050, 330050, 330051],
                  [32739, 32739, 93186, 348847, 348847, 348331]])

eff = cells/times

def disp(a):
    return f"{a:<13.0f}"

for i in range(len(eff)):
    print(' & '.join(map(disp, eff[i, :])))


# In[]

import matplotlib.pyplot as plt

plt.figure()
plt.imshow(np.log10(times))
plt.colorbar()
# plt.gca().invert_yaxis()
plt.show()


plt.figure()
plt.imshow(np.log10(cells))
plt.colorbar()
# plt.gca().invert_yaxis()
plt.show()


plt.figure()
plt.imshow(np.log10(eff))
plt.colorbar()
# plt.gca().invert_yaxis()
plt.show()


plt.figure()
plt.plot(np.log10(cells.ravel()), np.log10(eff.ravel()), '+b')
# plt.gca().invert_yaxis()
plt.show()


plt.figure()
plt.plot(np.log10(cells.ravel()), np.log10(times.ravel()), '+g')
# plt.gca().invert_yaxis()
plt.show()




