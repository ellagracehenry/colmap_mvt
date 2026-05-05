import open3d as o3d

mesh = o3d.io.read_triangle_mesh("/Users/mad4rosie/Downloads/JM_152_full_1fps_opt_meshed-poisson.ply")

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

o3d.io.write_triangle_mesh("/Users/mad4rosie/Downloads/cleaned_JM_152_full_mesh.ply", mesh)