#!/bin/bash -l
#SBATCH --partition=amilan
#SBATCH --nodes=1
#SBATCH --ntasks=30
#SBATCH --output=./logs/%j.out # Create a logs folder in your wd if it does not already exist! 
#SBATCH --error=./logs/%j.err
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1

cd "$scripts_dir"

# Load glomap environment and 
module load miniforge
mamba activate /projects/maha7624/software/anaconda/envs/glomap_env

# Run step 2 of the pipeline: Sparse Reconstruction Only

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
    --no_rename_images
    --no_run_feat_ext_match
    --no_run_dense
)
if [[ "$run_sparse" == "False" ]]; then
    cmd+=(--no_run_sparse)
fi

# Run the COLMAP command
printf 'Running command:\n'
printf '  %q' "${cmd[@]}"
printf '\n'
"${cmd[@]}"

echo 'End of Step 2: Sparse Reconstruction'