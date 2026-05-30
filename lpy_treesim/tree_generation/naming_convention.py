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


class TreeNamingConvention:
    part_names = ["rootstock", "trunk", "branch", "spur", "leaf", "flower", "fruit"]
    ROOT_STOCK = 0
    TRUNK = 1
    BRANCH = 2
    SPUR = 3
    LEAF = 4
    FLOWER = 5
    FRUIT = 6

    # For semantic labeling by part
    _component_colors={"rootstock":(50, 50, 50), "trunk":(50, 50, 255), "branch":((50, 220, 50), (40, 190, 40), (30, 160, 30), (20, 130, 20)), "spur":(255, 50, 50)}

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

    @staticmethod
    def semantic_color(name):
        if "trunk" in name:
            return TreeNamingConvention._component_colors["trunk"]
        elif "branch" in name:
            if "L" in name:
                split_name = name.split('-')
                indx = min(int(split_name[1]), len(TreeNamingConvention._component_colors["branch"]) - 1)
                return TreeNamingConvention._component_colors["branch"][indx]
            else:
                return TreeNamingConvention._component_colors["branch"][0]
        elif "spur" in name:
            return TreeNamingConvention._component_colors["spur"]
        else:
            print(f"No known semantic name {name}")
        return (255, 255, 255)

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

    @staticmethod
    def _root_key():
        return TreeNamingConvention.part_names[TreeNamingConvention.ROOT_STOCK]

    @staticmethod
    def _trunk_key():
        return TreeNamingConvention.part_names[TreeNamingConvention.TRUNK]

    @staticmethod
    def _branch_key():
        return TreeNamingConvention.part_names[TreeNamingConvention.BRANCH]

    @staticmethod
    def _spur_key():
        return TreeNamingConvention.part_names[TreeNamingConvention.SPUR]

    def trunk_parts(self):
        return self.part_list[TreeNamingConvention._trunk_key()]

    def branch_parts(self):
        return self.part_list[TreeNamingConvention._branch_key()]

    @staticmethod
    def _part_dictionary(kind:str, id:int, full_name:str, part_name:str, usd_name:str)->dict:
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

        for name in TreeNamingConvention.part_names:
            blank_dict[name] = []

        return blank_dict

    @staticmethod
    def _rootstock_name(has_root_stock: bool)->str:
        if has_root_stock:
            root_stock_name = f"{TreeNamingConvention._root_key()}"
        else:
            root_stock_name = "NoRootStock"
        return root_stock_name

    @staticmethod
    def rootstock_full_name(has_root_stock: bool)->str:
        root_stock_name = TreeNamingConvention._rootstock_name(has_root_stock)
        return root_stock_name

    @staticmethod
    def _trunk_name(trunk_id:int)->str:
        trunk_name = f"{TreeNamingConvention._trunk_key()}Id-{trunk_id}"
        return trunk_name

    @staticmethod
    def trunk_full_name(has_root_stock: bool, trunk_id:int)->str:
        root_stock_name = TreeNamingConvention.rootstock_full_name(has_root_stock)
        trunk_name = TreeNamingConvention._trunk_name(trunk_id=trunk_id)
        return f"{root_stock_name}_{trunk_name}"

    @staticmethod
    def trunk_usd_name(trunk_id:int)->str:
        trunk_usd_name = f"/{TreeNamingConvention._trunk_name(trunk_id=trunk_id)}"
        return trunk_usd_name

    @staticmethod
    def _branch_name(branch_level:int, branch_id:int)->str:
        branch_name = f"{TreeNamingConvention._branch_key()}L-{branch_level}-Id-{branch_id:03d}"
        return branch_name

    @staticmethod
    def branch_full_name(has_root_stock: bool, trunk_id: int, branch_and_parent_ids: list)->str:
        root_stock_name = TreeNamingConvention.rootstock_full_name(has_root_stock)
        trunk_name = f"{TreeNamingConvention._trunk_key()}Id{trunk_id}"
        build_name = f"{root_stock_name}_{trunk_name}"
        for level, id in enumerate(branch_and_parent_ids):
            branch_name = TreeNamingConvention._branch_name(level, id)
            build_name = f"{build_name}_{branch_name}"

        return build_name

    @staticmethod
    def branch_usd_name(trunk_id: int, branch_and_parent_ids: list)->str:
        trunk_usd_name = TreeNamingConvention.trunk_usd_name(trunk_id=trunk_id)
        build_usd_name = f"{trunk_usd_name}"
        for level, id in enumerate(branch_and_parent_ids):
            branch_name = TreeNamingConvention._branch_name(level, id)
            build_usd_name = f"{build_usd_name}/{branch_name}"
        return build_usd_name

    @staticmethod
    def _spur_name(spur_id:int)->str:
        spur_name = f"spurId-{spur_id:04d}"
        return spur_name

    @staticmethod
    def spur_full_name(has_root_stock: bool, trunk_id: int, branch_and_parent_ids: list, spur_id:int)->str:
        root_stock_name = TreeNamingConvention.rootstock_full_name(has_root_stock)
        trunk_name = f"{TreeNamingConvention._trunk_key()}Id{trunk_id}"
        build_name = f"{root_stock_name}_{trunk_name}"
        for level, id in enumerate(branch_and_parent_ids):
            branch_name = TreeNamingConvention._branch_name(level, id)
            build_name = f"{build_name}_{branch_name}"

        spur_name = TreeNamingConvention._spur_name(spur_id=spur_id)
        build_name = f"{build_name}_{spur_name}"
        return build_name

    @staticmethod
    def spur_usd_name(trunk_id: int, branch_and_parent_ids: list, spur_id:int)->str:
        trunk_usd_name = TreeNamingConvention.trunk_usd_name(trunk_id=trunk_id)
        build_usd_name = f"{trunk_usd_name}"
        for level, id in enumerate(branch_and_parent_ids):
            branch_name = TreeNamingConvention._branch_name(level, id)
            build_usd_name = f"{build_usd_name}/{branch_name}"

        spur_name = TreeNamingConvention._spur_name(spur_id=spur_id)
        build_usd_name = f"{build_usd_name}/{spur_name}"
        return build_usd_name

    @staticmethod
    def get_root_stock_id(part_dict: dict)->int:
        return part_dict[TreeNamingConvention._root_key()]

    @staticmethod
    def get_trunk_id(part_dict: dict)->int:
        return part_dict[TreeNamingConvention._trunk_key()]

    def get_parent_id_list(self, part_dict: dict)->list:
        if part_dict["parent_type"] == TreeNamingConvention._trunk_key():
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

    def remove_key(self, key_name: str):
        if TreeNamingConvention._spur_key() in key_name:
            if not key_name in self.part_list[TreeNamingConvention._spur_key()]:
                print(f"Warning, trying to remove a key that doesn't exist {key_name}")
            else:
                del self.part_list[TreeNamingConvention._spur_key()][key_name]
        elif TreeNamingConvention._branch_key() in key_name:
            if not key_name in self.part_list[TreeNamingConvention._branch_key()]:
                print(f"Warning, trying to remove a key that doesn't exist {key_name}")
            else:
                del self.part_list[TreeNamingConvention._branch_key()][key_name]
        elif TreeNamingConvention._trunk_key() in key_name:
            print(f"Warning, removing trunk part {key_name}")
            if not key_name in self.part_list[TreeNamingConvention._trunk_key()]:
                print(f"Warning, trying to remove a key that doesn't exist {key_name}")
            else:
                del self.part_list[TreeNamingConvention._trunk_key()][key_name]

    def new_root(self):
        self.has_root_stock = True

        full_name = TreeNamingConvention.rootstock_full_name(self.has_root_stock)
        root_dict = TreeNamingConvention._part_dictionary(kind=TreeNamingConvention._root_key(),
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
        trunk_dict = TreeNamingConvention._part_dictionary(kind=TreeNamingConvention._trunk_key(),
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
        trunk_dict = self.part_list[TreeNamingConvention._trunk_key()][trunk_name]

        full_name = self.branch_full_name(has_root_stock=self.has_root_stock, trunk_id=trunk_id, branch_and_parent_ids=branch_and_parent_ids)
        usd_name = self.branch_usd_name(trunk_id=trunk_id, branch_and_parent_ids=branch_and_parent_ids)
        branch_name = TreeNamingConvention._branch_name(level, self.current_branch[level])
        branch_dict = TreeNamingConvention._part_dictionary(kind=TreeNamingConvention._branch_key(),
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
        spur_dict = TreeNamingConvention._part_dictionary(kind=TreeNamingConvention._spur_key(),
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
