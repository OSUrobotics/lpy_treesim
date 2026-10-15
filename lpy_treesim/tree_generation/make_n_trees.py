#! /usr/bin/env python3
import argparse
import numpy as np
from pathlib import Path
import secrets
import os as os
import logging

from lpy_treesim.tree_generation.tree_builder_lpy import TreeBuilder
from lpy_treesim.tree_generation.file_naming_config import FileNamingConfig
from lpy_treesim.tree_generation.tree_to_usd import create_mesh_usd, create_skeleton_usd, check_texture
from lpy_treesim.textures.generate_texture import make_texture_set, make_uv_texture
from lpy_treesim.tree_generation.lpy_scene_to_mesh import plant_gl_scene_to_vertices_and_faces, stitch_cylinders, write_mesh

logger = logging.getLogger(__name__)

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate and save multiple L-Py trees.")
    parser.add_argument("--num-trees", type=int, default=1, help="Number of trees to generate")
    parser.add_argument("--stage-dir", type=Path, default=Path("./"), help="Directory for top of Stage USD files")
    parser.add_argument("--output-dir", type=Path, default=Path("./data/"), help="Directory for regular mesh outputs")
    parser.add_argument("--tree-name", type=str, default="ufo", help="Tree family to generate (UFO/Envy/etc.)")
    parser.add_argument("--texture-name", type=str, default="apple", help="Use/make all textures with this name")
    parser.add_argument("--verbose", action="store_true", help="Print progress details")
    parser.add_argument("--interactive", action="store_true", help="Show tree growing")
    parser.add_argument("--dataset-seed", type=int, default=None, help="Optional deterministic seed for dataset generation")
    parser.add_argument("--namespace", type=str, default="lpy", help="Prefix namespace for output filenames")
    parser.add_argument("--ply", action="store_true", help="Write out ply file format")
    parser.add_argument("--obj", action="store_false", help="Write out obj file format")
    parser.add_argument("--meta-data", action="store_true", help="Write out meta data")
    parser.add_argument("--usda", action="store_true", help="Write out universal scene descriptor format")
    parser.add_argument("--skeleton", action="store_true", help="Write out skeleton as separate usd file")
    parser.add_argument("--make-textures", action="store_true", help="Create a new set of textures")
    args = parser.parse_args()

    if args.num_trees > (FileNamingConfig.MAX_TREES + 1) or args.num_trees < 1:
        raise ValueError(f"num_trees={args.num_trees} is not in the range [1, {FileNamingConfig.MAX_TREES + 1}].")
    if args.dataset_seed is None:
        args.dataset_seed = secrets.randbits(32)
    return args


def main():
    logger.info("Starting tree generation...")
    args = _parse_args()

    naming = FileNamingConfig(namespace=args.namespace, tree_type=args.tree_name)
    # ensure_output_dir(args.output_dir)
    os.makedirs(args.output_dir, exist_ok=True)

    stage_context = []
    if args.stage_dir is not None:
        from pxr import Ar, Usd
        # 1. Define your search paths
        loc_name = str(args.stage_dir)
        os.chdir(loc_name)
        print(f"Changing to {loc_name}")
        search_paths = [loc_name]

        # 2. Create a context with these paths
        stage_context = Ar.DefaultResolverContext(search_paths)

        check_texture(stage_context)

        if args.make_textures:
            radii, name_radii = make_texture_set(args.tree_name, loc_name + "/textures")
        else:
            radii = [1]
            name_radii = ["pine_bark_vmbibe2g_2k"]

    # Generate trees - use unique seeds
    tree_rng: np.random.Generator = np.random.default_rng(seed=args.dataset_seed)
    for index in range(args.num_trees):
        # Seed
        tree_seed = tree_rng.integers(low=0, high=1_000_000)

        # Initialize the class
        lsb = TreeBuilder(tree_name=args.tree_name, seed_value=int(tree_seed), interactive=args.interactive)

        if args.verbose:
            print(f"INFO: Generating {args.tree_name} tree #{index:03d}")
        logging.info(f"Generating {args.tree_name} tree #{index:03d} with seed {tree_seed}")

        # Generates the l-string that everything is built off of, then converts it to the "scene"
        #   Also sets one color for each spur/branch/trunk instance (stored in branch_hierarchy)
        lstring, scene = lsb.generate_tree()

        # Converts the scene to our tree structure.
        #   Mapping maps the unique ids from the lstring into our tree structure
        #   This ensures the branches etc are numbered sequentially
        tree, mapping_lpy, mapping_tree_structure = lsb.create_tree_structure()

        # Adds to each tree component the mesh cylinders created by lpy
        bud_sites = plant_gl_scene_to_vertices_and_faces(scene,
                                                         mapping_tree_structure=mapping_tree_structure,
                                                         color_mapping=lsb.color_manager)

        # Now stitch together all of the mesh components into tubes instead of discrete cylinders
        # Also adds colors and texture coordinates
        color_to_part, keys_to_remove = stitch_cylinders(tree=tree)
        # Some newly created branch parts do not have any meshes associated with them
        #for key in keys_to_remove:
        #    tree.remove_key(key)

        # Write out mesh file formats
        if args.ply or args.obj:
            mesh_path = args.output_dir / naming.mesh_filename(index, file_type="")
            uv_name = str(mesh_path) + "_uv.png"
            make_uv_texture(uv_name)
            write_mesh(tree=tree, fname=mesh_path, bud_sites=bud_sites, image_name=uv_name)

        if stage_context is not [] and args.usda:
            # Where the usd files are stored
            usd_path = os.path.join(str(args.stage_dir), naming.usd_filename(index))
            uv_name = str(args.stage_dir ) + "/textures/mesh_uv.png"
            make_uv_texture(uv_name)
            for b_use_uv in [True, False]:
                create_mesh_usd(stage_context, 
                                world_path=str(args.stage_dir), 
                                in_tree_name=naming._prefix(index), 
                                tree=tree, 
                                radii=radii, name_radii=name_radii,
                                b_use_uv=b_use_uv)
            if args.skeleton:
                create_skeleton_usd(stage_context=stage_context,
                                    world_path=str(args.stage_dir),
                                    in_tree_name=naming._prefix(index),
                                    tree=tree,
                                    level_limit=2)
            logger.info(f"Wrote mesh to {usd_path}")

        if args.meta_data:
            import json
            metadata_path = args.output_dir / naming.metadata_filename(index)
            meta_data = lsb.get_metadata()
            meta_data["tree"] = tree.create_dict()
            # meta_data["tree_mapping"] = mapping
            meta_data["color_mapping"] = color_to_part
            with open(metadata_path, "w") as f:
                json.dump(meta_data, f, indent=4)
            logger.info(f"Wrote meta data to {metadata_path}")

        del scene
        del lstring
        del lsb
    logger.info("Tree generation complete.")
    return


if __name__ == "__main__":
    main()
