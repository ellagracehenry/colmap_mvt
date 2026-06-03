import numpy as np
import trimesh
import pandas as pd
from scipy.spatial import cKDTree
import os
import gc

def main(mesh_path, trajectory_ply, trajectory_csv, radius, output_path):

    # parameters
    chunk_size = 2
    
    # Define functions
    def calculate_surface_area(mesh):
        return mesh.area

    def calculate_projected_area(mesh):
        areas = mesh.area_faces
        nz = np.abs(mesh.face_normals[:, 2])
        return np.sum(areas * nz)

    def calculate_rugosity(mesh):
        total_area = calculate_surface_area(mesh)
        projected_area = calculate_projected_area(mesh)
        return total_area / projected_area

    def get_faces_within_radius(position, radius, face_tree):
        return face_tree.query_ball_point(position, r=radius)


    #Calculate local rugosity
    def calculate_local_rugosity(position, radius, face_tree, face_areas, face_nz):
        face_ids = get_faces_within_radius(position, radius, face_tree)

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
        

    def calculate_percent_no_mesh(position, radius, face_tree, face_areas, face_nz):
        face_ids = get_faces_within_radius(position, radius, face_tree)

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


    #relief calculation
    def calculate_relief(position, radius, face_tree, face_z):
    
        # highest within CLI radius
        high_ids = face_tree.query_ball_point(position, r=radius)
        
        # lowest within 3m 
        low_ids = face_tree.query_ball_point(position, r=3.0)
        if len(high_ids) == 0 or len(low_ids) == 0:
            return np.nan, np.nan, np.nan
        max_z = np.max(face_z[high_ids])
        min_z = np.min(face_z[low_ids])
        relief = max_z - min_z
        return relief, max_z, min_z


    # Load reef mesh
    mesh = trimesh.load_mesh(mesh_path)
    print("Mesh loaded")
    
    # Precompute triangle data 
    face_centroids = mesh.triangles_center
    face_areas = mesh.area_faces
    face_nz = np.abs(mesh.face_normals[:, 2])
    face_z = face_centroids[:, 2]
    face_tree = cKDTree(face_centroids)


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
            "x",
            "y",
            "z",
            "local_rugosity",
            "local_total_area",
            "percent_no_mesh",
            "projected_mesh_area",
            "relief",
            "max_z",
            "min_z"
        ]
    )
    header_df.to_csv(output_path, index=False)


    # Compute per frame
    buffer_rows = []

    for frame_idx, pos in zip(frame_ids, fish_path):

        if np.isnan(pos).any():
            rugosity, total_area = np.nan, np.nan
            percent_no_mesh, projected_mesh_area = np.nan, np.nan
            relief, max_z, min_z = np.nan, np.nan, np.nan
        else:
            rugosity, total_area = calculate_local_rugosity(
                pos, radius, face_tree, face_areas, face_nz
            )

            percent_no_mesh, projected_mesh_area, _ = calculate_percent_no_mesh(
                pos, radius, face_tree, face_areas, face_nz
            )

            relief, max_z, min_z = calculate_relief(
                pos, radius, face_tree, face_z
            )

        buffer_rows.append([
            frame_idx,
            pos[0],
            pos[1],
            pos[2],
            rugosity,
            total_area,
            percent_no_mesh,
            projected_mesh_area,
            relief,
            max_z,
            min_z
        ])

        if (frame_idx + 1) % chunk_size == 0 or frame_idx == frame_ids[-1]:
            df_chunk = pd.DataFrame(
                buffer_rows,
                columns=[
                    "frame",
                    "x",
                    "y",
                    "z",
                    "local_rugosity",
                    "local_total_area",
                    "percent_no_mesh",
                    "projected_mesh_area",
                    "relief",
                    "max_z",
                    "min_z"
                ]
            )
            df_chunk = df_chunk.round(5)
            df_chunk.to_csv(output_path, mode="a", header=False, index=False)
            buffer_rows = []
            gc.collect()
            print(f"Wrote up to frame {frame_idx}")

    print(f"Finished. CSV saved to: {output_path}")


# Main
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Calculating local rugosity')
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