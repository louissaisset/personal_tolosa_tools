#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu May 22 15:30:50 2025

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

import matplotlib as mpl
mpl.use('agg')

import matplotlib.pyplot as plt
# Paramètres d'affichage pour que ce soit toujours plus propre
plt.rcParams["font.family"] = "cmr10"
plt.rcParams["font.size"] = 8
if not os.uname()[1].startswith('belenos'):
    plt.rcParams['text.usetex'] = True
    plt.rcParams['axes.formatter.use_mathtext'] = True
    plt.rcParams['mathtext.fontset'] = "custom"
    plt.rcParams['mathtext.rm'] = "cmr10"
    plt.rcParams['mathtext.it'] = "cmr10:italic"
    plt.rcParams['mathtext.bf'] = "cmr10:bold"

from pathlib import Path
import argparse








if __name__ == '__main__':

    from init import set_logging
    
    set_logging('info', 'log/')
    
    path = '/local/home/lsaisset/DATA/DEBUG_ISLANDS/BELENOS/SIMPLE_TESTS/BINARY/res/vtk/'

    file_rdr = FileReader()
    
    # details = file_rdr.read_file(path, next(Info.search(path)))
    # print(details)


    # vtkdata = file_rdr.read_file(path, 'result_000000.vtk')
    # print(vtkdata)

    #
    # num_nodes = details[next(Mesh.search(path))]['num_nodes']
    # num_cells = details[next(Mesh.search(path))]['num_cells']

    data_files = sorted(list(VTKDataReader.search(path)))
    print(data_files)

    #
    # variables = details['result_data_xxxxxx.bin']['variables']
    # minmax_written = details['result_data_xxxxxx.bin']['min_max']
    # date_written = details['result_data_xxxxxx.bin']['date']
    
    
    
    # num_bytes = Data._count_byte(variables, num_cells, date_written, minmax_written)
    # print(num_bytes)
    
    # data = file_rdr.read_file(path, data_files[0], variables=variables)
    # print(data[1].shape)
    

    # # get the number totals of outputs times
    # num_times = os.path.getsize('/'.join([path, next(Data.search(path))])) // num_bytes
    # # num_times = len(file_rdr.read_file(path, next(DataMinMax.search(path)))))


    # # # concatened
    # # test = {}
    # # offset = 0
    # # count = len(variables) * num_cells
    # # for t in range(num_times):
    # #     for variable in variables:
    # #         date, data = file_rdr.read_file(path, next(Data.search(path)), variables=variables,
    # #                                         count=count, offset=offset)
    # #         test[date] = data
    # #     offset += num_bytes 

    # # print(test)

    
