
import os
import sys

sys.path.append('/projects/elhe2720/software/multiviewtracks_Gil_Lab') # edit this
import MultiViewTracks as mvt
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from glob import glob

print("mvt contents:", dir(mvt))

# Use absolute path to append to sys.path
project_path = "/scratch/alpine/elhe2720/colmap/project_3" #change project name

# Define absolute paths for model_path and tracks_path
model_path = os.path.join(project_path, 'sparse','0')  # Absolute path to the sparse directory
tracks_path = os.path.join(project_path, 'tracks')  # Absolute path to the tracks directory

print("Model path: {model_path}")
print("Tracks path: {tracks_path}")

# Debugging: Check directory contents
print("Contents of model path ({model_path}):", os.listdir(model_path))
print("Contents of tracks path ({tracks_path}):", os.listdir(tracks_path))

# Initialize the scene with absolute paths
scene = mvt.Scene(model_path=model_path,
                  tracks_path=tracks_path,
                  fisheye=False,
                  verbose=False)

#Get point cloud
scene.get_pointcloud()

# Get cameras information from the scene
scene.get_cameras()

#Make the camera path a continuous line
scene.interpolate_cameras()

#Triangulate fish points that are observed in both left and right
scene.triangulate_multiview_tracks()
#Calculate reprojection erros
scene.get_reprojection_errors()

# Gather all track identities visible in each camera
all_identities = []
for cam_id, cam in scene.cameras.items():
    if cam.tracks is not None:
        all_identities.append(cam.tracks['IDENTITIES'])

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


#Project trajectory points observed in one view using interpolated depth from triangulated trajectories
#scene.project_singleview_tracks()
#Combine triangulated and projected trajectories
#scene.get_tracks_3d()


#Select camera IDs
camera_ids = [1, 2]
#Input distance between
world_distance = 1

#Print camera IDs with their view numbers (how many frames)
for camera_id in camera_ids:
    print(scene.cameras[camera_id])

#Scale tracks and retrieve reconstruction errors (per-frame difference of the reconstructed camera positions and the known real world distance)
reconstruction_errors = scene.scale(camera_ids, world_distance)

#Rotate tracks to ensure the z is the depth of the scene (by making x and y of the tracks match the first two principal components of the camera paths)
scene.rotate()

#Plot with mesh
#Linearly interpolate  3D track for visualisation
if has_single_view_tracks:
    tracks_interpolated = mvt.tracks.interpolate_tracks(scene.tracks_3d)
else:
    tracks_interpolated = mvt.tracks.interpolate_tracks(scene.tracks_triangulated)

#Extract points at resolution of choice
pts_3d_interpolated = []

for idx in tracks_interpolated['FRAME_IDX']:
    if not np.all([np.isin(idx, tracks_interpolated[str(i)]['FRAME_IDX']) for i in tracks_interpolated['IDENTITIES']]):
        continue
    pts_3d = [np.transpose([tracks_interpolated[str(i)]['X'][tracks_interpolated[str(i)]['FRAME_IDX'] == idx],
                            tracks_interpolated[str(i)]['Y'][tracks_interpolated[str(i)]['FRAME_IDX'] == idx],
                            tracks_interpolated[str(i)]['Z'][tracks_interpolated[str(i)]['FRAME_IDX'] == idx]]) \
              for i in tracks_interpolated['IDENTITIES']]
    # Interpolate 3D points between frames
    pts_3d_interpolated.append(np.array(pts_3d))

pts_3d_interpolated = np.array(pts_3d_interpolated)

print(pts_3d_interpolated)
print(np.shape(pts_3d_interpolated))

frame_indices = np.array(tracks_interpolated['FRAME_IDX'])
x_interp, y_interp, z_interp = [], [], []    

# Now we will interpolate across the frames

# Since you only have one point per frame, this is how you can handle the interpolation



# Prepare x, y, z for interpolation

x_coords = pts_3d_interpolated[:, 0, 0, 0]  # Extract x values from the first column of the 3D array

y_coords = pts_3d_interpolated[:, 0, 0, 1]  # Extract y values from the second column

z_coords = pts_3d_interpolated[:, 0, 0, 2]  # Extract z values from the third column



# Interpolate across all frames

x_interp = np.interp(np.linspace(min(frame_indices), max(frame_indices), len(frame_indices)*10), frame_indices, x_coords)

y_interp = np.interp(np.linspace(min(frame_indices), max(frame_indices), len(frame_indices)*10), frame_indices, y_coords)

z_interp = np.interp(np.linspace(min(frame_indices), max(frame_indices), len(frame_indices)*10), frame_indices, z_coords)
    
# Combine the interpolated x, y, z coordinates into a single array
interpolated_points = np.stack((x_interp, y_interp, z_interp), axis=-1)
   
# Create numpy array in the same format as COLMAP reconstruction and write to .ply file
rgb = np.zeros_like(interpolated_points)  # Create an array for RGB colors
rgb[:, 0] = 255  # Set the points to be red
point_cloud = np.append(interpolated_points, rgb, axis=1)  # Combine the 3D points and RGB values



#x_interpolated = []
#y_interpolated = []
#z_interpolated = []
#for component, component_interpolated in zip([x, y, z], [x_interpolated, y_interpolated, z_interpolated]):
 #   for idx in range(component.shape[0]):
  #      component_interpolated.append(np.interp(np.linspace(0, 1, 100), np.array((0, 1)), component[idx, :]))
#x_interpolated = np.array(x_interpolated)
#y_interpolated = np.array(y_interpolated)
#z_interpolated = np.array(z_interpolated)

#Create numpy array in same format as COLMAP reconstruction and write to .ply file
#pts_interpolated = np.transpose([x_interpolated, y_interpolated, z_interpolated]).reshape(-1, 3)
#rgb = np.zeros_like(pts_interpolated)
#rgb[:, 0] = 255
#point_cloud = np.append(pts_interpolated, rgb, axis=1)

tracks_3d_df = pd.DataFrame(point_cloud)
tracks_3d_df.to_csv("project_3/tracks_3d_output.csv", index=False)

point_dim_t = 6
point_dim_m = 9

print("3D tracks saved to tracks_3d_output.csv")
mvt.utils.write_ply(mvt.utils.pointcloud_to_ply(point_cloud),point_dim_t,
                    file_name='project_3/3d_tracks.ply')
print("3D tracks saved to 3d_tracks.ply")
mvt.utils.write_ply(mvt.utils.pointcloud_to_ply(scene.point_cloud),point_dim_m,
                    file_name='project_3/model.ply')
print("model saved to model.ply")
