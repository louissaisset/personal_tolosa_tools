#!/bin/bash

# This is a simple wrapper to use any yaml file for meshtool
# launch_meshtool path_to_yaml_file 

echo -e "\n       \e[32mOK:\e[0m Begining wrapper for meshtool"


# change for other users
necessary_conda_env=meshtool-env
# necessary_conda_env=new_meshtool
path_meshtool=~/SOFTS/mesh-tool

if [[ ! "$CONDA_DEFAULT_ENV" == "$necessary_conda_env" ]]; then
	echo -e "    \e[31mERROR:\e[0m Activate $necessary_conda_env conda environment"
	exit
fi

path_src="$path_meshtool/src"
if [[ ! ":$PYTHONPATH:" == *":$path_src"* ]]; then
	# echo -e "\e[33mWARNING:\e[0m adding $path_src to PYTHONPATH\n"
	export PYTHONPATH=$PYTHONPATH:$path_src
fi

path_yaml="$path_meshtool/bin/input.yaml"
if [[ -f $1 ]]; then
	path_absolute=$(readlink -f $1)
	# echo -e "       \e[32mOK:\e[0m using file $path_absolute"
	echo -e "  \e[33mWARNING:\e[0m Adding a symbolic link to $path_absolute in $path_meshtool/bin/"
	ln -sf $path_absolute $path_yaml
	echo -e "       \e[32mOK:\e[0m Launching command 'python3 -m meshtool'"
	python3 -m meshtool
else
	if [[ -f $path_yaml ]]; then
		echo -e "  \e[33mWARNING:\e[0m Using default file $path_yaml"
		echo -e "       \e[32mOK:\e[0m Launching command 'python3 -m meshtool'"
		python3 -m meshtool
	else
		echo -e "    \e[31mERROR:\e[0m Default yaml file $path_yaml does not exist"
		exit
	fi
fi

