from pxr import Usd, UsdGeom, Gf, UsdSemantics, Sdf, UsdShade, Ar, UsdPhysics

from lpy_treesim.tree_generation.skeleton_components import JunctionComponent
from lpy_treesim.tree_generation.tree_naming_convention import TreeNamingConvention
from lpy_treesim.tree_generation.tree_structure import TreeStructure


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


def create_skeleton_geometry(stage, parent_path: str, tree: TreeStructure, level_limit: int = -1):
    """ One sphere for each junction, one cylinder for each branch/part"""
    skeleton_path = parent_path.AppendChild("skeleton")
    skel_root_xform = UsdGeom.Xform.Define(stage, skeleton_path)
    # By default, hide this geometry
    imageable = UsdGeom.Imageable(skel_root_xform.GetPrim())
    imageable.GetVisibilityAttr().Set(UsdGeom.Tokens.invisible)

    # How much "fatter" to make the cylinders/spheres
    scl_factor = 1.1
    
    col_tuple = TreeNamingConvention.semantic_color("trunk")
    col = Gf.Vec3f(col_tuple[0] / 255.0, col_tuple[1] / 255.0, col_tuple[2] / 255.0)

    junction_path = skeleton_path.AppendChild("junctions")
    junction_xform = UsdGeom.Xform.Define(stage, junction_path)
    semantic_label = "TrunkJunction"
    junction_joints = {}
    for junction_list in (tree.trunk_junctions, tree.branch_junctions):
        for indx, junction in enumerate(junction_list):
            # USD paths can't have -, so replace - with _ and _ with __

            path_name = f"{junction.parent_name}__{junction.child_name}".replace("-", "_")
            if junction.type == JunctionComponent.JunctionType.BUD:
                name = f"{path_name}_bud_{indx:02}"
            elif junction.type is JunctionComponent.JunctionType.SPUR:
                name = f"{path_name}_spur_{indx:02}"
            elif junction.type == JunctionComponent.JunctionType.PRUNED:
                continue
            else:
                name = path_name

            if level_limit != -1:
                if junction.type is JunctionComponent.JunctionType.SPUR:
                    continue
                level = TreeStructure.get_level_from_name(junction.child_name)
                if level < level_limit:
                    continue

            joint_info = {"parent_name": path_name,
                          "loc": junction.pt_attach,
                          "cyl_index": indx,
                          "y_ang": junction.ang_attach,
                          "x_ang": junction.theta_around,
                          "height": junction.prev_section_height}
            junction_joints[junction.child_name] = joint_info

            sphere_xform_path = junction_path.AppendChild(name)
            sphere_xform = UsdGeom.Xform.Define(stage, sphere_xform_path)
            sphere_path = sphere_xform_path.AppendChild("junc")
            sphere = UsdGeom.Sphere.Define(stage, sphere_path)
            sphere.CreateRadiusAttr(junction.radius * scl_factor)

            translate_op = sphere_xform.AddTranslateOp()
            translate_op.Set(Gf.Vec3f(junction.pt_attach))

            # Add collision physics
            UsdPhysics.CollisionAPI.Apply(sphere.GetPrim())

            # Add semantic label
            labels_api = UsdSemantics.LabelsAPI.Apply(sphere.GetPrim(), "class")
            labels_api.CreateLabelsAttr().Set([semantic_label])

            #... and semantic color
            color_attr = sphere.CreateDisplayColorAttr()
            color_attr.Set([col])  # Semantic color
        # Switch from trunk to branch color
        col_tuple = TreeNamingConvention.semantic_color("branch")
        col = Gf.Vec3f(col_tuple[0] / 255.0, col_tuple[1] / 255.0, col_tuple[2] / 255.0)
        semantic_label = "BranchJunction"
    
    centerlines_path = skeleton_path.AppendChild("center_lines")
    centerlines_xform = UsdGeom.Xform.Define(stage, centerlines_path)
    for tree_part in tree.iterate_all_wood_parts():
        if not "skel" in tree_part:
            continue

        part_name = tree_part["name"].replace("-", "_")
        level = TreeNamingConvention.get_branch_level(tree_part["full_name"])

        name = f"cyl_{part_name}"
        if "spur" in part_name:
            continue
        elif level != -1:
            name = f"Level{level}/{name}"
        else:
            name = f"Trunk/{name}"

        # Bundle these into one container that has the semantic color
        cyls_path = centerlines_path.AppendPath(name)
        cyls_container = UsdGeom.Xform.Define(stage, cyls_path)
        col_tuple = TreeNamingConvention.semantic_color(tree_part["type"])
        col = Gf.Vec3f(col_tuple[0] / 255.0, col_tuple[1] / 255.0, col_tuple[2] / 255.0)

        # Now add in the cylinders
        skel = tree_part["skel"]
        skip_first = False
        if "rootstock" in name:
            skip_first = True
        else:
            joint_info = junction_joints[tree_part["name"]]

            parent_cyls_path = centerlines_path.AppendPath(joint_info['parent_name'])
            cyl_last_path = parent_cyls_path.AppendPath(f"cyl_{joint_info['cyl_index']}")
            prev_height = joint_info["height"]
            x_ang = joint_info["x_ang"]
            y_ang = joint_info["y_ang"]

        level = TreeStructure.get_level_from_name(tree_part["name"])
        for indx in range(0, len(skel.centroids)-1):
            pt_start = Gf.Vec3d(skel.centroids[indx])
            pt_end = Gf.Vec3d(skel.centroids[indx + 1])
            vec_axis = pt_end - pt_start
            height = vec_axis.GetLength()
            if height <= 0.0:
                print(f"Warning making usd skeleton: Height zero {part_name} {name}")
                height = 0.001
            midpoint = pt_start + vec_axis * 0.5

            name = f"cyl_{indx}"
            cyl_cur_path = cyls_path.AppendChild(name)
            cyl = UsdGeom.Cylinder.Define(stage, cyl_cur_path)
            if skel.radii[indx] < 0.0:
                print("Oops")
            cyl.CreateRadiusAttr(skel.radii[indx] * scl_factor)
            cyl.CreateHeightAttr(height)
            color_attr = cyl.CreateDisplayColorAttr()
            color_attr.Set([col])  # Beautiful bright blue

            # Add collision physics
            UsdPhysics.CollisionAPI.Apply(cyl.GetPrim())

            # Align along z axis
            cyl.CreateAxisAttr("Z")

            # Rotation to align z axis with vec_axis

            z_axis = Gf.Vec3d(0, 0, 1)
            rotation = Gf.Rotation(z_axis, vec_axis)
            quat = rotation.GetQuat()

            # Make cylinder transformable
            xformable = UsdGeom.Xformable(cyl)
            
            # rotate and translate to correct location
            xformable.AddTranslateOp().Set(midpoint)
            # I do not know why you have to cast to a float, but you do...
            xformable.AddOrientOp().Set(Gf.Quatf(quat))

            if indx == 0:
                joint_path = cyl_cur_path.AppendChild(f"BaseJoint_{indx}_{indx+1}")
            else:
                joint_path = cyl_cur_path.AppendChild(f"InteriorJoint_{indx}_{indx+1}")

            if not skip_first:
                joint = UsdPhysics.DistanceJoint.Define(stage, joint_path)
                joint_prim = joint.GetPrim()

                # Connect the two cylinders
                joint.GetBody0Rel().AddTarget(cyl_last_path)
                joint.GetBody1Rel().AddTarget(cyl_cur_path)

                # Anchor points based on ending point of last cylinder
                joint.GetLocalPos0Attr().Set(Gf.Vec3d(0.0, 0.0, -prev_height * 0.5))

                # Anchor points based on starting point of this cylinder
                joint.GetLocalPos1Attr().Set(Gf.Vec3d(0.0, 0.0, height * 0.5))

                # 4. Lock all linear translation degrees of freedom (X, Y, Z)
                # Setting low attribute > high attribute explicitly tells physics solvers to lock the axis.
                for axis in ["transX", "transY", "transZ"]:
                    limit_api = UsdPhysics.LimitAPI.Apply(joint_prim, axis)
                    limit_api.CreateLowAttr(1.0)
                    limit_api.CreateHighAttr(-1.0)

                # 5. Lock the twist degree of freedom (rotZ)
                # This prevents twisting along the length of the joint connection
                twist_limit = UsdPhysics.LimitAPI.Apply(joint_prim, "rotZ")
                twist_limit.CreateLowAttr(1.0)
                twist_limit.CreateHighAttr(-1.0)

                # 6. Optional: Set motion limits for swing axes (rotX, rotY)
                # If omitted entirely, these axes will be completely free (spinning infinitely).
                # Below, we limit swing freedom to a +/- 45 degree angle:
                for axis in ["rotX", "rotY"]:
                    swing_limit = UsdPhysics.LimitAPI.Apply(joint_prim, axis)
                    if level == 0:
                        swing_limit.CreateLowAttr(-10.0)
                        swing_limit.CreateHighAttr(10.0)
                    elif level == 1:
                        swing_limit.CreateLowAttr(-20.0)
                        swing_limit.CreateHighAttr(20.0)
                    elif level > 1:
                        swing_limit.CreateLowAttr(-45.0)
                        swing_limit.CreateHighAttr(45.0)
                    else:
                        swing_limit.CreateLowAttr(0.1)
                        swing_limit.CreateHighAttr(0.1)

                # Apply the DriveAPI to the "linear" degree of freedom to create a Spring
                # The token argument "linear" controls the distance metric between anchors
                spring_drive = UsdPhysics.DriveAPI.Apply(joint_prim, "linear")

                # Configure Spring Dynamics
                spring_drive.CreateTypeAttr("position")  # Computes forces relative to displacement
                spring_drive.CreateTargetPositionAttr(0.0)

                # Define your desired non-zero target angles (in degrees)
                target_angles = {
                    "rotX": x_ang,  # Rests at a 30-degree tilt
                    "rotY": y_ang  # Rests at a -15-degree tilt
                }

                for axis, angle in target_angles.items():
                    spring_drive = UsdPhysics.DriveAPI.Apply(joint_prim, axis)
                    spring_drive.CreateTypeAttr("position")

                    # Set the non-zero target angle here
                    spring_drive.CreateTargetPositionAttr(angle)

                spring_drive.CreateStiffnessAttr(1000.0)  # K constant (Spring stiffness)
                spring_drive.CreateDampingAttr(0.15)  # B constant (Resistive damping)

            prev_height = height
            cyl_last_path = cyl_cur_path
            x_ang = 0.0
            y_ang = 0.0

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

    # The tree's internal absolute path starts with the tree name;
    #   The actual location of the resulting file will be in world_path
    # Making the container for the model
    skeleton_path = Sdf.Path(f'/{in_tree_name}_skeleton')
    root_xform = UsdGeom.Xform.Define(stage, skeleton_path)

    # This fixes the "Cannot reference... has no default prim" error and makes it
    #   so this asset can be included in other scenes/stages
    stage.SetDefaultPrim(root_xform.GetPrim())

    # Spheres for the joints, cylinders for the trunks/branches
    # TODO Make it create collision geometry as well
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
