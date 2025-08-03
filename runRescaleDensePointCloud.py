import os
import sys

sys.path.append('/projects/elhe2720/software/multiviewtracks') # edit this
import MultiViewTracks as mvt
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
from glob import glob

print("mvt contents:", dir(mvt))

# Use absolute path to append to sys.path
project_path = "/scratch/alpine/elhe2720/colmap/project_200725" #change project name

# Define absolute paths for model_path and tracks_path
model_path = os.path.join(project_path, 'sparse','0')  # Absolute path to the sparse directory
#tracks_path = os.path.join(project_path, 'tracks')  # Absolute path to the tracks directory

print("Model path: {model_path}")
#print("Tracks path: {tracks_path}")

# Debugging: Check directory contents
print("Contents of model path ({model_path}):", os.listdir(model_path))
#print("Contents of tracks path ({tracks_path}):", os.listdir(tracks_path))

# Initialize the scene with absolute paths
scene = mvt.Scene(model_path=model_path,
                  tracks_path = model_path,
                  fisheye=False,
                  verbose=True)
                  
                  



#Get point cloud
scene.get_pointcloud()

# Get cameras information from the scene
scene.get_cameras()

#Make the camera path a continuous line
scene.interpolate_cameras()

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

point_dim_m = 9

mvt.utils.write_ply(mvt.utils.pointcloud_to_ply(scene.point_cloud),point_dim_m,
                    file_name='project_200725/resecaled_no_track_model.ply')
print("model saved to model.ply")
