# Personal TOLOSA Toolbox

Ceci est une collection de classes et de fonctions conçues par Louis Saisset pour créer des configurations TOLOSA, lancer les configurations correspondantes sur des machines déportées et traiter les sorties de ces simulations.

## Organisation

Ce projet est organisé comme suit :

```
personal_tolosa_tools/
│
├── personal_tolosa_tools/
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
```

- **personal_tolosa_tools/** : Dossier contenant l'ensemble des classes et fonctions définies pour générer, lancer ou post-traiter des simulations TOLOSA
   - **generation/** : Contient les classes et fonctions permettant de générer des maillages ou des forçages.
    - **launching/** : Contient les classes et fonctions permettant de lancer les jobs
    - **treatment/** : Contient les classes et fonctions permettant de lire et de modifier les sorties des différents modèles
- **scripts/** : Contient des scripts faisant usage des classes et des fonctions définies précédemment


