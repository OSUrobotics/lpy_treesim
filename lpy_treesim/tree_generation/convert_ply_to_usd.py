from pxr import Usd, UsdGeom, Gf, UsdSemantics, Sdf, UsdShade, Ar
from lpy_treesim.tree_generation.naming_convention import TreeNamingConvention


def create_labeled_asset(file_path):
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


def create_mesh(stage, path, points, face_vertex_counts, face_vertex_indices):
    """
    Helper function to create a USD mesh.
    """
    mesh = UsdGeom.Mesh.Define(stage, path)
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
    mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)
    mesh.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    return mesh


def check_texture(stage_context):
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


def make_mesh_from_components(mesh_usd, mesh_parts, b_use_uv=False):
    # Vertices, texture coords for vs, and faces
    vs = []
    vs_texs = []
    # Not really sure we need to do this, but otherwise have trouble with the USD call
    if b_use_uv:
        use_texs = mesh_parts["textures"]
    else:
        use_texs = mesh_parts["uv_textures"]
    for pt, tex in zip(mesh_parts["vertices"], use_texs):
        # swap y and z to make z up
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
    # We use 'st' as the name.
    # 'interpolation' determines how UVs map to the geometry.
    tex_coords = UsdGeom.PrimvarsAPI(mesh_usd).CreatePrimvar(
        "st",
        Sdf.ValueTypeNames.TexCoord2fArray,
        UsdGeom.Tokens.varying
    )
    # Set the UV values that tile along the mesh
    # These correspond to the points defined above: (u, v)
    # ts = [(t[0], t[1]) for t in mesh_component["textures"]]
    ts_ind_gen = [(pt[0], pt[1]) for pt in vs_texs]
    tex_coords.Set(ts_ind_gen)

    # No subdivision, please
    mesh_usd.CreateSubdivisionSchemeAttr(UsdGeom.Tokens.none)
    # TODO use catmul clark on big radii branches
    #mesh_usd.CreateSubdivisionSchemeAttr().Set("catmulClark")


def setup_top_level_textures(stage, radii_name: list):
    materials = []
    for name in radii_name:
        # 1. Create the Material at the top level
        material_path = Sdf.Path(f"/textures/{name}")
        material = UsdShade.Material.Define(stage, material_path)

        # 2 Create the Shader (UsdPreviewSurface)
        shader = UsdShade.Shader.Define(stage, material_path.AppendChild("PBRShader"))
        shader.CreateIdAttr("UsdPreviewSurface")
        shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(0.4)

        # 3. Create the Texture Sampler (UsdUVTexture)
        reader = UsdShade.Shader.Define(stage, material_path.AppendChild("TexSampler"))
        reader.CreateIdAttr("UsdUVTexture")
        reader.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(f"/textures/{name}")

        # 4 Connect texture output to shader's diffuseColor input
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(
            reader.CreateOutput("rgb", Sdf.ValueTypeNames.Color3f))

        # 5 Create the Primvar Reader (To tell the texture to use 'st')
        st_reader = UsdShade.Shader.Define(stage, material_path.AppendChild("STReader"))
        st_reader.CreateIdAttr("UsdPrimvarReader_float2")
        st_reader.CreateInput("varname", Sdf.ValueTypeNames.String).Set("st")

        # Connect reader output to texture sampler's st input
        reader.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(
            st_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2))

        materials.append(material)
    return materials


def create_material_look(stage, material_path_name="/Looks/PineBark", file_dir="../textures/pine_bark_vmbibe2g_2k/"):
    material_path = Sdf.Path(material_path_name)
    # Give the material a unique USD name
    material = UsdShade.Material.Define(stage, material_path)

    # 2 Create the Shader (UsdPreviewSurface)
    shader = UsdShade.Shader.Define(stage, material_path.AppendChild("PBRShader"))
    shader.CreateIdAttr("UsdPreviewSurface")
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    # 1. Create the ST Coordinates Reader (Primvar Reader)
    coord_reader = UsdShade.Shader.Define(stage, material_path.AppendChild("StReader"))
    coord_reader.CreateIdAttr("UsdPrimvarReader_float2")
    coord_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")

    # Helper to create texture nodes
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

    # 1. Color Mapping (Diffuse)
    add_texture_file("DiffuseTex", file_dir + "Pine_Bark_vmbibe2g_2K_BaseColor.jpg", "diffuseColor", Sdf.ValueTypeNames.Color3f)

    # 2. Normal Mapping
    add_texture_file("NormalTex", file_dir + "Pine_Bark_vmbibe2g_2K_Normal.jpg", "normal", Sdf.ValueTypeNames.Normal3f)

    # 3. Bump/Displacement Mapping
    # In UsdPreviewSurface, bump is often driven by the displacement port
    add_texture_file("BumpTex", file_dir + "Pine_Bark_vmbibe2g_2K_Bump.jpg", "displacement", Sdf.ValueTypeNames.Float)

    add_texture_file("RoughnessTex", file_dir + "Pine_Bark_vmbibe2g_2K_Roughness.jpg", "roughness", Sdf.ValueTypeNames.Float)

    # I am not sure what these should map to
    #add_texture_file("CavityTex", file_dir + "Pine_Bark_vmbibe2g_2K_Cavity.jpg", "cavity", Sdf.ValueTypeNames.Float)
    #add_texture_file("SpecularTex", file_dir + "Pine_Bark_vmbibe2g_2K_Specular.jpg", "specular", Sdf.ValueTypeNames.Float)
    #add_texture_file("GlossTex", file_dir + "Pine_Bark_vmbibe2g_2K_Gloss.jpg", "gloss", Sdf.ValueTypeNames.Float)

    return material


def setup_pinebark(stage_context, path_world_name, file_dir="../textures/pine_bark_vmbibe2g_2k/"):

    with Ar.ResolverContextBinder(stage_context):
        stage_pinebark = Usd.Stage.CreateInMemory()

    material = create_material_look(stage_pinebark, material_path_name="/Material/PineBark", file_dir=file_dir)

    pinebark_file = str(path_world_name) + "/textures/pine_bark.usda"
    stage_pinebark.GetRootLayer().Export(pinebark_file)
    return material


def create_uv_material(stage, material_path_name, file_name="../textures/mesh_uv.png"):
    material_path = Sdf.Path(material_path_name)
    # Give the material a unique USD name
    material = UsdShade.Material.Define(stage, material_path)

    # 2 Create the Shader (UsdPreviewSurface)
    shader = UsdShade.Shader.Define(stage, material_path.AppendChild("PBRShader"))
    shader.CreateIdAttr("UsdPreviewSurface")
    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")

    # 1. Create the uv Coordinates Reader (Primvar Reader)
    # NOTE: Attach this one to uv, the tiling one to st
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


def create_mesh_usd(stage_context, world_path:str, tree_name:str, 
                    tree:TreeNamingConvention,
                    radii: list, name_radii: list,
                    b_use_uv=False):
    # 1. Create a new USD stage
    # Set the up axis and units
    #stage = Usd.Stage.CreateNew("/World")
    # 3. Create or open your stage using this context
    with Ar.ResolverContextBinder(stage_context):
        stage = Usd.Stage.CreateInMemory()

    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    # This acts as the "container" for your model
    root_xform = UsdGeom.Xform.Define(stage, f'/{tree_name}')

    # This fixes the "Cannot reference... has no default prim" error
    stage.SetDefaultPrim(root_xform.GetPrim())

    # Set up texture maps
    if b_use_uv:
        material = create_uv_material(stage, 
                                      material_path_name=f"/{tree_name}/Looks/UVColors", 
                                      file_name="../textures/mesh_uv.png")
        UsdShade.MaterialBindingAPI(root_xform).Bind(material)
    else:
    #materials = setup_top_level_textures(stage, name_radii)
        material = create_material_look(stage=stage, 
                                        material_path_name=f"/{tree_name}/Looks/PineBark", 
                                        file_dir="../textures/pine_bark_vmbibe2g_2k/")
 
    # TODO - make the following work so I don't keep copying materials
    # 3. Create a dedicated material scope to house incoming referenced assets
    #ref_materials_path = Sdf.Path("/World/textures")
    #ref_scope = UsdGeom.Scope.Define(stage, ref_materials_path)

    # Relative file path pointing from "assets/layout.usda" out and into "materials/library.usda"
    # We pull specifically from the original </World/Looks> prim inside that file
    #relative_path_to_lib = "../textures/pine_bark.usda"
    #ref_scope.GetPrim().GetReferences().AddReference(relative_path_to_lib, Sdf.Path("/Materials/PineBark"))

    # 5. Bind the Referenced Material to the Geometry
    # Because of our composition arc, GoldMaterial now safely resolves locally at this path:
    #target_material_path = Sdf.Path("/Materials/PineBark")
    #target_material = UsdShade.Material.Get(stage, target_material_path)

    # Loop through all of the (organized) mesh components, adding meshes for each
    for part_dict in tree.iterate_all_wood_parts():
        mesh = part_dict["mesh"]

        if mesh is None:
            continue

        if len(mesh["vertices"]) == 0:
            print(f"Skipping {part_dict['name']}, no mesh parts")
            continue

        # 1 Define the Mesh primitive
        usd_name = part_dict["usd_name"]
        xform_name = f"/{tree_name}{usd_name}"
        mesh_name = f"/{tree_name}{usd_name}/meshGeom"

        # Xform for the tree part
        branch_xform = UsdGeom.Xform.Define(stage, xform_name)
        # Mesh for the tree part
        mesh = UsdGeom.Mesh.Define(stage, mesh_name)
        #  Bind the Material to the Mesh
        #  TOFIX: Find the best size texture
        if not b_use_uv:
            UsdShade.MaterialBindingAPI(branch_xform).Bind(material)

        # Add semantic label
        labels_api = UsdSemantics.LabelsAPI.Apply(branch_xform.GetPrim(), "class")
        
        # Set the mesh's color based on what part it is
        # 'constant' means one value is used for the entire primitive
        color_primvar = mesh.CreateDisplayColorPrimvar(interpolation=UsdGeom.Tokens.constant)
        col_semantic = tree.semantic_color(part_dict["name"])
        col_vec = Gf.Vec3f(col_semantic[0] / 255.0, col_semantic[1] / 255.0, col_semantic[2] / 255.0)
        color_primvar.Set([col_vec])
        color_primvar.SetInterpolation("constant")
        labels_api.CreateLabelsAttr().Set([part_dict["type"]])

        # Actually adds the vertices, faces, and texture map coords
        make_mesh_from_components(mesh, part_dict["mesh"])

    """
    # Maybe use later to create two possible texture bindings
    root_layer = stage.GetRootLayer()
    root_layer.subLayerPaths.append(pine_bark_file)
    bound_material = UsdShade.Material(stage.GetPrimAtPath(pine_bark_material_path))
    UsdShade.MaterialBindingAPI(root_xform).Bind(bound_material)
    """

    #  Save the stage
    if b_use_uv:
        file_name = world_path + "/models/" + tree_name + "_uv.usda"
    else:
        file_name = world_path + "/models/" + tree_name + ".usda"
    print(f"Saving file to {file_name}")
    #print(stage.GetRootLayer().ExportToString())
    stage.GetRootLayer().Export(file_name)

# Example Data
# verts = [(0,0,0), (1,0,0), (1,1,0), (0,1,0)] # 4 vertices
# faces = [(0,1,2), (0,2,3)]                  # 2 triangles forming a square

# create_mesh_usd("mesh_example.usda", verts, faces)


def make_combined():
    stage = Usd.Stage.CreateInMemory()
    root_layer = stage.GetRootLayer()
    root_layer.subLayerPaths.append("./models/lpy_envy_00000.usda")
    root_layer.subLayerPaths.append("./texture/pine_bark.usda")
    stage.Export("./models/compiled_scene.usda")
