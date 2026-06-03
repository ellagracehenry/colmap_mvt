import open3d as o3d


import numpy as np
import trimesh
from scipy.spatial import cKDTree

input_mesh_path="/Users/mad4rosie/Downloads/A07_12fps_trial1.ply"
output_mesh_path = "/Users/mad4rosie/GilLab/Plastics/habitats/A07_12fps_clean.ply"



def calculate_surface_area(mesh):
    """
    Calculate the surface area of the mesh by summing the area of all triangles.
    """
    return mesh.area

def calculate_projected_area(mesh):
    """
    Calculate the projected surface area of the mesh onto the XY plane (ignoring Z).
    """
    projected_areas = []
    for face in mesh.faces:
        # Get the vertices of the face
        v0, v1, v2 = mesh.vertices[face]
        # Project the vertices onto the XY plane (ignoring Z)
        v0_proj = v0[:2]
        v1_proj = v1[:2]
        v2_proj = v2[:2]
        # Calculate the area of the projected triangle using the 2D cross product
        area_proj = 0.5 * abs(np.cross(v1_proj - v0_proj, v2_proj - v0_proj))
        projected_areas.append(area_proj)
    return np.sum(projected_areas)

def calculate_rugosity(mesh):
    """
    Calculate the rugosity of the entire mesh.
    """
    total_area = calculate_surface_area(mesh)
    projected_area = calculate_projected_area(mesh)
    return total_area / projected_area


mesh = o3d.io.read_triangle_mesh(input_mesh_path)

# 1. Remove degenerate geometry first
mesh.remove_degenerate_triangles()
mesh.remove_duplicated_vertices()

# 2. Cluster triangles to find floating bits
# Returns: cluster_index, cluster_num_triangles, cluster_area
triangle_clusters, cluster_n_triangles, cluster_area = (
    mesh.cluster_connected_triangles()
)

# 3. Identify and keep only the largest cluster
largest_cluster_idx = cluster_n_triangles.index(max(cluster_n_triangles))

triangles_to_remove = [
    i for i, cluster_id in enumerate(triangle_clusters) 
    if cluster_id != largest_cluster_idx
]
mesh.remove_triangles_by_index(triangles_to_remove)
o3d.io.write_triangle_mesh(output_mesh_path, mesh)

print(f"Mesh cleaned and saved to {output_mesh_path}.")

mesh = trimesh.load_mesh(output_mesh_path)
# Calculate the total rugosity of the reef
total_rugosity = calculate_rugosity(mesh)
print(f'Total Rugosity of the Reef: {total_rugosity}')
