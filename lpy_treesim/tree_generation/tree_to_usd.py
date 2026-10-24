from pxr import Usd, UsdGeom, Gf, UsdSemantics, Sdf, UsdShade, Ar, UsdPhysics

from lpy_treesim.tree_generation.skeleton_components import JunctionComponent, SkeletonComponent
from lpy_treesim.tree_generation.tree_naming_convention import TreeNamingConvention
from lpy_treesim.tree_generation.tree_structure import TreeStructure

import math


def create_labeled_asset(file_path):
    # NOT USED - EXAMPLE CODE FOR SEMANTIC LABELING
    # 1. Create a new Stage
    stage = Usd.Stage.CreateNew(file_path)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    # 2. Create your Mesh or Xform
    root_path = "/MyLabeledObject"
    mesh_prim = UsdGeom.Mesh.Define(stage, root_path)

    # 3. Apply the SemanticsAPI
    # The 'instanceName' (second arg) is usually "class" for Isaac Sim
    semantics_api = UsdSemantics.SemanticsAPI.Apply(mesh_prim.GetPrim(), "class")

    # 4. Set the attributes that Isaac Sim's annotators read
    # semanticType: Defines the category (usually 'class')
    # semanticData: Defines the specific label (e.g., 'engine_part')
    semantics_api.CreateSemanticTypeAttr().Set("class")
    semantics_api.CreateSemanticDataAttr().Set("engine_part")

    # Do twice to get two different labelings
    semantics_api.CreateSemanticTypeAttr().Set("class II")
    semantics_api.CreateSemanticDataAttr().Set("engine_part")

    # Save the stage
    stage.GetRootLayer().Save()
    print(f"Asset created at: {file_path}")


def check_texture(stage_context):
    # TESTING CODE FOR TEXTURE - This is mostly to check that
    #   the stage_context is set up correctly and can access the texture files
    # Also has examples of setting material properties
    with Ar.ResolverContextBinder(stage_context):
        # 1. Create a new USD stage
        # Set the up axis and units
        stage = Usd.Stage.CreateInMemory()
        #stage = Usd.Stage.CreateNew("test_texture.usda")
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)

        # 2. Define the Mesh primitive
        mesh = UsdGeom.Mesh.Define(stage, '/tree_texture_check')

        # 2. Define Texture Coordinates (UVs)
        # We use 'st' as the name.
        # 'interpolation' determines how UVs map to the geometry.
        tex_coords = UsdGeom.PrimvarsAPI(mesh).CreatePrimvar(
            "st",
            Sdf.ValueTypeNames.TexCoord2fArray,
            UsdGeom.Tokens.varying
        )

        # 2. Create the Material
        material_path = Sdf.Path("/textures/pine_bark_vmbibe2g_2k")
        material = UsdShade.Material.Define(stage, material_path)

        # 3. Create the Shader (UsdPreviewSurface)
        shader = UsdShade.Shader.Define(stage, material_path.AppendChild("PBRShader"))
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.4)

        # 4. Create the Texture Sampler (UsdUVTexture)
        reader = UsdShade.Shader.Define(stage, material_path.AppendChild("TexSampler"))
        reader.CreateIdAttr("UsdUVTexture")
        reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set("/textures/Pine_Bark_vmbibe2g_2K_BaseColor.jpg")
        # Connect texture output to shader's diffuseColor input
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
            reader.CreateOutput("rgb", Sdf.ValueTypeNames.Color3f))

        # 5. Create the Primvar Reader (To tell the texture to use 'st')
        st_reader = UsdShade.Shader.Define(stage, material_path.AppendChild("STReader"))
        st_reader.CreateIdAttr("UsdPrimvarReader_float2")
        st_reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")
        # Connect reader output to texture sampler's st input
        reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
            st_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2))

        # 6. Bind the Material to the Mesh
        UsdShade.MaterialBindingAPI(mesh).Bind(material)
        # 6. Save the stage
        #print(stage.GetRootLayer().ExportToString())
        stage.GetRootLayer().Export("tree_texture_check.usda")


def make_mesh_from_components(mesh_usd, tree_parts : dict, b_use_uv=False):
    """ Sets up the vertices, texture coordinates, faces"""
    mesh_parts = tree_parts["mesh"]
    # Vertices, texture coords for vs, and faces
    vs = []
    vs_texs = []
    # Not really sure we need to do this, but otherwise have trouble with the USD call
    if b_use_uv:
        use_texs = mesh_parts["uv_textures"]
    else:
        use_texs = mesh_parts["textures"]
    for pt, tex in zip(mesh_parts["vertices"], use_texs):
        # Fill in vertex/texture lists
        vs.append((pt[0], pt[1], pt[2]))
        vs_texs.append((tex[0], tex[1]))

    face_counts = []
    face_indices = []
    for face in mesh_parts["faces"]:
        face_counts.append(len(face))
        face_vs = []
        for idx in face:
            face_vs.append(idx)
        face_indices.append(face_vs)

    # I don't know if you need to do this, but it balks otherwise
    vs_ind_gen = [(pt[0], pt[1], pt[2]) for pt in vs]
    mesh_usd.CreatePointsAttr(vs_ind_gen)
    mesh_usd.CreateFaceVertexCountsAttr(face_counts)

    # Convert face_indices into a generator
    face_ind_gen = [idx for face in face_indices for idx in face]
    mesh_usd.CreateFaceVertexIndicesAttr(face_ind_gen)

    # Add Texture Coordinates (UVs)
    # 'st' is now the standard name to use for storing texture coordinates
    #   Isaac sim is suppose to allow other names, but it doesn't
    # 'interpolation' determines how UVs map to the geometry - we want a wrap
    tex_coords = UsdGeom.PrimvarsAPI(mesh_usd).CreatePrimvar(
        "st",
        Sdf.ValueTypeNames.TexCoord2fArray,
        UsdGeom.Tokens.varying
    )
    # Set the UV values that tile along the mesh
    # These correspond to the points defined above: (u, v)
    ts_ind_gen = [(pt[0], pt[1]) for pt in vs_texs]
    tex_coords.Set(ts_ind_gen)

    # No subdivision, please
    mesh_usd.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)

    if "skel" in tree_parts:
        skel = tree_parts["skel"]
        if skel.radii[0] > 0.2:
            # Use catmul clark on big radii branches
            mesh_usd.CreateSubdivisionSchemeAttr().Set("catmulClark")


def create_material_look(stage, material_path, file_dir="../textures/pine_bark_vmbibe2g_2k/"):
    # Give the material a unique USD name
    material = UsdShade.Material.Define(stage, material_path)

    # Create the Shader (UsdPreviewSurface)
    shader = UsdShade.Shader.Define(stage, material_path.AppendChild("PBRShader"))
    shader.CreateIdAttr("UsdPreviewSurface")
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    # Create the ST Coordinates Reader (Primvar Reader)
    coord_reader = UsdShade.Shader.Define(stage, material_path.AppendChild("StReader"))
    coord_reader.CreateIdAttr("UsdPrimvarReader_float2")
    coord_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")

    # Helper function to add texture files to the appropriate shader attributes
    def add_texture_file(name, file_path, input_name, type_name):
        tex = UsdShade.Shader.Define(stage, material_path.AppendChild(name))
        tex.CreateIdAttr("UsdUVTexture")
        
        # Make wrap in s and tile in t
        tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
        tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")

        # Use st
        tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(coord_reader.ConnectableAPI(), "result")

        # Which file
        tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(file_path)

        # Connect texture output to shader input
        if "Color" in input_name or "Normal" in input_name:
            shader.CreateInput(input_name, type_name).ConnectToSource(tex.ConnectableAPI(), "rgb")
        else:
            shader.CreateInput(input_name, type_name).ConnectToSource(tex.ConnectableAPI(), "r")
            
        return tex

    # Diffuse color
    add_texture_file("DiffuseTex", file_dir + "Pine_Bark_vmbibe2g_2K_BaseColor.jpg", "diffuseColor", Sdf.ValueTypeNames.Color3f)

    # Normal Mapping
    add_texture_file("NormalTex", file_dir + "Pine_Bark_vmbibe2g_2K_Normal.jpg", "normal", Sdf.ValueTypeNames.Normal3f)

    # Bump/Displacement Mapping
    add_texture_file("BumpTex", file_dir + "Pine_Bark_vmbibe2g_2K_Bump.jpg", "displacement", Sdf.ValueTypeNames.Float)

    # Roughness
    add_texture_file("RoughnessTex", file_dir + "Pine_Bark_vmbibe2g_2K_Roughness.jpg", "roughness", Sdf.ValueTypeNames.Float)

    # I am not sure what these images in the pinebark texture should map to
    #add_texture_file("CavityTex", file_dir + "Pine_Bark_vmbibe2g_2K_Cavity.jpg", "cavity", Sdf.ValueTypeNames.Float)
    #add_texture_file("SpecularTex", file_dir + "Pine_Bark_vmbibe2g_2K_Specular.jpg", "specular", Sdf.ValueTypeNames.Float)
    #add_texture_file("GlossTex", file_dir + "Pine_Bark_vmbibe2g_2K_Gloss.jpg", "gloss", Sdf.ValueTypeNames.Float)

    return material


def _cyl_name(path_name: str, index: int):
    return f"{path_name}_cyl_{index}"

def _add_collision_cylinder(stage,
                            path: Sdf.Path,
                            skel: SkeletonComponent,
                            centerline: dict,
                            indx: int):
    # How much "fatter" to make the cylinders than the underlying tree geometry
    scl_factor = 1.05

    # Ratio of area of 1 m^3 to mass in kilo grams
    area_mass = 1000

    # Make the xform
    cyl_path = path.AppendChild(_cyl_name(skel.part_name, indx))
    cyl_xform = UsdGeom.Xform.Define(stage, cyl_path)
    cyl_shape = UsdGeom.Cylinder.Define(stage, cyl_path.AppendChild("Collider"))
    # Make it a rigid body
    UsdPhysics.RigidBodyAPI.Apply(cyl_xform.GetPrim())

    # Get the orientation, height, scale
    centroids = centerline["centroids"]
    radii = centerline["radii"]
    pt_start = Gf.Vec3d(centroids[indx])
    pt_end = Gf.Vec3d(centroids[indx + 1])
    vec_axis = pt_end - pt_start
    height = vec_axis.GetLength()
    skel.heights.append(height)
    if height <= 0.0:
        print(f"Warning making usd skeleton: Height zero {skel.part_name}")
        height = 0.001
    midpoint = pt_start + vec_axis * 0.5

    if radii[indx] < 0.0:
        print("Oops")
    # Radius and height
    cyl_shape.CreateRadiusAttr(radii[indx] * scl_factor)
    cyl_shape.CreateHeightAttr(height)

    # Align along z axis
    cyl_shape.CreateAxisAttr("Z")
    x_axis = centerline["x_vecs"][indx]
    x_axis = Gf.Vec3d(x_axis[0], x_axis[1], x_axis[2])
    y_axis = centerline["y_vecs"][indx]
    y_axis = Gf.Vec3d(y_axis[0], y_axis[1], y_axis[2])
    z_axis = centerline["z_vecs"][indx]
    z_axis = Gf.Vec3d(z_axis[0], z_axis[1], z_axis[2])
    rot_matrix = Gf.Matrix3d(
        x_axis[0], x_axis[1], x_axis[2],
        y_axis[0], y_axis[1], y_axis[2],
        z_axis[0], z_axis[1], z_axis[2]
    )

    rotation: Gf.Rotation = rot_matrix.ExtractRotation()
    quat = rotation.GetQuat()

    if indx == 0:
        skel.rotations.append(rotation)
        skel.euler_angles.append(rotation.Decompose(x_axis, y_axis, z_axis))
    else:
        prev_rotation: Gf.Rotation = skel.rotations[-1]
        from_prev_rotation: Gf.Rotation = prev_rotation.GetInverse() * rotation
        skel.rotations.append(rotation)
        skel.euler_angles.append(from_prev_rotation.Decompose(x_axis, y_axis, z_axis))

    # rotate and translate to correct location
    cyl_xform.AddTranslateOp().Set(midpoint)
    # I do not know why you have to cast to a float, but you do...
    cyl_xform.AddOrientOp().Set(Gf.Quatf(quat))

    # Color by type
    color_attr = cyl_shape.CreateDisplayColorAttr()
    col_tuple = skel.color
    col = Gf.Vec3f(col_tuple[0] / 255.0, col_tuple[1] / 255.0, col_tuple[2] / 255.0)
    color_attr.Set([col])  # Based on type

    # Add collision physics
    UsdPhysics.CollisionAPI.Apply(cyl_shape.GetPrim())

    # Mass by area
    area = 2.0 * math.pi * skel.radii[indx] * height
    cyl_mass = UsdPhysics.MassAPI.Apply(cyl_xform.GetPrim())
    skel.mass = area * area_mass
    cyl_mass.CreateMassAttr(area * area_mass)


def _add_hinge_joint(stage,
                     path: Sdf.Path,
                     skel: SkeletonComponent,
                     indx: int):

    name = f'{skel.part_name}_joint_{indx-1}_{indx}'
    joint_path = path.AppendChild(name)
    joint = UsdPhysics.RevoluteJoint.Define(stage, joint_path)

    # Establish connection paths between rigid body nodes
    cyl_left_name = _cyl_name(skel.part_name, indx-1)
    cyl_right_name = _cyl_name(skel.part_name, indx)
    joint.CreateBody0Rel().SetTargets([cyl_left_name])
    joint.CreateBody1Rel().SetTargets([cyl_right_name])

    # Anchor pivot frames
    # Anchor points based on ending point of last cylinder
    prev_height = skel.heights[indx-1]
    height = skel.heights[indx]
    joint.GetLocalPos0Attr().Set(Gf.Vec3d(0.0, 0.0, -prev_height * 0.5))
    joint.GetLocalPos1Attr().Set(Gf.Vec3d(0.0, 0.0, height * 0.5))

    # Create springs and target angles for the x and y rotation angles
    # the rotattion around z (twist) is very stiff
    level = skel.level
    angs = skel.euler_angles[indx]
    for ang, axis in zip(angs, ["rotX", "rotY", "rotZ"]):
        # This is the limit
        swing_limit = UsdPhysics.LimitAPI.Apply(joint.GetPrim(), axis)
        # This is used to set the desired angle
        spring_drive = UsdPhysics.DriveAPI.Apply(joint.GetPrim(), axis)
        spring_drive.CreateTypeAttr("position")

        # Set the non-zero target angle here
        spring_drive.CreateTargetPositionAttr(ang)

        # Now set the limits
        if axis == "rotZ":
            # Limit twist
            swing_limit.CreateLowAttr(ang - 0.01)
            swing_limit.CreateHighAttr(ang + 0.01)
            # Make stiff
            spring_drive.CreateStiffnessAttr(1000.0)  # K constant (Spring stiffness)
            spring_drive.CreateDampingAttr(0.15)  # B constant (Resistive damping)
        else:
            if level == 0:
                swing_limit.CreateLowAttr(ang - 10.0)
                swing_limit.CreateHighAttr(ang + 10.0)
            elif level == 1:
                swing_limit.CreateLowAttr(ang - 20.0)
                swing_limit.CreateHighAttr(ang + 20.0)
            elif level > 1:
                swing_limit.CreateLowAttr(ang - 45.0)
                swing_limit.CreateHighAttr(ang + 45.0)
            else:
                swing_limit.CreateLowAttr(ang - 0.1)
                swing_limit.CreateHighAttr(ang + 0.1)

            # Make not too stiff
            spring_drive.CreateStiffnessAttr(100.0)  # K constant (Spring stiffness)
            spring_drive.CreateDampingAttr(0.15)  # B constant (Resistive damping)


def create_skeleton_geometry(stage, parent_path: str, tree: TreeStructure, level_limit: int = -1):
    """ This produces a Universal scene descriptor structure for physics modeling of the tree
      Each branch/trunk is chopped up into cylinders that are connected via hinge joints
      The cylinders themselves are collision objects
      The first branch cylinder is connected to the top of cylinder of the tree trunk that is below the
      bud junction.
      The structure is flattened - spit out all the cylinders at one level; don't nest them
      Use name_name_cyl_index where name is, eg, trunk0, branch_l1
      Mass is a function of size, with trunks being slightly denser than branches
      Level lets you control how much of the tree to skeletonize; eg, level 0 will give the trunk,
        level 1 the trunk plus the primary branches"""

    # Create the physics scene
    physics_scene_path = parent_path.AppendChild("physicsScene")
    physics_scene = UsdPhysics.Scene.Define(stage, physics_scene_path)
    physics_scene.CreateGravityDirectionAttr(Gf.Vec3f(0.0, 0.0, -1.0))
    physics_scene.CreateGravityMagnitudeAttr(9.81)

    # Create the articulation root
    skeleton_path = parent_path.AppendChild("skeleton")
    skel_root_xform = UsdGeom.Xform.Define(stage, skeleton_path)
    # Apply articulation API so physics treats it as an interconnected object
    UsdPhysics.ArticulationRootAPI.Apply(skel_root_xform.GetPrim())

    # By default, hide this geometry
    # imageable = UsdGeom.Imageable(skel_root_xform.GetPrim())
    # imageable.GetVisibilityAttr().Set(UsdGeom.Tokens.invisible)

    # For each trunk/branch, create collider cylinders with mass
    #  Naming convention is: fullname_cyl_id with - turned to _
    #  Which parts of the skeleton to keep
    skel_parts: list[SkeletonComponent] = []
    centerline_parts: list[dict] = []
    map_full_name_to_skel_part = {}
    for tree_part in tree.iterate_all_wood_parts():
        if "skel" not in tree_part:
            continue
        if "centerline" not in tree_part:
            continue

        # eg rootstock_trunk0_branchL0
        part_name = tree_part["full_name"].replace("-", "_")

        # Primary, secondary, etc
        level = TreeNamingConvention.get_branch_level(tree_part["full_name"])

        if level_limit != -2:
            # Don't do spurs if level limit is set to anything but -2
            if "spur" in part_name:
                continue
        # Don't do geometry below a certain level
        if level_limit >= 0 and level < level_limit:
            continue

        # Color the cylinder by the tree part
        col_tuple = TreeNamingConvention.semantic_color(tree_part["type"])

        skel: SkeletonComponent = tree_part["skel"]
        skel_parts.append(skel)
        skel.color = col_tuple
        skel.part_name = part_name
        skel.level = level
        map_full_name_to_skel_part[tree_part["full_name"]] = skel
        centerline_parts.append(tree_part["centerline"])

    for skel, centerline in zip(skel_parts, centerline_parts):
        # Now add in the cylinders
        for indx in range(0, len(skel.centroids) - 1):
            _add_collision_cylinder(stage=stage,
                                    path=skeleton_path,
                                    skel=skel,
                                    centerline=centerline,
                                    indx=indx)

    # Add in the Fixed or hinge joint for the base of the trunk
    for skel in skel_parts:
        if "trunk" in skel.name:
            joint_path = skeleton_path.AppendChild(f"{skel.part_name}_base")
            joint = UsdPhysics.FixedJoint.Define(stage, joint_path)
            cyl_name = _cyl_name(skel.part_name, 0)
            joint.CreateBody1Rel().SetTargets([cyl_name])
            height = skel.heights[0]
            joint.CreateLocalPos1Attr((0.0, 0.0, height * 0.5))

    # Add in a hinge joint for each cylinder
    for skel in skel_parts:
        for indx in range(1, len(skel.centroids) - 2):
            _add_hinge_joint(stage=stage,
                             path=skeleton_path,
                             skel=skel,
                             indx=indx)


def create_uv_material(stage, material_path, file_name="../textures/mesh_uv.png"):
    """ For the UV textured mesh, set up the material"""
    # Give the material a unique USD name
    material = UsdShade.Material.Define(stage, material_path)

    # 2 Create the Shader (UsdPreviewSurface)
    shader = UsdShade.Shader.Define(stage, material_path.AppendChild("PBRShader"))
    shader.CreateIdAttr("UsdPreviewSurface")
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    # Set up the texture coordinates and material 
    coord_reader = UsdShade.Shader.Define(stage, material_path.AppendChild("StReader"))
    coord_reader.CreateIdAttr("UsdPrimvarReader_float2")
    coord_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")

    tex = UsdShade.Shader.Define(stage, material_path.AppendChild("Uv_colors"))
    tex.CreateIdAttr("UsdUVTexture")
        
    # Make wrap in s
    tex.CreateInput("wrapS", Sdf.ValueTypeNames.Token).Set("repeat")
    tex.CreateInput("wrapT", Sdf.ValueTypeNames.Token).Set("repeat")

    # Use uv
    tex.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(coord_reader.ConnectableAPI(), "result")

    # Which file
    tex.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(file_name)

    shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(tex.ConnectableAPI(), "rgb")

    return material


def create_mesh_usd(stage_context, world_path:str, in_tree_name:str, 
                    tree: TreeStructure,
                    radii: list, name_radii: list,
                    b_use_uv=False):
    
    # Create a new USD stage in memory to hold the tree and it's parts
    with Ar.ResolverContextBinder(stage_context):
        stage = Usd.Stage.CreateInMemory()

    # Set the up axis to be z and set the units to be in meters
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    # The tree's internal absolute path starts with the tree name;
    #   The actual location of the resulting file will be in world_path
    # Making the container for the model
    tree_path = Sdf.Path(f'/{in_tree_name}')
    root_xform = UsdGeom.Xform.Define(stage, tree_path)

    # This fixes the "Cannot reference... has no default prim" error and makes it
    #   so this asset can be included in other scenes/stages
    stage.SetDefaultPrim(root_xform.GetPrim())

    # Set up texture maps - either uv (if applying red/green color map so that
    #  red wraps around each branch, green goes along it) or default bark textures
    # This assumes the texture files will be available up one directory in a
    #  directory named textures
    # TODO: Create multiple texture maps at different scales based on actual apple
    #   bark rather than pine
    material_path = tree_path.AppendChild("Looks")
    if b_use_uv:
        uv_path = material_path.AppendChild("UVColors")
        material = create_uv_material(stage, 
                                      material_path=uv_path, 
                                      file_name="../textures/mesh_uv.png")
        UsdShade.MaterialBindingAPI(root_xform).Bind(material)
    else:
        # TODO make this multiple textures, one for each radius size
        pine_path = material_path.AppendChild("PineBark")
        material = create_material_look(stage=stage, 
                                        material_path=pine_path, 
                                        file_dir="../textures/pine_bark_vmbibe2g_2k/")
 
    # Loop through all of the (organized) mesh components, adding meshes for each
    for part_dict in tree.iterate_all_wood_parts():
        mesh = part_dict["mesh"]

        if mesh is None:
            # No mesh assigned to this part (probably root)
            continue

        if len(mesh["vertices"]) == 0:
            # This should not happen, because we took all of empty mesh parts out, but
            #  still here as a safetly check
            print(f"ERR: Skipping {part_dict['name']}, no mesh parts")
            continue

        # Each mesh part will be labeled with full part name to enable instance
        #  segmentation. All mesh parts are stored as an xform with a mesh inside
        #  of it (hence the two names)
        usd_name = part_dict["usd_name"]
        xform_path = tree_path.AppendPath(usd_name)
        mesh_path = xform_path.AppendPath("meshGeom")

        # Xform for the tree part
        branch_xform = UsdGeom.Xform.Define(stage, xform_path)
        # Mesh for the tree part
        mesh = UsdGeom.Mesh.Define(stage, mesh_path)
        #  Bind the Material to the Mesh
        #  TODO: use the best size texture
        UsdShade.MaterialBindingAPI(branch_xform).Bind(material)

        # Add semantic label
        labels_api = UsdSemantics.LabelsAPI.Apply(branch_xform.GetPrim(), "class")
        labels_api.CreateLabelsAttr().Set([part_dict["type"]])
        
        # Set the mesh's color based on what part it is
        # 'constant' means one value is used for the entire primitive
        color_primvar = mesh.CreateDisplayColorPrimvar(interpolation=UsdGeom.Tokens.constant)
        col_semantic = TreeNamingConvention.semantic_color(part_dict["name"])
        col_vec = Gf.Vec3f(col_semantic[0] / 255.0, col_semantic[1] / 255.0, col_semantic[2] / 255.0)
        color_primvar.Set([col_vec])
        color_primvar.SetInterpolation("constant")

        # Actually adds the vertices, faces, and texture map coords
        make_mesh_from_components(mesh, part_dict, b_use_uv=b_use_uv)

    """
    # Maybe use later to create two possible texture bindings
    root_layer = stage.GetRootLayer()
    root_layer.subLayerPaths.append(pine_bark_file)
    bound_material = UsdShade.Material(stage.GetPrimAtPath(pine_bark_material_path))
    UsdShade.MaterialBindingAPI(root_xform).Bind(bound_material)
    """

    # Spheres for the joints, cylinders for the trunks/branches
    # TODO Make it create collision geometry as well
    create_skeleton_geometry(stage=stage, tree=tree, parent_path=tree_path, level_limit=-1)

    #  Save the stage
    if b_use_uv:
        file_name = world_path + "/models/" + in_tree_name + "_uv.usda"
    else:
        file_name = world_path + "/models/" + in_tree_name + ".usda"
    print(f"Saving file to {file_name}")
    # Actually write out the mesh
    stage.GetRootLayer().Export(file_name)


def create_skeleton_usd(stage_context,
                        world_path: str, in_tree_name: str,
                        tree: TreeStructure,
                        level_limit:int =-1):
    """ Build JUST a skeleton file for simulation in Isaac sim/newton or Mujoco"""
    # Create a new USD stage in memory to hold the tree and it's parts
    with Ar.ResolverContextBinder(stage_context):
        stage = Usd.Stage.CreateInMemory()

    # Set the up axis to be z and set the units to be in meters
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)
    UsdGeom.SetStageKilogramsPerUnit(stage, 1.0)

    # The tree's internal absolute path starts with the tree name;
    #   The actual location of the resulting file will be in world_path
    # Making the container for the model
    skeleton_path = Sdf.Path(f'/{in_tree_name}_skeleton')
    root_xform = UsdGeom.Xform.Define(stage, skeleton_path)

    # This fixes the "Cannot reference... has no default prim" error and makes it
    #   so this asset can be included in other scenes/stages
    stage.SetDefaultPrim(root_xform.GetPrim())

    # Spheres for the joints, cylinders for the trunks/branches
    create_skeleton_geometry(stage=stage, tree=tree, parent_path=skeleton_path, level_limit=level_limit)

    file_name = world_path + "/models/" + in_tree_name + "_skeleton.usda"
    print(f"Saving file to {file_name}")
    # Actually write out the mesh
    stage.GetRootLayer().Export(file_name)


def make_combined():
    # NOT TESTED - Just saving this as example code for adding sub layers
    stage = Usd.Stage.CreateInMemory()
    root_layer = stage.GetRootLayer()
    root_layer.subLayerPaths.append("./models/lpy_envy_00000.usda")
    root_layer.subLayerPaths.append("./texture/pine_bark.usda")
    stage.Export("./models/compiled_scene.usda")
