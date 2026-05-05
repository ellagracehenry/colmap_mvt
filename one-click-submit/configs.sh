#### Global parameters  ####
## Applied to every trial ##
ROOT_DIR="/scratch/alpine/maha7624/3D_Tracking/2024_FF"
scripts_dir="/projects/maha7624/3D_Tracking/one-click-submit"
vocab_tree_path="/projects/maha7624/3D_Tracking/one-click-submit/vocab_tree_flickr100K_words256K.bin"
email="maha7624@colorado.edu"
errors_csv_path="/scratch/alpine/maha7624/3D_Tracking/2024_FF/SAM2_errors_ff_2024.csv"

##### To run specific processes. Can be set to True or False  #####

### Step1.sh processes ###
rename_images=True
run_feat_ext_match=True

### Step2.sh processes ###
run_sparse=True

sparse_chunk_size=500
sparse_chunk_overlap=100

### Step3.sh processes ###
run_dense=True
dense_chunk_num=3
dense_spat_overlap=5

### Step 4.sh processes ###
dense_mesh=True

## MultiViewTracks Parameters 
run_MVT=True
interpolate_points=False
err_threshold=0.1

extract_centroids=True

# Run Manual Mask Cleaner: Removes known errors associated in SAM2-errors.csv
# Note: Will execute with AMC turned-on regardless of specification here
run_MMC=True

# Run Automatic Mask Cleaner: Removes both known errors and unmarked errors from the SAM2 masks ** Unfortunately, still is overcorrecting
# Will still run if no observationID is found in the SAM2-errors.csv
run_AMC=False






#### Batch parameters  ####
## List a value for every trial you want to run ##

# This will be the name of the trial folder within your root dir
trial_names=(
    #"JM_153"
    "JM_151"
)
    
# Left frames
frames_paths_L=(
    #"/scratch/alpine/maha7624/3D_Tracking/2024_FF/frames/MH_JM_060724_153_L"
    "/scratch/alpine/maha7624/3D_Tracking/2024_FF/frames/MH_JM_060724_151_L"

)

# Right frames
frames_paths_R=(
    #"/scratch/alpine/maha7624/3D_Tracking/2024_FF/frames/MH_JM_060724_153_R"
    "/scratch/alpine/maha7624/3D_Tracking/2024_FF/frames/MH_JM_060724_151_R"

)

# Left SAM2 Masks
masks_paths_L=(
   # "/scratch/alpine/maha7624/3D_Tracking/2024_FF/masks/CR_JM_060724_153_playa_largu_scuba_TPScv_L_mask.pkl"
    "/scratch/alpine/maha7624/3D_Tracking/2024_FF/masks/CR_JM_060724_151_playa_largu_scuba_TPScv_L_mask.pkl"


)

# Right SAM2 Masks
masks_paths_R=(
    #"/scratch/alpine/maha7624/3D_Tracking/2024_FF/masks/CR_JM_060724_153_playa_largu_scuba_TPScv_R_mask.pkl"
    "/scratch/alpine/maha7624/3D_Tracking/2024_FF/masks/CR_JM_060724_151_playa_largu_scuba_TPScv_R_mask.pkl"

)


# Left ObservationID as specified in errors.csv
observation_ids_L=(
    #"JM_060724_153_playa_largu_scuba_TPScv_L"
    "JM_060724_151_playa_largu_scuba_TPScv_L"
)

# Right ObservationID as specified in errors.csv
observation_ids_R=(
   # "JM_060724_153_playa_largu_scuba_TPScv_R"
    "JM_060724_151_playa_largu_scuba_TPScv_R"
)

# Left Annotations Path
annotations_paths_L=(
   # "/scratch/alpine/maha7624/3D_Tracking/2024_FF/annotations/annotations_processed_sam2/CR_JM_060724_153_playa_largu_scuba_TPScv_L_annotations.npy"
    "/scratch/alpine/maha7624/3D_Tracking/2024_FF/annotations/annotations_processed_sam2/CR_JM_060724_151_playa_largu_scuba_TPScv_L_annotations.npy"
)

# Left Annotations Path
annotations_paths_R=(
   # "/scratch/alpine/maha7624/3D_Tracking/2024_FF/annotations/annotations_processed_sam2/CR_JM_060724_153_playa_largu_scuba_TPScv_R_annotations.npy"
    "/scratch/alpine/maha7624/3D_Tracking/2024_FF/annotations/annotations_processed_sam2/CR_JM_060724_151_playa_largu_scuba_TPScv_R_annotations.npy"
    )

# Intercamera distances
world_distances=(
   # 0.8442
   1.0105
)

# Frame rate that was originally extracted (almost always 3)
extracted_fpss=(
   # 3
    3
)

# Desired frame rate to process through COLMAP --> MVT
final_fpss=(
    #1
   1
)