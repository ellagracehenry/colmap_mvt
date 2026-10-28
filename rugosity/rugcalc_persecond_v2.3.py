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
        """
        Calculate the surface area of the mesh by summing the area of all triangles.
        """
        return mesh.area


    def calculate_projected_area(mesh):
        """
        Calculate the projected surface area of the mesh onto the XY plane (ignoring Z).
        """
        areas = mesh.area_faces
        nz = np.abs(mesh.face_normals[:, 2])
        return np.sum(areas * nz)


    def calculate_rugosity(mesh):
        """
        Calculate the rugosity of the entire mesh.
        """
        total_area = calculate_surface_area(mesh)
        projected_area = calculate_projected_area(mesh)
        return total_area / projected_area


    def get_faces_within_radius(position, radius, face_tree):
        """
        For a given position, find all mesh faces within a radius.
        """
        return face_tree.query_ball_point(position, r=radius)


    # -----------------------------
    # FAST local rugosity (no submesh)
    # -----------------------------
    def calculate_local_rugosity(position, radius, face_tree, face_areas, face_nz):
        """
        Calculate rugosity and total surface area of the reef within a radius
        around a position using precomputed triangle data (no submesh).
        Returns:
            rugosity, total_area
        """
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


    # Load reef mesh
    mesh = trimesh.load_mesh(mesh_path)
    print("Mesh loaded")
    
    # Calculate total rugosity
    #total_rugosity=calculate_rugosity(mesh)
   # save_path="/scratch/alpine/maha7624/3D_Tracking/2024_FF/JM_153_final/JM_153_final_totalrug.txt"
   # print(f"Total Mesh Rugosity is {total_rugosity}")
    
    #with open(save_path, "w") as text_file:
    #    text_file.write(f"{total_rugosity}")
    
    
    # Calculate local rugosity
    # Precompute triangle data ONCE
    face_centroids = mesh.triangles_center
    face_areas = mesh.area_faces
    face_nz = np.abs(mesh.face_normals[:, 2])
    face_tree = cKDTree(face_centroids)


    # Load fish path
    fish_path_geom = trimesh.load(trajectory_ply,force='scene')

    #fish path with frames
    frame_id_df = pd.read_csv(trajectory_csv)
    frame_ids = frame_id_df['frame'].values

    fish_geom = fish_path_geom.dump(concatenate=True)
    fish_path = np.asarray(fish_geom.vertices)

    print("Fish path shape:", fish_path.shape)

    n_frames = len(fish_path)
    print("Total frames:", n_frames)

    # Prepare CSV output
    if os.path.exists(output_path):
        os.remove(output_path)

    header_df = pd.DataFrame(
        columns=["frame", "x", "y", "z", "local_rugosity", "local_total_area"]
    )
    header_df.to_csv(output_path, index=False)


    # Compute local rugosity per FRAME
    buffer_rows = []

    for frame_idx, pos in zip(frame_ids, fish_path):

        if np.isnan(pos).any():
            rugosity, total_area = np.nan, np.nan
        else:
            rugosity, total_area = calculate_local_rugosity(
                pos,
                radius,
                face_tree,
                face_areas,
                face_nz
            )

        buffer_rows.append([
            frame_idx,
            pos[0],
            pos[1],
            pos[2],
            rugosity,
            total_area
        ])

        if (frame_idx + 1) % chunk_size == 0 or frame_idx == frame_ids[-1]:
            df_chunk = pd.DataFrame(
                buffer_rows,
                columns=["frame", "x", "y", "z", "local_rugosity", "local_total_area"]
            )
            df_chunk.to_csv(output_path, mode="a", header=False, index=False)
            buffer_rows = []
            gc.collect()
            print(f"Wrote up to frame {frame_idx}")

    print(f"Finished. CSV saved to: {output_path}")
    #print(f"Total Mesh Rugosity is {total_rugosity}. Saved total mesh rugosity to {save_path}.")

# Run Main Loop
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Calculating local and total rugosity')
    parser.add_argument('--mesh_path', type=str, required=True, help='Poisson mesh from reconstruction')
    parser.add_argument('--trajectory_ply', type=str, required=True, help='Path to fish path in .ply format')
    parser.add_argument('--trajectory_csv', type=str, required=True, help='Path fish path in .csv format')
    parser.add_argument('--radius', type=float, required=True, help='Radius around which to calculate rugosity')
    parser.add_argument('--output_path', type=str, required=True, help='Saving output path. Must be a .csv format.')
    
    args = parser.parse_args()
    
    main(mesh_path=args.mesh_path,
    trajectory_ply=args.trajectory_ply,
    trajectory_csv=args.trajectory_csv,
    radius=args.radius,
    output_path=args.output_path)


    
    