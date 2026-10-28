import numpy as np
import trimesh
import pandas as pd
from scipy.spatial import cKDTree
import os
import gc

def main(mesh_path, trajectory_ply, trajectory_csv, radius, output_path):

    # parameters
    chunk_size = 2

    # -----------------------------
    # Raycast + 2D cylinder functions (reef-anchored, height-independent)
    # -----------------------------

    def get_reef_xy_below(pos, mesh):
        """
        Fire a ray straight down from the fish position and return the XY
        coordinates of the first reef surface hit.
        Returns None if the ray misses the mesh entirely.
        """
        ray_origin = pos.reshape(1, 3)
        ray_direction = np.array([[0, 0, -1]])

        locations, _, _ = mesh.ray.intersects_location(
            ray_origins=ray_origin,
            ray_directions=ray_direction,
            multiple_hits=False
        )

        if len(locations) == 0:
            return None

        return locations[0, :2]


    def calculate_local_rugosity(face_ids, face_areas, face_nz):
        if len(face_ids) == 0:
            return np.nan, np.nan

        A = face_areas[face_ids]
        nz = face_nz[face_ids]

        total_area = np.sum(A)
        projected_area = np.sum(A * nz)

        if projected_area == 0:
            return np.nan, total_area

        rugosity = total_area / projected_area
        return rugosity, total_area


    def calculate_percent_no_mesh(face_ids, face_areas, face_nz, radius):
        if len(face_ids) == 0:
            circle_area = np.pi * radius**2
            return 100.0, 0.0, circle_area

        A = face_areas[face_ids]
        nz = face_nz[face_ids]

        projected_mesh_area = np.sum(A * nz)
        circle_area = np.pi * radius**2

        coverage_fraction = min(projected_mesh_area / circle_area, 1.0)
        percent_no_mesh = 100.0 * (1.0 - coverage_fraction)

        return percent_no_mesh, projected_mesh_area, circle_area


    def calculate_relief(reef_pos_xy, radius, face_tree_2d, face_z):
        high_ids = face_tree_2d.query_ball_point(reef_pos_xy, r=radius)
        low_ids = face_tree_2d.query_ball_point(reef_pos_xy, r=3.0)

        if len(high_ids) == 0 or len(low_ids) == 0:
            return np.nan, np.nan, np.nan

        max_z = np.max(face_z[high_ids])
        min_z = np.min(face_z[low_ids])
        relief = max_z - min_z
        return relief, max_z, min_z


    # -----------------------------
    # Original 3D sphere bubble functions (fish-centered, height-dependent)
    # -----------------------------

    def calculate_bubble_rugosity(position, radius, face_tree_3d, face_areas, face_nz):
        face_ids = face_tree_3d.query_ball_point(position, r=radius)

        if len(face_ids) == 0:
            return np.nan, np.nan

        A = face_areas[face_ids]
        nz = face_nz[face_ids]

        total_area = np.sum(A)
        projected_area = np.sum(A * nz)

        if projected_area == 0:
            return np.nan, total_area

        rugosity = total_area / projected_area
        return rugosity, total_area


    def calculate_bubble_percent_no_mesh(position, radius, face_tree_3d, face_areas, face_nz):
        face_ids = face_tree_3d.query_ball_point(position, r=radius)

        if len(face_ids) == 0:
            circle_area = np.pi * radius**2
            return 100.0, 0.0, circle_area

        A = face_areas[face_ids]
        nz = face_nz[face_ids]

        projected_mesh_area = np.sum(A * nz)
        circle_area = np.pi * radius**2

        coverage_fraction = min(projected_mesh_area / circle_area, 1.0)
        percent_no_mesh = 100.0 * (1.0 - coverage_fraction)

        return percent_no_mesh, projected_mesh_area, circle_area


    def calculate_bubble_relief(position, radius, face_tree_3d, face_z):
        high_ids = face_tree_3d.query_ball_point(position, r=radius)
        low_ids = face_tree_3d.query_ball_point(position, r=3.0)

        if len(high_ids) == 0 or len(low_ids) == 0:
            return np.nan, np.nan, np.nan

        max_z = np.max(face_z[high_ids])
        min_z = np.min(face_z[low_ids])
        relief = max_z - min_z
        return relief, max_z, min_z


    # Load reef mesh — must keep in memory for raycasting
    mesh = trimesh.load_mesh(mesh_path)
    print("Mesh loaded")

    # Precompute triangle data
    face_centroids = mesh.triangles_center
    face_areas = mesh.area_faces
    face_nz = np.abs(mesh.face_normals[:, 2])
    face_z = face_centroids[:, 2]

    # 3D tree for bubble (sphere) queries
    face_tree_3d = cKDTree(face_centroids)

    # 2D tree for cylinder (spotlight) queries
    face_tree_2d = cKDTree(face_centroids[:, :2])

    print("Trees built")


    # Load fish path
    fish_path_geom = trimesh.load(trajectory_ply, force='scene')
    fish_geom = fish_path_geom.dump(concatenate=True)
    fish_path = np.asarray(fish_geom.vertices)

    frame_ids = np.arange(len(fish_path))

    print("Fish path shape:", fish_path.shape)
    print("Total frames:", len(fish_path))


    # Prepare CSV output
    if os.path.exists(output_path):
        os.remove(output_path)

    header_df = pd.DataFrame(
        columns=[
            "frame",
            "x", "y", "z",
            # Raycast + 2D cylinder metrics (reef-anchored)
            "local_rugosity",
            "local_total_area",
            "percent_no_mesh",
            "projected_mesh_area",
            "relief",
            "max_z",
            "min_z",
            # 3D sphere bubble metrics (fish-centered)
            "bubble_rugosity",
            "bubble_total_area",
            "bubble_percent_no_mesh",
            "bubble_projected_mesh_area",
            "bubble_relief",
            "bubble_max_z",
            "bubble_min_z"
        ]
    )
    header_df.to_csv(output_path, index=False)


    # Compute per frame
    buffer_rows = []
    ray_miss_count = 0

    for frame_idx, pos in zip(frame_ids, fish_path):

        if np.isnan(pos).any():
            # Cylinder metrics
            rugosity, total_area = np.nan, np.nan
            percent_no_mesh, projected_mesh_area = np.nan, np.nan
            relief, max_z, min_z = np.nan, np.nan, np.nan
            # Bubble metrics
            bubble_rugosity, bubble_total_area = np.nan, np.nan
            bubble_percent_no_mesh, bubble_projected_mesh_area = np.nan, np.nan
            bubble_relief, bubble_max_z, bubble_min_z = np.nan, np.nan, np.nan

        else:
            # -----------------------------
            # Raycast + 2D cylinder
            # -----------------------------
            reef_pos_xy = get_reef_xy_below(pos, mesh)

            if reef_pos_xy is None:
                ray_miss_count += 1
                rugosity, total_area = np.nan, np.nan
                percent_no_mesh = 100.0
                projected_mesh_area = np.nan
                relief, max_z, min_z = np.nan, np.nan, np.nan
            else:
                face_ids_2d = face_tree_2d.query_ball_point(reef_pos_xy, r=radius)

                rugosity, total_area = calculate_local_rugosity(
                    face_ids_2d, face_areas, face_nz
                )
                percent_no_mesh, projected_mesh_area, _ = calculate_percent_no_mesh(
                    face_ids_2d, face_areas, face_nz, radius
                )
                relief, max_z, min_z = calculate_relief(
                    reef_pos_xy, radius, face_tree_2d, face_z
                )

            # -----------------------------
            # 3D sphere bubble (original method)
            # -----------------------------
            bubble_rugosity, bubble_total_area = calculate_bubble_rugosity(
                pos, radius, face_tree_3d, face_areas, face_nz
            )
            bubble_percent_no_mesh, bubble_projected_mesh_area, _ = calculate_bubble_percent_no_mesh(
                pos, radius, face_tree_3d, face_areas, face_nz
            )
            bubble_relief, bubble_max_z, bubble_min_z = calculate_bubble_relief(
                pos, radius, face_tree_3d, face_z
            )

        buffer_rows.append([
            frame_idx,
            pos[0], pos[1], pos[2],
            rugosity, total_area,
            percent_no_mesh, projected_mesh_area,
            relief, max_z, min_z,
            bubble_rugosity, bubble_total_area,
            bubble_percent_no_mesh, bubble_projected_mesh_area,
            bubble_relief, bubble_max_z, bubble_min_z
        ])

        if (frame_idx + 1) % chunk_size == 0 or frame_idx == frame_ids[-1]:
            df_chunk = pd.DataFrame(
                buffer_rows,
                columns=[
                    "frame",
                    "x", "y", "z",
                    "local_rugosity",
                    "local_total_area",
                    "percent_no_mesh",
                    "projected_mesh_area",
                    "relief",
                    "max_z",
                    "min_z",
                    "bubble_rugosity",
                    "bubble_total_area",
                    "bubble_percent_no_mesh",
                    "bubble_projected_mesh_area",
                    "bubble_relief",
                    "bubble_max_z",
                    "bubble_min_z"
                ]
            )
            df_chunk = df_chunk.round(5)
            df_chunk.to_csv(output_path, mode="a", header=False, index=False)
            buffer_rows = []
            gc.collect()
            print(f"Wrote up to frame {frame_idx}")

    print(f"Finished. CSV saved to: {output_path}")
    print(f"Ray misses (fish over gap/edge): {ray_miss_count} / {len(fish_path)} frames")


# Main
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Calculating local rugosity with raycast spotlight and 3D bubble')
    parser.add_argument('--mesh_path', type=str, required=True)
    parser.add_argument('--trajectory_ply', type=str, required=True)
    parser.add_argument('--trajectory_csv', type=str, required=True)
    parser.add_argument('--radius', type=float, required=True)
    parser.add_argument('--output_path', type=str, required=True)

    args = parser.parse_args()

    main(
        mesh_path=args.mesh_path,
        trajectory_ply=args.trajectory_ply,
        trajectory_csv=args.trajectory_csv,
        radius=args.radius,
        output_path=args.output_path
    )
