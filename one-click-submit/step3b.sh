#!/bin/bash -l

#SBATCH --partition=aa100
#SBATCH --nodes=1
#SBATCH --gres=gpu:1
#SBATCH --mem=30G
#SBATCH --ntasks=10
#SBATCH --time=3:00:00
#SBATCH --output=./logs/%j.out # Create a logs folder in your wd if it does not already exist! 
#SBATCH --error=./logs/%j.err
#SBATCH --qos=normal
#SBATCH --account=ucb689_peak1
#SBATCH --mail-type=ALL

module load miniforge
mamba activate glomap_env

echo "Processing patch match stereo for $chunk_file."
colmap patch_match_stereo --workspace_path ${PROJECT_DIR}/dense --PatchMatchStereo.geom_consistency=false --PatchMatchStereo.filter=true --PatchMatchStereo.max_image_size=1500 --PatchMatchStereo.window_step=2 --PatchMatchStereo.num_iterations=3 --PatchMatchStereo.num_samples=15 --PatchMatchStereo.gpu_index=0 --config_path "${PROJECT_DIR}/dense/stereo/${chunk_file}"