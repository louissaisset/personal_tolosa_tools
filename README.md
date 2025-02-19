# Personal TOLOSA Toolbox

Ceci est une collection de classes et de fonctions conçues par Louis Saisset pour créer des configurations TOLOSA, lancer les configurations correspondantes sur des machines déportées et traiter les sorties de ces simulations.

## Organisation

Ce projet est organisé comme suit :

```
personal_tolosa_tools/
│
├── personal_tolosa_tools/
│   ├── __init__.py
│   ├── create_meshtool_yaml.py
│   └── local_vtk_reader.py
├── scripts/
│   ├── tools
│   │   ├── launch_meshtool_yaml_all_tools.py
│   │   ├── launch_meshtool_yaml.py
│   │   ├── launch_yaml_create_default.py
│   │   └── launch_yaml_update.pymain_create.py
│   └── wip
│       ├── Test_de_base.py
│       └── main_claude.py
├── README.md
└── .gitignore
```

- **personal_tolosa_tools/** : Dossier contenant l'ensemble des classes et fonctions définies pour générer, lancer ou post-traiter des simulations TOLOSA
- **scripts/** : Contient des scripts faisant usage des classes et des fonctions définies précédemment


