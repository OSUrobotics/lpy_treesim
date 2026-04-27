Usage
=====

The typical workflow for `lpy_treesim` has three stages:

1. Describe **prototypes** that capture the botanical building blocks for your
   training system.
2. Provide a **simulation configuration** that tunes derivation length, pruning
   passes, and support layout.
3. Feed both into the CLI generator (`tree_generation/make_n_trees.py`) to
   batch-export `.ply` meshes and color maps.

The following sections walk through each step with concrete file references so
you can add your own tree families next to the built-in `UFO` example.

1. Define prototypes
--------------------------------

Prototype files live under ``examples/<TreeName>/<TreeName>_prototypes.py``. They
describe the biological components of your tree by subclassing
``stochastic_tree.TreeBranch`` (ultimately ``BasicWood``). Study the existing UFO
implementation for a concrete template: ``examples/UFO/UFO_prototypes.py``.

The critical building blocks are the four state dataclasses defined in
``stochastic_tree.py``:

* ``LocationState`` tracks the start/end coordinates and the last tie point.
* ``TyingState`` stores tie axis, guide points, and the wire to attach to.
* ``GrowthState`` holds thickness increments, per-step growth length, and max
  length.
* ``InfoState`` carries metadata such as age, order, prunability, and color.

When you instantiate a prototype with ``BasicWoodConfig`` these states are
created for you. Your subclass is responsible for overriding the behavioral
hooks:

* ``is_bud_break`` decides when a new bud/branch emerges.
* ``create_branch`` clones another prototype from ``basicwood_prototypes`` and
  returns it.
* ``pre_bud_rule`` / ``post_bud_rule`` allow in-place adjustments to growth and
  tying parameters.
* ``post_bud_rule`` can emit custom L-Py modules (e.g., ``@O`` for fruiting).

Below is a simplified excerpt from the real UFO spur definition showing how the
pieces line up:

.. code-block:: python

    from stochastic_tree import BasicWood, BasicWoodConfig

    basicwood_prototypes = {}

    class Spur(TreeBranch):
        def __init__(self, config=None, copy_from=None, prototype_dict=None):
            super().__init__(config, copy_from, prototype_dict)

        def is_bud_break(self, num_buds_segment):
            if num_buds_segment >= self.growth.max_buds_segment:
                return False
            return rd.random() < 0.1 * (1 - num_buds_segment / self.growth.max_buds_segment)

        def create_branch(self):
            return None  # spurs terminate growth

        def post_bud_rule(self, plant_segment, simulation_config):
            radius = plant_segment.growth.thickness * simulation_config.thickness_multiplier
            return [('@O', [float(radius)])]

    spur_config = BasicWoodConfig(
        max_buds_segment=2,
        growth_length=0.05,
        cylinder_length=0.01,
        thickness=0.003,
        color=[0, 255, 0],
        bud_spacing_age=1,
        curve_x_range=(-0.2, 0.2),
        curve_y_range=(-0.2, 0.2),
        curve_z_range=(-1, 1),
    )
    basicwood_prototypes['spur'] = Spur(config=spur_config, prototype_dict=basicwood_prototypes)

Two more classes, ``Branch`` and ``Trunk``, reference the same dictionary when
spawning children:

.. code-block:: python

    class Trunk(TreeBranch):
        def create_branch(self):
            if rd.random() > 0.1:
                return Branch(copy_from=self.prototype_dict['branch'])

    branch_config = BasicWoodConfig(
        tie_axis=(0, 0, 1),
        thickness=0.01,
        thickness_increment=1e-5,
        growth_length=0.1,
        color=[255, 150, 0],
        bud_spacing_age=2,
    )
    basicwood_prototypes['branch'] = Branch(config=branch_config, prototype_dict=basicwood_prototypes)

Key implementation details to replicate:

* Always pass ``prototype_dict=basicwood_prototypes`` when constructing each
  prototype so clones reference the shared registry.
* Set ``BasicWoodConfig.tie_axis`` for the classes you expect to tie; the base
  simulation will skip tying for branches whose tie axis is ``None``.
* Use ``BasicWoodConfig.color`` for per-instance labeling—the ``ColorManager``
  picks up these RGB triplets and writes them to the ``*_colors.json`` mapping.

2. Configure simulation parameters
----------------------------------

The simulator pairs your prototypes with tie/prune logic by subclassing
`TreeSimulationBase` and `SimulationConfig` (see `simulation_base.py`). Each tree
family stores both classes in `examples/<TreeName>/<TreeName>_simulation.py`.

For example, ``examples/UFO/UFO_simulation.py`` implements both the config and
the runtime class:

.. code-block:: python

    from simulation_base import SimulationConfig, TreeSimulationBase

    @dataclass
    class UFOSimulationConfig(SimulationConfig):
        num_iteration_tie: int = 8
        num_iteration_prune: int = 16
        pruning_age_threshold: int = 8
        derivation_length: int = 160
        support_trunk_wire_point: tuple = (0.6, 0, 0.4)
        support_num_wires: int = 7
        ufo_x_range: tuple = (0.65, 3)
        ufo_x_spacing: float = 0.3
        ufo_z_value: float = 1.4
        ufo_y_value: float = 0
        thickness_multiplier: float = 1.2

    class UFOSimulation(TreeSimulationBase):
        def generate_points(self):
            x = np.arange(
                self.config.ufo_x_range[0],
                self.config.ufo_x_range[1],
                self.config.ufo_x_spacing,
            )
            z = np.full((x.shape[0],), self.config.ufo_z_value)
            y = np.full((x.shape[0],), self.config.ufo_y_value)
            return list(zip(x, y, z))

The base class exposes:

* ``num_iteration_tie`` / ``num_iteration_prune``: cadence for maintenance.
* ``energy_distance_weight`` / ``energy_threshold``: scoring knobs for the
  branch-to-wire assignment matrix built inside ``TreeSimulationBase.get_energy_mat``.
* ``pruning_age_threshold``: compared against ``branch.info.age`` in
  ``TreeSimulationBase.prune`` before removing geometry via ``helper.cut_from``.

On the runtime side, ``TreeSimulationBase`` supplies ready-to-use algorithms for
tying, pruning, and support assignment:

* ``generate_points`` must return the actual wire coordinates used when tie
  curves are computed (``BasicWood.update_guide``).
* ``tie`` walks the L-system string and calls ``branch.tie_lstring`` for one
  eligible branch per invocation.
* ``prune`` removes untied branches whose age exceeds
  ``config.pruning_age_threshold`` and whose prototype flag ``prunable`` is set.

To bring up a new architecture, duplicate the UFO module, rename the classes to
``<TreeName>SimulationConfig`` / ``<TreeName>Simulation``, and add any extra
dataclass fields required for your geometry (wire spacing, tie axis overrides,
etc.). Ensure the class names match the paths you pass to ``make_n_trees.py``.

Checklist for a new tree type:

1. Copy `examples/UFO/UFO_simulation.py` to `examples/<TreeName>/<TreeName>_simulation.py`.
2. Rename the dataclass to `<TreeName>SimulationConfig`.
3. Rename the runtime class to `<TreeName>Simulation` and override any helper
   methods you need.
4. Ensure the module exposes the two symbols with those exact names so the CLI
   resolver can import them.

3. Batch-generate assets
------------------------

Once prototypes and simulations exist, the CLI script assembles everything. It
always loads `base_lpy.lpy` and expects your modules to live inside the
`examples` package.

.. code-block:: bash

    cd lpy_treesim
    python lpy_treesim/tree_generation/make_n_trees.py \
        --tree_name UFO \
        --namespace orchardA \
        --num_trees 64 \
        --output_dir dataset/ufo_batch \
        --rng-seed 42 \
        --semantic-label \
        --verbose

Important flags:

``--tree_name``
    The directory under `examples/` that contains both the prototype and
    simulation modules (`examples/UFO`, `examples/Envy`, etc.). The script
    automatically builds module paths such as
    `examples.UFO.UFO_prototypes.basicwood_prototypes`.

``--namespace``
    Prefix for exported files. Meshes are named
    ``{namespace}_{tree_name}_{index:05d}.ply`` and color maps are suffixed with
    ``_colors.json``. Up to 99,999 indices are supported per run.

``--rng-seed``
    Provides reproducible randomness while still using a different seed for each
    tree inside the batch.

``--semantic-label``
    Enable semantic labeling mode. Parts of the tree are labeled by their
    semantic type (trunk, branch, spur, etc.).

``--instance-label``
    Enable instance labeling mode. Each individual branch instance receives a
    unique color for segmentation.

``--per-cylinder-label``
    Enable per-cylinder labeling mode. Each cylinder in the mesh receives a
    unique identifier.

.. note::
    Only one labeling mode can be enabled at a time. If no labeling flag is
    provided, no labeling is applied to the generated trees.

Outputs include:

- `.ply` meshes stored in the target directory.
- JSON color maps emitted by `ColorManager` so downstream segmentation models
  can recover per-instance labeling.

4. Inspect results (optional)
-----------------------------

If you want to watch an individual tree evolve, run the same environment through
the L-Py GUI:

.. code-block:: bash

    conda activate lpy
    lpy lpy_treesim/base_lpy.lpy

Inside the GUI, set the extern variables (prototype paths, simulation classes,
`color_manager`, etc.) to match the CLI defaults or a custom configuration
dictionary. Use **Animate** rather than **Run** so tying/pruning hooks fire.
