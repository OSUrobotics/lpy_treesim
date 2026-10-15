"""
Part naming management utilities for tree structures

This module provides utilities for assigning unique names to tree structures to support semantic labeling
in isaac sim and else where.

Hierarchical naming structure

root_stock - the base root stock component (if tree is grafted)
trunk - the trunk(s)
branchL01, branchL02 etc - primary, secondary branches (determined by branching structure)
spur
leaf
flower
fruit

For each item above, instances are labeled -n, eg, trunk-Id00 is the first trunk, trunk-Id01 is the second trunk
For branches/spurs, the hierarchy is in the name. Eg, a spur on a second branch would have a full name of
trunk-Id01_branchL0-Id10_branchL1-Id15_spur-Id30

and a "short" name of
spur-Id30

When building a tree the intent is to have bi-directional and "flattened" dictionaries. Eg, give me a list of all of
the spurs, give me all branches of level 1, give me the parent trunk for a branch, etc.

See also skeleton_convention for defining a skeleton for each tree part (centerline plus radius) that also links face
and vertex ids to mesh components
"""

import itertools
import json

from pandas.io.formats.format import return_docstring

from lpy_treesim.tree_generation.skeleton_components import SkeletonComponent
from lpy_treesim.tree_generation.tree_naming_convention import TreeNamingConvention


class TreeStructure:
    def __init__(self):
        self.has_root_stock = False
        self.current_trunk_id = -1
        self.current_branch = []
        self.current_spur = -1
        self.current_leaf = -1
        self.current_flower = -1
        self.current_fruit = -1

        # Given a short name (like spur-Id30) return the full name (trunk-branch-branch-spur)
        # self.full_names_by_id = {}

        # Keep all the unique full and short names for each part, organized by part name
        #   These are organized by the unique part name (eg, branchL0_Id3)
        self.part_list = {}
        for name in TreeNamingConvention.part_names:
            self.part_list[name] = {}

        self.trunk_junctions = []
        self.branch_junctions = []
        self.map_full_name_to_part = {}

    @staticmethod
    def get_level_from_name(name):
        if "trunk" in name:
            return 0
        elif "branch" in name:
            if "L" in name:
                split_name = name.split('-')
                level_indx = min(int(split_name[1]), len(TreeNamingConvention._component_colors["branch"]) - 1)
                return level_indx
        return -1

    def instance_color(self, name):
        if "trunk" in name:
            col = TreeNamingConvention._component_colors["trunk"]
            split_name = name.split('-')
            indx = int(split_name[-1])
            # Once the tree is computed, this should be the maximum number of branches
            blue = 150 + indx * 100 // (self.current_trunk_id + 1)
            return (col[0], col[1], blue)
        elif "branch" in name:
            if "L" in name:
                split_name = name.split('-')
                level_indx = min(int(split_name[1]), len(TreeNamingConvention._component_colors["branch"]) - 1)
                id_indx = int(split_name[-1])
                col = TreeNamingConvention._component_colors["branch"][level_indx]
                red_blue = 0
                while id_indx > 25:
                    red_blue += 1
                    id_indx -= 25
                green = id_indx
                return (col[0] + red_blue, col[1] + green, col[2] + red_blue)
            else:
                return TreeNamingConvention._component_colors["branch"][0]
        elif "spur" in name:
            col = TreeNamingConvention._component_colors["spur"]
            split_name = name.split('-')
            spur_id = int(split_name[-1])
            green_blue = 0
            while spur_id > 100:
                green_blue += 1
                spur_id -= 100

            return (spur_id * 2, col[1] + green_blue, col[2] + green_blue)
        else:
            print(f"No known semantic name {name}")
        return (255, 255, 255)

    def trunk_parts(self):
        return self.part_list[TreeNamingConvention._trunk_key()]

    def branch_parts(self):
        return self.part_list[TreeNamingConvention._branch_key()]

    def _part_dictionary(self, kind:str, id:int, full_name:str, part_name:str, usd_name:str)->dict:
        blank_dict = {}
        blank_dict["parent_name"] = ""
        blank_dict["parent_type"] = ""
        blank_dict["parent_id"] = -1
        blank_dict["type"] = kind
        blank_dict["id"] = id
        blank_dict["full_name"] = full_name
        blank_dict["usd_name"] = usd_name.replace('-', '_')
        blank_dict["name"] = part_name
        blank_dict["mesh_cyl"] = []
        blank_dict["mesh"] = None
        blank_dict["start_loc"] = (0, 0, 0)
        blank_dict["end_loc"] = (0, 0, 0)
        blank_dict["skel"] = SkeletonComponent(part_name)

        for name in TreeNamingConvention.part_names:
            blank_dict[name] = []

        # Save both of these in the mapping dictionary
        self.map_full_name_to_part[full_name] = blank_dict
        self.map_full_name_to_part[part_name] = blank_dict
        return blank_dict

    def get_parent_id_list(self, part_dict: dict)->list:
        if part_dict["parent_type"] == TreeNamingConvention._trunk_key():
            return []

        if part_dict["parent_type"] == TreeNamingConvention._root_key():
            return []

        if not TreeNamingConvention._branch_key() in part_dict["parent_type"]:
            print(f"Unknown parent type {part_dict['parent_type']}")
            return []

        parent_dict = self.part_list[TreeNamingConvention._branch_key()][part_dict["parent_name"]]
        parent_id_list = self.get_parent_id_list(parent_dict)
        parent_id_list.append(part_dict["parent_id"])
        return parent_id_list

    def iterate_all_wood_parts(self):
        if self.has_root_stock:
            yield self.part_list[TreeNamingConvention._root_key()]
        for _, trunk_dict in self.part_list[TreeNamingConvention._trunk_key()].items():
            yield trunk_dict
        for _, branch_dict in self.part_list[TreeNamingConvention._branch_key()].items():
            yield branch_dict
        for _, spur_dict in self.part_list[TreeNamingConvention._spur_key()].items():
            yield spur_dict

    def map_key_name_to_part(self, key_name: str):
        full_name = ""
        if TreeNamingConvention._spur_key() in key_name:
            if not key_name in self.part_list[TreeNamingConvention._spur_key()]:
                print(f"Warning, trying to find a key that doesn't exist {key_name}")
            else:
                full_name = self.part_list[TreeNamingConvention._spur_key()][key_name]["full_name"]
        elif TreeNamingConvention._branch_key() in key_name:
            if not key_name in self.part_list[TreeNamingConvention._branch_key()]:
                print(f"Warning, trying to remove a key that doesn't exist {key_name}")
            else:
                full_name = self.part_list[TreeNamingConvention._branch_key()][key_name]["full_name"]
        elif TreeNamingConvention._trunk_key() in key_name:
            if not key_name in self.part_list[TreeNamingConvention._trunk_key()]:
                print(f"Warning, trying to remove a key that doesn't exist {key_name}")
            else:
                full_name = self.part_list[TreeNamingConvention._trunk_key()][key_name]["full_name"]
        if full_name == "":
            return None
        return self.map_full_name_to_part[full_name]

    def remove_key(self, key_name: str):
        full_name = ""
        if TreeNamingConvention._spur_key() in key_name:
            if not key_name in self.part_list[TreeNamingConvention._spur_key()]:
                print(f"Warning, trying to remove a key that doesn't exist {key_name}")
            else:
                full_name = self.part_list[TreeNamingConvention._spur_key()][key_name]["full_name"]
                del self.part_list[TreeNamingConvention._spur_key()][key_name]
        elif TreeNamingConvention._branch_key() in key_name:
            if not key_name in self.part_list[TreeNamingConvention._branch_key()]:
                print(f"Warning, trying to remove a key that doesn't exist {key_name}")
            else:
                full_name = self.part_list[TreeNamingConvention._branch_key()][key_name]["full_name"]
                del self.part_list[TreeNamingConvention._branch_key()][key_name]
        elif TreeNamingConvention._trunk_key() in key_name:
            print(f"Warning, removing trunk part {key_name}")
            if not key_name in self.part_list[TreeNamingConvention._trunk_key()]:
                print(f"Warning, trying to remove a key that doesn't exist {key_name}")
            else:
                full_name = self.part_list[TreeNamingConvention._trunk_key()][key_name]["full_name"]
                del self.part_list[TreeNamingConvention._trunk_key()][key_name]

        for junction_lists in (self.trunk_junctions, self.branch_junctions):
            for junction in junction_lists:
                if junction.child_name == key_name:
                    parent_tree_part = self.map_key_name_to_part(junction.parent_name)
                    skel = parent_tree_part["skel"]
                    skel.child_junctions.remove(junction)
                    junction_lists.remove(junction)
                    break

        if full_name in self.map_full_name_to_part:
            del self.map_full_name_to_part[full_name]
        if key_name in self.map_full_name_to_part:
            del self.map_full_name_to_part[key_name]

    def new_root(self):
        self.has_root_stock = True

        full_name = TreeNamingConvention.rootstock_full_name(self.has_root_stock)
        root_dict = self._part_dictionary(kind=TreeNamingConvention._root_key(),
                                          id=self.current_trunk_id,
                                          full_name=full_name,
                                          part_name=TreeNamingConvention._rootstock_name(self.has_root_stock),
                                          usd_name="/root")
        root_dict[TreeNamingConvention._root_key()] = self

        # Expecting only one root stock
        self.part_list[TreeNamingConvention._root_key()] = root_dict
        return root_dict

    def new_trunk(self):
        self.current_trunk_id += 1

        full_name = TreeNamingConvention.trunk_full_name(has_root_stock=self.has_root_stock, trunk_id=self.current_trunk_id)
        trunk_name = TreeNamingConvention._trunk_name(self.current_trunk_id)
        usd_name = TreeNamingConvention.trunk_usd_name(trunk_id=self.current_trunk_id)
        trunk_dict = self._part_dictionary(kind=TreeNamingConvention._trunk_key(),
                                           id=self.current_trunk_id,
                                           full_name=full_name,
                                           part_name=trunk_name,
                                           usd_name=usd_name)
        trunk_dict[TreeNamingConvention._root_key()] = self.has_root_stock
        trunk_dict[TreeNamingConvention._trunk_key()] = self.current_trunk_id
        trunk_dict["parent_name"] = TreeNamingConvention._rootstock_name(self.has_root_stock)
        trunk_dict["parent_type"] = TreeNamingConvention._root_key()
        trunk_dict["parent_id"] = 0

        self.part_list[TreeNamingConvention._trunk_key()][trunk_name] = trunk_dict
        return trunk_dict

    def new_branch(self, trunk_id:int, parent_ids: list):
        # Branches are identified by what level in the tree structure they are
        level = len(parent_ids)
        for new_level in range(len(self.current_branch), level+1):
            self.current_branch.append(-1)
        self.current_branch[level] += 1
        branch_and_parent_ids = []
        for id in parent_ids:
            branch_and_parent_ids.append(id)
        branch_and_parent_ids.append(self.current_branch[level])

        trunk_name = TreeNamingConvention._trunk_name(self.current_trunk_id)
        
        full_name = TreeNamingConvention.branch_full_name(has_root_stock=self.has_root_stock, trunk_id=trunk_id, branch_and_parent_ids=branch_and_parent_ids)
        usd_name = TreeNamingConvention.branch_usd_name(trunk_id=trunk_id, branch_and_parent_ids=branch_and_parent_ids)
        branch_name = TreeNamingConvention._branch_name(level, self.current_branch[level])
        branch_dict = self._part_dictionary(kind=TreeNamingConvention._branch_key(),
                                            id=self.current_branch[level],
                                            full_name=full_name,
                                            part_name=branch_name,
                                            usd_name=usd_name)

        if level == 0:
            branch_dict["parent_name"] = trunk_name
            branch_dict["parent_type"] = TreeNamingConvention._trunk_key()
            branch_dict["parent_id"] = trunk_id
        else:
            parent_branch_name = TreeNamingConvention._branch_name(level-1, parent_ids[-1])
            branch_dict["parent_name"] = parent_branch_name
            branch_dict["parent_type"] = TreeNamingConvention._branch_key()
            branch_dict["parent_id"] = parent_ids[-1]

        branch_dict[TreeNamingConvention._root_key()] = self.has_root_stock
        branch_dict[TreeNamingConvention._trunk_key()] = trunk_id
        branch_dict[TreeNamingConvention._branch_key()].extend(parent_ids)

        self.part_list[TreeNamingConvention._branch_key()][branch_name] = branch_dict
        return branch_dict

    def new_spur(self, trunk_id:int, parent_and_branch_ids: list):
        # spurs can be attached to trunks or branches. If trunk, parent_ids is the empty list
        self.current_spur += 1

        parent_dict = None
        trunk_name = TreeNamingConvention._trunk_name(trunk_id=trunk_id)
        if len(parent_and_branch_ids) == 0:
            parent_dict = self.part_list[TreeNamingConvention._trunk_key()][trunk_name]
        else:
            branch_name = TreeNamingConvention._branch_name(branch_level=len(parent_and_branch_ids)-1, branch_id=parent_and_branch_ids[-1])
            if branch_name in self.part_list[TreeNamingConvention._branch_key()]:
                parent_dict = self.part_list[TreeNamingConvention._branch_key()][branch_name]
            else:
                parent_dict =  self.part_list[TreeNamingConvention._trunk_key()][trunk_name]
                print(f"Bad computer branch_name")

        full_name = TreeNamingConvention.spur_full_name(has_root_stock=self.has_root_stock, trunk_id=trunk_id, branch_and_parent_ids=parent_and_branch_ids, spur_id=self.current_spur)
        usd_name = TreeNamingConvention.spur_usd_name(trunk_id=trunk_id, branch_and_parent_ids=parent_and_branch_ids, spur_id=self.current_spur)
        spur_name = TreeNamingConvention._spur_name(self.current_spur)
        spur_dict = self._part_dictionary(kind=TreeNamingConvention._spur_key(),
                                          id=self.current_spur,
                                          full_name=full_name,
                                          part_name=spur_name,
                                          usd_name=usd_name)

        spur_dict[TreeNamingConvention._root_key()] = self.has_root_stock
        spur_dict[TreeNamingConvention._trunk_key()] = TreeNamingConvention.get_trunk_id(part_dict=parent_dict)
        spur_dict[TreeNamingConvention._branch_key()].extend(parent_and_branch_ids)

        if len(parent_and_branch_ids) == 0:
            spur_dict["parent_name"] = trunk_name
            spur_dict["parent_type"] = TreeNamingConvention._trunk_key()
            spur_dict["parent_id"] = trunk_id
        else:
            parent_branch_name = TreeNamingConvention._branch_name(len(parent_and_branch_ids)-1, parent_and_branch_ids[-1])
            spur_dict["parent_name"] = parent_branch_name
            spur_dict["parent_type"] = TreeNamingConvention._branch_key()
            spur_dict["parent_id"] = parent_and_branch_ids[-1]

        self.part_list[TreeNamingConvention._spur_key()][spur_name] = spur_dict
        return spur_dict

    def _create_dict(self, part_dict):
        ret_dict = {"parent_name": part_dict["parent_name"],
                    "parent_type": part_dict["parent_type"],
                    "parent_id": part_dict["parent_id"],
                    "type": part_dict["type"],
                    "id": part_dict["id"],
                    "full_name": part_dict["full_name"],
                    "name": part_dict["name"]
                    }
        return ret_dict

    def create_dict(self) ->dict:
        ret_dict = {"tree": {}, "skeleton": {}, "junctions": {}}
        tree_dict = ret_dict["tree"]
        skel_dict = ret_dict["skeleton"]
        for part_name, part_dicts in self.part_list.items():
            tree_dict[part_name] = {}
            if "rootstock" in part_name:
                tree_dict[part_name] = self._create_dict(part_dicts)
            else:
                for key, item in part_dicts.items():
                    tree_dict[part_name][key] = self._create_dict(item)
                    if "skel" in item:
                        skel_dict[key] = item["skel"].create_dict()
        junc_dict = ret_dict["junctions"]
        junc_dict["trunk"] = []
        junc_dict["branch"] = []
        for junc in self.trunk_junctions:
            junc_dict["trunk"].append(junc.create_dict())
        for junc in self.branch_junctions:
            junc_dict["branch"].append(junc.create_dict())

        return ret_dict
    
    # TODO Read in from dictionary
