import pickle
import pandas as pd
import json
import numpy as np

# Define the identity at the top (only one identity here)
identity = 3495  # Identity as int64
identity_str = str(identity)  # Convert identity to string for the dictionary key

# Example file paths (update these accordingly)
left_json = r"C:\Users\ellag\Desktop\ACADEMIC PROJECTS\3D_tracking_pipeline\calibration\MH_151_060724_JM_left.json"
right_json = r"C:\Users\ellag\Desktop\ACADEMIC PROJECTS\3D_tracking_pipeline\calibration\MH_151_060724_JM_right.json"

# Step 1: Read the JSON files
with open(left_json) as file_L:
    data_L = json.load(file_L)
with open(right_json) as file_R:
    data_R = json.load(file_R)

# Extract fish position points and image IDs for left
annotations_L = data_L["annotations"]
points_L = [(item['image_id'], item['keypoints'][0], item['keypoints'][1]) for item in annotations_L]

# Extract fish position points and image IDs for right
annotations_R = data_R["annotations"]
points_R = [(item['image_id'], item['keypoints'][0], item['keypoints'][1]) for item in annotations_R]

# Convert to DataFrames for easier manipulation
df_L = pd.DataFrame(points_L, columns=["frame_idx", "x", "y"])
df_R = pd.DataFrame(points_R, columns=["frame_idx", "x", "y"])

# Extract unique frame indices for top-level key
frame_idx_L = np.sort(df_L["frame_idx"].unique())
frame_idx_R = np.sort(df_R["frame_idx"].unique())

# Initialize the final dictionary structure with the defined identity as int64
identity_dict_L = {"FRAME_IDX": frame_idx_L, "IDENTITIES": np.array([identity], dtype=np.int64)}
identity_dict_R = {"FRAME_IDX": frame_idx_R, "IDENTITIES": np.array([identity], dtype=np.int64)}

# Initialize the identity sub-dictionaries with string keys
identity_dict_L[identity_str] = {"FRAME_IDX": [], "X": [], "Y": []}
identity_dict_R[identity_str] = {"FRAME_IDX": [], "X": [], "Y": []}

# Collect data for all frames from left camera
for _, row in df_L.iterrows():
    identity_dict_L[identity_str]["FRAME_IDX"].append(row["frame_idx"])
    identity_dict_L[identity_str]["X"].append(row["x"])
    identity_dict_L[identity_str]["Y"].append(row["y"])

# Collect data for all frames from right camera
for _, row in df_R.iterrows():
    identity_dict_R[identity_str]["FRAME_IDX"].append(row["frame_idx"])
    identity_dict_R[identity_str]["X"].append(row["x"])
    identity_dict_R[identity_str]["Y"].append(row["y"])

# Convert lists to numpy arrays
identity_dict_L[identity_str]["FRAME_IDX"] = np.array(identity_dict_L[identity_str]["FRAME_IDX"], dtype=np.int64)
identity_dict_L[identity_str]["X"] = np.array(identity_dict_L[identity_str]["X"])
identity_dict_L[identity_str]["Y"] = np.array(identity_dict_L[identity_str]["Y"])

identity_dict_R[identity_str]["FRAME_IDX"] = np.array(identity_dict_R[identity_str]["FRAME_IDX"], dtype=np.int64)
identity_dict_R[identity_str]["X"] = np.array(identity_dict_R[identity_str]["X"])
identity_dict_R[identity_str]["Y"] = np.array(identity_dict_R[identity_str]["Y"])

# Save the dictionaries as pickle files
with open("identity_points_L.pkl", "wb") as f_L:
    pickle.dump(identity_dict_L, f_L)

with open("identity_points_R.pkl", "wb") as f_R:
    pickle.dump(identity_dict_R, f_R)

print("Pickle files for left and right cameras saved successfully.")

# Load and print the pickle file contents
with open("identity_points_L.pkl", "rb") as f_L:
    identity_dict_L_loaded = pickle.load(f_L)
    print("Contents of identity_points_L.pkl:")
    print(identity_dict_L_loaded)

with open("identity_points_R.pkl", "rb") as f_R:
    identity_dict_R_loaded = pickle.load(f_R)
    print("\nContents of identity_points_R.pkl:")
    print(identity_dict_R_loaded)
