Files and Directory Structure
=============================

The project is organized so that every custom tree lives wholly inside the
`examples/` package, while the shared runtime sits at the repository root.

Top-level Python modules
------------------------

``base_lpy.lpy``
    The canonical L-Py grammar. It loads extern variables that point to your
    prototype dictionary, simulation classes, and color manager, then drives the
    derivation/prune/tie loop.

``simulation_base.py``
    Defines `SimulationConfig` and `TreeSimulationBase`. All simulation files in
    `examples/<TreeName>` inherit from these classes.

``stochastic_tree.py``
    Hosts the `TreeBranch`, `BasicWood`, `Support`, and related data structures
    referenced by prototypes.

``color_manager.py``
    Implements `ColorManager`, which tracks per-instance color IDs and can dump
    them via `export_mapping` to JSON.

Documentation (`docs/`)
-----------------------

Sphinx project containing the pages you are reading now. Run `make html` inside
`lpy_treesim/docs` to build the site locally.

Examples (`examples/`)
----------------------

Each subfolder describes one tree training system. For `UFO` you will find:

``examples/UFO/UFO_prototypes.py``
    Prototype classes (`Trunk`, `Branch`, `Spur`, etc.) plus the
    `basicwood_prototypes` dictionary.

``examples/UFO/UFO_simulation.py``
    `UFOSimulationConfig` and `UFOSimulation`, consumed by the base grammar.

``examples/UFO/UFO.lpy``
    Optional GUI entry point if you want to run the species manually inside
    L-Py. Most development happens via `base_lpy.lpy`, but the standalone files
    are helpful for debugging.

Add a new tree type by duplicating this directory and renaming files to match
your `--tree_name` argument.

Tree generation utilities (`tree_generation/`)
---------------------------------------------

``tree_generation/make_n_trees.py``
    CLI entry point that imports the base grammar, wires in your prototypes, and
    exports `.ply` meshes plus `{...}_colors.json` label maps. Accepts
    `--num_trees`, `--namespace`, `--rng-seed`, and `--output_dir`.

``tree_generation/helpers.py``
    Contains `write` (PLY serializer) and other small utilities referenced by
    the generator.

Supporting assets
-----------------

``dataset/``
    Destination for generated `.ply` files by default. Subfolders such as
    `test_output/` are safe to delete or replace with your own datasets.

``media/`` and ``other_files/``
    Legacy L-Py grammars, renderings, and experiments kept for historical
    reference.