import os
import sys

sys.path.append('/projects/maha7624/software/multiviewtracks_Gil_Lab') # edit this
import MultiViewTracks as mvt
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from glob import glob
import centroids_functions as cf
from pathlib import Path

def main(project_dir,
        trial_name,
        masks_path_L,
        masks_path_R,
        extracted_fps,
        final_fps,
        world_distance,
        err_threshold,
        extract_centroids,
        interpolate_points,
        used_AMC,
        run_dense,
        csv_error_path=None,
        observation_id_L=None,
        observation_id_R=None
    ):
    
    ##### Extract Centroids from Masks #####
    print(f"trial directory is: {project_dir}")
    print(f"left masks path is: {masks_path_L}. Right masks path is {masks_path_R}")
    
    ### Define output paths
    # Make tracks directory
    tracks_path=os.path.join(project_dir, "tracks")
    os.makedirs(tracks_path, exist_ok=True)

    # Define temporary centroids files
    temp_path_L = os.path.join(tracks_path, "centroids_L.npy")
    temp_path_R = os.path.join(tracks_path, "centroids_R.npy")

    output_path_L = os.path.join(tracks_path, "tracks_left.pkl")
    output_path_R = os.path.join(tracks_path, "tracks_right.pkl")

    excised_path_L = os.path.join(tracks_path, "excised_L.npy")
    excised_path_R = os.path.join(tracks_path, "excised_R.npy")

    if extract_centroids==True:
        sub=int(extracted_fps/final_fps)
        # Calculate centroids from SAM2 masks
        if used_AMC==True:
            cf.process_coco_masks(masks_path_L, temp_path_L, sub)
            cf.process_coco_masks(masks_path_R, temp_path_R, sub)
        else:
            cf.process_masks(masks_path_L, temp_path_L, sub)
            cf.process_masks(masks_path_R, temp_path_R, sub)
            
        # This code can be used if any additional erroneous frames were missed by the AMC
        # Can alternatively manually remove poor centroids here
        # Excise erroneous SAM2 frames
        #remove_frames=[0,1,2]
        #cf.excise_centroids(temp_path_L, output_file=excised_path_L, remove_frames=remove_frames)
        #cf.excise_centroids(temp_path_R, output_file=excised_path_R, remove_frames=remove_frames)
        #cf.remove_centroids_from_csv(temp_path_L, csv_error_path, observation_id_L, excised_path_L)
        #cf.remove_centroids_from_csv(temp_path_R, csv_error_path, observation_id_R, excised_path_R)
        # Reformat centroids to COLMAP compatible PKL file
        #cf.PKL_REFORMAT(excised_path_L, output_path_L)
        #cf.PKL_REFORMAT(excised_path_R, output_path_R)

        # Reformat centroids to COLMAP compatible PKL file
        cf.PKL_REFORMAT(temp_path_L, output_path_L)
        cf.PKL_REFORMAT(temp_path_R, output_path_R)


    ##### Triangulate positions ##### 
    print("mvt contents:", dir(mvt))

    # Select the model path that has the largest images.bin
    model_path = None
    parent_sparse_dir = Path(project_dir) / "sparse"  # Absolute path to the parent sparse directory
    largest_size = -1
    for subdir in parent_sparse_dir.iterdir():
        if subdir.is_dir():
            img_file = subdir / "images.bin"
            if img_file.exists():
                size = img_file.stat().st_size
                if size > largest_size:
                    largest_size = size
                    model_path = subdir

    print(f"Sparse model used is {model_path}.")
    
    # Define absolute paths for tracks_path

    tracks_path = os.path.join(project_dir, 'tracks')  # Absolute path to the tracks directory

    print(f"Model path: {model_path}")
    print(f"Tracks path: {tracks_path}")

    # Debugging: Check directory contents
    print(f"Contents of model path ({model_path}):", os.listdir(model_path))
    print(f"Contents of tracks path ({tracks_path}):", os.listdir(tracks_path))

    # Initialize the scene with absolute paths
    scene = mvt.Scene(model_path=model_path,
                    tracks_path=tracks_path,
                    fisheye=False,
                    verbose=False)

    #Get point cloud
    scene.get_pointcloud()

    # Get cameras information from the scene
    scene.get_cameras()
    
    if interpolate_points:
        #Make the camera path a continuous line
        scene.interpolate_cameras()
    else:
        print("Not interpolating points. If a continuous line is desired, use --interpolate_points")
    #Triangulate fish points that are observed in both left and right
    scene.triangulate_multiview_tracks()

    #Calculate reprojection errors
    scene.get_reprojection_errors()

    # Gather all track identities visible in each camera
    all_identities = []
    for cam_id, cam in scene.cameras.items():
        if cam.tracks is not None:
            all_identities.append(cam.tracks['IDENTITIES'])
    print(f"all identiies: {all_identities}")

    if not all_identities:
        print("No camera tracks available, skipping project_singleview_tracks")
    else:
        all_identities = np.unique(np.concatenate(all_identities))
    
        # Check for single view frames (frames visible in exactly one camera) per identity
        has_single_view_tracks = False
        for identity in all_identities:
            # Get all frames where this identity is visible in any camera
            frames_per_camera = []
            for cam_id, cam in scene.cameras.items():
                frames = cam.frames_in_view(identity)
                if frames.size > 0:
                    frames_per_camera.append(set(frames))
        
            if not frames_per_camera:
                continue
        
            # Union of all frames where identity is seen
            all_frames = set.union(*frames_per_camera)
        
            # For each frame, count how many cameras see this identity
            for frame in all_frames:
                visible_count = sum([1 for frames in frames_per_camera if frame in frames])
                if visible_count == 1:
                    has_single_view_tracks = True
                    break
            if has_single_view_tracks:
                break

        if has_single_view_tracks:
            print("Single-view tracks detected, running project_singleview_tracks()")
            scene.project_singleview_tracks()
            scene.get_tracks_3d()
        else:
            print("No single-view tracks found, skipping project_singleview_tracks()")
            scene.get_tracks_3d()



    # Combine triangulated and projected trajectories
    #scene.get_tracks_3d()

    # Select camera IDs
    camera_ids = [1, 2]


    # Print camera IDs with their view numbers (how many frames)
    #for camera_id in camera_ids:
    #    print(scene.cameras[camera_id])

    # Scale tracks and retrieve reconstruction errors (per-frame difference of the reconstructed camera positions and the known real world distance)
    reconstruction_errors = scene.scale(camera_ids, world_distance)

    # Rotate tracks to ensure the z is the depth of the scene (by making x and y of the tracks match the first two principal components of the camera paths)
    scene.rotate()

    #### Make Error Plots
    # retrieve the two cameras which were used for scaling from the scene
    cameras = [scene.cameras[camera_ids[0]], scene.cameras[camera_ids[1]]]
    # generate masks for each camera view indices in which both cameras are reconstructed
    reconstructed = [np.isin(cameras[0].view_idx, cameras[1].view_idx),
                    np.isin(cameras[1].view_idx, cameras[0].view_idx)]
    # retrieve the camera center paths for both cameras with applied masks
    pts_3d = [np.array([cameras[0].projection_center(idx) for idx in cameras[0].view_idx])[reconstructed[0]],
            np.array([cameras[1].projection_center(idx) for idx in cameras[1].view_idx])[reconstructed[1]]]
    # calculate the scale factor and the reconstruction errors
    distances = np.sqrt(np.square(pts_3d[0] - pts_3d[1]).sum(axis=1))
    scale = world_distance / distances.mean()
    distances = distances * scale
    # now calculate the reconstruction errors.
    # these are same as returned by scene.scale, but we needed the camera paths for later visualization.
    errors = distances - distances.mean()


    fig, axes = plt.subplots(1, 2, sharex=True, figsize=(15, 4))
    sns.distplot(errors, bins=100, ax=axes[0])
    sns.distplot(errors, bins=100, ax=axes[1], kde=False, hist=False, rug=True, rug_kws={'height': 1, 'alpha': 0.2})
    axes[1].set_ylim((0, 1));

    # Plot histogram of reconstruction errors
    fig, axes = plt.subplots(1, 2, sharex=True, figsize=(15, 4))
    sns.distplot(errors, bins=100, ax=axes[0])
    sns.distplot(errors, bins=100, ax=axes[1], kde=False, hist=False, rug=True, rug_kws={'height': 1, 'alpha': 0.2})
    axes[1].set_ylim((0, 1));
    fig.savefig(os.path.join(project_dir,"error_hist.png"), dpi=300, bbox_inches='tight')

    # Plot multiview triangulation path with reconstruction errors
    fig = plt.figure(figsize=(12, 10))
    ax = fig.add_axes([0, 0, 1, 1])
    for camera_path in pts_3d:
        mappable = ax.scatter(camera_path[:, 1], camera_path[:, 0], cmap=plt.get_cmap('Spectral_r'), c=np.absolute(errors), s=0.25)
    ax.set_aspect('equal')
    cax = fig.add_axes([1.05, 0.2, 0.01, 0.6])
    fig.colorbar(mappable, cax=cax);
    fig.savefig(os.path.join(project_dir, "error_path.png"), dpi=300, bbox_inches='tight')


    #Linearly interpolate  3D track for visualisation
    if interpolate_points:
        if has_single_view_tracks:
            tracks = mvt.tracks.interpolate_tracks(scene.tracks_3d)
        else:
            tracks = mvt.tracks.interpolate_tracks(scene.tracks_triangulated)
    else:
        if has_single_view_tracks:
            tracks = scene.tracks_3d
        else:
            tracks = scene.tracks_triangulated

    def extract_valid_3d_points(tracks, reconstruction_errors, err_threshold):
        pts_3d = []
        frame_indices = []
        deleted_errors = []

        for err, idx in zip(reconstruction_errors, tracks['FRAME_IDX']):

            # Remove high-error frames
            if abs(err) > err_threshold:
                deleted_errors.append(err)
                continue

            # Require all identities to be present
            if not np.all([
                np.isin(idx, tracks[str(i)]['FRAME_IDX'])
                for i in tracks['IDENTITIES']
            ]):
                continue

            frame_pts = [
                np.transpose([
                    tracks[str(i)]['X'][tracks[str(i)]['FRAME_IDX'] == idx],
                    tracks[str(i)]['Y'][tracks[str(i)]['FRAME_IDX'] == idx],
                    tracks[str(i)]['Z'][tracks[str(i)]['FRAME_IDX'] == idx],
                ])
                for i in tracks['IDENTITIES']
            ]

            pts_3d.append(np.array(frame_pts))
            frame_indices.append(idx)

        print(f"{len(deleted_errors)} positions were removed due to triangulation error above {err_threshold}.")
        print(f"{len(frame_indices)} positions were retained for the track.")

        if len(frame_indices) == 0:
            print("No positions of sufficient quality were retained. Quitting triangulation. Check masks and fused.ply for massive errors")
            path_exists=False
            #sys.exit() 
        else:
            path_exists=True

        return np.array(pts_3d), np.array(frame_indices), path_exists
    
    def interpolate_3d_points(pts_3d, frame_indices, upsample_factor=10):
        # Assumes one identity, one point per frame
        x = pts_3d[:, 0, 0, 0]
        y = pts_3d[:, 0, 0, 1]
        z = pts_3d[:, 0, 0, 2]

        interp_frames = np.linspace(
            frame_indices.min(),
            frame_indices.max(),
            len(frame_indices) * upsample_factor
        )

        x_i = np.interp(interp_frames, frame_indices, x)
        y_i = np.interp(interp_frames, frame_indices, y)
        z_i = np.interp(interp_frames, frame_indices, z)

        return np.stack((x_i, y_i, z_i), axis=-1)

    point_dim_t = 6
    point_dim_m = 9
    

    pts_3d_raw, frame_indices, path_exists = extract_valid_3d_points(
        tracks,
        reconstruction_errors,
        err_threshold
        )
        
    if path_exists:
        if interpolate_points:
            pts_3d_final = interpolate_3d_points(pts_3d_raw, frame_indices)
        else:
            # Flatten raw points to (N, 3)
            pts_3d_final = pts_3d_raw[:, 0, 0, :]

        rgb = np.zeros_like(pts_3d_final)
        rgb[:, 0] = 255  # red points

        ply_points = np.hstack((pts_3d_final, rgb))   # ALWAYS 6 cols for PLY

        if interpolate_points:
            csv_points = ply_points
            columns = ["X","Y","Z","R","G","B"]
        else:
            frame_indices_2d = frame_indices.reshape(-1, 1)  # shape (N,1)
            csv_points = np.hstack((frame_indices_2d, ply_points))
            columns=["frame","X", "Y", "Z", "R", "G", "B"]

        tracks_3d_df = pd.DataFrame(csv_points,columns=columns)
    

    
        # Save 3D Tracks
        tracks_3d_df.to_csv(
            os.path.join(project_dir, f"{trial_name}_tracks_3d_output.csv"),
            index=False
        )

        print(f"3D tracks saved to {trial_name}_tracks_3d_output.csv")
    
        mvt.utils.write_ply(mvt.utils.pointcloud_to_ply(ply_points),point_dim_t,
                            file_name=os.path.join(project_dir,f"{trial_name}_3d_tracks.ply"))
        print(f"3D tracks saved to {trial_name}_3d_tracks.ply")

    
    # Save rescaled model
    if run_dense==True:
        mvt.utils.write_ply(mvt.utils.pointcloud_to_ply(scene.point_cloud),point_dim_m,
                        file_name=os.path.join(project_dir,"dense", f"{trial_name}_scaled_fused.ply"))
        print(f"dense rescaled model saved to {trial_name}_scaled_fused.ply")

    else:
        mvt.utils.write_ply(mvt.utils.pointcloud_to_ply(scene.point_cloud),point_dim_t,
                        file_name=os.path.join(project_dir,"sparse", f"{trial_name}_scaled_sparse.ply"))       
        print(f"sparse_rescaled model saved to {trial_name}_scaled_sparse.ply")


# Run Main Loop
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Extracting centroids and running MVT')
    parser.add_argument('--project_dir', type=str, required=True, help='Project directory for reconstruction')
    parser.add_argument('--trial_name', type=str, required=True, help='Trial name for labelling')
    parser.add_argument('--masks_path_L', type=str, required=True, help='Path left masks file')
    parser.add_argument('--masks_path_R', type=str, required=True, help='Path to right masks file')
    parser.add_argument('--extracted_fps', type=int, default=3, help='Original FPS of synced & extracted images')
    parser.add_argument('--final_fps', type=int, default=1, help='Overlap ratio for temporal chunking')
    parser.add_argument('--world_distance', type=float, default=1, help='Inter-camera distance for this trial')
    parser.add_argument('--err_threshold', type=float, default=.01, help='Error threshold for triangulation')
    
    parser.add_argument('--extract_centroids', action='store_true',
                    help='Extract centroids from mask files and reformat for MVT')
    parser.add_argument('--no_extract_centroids', dest='extract_centroids',
                    action='store_false',
                    help='Skip centroid extraction and reformatting')
    parser.set_defaults(extract_centroids=True)
    
    parser.add_argument('--interpolate_points', action='store_true',
                    help='Interpolate between known positions during triangulation')
    parser.add_argument('--no_interpolate_points', dest='interpolate_points',
                    action='store_false',
                    help='Skip interpolation in triangulation')
    parser.set_defaults(interpolate_points=True)
    
    parser.add_argument('--used_AMC', action='store_true',
                    help='If Automatic Mask Cleaner was used, specify so .json masks can be used')
    parser.add_argument('--no_AMC', dest='used_AMC',
                    action='store_false',
                    help='Using .pkl masks directly from SAM2')
    parser.set_defaults(used_AMC=True)
    parser.add_argument('--run_dense', action='store_true',
                    help='Rescaling dense point cloud')
    parser.add_argument('--no_run_dense', dest='run_dense',
                    action='store_false',
                    help='Rescaling sparse point cloud')
    parser.set_defaults(run_dense=True)
    
    parser.add_argument('--csv_error_path', type=str, required=False, help='Path to errors.csv to remove centroids from erroneous masks, if not already done by AMC')
    parser.add_argument('--observation_id_L', type=str, required=False, help='Name of left observation ID according to errors.csv')
    parser.add_argument('--observation_id_R', type=str, required=False, help='Name of right observation ID according to errors.csv')

    args = parser.parse_args()
    
    main(
        project_dir=args.project_dir,
        trial_name=args.trial_name,
        masks_path_L=args.masks_path_L,
        masks_path_R=args.masks_path_R,
        extracted_fps=args.extracted_fps,
        final_fps=args.final_fps,
        world_distance=args.world_distance,
        err_threshold=args.err_threshold,
        extract_centroids=args.extract_centroids,
        interpolate_points=args.interpolate_points,
        used_AMC=args.used_AMC,
        csv_error_path=args.csv_error_path,
        observation_id_L=args.observation_id_L,
        observation_id_R=args.observation_id_R,
        run_dense=args.run_dense
        
    )