#supress file print statements
original_print = print
print = lambda *args, **kwargs: None

#!/usr/bin/env python3
import sys
from pathlib import Path

import numpy as np

from lpy_treesim.utils.color_manager import ColorManager
import json
from openalea.lpy import Lsystem
from openalea.plantgl.all import *
from lpy_treesim.tree_generation.skeleton_components import SkeletonComponent, JunctionComponent
from lpy_treesim.tree_generation.tree_naming_convention import TreeNamingConvention
from lpy_treesim.tree_generation.tree_structure import TreeStructure
from lpy_treesim.tree_models.base_tree.bud_site import BudSite
from lpy_treesim.tree_models.base_tree.tree_wood_prototypes import BasicWood
import logging


class TreeBuilder:
    logger = logging.getLogger(__name__)
    b_init_sys_path = False

    # Where to find base_lpy.lpy, which is the one and only lpy file that defines the string generation
    BASE_LPY_PATH = Path(__file__).resolve().parents[1] / "lpy_functions" / "base_lpy.lpy"

    def __init__(self,
                 tree_name: str,
                 seed_value: int,
                 interactive: bool):

        if not TreeBuilder.b_init_sys_path:
            # Ensure repository root is discoverable for prototype imports
            sys.path.insert(0, str(TreeBuilder.BASE_LPY_PATH.parents[0]))
            TreeBuilder.b_init_sys_path = True

        # Store the branches as they're created
        self.branch_hierarchy = {}
        self.map_name_instance = {}

        # For unique labeling of branch cylinders
        self.color_manager = ColorManager()

        # Show tree or not while building
        self.b_interactive = interactive

        # Where to find the source code and start values for the trunk
        # See extern_variables in base_lpy.lpy
        self.extern_vars = {
            "prototype_builder_path": f"lpy_treesim.tree_models.{tree_name}.{tree_name}_prototypes.build_basicwood_prototypes",
            "trunk_class_path": f"lpy_treesim.tree_models.{tree_name}.{tree_name}_prototypes.Trunk",
            "simulation_config_class_path": f"lpy_treesim.tree_models.{tree_name}.{tree_name}_simulation.{tree_name.upper()}SimulationConfig",
            "simulation_class_path": f"lpy_treesim.tree_models.{tree_name}.{tree_name}_simulation.{tree_name.upper()}Simulation",
            "branch_hierarchy": self.branch_hierarchy,
            "map_name_instance": self.map_name_instance,
            "color_manager": self.color_manager,
            "seed_value": seed_value,
            "interactive": self.b_interactive
        }
        # Enable batch mode before displaying anything
        self.__lsystem = Lsystem(str(TreeBuilder.BASE_LPY_PATH), self.extern_vars)

    def lsystem(self) -> Lsystem:
        return self.__lsystem

    @staticmethod
    def convert_vec3_to_tuple(vec3) -> tuple:
        return (float(vec3.x), float(vec3.y), float(vec3.z))

    @staticmethod
    def _replace_keyword(piece: str)->str:
        """ For making strings readable - converts pointers to strings"""
        check_keywords = ["Support", "Bud", "Spur", "Trunk", "Branch"]
        for kw in check_keywords:
            if kw in piece:
                return "!" + kw + "!"
        # No keyword found - don't replace
        return "!" + piece + "!"

    @staticmethod
    def _take_out_class_refs(piece_in: str)->str:
        """ For making strings readable - converts <> instances to strings"""
        piece = piece_in
        while "<" in piece:
            piece_kw = ""
            if piece[0] == "<":
                split_break = piece.split(">")
                piece_kw = TreeBuilder._replace_keyword(split_break[0])
                piece = piece_kw + "".join(split_break[1:])
            else:
                split_break_left = piece.split("<")
                split_break_right = split_break_left[1].split(">")
                piece_kw = TreeBuilder._replace_keyword(split_break_right[0])
                piece = split_break_left[0] + piece_kw + "".join(split_break_right[1:])
                for indx in range(2, len(split_break_left)):
                    piece = piece + "<" + split_break_left[indx]
        return piece

    @staticmethod
    def make_string_readable(lstring: str):
        """ A not very good bit of code for indenting strings by brackets []
        """
        str_break_left_bracket = lstring.split('[')
        indent = 0
        for before_bracket in str_break_left_bracket:
            indent += 2

            b_has_end_bracket = False
            if len(before_bracket) > 0:
                b_has_end_bracket = before_bracket[-1] == "]"

            str_break_end_bracket = before_bracket.split("]")
            n_spaces = " " * indent
            print(f"\n{n_spaces}[", end="")
            for indx, up_to_end_bracket in enumerate(str_break_end_bracket):
                n_spaces = " " * indent
                piece = up_to_end_bracket.replace("WoodStart", "\n" + n_spaces + "WoodStart")
                piece = piece.replace("ParameterSet(type=", "PS(")
                piece = TreeBuilder._take_out_class_refs(piece)
                print(f"{piece}", end="")
                if indx < len(str_break_end_bracket) - 1 or b_has_end_bracket:
                    print(f"]")
                    indent -= 2

    def check_tree(self):
        found_buds = []
        found_branches = []
        for branch_key, branch_buds in self.branch_hierarchy.items():
            if "root" in branch_key:
                continue
            if not branch_key in self.map_name_instance:
                print(f"Checking tree: No branch {branch_key} in map instance")
                continue
            if "bud" in branch_key:
                continue
            branch = self.map_name_instance[branch_key]
            for bud in branch_buds:
                found_buds.append(bud.name)
                if bud.branch_child:
                    found_branches.append(bud.branch_child.name)
                if bud.spur_child:
                    found_branches.append(bud.spur_child.name)
                if bud.dist_along > branch.growth.length:
                    print(f"Problem: {branch.name}, {bud.name}")
        for bud_name in found_buds:
            if not bud_name in self.branch_hierarchy:
                print(f"Problem: {bud_name} is alive but not in hierarchy")
        for branch_name in found_branches:
            if not branch_name in self.branch_hierarchy:
                print(f"Problem: {branch_name} is alive but not in hierarchy")

    def check_string(self, lstring: str):
        find_wood = lstring.split("WoodStart")
        for string_bit in find_wood[1:]:
            if not string_bit[0] == "(":
                continue
            name = string_bit[1:].split(")")[0]
            if not name in self.branch_hierarchy:
                print(f"Could not find name {name} in branch hierarchy")
        find_spur = lstring.split("SpurStart")
        for string_bit in find_spur[1:]:
            if not string_bit[0] == "(":
                continue
            name = string_bit[1:].split(")")[0]
            if not name in self.branch_hierarchy:
                print(f"Could not find name {name} in branch hierarchy")

    def generate_tree(self):
        """ Actually build the lpy string
        @param b_interactive - do you want to have to hit a key every iteration?"""

        # First string - see base_lpy.lpy axiom module
        lstring = self.__lsystem.axiom

        if self.b_interactive:
            """Suppose to bring up a window. Whether or not it does depends on OS"""
            Viewer.start()

        # Iterate, replacing modules with new ones every iteration
        #  Roughly 28 iterations per year, 3-5 years (depending on SimulationConfig parameters)
        b_check_string = False
        for iteration in range(self.__lsystem.derivationLength):
            #print = original_print
            print(f"Iteration {iteration}")
            #print = lambda *args, **kwargs: None

            if b_check_string:
                self.check_string(str(lstring))
                b_check_string = False

            # One iteration - replace symbols
            lstring = self.__lsystem.derive(lstring, iteration, 1)
            #self.make_string_readable(str(lstring))

            if "%" in str(lstring):
                print("PRUNING cuts found in string")
                self.check_tree()
                b_check_string = True

            # DO NOT TAKE OUT THIS LINE - or everything will stop working
            # This calls all the code in the "Interpretation" block in base_lpy.py (the I() modules)
            interpreted_string = self.__lsystem.interpret(lstring)

            # if iteration % self.__lsystem.derivationLength == 28:
            #     self.make_string_readable(str(interpreted_string))
            if self.b_interactive:
                scene =  self.__lsystem.sceneInterpretation(interpreted_string)
                Viewer.display(scene)

                input("Press Enter to continue...")

        if self.b_interactive:
            Viewer.exit()

        # String and scene (which has geometry)
        #   This string will have all the F() modules, which are the ones that actually produce geometry
        self.check_string(str(lstring))
        self.check_string(str(self.__lsystem.sceneInterpretation(lstring)))
        return lstring, self.__lsystem.sceneInterpretation(lstring)

    def _add_junctions(self,
                       mapping_tree_structure: dict,
                       parent_dict: dict,
                       parent_lpy: BasicWood,
                       bud_sites: list[BudSite]):
        """ Get all the junctions for this branch. Fills in the junction information"""
        new_junctions = []
        for bud_indx, bud in enumerate(bud_sites):
            new_junction = JunctionComponent()
            new_junction.t_along = bud.dist_along / parent_lpy.growth.length
            new_junction.theta_around = bud.bud_angle_around
            new_junction.pt_attach = self.convert_vec3_to_tuple(bud.start_loc)
            if bud_indx < len(bud_sites) - 1:
                vec_parent_dir = bud_sites[bud_indx + 1].start_loc - bud.start_loc
                vec_parent_dir /= np.linalg.norm(vec_parent_dir)
            else:
                vec_parent_dir = parent_lpy.location.end_dir
            new_junction.prev_section_height = 0.0
            if bud_indx > 0:
                vec_prev_sec = bud_sites[bud_indx].start_loc - bud_sites[bud_indx-1].start_loc
                new_junction.prev_section_height = np.linalg.norm(vec_prev_sec)
            new_junction.vec_along_parent = self.convert_vec3_to_tuple(vec_parent_dir)
            new_junction.vec_branch = self.convert_vec3_to_tuple(bud.start_dir)
            new_junction.ang_attach = bud.bud_angle_from_parent
            new_junction.radius = parent_lpy.growth.get_diameter(bud.dist_along)
            new_junction.parent_name = parent_dict["name"]
            new_junction.child_name = ""
            if bud.bud_state is BudSite.BudType.PRUNED:
                new_junction.type = JunctionComponent.JunctionType.PRUNED
            if bud.bud_state is BudSite.BudType.DORMANT:
                new_junction.type = JunctionComponent.JunctionType.BUD
            if bud.branch_child:
                lpy_child_name = bud.branch_child.name
                child_dict = mapping_tree_structure[lpy_child_name]
                new_junction.child_name = child_dict["full_name"]
                new_junction.type = JunctionComponent.JunctionType.BRANCH
            if bud.spur_child:
                lpy_child_name = bud.spur_child.name
                child_dict = mapping_tree_structure[lpy_child_name]
                new_junction.child_name = child_dict["name"]
                if bud.branch_child:
                    new_junction.type = JunctionComponent.JunctionType.BRANCH_AND_SPUR
                else:
                    new_junction.type = JunctionComponent.JunctionType.BRANCH

            new_junctions.append(new_junction)

        return new_junctions

    def _add_buds(self,
                  mapping_tree_structure: dict,
                  mapping_lpy: dict,
                  tree: TreeStructure,
                  parent_dict: dict,
                  bud_sites: list[BudSite]):
        """ Turning branch_hierarchy into TreeStructure data structure
        This helper method loops over all the bud sites on a branch and adds the bud sites' branch/spur children
        to the parent_dict structure"""
        trunk_id = TreeNamingConvention.get_trunk_id(parent_dict)
        parent_ids = tree.get_parent_id_list(parent_dict)
        for bud in bud_sites:
            if bud.branch_child:
                child_lpy_name: str = bud.branch_child.name
                branch_dict = tree.new_branch(trunk_id=trunk_id, parent_ids=parent_ids)
                mapping_tree_structure[child_lpy_name] = branch_dict
                mapping_lpy[child_lpy_name] = bud.branch_child
            if bud.spur_child:
                child_lpy_name: str = bud.spur_child.name
                spur_dict = tree.new_spur(trunk_id=trunk_id, parent_and_branch_ids=parent_ids)
                mapping_tree_structure[child_lpy_name] = spur_dict
                mapping_lpy[child_lpy_name] = bud.spur_child

    def _add_skeleton(self,
                      mapping_tree_structure: dict,
                      branch_dict: dict,
                      branch_lpy: BasicWood,
                      bud_sites: list[BudSite]):
        """ Adds the skeleton components to the tree structure"""
        skel = SkeletonComponent(branch_dict["name"])
        skel.start_pt = self.convert_vec3_to_tuple(branch_lpy.location.start)
        skel.end_pt = self.convert_vec3_to_tuple(branch_lpy.location.end)
        skel.length = branch_lpy.growth.length

        skel.centroids.append(self.convert_vec3_to_tuple(branch_lpy.location.start))
        skel.radii.append(branch_lpy.growth.get_diameter(0.0))
        skel.t_values.append(0.0)
        for bud in bud_sites:
            skel.centroids.append(self.convert_vec3_to_tuple(bud.start_loc))
            skel.radii.append(branch_lpy.growth.get_diameter(bud.dist_along))
            skel.t_values.append(bud.dist_along / branch_lpy.growth.length)

        l = 0.0
        for indx in range(0, 3):
            l += (skel.centroids[-1][indx] - branch_lpy.location.end[indx]) ** 2

        if not np.isclose(l, 0.0):
            skel.centroids.append(self.convert_vec3_to_tuple(branch_lpy.location.end))
            skel.radii.append(branch_lpy.growth.get_diameter(branch_lpy.growth.length))
            skel.t_values.append(1.0)

        skel.child_junctions = self._add_junctions(mapping_tree_structure=mapping_tree_structure,
                                                   parent_dict=branch_dict,
                                                   parent_lpy=branch_lpy,
                                                   bud_sites=bud_sites)
        branch_dict["skel"] = skel

    def create_tree_structure(self) -> (TreeStructure, dict, dict):
        """ Loop over the branch structure and make one Tree component for each structure.
        Returns the tree structure and a mapping from the lpy names to the new tree structures"""
        tree = TreeStructure()

        # Map lpy names to tree parts
        mapping_tree_structure = {}
        # Map lpy names to Tree structure pointers
        mapping_lpy = {}
        # Each item in the branch_hierarchy dictionary is organized as name -> list of buds
        # This is relying on the fact that looping over the dictionary will happen in the order that the objects
        #  were created (eg root, trunk, primary branches)
        for key_orig, child_list in self.branch_hierarchy.items():
            key = key_orig.lower().strip()
            if "root" in key:
                # Root - start adding trunks
                root_dict = tree.new_root()
                for trunk_lpy in child_list:
                    trunk_dict = tree.new_trunk()
                    mapping_tree_structure[trunk_lpy.name] = trunk_dict
                    mapping_lpy[trunk_lpy.name] = trunk_lpy
            elif "bud" in key:
                # Skipping these because buds will be handled when processing each branch/trunk
                continue
            else:
                # The dictionary elements are created when we process the parent, so we just have to get
                # them back
                branch_dict = mapping_tree_structure[key_orig]
                branch_lpy = self.map_name_instance[key_orig]
                # This creates and adds the tree components
                self._add_buds(mapping_tree_structure=mapping_tree_structure,
                               mapping_lpy=mapping_lpy,
                               tree=tree,
                               parent_dict=branch_dict,
                               bud_sites=child_list)
                # This creates the SkeletonComponent for the branch
                self._add_skeleton(mapping_tree_structure=mapping_tree_structure,
                                   branch_dict=branch_dict,
                                   branch_lpy=branch_lpy,
                                   bud_sites=child_list)
                for junc in branch_dict["skel"].child_junctions:
                    if "trunk" in key:
                        tree.trunk_junctions.append(junc)
                    else:
                        tree.branch_junctions.append(junc)


        return tree, mapping_lpy, mapping_tree_structure

    def export_hierarchy_dict(self) -> dict:
        named_hierarchy = {}
        for key, branch in self.branch_hierarchy.items():
            key = key.lower().strip()
            named_hierarchy[key] = []
            for child in branch:
                named_hierarchy[key].append(child.name.lower().strip())
        return named_hierarchy

    def export_branch_location_dict(self) -> dict:
        named_hierarchy = {}
        for key, branch in self.branch_hierarchy.items():
            for child in branch:
                child_name = child.name.lower().strip()
                if "bud" in child_name:
                    named_hierarchy[child_name] = {"start": self.convert_vec3_to_tuple(child.start_loc)}
                else:
                    named_hierarchy[child_name] = {"start": self.convert_vec3_to_tuple(child.location.start),
                                                   "end": self.convert_vec3_to_tuple(child.location.end)}
        return named_hierarchy
    
    def get_metadata(self) -> dict:
        """Export metadata based on label settings. Includes hierarchy and L-Py vars."""
        export_dict = {"seed_value": int(self.extern_vars["seed_value"])}
        # Hierarchy
        export_dict["hierarchy"] = self.export_hierarchy_dict()
        export_dict["branch_locations"] = self.export_branch_location_dict()
        return export_dict

    def export_metadata(self, metadata_path: str) -> dict:
        """Export metadata based on label settings. Includes hierarchy and L-Py vars."""
        TreeBuilder.logger.info(f"Exporting metadata to {metadata_path}...")
        export_dict = self.get_metadata()
        with open(metadata_path, "w") as f:
            json.dump(export_dict, f, indent=4)
        return export_dict
