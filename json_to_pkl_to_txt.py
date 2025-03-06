import json
import pickle
import pandas as pd

# USER EDITS HERE: Change both names to the names of your exported CVAT json files (left and right)
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

# Initialize identity dict as standard dictionaries (no lambda function)
identity_dict_L = {}
identity_dict_R = {}

identityL = 1
identityR = 2

# Collect data for all frames from left camera
for _, row in df_L.iterrows():
    if identityL not in identity_dict_L:
        identity_dict_L[identityL] = {'FRAME_IDX': [], 'X': [], 'Y': []}
    identity_dict_L[identityL]['FRAME_IDX'].append(row['frame_idx'])
    identity_dict_L[identityL]['X'].append(row['x'])
    identity_dict_L[identityL]['Y'].append(row['y'])



# Collect data for all frames from right camera
for _, row in df_R.iterrows():
    if identityR not in identity_dict_R:
        identity_dict_R[identityR] = {'FRAME_IDX': [], 'X': [], 'Y': []}
    identity_dict_R[identityR]['FRAME_IDX'].append(row['frame_idx'])
    identity_dict_R[identityR]['X'].append(row['x'])
    identity_dict_R[identityR]['Y'].append(row['y'])

# Convert lists to numpy arrays for better data handling
identity_dict_L[identityL]['FRAME_IDX'] = pd.Series(identity_dict_L[identityL]['FRAME_IDX']).to_numpy()
identity_dict_L[identityL]['X'] = pd.Series(identity_dict_L[identityL]['X']).to_numpy()
identity_dict_L[identityL]['Y'] = pd.Series(identity_dict_L[identityL]['Y']).to_numpy()

identity_dict_R[identityR]['FRAME_IDX'] = pd.Series(identity_dict_R[identityR]['FRAME_IDX']).to_numpy()
identity_dict_R[identityR]['X'] = pd.Series(identity_dict_R[identityR]['X']).to_numpy()
identity_dict_R[identityR]['Y'] = pd.Series(identity_dict_R[identityR]['Y']).to_numpy()

# Save the dictionaries as pickle files
with open("identity_points_L.pkl", "wb") as f_L:
    pickle.dump(identity_dict_L, f_L)

with open("identity_points_R.pkl", "wb") as f_R:
    pickle.dump(identity_dict_R, f_R)

print("Fish points saved successfully for left and right cameras in the identity dictionary format.")

# Now, load the pickle file and print its contents to a text file
def save_dict_to_txt(pickle_file, txt_file):
    with open(pickle_file, "rb") as f:
        data = pickle.load(f)

    # Writing the ID list at the top of the file
    with open(txt_file, 'w') as f:
        identities = list(data.keys())
        f.write(f"IDENTITIES: {identities}\n")  # List of identities at the top
        
        # For each identity, print its data
        for identity, frames in data.items():
            f.write(f"{identity}: {{'FRAME_IDX': array({frames['FRAME_IDX']}, dtype=int64), 'X': array({frames['X']}), 'Y': array({frames['Y']})}}\n")
            f.write("\n" + "="*50 + "\n")

# Convert the identity dictionary to a readable text file
save_dict_to_txt("identity_points_L.pkl", "identity_points_L.txt")
save_dict_to_txt("identity_points_R.pkl", "identity_points_R.txt")

print("Pickle data has been saved to text files for reading.")
