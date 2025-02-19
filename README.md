# TOLOSA Toolbox

Ceci est une collection de classes et de fonctions conçues pour créer des configurations TOLOSA, lancer les configurations correspondantes sur des calculateurs déportés et traiter les sorties de ces simulations.

## Organisation

Ce projet est organisé comme suit

tolosa_toolbox/
│
├── tolosa_toolbox/
│   ├── __init__.py
│   ├── generation/
│   │   ├── __init__.py
│   │   └── create_meshtool_yaml.py
│   ├── launching/
│   │   ├── __init__.py
│   │   └── launch_meshtool_all_tools.py
│   ├── treatment/
│   │   ├── __init__.py
│   │   ├── local_vtk_reader.py
│   │   └── local_fig_creator.py
│
├── scripts/
│   ├── main_create.py
│   └── script2.py
│
├── README.md
└── .gitignore



