"""
Keeping skeleton data for tree structures

This module provides utilities for keeping skeletoal meta-data structure information. It both stores the skeletal
information and links mesh vertices/faces to skeleton components.

Because most tree skeletons are made out of cylinders or some sort of swept surface, and we want to tie the skeleton
to the mesh/point cloud geometry, the decision was made to keep the skeleton as a sequence of simplified cylinders
(a centroid with a vector and a radius) with the end points of the skeleton derived from that data

One skeleton component corresponds to a trunk or a branch in the naming_convention scheme

Data kept for the skeleton (if available)
- Skeleton is separated into a sequence of centroids + vectors
- At each centroid, the radius of the cylinder at that point
- t value (percentage along the skeleton)
- A coordinate system with one vector pointing along the cylinder and the second pointing in the direction of the seam
- mesh faces and vertices (or point cloud) that correspond to each segment

"""
import numpy as np
from enum import Enum


class JunctionComponent:
    class JunctionType(Enum):
        PRUNED = "pruned"
        BUD = "bud"
        BRANCH = "branch"
        SPUR = "spur"
        BRANCH_AND_SPUR = "branch_and_spur"

    def __init__(self):
        self.t_along = 0.0
        self.theta_around = 0.0
        self.pt_attach = (0, 0, 0)
        self.vec_along_parent = (0, 0, 0)
        self.vec_branch = (0, 0, 0)
        self.prev_section_height = 0
        self.ang_attach = 0.0   # Angle from dot product at attach point
        self.radius = 0.0
        self.parent_name = ""
        self.child_name = ""
        self.type: JunctionComponent.JunctionType = JunctionComponent.JunctionType.BUD

    def create_dict(self) -> dict:
        ret_dict = {"t_along": self.t_along,
                    "theta_around": self.theta_around,
                    "pt_attach": self.pt_attach,
                    "vec_along_parent": self.vec_along_parent,
                    "vec_branch": self.vec_branch,
                    "ang_attach": self.ang_attach,
                    "radius": self.radius,
                    "parent_name": self.parent_name,
                    "child_name": self.child_name,
                    "type": str(self.type)}
        return ret_dict

    def set_from_dict(self, in_dict: dict):
        self.t_along = in_dict["t_along"]
        self.theta_around = in_dict["theta_around"]
        self.pt_attach = in_dict["pt_attach"]
        self.vec_along_parent = in_dict["vec_along_parent"]
        self.vec_branch = in_dict["vec_branch"]
        self.ang_attach = in_dict["ang_attach"]
        self.radius = in_dict["radius"]
        self.parent_name = in_dict["parent_name"]
        self.child_name = in_dict["child_name"]
        # TODO: Fix this
        self.type = JunctionComponent.JunctionType(in_dict["type"])


class SkeletonComponent:
    def __init__(self, name:str):
        self.name = name
        # Computed from bud sites
        self.centroids = []
        self.radii = []
        self.t_values = []
        # Set when parsing branch hierarchy
        self.start_pt = (0, 0, 0)
        self.start_vec = (1, 0, 0)
        self.end_pt = (0, 0, 0)
        self.length = 0.0
        self.child_junctions = []
        # Computed after cylinders are processed

    def add_junction(self, child_component: JunctionComponent):
        self.child_junctions.append(child_component)

    def create_dict(self) ->dict:
        ret_dict = {}
        ret_dict["name"] = self.name
        ret_dict["centroids"] = self.centroids
        ret_dict["radii"] = self.radii
        ret_dict["start_pt"] = self.start_pt
        ret_dict["start_vec"] = self.start_vec
        ret_dict["end_pt"] = self.end_pt
        ret_dict["t_values"] = self.t_values
        ret_dict["length"] = self.length
        ret_dict["child_junctions"] = []
        for child in self.child_junctions:
            ret_dict["child_junctions"].append(child.create_dict())
        return ret_dict

    def set_from_dict(self, in_dict: dict):
        self.name = in_dict["name"]
        self.centroids = in_dict["centroids"]
        self.radii = in_dict["radii"]
        self.start_pt = in_dict["start_pt"]
        self.start_vec = in_dict["start_vec"]
        self.end_pt = in_dict["end_pt"]
        self.t_values = in_dict["t_values"]
        self.length = in_dict["length"]
        self.child_junctions = []
        for child_dict in in_dict["child_junctions"]:
            child = JunctionComponent()
            child.set_from_dict(child_dict)
            self.child_junctions.append(child)
