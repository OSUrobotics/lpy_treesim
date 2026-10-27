#supress file print statements
print = lambda *args, **kwargs: None

"""
General-purpose routines to turn the plantgl mesh structures into meshes
Opting to force cylinders to be less than a certain size (see IMakeCylinders in base_lpy.lpy) and NOT to use generalized
cylinders. This means the cylinders are disconnected (the end vertices of one cylinder might not line up exactly with
the start of the next if there's a twist). Fix this by stitching the cyliners back together.
Also does texture map coordinates in one of two ways:
s is always 0 to one around the tube, with the 0 value being the left vector of the lpy system
option 1: 0-1 along the length of the tube
option 2: repeat 0,1 so that t cycles at a distance 2 pi r of the radius.

Uses trimesh to write the meshes out in obj and ply format.
Sadly, it doesn't seem to support doing vertex and face and texture map coords, so write out
a bunch of meshes (fc - faces colored by type, vc - vertices colored by type,
   tm is for regular texture mapping (tiling), uv is option 1 (v runs 0, 1)
Also, obj only supports face colors or texture map coordinates
"""
import openalea.plantgl as plantgl
import openalea.plantgl.scenegraph as sg
import openalea.plantgl.algo as alg

from lpy_treesim.tree_generation.tree_naming_convention import TreeNamingConvention
from lpy_treesim.tree_generation.tree_structure import TreeStructure
from lpy_treesim.utils.color_manager import ColorManager
import numpy as np
from trimesh import Trimesh
from trimesh.visual import TextureVisuals


def _add_cylinder(centerline_dict: dict, vs: list) -> np.array:
    vs_as_np = np.array(vs)
    centroid = np.mean(vs_as_np, axis=0)
    # Really annoying to cast to float, but otherwise json doesn't work
    centerline_dict["centroids"].append((float(centroid[0]), float(centroid[1]), float(centroid[2])))
    x_vec = vs_as_np[0, :] - centroid
    x_vec = x_vec / np.linalg.norm(x_vec)
    radius = float(np.linalg.norm(vs_as_np[0, :] - centroid[:]))
    centerline_dict["radii"].append(radius)
    return x_vec


def _compute_t_values(centerline_dict: dict):
    """ Call AFTER all cylinders have been added"""
    # Really annoying to cast to float, but otherwise json doesn't work

    centroids = centerline_dict["centroids"]
    centers_as_np = np.array(centroids)

    vec_to_first_pt = centers_as_np[1, :] - centers_as_np[0, :]
    len_vec = np.linalg.norm(vec_to_first_pt)
    if np.isclose(len_vec, 0.0):
        print(f"Warning, zero length vec in _compute_t_values")

    dists = np.zeros(len(centroids))
    for indx in range(0, len(centroids) - 1):
        start_pt = centers_as_np[indx, :]
        end_pt = centers_as_np[indx + 1, :]
        dist = np.linalg.norm(end_pt - start_pt)
        dists[indx + 1] = dist

    centerline_dict["length"] = float(np.sum(dists))
    if centerline_dict["length"] > 0.0:
        dists = dists / centerline_dict["length"]
    centerline_dict["t_values"] = []
    dist_sum = dists[0]
    for dist in dists[1:]:
        centerline_dict["t_values"].append(float(dist_sum))
        dist_sum += dist


def _stitch_cylinder(cyls: list, col_plant_type: tuple, col_instance: tuple) -> (dict, dict):
    """Takes in a list of cylinders (should be in order along the trunk/branch) and makes a single mesh out of it
    Merges the vertices from the previous row with the next to make the mesh seamless
    Adds texture map coordinates
    Applies the color for semantic labeling (eg branch, spur, trunk) to the vertex colors
    Applies the color for instance labeling (eg branch 32) to the face colors
    @param cyls - the list of cylinders with vertices, faces
    @param col_plant_type - the semantic color of the plant, from TreeNamingConvention
    @param col_instance - the semantic color for the instance, from TreeNamingConvention
    @return the stitched together mesh as vertices and faces, texture coordinates, and vertex/face colors"""

    # Vertices and faces come from the original cylinders; only keep the first ring of vertices from each
    #   cylinder to mesh is stitched together
    # Vertex colors are set by plont part type, face colors by a unique color for each instance
    # In the first draft, the u coordinates of the texture are set correctly but the v (vertical) are not
    mesh_component = {"vertices": [],
                      "vertex_colors": [],
                      "faces": [],
                      "textures": [],
                      "uv_textures": [],
                      "face_colors": [],
                      "scale_texture": 1.0}

    offset = 0
    v_delta = 1.0 if len(cyls) == 1 else 1.0 / (len(cyls) - 1.0)
    v_coord = 0.0
    n_split = 8   # Will be over-ridden

    centerline_dict = {"centroids": [],
                       "radii": [],
                       "x_vecs": [],
                       "y_vecs": [],
                       "z_vecs": [],
                       "t_values": [],
                       "length": 0}
    for cyl in cyls:
        # mesh cylinders that come out of lpy alternate vertices in each ring
        n_split = len(cyl["vertices"]) // 2
        s_div = 1.0 / (n_split - 1.0)
        for vi in range(0, n_split):
            mesh_component["vertices"].append(cyl["vertices"][2 * vi])
            mesh_component["vertex_colors"].append(col_plant_type)
            mesh_component["textures"].append((vi * s_div, v_coord))
            mesh_component["uv_textures"].append((vi * s_div, v_coord))
        v_coord += v_delta

        # Calculate the center and radii of the cylinder
        x_vec = _add_cylinder(centerline_dict, mesh_component["vertices"][-n_split:])
        centerline_dict["x_vecs"].append(x_vec)

        # Re-do the face vertices so they do ring one ring two
        #   Note that these are quads. TriMesh will split to triangles
        for ind, fi in enumerate(cyl["faces"]):
            face = []
            for face_id in fi:
                n_around = face_id // 2
                which_side = face_id % 2
                face.append(offset + which_side * n_split + n_around)

            mesh_component["faces"].append(face)
            mesh_component["face_colors"].append(col_instance)

        offset += len(cyl["vertices"]) // 2
        # print(f"v {cyl['vertices'][0]} {cyl['vertices'][1]}")

    # And add in the last ring of vertices
    cyl = cyls[-1]
    for vi in range(0, len(cyl["vertices"]) // 2):
        n_split = len(cyl["vertices"]) // 2
        s_div = 1.0 / (n_split - 1.0)
        # Take the second ring, not the first
        mesh_component["vertices"].append(cyl["vertices"][2 * vi + 1])
        mesh_component["vertex_colors"].append(col_plant_type)
        mesh_component["textures"].append((vi * s_div, v_coord))
        mesh_component["uv_textures"].append((vi * s_div, v_coord))

    _add_cylinder(centerline_dict, mesh_component["vertices"][-n_split:])

    # Now fix the t texture values so they are roughly spaced based on the length
    _compute_t_values(centerline_dict)   # Calculate the length and t values based on each cylinder
    radii = 0.5 * (centerline_dict["radii"][0] + centerline_dict["radii"][-1])  # Average radius
    circum = 2.0 * np.pi * radii
    scl_t_values = centerline_dict["length"] / (2.0 * circum)   # Texture is twice as tall as wide
    tex_offset = np.random.uniform(0.0, 1.0)
    for n_rings, t_val in enumerate(centerline_dict["t_values"]):
        # This does a random offset of the texture - this is for tiling textures
        tex_v_value = tex_offset + t_val * scl_t_values
        for indx in range(0, n_split):
            tex_coord = mesh_component["textures"][n_rings * n_split + indx]
            # Texture map coords for coloring the mesh - these tile to avoid stretching the texture
            mesh_component["textures"][n_rings * n_split + indx] = (tex_coord[0], tex_v_value)
            # Special-purpose texture coords for extracting the length and theta value from the texture color
            mesh_component["uv_textures"][n_rings * n_split + indx] = (tex_coord[0], t_val)

    centroids = centerline_dict["centroids"]
    for indx, centroid in enumerate(centroids[0:-1]):
        z_vec = np.zeros((3,))
        for j in range(0, 3):
            z_vec[j] = centroids[indx+1][j] - centroid[j]
        len_z_vec = np.linalg.norm(z_vec)
        z_vec = z_vec / len_z_vec
        centerline_dict["z_vecs"].append(z_vec)
        x_vec = centerline_dict["x_vecs"][indx]
        y_vec = np.cross(z_vec, x_vec)
        len_y_vec = np.linalg.norm(y_vec)
        y_vec = y_vec / len_y_vec
        centerline_dict["y_vecs"].append(y_vec)
        assert np.isclose(np.dot(x_vec, z_vec), 0.0)
        assert np.isclose(np.dot(x_vec, y_vec), 0.0)
        assert np.isclose(np.dot(y_vec, z_vec), 0.0)
        assert np.isclose(np.dot(x_vec, x_vec), 1.0)
        assert np.isclose(np.dot(y_vec, y_vec), 1.0)
        assert np.isclose(np.dot(z_vec, z_vec), 1.0)
    return mesh_component, centerline_dict


def stitch_cylinders(tree: TreeStructure) -> (dict, list):

    # Keep track of any tree components that do not have any mesh parts
    keys_to_remove = []

    color_to_part = {"semantic": {}, "instance": {}}
    for part_dict in tree.iterate_all_wood_parts():
        if len(part_dict["mesh_cyl"]) > 0:
            col_plant_type = TreeNamingConvention.semantic_color(part_dict["name"])
            col_instance = tree.instance_color(part_dict["name"])
            color_to_part["semantic"][str(col_plant_type)] = part_dict["full_name"]
            color_to_part["instance"][str(col_instance)] = part_dict["full_name"]
            part_dict["mesh"], part_dict["centerline"] = _stitch_cylinder(cyls=part_dict["mesh_cyl"],
                                                                          col_plant_type=col_plant_type,
                                                                          col_instance=col_instance)
        else:
            if part_dict['type'] == TreeNamingConvention._root_key():
                continue
            keys_to_remove.append(part_dict["name"])
            print(f"Part {part_dict['name']} has no mesh, removing")

    return color_to_part, keys_to_remove


# from https://pymeshlab.readthedocs.io/en/latest/tutorials/import_mesh_from_arrays.html
def create_mesh(tree: TreeStructure, bud_sites: list[dict], tex_image_file_name) -> (Trimesh, Trimesh, Trimesh, Trimesh, Trimesh):
    """ Put all the cylinders into one big TriMesh file
    Because TriMesh only supports adding one material (either texture coords, face colors, or vertex colors)
    this actually returns three meshes
    @param tree - the actual tree parts
    @tex_image_file_name - the filename of the texture map
    """
    vs = []
    vs_tex = []
    vs_tex_uv = []
    vs_col = []
    faces = []
    face_cols = []
    v_offset = 0

    part_dicts = []
    for part_dict in tree.iterate_all_wood_parts():
        part_dicts.append(part_dict["mesh"])
    for mc in part_dicts:
        if mc is None:
            continue

        for v in mc["vertices"]:
            vs.append(v)
        for t in mc["textures"]:
            vs_tex.append(t)
        for t in mc["uv_textures"]:
            vs_tex_uv.append(t)
        for c in mc["vertex_colors"]:
            # trimesh likes alpha
            vs_col.append([c[0], c[1], c[2], 255])
        for f, f_col in zip(mc["faces"], mc["face_colors"]):
            face = []
            for fid in f:
                face.append(fid + v_offset)
            face_cols.append([f_col[0], f_col[1], f_col[2], 255])
            faces.append(face)
            if len(face) == 4:
                # trimesh will split faces on load
                face_cols.append([f_col[0], f_col[1], f_col[2], 255])

        v_offset += len(mc["vertices"])

    if len(vs) == 0:
        print(f"Warning: No mesh parts, bailing")
        return None, None, None

    vs_np = np.array(vs, dtype=np.float64)
    vs_tex_np = np.array(vs_tex, dtype=np.float32)
    vs_tex_uv_np = np.array(vs_tex_uv, dtype=np.float32)
    vs_cols_np = np.array(vs_col, dtype=np.uint8)
    fs_np = np.array(faces, dtype=np.int64)
    fs_cols_np = np.array(face_cols, dtype=np.uint8)
    print(f"N vertices {vs_np.shape[0]}")
    print(f"N faces {fs_np.shape[0]} {fs_cols_np.shape}max {np.max(fs_np)}")

    #texs = TextureVisuals(uv=vs_tex_np, image=tex_image_file_name)
    #texs_uv = TextureVisuals(uv=vs_tex_uv_np, image=tex_image_file_name)
    texs = TextureVisuals(uv=vs_tex_np)
    texs_uv = TextureVisuals(uv=vs_tex_uv_np)
    # Initialize with texture map coordinates for each vertex, no face or vertex color
    mesh_tm = Trimesh(vertices=vs_np, faces=fs_np, visual=texs)
    # Initialize with texture map coordinates for each vertex, no face or vertex color
    mesh_uv = Trimesh(vertices=vs_np, faces=fs_np, visual=texs_uv)
    # Initialize with colors for each face (colors are instance - eg trunk 0, branch 20)
    mesh_fc = Trimesh(vertices=vs_np, faces=fs_np, face_colors=fs_cols_np)
    # Initialize with colors for each vertex (colors are semantic - eg, trunk, branch,...)
    mesh_vc = Trimesh(vertices=vs_np, faces=fs_np, vertex_colors=vs_cols_np)
    # mesh_tex = trimesh.visual.texture.Tex

    for mc in bud_sites:
        if mc is None:
            continue

        for v in mc["vertices"]:
            vs.append(v)
        for c in mc["vertex_colors"]:
            # trimesh likes alpha
            vs_col.append([c[0], c[1], c[2], 255])
        for f in mc["faces"]:
            face = []
            for fid in f:
                face.append(fid + v_offset)
            faces.append(face)

        v_offset += len(mc["vertices"])
    # Add the bud geometry
    vs_np = np.array(vs, dtype=np.float64)
    vs_cols_np = np.array(vs_col, dtype=np.uint8)
    fs_np = np.array(faces, dtype=np.int64)
    mesh_budsites = Trimesh(vertices=vs_np, faces=fs_np, vertex_colors=vs_cols_np)

    return mesh_tm, mesh_uv, mesh_fc, mesh_vc, mesh_budsites


# Convert the PlantGL to a list of vertices and faces
def plant_gl_scene_to_vertices_and_faces(scene, mapping_tree_structure: dict, color_mapping: ColorManager) -> list[dict]:
    """ extract vertices and faces from a plantGL scene graph.
       The vertices/faces will be stored in the appropriate tree component
    @param mapping_tree_structure - lpy branch part names to tree parts
    @param color_mapping - colors to lpy branch parts"""
    d = alg.Discretizer()

    # Hold the bud sites (if any)
    bud_sites = []

    for item in scene:
        # Skip things that are not cylinders
        if not item.apply(d):
            continue

        p = d.result
        if not isinstance(p, plantgl.scenegraph._pglsg.QuadSet):
            continue

        # The vertices and faces from the cylinder
        pts = p.pointList
        face = p.indexList
        n = len(p.pointList)
        if n == 0:
            print(f"Warning: Empty cylinder")
            continue


        # Use this trick to get the tree component part back
        color = item.appearance.diffuseColor()

        # A bit roundabout - but use the color to get the lpy name, and the lpy name to get the tree part
        r, g, b = color
        unique_color = (r, g, b)
        hierarchy_name = color_mapping.color_to_name[unique_color]
        if "bud" in hierarchy_name:
            tree_part_dict = {}
        else:
            tree_part_dict = mapping_tree_structure[hierarchy_name]

        # Store the points and the faces
        mesh_component = {"vertices":[], "faces":[]}
        for v_id, pt in enumerate(pts):
            # pt_swap_y_z = [pt[0], pt[2], pt[1]]
            mesh_component["vertices"].append(pt)
        for j in face:
            flatten_f = list(map(lambda x: x, j))
            mesh_component["faces"].append(flatten_f)

        if n != 16:
            # Unless someone changes it, the default radial resolution of the cylinders should be 16
            raise ValueError(f"Diff number of vs {n}")

        if "bud" in hierarchy_name:
            bud_color = TreeNamingConvention.semantic_color("bud")
            mesh_component["textures"] = []
            mesh_component["uv_textures"] = []
            mesh_component["vertex_colors"] = []
            mesh_component["face_colors"] = []
            for indx in range(0, len(mesh_component["vertices"])):
                dt = (indx % n) / n
                mesh_component["textures"].append((float(indx // n), dt))
                mesh_component["uv_textures"].append((float(indx // n), dt))
                mesh_component["vertex_colors"].append(bud_color)
            for indx in range(0, len(mesh_component["faces"])):
                mesh_component["face_colors"].append(bud_color)
            bud_sites.append(mesh_component)
        else:
            # Most of the plant parts are made of multiple cylinders which we'll stitch together later
            tree_part_dict["mesh_cyl"].append(mesh_component)
    return bud_sites


def write_mesh(fname: str, tree: TreeStructure, bud_sites: list[dict], image_name: str):
    # Use TriMesh to write out the mesh in a handful of forms
    #  - tm texture mapping coordinates
    #  - fc faces colored by semantic labels
    #  - vc vertices colored by instance labels
    mesh_tm, mesh_uv, mesh_fc, mesh_vc, mesh_bud_sites = create_mesh(tree=tree, bud_sites=bud_sites, tex_image_file_name=image_name)
    if mesh_tm is not None:
        mesh_tm.export(str(fname) + "_tm.obj")
        mesh_tm.export(str(fname) + "_tm.ply")
    if mesh_uv is not None:
        mesh_uv.export(str(fname) + "_uv.obj")
        mesh_uv.export(str(fname) + "_uv.ply")
    if mesh_fc is not None:
        mesh_fc.export(str(fname) + "_fc.ply")
        mesh_fc.export(str(fname) + "_fc.obj")
    if mesh_vc is not None:
        mesh_vc.export(str(fname) + "_vc.obj")
        mesh_vc.export(str(fname) + "_vc.ply")
    if mesh_bud_sites is not None:
        mesh_bud_sites.export(str(fname) + "_budsites.obj")
        mesh_bud_sites.export(str(fname) + "_budsites.ply")
