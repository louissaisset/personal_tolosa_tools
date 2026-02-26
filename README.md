# Personal TOLOSA Toolbox

Ceci est une collection de classes et de fonctions conçues par Louis Saisset pour créer des configurations TOLOSA, lancer les configurations correspondantes sur des machines déportées et traiter les sorties de ces simulations.

## Organisation

Ce projet est organisé comme suit :

```
.
├── personal_tolosa_tools
│   ├── common.py
│   ├── initialize_logs.py
│   ├── __init__.py
│   ├── plotters.py
│   ├── processors.py
│   ├── readers.py
│   ├── vtk_plotter_lib.py
│   ├── wrappers.py
│   └── yaml_meshtool.py
├── README.md
└── scripts
    ├── tools
    │   ├── change_init_file_key_value.py
    │   ├── change_mesh_input_file_key_value.sh
    │   ├── change_mesh_reset_forcings.sh
    │   ├── initialize_script.sh
    │   ├── launch_change_regionaldepth_mesh_tif.py
    │   ├── launch_cini_initialize_folder.csh
    │   ├── launch_crop_reproj_tiffile.py
    │   ├── launch_figs_create_hydro_recap_latex.sh
    │   ├── launch_figs_create_mesh_recap_latex.sh
    │   ├── launch_fillnan_shpfile.py
    │   ├── launch_global_tide.sh
    │   ├── launch_grib2tolosa_mesh_grib.sh
    │   ├── launch_mesh_convert_tolosa_to_ww3.py
    │   ├── launch_mesh_plot_mesh.py
    │   ├── launch_meshtool_yaml_all_tools.py
    │   ├── launch_meshtool_yaml.sh
    │   ├── launch_meshtool_yaml_tool.py
    │   ├── launch_prmsl_ref.sh
    │   ├── launch_reproj_shpfile.py
    │   ├── launch_vtk_plot_comparison_folder1_folder2_data_timestep.py
    │   ├── launch_vtk_plot_comparison_interp_folder1_folder2_data_timestep_xreso_yreso_BCtype.py
    │   ├── launch_vtk_plot_mesh.py
    │   ├── launch_vtk_plot_recap_folder_timestep.py
    │   ├── launch_yaml_change_file_key_value.py
    │   ├── launch_yaml_create_default.py
    │   ├── launch_yaml_update.py
    │   └── wip_launch_create_tide_list.sh
    └── wip
        ├── compare_vtk_same_grid.py
        ├── Create_BC_Tolosa.py
        ├── grib_generator.py
        ├── interp_vtk_regular_grid.py
        ├── main_claude.py
        ├── Read_grib.py
        └── selective_smoothing_test.py
```

- **personal_tolosa_tools/** : Dossier contenant l'ensemble des classes et fonctions définies pour générer, lancer ou post-traiter des simulations TOLOSA
- **scripts/** : Contient des scripts faisant usage des classes et des fonctions définies précédemment avec **tools** un dossier contenant des outils prêt à être utilisés tels quels et **wip** un dossier contenant les scripts encore en cours d'écriture.


