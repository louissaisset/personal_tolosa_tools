# Personal TOLOSA Toolbox

Ceci est une collection de classes et de fonctions conçues par Louis Saisset pour créer des configurations TOLOSA, lancer les configurations correspondantes sur des machines déportées et traiter les sorties de ces simulations.

## Organisation

Ce projet est organisé comme suit :

```
personal_tolosa_tools/
├── personal_tolosa_tools
│   ├── __init__.py
│   ├── vtk_plotter_lib.py
│   └── yaml_meshtool.py
├── README.md
└── scripts
    ├── tools
    │   ├── launch_meshtool_yaml_all_tools.py
    │   ├── launch_meshtool_yaml.sh
    │   ├── launch_vtk_create_mesh_map_from_diag.py
    │   ├── launch_vtk_create_u-v-ssh_map-timestep.py
    │   ├── launch_yaml_create_default.py
    │   ├── launch_yaml_create_default.py.bak
    │   └── launch_yaml_update.py
    └── wip
        ├── compare_vtk_same_grid.py
        ├── interp_vtk_regular_grid.py
        └── main_claude.py


```

- **personal_tolosa_tools/** : Dossier contenant l'ensemble des classes et fonctions définies pour générer, lancer ou post-traiter des simulations TOLOSA
- **scripts/** : Contient des scripts faisant usage des classes et des fonctions définies précédemment avec **tools** un dossier contenant des outils prêt à être utilisés tels quels et **wip** un dossier contenant les scripts encore en cours d'écriture.


