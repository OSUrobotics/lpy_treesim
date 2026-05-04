============
TreeSim_Lpy
============

Description
-----------

TreeSim_Lpy is a tree modelling tool which is built upon L-py with the added features of pruning and tying trees down to mimic different tree architectures such as Upright fruiting offshoot, V-Trellis, etc. 

Applications
------------
Learning to Prune Branches in Modern Tree-Fruit Orchard - https://ieeexplore.ieee.org/stamp/stamp.jsp?arnumber=11128361

A Dataset for Semantic and Instance Segmentation of Modern Fruit Orchards - https://github.com/tqosu/MFO

Documentation
-------------

The documentation is provided at `Read the Docs <https://osurobotics.github.io/lpy_treesim/>

You can find the latest L-Py documentation at <https://lpy.readthedocs.io/en/latest>

Docker GUI (noVNC) and activating the `lpy` environment
-------------------------------------------------------

You can run TreeSim inside a Docker container that provides a virtual X display and noVNC (a browser VNC client).
This container also provides a conda environment named ``lpy`` containing the required LPy packages.

Build the Docker image (recommended tag: ``lpy-treesim:ubuntu22``):

.. code-block:: bash

   docker build -t lpy-treesim:ubuntu22 .

Run the container (detached), mounting your local cloned workspace:

.. code-block:: bash

   # Mount the entire local repo to /app for editable install
   docker run -d --name lpy-gui -p 6080:6080 -p 5900:5900 -v ${PWD}:/app lpy-treesim:ubuntu22

This mounts your local cloned workspace (with all files like ``.git``, ``README.rst``, etc.) to ``/app``. The entrypoint installs the package in editable mode from the mounted code, so local changes are reflected immediately without rebuilding.

Connect to the GUI with your browser:

 - Visit: ``http://localhost:6080/vnc.html?host=localhost&port=6080``
 - A desktop session with fluxbox and Xvfb will start, along with an xterm terminal.

To verify the environment is active inside the container:

.. code-block:: bash

   # Should print 'lpy' if activated
   echo $CONDA_DEFAULT_ENV
   python -c "import openalea.lpy; print('openalea.lpy import ok')"

NOTE: You can copy and paste content in noVNC using the clipboard menu in the left bar and middle click (mouse button) to paste in the terminal.

See the repository Dockerfile for more details about the installed packages and build steps.

Installing (Windows and Linux only)
-----------------------
First install conda mini-forge; you need this to get the openalea environment (mamba)
- make sure you have conda-build enabled 
- conda install conda-build
Follow the instructions to install openalea-meta. Note that you need miniforge (which has mamba)
-  "https://github.com/openalea/openalea-meta"

Copy the openalea environment
 - conda create --name lpy_tree --clone openalea
- conda activate lpy_tree

Add the Universal Scene Description libraries
- python -m pip install usd-core

shapely, used by generate_orchard
 - python -m pip install shapely

either pip install or set up conda develop (note, in PyCharm you can just set the current folder to be the top one)
- conda develop .
cd into the lpy_treesim directory and pip install 
- pip install .
now you should be able to run code as below

Making your first tree
----------------------
To create your first tree using TreeSim_Lpy, in the NoVNC window with the terminal with L-Py activated, run the following commands:

.. code-block:: bash
   
   python lpy_treesim/tree_generation/make_n_trees.py --num-trees 1 --output-dir ./dataset


This should create a dataset folder in the current directory with one generated tree mesh in it. It should be available locally on your host machine in the cloned repository folder.

Labeling Options
----------------
You can specify labeling options via command-line flags. Only one labeling mode can be enabled at a time:

.. code-block:: bash

   # Enable semantic labeling
   python lpy_treesim/tree_generation/make_n_trees.py --num_trees 1 --semantic-label

   # Enable instance labeling
   python lpy_treesim/tree_generation/make_n_trees.py --num_trees 1 --instance-label

   # Enable per-cylinder labeling
   python lpy_treesim/tree_generation/make_n_trees.py --num_trees 1 --per-cylinder-label

If no labeling flag is provided, no labeling is applied to the generated trees.

Removing Intersecting Branches
------------------------------
When branches grow they often intersect with each other. Use the post-processing script to remove intersecting branches from the output PLY file:

.. code-block:: bash

   # Remove intersecting branches from a PLY file
   python -m lpy_treesim.tree_generation.remove_intersecting_branches --ply dataset/lpy_UFO_00000.ply --metadata dataset/lpy_UFO_00000_metadata.json --verbose

   # Save output to a different file
   python -m lpy_treesim.tree_generation.remove_intersecting_branches --ply input.ply --output cleaned.ply --verbose

The script identifies branches by their color and uses bounding box intersection tests to detect overlapping branches. When intersections are found, the smaller or lower-priority branch is removed (tertiary branches are removed before secondary branches, which are removed before the trunk).

Features
--------

- **Pruning:** Remove unwanted branches to simulate pruning.
- **Branch Tying:** Simulate branches being tied down to mimic different orchard architectures.
- **Labelling:** Get instance and semantic segmentation labels of the mesh
- **Intersection Removal:** Post-processing to remove intersecting branches from generated meshes


Contact
-------

Please open an **Issue** if you need support or you run into any error (Installation, Runtime, etc.).
We'll try to resolve it as soon as possible.

