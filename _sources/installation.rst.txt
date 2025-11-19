Installation
============

`lpy_treesim` ships as a Python package plus a collection of L-Py grammars, so
you need both the OpenAlea/L-Py toolchain and the Python modules in this repo.

Prerequisites
-------------

- **Conda (recommended)** for installing `openalea.lpy` and PlantGL.
- **Python 3.9+** for running the helper scripts.
- A GPU is not required; everything runs on CPU.

Set up the L-Py environment
---------------------------

1. Create a dedicated environment that contains L-Py and PlantGL:

   .. code-block:: bash

       conda create -n lpy openalea.lpy plantgl python=3.9 -c fredboudon -c conda-forge

2. Activate the environment any time you work on the project:

   .. code-block:: bash

       conda activate lpy

3. Validate the installation by launching the GUI (optional but handy for
   debugging grammars):

   .. code-block:: bash

       lpy

Install `lpy_treesim`
---------------------

With the environment active, clone and install the package in editable mode so
that L-Py can import your custom prototypes:

.. code-block:: bash

    git clone https://github.com/OSUrobotics/lpy_treesim.git
    cd lpy_treesim
    pip install -e .

Editable installs expose modules such as `lpy_treesim.ColorManager` and ensure
`examples/<tree>` can import the shared base grammar.

Optional tooling
-----------------

The repository includes a Sphinx documentation project. To build the docs
locally install Sphinx, then run `make`:

.. code-block:: bash

    cd lpy_treesim/lpy_treesim/docs
    pip install sphinx
    make html

Open `_build/html/index.html` in a browser to preview the rendered docs.