Installation
============

`lpy_treesim` ships as a Python package plus a collection of L-Py grammars, so
you need both the OpenAlea/L-Py toolchain and the Python modules in this repo.
OR you can use the provided Docker container with everything preinstalled.

Installing manually
-------------

- **Conda (recommended)** for installing `openalea.lpy` and PlantGL.
- A GPU is not required; everything runs on CPU.

Set up the L-Py environment
---------------------------

1. Create a dedicated environment that contains L-Py and PlantGL:

   .. code-block:: bash

       conda create -n lpy openalea.lpy=3.14.1 python=3.10 -c fredboudon -c conda-forge 

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

Docker-based installation (GUI + Conda preconfigured)
-----------------------------------------------------

If you prefer a containerized setup with a browser-based GUI (noVNC) and a
preconfigured `lpy` environment, use the provided Dockerfile. This is the
fastest way to get a working L-Py environment without troubleshooting local
graphics or conda channels.

Build the image:

.. code-block:: bash

        docker build -t lpy-treesim:ubuntu22 .

Run the container (exposing GUI ports and mounting only what you need):

.. code-block:: bash

        # Mount your local repo to /app for editable install, and a dedicated results dir
        mkdir -p ./results
        docker run -d --name lpy-gui \
                -p 6080:6080 -p 5900:5900 \
                -v ${PWD}:/app \
                -v ${PWD}/results:/results \
                -w /app lpy-treesim:ubuntu22

Connect to the GUI:

.. code-block:: text

        http://localhost:6080/vnc.html?host=localhost&port=6080

Notes:

- The container launches an xterm with the `lpy` conda environment activated.
- The entrypoint installs the package from `/app` in editable mode so your
    local changes take effect immediately.



Optional tooling
-----------------

The repository includes a Sphinx documentation project. To build the docs
locally install Sphinx, then run `make`:

.. code-block:: bash

    cd lpy_treesim/lpy_treesim/docs
    pip install sphinx
    make html

Open `_build/html/index.html` in a browser to preview the rendered docs.

