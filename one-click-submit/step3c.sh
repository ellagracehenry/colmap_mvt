#!/bin/bash -l
#SBATCH --partition=amem
#SBATCH --qos=mem-normal
#SBATCH --nodes=1
#SBATCH --ntasks=50
#SBATCH --mem=256G
#SBATCH --time=2:00:00
#SBATCH --output=./logs/%j.out
#SBATCH --error=./logs/%j.err
#SBATCH --mail-type=ALL
#SBATCH --account=ucb689_peak1

module purge
module load miniforge
mamba activate /projects/maha7624/software/anaconda/envs/glomap_env

colmap stereo_fusion \
    --workspace_path ${PROJECT_DIR}/dense \
    --workspace_format COLMAP \
    --input_type photometric \
    --StereoFusion.max_image_size 1500 \
    --StereoFusion.num_threads 32 \
    --output_path ${PROJECT_DIR}/dense/fused.ply

echo "stereo_fusion complete"