import sys
import os

# Use absolute path to append to sys.path
project_path = r"C:\Users\ellag\Desktop\ACADEMIC PROJECTS\3D_tracking_pipeline\colmap"
sys.path.append(project_path)

# Now import your modules
import MultiViewTracks as mvt
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

# Define absolute paths for model_path and tracks_path
model_path = os.path.join(project_path, 'data', 'sparse')  # Absolute path to the sparse directory
tracks_path = os.path.join(project_path, 'data', 'tracks')  # Absolute path to the tracks directory

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

#Plot multi view triangulation
fig, axes = plt.subplots(3, 1, figsize=(20, 20), sharey=True, sharex=True)
axes[0] = mvt.utils.plot_tracks_2d(scene.tracks_triangulated, ax=axes[0], show=False, size=0.1, style='errors')
axes[1] = mvt.utils.plot_tracks_2d(scene.tracks_projected, ax=axes[1], show=False, size=0.1)
axes[2] = mvt.utils.plot_tracks_2d(scene.tracks_3d, ax=axes[2], show=True, size=0.1);

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

#Plot on top of dense point clo
fig, ax = plt.subplots(figsize=(20, 20))
ax.axes.axis('off')
ax.scatter(scene.point_cloud[:, 0], scene.point_cloud[:, 1], s=0.02, c=scene.point_cloud[:, 3:] / 255)
lc = ax.plot(*np.transpose(pts_2d), c='r', lw=2.5, solid_capstyle='round')
ax.set_aspect('equal');

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
mvt.utils.write_ply(mvt.utils.pointcloud_to_ply(point_cloud),
                    file_name='./data/dense/visualization_calibration_wand.ply')
mvt.utils.write_ply(mvt.utils.pointcloud_to_ply(scene.point_cloud),
                    file_name='./data/dense/visualization_reconstruction.ply')

#Use mesh lab to load and visualise 