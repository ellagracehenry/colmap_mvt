import os
import sys

sys.path.append('/projects/elhe2720/software/multiviewtracks') # edit this
import MultiViewTracks as mvt
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from glob import glob

# Use absolute path to append to sys.path
project_path = "/scratch/alpine/elhe2720/colmap/project_3" #change project name

# Define absolute paths for model_path and tracks_path
model_path = os.path.join(project_path, 'sparse')  # Absolute path to the sparse directory
tracks_path = os.path.join(project_path, 'tracks')  # Absolute path to the tracks directory

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

# Get cameras information from the scene
scene.get_cameras()

#Make the camera path a continuous line
scene.interpolate_cameras()

#Triangulate fish points that are observed in both left and right
scene.triangulate_multiview_tracks()
#Calculate reprojection erros
scene.get_reprojection_errors()
#Project trajectory points observed in one view using interpolated depth from triangulated trajectories
scene.project_singleview_tracks()
#Combine triangulated and projected trajectories
scene.get_tracks_3d()

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
tracks_interpolated = mvt.tracks.interpolate_tracks(scene.tracks_3d)

#Extract points at resolution of choice
pts_2d = []
pts = []
for idx in tracks_interpolated['FRAME_IDX'][10::60]:
    if not np.all([np.isin(idx, tracks_interpolated[str(i)]['FRAME_IDX']) for i in tracks_interpolated['IDENTITIES']]):
        continue
    pts_3d = [np.transpose([tracks_interpolated[str(i)]['X'][tracks_interpolated[str(i)]['FRAME_IDX'] == idx],
                            tracks_interpolated[str(i)]['Y'][tracks_interpolated[str(i)]['FRAME_IDX'] == idx],
                            tracks_interpolated[str(i)]['Z'][tracks_interpolated[str(i)]['FRAME_IDX'] == idx]]) \
              for i in tracks_interpolated['IDENTITIES']]
    pts_2d.append(np.array(pts_3d)[:, :, :2].reshape(2, 2))
    pts.append(np.array(pts_3d))

#Interpolate 3D points between identities (don't think necessary for us)
pts = np.array(pts).reshape(-1, 2, 3)
x = pts[:, :, 0]
y = pts[:, :, 1]
z = pts[:, :, 2]
x_interpolated = []
y_interpolated = []
z_interpolated = []
for component, component_interpolated in zip([x, y, z], [x_interpolated, y_interpolated, z_interpolated]):
    for idx in range(component.shape[0]):
        component_interpolated.append(np.interp(np.linspace(0, 1, 100), np.array((0, 1)), component[idx, :]))
x_interpolated = np.array(x_interpolated)
y_interpolated = np.array(y_interpolated)
z_interpolated = np.array(z_interpolated)

#Create numpy array in same format as COLMAP reconstruction and write to .ply file
pts_interpolated = np.transpose([x_interpolated, y_interpolated, z_interpolated]).reshape(-1, 3)
rgb = np.zeros_like(pts_interpolated)
rgb[:, 0] = 255
point_cloud = np.append(pts_interpolated, rgb, axis=1)

tracks_3d_df = pd.DataFrame(point_cloud)
tracks_3d_df.to_csv("tracks_3d_output.csv", index=False)

print("3D tracks saved to tracks_3d_output.csv")
mvt.utils.write_ply(mvt.utils.pointcloud_to_ply(point_cloud),
                    file_name='3d_tracks.ply')
mvt.utils.write_ply(mvt.utils.pointcloud_to_ply(scene.point_cloud),
                    file_name='model.ply')
