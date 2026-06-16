## Calculate rugosity from meshes and fish trajectory

#11/6/24 by Madelyn Hair
#Python 3.12.4

import numpy as np
import trimesh
from scipy.spatial import cKDTree

mesh = trimesh.load_mesh('/Users/mad4rosie/GilLab/Plastics/habitats/A21_12fps_clean2.ply')

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

def get_points_within_radius(fish_path, radius, mesh):
    """
    For each fish path point, find all mesh vertices within a specified radius.
    """
    # Build a k-d tree for fast distance queries
    kdtree = cKDTree(mesh.vertices)
    
    # Find points within the radius for each fish path position
    points_in_radius = []
    for pos in fish_path:
        indices = kdtree.query_ball_point(pos, radius)
        points_in_radius.append(indices)
    return points_in_radius

def calculate_local_rugosity(fish_path, radius, mesh):
    """
    Calculate rugosity of reef faces whose centroids lie within
    a given radius of the fish path.
    """

    # KD-tree of fish path points
    path_tree = cKDTree(fish_path)

    # Compute centroids of all reef faces
    face_centroids = mesh.triangles_center

    # For each face centroid, find distance to nearest fish-path point
    distances, _ = path_tree.query(face_centroids)

    # Mask faces within radius
    face_mask = distances <= radius

    if not np.any(face_mask):
        print("No faces found within radius")
        return 0.0

    # Extract submesh
    submesh = mesh.submesh([face_mask], append=True)

    print(f"Faces in local submesh: {len(submesh.faces)}")

    return calculate_rugosity(submesh)




# Calculate the total rugosity of the reef
total_rugosity = calculate_rugosity(mesh)
print(f'Total Rugosity of the Reef: {total_rugosity}')

# Calculate the local rugosity around the fish path (3m radius)
#radius = 1  # radius in meters
#local_rugosity = calculate_local_rugosity(fish_path, radius, mesh)
#print(f'Local Rugosity within a {radius}m radius of the fish path: {local_rugosity}')

"""""
print("Fish path bounds:")
print(fish_path.min(axis=0), fish_path.max(axis=0))

print("\nReef bounds:")
print(mesh.bounds)

# Compute minimum distance between any path point and any reef vertex
reef_tree = cKDTree(mesh.vertices)
dists, _ = reef_tree.query(fish_path, k=1)

print("\nMinimum fish→reef vertex distance:", dists.min())
print("Median fish→reef vertex distance:", np.median(dists))


#### Trouble Shooting
#Check the bounding box of the mesh
print("Mesh Bounding Box:", mesh.bounds)
print("First few mesh vertices:", mesh.vertices[:5])
print("Last few mesh vertices", mesh.vertices[-5:])
print("Mesh Centroid: ", mesh.centroid)
fish_path1 = fish_path_df[[0,1,2]]
summary_stats = fish_path1.describe()
max=fish_path1.max()
min = fish_path1.min()
print("Summary Statistics: ", summary_stats)
print('Max values:', max)
print("Min values", min)
"""""
