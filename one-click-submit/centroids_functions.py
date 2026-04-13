#!/usr/bin/env python
import gc
import numpy as np
import os
import pickle
import torch
import math
import csv
import json
from collections import defaultdict
from pycocotools import mask as maskUtils




def compute_centroid(dense_mask):
    """
    Given a dense mask tensor, compute the centroid of the True pixels.

    The mask is assumed to be indexed as (row, col) = (y, x).
    This function RETURNS (x, y) to match image plotting conventions.

    If the mask is three-dimensional (e.g. shape [1, H, W]),
    the first dimension is ignored.

    If the mask is empty, returns (np.nan, np.nan).
    """
    indices = torch.nonzero(dense_mask, as_tuple=False)

    if indices.numel() == 0:
        return (float("nan"), float("nan"))

    # If mask is [C, H, W], drop channel index
    if indices.shape[1] > 2:
        indices = indices[:, 1:]  # keep (row, col)

    # Mean row, col
    row, col = indices.float().mean(dim=0)

    # RETURN (x, y)
    x = col.item()
    y = row.item()

    return (x, y)
    
def compute_centroid_coco(mask: np.ndarray):
    """
    Compute the centroid of a dense NumPy mask.

    mask: HxW or 1xHxW boolean or binary array

    The mask is indexed as (row, col) = (y, x).
    This function RETURNS (x, y) to match image plotting conventions.

    Returns:
        (x, y) as floats
    """
    # Handle optional channel dimension
    if mask.ndim > 2:
        mask = mask[0]

    # Get (row, col) indices of foreground pixels
    rows, cols = np.nonzero(mask)

    if rows.size == 0:
        return (float("nan"), float("nan"))

    # Mean row, col
    row = rows.mean()
    col = cols.mean()

    # RETURN (x, y)
    x = float(col)
    y = float(row)

    return (x, y)
    

def remove_centroids_from_csv(
    centroid_file,
    csv_file,
    observation_id,
    output_file=None):
    """
    Replaces centroid values with NaN for frames in specified ranges based on a CSV describing invalid intervals.

    CSV format (0-based columns):
        0 = observation ID
        3 = start frame (inclusive)
        4 = end frame (inclusive)
    
    Args:
        centroid_file: path to .npy centroid dictionary
        csv_file: the .csv containing frame ranges
        observation_id: ID to match in column 0
        output_file: where to save cleaned centroids. If None, overwrite.
        # Note: Should be edited to add fishID for stationary
    TODO: Incorporate ObjID
    """
    # Load centroid dictionary
    centroids = np.load(centroid_file, allow_pickle=True).item()
    
    # Collect all ranges for this observation ID
    ranges_to_nan = []
    
    with open(csv_file, "r") as f:
        reader = csv.reader(f, delimiter=",")
        for row in reader:
            if row[0].strip() == observation_id.strip():
                try:
                    start = int(row[3])
                    end   = int(row[4])
                    ranges_to_nan.append((start, end))
                except ValueError:
                    print("Skipping invalid row:", row)

    if not ranges_to_nan:
        print(f"No matching rows found for observation ID '{observation_id}'")
        print(f"Saving original centroids for {observation_id} to {output_file}.")
        np.save(output_file, centroids)
        return

    print(f"Removing ranges for observation '{observation_id}': {ranges_to_nan}")
    
    # Remove frames in each range
    for start, end in ranges_to_nan:
        for frame in range(start, end + 1):
            if frame in centroids:
            # Replace all object centroids in this frame
                for obj_id in centroids[frame].keys():
                    centroids[frame][obj_id] = (math.nan, math.nan)

    # Save the modified dictionary
    if output_file is None:
        output_file = centroid_file

    np.save(output_file, centroids)
    print(f"Saved cleaned centroids to {output_file}")
    
    
def excise_centroids(
    centroid_file,
    output_file=None,
    remove_frames = None,
    remove_frame_range=None,
    remove_objects=None
):
    """
    Remove centroids based on frame indices and/or object IDs.

    Args:
        centroid_file (str): Path to the .npy file created by process_masks.
        output_file (str): Where to save the filtered centroids.
                           If None, overwrites the input file.
        remove_frames (list[int]): Specific frame indices to remove completely.
        remove_frame_range (tuple[int,int]): (start, end) inclusive frame range to remove.
        remove_objects (dict[int, list[int]]):
            { frame_idx: [obj_id1, obj_id2, ...] }
            Remove only these objects for the specified frames.
            
        TODO: Incorporate ObjID
    """
     # Load dictionary
    centroids = np.load(centroid_file, allow_pickle=True).item()
    if remove_frames:
        for f in remove_frames:
            if f in centroids:
                for obj_id in centroids[f]:
                    centroids[f][obj_id]=(math.nan, math.nan)
                    print(f"Setting centroids in frame {f} to NaN")
    
    if remove_frame_range:
        start, end = remove_frame_range
        for f in range (start, end + 1):
            if f in centroids:
                for obj_id in centroids[f]:
                    centroids[f][obj_id] = (math.nan, math.nan)
                    print(f"Setting centroids in frame {f} to NaN")
    
    if remove_objects:
        # Example: remove_objects = { 10: [3,5], 14: [2] }
        for f, obj_ids in remove_objects.items():
            if f in centroids:
                for obj in obj_ids:
                    if obj in centroids[f]: 
                        centroids[f][obj] = (math.nan, math.nan)
                    centroids[f].pop(obj, None)
    
    if output_file is None:
        output_file = centroid_file  # overwrite  
        print(f"Warning, overwriting {centroid_file} with NaN-filled points")
    
    np.save(output_file, centroids)
    print(f"Filtered centroids saved to {output_file}")

    
def process_masks(pickle_file, output_file, sub):
    # Load the pickle file that contains the frame masks dictionary.
    # The dictionary structure is assumed to be:
    # { frame_idx: { obj_id: sparse_mask_tensor, ... }, ... }
    with open(pickle_file, 'rb') as f:
        frame_masks = pickle.load(f)
    
    # Set batch size (number of frames to process at once)
    BATCH_SIZE = 10
    # Prepare a dictionary to store centroids for each frame and each object.
    centroids = {}
    
    # Process frames in sorted order in batches of BATCH_SIZE.
    all_frames = sorted(frame_masks.keys())
    all_frames=all_frames[::sub]
    total_frames = len(all_frames)
    print(total_frames)
    for batch_start in range(0, total_frames, BATCH_SIZE):
        batch_frames = all_frames[batch_start:batch_start+BATCH_SIZE]
        print (batch_frames)
        print(f"Processing frames {batch_start} to {batch_start + len(batch_frames) - 1}...")
        for frame in batch_frames:
            centroids[int(frame)+1] = {}
            obj_dict = frame_masks[frame]
            for obj_id, sparse_mask in obj_dict.items():
                # Convert sparse mask to dense.
                dense_mask = sparse_mask.to_dense()
                # Compute the centroid of the mask.
                centroid = compute_centroid(dense_mask)
                centroids[int(frame)+1][obj_id] = centroid

                # Delete the dense mask to free memory.
                del dense_mask
                gc.collect()
        # Clear any lingering objects and force garbage collection after processing a batch.
        gc.collect()
    # Save the centroids dictionary to a .npy file.
    np.save(output_file, centroids)
    print(f"Centroids saved to {output_file}")

def coco_segmentation_to_mask(segmentation, height, width):
    """
    Converts COCO polygon or RLE to a dense binary mask
    """
    rle = maskUtils.frPyObjects(segmentation, height, width)
    mask = maskUtils.decode(rle)
    return mask.astype(bool)
    
def process_coco_masks(
    coco_json,
    output_file,
    sub=1,
    batch_size=10
):
    """
    coco_json: path to COCO annotations (.json)
    output_file: .npy output path
    sub: frame subsampling factor
    """

    with open(coco_json, "r") as f:
        coco = json.load(f)
        
    # image_id → image metadata
    images_by_id = {img["id"]: img for img in coco["images"]}

    # frame_name (no extension) → image metadata
    images_by_name = {
        img["file_name"].rsplit(".", 1)[0]: img
        for img in coco["images"]
    }

    # Group annotations by frame name
    ann_by_image = defaultdict(list)
    for ann in coco["annotations"]:
        frame_name = images_by_id[ann["image_id"]]["file_name"].rsplit(".", 1)[0]
        ann_by_image[frame_name].append(ann)
        
    all_frames = sorted(ann_by_image.keys())
    total_frames = len(all_frames)
    print(f"Total frames: {total_frames}")

    centroids = {}

    for batch_start in range(0, total_frames, batch_size):
        batch_frames = all_frames[batch_start:batch_start + batch_size]
        print(f"Processing frames {batch_start} to {batch_start + len(batch_frames) - 1}")

        for frame_id in batch_frames:
            img = images_by_name[frame_id]
            H, W = img["height"], img["width"]

            centroids[int(frame_id)] = {}

            for ann in ann_by_image.get(frame_id, []):
                fish_id = ann["attributes"]["ObjID"] 

                mask = coco_segmentation_to_mask(
                    ann["segmentation"],
                    H,
                    W
                )

                centroid = compute_centroid_coco(mask)
                centroids[int(frame_id)][fish_id] = centroid

                del mask
                gc.collect()

        gc.collect()

    np.save(output_file, centroids)
    print(f"Centroids saved to {output_file}")
    
def PKL_REFORMAT(centroid_npy, PKL_output):
    #load the numpy array
    npy_array = np.load(centroid_npy, allow_pickle=True)
    #create empty arrays for the X, Y, and Frame_IDX values
    Frame_Total = np.array([], dtype=np.int64)
    #Sets the Identities 
    Identities = np.array([], dtype=np.int64)

    for key in npy_array.item():
        Frame_Total = np.append(Frame_Total, key)
        for value in npy_array.item()[key]:
            if value not in Identities:
                Identities = np.append(Identities, value)

    #Formats the dictionary for COLMAP
    reformatted_dict = {'FRAME_IDX': Frame_Total, 'IDENTITIES': Identities}
    print(npy_array)
    #Iterate through the numpy array and append the values to the X, Y, and Frame_IDX arrays
    for i in Identities:
        X = np.array([])
        Y = np.array([])
        Frame_IDX = np.array([], dtype=np.int64)
        for key in npy_array.item():
            for value in npy_array.item()[key]:
                if value == i:
                    #Check if the centroid is not NaN before appending
                    if str(npy_array.item()[key][value][0]) != 'nan':
                        #Appends the appropriate values to the X, Y, and Frame_IDX arrays
                        X=np.append(X, npy_array.item()[key][value][0])
                        Y=np.append(Y, npy_array.item()[key][value][1])
                        Frame_IDX=np.append(Frame_IDX, key)
        ID_Dict= {'FRAME_IDX': Frame_IDX, 'X': np.round(X, 2), 'Y': np.round(Y,2)}
        reformatted_dict[str(i)] = ID_Dict


    with open(PKL_output, "wb") as file:
        # Use pickle.dump() to serialize the dictionary and write it to the file
        pickle.dump(reformatted_dict, file)

def rename(Initials, ObsID, base_path,Left_Folder, Right_Folder):
    base_path+= "/"

    #Set directory to the left folder
    os.chdir(os.path.join(base_path,Left_Folder))
    #Loop through all files in the left folder
    for filename in os.listdir(os.path.join(base_path, Left_Folder)):
        #Check if the file is a .jpg file and does not already start with "right_"
        if filename.endswith('.jpg') and not filename.startswith('{ObsID}L_'):
            #Adds "left_" before filename
            new_filename = str(f"{ObsID}L_" + filename)
            os.rename(filename, new_filename)

    #Set directory to the right folder
    os.chdir(os.path.join(base_path,Right_Folder))
    #Loop through all files in the right folder
    for filename in os.listdir(os.path.join(base_path, Right_Folder)):
        #Check if the file is a .jpg file and does not already start with "right_"
        if filename.endswith('.jpg') and not filename.startswith('{ObsID}R_'):
            #Adds "right_" before filename
            new_filename = str("{ObsID}R_" + filename)
            os.rename(filename, new_filename)