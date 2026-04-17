#!/bin/bash -l
#SBATCH --partition=aa100
#SBATCH --nodes=1
#SBATCH --gres=gpu:1
#SBATCH --ntasks=21
#SBATCH --time=4:00:00
#SBATCH --output=./logs/%j.out # Create a logs folder in your wd if it does not already exist! 
#SBATCH --error=./logs/%j.err
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

### This script should run image re-organization, then COLMAP feature extraction, and feature matching

# Load glomap environment and 
module load miniforge
mamba activate /projects/maha7624/software/anaconda/envs/glomap_env

cd "$scripts_dir"

# Run step 1 of the pipeline: Re-organize images and run feature matching --> dense reconstruction
############# GPU NEEDED: Requires ~2 GPU for ~ 4-5 hours ###############
# build command
cmd=(
    python runCOLMAP.py
    --project_dir="$PROJECT_DIR"
    --folder_path_L="$frames_path_L"
    --folder_path_R="$frames_path_R"
    --vocab_tree_path="$vocab_tree_path"
    --extracted_fps=$extracted_fps
    --final_fps=$final_fps
    --mode="$mode"
    --no_run_sparse
    --no_run_dense
)
if [[ "$rename_images" == "False" ]]; then
    cmd+=(--no_rename_images)
fi

if [[ "$run_feat_ext_match" == "False" ]]; then
    cmd+=(--no_run_feat_ext_match)
fi

# Run the COLMAP command
printf 'Running command:\n'
printf '  %q' "${cmd[@]}"
printf '\n'
"${cmd[@]}"

echo 'End of Step 1: Image Reorganization and feature extraction/matching'