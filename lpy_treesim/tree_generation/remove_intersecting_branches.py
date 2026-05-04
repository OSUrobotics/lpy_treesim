"""
Post-processing script to remove intersecting branches from PLY files.

When branches grow they often intersect with each other. This script detects
intersections between branches and removes the smaller intersecting branch.
It identifies branches by their color in the PLY file and uses the metadata
JSON file to determine branch types (tertiary vs secondary).
"""

import argparse
import json
import numpy as np
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional


def parse_ply(ply_path: str) -> Tuple[List[Tuple[Tuple[float, float, float], Tuple[int, int, int]]], 
                                       List[List[int]], Dict[str, int], List[str]]:
    """
    Parse an ASCII PLY file and return vertices, faces, and header info.
    
    Args:
        ply_path: Path to the PLY file.
        
    Returns:
        Tuple containing:
        - vertices: List of ((x, y, z), (r, g, b)) tuples
        - faces: List of vertex index lists for each face
        - header_info: Dict with 'num_vertices', 'num_faces', 'header_end_index'
        - header_lines: List of header line strings
    """
    with open(ply_path, 'r') as f:
        lines = f.readlines()
    
    header_end_index = 0
    num_vertices = 0
    num_faces = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "end_header":
            header_end_index = i + 1
            break
        if stripped.startswith("element vertex"):
            num_vertices = int(stripped.split()[2])
        elif stripped.startswith("element face"):
            num_faces = int(stripped.split()[2])
    
    # Parse vertices
    vertices = []
    for i in range(header_end_index, header_end_index + num_vertices):
        parts = lines[i].split()
        if len(parts) < 6:
            continue
        x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
        r, g, b = int(float(parts[3])), int(float(parts[4])), int(float(parts[5]))
        vertices.append(((x, y, z), (r, g, b)))
    
    # Parse faces
    faces = []
    face_start = header_end_index + num_vertices
    for i in range(face_start, face_start + num_faces):
        parts = lines[i].split()
        if len(parts) < 1:
            continue
        num_indices = int(parts[0])
        indices = [int(parts[j + 1]) for j in range(num_indices)]
        faces.append(indices)
    
    header_info = {
        'num_vertices': num_vertices,
        'num_faces': num_faces,
        'header_end_index': header_end_index
    }
    
    return vertices, faces, header_info, lines[:header_end_index]


def group_by_color(vertices: List[Tuple[Tuple[float, float, float], Tuple[int, int, int]]],
                   faces: List[List[int]]) -> Dict[Tuple[int, int, int], Dict]:
    """
    Group vertices and faces by color.
    
    Args:
        vertices: List of ((x, y, z), (r, g, b)) tuples
        faces: List of vertex index lists
        
    Returns:
        Dict mapping color tuples to dicts containing:
        - 'vertices': List of (x, y, z) tuples
        - 'vertex_indices': Set of original vertex indices
        - 'faces': List of face index lists (using original indices)
    """
    color_data = defaultdict(lambda: {'vertices': [], 'vertex_indices': set(), 'faces': []})
    
    # Group vertices by color
    for idx, (pos, color) in enumerate(vertices):
        color_data[color]['vertices'].append(pos)
        color_data[color]['vertex_indices'].add(idx)
    
    # Assign faces to colors based on their vertices
    for face in faces:
        if not face:
            continue
        # Get the color of the first vertex in the face
        first_vertex_color = vertices[face[0]][1]
        # Check if all vertices in the face have the same color
        all_same_color = all(vertices[idx][1] == first_vertex_color for idx in face)
        if all_same_color:
            color_data[first_vertex_color]['faces'].append(face)
    
    return dict(color_data)


def compute_bounding_box(points: List[Tuple[float, float, float]]) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute the axis-aligned bounding box for a set of points.
    
    Args:
        points: List of (x, y, z) tuples
        
    Returns:
        Tuple of (min_corner, max_corner) as numpy arrays
    """
    if not points:
        return np.array([0, 0, 0]), np.array([0, 0, 0])
    
    pts = np.array(points)
    return pts.min(axis=0), pts.max(axis=0)


def bounding_boxes_intersect(bb1_min: np.ndarray, bb1_max: np.ndarray,
                              bb2_min: np.ndarray, bb2_max: np.ndarray) -> bool:
    """
    Check if two axis-aligned bounding boxes intersect.
    
    Args:
        bb1_min, bb1_max: Min and max corners of first bounding box
        bb2_min, bb2_max: Min and max corners of second bounding box
        
    Returns:
        True if bounding boxes intersect, False otherwise
    """
    # Check for separation along each axis
    for i in range(3):
        if bb1_max[i] < bb2_min[i] or bb2_max[i] < bb1_min[i]:
            return False
    return True


def compute_mesh_volume(points: List[Tuple[float, float, float]]) -> float:
    """
    Estimate the volume of a mesh by computing the volume of its bounding box.
    This is a simple approximation; for more accurate results, a proper mesh
    volume calculation would be needed.
    
    Args:
        points: List of (x, y, z) tuples
        
    Returns:
        Estimated volume (bounding box volume)
    """
    if len(points) < 2:
        return 0.0
    
    bb_min, bb_max = compute_bounding_box(points)
    dimensions = bb_max - bb_min
    return float(np.prod(dimensions))


def get_branch_type(part_name: str) -> str:
    """
    Extract the branch type from a part name.
    
    Args:
        part_name: Full part name (e.g., "TertiaryBranch_0", "Branch_1")
        
    Returns:
        Branch type (e.g., "TertiaryBranch", "Branch", "Trunk")
    """
    if '_' in part_name:
        return part_name.rsplit('_', 1)[0]
    return part_name


def get_branch_order(branch_type: str) -> int:
    """
    Get the hierarchical order of a branch type.
    Lower numbers = higher priority (trunk > secondary > tertiary > spur)
    
    Args:
        branch_type: Type of branch
        
    Returns:
        Order number (lower = more important/larger)
    """
    order_map = {
        'Trunk': 0,
        'Branch': 1,  # Secondary branches
        'TertiaryBranch': 2,
        'Spur': 3,
    }
    return order_map.get(branch_type, 4)


def load_metadata(json_path: str) -> Dict[str, str]:
    """
    Load metadata JSON file mapping colors to part names.
    
    Args:
        json_path: Path to the metadata JSON file
        
    Returns:
        Dict mapping color strings (e.g., "(255, 0, 0)") to part names
    """
    with open(json_path, 'r') as f:
        data = json.load(f)
    
    # Extract part names from the metadata structure
    result = {}
    for color_key, value in data.items():
        if isinstance(value, dict) and 'part_name' in value:
            result[color_key] = value['part_name']
        elif isinstance(value, str):
            result[color_key] = value
    
    return result


def detect_intersections(color_data: Dict[Tuple[int, int, int], Dict],
                         metadata: Optional[Dict[str, str]] = None) -> List[Tuple[Tuple[int, int, int], Tuple[int, int, int]]]:
    """
    Detect intersecting branch pairs using bounding box intersection test.
    
    Args:
        color_data: Dict mapping colors to their vertex/face data
        metadata: Optional dict mapping color strings to part names
        
    Returns:
        List of (color1, color2) tuples representing intersecting pairs
    """
    colors = list(color_data.keys())
    intersecting_pairs = []
    
    # Compute bounding boxes for all colors
    bboxes = {}
    for color in colors:
        points = color_data[color]['vertices']
        if points:
            bboxes[color] = compute_bounding_box(points)
    
    # Check all pairs for intersection
    for i in range(len(colors)):
        for j in range(i + 1, len(colors)):
            color1, color2 = colors[i], colors[j]
            
            if color1 not in bboxes or color2 not in bboxes:
                continue
            
            bb1_min, bb1_max = bboxes[color1]
            bb2_min, bb2_max = bboxes[color2]
            
            if bounding_boxes_intersect(bb1_min, bb1_max, bb2_min, bb2_max):
                intersecting_pairs.append((color1, color2))
    
    return intersecting_pairs


def determine_branch_to_remove(color1: Tuple[int, int, int], 
                                color2: Tuple[int, int, int],
                                color_data: Dict[Tuple[int, int, int], Dict],
                                metadata: Optional[Dict[str, str]] = None) -> Tuple[int, int, int]:
    """
    Determine which of two intersecting branches should be removed.
    
    Priority for removal (branch to remove):
    1. Lower priority branch type (tertiary before secondary, etc.)
    2. If same type, the smaller branch (by volume)
    
    Args:
        color1, color2: Colors of the two intersecting branches
        color_data: Dict mapping colors to their vertex/face data
        metadata: Optional dict mapping color strings to part names
        
    Returns:
        Color of the branch to remove
    """
    # Get branch types if metadata available
    type1, type2 = None, None
    if metadata:
        color1_str = str(color1)
        color2_str = str(color2)
        if color1_str in metadata:
            type1 = get_branch_type(metadata[color1_str])
        if color2_str in metadata:
            type2 = get_branch_type(metadata[color2_str])
    
    # Compare by branch order if types are known
    if type1 and type2:
        order1 = get_branch_order(type1)
        order2 = get_branch_order(type2)
        
        # Remove the lower priority (higher order number) branch
        if order1 != order2:
            return color1 if order1 > order2 else color2
    
    # Fall back to volume comparison
    vol1 = compute_mesh_volume(color_data[color1]['vertices'])
    vol2 = compute_mesh_volume(color_data[color2]['vertices'])
    
    # Remove the smaller branch
    return color1 if vol1 < vol2 else color2


def remove_branches(vertices: List[Tuple[Tuple[float, float, float], Tuple[int, int, int]]],
                    faces: List[List[int]],
                    colors_to_remove: Set[Tuple[int, int, int]]) -> Tuple[List[Tuple[Tuple[float, float, float], Tuple[int, int, int]]], 
                                                                           List[List[int]]]:
    """
    Remove vertices and faces belonging to specified colors.
    
    Args:
        vertices: List of ((x, y, z), (r, g, b)) tuples
        faces: List of vertex index lists
        colors_to_remove: Set of colors whose branches should be removed
        
    Returns:
        Tuple of (new_vertices, new_faces) with removed branches excluded
    """
    # Build mapping from old indices to new indices
    old_to_new = {}
    new_vertices = []
    
    for old_idx, (pos, color) in enumerate(vertices):
        if color not in colors_to_remove:
            new_idx = len(new_vertices)
            old_to_new[old_idx] = new_idx
            new_vertices.append((pos, color))
    
    # Filter and remap faces
    new_faces = []
    for face in faces:
        # Check if all vertices in face are kept
        if all(idx in old_to_new for idx in face):
            new_face = [old_to_new[idx] for idx in face]
            new_faces.append(new_face)
    
    return new_vertices, new_faces


def write_ply(output_path: str,
              vertices: List[Tuple[Tuple[float, float, float], Tuple[int, int, int]]],
              faces: List[List[int]]) -> None:
    """
    Write vertices and faces to a PLY file.
    
    Args:
        output_path: Path for the output PLY file
        vertices: List of ((x, y, z), (r, g, b)) tuples
        faces: List of vertex index lists
    """
    header = f'''ply
format ascii 1.0
comment author abhinav
comment File Generated with PlantGL 3D Viewer
comment Post-processed to remove intersecting branches
element vertex {len(vertices)}
property float x
property float y
property float z
property uchar red
property uchar green
property uchar blue
element face {len(faces)}
property list uchar int vertex_indices
end_header'''

    with open(output_path, 'w') as f:
        f.write(header + '\n')
        
        for (x, y, z), (r, g, b) in vertices:
            f.write(f'{x:.4f} {y:.4f} {z:.4f} {r:.0f} {g:.0f} {b:.0f}\n')
        
        for face in faces:
            f.write(f'{len(face)}')
            for idx in face:
                f.write(f' {idx}')
            f.write('\n')


def update_metadata(metadata: Dict[str, str],
                    colors_to_remove: Set[Tuple[int, int, int]]) -> Dict[str, str]:
    """
    Remove entries for removed branches from metadata.
    
    Args:
        metadata: Original metadata dict
        colors_to_remove: Set of colors to remove
        
    Returns:
        Updated metadata dict
    """
    colors_to_remove_strs = {str(c) for c in colors_to_remove}
    return {k: v for k, v in metadata.items() if k not in colors_to_remove_strs}


def process_ply_file(ply_path: str,
                     output_path: Optional[str] = None,
                     metadata_path: Optional[str] = None,
                     output_metadata_path: Optional[str] = None,
                     verbose: bool = False) -> int:
    """
    Process a PLY file to remove intersecting branches.
    
    Args:
        ply_path: Path to input PLY file
        output_path: Path for output PLY file (default: overwrites input)
        metadata_path: Optional path to metadata JSON file
        output_metadata_path: Path for output metadata (default: overwrites input)
        verbose: Print progress information
        
    Returns:
        Number of branches removed
    """
    if output_path is None:
        output_path = ply_path
    
    if verbose:
        print(f"Processing {ply_path}...")
    
    # Parse PLY file
    vertices, faces, header_info, _ = parse_ply(ply_path)
    
    if verbose:
        print(f"  Loaded {len(vertices)} vertices and {len(faces)} faces")
    
    # Load metadata if available
    metadata = None
    if metadata_path and Path(metadata_path).exists():
        metadata = load_metadata(metadata_path)
        if verbose:
            print(f"  Loaded metadata with {len(metadata)} entries")
    
    # Group by color
    color_data = group_by_color(vertices, faces)
    
    if verbose:
        print(f"  Found {len(color_data)} distinct branches (by color)")
    
    # Detect intersections
    intersecting_pairs = detect_intersections(color_data, metadata)
    
    if verbose:
        print(f"  Found {len(intersecting_pairs)} intersecting branch pairs")
    
    # Determine which branches to remove
    colors_to_remove = set()
    for color1, color2 in intersecting_pairs:
        color_to_remove = determine_branch_to_remove(color1, color2, color_data, metadata)
        colors_to_remove.add(color_to_remove)
        
        if verbose:
            name = "unknown"
            if metadata:
                color_str = str(color_to_remove)
                if color_str in metadata:
                    name = metadata[color_str]
            print(f"    Removing branch: {name} (color: {color_to_remove})")
    
    if not colors_to_remove:
        if verbose:
            print("  No intersecting branches to remove")
        return 0
    
    # Remove branches
    new_vertices, new_faces = remove_branches(vertices, faces, colors_to_remove)
    
    if verbose:
        print(f"  Removed {len(colors_to_remove)} branches")
        print(f"  New mesh: {len(new_vertices)} vertices, {len(new_faces)} faces")
    
    # Write output PLY
    write_ply(output_path, new_vertices, new_faces)
    
    if verbose:
        print(f"  Wrote output to {output_path}")
    
    # Update metadata if provided
    if metadata and output_metadata_path:
        # Re-load full metadata to preserve structure
        with open(metadata_path, 'r') as f:
            full_metadata = json.load(f)
        
        colors_to_remove_strs = {str(c) for c in colors_to_remove}
        updated_metadata = {k: v for k, v in full_metadata.items() 
                           if k not in colors_to_remove_strs}
        
        with open(output_metadata_path, 'w') as f:
            json.dump(updated_metadata, f, indent=4)
        
        if verbose:
            print(f"  Updated metadata at {output_metadata_path}")
    
    return len(colors_to_remove)


def main():
    """Command-line interface for removing intersecting branches."""
    parser = argparse.ArgumentParser(
        description="Remove intersecting branches from PLY tree mesh files."
    )
    parser.add_argument(
        '--ply', 
        type=str, 
        required=True,
        help='Path to input PLY file'
    )
    parser.add_argument(
        '--output', 
        type=str, 
        default=None,
        help='Path for output PLY file (default: overwrites input)'
    )
    parser.add_argument(
        '--metadata', 
        type=str, 
        default=None,
        help='Path to metadata JSON file (for branch type information)'
    )
    parser.add_argument(
        '--output-metadata',
        type=str,
        default=None,
        help='Path for output metadata JSON (default: overwrites input if --metadata provided)'
    )
    parser.add_argument(
        '--verbose', 
        action='store_true',
        help='Print progress information'
    )
    
    args = parser.parse_args()
    
    # Set default output metadata path
    output_metadata = args.output_metadata
    if output_metadata is None and args.metadata:
        output_metadata = args.metadata
    
    # Process the PLY file
    num_removed = process_ply_file(
        ply_path=args.ply,
        output_path=args.output,
        metadata_path=args.metadata,
        output_metadata_path=output_metadata,
        verbose=args.verbose
    )
    
    print(f"Removed {num_removed} intersecting branches")


if __name__ == "__main__":
    main()
